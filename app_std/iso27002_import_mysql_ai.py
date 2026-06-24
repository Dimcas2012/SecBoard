import os
import json
import logging
from typing import Optional, Dict, List
import anthropic
import pymysql
import pymysql.err
from deep_translator import GoogleTranslator
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ISO27002Importer:
    def __init__(self, config: dict, api_key: str):
        self.db_config = {
            'host': config['HOST'],
            'user': config['USER'],
            'password': config['PASSWORD'],
            'database': config['NAME'],
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci'
        }
        self.client = anthropic.Anthropic(api_key=api_key)
        self.translator = TranslationManager()

    def get_connection(self):
        return pymysql.connect(**self.db_config)

    def _split_controls(self, text: str) -> List[str]:
        controls = []
        current_control = []

        for line in text.split('\n'):
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
        logger.info(f"Processing {len(control_chunks)} control chunks")

        for i, chunk in enumerate(control_chunks, 1):
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
                    logger.error(f"No JSON found in response for chunk {i}")
                    continue

                json_str = response_text[json_start:json_end]
                chunk_data = json.loads(json_str)

                if 'controls' in chunk_data and chunk_data['controls']:
                    all_controls.extend(chunk_data['controls'])
                    logger.info(f"Successfully processed chunk {i}")

            except Exception as e:
                logger.error(f"Error processing chunk {i}: {e}")
                continue

        return {
            'controls': all_controls,
            'themes': ["Organizational", "People", "Physical", "Technological"]
        }

    def process_controls(self, data: dict) -> None:
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            theme_ids = self._insert_themes(cursor, data.get('themes', []))
            conn.commit()

            controls = data.get('controls', [])
            processed = 0

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
                            processed += 1
                            if processed % 10 == 0:
                                conn.commit()
                                logger.info(f"Committed {processed} controls")
                    except Exception as e:
                        logger.error(f"Error processing control: {e}")
                        conn.rollback()

            conn.commit()
            logger.info(f"Successfully processed and committed {processed} controls")

        except pymysql.Error as e:
            logger.error(f"MySQL Error: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _insert_themes(self, cursor: pymysql.cursors.Cursor, themes: List[str]) -> Dict[str, int]:
        theme_ids = {}
        for theme in themes:
            try:
                cursor.execute("""
                    INSERT INTO app_std_iso27002theme (name, description)
                    VALUES (%s, %s)
                """, (theme, ''))
            except pymysql.err.IntegrityError as e:
                if e.args[0] == 1062:  # Duplicate entry error
                    pass
                else:
                    logger.error(f"Error inserting theme {theme}: {e}")

            cursor.execute("SELECT id FROM app_std_iso27002theme WHERE name = %s", (theme,))
            result = cursor.fetchone()
            if result:
                theme_ids[theme] = result[0]
                logger.info(f"Theme {theme} has ID {result[0]}")
        return theme_ids

    def _process_single_control(self, control: dict, theme_ids: Dict[str, int]) -> Optional[tuple]:
        try:
            theme_name = control.get('theme', 'Organizational')
            theme_id = theme_ids.get(theme_name)

            if not theme_id:
                logger.warning(f"No theme ID found for {theme_name}")
                return None

            translations = self.translator.translate_control_fields(control)
            security_domain = control.get('security_domains', [])[0] if control.get('security_domains') else ''

            title = control.get('title_en', '') or translations.get('title_uk', '')
            control_desc = control.get('control_description', '') or translations.get('description_uk', '')
            purpose = control.get('purpose', '') or translations.get('purpose_uk', '')
            guidance = control.get('guidance_en', '') or translations.get('guidance_uk', '')
            other_info = control.get('other_information', '') or translations.get('other_info_uk', '')
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

    def _insert_control(self, cursor: pymysql.cursors.Cursor, control_data: tuple) -> None:
        try:
            cursor.execute("""
                INSERT INTO app_std_iso27002control (
                    control_number, title, control_description, purpose, guidance, other_information,
                    control_type, information_security_properties, cybersecurity_concepts,
                    operational_capabilities, security_domain, theme_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, control_data)
            logger.info(f"Inserted control {control_data[0]}")
        except pymysql.Error as e:
            logger.error(f"Error inserting control {control_data[0]}: {e}")

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
    iso_file = os.path.join(script_dir, 'ISO_IEC_27002_2022.txt')

    db_config = {
        'NAME': os.environ.get('DB_NAME', 'secboard_db'),
        'USER': os.environ.get('DB_USER', 'secboard_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }

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
        importer = ISO27002Importer(db_config, api_key)

        data = importer.get_claude_response(iso_text)
        if data:
            importer.process_controls(data)
            logger.info(f"Successfully imported {len(data.get('controls', []))} controls")
    except Exception as e:
        logger.error(f"Error during import process: {e}")


if __name__ == "__main__":
    main()