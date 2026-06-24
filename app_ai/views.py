from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import threading
import json
import os
import polib
import anthropic
import time

# Global variables to track translation progress
translation_in_progress = False
translation_progress = {
    'total': 0,
    'processed': 0,
    'ru_translated': 0,
    'ru_skipped': 0,
    'uk_translated': 0,
    'uk_skipped': 0,
    'log': []
}
translation_stop_requested = False
# Store preview translations: {language: {entry_index: {'msgid': str, 'msgstr': str, 'entry_data': dict}}}
preview_translations = {}

# Global variables to track fuzzy fix progress
fuzzy_fix_in_progress = False
fuzzy_fix_progress = {
    'total': 0,
    'processed': 0,
    'ru_fixed': 0,
    'ru_skipped': 0,
    'uk_fixed': 0,
    'uk_skipped': 0,
    'log': []
}
fuzzy_fix_stop_requested = False
# Store fuzzy fix preview translations: {language: {entry_index: {'msgid': str, 'msgstr_old': str, 'msgstr_new': str}}}
fuzzy_fix_preview = {}


def _get_po_path(language):
    """Helper to find PO file path for a given language code (ru or uk)."""
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
    possible_dirs = ['SecBoard', 'SecBoard_develop']
    for dir_name in possible_dirs:
        path = os.path.join(PROJECT_ROOT, dir_name, 'locale', language, 'LC_MESSAGES', 'django.po')
        if os.path.exists(path):
            return path
    return os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', language, 'LC_MESSAGES', 'django.po')


def _log_fuzzy(message):
    """Add a message to the fuzzy fix log."""
    global fuzzy_fix_progress
    fuzzy_fix_progress['log'].append({
        'time': time.strftime('%H:%M:%S'),
        'message': message
    })


def _translate_text(msgid, target_lang, selected_model):
    """
    Translate a single msgid string using the selected AI/translation model.
    Returns the translated string or raises an exception.
    """
    from app_conf.translate_po_views import (
        generate_translation_prompt, remove_apostrophes,
        preserve_format_strings, format_msgstr_like_msgid
    )

    if selected_model == 'google_translate':
        from deep_translator import GoogleTranslator
        lang_map = {'Russian': 'ru', 'russian': 'ru', 'Ukrainian': 'uk', 'ukrainian': 'uk'}
        translator = GoogleTranslator(source='en', target=lang_map.get(target_lang, 'ru'))
        translation = translator.translate(msgid)

    elif selected_model == 'claude':
        from .models import APISettingsClaude
        import anthropic as _anthropic
        claude_settings = APISettingsClaude.objects.first()
        if not claude_settings or not claude_settings.model_name:
            raise Exception("Claude settings or model not configured")
        client = _anthropic.Anthropic(api_key=claude_settings.api_key)
        prompt = generate_translation_prompt(msgid, target_lang)
        response = client.messages.create(
            model=claude_settings.model_name.model_id,
            max_tokens=claude_settings.max_tokens,
            temperature=claude_settings.temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        translation = response.content[0].text.strip()

    elif selected_model == 'google':
        import google.generativeai as genai
        from .models import APISettingsGoogle
        google_settings = APISettingsGoogle.objects.first()
        if not google_settings or not google_settings.model_name:
            raise Exception("Google settings or model not configured")
        genai.configure(api_key=google_settings.api_key)
        model = genai.GenerativeModel(google_settings.model_name.model_id)
        prompt = generate_translation_prompt(msgid, target_lang)
        response = model.generate_content(prompt)
        translation = response.text.strip()

    elif selected_model == 'groq':
        from groq import Groq
        from .models import APISettingsGroq
        groq_settings = APISettingsGroq.objects.first()
        if not groq_settings or not groq_settings.model_name:
            raise Exception("Groq settings or model not configured")
        client = Groq(api_key=groq_settings.api_key)
        prompt = generate_translation_prompt(msgid, target_lang)
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a translation assistant. Provide only the translation."},
                {"role": "user", "content": prompt}
            ],
            model=groq_settings.model_name.model_id,
        )
        translation = response.choices[0].message.content.strip()

    elif selected_model == 'ollama':
        from ollama import Client
        from .models import APISettingsOllama
        ollama_settings = APISettingsOllama.objects.first()
        if not ollama_settings or not ollama_settings.model_name:
            raise Exception("Ollama settings or model not configured")
        client = Client(host=ollama_settings.api_url)
        prompt = generate_translation_prompt(msgid, target_lang)
        response = client.chat(
            model=ollama_settings.model_name.model_id,
            messages=[
                {"role": "system", "content": "You are a translation assistant. Provide only the translation."},
                {"role": "user", "content": prompt}
            ]
        )
        translation = response.message.content.strip()

    elif selected_model == 'deepseek':
        from openai import OpenAI
        from .models import APISettingsDeepSeek
        deepseek_settings = APISettingsDeepSeek.objects.first()
        if not deepseek_settings or not deepseek_settings.model_name:
            raise Exception("DeepSeek settings or model not configured")
        client = OpenAI(api_key=deepseek_settings.api_key, base_url="https://api.deepseek.com/v1")
        prompt = generate_translation_prompt(msgid, target_lang)
        response = client.chat.completions.create(
            model=deepseek_settings.model_name.model_id,
            messages=[
                {"role": "system", "content": "You are a translation assistant. Provide only the translation."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=deepseek_settings.max_tokens,
            temperature=deepseek_settings.temperature
        )
        translation = response.choices[0].message.content.strip()

    else:
        raise Exception(f"Unknown model: {selected_model}")

    translation = remove_apostrophes(translation)
    translation = preserve_format_strings(msgid, translation)
    translation = format_msgstr_like_msgid(msgid, translation)
    return translation


def _run_fuzzy_fix_process():
    """Background thread: translate all fuzzy entries and optionally save directly."""
    global fuzzy_fix_in_progress, fuzzy_fix_progress, fuzzy_fix_stop_requested, fuzzy_fix_preview

    try:
        fuzzy_fix_stop_requested = False
        selected_model = fuzzy_fix_progress.get('selected_model', 'google_translate')
        config = fuzzy_fix_progress.get('config', {})
        fix_russian = config.get('fix_russian', True)
        fix_ukrainian = config.get('fix_ukrainian', True)
        preview_mode = config.get('preview_mode', True)

        _log_fuzzy(f"Starting fuzzy fix process using {selected_model}...")
        _log_fuzzy(f"Languages: RU={'Yes' if fix_russian else 'No'}, UK={'Yes' if fix_ukrainian else 'No'}")

        # Collect fuzzy entries per language
        tasks = []
        if fix_russian:
            ru_path = _get_po_path('ru')
            if os.path.exists(ru_path):
                ru_po = polib.pofile(ru_path)
                for idx, entry in enumerate(ru_po):
                    if 'fuzzy' in entry.flags:
                        tasks.append(('ru', ru_path, idx, entry.msgid, entry.msgstr))
                _log_fuzzy(f"Russian: {sum(1 for t in tasks if t[0]=='ru')} fuzzy entries found")
            else:
                _log_fuzzy(f"Russian PO file not found: {ru_path}")

        if fix_ukrainian:
            uk_path = _get_po_path('uk')
            if os.path.exists(uk_path):
                uk_po = polib.pofile(uk_path)
                for idx, entry in enumerate(uk_po):
                    if 'fuzzy' in entry.flags:
                        tasks.append(('uk', uk_path, idx, entry.msgid, entry.msgstr))
                _log_fuzzy(f"Ukrainian: {sum(1 for t in tasks if t[0]=='uk')} fuzzy entries found")
            else:
                _log_fuzzy(f"Ukrainian PO file not found: {uk_path}")

        fuzzy_fix_progress['total'] = len(tasks)
        if len(tasks) == 0:
            _log_fuzzy("No fuzzy entries found. Nothing to fix.")
            fuzzy_fix_in_progress = False
            return

        # Translate each fuzzy entry
        for i, (lang, po_path, entry_idx, msgid, msgstr_old) in enumerate(tasks, 1):
            if fuzzy_fix_stop_requested:
                _log_fuzzy("Fuzzy fix process stopped by user.")
                break

            fuzzy_fix_progress['processed'] = i
            lang_label = 'RU' if lang == 'ru' else 'UK'
            target_lang = 'Russian' if lang == 'ru' else 'Ukrainian'
            _log_fuzzy(f"--- [{lang_label}] Entry {i}/{len(tasks)} ---")
            _log_fuzzy(f"msgid: {msgid[:100]}...")
            _log_fuzzy(f"old msgstr: {str(msgstr_old)[:80]}...")

            try:
                new_translation = _translate_text(msgid, target_lang, selected_model)
                _log_fuzzy(f"new msgstr: {new_translation[:80]}...")

                if lang not in fuzzy_fix_preview:
                    fuzzy_fix_preview[lang] = {}
                fuzzy_fix_preview[lang][str(entry_idx)] = {
                    'msgid': msgid,
                    'msgstr_old': str(msgstr_old),
                    'msgstr_new': new_translation,
                }

                if lang == 'ru':
                    fuzzy_fix_progress['ru_fixed'] += 1
                else:
                    fuzzy_fix_progress['uk_fixed'] += 1

            except Exception as e:
                _log_fuzzy(f"  X Error: {str(e)}")
                if lang == 'ru':
                    fuzzy_fix_progress['ru_skipped'] += 1
                else:
                    fuzzy_fix_progress['uk_skipped'] += 1

            time.sleep(0.5)

        if not preview_mode:
            # Apply directly to PO files
            _log_fuzzy("Applying fixes directly to PO files...")
            _apply_fuzzy_fixes_to_files(fuzzy_fix_preview)
            fuzzy_fix_preview = {}
            _log_fuzzy("Done! Run 'python manage.py compilemessages' to apply changes.")
        else:
            _log_fuzzy("Preview ready. Review translations before saving.")

    except Exception as e:
        _log_fuzzy(f"An error occurred: {str(e)}")
    finally:
        fuzzy_fix_in_progress = False
        fuzzy_fix_stop_requested = False


def _apply_fuzzy_fixes_to_files(fixes):
    """Write fixed translations to PO files and remove fuzzy flags."""
    for lang, entries in fixes.items():
        po_path = _get_po_path(lang)
        if not os.path.exists(po_path):
            continue
        po = polib.pofile(po_path)
        for entry_idx_str, fix_data in entries.items():
            try:
                idx = int(entry_idx_str)
                if 0 <= idx < len(po):
                    entry = po[idx]
                    if entry.msgid == fix_data['msgid']:
                        entry.msgstr = fix_data['msgstr_new']
                        entry.flags = [f for f in entry.flags if f != 'fuzzy']
                        entry.previous_msgid = None
                        entry.previous_msgid_plural = None
                        entry.previous_msgctxt = None
            except (ValueError, IndexError):
                continue
        po.save()


def is_superuser(user):
    """Check if user is superuser or has options access"""
    if not user.is_authenticated:
        return False
    
    # Allow superusers
    if user.is_superuser:
        return True
    
    # Allow users with options access through AccessOption model
    from app_conf.models import AccessOption
    return AccessOption.user_has_options_access(user)

@user_passes_test(is_superuser)
def translate_po_page(request):
    """
    Page to run PO file translations using AI
    """
    # Get project root
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
    
    # Get translation file paths - check both possible directories
    possible_dirs = ['SecBoard', 'SecBoard_develop']
    ru_po_file_path = None
    uk_po_file_path = None
    
    for dir_name in possible_dirs:
        ru_path = os.path.join(PROJECT_ROOT, dir_name, 'locale', 'ru', 'LC_MESSAGES', 'django.po')
        uk_path = os.path.join(PROJECT_ROOT, dir_name, 'locale', 'uk', 'LC_MESSAGES', 'django.po')
        
        if os.path.exists(ru_path) and ru_po_file_path is None:
            ru_po_file_path = ru_path
        if os.path.exists(uk_path) and uk_po_file_path is None:
            uk_po_file_path = uk_path
            
        if ru_po_file_path and uk_po_file_path:
            break
    
    # Fallback to SecBoard if neither path is found (shouldn't happen but just in case)
    if not ru_po_file_path:
        ru_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'ru', 'LC_MESSAGES', 'django.po')
    if not uk_po_file_path:
        uk_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'uk', 'LC_MESSAGES', 'django.po')
    
    try:
        # Get AI settings from models
        from .models import APISettingsClaude, APISettingsGoogle, APISettingsGroq, APISettingsOllama, APISettingsDeepSeek
        claude_settings = APISettingsClaude.objects.first()
        google_settings = APISettingsGoogle.objects.first()
        groq_settings = APISettingsGroq.objects.first()
        ollama_settings = APISettingsOllama.objects.first()
        deepseek_settings = APISettingsDeepSeek.objects.first()
        
        # Create a list of available AI models
        available_models = []
        # Add Google Translator (free, no API key required)
        available_models.append(('google_translate', 'Google Translator (Free, No API Key)'))
        if claude_settings and claude_settings.model_name:
            available_models.append(('claude', f'Claude - {claude_settings.model_name.model_name}'))
        if google_settings and google_settings.model_name:
            available_models.append(('google', f'Google Gemini - {google_settings.model_name.model_id}'))
        if groq_settings and groq_settings.model_name:
            available_models.append(('groq', f'Groq - {groq_settings.model_name.model_name}'))
        if ollama_settings and ollama_settings.model_name:
            available_models.append(('ollama', f'Ollama - {ollama_settings.model_name.model_id}'))
        if deepseek_settings and deepseek_settings.model_name:
            available_models.append(('deepseek', f'DeepSeek - {deepseek_settings.model_name.model_name}'))
            
    except Exception as e:
        claude_settings = None
        google_settings = None
        groq_settings = None
        ollama_settings = None
        deepseek_settings = None
        available_models = []
        messages.error(request, f"Error loading AI settings: {str(e)}")
    
    # Check if files exist
    ru_file_exists = os.path.exists(ru_po_file_path)
    uk_file_exists = os.path.exists(uk_po_file_path)
    
    # If both files exist, count untranslated and fuzzy strings
    ru_untranslated = 0
    uk_untranslated = 0
    ru_fuzzy = 0
    uk_fuzzy = 0

    if ru_file_exists:
        try:
            ru_po = polib.pofile(ru_po_file_path)
            ru_untranslated = len([e for e in ru_po if not is_entry_translated(e)])
            ru_fuzzy = len([e for e in ru_po if 'fuzzy' in e.flags])
        except Exception as e:
            messages.error(request, f"Error reading Russian PO file: {str(e)}")
            
    if uk_file_exists:
        try:
            uk_po = polib.pofile(uk_po_file_path)
            uk_untranslated = len([e for e in uk_po if not is_entry_translated(e)])
            uk_fuzzy = len([e for e in uk_po if 'fuzzy' in e.flags])
        except Exception as e:
            messages.error(request, f"Error reading Ukrainian PO file: {str(e)}")
    
    context = {
        'ru_file_exists': ru_file_exists,
        'uk_file_exists': uk_file_exists,
        'ru_untranslated': ru_untranslated,
        'uk_untranslated': uk_untranslated,
        'ru_fuzzy': ru_fuzzy,
        'uk_fuzzy': uk_fuzzy,
        'fuzzy_fix_in_progress': fuzzy_fix_in_progress,
        'translation_in_progress': translation_in_progress,
        'claude_settings': claude_settings,
        'google_settings': google_settings,
        'groq_settings': groq_settings,
        'ollama_settings': ollama_settings,
        'deepseek_settings': deepseek_settings,
        'available_models': available_models,
    }
    
    return render(request, 'app_conf/translate_po.html', context)

