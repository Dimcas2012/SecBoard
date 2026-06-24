# SecBoard/app_conf/translate_po.py
"""
PO File Translation Script with Google Translator Support

This script translates Django PO files (Russian and Ukrainian) using Google Translator.

USAGE:
    python SecBoard/app_conf/translate_po.py [--languages LANG1,LANG2]
    
    Examples:
        python SecBoard/app_conf/translate_po.py                    # Translate both ru and uk
        python SecBoard/app_conf/translate_po.py --languages ru     # Translate only Russian
        python SecBoard/app_conf/translate_po.py --languages uk     # Translate only Ukrainian
        python SecBoard/app_conf/translate_po.py --languages ru,uk  # Translate both

FEATURES:
    - Uses Google Translator (free, no API key required)
    - Automatically translates untranslated strings in PO files
    - Removes apostrophes from translations
    - Cleans fuzzy flags and previous message comments
    - Select specific languages to translate

ALTERNATIVE:
    For better translation quality with AI models (Claude, Google Gemini, Groq, etc.),
    use the web interface at: /ai/translate-po/
    
    The web interface provides:
    - Multiple AI model options
    - Real-time progress tracking
    - Better translation quality
    - Configurable translation options
    - Language selection via UI
"""
import os
import polib
from deep_translator import GoogleTranslator
import time
import re
import sys
import argparse

# Get the absolute path of the current script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Get the project root directory (two levels up from app_conf)
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

# Updated paths relative to project root
ru_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'ru', 'LC_MESSAGES', 'django.po')
uk_po_file_path = os.path.join(PROJECT_ROOT, 'SecBoard', 'locale', 'uk', 'LC_MESSAGES', 'django.po')

# Translation method configuration
# Options: 'google_translate' (default, free), 'ai' (requires AI configuration)
TRANSLATION_METHOD = 'google_translate'

# Initialize Google translators (used for 'google_translate' method)
ru_translator = GoogleTranslator(source='en', target='ru')
uk_translator = GoogleTranslator(source='en', target='uk')


def remove_all_apostrophes(text):
    """
    Remove all types of apostrophes and quotes from the text.
    """
    # List of all possible apostrophe and quote characters
    apostrophes = ["'", "'", "'", "`", "'", "‛", "′", "‵", "'", "'"]

    # Remove all types of apostrophes
    for apostrophe in apostrophes:
        text = text.replace(apostrophe, "")

    # Double check with regex to catch any remaining apostrophes
    text = re.sub(r'[''`′‵‛]', '', text)

    return text


def clean_po_file(po_file):
    for entry in po_file:
        # Remove fuzzy flags
        entry.flags = [flag for flag in entry.flags if flag != 'fuzzy']

        # Remove previous message comments
        entry.previous_msgid = None
        entry.previous_msgid_plural = None
        entry.previous_msgctxt = None

        # Clean apostrophes from existing translations
        if entry.msgstr:
            original_msgstr = entry.msgstr
            cleaned_msgstr = remove_all_apostrophes(entry.msgstr)
            if original_msgstr != cleaned_msgstr:
                print("Видалено апострофи з перекладу:")
                print(f"Оригінал: {original_msgstr}")
                print(f"Очищено: {cleaned_msgstr}")
                entry.msgstr = cleaned_msgstr


