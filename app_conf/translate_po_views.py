# Translation PO Views (moved from app_ai)
# This file contains all translate_po related views and functions

from django.shortcuts import render
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
import logging

from app_conf.models import AccessOption
from app_ai.models import APISettingsClaude, APISettingsGoogle, APISettingsGroq, APISettingsOllama, APISettingsDeepSeek

logger = logging.getLogger(__name__)

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


def check_translation_po_access(user):
    """Check if user has access to Translation PO"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return AccessOption.user_has_translation_po_access(user)


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
            logger.warning(f"Python format placeholder {python_fmt} missing in translation")
    
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


def log_message(message):
    """Add a message to the log"""
    global translation_progress
    translation_progress['log'].append({
        'time': time.strftime('%H:%M:%S'),
        'message': message
    })
    logger.info(message)


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
            settings = APISettingsClaude.objects.first()
            if settings:
                model_available = True
                log_message(f"Using Claude model: {settings.model_name.model_id}")
        elif selected_model == 'google':
            settings = APISettingsGoogle.objects.first()
            if settings:
                model_available = True
                log_message(f"Using Google Gemini model: {settings.model_name.model_id}")
        elif selected_model == 'groq':
            settings = APISettingsGroq.objects.first()
            if settings:
                model_available = True
                log_message(f"Using Groq model: {settings.model_name.model_id}")
        elif selected_model == 'ollama':
            settings = APISettingsOllama.objects.first()
            if settings:
                model_available = True
                log_message(f"Using Ollama model: {settings.model_name.model_id}")
        elif selected_model == 'deepseek':
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