@user_passes_test(is_superuser)
@csrf_exempt
def start_translation(request):
    """Start the translation process in a background thread"""
    global translation_in_progress, translation_progress
    
    if translation_in_progress:
        return JsonResponse({
            'success': False,
            'message': 'Translation is already in progress'
        })
    
    # Get data from request
    data = json.loads(request.body)
    selected_model = data.get('model', 'claude')  # Default to Claude if not specified
    
    # Get configuration options
    config = data.get('config', {})
    translate_russian = config.get('translateRussian', True)
    translate_ukrainian = config.get('translateUkrainian', True)
    clear_fuzzy = config.get('clearFuzzy', True)
    clear_existing = config.get('clearExisting', False)
    only_empty = config.get('onlyEmpty', True)
    remove_comments = config.get('removeComments', False)
    preview_mode = config.get('previewMode', False)
    
    # Reset progress tracking
    translation_progress = {
        'total': 0,
        'processed': 0,
        'ru_translated': 0,
        'ru_skipped': 0,
        'uk_translated': 0,
        'uk_skipped': 0,
        'log': [],
        'selected_model': selected_model,
        'preview_mode': preview_mode,
        'config': {
            'translate_russian': translate_russian,
            'translate_ukrainian': translate_ukrainian,
            'clear_fuzzy': clear_fuzzy,
            'clear_existing': clear_existing,
            'only_empty': only_empty,
            'remove_comments': remove_comments,
            'preview_mode': preview_mode
        }
    }
    
    # Clear preview translations if starting new translation
    global preview_translations
    preview_translations = {}
    
    # Start translation in background thread
    translation_in_progress = True
    thread = threading.Thread(target=run_translation_process)
    thread.daemon = True
    thread.start()
    
    return JsonResponse({
        'success': True,
        'message': 'Translation process started'
    })

@user_passes_test(is_superuser)
def get_translation_progress(request):
    """Get the current progress of the translation process"""
    global translation_in_progress, translation_progress
    
    # Include preview_mode in progress if it exists
    progress_data = translation_progress.copy()
    if 'preview_mode' not in progress_data:
        progress_data['preview_mode'] = False
    
    return JsonResponse({
        'in_progress': translation_in_progress,
        'progress': progress_data
    })

@user_passes_test(is_superuser)
@csrf_exempt
def stop_translation(request):
    """Stop the translation process"""
    global translation_in_progress, translation_stop_requested
    
    if not translation_in_progress:
        return JsonResponse({
            'success': False,
            'message': 'No translation is currently in progress'
        })
    
    # Set the stop flag
    translation_stop_requested = True
    log_message("Stop translation requested by user - will complete current entry and then stop")
    
    return JsonResponse({
        'success': True,
        'message': 'Stop translation requested'
    })

def log_message(message):
    """Add a message to the log"""
    global translation_progress
    translation_progress['log'].append({
        'time': time.strftime('%H:%M:%S'),
        'message': message
    })
    print(message)

def is_entry_translated(entry):
    """
    Check if an entry already has a translation, including multiline translations.
    Returns True if the entry has any non-empty translation.
    """
    if isinstance(entry.msgstr, list):
        # Handle plural forms
        return any(bool(str_value.strip()) for str_value in entry.msgstr)
    else:
        # Handle single translations
        return bool(str(entry.msgstr).strip())

def remove_apostrophes(text):
    """Remove apostrophes from the translation"""
    return text.replace("'", "").replace("'", "").replace("'", "")

def format_msgstr_like_msgid(msgid, msgstr):
    """
    Format msgstr to match the structure of msgid.
    If msgid is multiline (starts with ""), make msgstr multiline too.
    """
    if not msgid or not msgstr:
        return msgstr
    
    # Check if msgid is multiline format (starts with empty string)
    if msgid.startswith('""'):
        # Extract the actual text from msgid to understand its structure
        msgid_lines = msgid.split('\n')
        if len(msgid_lines) > 1:
            # Build multiline msgstr format
            msgstr_lines = ['""']
            
            # Split msgstr into parts that match msgid structure
            msgstr_content = msgstr.strip()
            
            # For multiline entries, try to preserve the structure
            # but put the translated content appropriately
            for i, line in enumerate(msgid_lines[1:], 1):
                if line.strip().startswith('"') and line.strip().endswith('"'):
                    # This is a content line
                    if i == 1:
                        # First content line - put the translated text here
                        content = line.strip()[1:-1]  # Remove quotes
                        if content.startswith('\\n'):
                            # Preserve leading newline
                            msgstr_lines.append(f'"\\n"')
                            msgstr_lines.append(f'"{msgstr_content}\\n"')
                        else:
                            msgstr_lines.append(f'"{msgstr_content}\\n"')
                    else:
                        # Subsequent lines - usually whitespace/formatting
                        content = line.strip()[1:-1]  # Remove quotes
                        if content.strip():
                            # If there's actual content, use empty string for structure
                            msgstr_lines.append('""')
                        else:
                            # Preserve whitespace structure
                            msgstr_lines.append(line.strip())
            
            return '\n'.join(msgstr_lines)
    
    return msgstr

def preserve_format_strings(original_msgid, translated_msgstr):
    """
    Preserve format strings and placeholders from msgid in msgstr.
    This prevents format string errors by ensuring consistency.
    """
    import re
    
    if not original_msgid or not translated_msgstr:
        return translated_msgstr
    
    # Preserve Python format placeholders like %(variable)s
    python_format_pattern = r'%\([^)]+\)[sd]'
    python_formats = re.findall(python_format_pattern, original_msgid)
    
    # Preserve percentage signs (single % and double %%)
    # Count double percentages in original
    double_percent_count = original_msgid.count('%%')
    single_percent_count = original_msgid.count('%') - (double_percent_count * 2)
    
    # Fix common format issues in translation
    fixed_msgstr = translated_msgstr
    
    # Fix comma vs period in percentages (Ukrainian/Russian often use commas)
    # Find patterns like "99,2%" and replace with "99.2%" if original has periods
    if '.' in original_msgid and '%' in original_msgid:
        # Replace comma-decimal with period-decimal in percentages
        fixed_msgstr = re.sub(r'(\d+),(\d+)%', r'\1.\2%', fixed_msgstr)
    
    # Ensure double percentages are preserved
    if double_percent_count > 0:
        # Find single % followed by space or punctuation and convert to %%
        # but avoid Python format placeholders
        for python_fmt in python_formats:
            fixed_msgstr = fixed_msgstr.replace(python_fmt, f"__PYTHON_FMT_{len(python_formats)}__")
        
        # Fix single % that should be double %%
        # Look for percentages that are not part of Python format strings
        pattern = r'(\d+(?:\.\d+)?)%(?![%s])'
        if re.search(pattern, original_msgid.replace('%%', '__DOUBLE_PERCENT__')):
            # Original has literal percentages, ensure they're double in translation
            fixed_msgstr = re.sub(pattern, r'\1%%', fixed_msgstr)
        
        # Restore Python format placeholders
        for i, python_fmt in enumerate(python_formats):
            fixed_msgstr = fixed_msgstr.replace(f"__PYTHON_FMT_{i}__", python_fmt)
    
    # Ensure all Python format placeholders are present
    for python_fmt in python_formats:
        if python_fmt not in fixed_msgstr:
            log_message(f"WARNING: Python format placeholder {python_fmt} missing in translation")
    
    return fixed_msgstr

def validate_translation(msgid, msgstr):
    """
    Validate that the translation doesn't have obvious format issues.
    Returns (is_valid, error_message)
    """
    import re
    
    if not msgid or not msgstr:
        return True, ""
    
    errors = []
    
    # Check Python format placeholders
    msgid_python_formats = set(re.findall(r'%\([^)]+\)[sd]', msgid))
    msgstr_python_formats = set(re.findall(r'%\([^)]+\)[sd]', msgstr))
    
    if msgid_python_formats != msgstr_python_formats:
        missing = msgid_python_formats - msgstr_python_formats
        extra = msgstr_python_formats - msgid_python_formats
        if missing:
            errors.append(f"Missing format placeholders: {missing}")
        if extra:
            errors.append(f"Extra format placeholders: {extra}")
    
    # Check multiline format consistency
    msgid_is_multiline = msgid.startswith('""')
    msgstr_is_multiline = msgstr.startswith('""')
    
    if msgid_is_multiline and not msgstr_is_multiline:
        errors.append("msgid is multiline but msgstr is single line")
    
    return len(errors) == 0, "; ".join(errors)

def generate_translation_prompt(msgid, target_lang):
    """
    Generate an improved translation prompt that includes specific formatting requirements
    to prevent common PO file errors.
    """
    # Check if msgid contains format placeholders
    import re
    has_python_formats = bool(re.search(r'%\([^)]+\)[sd]', msgid))
    has_double_percent = '%%' in msgid
    has_decimal_numbers = bool(re.search(r'\d+\.\d+', msgid))
    
    base_prompt = f"Translate the following text from English to {target_lang}. The context of this translation is related to information security / cybersecurity domain."
    
    requirements = [
        "Provide only the translation, without any additional comments or apostrophes"
    ]
    
    if has_python_formats:
        requirements.append("Preserve all format placeholders like %(variable)s exactly as they appear - do not translate or modify them")
    
    if has_double_percent:
        requirements.append("Keep double percentage signs (%%) as double signs - do not convert to single %")
    
    if has_decimal_numbers:
        requirements.append("Use periods (not commas) in decimal numbers (e.g., 99.2%% not 99,2%%)")
    
    requirements.append("Maintain the same structure and formatting as the original")
    
    prompt = f"""{base_prompt}

Important requirements:
{chr(10).join(f"{i+1}. {req}" for i, req in enumerate(requirements))}

Text to translate:
{msgid}"""
    
    return prompt

def clear_entry_translation(entry):
    """Clear the translation in a PO entry"""
    if isinstance(entry.msgstr, list):
        entry.msgstr = [''] * len(entry.msgstr)
    else:
        entry.msgstr = ''

def clean_po_file(po_file, config):
    """Clean up PO file based on configuration"""
    for entry in po_file:
        # Clear fuzzy flags if requested
        if config.get('clear_fuzzy', True):
            entry.flags = [flag for flag in entry.flags if flag != 'fuzzy']
        
        # Clear existing translations if requested
        if config.get('clear_existing', False):
            clear_entry_translation(entry)
        
        # Remove comments if requested
        if config.get('remove_comments', False):
            entry.comment = ''
            entry.tcomment = ''
        
        # Always clear previous msgid/msgstr info
        entry.previous_msgid = None
        entry.previous_msgid_plural = None
        entry.previous_msgctxt = None