def translate_entry(entry, translator, lang):
    """
    Translate a PO entry using the selected translation method.
    
    Args:
        entry: PO file entry to translate
        translator: GoogleTranslator instance (for google_translate method)
        lang: Target language code ('ru' or 'uk')
    
    Returns:
        bool: True if translation was successful, False otherwise
    """
    if not entry.msgstr:
        try:
            if TRANSLATION_METHOD == 'google_translate':
                # Use Google Translator (free, no API key required)
                translation = translator.translate(entry.msgid)
            elif TRANSLATION_METHOD == 'ai':
                # This would require AI configuration from Django settings
                # For standalone script, use google_translate instead
                print(f"[{lang.upper()}] AI translation method requires Django environment. Using Google Translator instead.")
                translation = translator.translate(entry.msgid)
            else:
                # Default to Google Translator
                translation = translator.translate(entry.msgid)

            # Clean any apostrophes from the translation
            original_translation = translation
            cleaned_translation = remove_all_apostrophes(translation)

            if original_translation != cleaned_translation:
                print(f"[{lang.upper()}] Виявлено апострофи в перекладі. Видаляємо їх.")
                print(f"[{lang.upper()}] Оригінальний переклад: {original_translation}")
                print(f"[{lang.upper()}] Очищений переклад: {cleaned_translation}")
            else:
                print(f"[{lang.upper()}] Апострофів у перекладі не виявлено.")

            entry.msgstr = cleaned_translation
            print(f"\n[{lang.upper()}] Переклад: {entry.msgid}")
            print(f"[{lang.upper()}] Кінцевий результат: {cleaned_translation}")
            return True
        except Exception as e:
            print(f"\n[{lang.upper()}] Помилка при перекладі {entry.msgid}: {str(e)}")
    return False


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Translate Django PO files using Google Translator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                        Translate both Russian and Ukrainian
  %(prog)s --languages ru         Translate only Russian
  %(prog)s --languages uk         Translate only Ukrainian
  %(prog)s --languages ru,uk      Translate both Russian and Ukrainian
        '''
    )
    parser.add_argument(
        '--languages',
        type=str,
        default='ru,uk',
        help='Comma-separated list of languages to translate (ru, uk). Default: ru,uk'
    )
    
    args = parser.parse_args()
    
    # Parse languages
    selected_languages = [lang.strip().lower() for lang in args.languages.split(',')]
    translate_russian = 'ru' in selected_languages
    translate_ukrainian = 'uk' in selected_languages
    
    # Validate languages
    if not translate_russian and not translate_ukrainian:
        print("Помилка: Необхідно вибрати хоча б одну мову для перекладу (ru або uk)")
        print("Використання: python SecBoard/app_conf/translate_po.py --languages ru,uk")
        return
    
    try:
        print("=" * 70)
        print("Починаємо процес перекладу PO файлів...")
        print("=" * 70)
        print(f"Метод перекладу: {TRANSLATION_METHOD}")
        if TRANSLATION_METHOD == 'google_translate':
            print("Використовується Google Translator (безкоштовний, без API ключа)")
        print(f"Кореневий каталог проекту: {PROJECT_ROOT}")
        
        # Display selected languages
        print("\nВибрані мови для перекладу:")
        if translate_russian:
            print(f"  ✓ Російська (ru): {ru_po_file_path}")
        if translate_ukrainian:
            print(f"  ✓ Українська (uk): {uk_po_file_path}")

        # Prepare PO files and counters
        po_files = {}
        translators = {}
        translated_counts = {}
        
        if translate_russian:
            if not os.path.exists(ru_po_file_path):
                print(f"Попередження: Російський PO файл не знайдено: {ru_po_file_path}")
                print(f"Поточний робочий каталог: {os.getcwd()}")
                print(f"Каталог скрипта: {SCRIPT_DIR}")
                return
            po_files['ru'] = polib.pofile(ru_po_file_path)
            translators['ru'] = ru_translator
            translated_counts['ru'] = 0
            print(f"Відкрито російський PO файл: {ru_po_file_path}")
        
        if translate_ukrainian:
            if not os.path.exists(uk_po_file_path):
                print(f"Попередження: Український PO файл не знайдено: {uk_po_file_path}")
                print(f"Поточний робочий каталог: {os.getcwd()}")
                print(f"Каталог скрипта: {SCRIPT_DIR}")
                return
            po_files['uk'] = polib.pofile(uk_po_file_path)
            translators['uk'] = uk_translator
            translated_counts['uk'] = 0
            print(f"Відкрито український PO файл: {uk_po_file_path}")

        # Get total entries (use first available language)
        first_lang = list(po_files.keys())[0]
        total_entries = len(po_files[first_lang])
        
        print(f"\nВсього записів для обробки: {total_entries}")

        # Process all entries
        for i in range(total_entries):
            print(f"\n--- Обробка запису {i+1}/{total_entries} ---")
            
            # Translate for each selected language
            for lang in po_files.keys():
                entry = po_files[lang][i]
                if translate_entry(entry, translators[lang], lang):
                    translated_counts[lang] += 1
            
            # Show progress
            progress_str = f"\nПрогрес: {i+1}/{total_entries}"
            for lang in po_files.keys():
                progress_str += f", {lang.upper()}: {translated_counts[lang]}/{total_entries}"
            print(progress_str)

            time.sleep(1)

        print("\nОчищення PO файлів від специфічних коментарів...")
        for lang, po_file in po_files.items():
            clean_po_file(po_file)

        print("Збереження змін у PO файли...")
        for lang, po_file in po_files.items():
            po_file.save()

        print(f"\nПереклад завершено!")
        for lang in po_files.keys():
            lang_name = "російську" if lang == 'ru' else "українську"
            print(f"Перекладено на {lang_name}: {translated_counts[lang]} записів з {total_entries}")

        print("\nДля застосування перекладів:")
        print("1. Перевірте якість перекладів у PO файлах")
        print("2. Скомпілюйте командою: python manage.py compilemessages")
        print("3. Перезапустіть Django сервер")
        print("4. За потреби очистіть кеш браузера")

    except Exception as e:
        print(f"Виникла помилка: {str(e)}")


if __name__ == "__main__":
    main()