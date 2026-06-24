import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from app_cif.models import CIFProtectionPlanTemplate


class Command(BaseCommand):
    help = "Import CIF protection plan templates from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument("--path", type=str, required=True, help="Path to JSON template file")

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CommandError(f"Cannot parse JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise CommandError("JSON root must be an object keyed by category (I/II/III/IV).")

        updated = 0
        created = 0
        for category, structure in payload.items():
            structure_text = json.dumps(structure, ensure_ascii=False, indent=2)
            obj, was_created = CIFProtectionPlanTemplate.objects.update_or_create(
                category=category,
                defaults={
                    "name": f"Category {category} base template",
                    "structure": structure_text,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
            self.stdout.write(self.style.SUCCESS(f"Template {obj.category} imported"))

        self.stdout.write(self.style.SUCCESS(f"Done. created={created}, updated={updated}"))
