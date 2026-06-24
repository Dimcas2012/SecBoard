# SecBoard/app_ai/translate_po_clear_ai.py
import os
import sys
import polib
import anthropic
import time
import re

from SecBoard.credential import api_key_claude

# Get the absolute path of the current script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Get the project root directory (two levels up from app_ai)
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

# Add the Django project root to the Python path
sys.path.append(PROJECT_ROOT)

# Manual configuration (use this if not running in Django environment)
MANUAL_CONFIG = {
    'api_key': api_key_claude,
    'model_name': 'claude-3-sonnet-20240229',
    'max_tokens': 1000,
    'temperature': 0.2,
}

# Updated paths relative to project root
ru_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'ru', 'LC_MESSAGES', 'django.po')
uk_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'uk', 'LC_MESSAGES', 'django.po')


def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SecBoard.settings")
    import django
    django.setup()


def get_claude_settings():
    try:
        setup_django()
        from .models import APISettingsClaude
        return APISettingsClaude.objects.first()
    except Exception as e:
        print(f"Failed to load Django settings: {e}")
        print("Using manual configuration.")
        return type('ObjectLike', (), MANUAL_CONFIG)()


def clean_po_file(po_file):
    for entry in po_file:
        entry.flags = [flag for flag in entry.flags if flag != 'fuzzy']
        entry.previous_msgid = None
        entry.previous_msgid_plural = None
        entry.previous_msgctxt = None


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
    """
    Remove all types of apostrophes and quotes from the text.
    Handles various Unicode apostrophes and quotes.
    """
    # List of all possible apostrophe and quote characters
    apostrophes = ["'", "'", "'", "`", "'", "‛", "′", "‵", "'", "'"]

    # Remove all types of apostrophes
    for apostrophe in apostrophes:
        text = text.replace(apostrophe, "")

    # Double check with regex to catch any remaining apostrophes
    text = re.sub(r'[''`′‵‛]', '', text)

    return text


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
            print(f"WARNING: Python format placeholder {python_fmt} missing in translation")
    
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


