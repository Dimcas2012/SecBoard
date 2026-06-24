import os
import sys
import traceback

# Get the absolute path of the current script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Get the project root directory (two levels up from app_conf)
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

def setup_po_files():
    try:
        print("Starting PO file setup script...")
        print(f"Script directory: {SCRIPT_DIR}")
        print(f"Project root: {PROJECT_ROOT}")
        
        # Define the locale directory and language paths
        locale_dir = os.path.join(PROJECT_ROOT, 'locale')
        ru_dir = os.path.join(locale_dir, 'ru', 'LC_MESSAGES')
        uk_dir = os.path.join(locale_dir, 'uk', 'LC_MESSAGES')
        
        print(f"Locale directory: {locale_dir}")
        print(f"Russian directory: {ru_dir}")
        print(f"Ukrainian directory: {uk_dir}")
        
        # Create directories if they don't exist
        for directory in [locale_dir, ru_dir, uk_dir]:
            if not os.path.exists(directory):
                print(f"Creating directory: {directory}")
                os.makedirs(directory, exist_ok=True)
            else:
                print(f"Directory already exists: {directory}")
        
        # Define PO file paths
        ru_po_file_path = os.path.join(ru_dir, 'django.po')
        uk_po_file_path = os.path.join(uk_dir, 'django.po')
        
        print(f"Russian PO file path: {ru_po_file_path}")
        print(f"Ukrainian PO file path: {uk_po_file_path}")
        
        # Create empty PO files if they don't exist
        for po_path, lang in [(ru_po_file_path, 'Russian'), (uk_po_file_path, 'Ukrainian')]:
            if not os.path.exists(po_path):
                print(f"Creating empty {lang} PO file: {po_path}")
                # Create an empty file first
                with open(po_path, 'w', encoding='utf-8') as f:
                    f.write('msgid ""\nmsgstr ""\n')
                    f.write('"Project-Id-Version: SecBoard\\n"\n')
                    f.write('"Report-Msgid-Bugs-To: \\n"\n')
                    f.write('"POT-Creation-Date: 2024-01-01 12:00+0000\\n"\n')
                    f.write('"PO-Revision-Date: 2024-01-01 12:00+0000\\n"\n')
                    f.write('"Last-Translator: \\n"\n')
                    f.write(f'"Language-Team: {lang}\\n"\n')
                    f.write(f'"Language: {"ru" if lang == "Russian" else "uk"}\\n"\n')
                    f.write('"MIME-Version: 1.0\\n"\n')
                    f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
                    f.write('"Content-Transfer-Encoding: 8bit\\n"\n')
                    f.write('"Plural-Forms: nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);\\n"\n')
                print(f"Created {lang} PO file successfully")
            else:
                print(f"{lang} PO file already exists: {po_path}")
        
        print("\nTo generate real translatable strings, run:")
        print("python manage.py makemessages -l ru -l uk")
        print("\nPO file setup completed successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    setup_po_files()