def translate_entry_ai(entry, target_lang, selected_model, config, entry_index=None):
    """Translate a single PO entry using the selected AI model"""
    global translation_progress, preview_translations
    
    try:
        # Clear existing translation if needed, even if not empty
        # This ensures we're not mixing old and new translations
        if config.get('clear_existing', False) and not config.get('only_empty', True):
            clear_entry_translation(entry)
        
        translation = ""
        
        if selected_model == 'claude':
            from .models import APISettingsClaude
            claude_settings = APISettingsClaude.objects.first()
            if not claude_settings or not claude_settings.model_name:
                raise Exception("Claude settings or model not configured")
                
            client = anthropic.Anthropic(api_key=claude_settings.api_key)
            
            prompt = generate_translation_prompt(entry.msgid, target_lang)
            
            response = client.messages.create(
                model=claude_settings.model_name.model_id,
                max_tokens=claude_settings.max_tokens,
                temperature=claude_settings.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            translation = response.content[0].text.strip()
            
        elif selected_model == 'google':
            import google.generativeai as genai
            from .models import APISettingsGoogle
            
            google_settings = APISettingsGoogle.objects.first()
            if not google_settings or not google_settings.model_name:
                raise Exception("Google settings or model not configured")
                
            genai.configure(api_key=google_settings.api_key)
            model = genai.GenerativeModel(google_settings.model_name.model_id)
            
            prompt = generate_translation_prompt(entry.msgid, target_lang)
            
            response = model.generate_content(prompt)
            translation = response.text.strip()
            
        elif selected_model == 'groq':
            from groq import Groq
            from .models import APISettingsGroq
            
            groq_settings = APISettingsGroq.objects.first()
            if not groq_settings or not groq_settings.model_name:
                raise Exception("Groq settings or model not configured")
                
            client = Groq(api_key=groq_settings.api_key)
            
            prompt = generate_translation_prompt(entry.msgid, target_lang)
            
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a translation assistant. Provide only the translation."},
                    {"role": "user", "content": prompt}
                ],
                model=groq_settings.model_name.model_id,
            )
            
            translation = response.choices[0].message.content.strip()
            
        elif selected_model == 'ollama':
            from ollama import Client
            from .models import APISettingsOllama
            
            ollama_settings = APISettingsOllama.objects.first()
            if not ollama_settings or not ollama_settings.model_name:
                raise Exception("Ollama settings or model not configured")
                
            client = Client(host=ollama_settings.api_url)
            
            prompt = generate_translation_prompt(entry.msgid, target_lang)
            
            response = client.chat(
                model=ollama_settings.model_name.model_id,
                messages=[
                    {"role": "system", "content": "You are a translation assistant. Provide only the translation."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            translation = response.message.content.strip()
            
        elif selected_model == 'deepseek':
            from openai import OpenAI
            from .models import APISettingsDeepSeek
            
            deepseek_settings = APISettingsDeepSeek.objects.first()
            if not deepseek_settings or not deepseek_settings.model_name:
                raise Exception("DeepSeek settings or model not configured")
                
            client = OpenAI(api_key=deepseek_settings.api_key, base_url="https://api.deepseek.com/v1")
            
            prompt = generate_translation_prompt(entry.msgid, target_lang)
            
            response = client.chat.completions.create(
                model=deepseek_settings.model_name.model_id,
                messages=[
                    {"role": "system", "content": "You are a translation assistant. Provide only the translation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=deepseek_settings.max_tokens,
                temperature=deepseek_settings.temperature
            )
            
            translation = response.choices[0].message.content.strip()
            
        elif selected_model == 'google_translate':
            from deep_translator import GoogleTranslator
            
            # Map target language to language codes
            lang_map = {
                'Russian': 'ru',
                'russian': 'ru',
                'Ukrainian': 'uk',
                'ukrainian': 'uk'
            }
            
            target_lang_code = lang_map.get(target_lang, 'ru')
            
            # Use Google Translator (free, no API key required)
            translator = GoogleTranslator(source='en', target=target_lang_code)
            
            # Translate the text
            translation = translator.translate(entry.msgid)
        
        # Clean translation of any apostrophes
        cleaned_translation = remove_apostrophes(translation)

        if translation != cleaned_translation:
            log_message(f"  > Removed apostrophes")

        # Preserve format strings and fix format issues
        format_preserved_translation = preserve_format_strings(entry.msgid, cleaned_translation)
        
        if cleaned_translation != format_preserved_translation:
            log_message(f"  > Fixed format strings")
        
        # Format msgstr to match msgid structure (multiline format)
        properly_formatted_translation = format_msgstr_like_msgid(entry.msgid, format_preserved_translation)
        
        if format_preserved_translation != properly_formatted_translation:
            log_message(f"  > Formatted to match msgid structure")
        
        # Validate the final translation
        is_valid, error_message = validate_translation(entry.msgid, properly_formatted_translation)
        
        if not is_valid:
            log_message(f"  ! WARNING: Validation failed: {error_message}")
            # Still proceed with the translation but log the warning
        
        # Store translation in preview mode or apply directly
        preview_mode = config.get('preview_mode', False)
        if preview_mode and entry_index is not None:
            # Store in preview_translations instead of modifying entry
            lang_code = 'ru' if target_lang.lower() == 'russian' else 'uk'
            if lang_code not in preview_translations:
                preview_translations[lang_code] = {}
            
            preview_translations[lang_code][entry_index] = {
                'msgid': entry.msgid,
                'msgstr': properly_formatted_translation,
                'original_msgstr': entry.msgstr,  # Keep original for comparison
                'entry_data': {
                    'occurrences': entry.occurrences,
                    'comment': entry.comment,
                    'tcomment': entry.tcomment,
                    'flags': entry.flags.copy() if hasattr(entry.flags, 'copy') else list(entry.flags)
                }
            }
        else:
            # Apply translation directly (non-preview mode)
            entry.msgstr = properly_formatted_translation
        
        if target_lang.lower() == 'russian':
            translation_progress['ru_translated'] += 1
        else:
            translation_progress['uk_translated'] += 1
        
        return True
    except Exception as e:
        log_message(f"  X Error: {str(e)}")
        return False

def run_translation_process():
    """Run the full translation process for both Russian and Ukrainian PO files"""
    global translation_in_progress, translation_progress, translation_stop_requested
    
    try:
        translation_stop_requested = False
        selected_model = translation_progress.get('selected_model', 'claude')
        config = translation_progress.get('config', {
            'translate_russian': True,
            'translate_ukrainian': True,
            'clear_fuzzy': True,
            'clear_existing': False,
            'only_empty': True,
            'remove_comments': False
        })
        
        # Get language selection
        translate_russian = config.get('translate_russian', True)
        translate_ukrainian = config.get('translate_ukrainian', True)
        
        log_message(f"Starting PO file translation process using {selected_model}...")
        log_message(f"Target languages: Russian={'Yes' if translate_russian else 'No'}, Ukrainian={'Yes' if translate_ukrainian else 'No'}")
        log_message(f"Configuration: Clear fuzzy: {config['clear_fuzzy']}, " +
                   f"Clear existing: {config['clear_existing']}, " +
                   f"Only empty: {config['only_empty']}, " +
                   f"Remove comments: {config['remove_comments']}")
        
        # Get project root
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
        
        # Get translation file paths - check both possible directories
        possible_dirs = ['SecBoard', 'SecBoard_develop']
        ru_po_file_path = None
        uk_po_file_path = None
        
        # Only get paths for selected languages
        if translate_russian:
            for dir_name in possible_dirs:
                ru_path = os.path.join(PROJECT_ROOT, dir_name, 'locale', 'ru', 'LC_MESSAGES', 'django.po')
                if os.path.exists(ru_path):
                    ru_po_file_path = ru_path
                    break
            if not ru_po_file_path:
                ru_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'ru', 'LC_MESSAGES', 'django.po')
            log_message(f"Russian PO file path: {ru_po_file_path}")
        
        if translate_ukrainian:
            for dir_name in possible_dirs:
                uk_path = os.path.join(PROJECT_ROOT, dir_name, 'locale', 'uk', 'LC_MESSAGES', 'django.po')
                if os.path.exists(uk_path):
                    uk_po_file_path = uk_path
                    break
            if not uk_po_file_path:
                uk_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'uk', 'LC_MESSAGES', 'django.po')
            log_message(f"Ukrainian PO file path: {uk_po_file_path}")
        
        # Check if selected AI model is available
        model_available = False
        
        if selected_model == 'google_translate':
            # Google Translator is always available (no API key required)
            model_available = True
            log_message(f"Using Google Translator (free, no API key required)")
        elif selected_model == 'claude':
            from .models import APISettingsClaude
            settings = APISettingsClaude.objects.first()
            if settings:
                model_available = True
                log_message(f"Using Claude model: {settings.model_name.model_id}")
        elif selected_model == 'google':
            from .models import APISettingsGoogle
            settings = APISettingsGoogle.objects.first()
            if settings:
                model_available = True
                log_message(f"Using Google Gemini model: {settings.model_name.model_id}")
        elif selected_model == 'groq':
            from .models import APISettingsGroq
            settings = APISettingsGroq.objects.first()
            if settings:
                model_available = True
                log_message(f"Using Groq model: {settings.model_name.model_id}")
        elif selected_model == 'ollama':
            from .models import APISettingsOllama
            settings = APISettingsOllama.objects.first()
            if settings:
                model_available = True
                log_message(f"Using Ollama model: {settings.model_name.model_id}")
        elif selected_model == 'deepseek':
            from .models import APISettingsDeepSeek
            settings = APISettingsDeepSeek.objects.first()
            if settings:
                model_available = True
                log_message(f"Using DeepSeek model: {settings.model_name.model_id}")
                
        if not model_available:
            log_message(f"Error: Selected AI model '{selected_model}' is not available. Please configure it in the admin panel.")
            translation_in_progress = False
            return
        
        # Ensure the paths exist and open selected PO files
        ru_po = None
        uk_po = None
        
        if translate_russian:
            if not os.path.exists(ru_po_file_path):
                log_message(f"Error: Russian PO file does not exist: {ru_po_file_path}")
                translation_in_progress = False
                return
            ru_po = polib.pofile(ru_po_file_path)
            log_message(f"Opened Russian PO file: {ru_po_file_path}")
        
        if translate_ukrainian:
            if not os.path.exists(uk_po_file_path):
                log_message(f"Error: Ukrainian PO file does not exist: {uk_po_file_path}")
                translation_in_progress = False
                return
            uk_po = polib.pofile(uk_po_file_path)
            log_message(f"Opened Ukrainian PO file: {uk_po_file_path}")
        
        # Pre-process PO files based on configuration
        if config['clear_existing'] or config['clear_fuzzy'] or config['remove_comments']:
            log_message("Pre-processing PO files based on configuration...")
            if ru_po:
                clean_po_file(ru_po, config)
            if uk_po:
                clean_po_file(uk_po, config)
        
        # Collect empty (untranslated) entries if only_empty is enabled
        if config.get('only_empty', True):
            log_message("Collecting empty strings that need translation...")
            ru_entries_to_translate = []
            uk_entries_to_translate = []
            
            # Determine total entries from the first available PO file
            total_entries = len(ru_po) if ru_po else (len(uk_po) if uk_po else 0)
            
            # Collect Russian entries if selected
            if ru_po and translate_russian:
                for ru_entry in ru_po:
                    if not is_entry_translated(ru_entry):
                        ru_entries_to_translate.append(ru_entry)
            
            # Collect Ukrainian entries if selected
            if uk_po and translate_ukrainian:
                for uk_entry in uk_po:
                    if not is_entry_translated(uk_entry):
                        uk_entries_to_translate.append(uk_entry)
            
            total_ru_to_translate = len(ru_entries_to_translate)
            total_uk_to_translate = len(uk_entries_to_translate)
            ru_skipped_count = total_entries - total_ru_to_translate if translate_russian else 0
            uk_skipped_count = total_entries - total_uk_to_translate if translate_ukrainian else 0
            
            translation_progress['ru_skipped'] = ru_skipped_count
            translation_progress['uk_skipped'] = uk_skipped_count
            
            log_message(f"Total entries in PO files: {total_entries}")
            if translate_russian:
                log_message(f"Russian: {total_ru_to_translate} to translate, {ru_skipped_count} already translated")
            if translate_ukrainian:
                log_message(f"Ukrainian: {total_uk_to_translate} to translate, {uk_skipped_count} already translated")
            
            if total_ru_to_translate == 0 and total_uk_to_translate == 0:
                log_message("No empty strings found. All entries are already translated!")
                translation_in_progress = False
                return
            
            translation_progress['total'] = total_ru_to_translate + total_uk_to_translate
            
            # Translate Russian entries (only if selected)
            if translate_russian and total_ru_to_translate > 0:
                log_message("="*60)
                log_message(f"[RUSSIAN TRANSLATION] Translating {total_ru_to_translate} entries...")
                log_message("="*60)
                for i, ru_entry in enumerate(ru_entries_to_translate, 1):
                    if translation_stop_requested:
                        log_message("Translation process stopped by user")
                        break
                    
                    translation_progress['processed'] = i
                    log_message(f"--- [RU] Entry {i}/{total_ru_to_translate} ---")
                    log_message(f"Original (EN): {ru_entry.msgid[:100]}...")
                    # Find entry index in original PO file
                    entry_index = None
                    if config.get('preview_mode', False) and ru_po:
                        for idx, orig_entry in enumerate(ru_po):
                            if orig_entry.msgid == ru_entry.msgid:
                                entry_index = idx
                                break
                    if translate_entry_ai(ru_entry, 'Russian', selected_model, config, entry_index):
                        preview_mode = config.get('preview_mode', False)
                        if preview_mode:
                            preview_msgstr = preview_translations.get('ru', {}).get(entry_index, {}).get('msgstr', '')
                            log_message(f"Translation (RU): {preview_msgstr[:100] if isinstance(preview_msgstr, str) else preview_msgstr}...")
                        else:
                            log_message(f"Translation (RU): {ru_entry.msgstr[:100] if isinstance(ru_entry.msgstr, str) else ru_entry.msgstr}...")
                    log_message(f"Progress: {i}/{total_ru_to_translate} ({translation_progress['ru_translated']} successful)")
                    time.sleep(1)
            
            # Translate Ukrainian entries (only if selected)
            if translate_ukrainian and total_uk_to_translate > 0:
                log_message("="*60)
                log_message(f"[UKRAINIAN TRANSLATION] Translating {total_uk_to_translate} entries...")
                log_message("="*60)
                for i, uk_entry in enumerate(uk_entries_to_translate, 1):
                    if translation_stop_requested:
                        log_message("Translation process stopped by user")
                        break
                    
                    translation_progress['processed'] = total_ru_to_translate + i
                    log_message(f"--- [UK] Entry {i}/{total_uk_to_translate} ---")
                    log_message(f"Original (EN): {uk_entry.msgid[:100]}...")
                    # Find entry index in original PO file
                    entry_index = None
                    if config.get('preview_mode', False) and uk_po:
                        for idx, orig_entry in enumerate(uk_po):
                            if orig_entry.msgid == uk_entry.msgid:
                                entry_index = idx
                                break
                    if translate_entry_ai(uk_entry, 'Ukrainian', selected_model, config, entry_index):
                        preview_mode = config.get('preview_mode', False)
                        if preview_mode:
                            preview_msgstr = preview_translations.get('uk', {}).get(entry_index, {}).get('msgstr', '')
                            log_message(f"Translation (UK): {preview_msgstr[:100] if isinstance(preview_msgstr, str) else preview_msgstr}...")
                        else:
                            log_message(f"Translation (UK): {uk_entry.msgstr[:100] if isinstance(uk_entry.msgstr, str) else uk_entry.msgstr}...")
                    log_message(f"Progress: {i}/{total_uk_to_translate} ({translation_progress['uk_translated']} successful)")
                    time.sleep(1)
        else:
            # Original behavior: translate all entries
            # Determine total entries from the first available PO file
            total_entries = len(ru_po) if ru_po else (len(uk_po) if uk_po else 0)
            translation_progress['total'] = total_entries
            log_message(f"Total entries to process: {total_entries}")
            
            # If both languages are selected, process them together
            if ru_po and uk_po and translate_russian and translate_ukrainian:
                for i, (ru_entry, uk_entry) in enumerate(zip(ru_po, uk_po), 1):
                    if translation_stop_requested:
                        log_message("Translation process stopped by user")
                        break
                        
                    translation_progress['processed'] = i
                    log_message(f"--- Processing entry {i}/{total_entries} ---")
                    
                    translate_entry_ai(ru_entry, 'Russian', selected_model, config)
                    translate_entry_ai(uk_entry, 'Ukrainian', selected_model, config)
                    
                    log_message(f"Progress: {i}/{total_entries}")
                    time.sleep(1)
            # If only Russian is selected
            elif ru_po and translate_russian:
                for i, ru_entry in enumerate(ru_po, 1):
                    if translation_stop_requested:
                        log_message("Translation process stopped by user")
                        break
                        
                    translation_progress['processed'] = i
                    log_message(f"--- [RU] Processing entry {i}/{total_entries} ---")
                    
                    translate_entry_ai(ru_entry, 'Russian', selected_model, config)
                    
                    log_message(f"Progress: {i}/{total_entries}")
                    time.sleep(1)
            # If only Ukrainian is selected
            elif uk_po and translate_ukrainian:
                for i, uk_entry in enumerate(uk_po, 1):
                    if translation_stop_requested:
                        log_message("Translation process stopped by user")
                        break
                        
                    translation_progress['processed'] = i
                    log_message(f"--- [UK] Processing entry {i}/{total_entries} ---")
                    
                    translate_entry_ai(uk_entry, 'Ukrainian', selected_model, config)
                    
                    log_message(f"Progress: {i}/{total_entries}")
                    time.sleep(1)
        
        # Clean and save files (only for selected languages and if not in preview mode)
        preview_mode = config.get('preview_mode', False)
        
        if not preview_mode:
            log_message("Cleaning PO files of specific comments...")
            if ru_po and translate_russian:
                clean_po_file(ru_po, config)
            if uk_po and translate_ukrainian:
                clean_po_file(uk_po, config)
            
            log_message("Saving changes to PO files...")
            if ru_po and translate_russian:
                ru_po.save()
                log_message(f"Saved Russian PO file: {ru_po_file_path}")
            if uk_po and translate_ukrainian:
                uk_po.save()
                log_message(f"Saved Ukrainian PO file: {uk_po_file_path}")
            
            log_message("Translation process completed!")
            log_message("To apply the translations:")
            log_message("1. Compile with: python manage.py compilemessages")
            log_message("2. Restart your Django server")
            log_message("3. Clear your browser cache if needed")
        else:
            log_message("Translation process completed in PREVIEW MODE!")
            log_message("Please review the translations in the preview interface before saving.")
        
    except Exception as e:
        log_message(f"An error occurred: {str(e)}")
    
    finally:
        translation_in_progress = False
        translation_stop_requested = False

@user_passes_test(is_superuser)
def get_untranslated_strings(request, language):
    """Get a list of untranslated strings from a specific language PO file"""
    if language not in ['ru', 'uk']:
        return JsonResponse({
            'success': False,
            'message': 'Invalid language code'
        })
    
    # Get project root
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
    
    # Get translation file path - check both possible directories
    possible_dirs = ['SecBoard', 'SecBoard_develop']
    po_file_path = None
    
    for dir_name in possible_dirs:
        path = os.path.join(PROJECT_ROOT, dir_name, 'locale', language, 'LC_MESSAGES', 'django.po')
        if os.path.exists(path):
            po_file_path = path
            break
    
    # Fallback to SecBoard if not found
    if not po_file_path:
        po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', language, 'LC_MESSAGES', 'django.po')
    
    if not os.path.exists(po_file_path):
        return JsonResponse({
            'success': False,
            'message': f'PO file not found: {po_file_path}'
        })
    
    try:
        # Open PO file
        po = polib.pofile(po_file_path)
        
        # Get untranslated entries
        untranslated = []
        for entry in po:
            if not is_entry_translated(entry):
                # Limit the length of displayed strings to avoid huge responses
                msgid = entry.msgid
                if len(msgid) > 500:
                    msgid = msgid[:500] + "..."
                
                untranslated.append({
                    'msgid': msgid,
                    'line': entry.linenum if hasattr(entry, 'linenum') else 0,
                    'occurrences': entry.occurrences
                })
        
        return JsonResponse({
            'success': True,
            'language': language,
            'untranslated_count': len(untranslated),
            'untranslated': untranslated[:100],  # Limit to 100 entries
            'has_more': len(untranslated) > 100
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error reading PO file: {str(e)}'
        })

@user_passes_test(is_superuser)
def get_preview_translations(request):
    """Get preview translations for review"""
    global preview_translations
    
    return JsonResponse({
        'success': True,
        'preview_translations': preview_translations
    })

@user_passes_test(is_superuser)
def get_fuzzy_strings(request, language):
    """Return a list of fuzzy entries from the given language PO file."""
    if language not in ['ru', 'uk']:
        return JsonResponse({'success': False, 'message': 'Invalid language code'})

    po_path = _get_po_path(language)
    if not os.path.exists(po_path):
        return JsonResponse({'success': False, 'message': f'PO file not found: {po_path}'})

    try:
        po = polib.pofile(po_path)
        fuzzy_entries = []
        for idx, entry in enumerate(po):
            if 'fuzzy' in entry.flags:
                msgid = entry.msgid if len(entry.msgid) <= 500 else entry.msgid[:500] + '...'
                msgstr = entry.msgstr if isinstance(entry.msgstr, str) else str(entry.msgstr)
                if len(msgstr) > 300:
                    msgstr = msgstr[:300] + '...'
                fuzzy_entries.append({
                    'index': idx,
                    'msgid': msgid,
                    'msgstr': msgstr,
                    'occurrences': entry.occurrences[:3],
                    'previous_msgid': entry.previous_msgid or '',
                })
        return JsonResponse({
            'success': True,
            'language': language,
            'fuzzy_count': len(fuzzy_entries),
            'fuzzy_entries': fuzzy_entries[:200],
            'has_more': len(fuzzy_entries) > 200,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error reading PO file: {str(e)}'})


@user_passes_test(is_superuser)
@csrf_exempt
def start_fuzzy_fix(request):
    """Start fixing fuzzy entries in a background thread."""
    global fuzzy_fix_in_progress, fuzzy_fix_progress, fuzzy_fix_preview

    if fuzzy_fix_in_progress:
        return JsonResponse({'success': False, 'message': 'Fuzzy fix is already in progress'})

    try:
        data = json.loads(request.body)
        selected_model = data.get('model', 'google_translate')
        config = data.get('config', {})
        config.setdefault('fix_russian', True)
        config.setdefault('fix_ukrainian', True)
        config.setdefault('preview_mode', True)

        fuzzy_fix_preview = {}
        fuzzy_fix_progress.update({
            'total': 0,
            'processed': 0,
            'ru_fixed': 0,
            'ru_skipped': 0,
            'uk_fixed': 0,
            'uk_skipped': 0,
            'log': [],
            'selected_model': selected_model,
            'config': config,
            'preview_mode': config.get('preview_mode', True),
        })
        fuzzy_fix_in_progress = True

        thread = threading.Thread(target=_run_fuzzy_fix_process)
        thread.daemon = True
        thread.start()

        return JsonResponse({'success': True, 'message': 'Fuzzy fix started'})
    except Exception as e:
        fuzzy_fix_in_progress = False
        return JsonResponse({'success': False, 'message': str(e)})


@user_passes_test(is_superuser)
def get_fuzzy_fix_progress(request):
    """Return current fuzzy fix progress."""
    return JsonResponse({
        'in_progress': fuzzy_fix_in_progress,
        'progress': {
            'total': fuzzy_fix_progress['total'],
            'processed': fuzzy_fix_progress['processed'],
            'ru_fixed': fuzzy_fix_progress['ru_fixed'],
            'ru_skipped': fuzzy_fix_progress['ru_skipped'],
            'uk_fixed': fuzzy_fix_progress['uk_fixed'],
            'uk_skipped': fuzzy_fix_progress['uk_skipped'],
            'log': fuzzy_fix_progress['log'],
            'preview_mode': fuzzy_fix_progress.get('preview_mode', True),
        }
    })


@user_passes_test(is_superuser)
@csrf_exempt
def stop_fuzzy_fix(request):
    """Request the fuzzy fix process to stop."""
    global fuzzy_fix_stop_requested
    fuzzy_fix_stop_requested = True
    return JsonResponse({'success': True, 'message': 'Stop requested'})


@user_passes_test(is_superuser)
def get_fuzzy_fix_preview(request):
    """Return the fuzzy fix preview translations."""
    return JsonResponse({'success': True, 'fuzzy_preview': fuzzy_fix_preview})


@user_passes_test(is_superuser)
@csrf_exempt
def save_fuzzy_fixes(request):
    """Save reviewed fuzzy fixes to PO files."""
    global fuzzy_fix_preview
    try:
        data = json.loads(request.body)
        fixes = data.get('fixes', {})

        # Merge any user-edited translations back into the preview data
        for lang, entries in fixes.items():
            for idx_str, fix_data in entries.items():
                if lang in fuzzy_fix_preview and idx_str in fuzzy_fix_preview[lang]:
                    fuzzy_fix_preview[lang][idx_str]['msgstr_new'] = fix_data.get('msgstr_new', fuzzy_fix_preview[lang][idx_str]['msgstr_new'])

        # Only save the languages/entries that were sent from the client
        fixes_to_save = {}
        for lang, entries in fixes.items():
            fixes_to_save[lang] = {}
            for idx_str, fix_data in entries.items():
                if lang in fuzzy_fix_preview and idx_str in fuzzy_fix_preview[lang]:
                    fixes_to_save[lang][idx_str] = fuzzy_fix_preview[lang][idx_str]

        _apply_fuzzy_fixes_to_files(fixes_to_save)

        saved = sum(len(v) for v in fixes_to_save.values())
        fuzzy_fix_preview = {}

        return JsonResponse({
            'success': True,
            'message': f'Successfully fixed {saved} fuzzy entries',
            'saved_count': saved,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@user_passes_test(is_superuser)
@csrf_exempt
def save_confirmed_translations(request):
    """Save confirmed translations from preview mode to PO files"""
    global preview_translations, translation_progress
    
    try:
        data = json.loads(request.body)
        translations_to_save = data.get('translations', {})
        
        # Get project root
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
        
        # Get translation file paths
        possible_dirs = ['SecBoard', 'SecBoard_develop']
        ru_po_file_path = None
        uk_po_file_path = None
        
        # Get paths for languages that have translations
        if 'ru' in translations_to_save:
            for dir_name in possible_dirs:
                ru_path = os.path.join(PROJECT_ROOT, dir_name, 'locale', 'ru', 'LC_MESSAGES', 'django.po')
                if os.path.exists(ru_path):
                    ru_po_file_path = ru_path
                    break
            if not ru_po_file_path:
                ru_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'ru', 'LC_MESSAGES', 'django.po')
        
        if 'uk' in translations_to_save:
            for dir_name in possible_dirs:
                uk_path = os.path.join(PROJECT_ROOT, dir_name, 'locale', 'uk', 'LC_MESSAGES', 'django.po')
                if os.path.exists(uk_path):
                    uk_po_file_path = uk_path
                    break
            if not uk_po_file_path:
                uk_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'uk', 'LC_MESSAGES', 'django.po')
        
        saved_count = 0
        
        # Save Russian translations
        if ru_po_file_path and os.path.exists(ru_po_file_path) and 'ru' in translations_to_save:
            ru_po = polib.pofile(ru_po_file_path)
            ru_translations = translations_to_save['ru']
            
            for entry_index_str, translation_data in ru_translations.items():
                try:
                    entry_index = int(entry_index_str)
                    if 0 <= entry_index < len(ru_po):
                        entry = ru_po[entry_index]
                        # Verify this is the correct entry by checking msgid (if available in preview)
                        expected_msgid = preview_translations.get('ru', {}).get(entry_index_str, {}).get('msgid')
                        if not expected_msgid or entry.msgid == expected_msgid:
                            entry.msgstr = translation_data.get('msgstr', '')
                            # Clear fuzzy flag
                            entry.flags = [flag for flag in entry.flags if flag != 'fuzzy']
                            saved_count += 1
                except (ValueError, IndexError, AttributeError) as e:
                    continue
            
            ru_po.save()
        
        # Save Ukrainian translations
        if uk_po_file_path and os.path.exists(uk_po_file_path) and 'uk' in translations_to_save:
            uk_po = polib.pofile(uk_po_file_path)
            uk_translations = translations_to_save['uk']
            
            for entry_index_str, translation_data in uk_translations.items():
                try:
                    entry_index = int(entry_index_str)
                    if 0 <= entry_index < len(uk_po):
                        entry = uk_po[entry_index]
                        # Verify this is the correct entry by checking msgid (if available in preview)
                        expected_msgid = preview_translations.get('uk', {}).get(entry_index_str, {}).get('msgid')
                        if not expected_msgid or entry.msgid == expected_msgid:
                            entry.msgstr = translation_data.get('msgstr', '')
                            # Clear fuzzy flag
                            entry.flags = [flag for flag in entry.flags if flag != 'fuzzy']
                            saved_count += 1
                except (ValueError, IndexError, AttributeError) as e:
                    continue
            
            uk_po.save()
        
        # Clear preview translations after saving
        preview_translations = {}
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully saved {saved_count} translations',
            'saved_count': saved_count
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error saving translations: {str(e)}'
        })

@csrf_exempt
@user_passes_test(is_superuser)
def test_google_connection(request, api_id):
    """Test connection to Google AI API"""
    try:
        import google.generativeai as genai
        from .models import APISettingsGoogle
        
        settings = APISettingsGoogle.objects.get(id=api_id)
        if not settings or not settings.model_name:
            return JsonResponse({'status': 'error', 'message': 'Google AI settings not configured properly'})
            
        genai.configure(api_key=settings.api_key)
        model = genai.GenerativeModel(settings.model_name.model_id)
        
        # Try a simple request
        response = model.generate_content("Hello")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Successfully connected to Google AI API'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Connection failed: {str(e)}'
        })

@csrf_exempt
@user_passes_test(is_superuser)
def test_claude_connection(request, api_id):
    """Test connection to Claude API"""
    try:
        import anthropic
        from .models import APISettingsClaude
        
        settings = APISettingsClaude.objects.get(id=api_id)
        if not settings or not settings.model_name:
            return JsonResponse({'status': 'error', 'message': 'Claude settings not configured properly'})
            
        client = anthropic.Anthropic(api_key=settings.api_key)
        
        # Try a simple request
        response = client.messages.create(
            model=settings.model_name.model_id,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hello"}]
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Successfully connected to Claude API'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Connection failed: {str(e)}'
        })

