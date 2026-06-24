# SecBoard/app_std/iso27002_import_ai.py
import os
import sqlite3
import json
import logging
from typing import Optional, Dict, List
import anthropic
from deep_translator import GoogleTranslator
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ISO27002Importer:
    def __init__(self, db_path: str, api_key: str):
        self.db_path = db_path
        self.client = anthropic.Anthropic(api_key=api_key)
        self.translator = TranslationManager()

    def setup_database(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_std_iso27002theme (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_std_iso27002control (
                    id INTEGER PRIMARY KEY,
                    control_number TEXT,
                    title TEXT,
                    control_description TEXT,
                    purpose TEXT,
                    guidance TEXT,
                    other_information TEXT,
                    control_type TEXT,
                    information_security_properties JSON,
                    cybersecurity_concepts JSON,
                    operational_capabilities JSON,
                    security_domain TEXT,
                    theme_id INTEGER,
                    FOREIGN KEY (theme_id) REFERENCES app_std_iso27002theme (id)
                )
            """)
            conn.commit()

    def _split_controls(self, text: str) -> List[str]:
        controls = []
        current_control = []

        for line in text.split('\n'):
            # Match any control number (e.g., 5.1, 6.1, etc.)
            if (line.strip() and
                    any(line.strip().startswith(f"{n}.") for n in range(1, 10)) and
                    line.strip()[2].isdigit()):
                if current_control:
                    controls.append('\n'.join(current_control))
                current_control = [line]
            elif current_control:
                current_control.append(line)

        if current_control:
            controls.append('\n'.join(current_control))

        return controls

    def get_claude_response(self, iso_text: str) -> Optional[dict]:
        control_chunks = self._split_controls(iso_text)
        all_controls = []

        for chunk in control_chunks:
            prompt = self._build_prompt(chunk)
            try:
                message = self.client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=4000,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}]
                )

                response_text = message.content[0].text
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1

                if json_start == -1 or json_end == -1:
                    logger.error(f"No JSON found in response for chunk starting with: {chunk[:100]}...")
                    continue

                json_str = response_text[json_start:json_end]
                chunk_data = json.loads(json_str)

                if 'controls' in chunk_data and chunk_data['controls']:
                    all_controls.extend(chunk_data['controls'])

            except Exception as e:
                logger.error(f"Error processing chunk: {e}")
                continue

        return {
            'controls': all_controls,
            'themes': ["Organizational", "People", "Physical", "Technological"]
        }

    def process_controls(self, data: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            theme_ids = self._insert_themes(cursor, data.get('themes', []))

            controls = data.get('controls', [])
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                for control in controls:
                    futures.append(
                        executor.submit(
                            self._process_single_control,
                            control,
                            theme_ids
                        )
                    )

                for future in as_completed(futures):
                    try:
                        control_data = future.result()
                        if control_data:
                            self._insert_control(cursor, control_data)
                    except Exception as e:
                        logger.error(f"Error processing control: {e}")

            conn.commit()

    def _insert_themes(self, cursor: sqlite3.Cursor, themes: List[str]) -> Dict[str, int]:
        theme_ids = {}
        for theme in themes:
            cursor.execute(
                "INSERT OR IGNORE INTO app_std_iso27002theme (name) VALUES (?)",
                (theme,)
            )
            cursor.execute(
                "SELECT id FROM app_std_iso27002theme WHERE name = ?",
                (theme,)
            )
            theme_ids[theme] = cursor.fetchone()[0]
        return theme_ids

    def _process_single_control(self, control: dict, theme_ids: Dict[str, int]) -> Optional[tuple]:
        try:
            theme_name = control.get('theme', 'Organizational')
            theme_id = theme_ids.get(theme_name)

            if not theme_id:
                logger.warning(f"No theme ID found for {theme_name}")
                return None

            translations = self.translator.translate_control_fields(control)

            title = control.get('title_en', '') or translations.get('title_uk', '')
            control_desc = control.get('control_description', '') or translations.get('description_uk', '')
            purpose = control.get('purpose', '') or translations.get('purpose_uk', '')
            guidance = control.get('guidance_en', '') or translations.get('guidance_uk', '')
            other_info = control.get('other_information', '') or translations.get('other_info_uk', '')
            security_domain = (control.get('security_domains') or [''])[0] if control.get('security_domains') else ''
            return (
                control['control_number'],
                title,
                control_desc,
                purpose,
                guidance,
                other_info,
                control.get('control_type', [''])[0],
                json.dumps(control.get('security_properties', [])),
                json.dumps(control.get('cybersecurity_concepts', [])),
                json.dumps(control.get('operational_capabilities', [])),
                security_domain,
                theme_id
            )
        except Exception as e:
            logger.error(f"Error processing control {control.get('control_number')}: {e}")
            return None

    def _insert_control(self, cursor: sqlite3.Cursor, control_data: tuple) -> None:
        cursor.execute("""
            INSERT INTO app_std_iso27002control (
                control_number, title, control_description, purpose, guidance, other_information,
                control_type, information_security_properties, cybersecurity_concepts,
                operational_capabilities, security_domain, theme_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, control_data)

    @staticmethod
    def _build_prompt(iso_text: str) -> str:
        return f"""
        Parse ALL controls in the ISO 27002:2022 text into a COMPLETE JSON format WITHOUT ANY ADDITIONAL COMMENTARY.

        CRITICAL INSTRUCTION: Ensure FULL, COMPLETE guidance text is extracted, including ALL details after 'procedures for handling exemptions and exceptions'.

        {{
          "controls": [
            {{
              "control_number": "Exact control number from text",
              "title_en": "Control title",
              "control_type": ["Preventive", "Detective", "Corrective"],
              "security_properties": ["Confidentiality", "Integrity", "Availability"],
              "cybersecurity_concepts": ["Identify", "Protect", "Detect", "Respond"],
              "operational_capabilities": ["Governance", "Resilience", "Defence"],
              "security_domains": ["Governance"],
              "control_description": "Complete control description text",
              "purpose": "Complete purpose text",
              "guidance_en": "FULL guidance text WITH ALL DETAILS, ensuring NO TRUNCATION",
              "other_information": "Complete other information text",
              "theme": "Organizational"
            }}
          ],
          "themes": ["Organizational", "People", "Physical", "Technological"]
        }}

        STRICT INSTRUCTIONS:
        1. Parse ALL controls in the text
        2. Provide FULL JSON WITHOUT ANY ADDITIONAL TEXT
        3. Include COMPLETE details for EVERY control
        4. EXACTLY match the provided JSON structure
        5. NO COMMENTARY OR ADDITIONAL NOTES
        6. PRESERVE FULL GUIDANCE TEXT WITHOUT TRUNCATION

        ISO text: {iso_text}
        """


class TranslationManager:
    def __init__(self):
        self.translators = {
            'uk': GoogleTranslator(source='auto', target='uk'),
            'ru': GoogleTranslator(source='auto', target='ru')
        }

    @lru_cache(maxsize=1000)
    def translate_text(self, text: str, target_lang: str) -> str:
        if not text:
            return ""
        try:
            return self.translators[target_lang].translate(text)
        except Exception as e:
            logger.error(f"Translation error to {target_lang}: {e}")
            return text

    def translate_control_fields(self, control: dict) -> dict:
        return {
            'title_uk': self.translate_text(control.get('title_en', ''), 'uk'),
            'title_ru': self.translate_text(control.get('title_en', ''), 'ru'),
            'description_uk': self.translate_text(control.get('control_description', ''), 'uk'),
            'description_ru': self.translate_text(control.get('control_description', ''), 'ru'),
            'purpose_uk': self.translate_text(control.get('purpose', ''), 'uk'),
            'purpose_ru': self.translate_text(control.get('purpose', ''), 'ru'),
            'guidance_uk': self.translate_text(control.get('guidance_en', ''), 'uk'),
            'guidance_ru': self.translate_text(control.get('guidance_en', ''), 'ru'),
            'other_info_uk': self.translate_text(control.get('other_information', ''), 'uk'),
            'other_info_ru': self.translate_text(control.get('other_information', ''), 'ru')
        }


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_file = os.path.join(script_dir, '../db.sqlite3')
    iso_file = os.path.join(script_dir, 'ISO_IEC_27002_2022.txt')

    try:
        with open(iso_file, 'r', encoding='utf-8') as file:
            iso_text = file.read()
    except Exception as e:
        logger.error(f"Error reading ISO file: {e}")
        return

    try:
        import sys
        import django
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SecBoard.settings')
        django.setup()
        from app_ai.ai_utils import get_claude_api_key
        api_key = get_claude_api_key()
        if not api_key:
            logger.error('Claude API key not configured. Set it in Admin › App_Ai › API Settings Claude.')
            return
        importer = ISO27002Importer(db_file, api_key)
        importer.setup_database()

        data = importer.get_claude_response(iso_text)
        if data:
            importer.process_controls(data)
            logger.info(f"Successfully imported {len(data.get('controls', []))} controls")
    except Exception as e:
        logger.error(f"Error during import process: {e}")


if __name__ == "__main__":
    main()