def translate_entry_ai(entry, target_lang, client, claude_settings):
    """Translate a single PO entry using Claude AI."""
    try:
        prompt = generate_translation_prompt(entry.msgid, target_lang)

        response = client.messages.create(
            model=claude_settings.model_name,
            max_tokens=claude_settings.max_tokens,
            temperature=claude_settings.temperature,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        translation = response.content[0].text.strip()

        # Clean translation of any apostrophes
        cleaned_translation = remove_apostrophes(translation)

        if translation != cleaned_translation:
            print(f"  > Removed apostrophes from translation")

        # Preserve format strings and fix format issues
        format_preserved_translation = preserve_format_strings(entry.msgid, cleaned_translation)
        
        if cleaned_translation != format_preserved_translation:
            print(f"  > Fixed format strings in translation")
        
        # Format msgstr to match msgid structure (multiline format)
        properly_formatted_translation = format_msgstr_like_msgid(entry.msgid, format_preserved_translation)
        
        if format_preserved_translation != properly_formatted_translation:
            print(f"  > Formatted translation to match msgid structure")
        
        # Validate the final translation
        is_valid, error_message = validate_translation(entry.msgid, properly_formatted_translation)
        
        if not is_valid:
            print(f"  ! WARNING: Translation validation failed: {error_message}")
            # Still proceed with the translation but log the warning

        entry.msgstr = properly_formatted_translation
        return True
    except Exception as e:
        print(f"  X Error: {str(e)}")
        return False


def main():
    try:
        print("Starting PO file translation process...")
        print(f"Project root directory: {PROJECT_ROOT}")
        print(f"Russian PO file path: {ru_po_file_path}")
        print(f"Ukrainian PO file path: {uk_po_file_path}")

        # Get Claude API settings
        claude_settings = get_claude_settings()
        print(f"Using Claude model: {claude_settings.model_name}")

        # Initialize Claude client
        client = anthropic.Anthropic(api_key=claude_settings.api_key)
        print("Claude client initialized")

        # Ensure the paths exist
        for path in [ru_po_file_path, uk_po_file_path]:
            if not os.path.exists(path):
                print(f"Warning: Path does not exist: {path}")
                print(f"Current working directory: {os.getcwd()}")
                print(f"Script directory: {SCRIPT_DIR}")
                print("Please ensure you're running the script from the correct directory")
                return

        # Open .po files
        ru_po = polib.pofile(ru_po_file_path)
        uk_po = polib.pofile(uk_po_file_path)
        print(f"Opened Russian PO file: {ru_po_file_path}")
        print(f"Opened Ukrainian PO file: {uk_po_file_path}")

        # First, collect all empty (untranslated) entries
        print("\nCollecting empty strings that need translation...")
        ru_entries_to_translate = []
        uk_entries_to_translate = []
        
        for ru_entry, uk_entry in zip(ru_po, uk_po):
            if not is_entry_translated(ru_entry):
                ru_entries_to_translate.append(ru_entry)
            if not is_entry_translated(uk_entry):
                uk_entries_to_translate.append(uk_entry)
        
        total_entries = len(ru_po)
        total_ru_to_translate = len(ru_entries_to_translate)
        total_uk_to_translate = len(uk_entries_to_translate)
        ru_skipped_count = total_entries - total_ru_to_translate
        uk_skipped_count = total_entries - total_uk_to_translate
        
        print(f"\nTotal entries in PO files: {total_entries}")
        print(f"Russian: {total_ru_to_translate} to translate, {ru_skipped_count} already translated")
        print(f"Ukrainian: {total_uk_to_translate} to translate, {uk_skipped_count} already translated")
        
        if total_ru_to_translate == 0 and total_uk_to_translate == 0:
            print("\nNo empty strings found. All entries are already translated!")
            return
        
        # Now translate only the empty entries
        ru_translated_count = 0
        uk_translated_count = 0
        
        print("\n" + "="*60)
        print("Starting translation of empty strings...")
        print("="*60)
        
        # Translate Russian entries
        if total_ru_to_translate > 0:
            print(f"\n{'='*60}")
            print(f"[RUSSIAN TRANSLATION] Translating {total_ru_to_translate} entries...")
            print(f"{'='*60}")
            for i, ru_entry in enumerate(ru_entries_to_translate, 1):
                print(f"\n--- [RU] Entry {i}/{total_ru_to_translate} ---")
                print(f"Original (EN): {ru_entry.msgid}")
                if translate_entry_ai(ru_entry, 'Russian', client, claude_settings):
                    ru_translated_count += 1
                    print(f"Translation (RU): {ru_entry.msgstr}")
                print(f"Progress: {i}/{total_ru_to_translate} ({ru_translated_count} successful)")
                time.sleep(1)
        
        # Translate Ukrainian entries
        if total_uk_to_translate > 0:
            print(f"\n{'='*60}")
            print(f"[UKRAINIAN TRANSLATION] Translating {total_uk_to_translate} entries...")
            print(f"{'='*60}")
            for i, uk_entry in enumerate(uk_entries_to_translate, 1):
                print(f"\n--- [UK] Entry {i}/{total_uk_to_translate} ---")
                print(f"Original (EN): {uk_entry.msgid}")
                if translate_entry_ai(uk_entry, 'Ukrainian', client, claude_settings):
                    uk_translated_count += 1
                    print(f"Translation (UK): {uk_entry.msgstr}")
                print(f"Progress: {i}/{total_uk_to_translate} ({uk_translated_count} successful)")
                time.sleep(1)

        print("\nCleaning PO files of specific comments...")
        clean_po_file(ru_po)
        clean_po_file(uk_po)

        print("Saving changes to PO files...")
        ru_po.save()
        uk_po.save()

        print(f"\nTranslation process completed!")
        print(f"Russian translations: {ru_translated_count} new, {ru_skipped_count} skipped")
        print(f"Ukrainian translations: {uk_translated_count} new, {uk_skipped_count} skipped")

        print("\nTo apply the translations:")
        print("1. Review the translations in the .po files")
        print("2. Compile with: python manage.py compilemessages")
        print("3. Restart your Django server")
        print("4. Clear your browser cache if needed")

    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