@csrf_exempt
@user_passes_test(is_superuser)
def test_groq_connection(request, api_id):
    """Test connection to Groq API"""
    try:
        from groq import Groq
        from .models import APISettingsGroq
        
        settings = APISettingsGroq.objects.get(id=api_id)
        if not settings or not settings.model_name:
            return JsonResponse({'status': 'error', 'message': 'Groq settings not configured properly'})
            
        client = Groq(api_key=settings.api_key)
        
        # Try a simple request
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"}
            ],
            model=settings.model_name.model_id,
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Successfully connected to Groq API'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Connection failed: {str(e)}'
        })

@csrf_exempt
@user_passes_test(is_superuser)
def test_ollama_connection(request, api_id):
    """Test connection to Ollama API"""
    try:
        from ollama import Client
        from .models import APISettingsOllama
        
        settings = APISettingsOllama.objects.get(id=api_id)
        if not settings or not settings.model_name:
            return JsonResponse({'status': 'error', 'message': 'Ollama settings not configured properly'})
            
        client = Client(host=settings.api_url)
        
        # Try a simple request
        response = client.chat(
            model=settings.model_name.model_id,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"}
            ]
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Successfully connected to Ollama API'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Connection failed: {str(e)}'
        })

@csrf_exempt
@user_passes_test(is_superuser)
def test_deepseek_connection(request, api_id):
    """Test connection to DeepSeek API"""
    try:
        from openai import OpenAI
        from .models import APISettingsDeepSeek
        
        settings = APISettingsDeepSeek.objects.get(id=api_id)
        if not settings or not settings.model_name:
            return JsonResponse({'status': 'error', 'message': 'DeepSeek settings not configured properly'})
            
        client = OpenAI(api_key=settings.api_key, base_url="https://api.deepseek.com/v1")
        
        # Try a simple request
        response = client.chat.completions.create(
            model=settings.model_name.model_id,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello"}
            ],
            max_tokens=10
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Successfully connected to DeepSeek API'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Connection failed: {str(e)}'
        })

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import AIAgentSettings
from .ai_utils import get_claude_response, get_google_response, get_groq_response, get_ollama_response, get_deepseek_response
import logging

