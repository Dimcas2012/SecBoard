"""
Автоматичне виправлення кодування для LocalComplianceRegulator
"""
from django.core.management.base import BaseCommand
from app_compliance.models import LocalComplianceRegulator


class Command(BaseCommand):
    help = 'Automatically fix encoding issues in LocalComplianceRegulator using cp1251→utf8'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without actually fixing',
        )
    
    def handle(self, *args, **options):
        """Виправити кодування автоматично"""
        
        regulators = LocalComplianceRegulator.objects.all()
        
        self.stdout.write(f"\n📋 Processing {regulators.count()} regulators...\n")
        
        fixed_count = 0
        error_count = 0
        skip_count = 0
        
        for reg in regulators:
            # Перевірити name_local
            if reg.name_local:
                # Шукати характерні символи проблемного кодування
                suspicious_chars = ['Р', 'Рѕ', 'Р°', 'Р†', 'Сѓ', 'С–', 'С,', 'С"', 'Т™', 'Т›']
                
                if any(char in reg.name_local for char in suspicious_chars):
                    try:
                        # Спробувати cp1251→utf8 конвертацію
                        fixed_text = reg.name_local.encode('cp1251', errors='ignore').decode('utf-8')
                        
                        if options['dry_run']:
                            self.stdout.write(
                                self.style.WARNING(f"[DRY-RUN] Would fix {reg.id}: {reg.name}")
                            )
                            self.stdout.write(f"   Old: {reg.name_local}")
                            self.stdout.write(f"   New: {fixed_text}\n")
                        else:
                            # Зберегти виправлений текст
                            reg.name_local = fixed_text
                            reg.save()
                            
                            self.stdout.write(
                                self.style.SUCCESS(f"✓ Fixed {reg.id}: {reg.name}")
                            )
                            self.stdout.write(f"   {fixed_text}\n")
                        
                        fixed_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(f"✗ Error fixing {reg.id}: {reg.name}")
                        )
                        self.stdout.write(f"   {str(e)}\n")
                else:
                    skip_count += 1
            else:
                skip_count += 1
        
        # Summary
        self.stdout.write("=" * 80)
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f"\n[DRY-RUN] Would fix: {fixed_count} regulators")
            )
            self.stdout.write("Run without --dry-run to apply changes")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Fixed: {fixed_count} regulators")
            )
        
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f"✗ Errors: {error_count}")
            )
        
        if skip_count > 0:
            self.stdout.write(f"⊘ Skipped (no issues): {skip_count}")
        
        if not options['dry_run'] and fixed_count > 0:
            self.stdout.write(
                self.style.SUCCESS("\n✅ Encoding fixed! Refresh admin page to see changes.")
            )

