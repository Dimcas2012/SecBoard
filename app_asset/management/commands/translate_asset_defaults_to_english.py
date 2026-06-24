"""
Management command: check default fields (name, description) in Asset Group,
Asset Type, and Criticality Level; translate any Ukrainian/Russian values to English.
Uses deep_translator GoogleTranslator(source='auto', target='en').
"""
import re
from django.core.management.base import BaseCommand
from django.db import transaction

from app_asset.models import AssetGroup, AssetType, CriticalityLevel


def contains_cyrillic(text):
    """Return True if text contains Cyrillic characters (needs translation to En)."""
    if not text or not isinstance(text, str):
        return False
    return bool(re.search(r'[\u0400-\u04FF]', text))


def translate_to_english(text):
    """Translate text to English using GoogleTranslator. Returns original on failure."""
    if not text or not text.strip():
        return text
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target='en')
        return translator.translate(text.strip())
    except Exception as e:
        return text  # keep original on error


def safe_str(s, max_len=80):
    """Return string safe for Windows console (ASCII, replace non-ASCII)."""
    if not s:
        return ''
    s = str(s)[:max_len]
    return s.encode('ascii', errors='replace').decode('ascii')


class Command(BaseCommand):
    help = (
        'Check Asset Group, Asset Type, and Criticality Level default fields (name, description). '
        'Translate any Ukrainian/Russian values to English.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only show what would be changed, do not save.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: no changes will be saved.'))

        updated_counts = {'AssetGroup': 0, 'AssetType': 0, 'CriticalityLevel': 0}

        with transaction.atomic():
            # --- AssetGroup: name, description (default = En) ---
            for obj in AssetGroup.objects.all():
                changed = False
                if contains_cyrillic(obj.name):
                    new_name = translate_to_english(obj.name)
                    self.stdout.write(f'AssetGroup id={obj.id} name: (cyrillic) -> "{safe_str(new_name)}"')
                    if not dry_run:
                        obj.name = new_name
                    changed = True
                if obj.description and contains_cyrillic(obj.description):
                    new_desc = translate_to_english(obj.description)
                    self.stdout.write(f'AssetGroup id={obj.id} description: (cyrillic) -> "{safe_str(new_desc, 60)}..."')
                    if not dry_run:
                        obj.description = new_desc
                    changed = True
                if changed:
                    if not dry_run:
                        obj.save()
                    updated_counts['AssetGroup'] += 1

            # --- AssetType: name, description (default = En) ---
            for obj in AssetType.objects.all():
                changed = False
                if contains_cyrillic(obj.name):
                    new_name = translate_to_english(obj.name)
                    self.stdout.write(f'AssetType id={obj.id} name: (cyrillic) -> "{safe_str(new_name)}"')
                    if not dry_run:
                        obj.name = new_name
                    changed = True
                if obj.description and contains_cyrillic(obj.description):
                    new_desc = translate_to_english(obj.description)
                    self.stdout.write(f'AssetType id={obj.id} description: (cyrillic) -> "{safe_str(new_desc, 60)}..."')
                    if not dry_run:
                        obj.description = new_desc
                    changed = True
                if changed:
                    if not dry_run:
                        obj.save()
                    updated_counts['AssetType'] += 1

            # --- CriticalityLevel: name + Basic Information CIA descriptions + translations ---
            for obj in CriticalityLevel.objects.all():
                name_changed = False
                level_changed = False
                if contains_cyrillic(obj.name):
                    new_name = translate_to_english(obj.name)
                    self.stdout.write(f'CriticalityLevel id={obj.id} name: (cyrillic) -> "{safe_str(new_name)}"')
                    if not dry_run:
                        obj.name = new_name
                    name_changed = True
                    level_changed = True
                for field in ('description_confid', 'description_integ', 'description_avail'):
                    val = getattr(obj, field, None)
                    if val and contains_cyrillic(val):
                        new_val = translate_to_english(val)
                        self.stdout.write(f'CriticalityLevel id={obj.id} {field}: (cyrillic) -> "{safe_str(new_val, 50)}..."')
                        if not dry_run:
                            setattr(obj, field, new_val)
                        level_changed = True
                for trans in obj.translations.all():
                    for field in ('description_confid', 'description_avail', 'description_integ'):
                        val = getattr(trans, field, None)
                        if val and contains_cyrillic(val):
                            new_val = translate_to_english(val)
                            self.stdout.write(f'CriticalityLevel id={obj.id} translation {trans.country_id} {field}: (cyrillic) -> "{safe_str(new_val, 50)}..."')
                            if not dry_run:
                                setattr(trans, field, new_val)
                                trans.save()
                            level_changed = True
                if level_changed:
                    if not dry_run:
                        obj.save()
                    updated_counts['CriticalityLevel'] += 1

            if dry_run:
                transaction.set_rollback(True)

        total = sum(updated_counts.values())
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No default fields contained Cyrillic; nothing to translate.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Updated: AssetGroup={updated_counts["AssetGroup"]}, '
                f'AssetType={updated_counts["AssetType"]}, '
                f'CriticalityLevel={updated_counts["CriticalityLevel"]}'
                + (' (dry run, no changes saved)' if dry_run else '')
            ))