logger = logging.getLogger(__name__)

@login_required
def get_page_context(request):
    """Отримати контекст поточної сторінки для AI помічника"""
    from django.utils.translation import gettext as _
    from urllib.parse import urlparse
    
    # Базовий контекст по самому API-запиту
    context = {
        'url': request.build_absolute_uri(),
        'path': request.path,
        'path_info': request.path_info,
        'page_title': getattr(request, 'page_title', ''),
        'app_name': request.resolver_match.app_name if request.resolver_match else '',
        'url_name': request.resolver_match.url_name if request.resolver_match else '',
    }
    
    # Визначити ОРИГІНАЛЬНУ сторінку, на якій знаходиться користувач.
    # Пріоритет:
    # 1) явні параметри ?url=&path= з фронтенду
    # 2) HTTP_REFERER
    # 3) сам API URL (fallback)
    original_url = request.GET.get('url') or request.META.get('HTTP_REFERER') or context['url']
    original_path = request.GET.get('path')
    
    if not original_path and original_url:
        try:
            original_path = urlparse(original_url).path
        except Exception:
            original_path = request.path
    
    if not original_path:
        original_path = request.path
    
    # Переписуємо в контексті URL/шлях на ОРИГІНАЛЬНІ значення сторінки
    context['url'] = original_url
    context['path'] = original_path
    context['path_info'] = original_path
    
    # Детальне визначення контексту залежно від ОРИГІНАЛЬНОЇ сторінки
    path_lower = original_path.lower()
    path_clean = path_lower.rstrip('/')
    app_name = context.get('app_name', '')
    
    # Compliance pages - перевіряємо і по path, і по app_name
    if 'compliance' in path_lower or app_name == 'compliance':
        context['page_type'] = 'compliance'
        # Головна сторінка Compliance Dashboard - перевірка різних варіантів URL
        is_compliance_dashboard = (
            path_clean.endswith('/app_compliance') or 
            path_clean.endswith('/app_compliance/') or
            path_clean == '/en/app_compliance' or 
            path_clean == '/uk/app_compliance' or
            path_clean == '/ru/app_compliance' or
            path_clean == '/en/app_compliance/' or 
            path_clean == '/uk/app_compliance/' or
            path_clean == '/ru/app_compliance/' or
            (app_name == 'compliance' and (context.get('url_name') == 'dashboard' or not context.get('url_name'))) or
            # Додаткова перевірка: якщо шлях містить /app_compliance/ і не містить подальших сегментів
            ('/app_compliance' in path_clean and path_clean.count('/') <= 3 and '/local/' not in path_lower and '/frameworks/' not in path_lower and '/controls/' not in path_lower and '/evidences/' not in path_lower)
        )
        
        if is_compliance_dashboard:
            context['description'] = _('Compliance Management Dashboard - Overview of compliance frameworks, controls, and their status')
            context['detailed_info'] = _('This is the main compliance management dashboard where you can view compliance frameworks (like ISO 27001, PCI DSS, GDPR), manage controls, track compliance status, monitor implementation progress, and access compliance-related reports and analytics.')
        elif '/local/' in path_lower:
            context['description'] = _('Local Compliance Management - Managing local regulatory compliance requirements and controls')
            context['detailed_info'] = _('This page is for managing local compliance requirements, regulatory controls, evidence, and assignments for specific countries or regions.')
        elif '/frameworks/' in path_lower:
            context['description'] = _('Compliance Frameworks Management - Creating and managing compliance frameworks (ISO 27001, PCI DSS, GDPR, etc.)')
            context['detailed_info'] = _('This section allows you to create, edit, and manage compliance frameworks, their categories, and controls.')
        elif '/controls/' in path_lower:
            context['description'] = _('Compliance Controls - Managing individual compliance controls, evidence, and assignments')
            context['detailed_info'] = _('This page is for managing specific compliance controls, adding evidence, assigning responsible users, and tracking implementation status.')
        elif '/evidences/' in path_lower:
            context['description'] = _('Compliance Evidence - Managing evidence for compliance controls')
            context['detailed_info'] = _('This page allows you to upload, review, approve, or reject evidence documents for compliance controls.')
        else:
            context['description'] = _('Compliance Management page')
            context['detailed_info'] = _('This is a compliance management page in the SecBoard platform.')
    
    # Risk Assessment pages
    elif 'risk' in path_lower:
        context['page_type'] = 'risk_assessment'
        if '/assessment/' in path_lower:
            context['description'] = _('Risk Assessment - Evaluating and analyzing security risks for information assets')
            context['detailed_info'] = _('This page allows you to assess risks associated with information assets, vulnerabilities, and threats.')
        elif '/treatment/' in path_lower:
            context['description'] = _('Risk Treatment - Managing risk mitigation and treatment plans')
            context['detailed_info'] = _('This page is for creating and managing risk treatment plans, assigning responsibilities, and tracking treatment status.')
        else:
            context['description'] = _('Risk Assessment and Management page')
            context['detailed_info'] = _('This is a risk management page where you can assess and manage information security risks.')
    
    # Incident Management pages (app_incident)
    elif '/app_incident/' in path_lower or 'incident' in path_lower or app_name == 'incident':
        context['page_type'] = 'incident'
        
        # Визначити тип сторінки управління інцидентами
        if '/incident_register' in path_lower or path_clean.endswith('/app_incident') or path_clean.endswith('/app_incident/'):
            context['description'] = _('Incident Register - List of security incidents and their status')
            context['detailed_info'] = _('This page displays the incident register with all security incidents. You can view, search, filter incidents by status, severity, date, and other criteria. Export incidents to Excel and manage incident lifecycle.')
        elif '/incident_add' in path_lower:
            context['description'] = _('Add Incident - Reporting a new security incident')
            context['detailed_info'] = _('This page allows you to report a new security incident. You can provide incident details, classification, severity, affected systems, initial response actions, and attach relevant files or evidence.')
        elif '/incident_detail' in path_lower:
            context['description'] = _('Incident Detail - Viewing detailed information about a specific security incident')
            context['detailed_info'] = _('This page displays detailed information about a specific security incident including incident timeline, affected systems, response actions, evidence, attachments, and incident status updates.')
        elif '/incident_edit' in path_lower:
            context['description'] = _('Edit Incident - Updating incident information and status')
            context['detailed_info'] = _('This page allows you to edit an existing security incident. You can update incident details, change status, add response actions, update affected systems, and modify incident classification.')
        elif '/export_incidents' in path_lower:
            context['description'] = _('Export Incidents - Exporting incident data to Excel')
            context['detailed_info'] = _('This page allows you to export security incidents data to Excel format for reporting, analysis, and documentation purposes.')
        else:
            context['description'] = _('Incident Management - Managing security incidents, response activities, and post-incident reviews')
            context['detailed_info'] = _('This page is for reporting, tracking, and managing security incidents, including incident response activities, documentation, evidence collection, and post-incident reviews.')
    
    # Asset Management pages (app_asset)
    elif '/app_asset/' in path_lower or ('asset' in path_lower and app_name != 'access') or app_name == 'asset':
        context['page_type'] = 'asset'
        
        # Визначити тип сторінки управління активами
        if '/information_assets' in path_lower or '/asset_data' in path_lower or path_clean.endswith('/app_asset') or path_clean.endswith('/app_asset/'):
            context['description'] = _('Information Assets - List of information assets and their details')
            context['detailed_info'] = _('This page displays the list of all information assets in the system. You can view, search, filter, and manage information assets, see their classification, criticality levels, owners, and administrators.')
        elif '/add_asset' in path_lower:
            context['description'] = _('Add Information Asset - Creating a new information asset')
            context['detailed_info'] = _('This page allows you to create a new information asset. You can specify asset details, classification, criticality level, assign owners and administrators, and configure asset protection requirements.')
        elif '/edit_asset' in path_lower or '/get_asset' in path_lower or '/get_asset_details' in path_lower:
            context['description'] = _('Edit Information Asset - Editing asset details and configuration')
            context['detailed_info'] = _('This page allows you to edit an existing information asset. You can modify asset properties, classification, criticality, update owners and administrators, and change protection requirements.')
        elif '/asset_type' in path_lower:
            context['description'] = _('Asset Types Management - Managing types and categories of information assets')
            context['detailed_info'] = _('This page allows you to manage asset types and categories. You can create, edit, and organize different types of information assets used in the classification system.')
        elif '/asset_group' in path_lower or '/asset-groups' in path_lower:
            context['description'] = _('Asset Groups Management - Organizing assets into groups and categories')
            context['detailed_info'] = _('This page is for managing asset groups. You can organize information assets into groups and categories for better management and organization.')
        elif '/asset_owner' in path_lower or '/asset-owner' in path_lower:
            context['description'] = _('Asset Owners Management - Assigning and managing asset owners')
            context['detailed_info'] = _('This page allows you to manage asset owners. You can assign owners to information assets, view ownership relationships, and manage responsibilities.')
        elif '/asset_administrator' in path_lower or '/asset-administrator' in path_lower:
            context['description'] = _('Asset Administrators Management - Assigning and managing asset administrators')
            context['detailed_info'] = _('This page is for managing asset administrators. You can assign administrators to information assets, configure administrative responsibilities, and manage administrative access.')
        elif '/export' in path_lower:
            context['description'] = _('Export Assets - Exporting asset data to Excel')
            context['detailed_info'] = _('This page allows you to export information assets data to Excel format for reporting and analysis purposes.')
        else:
            context['description'] = _('Asset Management - Managing information assets, their classification, and protection requirements')
            context['detailed_info'] = _('This page allows you to manage information assets, classify them by criticality, assign owners and administrators, and track their protection status.')
    
    # Vulnerability Management pages
    elif 'vulnerability' in path_lower:
        context['page_type'] = 'vulnerability'
        context['description'] = _('Vulnerability Management - Identifying, assessing, and managing security vulnerabilities')
        context['detailed_info'] = _('This page is for managing security vulnerabilities, their assessment, remediation, and tracking.')
    
    # Access Management pages (app_access)
    elif '/app_access/' in path_lower or 'access' in path_lower or app_name == 'access':
        context['page_type'] = 'access_management'
        
        # Визначити тип сторінки доступу
        if '/access-records' in path_lower or '/access/' in path_lower:
            context['description'] = _('Access Records - Managing access records for information systems')
            context['detailed_info'] = _('This page allows you to view, create, edit, and manage access records for information systems. You can assign access rights, roles, and permissions to users and groups for different systems and objects.')
        elif '/access-matrix' in path_lower or '/matrix' in path_lower:
            context['description'] = _('Access Matrix - Viewing and managing access matrix for information systems')
            context['detailed_info'] = _('This page displays the access matrix showing relationships between roles, objects, and access rights. You can view and manage access mappings for information systems.')
        elif '/user-access-request' in path_lower or '/submit-access-request' in path_lower:
            context['description'] = _('Access Request - Requesting access to information systems')
            context['detailed_info'] = _('This page allows users to submit access requests for information systems. You can request access to specific systems, objects, roles, and access rights.')
        elif '/manage-access-requests' in path_lower or '/approve-access-requests' in path_lower:
            context['description'] = _('Manage Access Requests - Reviewing and approving access requests')
            context['detailed_info'] = _('This page is for administrators to review, approve, or reject access requests. You can manage the approval workflow, assign approvers, and track request status.')
        elif '/access_config_is' in path_lower or '/access-rights' in path_lower:
            context['description'] = _('Access Configuration - Configuring access rights, roles, and functions')
            context['detailed_info'] = _('This page allows you to configure access rights, roles, functions, and objects for information systems. You can define access levels and permissions.')
        elif '/functions' in path_lower:
            context['description'] = _('Functions Management - Managing functions for information systems')
            context['detailed_info'] = _('This page is for managing functions (capabilities) available in information systems. You can create, edit, and organize functions used in access configurations.')
        elif '/objects' in path_lower or '/object-' in path_lower:
            context['description'] = _('Objects Management - Managing access objects for information systems')
            context['detailed_info'] = _('This page allows you to manage access objects (resources, modules, components) within information systems. You can create hierarchical object structures and assign access rights.')
        elif '/roles' in path_lower or '/role-' in path_lower:
            context['description'] = _('Roles Management - Managing roles for access control')
            context['detailed_info'] = _('This page is for managing roles used in access control. You can define roles, assign functions and access rights to them.')
        elif '/api-request' in path_lower:
            context['description'] = _('API Access Management - Managing API access and synchronization')
            context['detailed_info'] = _('This page allows you to manage API access requests, configure API credentials, synchronize users, and monitor API access status.')
        elif '/user-available-access' in path_lower:
            context['description'] = _('Available Access - Viewing available access options')
            context['detailed_info'] = _('This page shows available access options that users can request. You can browse systems, objects, roles, and access rights available for request.')
        elif '/access-notification' in path_lower or '/notification' in path_lower:
            context['description'] = _('Access Notifications - Configuring access-related email notifications')
            context['detailed_info'] = _('This page allows you to configure email notifications for access requests, approvals, and other access-related events.')
        else:
            context['description'] = _('Access Management - Managing access to information systems')
            context['detailed_info'] = _('This is an access management page where you can manage access to information systems, configure access rights, roles, and permissions.')
    
    # GDPR Compliance pages (app_gdpr)
    elif '/app_gdpr/' in path_lower or 'gdpr' in path_lower or app_name == 'app_gdpr':
        context['page_type'] = 'gdpr_compliance'
        
        # Визначити тип сторінки GDPR compliance
        if path_clean.endswith('/app_gdpr') or path_clean.endswith('/app_gdpr/') or (path_lower.count('/') <= 3 and '/app_gdpr' in path_lower):
            context['description'] = _('GDPR Compliance Dashboard - Overview of GDPR compliance status and activities')
            context['detailed_info'] = _('This is the GDPR compliance dashboard providing an overview of data protection compliance, data subjects, consents, data breach incidents, and compliance metrics.')
        elif '/data-subjects' in path_lower:
            context['description'] = _('Data Subjects Management - Managing personal data subjects')
            context['detailed_info'] = _('This page allows you to manage data subjects (individuals whose personal data is processed). You can add, edit, view, export, and anonymize personal data for GDPR compliance.')
        elif '/consents' in path_lower:
            context['description'] = _('Consent Records - Managing consent records for data processing')
            context['detailed_info'] = _('This page is for managing consent records. You can track consent given by data subjects for data processing activities, view consent history, and manage consent withdrawals.')
        elif '/dsr' in path_lower or '/data-subject-request' in path_lower:
            context['description'] = _('Data Subject Requests (DSR) - Managing GDPR data subject requests')
            context['detailed_info'] = _('This page allows you to manage Data Subject Requests (DSR) such as access requests, rectification, erasure, and data portability. You can create, process, and track DSR compliance.')
        elif '/breaches' in path_lower or '/data-breach' in path_lower:
            context['description'] = _('Data Breach Incidents - Managing and reporting data breach incidents')
            context['detailed_info'] = _('This page is for managing data breach incidents. You can report breaches, track incident details, assess risk, and generate breach reports for regulatory compliance.')
        elif '/activities' in path_lower or '/data-processing-activity' in path_lower:
            context['description'] = _('Data Processing Activities - Managing data processing activities register')
            context['detailed_info'] = _('This page allows you to manage the register of data processing activities (Article 30 GDPR). You can document how personal data is processed, for what purposes, and by whom.')
        elif '/policies' in path_lower or '/data-retention' in path_lower:
            context['description'] = _('Data Retention Policies - Managing data retention and deletion policies')
            context['detailed_info'] = _('This page is for managing data retention policies. You can define how long personal data should be retained, set deletion schedules, and ensure compliance with data minimization principles.')
        elif '/dpia' in path_lower:
            context['description'] = _('DPIA Assessments - Data Protection Impact Assessments')
            context['detailed_info'] = _('This page allows you to conduct and manage Data Protection Impact Assessments (DPIA). You can create assessments, evaluate risks, and obtain approvals for high-risk data processing activities.')
        elif '/reports' in path_lower:
            context['description'] = _('GDPR Compliance Reports - Generating and viewing compliance reports')
            context['detailed_info'] = _('This page allows you to generate and view GDPR compliance reports. You can export reports to Excel or PDF format, analyze compliance metrics, and track regulatory compliance status.')
        elif '/guide' in path_lower:
            context['description'] = _('GDPR Guide - Educational resources and guides for GDPR compliance')
            context['detailed_info'] = _('This page provides educational resources, guides, and documentation to help understand and implement GDPR compliance requirements.')
        else:
            context['description'] = _('GDPR Compliance - Managing GDPR data protection compliance')
            context['detailed_info'] = _('This is a GDPR compliance page for managing data protection, data subjects, consents, data breaches, and regulatory compliance in accordance with GDPR requirements.')
    
    # Standards Management pages (app_std)
    elif '/app_std/' in path_lower or 'std' in path_lower or app_name == 'std':
        context['page_type'] = 'standards'
        
        # Визначити тип сторінки управління стандартами
        if '/pcidss' in path_lower:
            if '/documents' in path_lower:
                context['description'] = _('PCI DSS Documents - Managing PCI DSS compliance documents')
                context['detailed_info'] = _('This page allows you to manage PCI DSS compliance documents. You can upload, view, and delete documents related to PCI DSS requirements and compliance evidence.')
            elif '/edit_pcidss' in path_lower or '/get_pcidss' in path_lower or '/add-pcidss' in path_lower:
                context['description'] = _('PCI DSS Requirement Management - Editing PCI DSS requirements')
                context['detailed_info'] = _('This page allows you to manage PCI DSS requirements. You can add, edit, view, and configure PCI DSS requirements, translate fields, and customize requirement details.')
            elif '/export' in path_lower or '/import' in path_lower:
                context['description'] = _('PCI DSS Import/Export - Importing and exporting PCI DSS requirements')
                context['detailed_info'] = _('This page allows you to import or export PCI DSS requirements to/from Excel format for backup, migration, or bulk updates.')
            elif '/search-pcidss' in path_lower:
                context['description'] = _('PCI DSS AI Search - Searching PCI DSS requirements using AI')
                context['detailed_info'] = _('This page allows you to search PCI DSS requirements using AI-powered search. You can find relevant requirements using natural language queries.')
            else:
                context['description'] = _('PCI DSS Requirements - Managing PCI DSS (Payment Card Industry Data Security Standard) requirements')
                context['detailed_info'] = _('This page displays and manages PCI DSS requirements. You can view, search, filter, and manage PCI DSS compliance requirements, track implementation status, and manage compliance evidence.')
        elif '/iso27002' in path_lower or '/iso' in path_lower:
            if '/edit-iso' in path_lower or '/get-iso' in path_lower or '/add-iso' in path_lower:
                context['description'] = _('ISO 27002 Control Management - Editing ISO 27002 controls')
                context['detailed_info'] = _('This page allows you to manage ISO 27002 controls. You can add, edit, view, and configure ISO 27002 information security controls, translate fields, and customize control details.')
            elif '/export' in path_lower or '/import' in path_lower:
                context['description'] = _('ISO 27002 Import/Export - Importing and exporting ISO 27002 controls')
                context['detailed_info'] = _('This page allows you to import or export ISO 27002 controls to/from Excel format for backup, migration, or bulk updates.')
            elif '/search-iso27002' in path_lower:
                context['description'] = _('ISO 27002 AI Search - Searching ISO 27002 controls using AI')
                context['detailed_info'] = _('This page allows you to search ISO 27002 controls using AI-powered search. You can find relevant controls using natural language queries.')
            else:
                context['description'] = _('ISO 27002 Controls - Managing ISO/IEC 27002 information security controls')
                context['detailed_info'] = _('This page displays and manages ISO 27002 information security controls. You can view, search, filter, and manage ISO 27002 controls, track implementation status, and manage compliance evidence.')
        else:
            context['description'] = _('Standards Management - Managing security standards and compliance requirements')
            context['detailed_info'] = _('This page allows you to manage security standards like PCI DSS and ISO 27002, including requirements, controls, and compliance documentation.')
    
    # SOC (Security Operations Center) pages (app_soc)
    elif '/app_soc/' in path_lower or 'soc' in path_lower or app_name == 'app_soc':
        context['page_type'] = 'soc'
        
        # Визначити тип сторінки SOC
        if '/fim/dashboard' in path_lower or '/fim/dashboard/' in path_lower or path_clean.endswith('/fim/dashboard'):
            context['description'] = _('FIM Alerts Dashboard - File Integrity Monitoring alerts and security events')
            context['detailed_info'] = _('This is the FIM (File Integrity Monitoring) alerts dashboard. You can view security alerts, file integrity changes, monitor system events from Wazuh agents, analyze alerts, and manage security incident detection.')
        elif '/fim/alert' in path_lower or '/fim/alert/' in path_lower:
            context['description'] = _('FIM Alert Detail - Detailed information about a file integrity monitoring alert')
            context['detailed_info'] = _('This page displays detailed information about a specific FIM alert. You can view alert details, file changes, event timeline, agent information, and analyze the security event.')
        elif '/agent' in path_lower or '/agent/' in path_lower:
            context['description'] = _('Agent Detail - Information about a Wazuh security agent')
            context['detailed_info'] = _('This page displays detailed information about a Wazuh security agent. You can view agent status, configuration, connected endpoints, alerts from this agent, and monitor agent health.')
        else:
            context['description'] = _('SOC - Security Operations Center for monitoring and detecting security threats')
            context['detailed_info'] = _('This is a Security Operations Center (SOC) page for monitoring security events, analyzing alerts, detecting threats, and managing security incident response. Includes File Integrity Monitoring (FIM) capabilities.')
    
    # Document Management pages (app_doc)
    elif '/app_doc/' in path_lower or ('doc' in path_lower and app_name != 'access') or app_name == 'doc':
        context['page_type'] = 'document_management'
        
        # Визначити тип сторінки управління документами
        if '/reg_docs' in path_lower or '/register-doc' in path_lower or '/add_register_doc' in path_lower or '/edit-register-doc' in path_lower:
            context['description'] = _('Register Documents - Managing document register and organizational documents')
            context['detailed_info'] = _('This page allows you to manage the document register. You can add, edit, view, and delete organizational documents, manage document approvals, and organize documents in the register.')
        elif '/related-docs' in path_lower:
            context['description'] = _('Related Documents - Managing related and linked documents')
            context['detailed_info'] = _('This page is for managing related documents. You can link documents together, view relationships between documents, and organize document dependencies.')
        elif '/legislative-docs' in path_lower:
            context['description'] = _('Legislative Documents - Managing legislative and regulatory documents')
            context['detailed_info'] = _('This page allows you to manage legislative documents, regulations, and compliance-related documents. You can add, edit, view, and track legislative requirements.')
        elif '/mandatory-processes' in path_lower:
            context['description'] = _('Mandatory Processes - Managing mandatory processes and procedures')
            context['detailed_info'] = _('This page is for managing mandatory processes and procedures. You can create, edit, track process execution, view execution history, and manage process reminders.')
        elif '/approve-document' in path_lower or '/document-approvals' in path_lower:
            context['description'] = _('Document Approvals - Reviewing and approving documents')
            context['detailed_info'] = _('This page allows you to review and approve documents. You can see pending approvals, approve or reject documents, and manage the approval workflow.')
        else:
            context['description'] = _('Document Management - Managing documents, registers, and document-related processes')
            context['detailed_info'] = _('This is a document management page where you can manage organizational documents, document registers, legislative documents, and related processes.')
    
    # Study/Learning pages (app_study)
    elif '/app_study/' in path_lower or 'study' in path_lower or app_name == 'study':
        context['page_type'] = 'study'
        
        # Спробувати отримати інформацію про сторінку з бази даних
        try:
            # Витягнути slug з URL (формат: /en/app_study/page/slug/)
            slug_match = None
            if '/page/' in path_lower:
                parts = path_lower.split('/page/')
                if len(parts) > 1:
                    slug_part = parts[1].rstrip('/').split('/')[0]
                    if slug_part:
                        slug_match = slug_part
            
            if slug_match:
                # Спробувати імпортувати модель Page та знайти сторінку
                try:
                    from app_study.models import Page
                    page_obj = Page.objects.filter(slug=slug_match).first()
                    if page_obj:
                        context['description'] = _('Study Page: {}').format(page_obj.title)
                        context['detailed_info'] = _('This is an educational page in the SecBoard learning hub. Page: "{}". Here you can study information security materials, view educational content, and access learning resources.').format(page_obj.title)
                        # Додати назву сторінки в page_title для кращого контексту
                        context['page_title'] = page_obj.title
                    else:
                        # Якщо slug не знайдено, все одно показати базовий опис для study
                        context['description'] = _('Study/Learning Page - Educational materials and training resources')
                        context['detailed_info'] = _('This is a page in the SecBoard learning hub where you can access educational materials, training resources, quizzes, and study information security topics.')
                except ImportError:
                    # Якщо не вдалося імпортувати модель
                    context['description'] = _('Study/Learning Page - Educational materials and training resources')
                    context['detailed_info'] = _('This is a page in the SecBoard learning hub where you can access educational materials, training resources, quizzes, and study information security topics.')
                except Exception as e:
                    # Логування помилки, але продовжити з базовим описом
                    logger.debug(f"Error fetching study page with slug '{slug_match}': {str(e)}")
                    context['description'] = _('Study/Learning Page - Educational materials and training resources')
                    context['detailed_info'] = _('This is a page in the SecBoard learning hub where you can access educational materials, training resources, quizzes, and study information security topics.')
            else:
                # Якщо це головна сторінка learning hub або інший розділ study
                if '/learning-hub' in path_lower or path_clean.endswith('/app_study') or path_clean.endswith('/app_study/'):
                    context['description'] = _('Learning Hub - Central place for educational materials, quizzes, and training resources')
                    context['detailed_info'] = _('This is the Learning Hub - the central place in SecBoard where you can access educational materials, take quizzes, view training resources, and study information security topics.')
                else:
                    context['description'] = _('Study/Learning Page - Educational materials and training resources')
                    context['detailed_info'] = _('This is a page in the SecBoard learning hub where you can access educational materials, training resources, quizzes, and study information security topics.')
        except Exception as e:
            # Якщо виникла помилка, використати базовий опис
            logger.debug(f"Error getting study page info: {str(e)}")
            context['description'] = _('Study/Learning Page - Educational materials and training resources')
            context['detailed_info'] = _('This is a page in the SecBoard learning hub where you can access educational materials, training resources, quizzes, and study information security topics.')
    
    # General pages - з fallback перевіркою
    else:
        # Додаткова перевірка для випадків, коли основна перевірка не спрацювала
        if '/app_compliance' in path_clean or app_name == 'compliance':
            context['page_type'] = 'compliance'
            context['description'] = _('Compliance Management Dashboard - Overview of compliance frameworks, controls, and their status')
            context['detailed_info'] = _('This is the main compliance management dashboard where you can view compliance frameworks, manage controls, track compliance status, and access compliance-related reports.')
        elif '/app_risk' in path_clean or app_name == 'risk':
            context['page_type'] = 'risk_assessment'
            context['description'] = _('Risk Assessment and Management page')
            context['detailed_info'] = _('This is a risk management page where you can assess and manage information security risks.')
        elif '/app_incident' in path_clean or app_name == 'incident':
            context['page_type'] = 'incident'
            context['description'] = _('Incident Management - Managing security incidents, response activities, and post-incident reviews')
            context['detailed_info'] = _('This page is for reporting, tracking, and managing security incidents, including incident response activities, documentation, evidence collection, and post-incident reviews.')
        elif '/app_asset' in path_clean or app_name == 'asset':
            context['page_type'] = 'asset'
            context['description'] = _('Asset Management - Managing information assets, their classification, and protection requirements')
            context['detailed_info'] = _('This page allows you to manage information assets, classify them by criticality, and track their protection status.')
        elif '/app_study' in path_clean or app_name == 'study':
            context['page_type'] = 'study'
            context['description'] = _('Study/Learning Page - Educational materials and training resources')
            context['detailed_info'] = _('This is a page in the SecBoard learning hub where you can access educational materials, training resources, quizzes, and study information security topics.')
        elif '/app_access' in path_clean or app_name == 'access':
            context['page_type'] = 'access_management'
            context['description'] = _('Access Management - Managing access to information systems')
            context['detailed_info'] = _('This is an access management page where you can manage access to information systems, configure access rights, roles, and permissions.')
        elif '/app_doc' in path_clean or app_name == 'doc':
            context['page_type'] = 'document_management'
            context['description'] = _('Document Management - Managing documents, registers, and document-related processes')
            context['detailed_info'] = _('This is a document management page where you can manage organizational documents, document registers, legislative documents, and related processes.')
        elif '/app_gdpr' in path_clean or app_name == 'app_gdpr':
            context['page_type'] = 'gdpr_compliance'
            context['description'] = _('GDPR Compliance - Managing GDPR data protection compliance')
            context['detailed_info'] = _('This is a GDPR compliance page for managing data protection, data subjects, consents, data breaches, and regulatory compliance in accordance with GDPR requirements.')
        elif '/app_soc' in path_clean or app_name == 'app_soc':
            context['page_type'] = 'soc'
            context['description'] = _('SOC - Security Operations Center for monitoring and detecting security threats')
            context['detailed_info'] = _('This is a Security Operations Center (SOC) page for monitoring security events, analyzing alerts, detecting threats, and managing security incident response. Includes File Integrity Monitoring (FIM) capabilities.')
        elif '/app_std' in path_clean or app_name == 'std':
            context['page_type'] = 'standards'
            context['description'] = _('Standards Management - Managing security standards and compliance requirements')
            context['detailed_info'] = _('This page allows you to manage security standards like PCI DSS and ISO 27002, including requirements, controls, and compliance documentation.')
        else:
            context['page_type'] = 'general'
            context['description'] = _('General SecBoard page')
            context['detailed_info'] = _('This is a general page in the SecBoard information security management platform.')
    
    # Логування для дебагу
    logger.debug(f"Page context determined - path: {request.path}, app_name: {app_name}, page_type: {context.get('page_type')}, description: {context.get('description')}")
    
    return JsonResponse(context)

@login_required
@csrf_exempt
@require_POST
def ai_assistant_chat(request):
    """Endpoint для чату з AI помічником"""
    import json
    import time
    from django.utils.translation import gettext as _
    from .models import AIAssistantHistory
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        page_context = data.get('page_context', None)  # Може бути None або dict
        use_page_context = data.get('use_page_context', True)  # За замовчуванням використовувати контекст
        
        # Нормалізувати page_context
        if page_context is None:
            page_context = {}
        
        if not user_message:
            return JsonResponse({
                'success': False,
                'error': _('Message is required')
            }, status=400)
        
        # Отримати налаштування агента для користувача
        agent_settings = AIAgentSettings.get_settings_for_user(request.user)
        
        if not agent_settings or not agent_settings.model_choice:
            return JsonResponse({
                'success': False,
                'error': _('AI Agent is not configured. Please configure it in the admin panel.')
            }, status=400)
        
        # Визначити модель залежно від provider
        model_provider = agent_settings.model_choice.provider.strip().lower() if agent_settings.model_choice.provider else None
        
        # Додати логування для діагностики
        logger.info(f"AI Assistant request - User: {request.user.username}, Model: {agent_settings.model_choice.model_name}, Provider: {model_provider}")
        logger.info(f"Use page context: {use_page_context}, Page context type: {type(page_context)}, Page context: {page_context}")
        
        if not model_provider:
            logger.error(f"Model provider is None for model_choice: {agent_settings.model_choice}")
            return JsonResponse({
                'success': False,
                'error': _('Model provider is not specified in the selected model choice.')
            }, status=400)
        
        # Формувати системний промпт залежно від того, чи використовувати контекст сторінки
        # Перевірити, чи потрібно використовувати контекст сторінки та чи він наявний
        should_use_context = use_page_context and page_context and isinstance(page_context, dict) and len(page_context) > 0
        
        logger.info(f"Should use page context: {should_use_context}")
        
        if should_use_context:
            # Обробка контексту сторінки тільки якщо потрібно
            page_description = page_context.get('description', 'General page')
            page_detailed_info = page_context.get('detailed_info', page_description)
            page_type = page_context.get('page_type', 'general')
            page_url = page_context.get('url', '')
            page_path = page_context.get('path', '')
            
            # Якщо контекст не визначено правильно, спробувати визначити з URL
            if page_type == 'general' and page_path and 'compliance' in page_path.lower():
                page_type = 'compliance'
                page_description = _('Compliance Management Dashboard - Overview of compliance frameworks, controls, and their status')
                page_detailed_info = _('This is the main compliance management dashboard where you can view compliance frameworks, manage controls, track compliance status, and access compliance-related reports.')
                logger.warning(f"Page context was 'general' but path contains 'compliance', updating context")
            
            # Додаткова перевірка: якщо page_description містить "General" або "загальн", але path містить compliance
            if page_path and ('general' in page_description.lower() or 'загальн' in page_description.lower()) and 'compliance' in page_path.lower():
                logger.warning(f"Description is generic but path contains compliance, updating: {page_description}")
                page_type = 'compliance'
                page_description = _('Compliance Management Dashboard - Overview of compliance frameworks, controls, and their status')
                page_detailed_info = _('This is the main compliance management dashboard where you can view compliance frameworks (like ISO 27001, PCI DSS, GDPR), manage controls, track compliance status, monitor implementation progress, and access compliance-related reports and analytics.')
            
            # Якщо page_type compliance, переконатися що опис правильний
            if page_type == 'compliance' and ('general' in page_description.lower() or 'загальн' in page_description.lower()):
                logger.warning(f"Compliance page detected but description seems generic: {page_description}, updating")
                page_description = _('Compliance Management Dashboard - Overview of compliance frameworks, controls, and their status')
                page_detailed_info = _('This is the main compliance management dashboard where you can view compliance frameworks (like ISO 27001, PCI DSS, GDPR), manage controls, track compliance status, monitor implementation progress, and access compliance-related reports and analytics.')
            # Режим з контекстом сторінки (за замовчуванням)
            system_prompt = f"""You are an AI assistant helping users with the SecBoard information security management platform.

You have access to information about the user's current page context, which should be used to provide relevant and contextual answers.

CURRENT PAGE CONTEXT:
- Page Type: {page_type}
- Page Description: {page_description}
- Page Details: {page_detailed_info}
- Page URL: {page_url}

HOW TO ANSWER QUESTIONS:

1. **If the question is about the current page** (e.g., "what is on this page", "про що на цій сторінці", "what can I do here"):
   - Describe the current page: {page_description}
   - Explain its functionality based on: {page_detailed_info}
   - Provide specific guidance about using this page

2. **If the question is general about SecBoard platform**:
   - Explain SecBoard's purpose and features
   - Discuss modules like Risk Management, Compliance, Incident Management, Asset Management, Vulnerability Management
   - Provide helpful information about using the platform
   - You can reference the current page context if it's relevant

3. **If the question is about information security topics**:
   - Provide educational and helpful answers
   - Relate to SecBoard's capabilities when relevant
   - Use the page context as additional context if applicable

4. **For any other questions**:
   - Be helpful and informative
   - Use the page context when it adds value to your answer

LANGUAGE INSTRUCTION - CRITICAL:
- You MUST detect the language of the user's question by analyzing the text
- You MUST respond in the SAME language that the user used in their question
- If the question is in Ukrainian (українська) - respond in Ukrainian
- If the question is in Russian (русский) - respond in Russian  
- If the question is in English - respond in English
- Always match the language exactly - do not mix languages
- Look at the user's message carefully to determine the language
- NEVER mention which language you detected or that you are responding in a specific language
- NEVER repeat or paraphrase the user's question in your response
- NEVER say things like "Since your question is in...", "You are asking about...", "Since you are on the page..."

RESPONSE STYLE - CRITICAL:
- Start your response directly with the answer - do not preface it with explanations about language detection or question repetition
- Do not mention that you detected the language or understood the question
- Do not say "You are asking..." or "Since you are on the page..."
- Provide the answer immediately without meta-commentary
- Be direct and to the point

GUIDELINES:
- Be helpful, accurate, and concise
- Use the page context to enrich your answers when relevant
- Don't force page context into every answer - only when it adds value
- Respond naturally and conversationally
- Use markdown formatting (**, *, lists) for better readability"""
            
            # Додати контекст сторінки до повідомлення як додаткову інформацію
            enhanced_message = f"""{user_message}

[Page Context - use this information if relevant to the question:]
Page: {page_description}
Type: {page_type}
Details: {page_detailed_info}
URL: {page_url}"""
        else:
            # Режим загальних відповідей без контексту сторінки
            system_prompt = """You are an AI assistant helping users with the SecBoard information security management platform.

You provide general assistance and answer questions about:
- SecBoard platform features and functionality
- Information security topics and best practices
- Risk management, compliance, incident management, asset management, vulnerability management
- General questions and queries

LANGUAGE INSTRUCTION - CRITICAL:
- You MUST detect the language of the user's question by analyzing the text
- You MUST respond in the SAME language that the user used in their question
- If the question is in Ukrainian (українська) - respond in Ukrainian
- If the question is in Russian (русский) - respond in Russian  
- If the question is in English - respond in English
- Always match the language exactly - do not mix languages
- Look at the user's message carefully to determine the language
- NEVER mention which language you detected or that you are responding in a specific language
- NEVER repeat or paraphrase the user's question in your response
- NEVER say things like "Since your question is in...", "You are asking about..."

RESPONSE STYLE - CRITICAL:
- Start your response directly with the answer - do not preface it with explanations about language detection or question repetition
- Do not mention that you detected the language or understood the question
- Do not say "You are asking..." or similar phrases
- Provide the answer immediately without meta-commentary
- Be direct and to the point

GUIDELINES:
- Be helpful, accurate, and concise
- Answer questions about SecBoard platform and information security
- Provide educational and informative responses
- Use markdown formatting (**, *, lists) for better readability
- Be conversational and friendly"""
            
            # Просто повідомлення користувача без контексту
            enhanced_message = user_message
        
        # Перевірити наявність API settings перед викликом
        if model_provider == 'claude':
            from .models import APISettingsClaude
            if not APISettingsClaude.objects.first():
                return JsonResponse({
                    'success': False,
                    'error': _('Claude API settings are not configured. Please configure them in the admin panel.')
                }, status=400)
        elif model_provider == 'google':
            from .models import APISettingsGoogle
            if not APISettingsGoogle.objects.first():
                return JsonResponse({
                    'success': False,
                    'error': _('Google API settings are not configured. Please configure them in the admin panel.')
                }, status=400)
        elif model_provider == 'groq':
            from .models import APISettingsGroq
            if not APISettingsGroq.objects.first():
                return JsonResponse({
                    'success': False,
                    'error': _('Groq API settings are not configured. Please configure them in the admin panel.')
                }, status=400)
        elif model_provider == 'ollama':
            from .models import APISettingsOllama
            if not APISettingsOllama.objects.first():
                return JsonResponse({
                    'success': False,
                    'error': _('Ollama API settings are not configured. Please configure them in the admin panel.')
                }, status=400)
        elif model_provider == 'deepseek':
            from .models import APISettingsDeepSeek
            if not APISettingsDeepSeek.objects.first():
                return JsonResponse({
                    'success': False,
                    'error': _('DeepSeek API settings are not configured. Please configure them in the admin panel.')
                }, status=400)
        
        # Записати час початку запиту для вимірювання часу відповіді
        start_time = time.time()
        
        # Викликати AI модель
        try:
            # Для всіх моделей передаємо системний промпт, де це підтримується
            # Функції тепер повертають tuple (response_text, usage_info)
            usage_info = None
            if model_provider == 'claude':
                ai_response, usage_info = get_claude_response(enhanced_message, conversation_history, system_prompt)
            elif model_provider == 'google':
                # Google також підтримує системні промпти через перше повідомлення
                ai_response, usage_info = get_google_response(enhanced_message, conversation_history, system_prompt)
            elif model_provider == 'groq':
                # Groq підтримує системні повідомлення
                ai_response, usage_info = get_groq_response(enhanced_message, conversation_history, system_prompt)
            elif model_provider == 'ollama':
                # Ollama підтримує системні промпти
                ai_response, usage_info = get_ollama_response(enhanced_message, conversation_history, system_prompt)
            elif model_provider == 'deepseek':
                ai_response, usage_info = get_deepseek_response(enhanced_message, conversation_history, system_prompt)
            else:
                logger.error(f"Unsupported provider: '{model_provider}' (type: {type(model_provider)})")
                logger.error(f"Model choice details: id={agent_settings.model_choice.id}, provider={agent_settings.model_choice.provider}, model_id={agent_settings.model_choice.model_id}")
                error_msg = _('Unsupported AI model provider: {}').format(model_provider)
                
                # Зберегти історію помилки
                try:
                    AIAssistantHistory.objects.create(
                        user=request.user,
                        model_choice=agent_settings.model_choice,
                        user_message=user_message,
                        ai_response=None,
                        page_url=page_context.get('url'),
                        page_type=page_context.get('page_type'),
                        page_description=page_context.get('description'),
                        is_success=False,
                        error_message=error_msg
                    )
                except Exception as history_error:
                    logger.error(f"Error saving history: {str(history_error)}")
                
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=400)
                
        except Exception as api_error:
            logger.error(f"Error calling AI model ({model_provider}): {str(api_error)}", exc_info=True)
            # Додати логування контексту для дебагу
            logger.debug(f"Page context was: {page_context}")
            logger.debug(f"Enhanced message: {enhanced_message[:200]}")
            error_msg = _('Error communicating with AI model: {}').format(str(api_error))
            
            # Зберегти історію помилки
            try:
                response_time = int((time.time() - start_time) * 1000)  # в мілісекундах
                AIAssistantHistory.objects.create(
                    user=request.user,
                    model_choice=agent_settings.model_choice,
                    user_message=user_message,
                    ai_response=None,
                    page_url=page_context.get('url'),
                    page_type=page_context.get('page_type'),
                    page_description=page_context.get('description'),
                    is_success=False,
                    error_message=error_msg,
                    response_time_ms=response_time
                )
            except Exception as history_error:
                logger.error(f"Error saving history: {str(history_error)}")
            
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=500)
        
        # Перевірити, чи відповідь не є повідомленням про помилку
        if ai_response and (ai_response.startswith('Error') or ai_response.startswith('An error') or ai_response.startswith('error')):
            # Вважаємо це помилкою
            error_msg = ai_response
            response_time = int((time.time() - start_time) * 1000)
            
            # Зберегти історію помилки
            try:
                AIAssistantHistory.objects.create(
                    user=request.user,
                    model_choice=agent_settings.model_choice,
                    user_message=user_message,
                    ai_response=None,
                    page_url=page_context.get('url'),
                    page_type=page_context.get('page_type'),
                    page_description=page_context.get('description'),
                    is_success=False,
                    error_message=error_msg,
                    response_time_ms=response_time
                )
            except Exception as history_error:
                logger.error(f"Error saving history: {str(history_error)}")
            
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=500)
        
        # Обчислити час відповіді
        response_time = int((time.time() - start_time) * 1000)  # в мілісекундах
        
        # Зберегти історію успішного запиту
        try:
            AIAssistantHistory.objects.create(
                user=request.user,
                model_choice=agent_settings.model_choice,
                user_message=user_message,
                ai_response=ai_response,
                page_url=page_context.get('url'),
                page_type=page_context.get('page_type'),
                page_description=page_context.get('description'),
                is_success=True,
                response_time_ms=response_time,
                input_tokens=usage_info.get('input_tokens') if usage_info else None,
                output_tokens=usage_info.get('output_tokens') if usage_info else None,
                total_tokens=usage_info.get('total_tokens') if usage_info else None
            )
        except Exception as history_error:
            logger.error(f"Error saving history: {str(history_error)}")
        
        return JsonResponse({
            'success': True,
            'response': ai_response,
            'model_used': agent_settings.model_choice.model_name,
            'context_type': 'page' if should_use_context else 'common'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def get_ai_agent_settings(request):
    """Отримати налаштування AI агента для поточного користувача"""
    from django.utils.translation import gettext as _
    
    try:
        agent_settings = AIAgentSettings.get_settings_for_user(request.user)
        
        if not agent_settings:
            return JsonResponse({
                'enabled': False,
                'error': _('AI Agent is not configured')
            })
        
        return JsonResponse({
            'enabled': agent_settings.is_active and agent_settings.enabled_for_all_pages,
            'model_name': agent_settings.model_choice.model_name if agent_settings.model_choice else None,
            'model_provider': agent_settings.model_choice.provider if agent_settings.model_choice else None
        })
    except Exception as e:
        return JsonResponse({
            'enabled': False,
            'error': str(e)
        })

@login_required
def get_previous_conversations(request):
    """Отримати 5 попередніх розмов для поточної сторінки"""
    from django.utils.translation import gettext as _
    from .models import AIAssistantHistory
    from datetime import timedelta
    
    try:
        # Отримати параметри з запиту
        page_url = request.GET.get('page_url', '')
        page_type = request.GET.get('page_type', '')
        
        # Фільтрувати розмови за користувачем та сторінкою
        queryset = AIAssistantHistory.objects.filter(
            user=request.user,
            is_success=True,
            ai_response__isnull=False
        ).exclude(ai_response='')
        
        # Якщо вказано page_url, фільтрувати за ним
        if page_url:
            queryset = queryset.filter(page_url=page_url)
        
        # Якщо вказано page_type, фільтрувати за ним
        if page_type:
            queryset = queryset.filter(page_type=page_type)
        
        # Отримати останні записи, відсортовані за часом
        all_records = queryset.order_by('-created_at')[:100]  # Беремо більше для групування
        
        # Групувати записи в розмови (повідомлення близькі за часом - в межах 10 хвилин)
        conversations = []
        processed_ids = set()
        
        for record in all_records:
            if record.id in processed_ids:
                continue
            
            # Знайти всі повідомлення з цієї розмови (в межах 10 хвилин до і після)
            time_window_start = record.created_at - timedelta(minutes=10)
            time_window_end = record.created_at + timedelta(minutes=10)
            
            conversation_messages = queryset.filter(
                created_at__gte=time_window_start,
                created_at__lte=time_window_end
            ).order_by('created_at')
            
            # Зібрати повідомлення розмови
            messages = []
            for msg in conversation_messages:
                if msg.id in processed_ids:
                    continue
                messages.append({
                    'role': 'user',
                    'content': msg.user_message,
                    'timestamp': msg.created_at.isoformat()
                })
                if msg.ai_response:
                    # Визначити тип контексту на основі наявності page_url та page_type
                    context_type = 'common'
                    if msg.page_url and msg.page_type:
                        context_type = 'page'
                    
                    messages.append({
                        'role': 'assistant',
                        'content': msg.ai_response,
                        'timestamp': msg.created_at.isoformat(),
                        'context_type': context_type
                    })
                processed_ids.add(msg.id)
            
            # Додати розмову, якщо є повідомлення
            if messages:
                user_messages = [m for m in messages if m['role'] == 'user']
                if user_messages:
                    first_user_msg = user_messages[0]['content']
                    conversations.append({
                        'id': record.id,
                        'title': first_user_msg[:50] + ('...' if len(first_user_msg) > 50 else ''),
                        'page_description': record.page_description or '',
                        'created_at': record.created_at.isoformat(),
                        'messages': messages,
                        'message_count': len(user_messages)
                    })
            
            if len(conversations) >= 5:
                break
        
        return JsonResponse({
            'success': True,
            'conversations': conversations
        })
        
    except Exception as e:
        logger.error(f"Error getting previous conversations: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)