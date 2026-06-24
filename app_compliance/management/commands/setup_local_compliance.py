"""
Management команда для повного налаштування Local Compliance
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Complete setup for Local Compliance (Countries and Regulator Types)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-countries',
            action='store_true',
            help='Skip loading countries',
        )
        parser.add_argument(
            '--skip-regulators',
            action='store_true',
            help='Skip loading regulator types',
        )
        parser.add_argument(
            '--skip-company-types',
            action='store_true',
            help='Skip loading company types',
        )
    
    def handle(self, *args, **options):
        """Повне налаштування Local Compliance"""
        
        self.stdout.write(
            self.style.SUCCESS("\n" + "="*80)
        )
        self.stdout.write(
            self.style.SUCCESS("🚀 LOCAL COMPLIANCE SETUP")
        )
        self.stdout.write(
            self.style.SUCCESS("="*80 + "\n")
        )
        
        # 1. Завантажити країни
        if not options['skip_countries']:
            self.stdout.write(
                self.style.WARNING("\n📍 Step 1: Loading Countries...")
            )
            self.stdout.write("-" * 80)
            call_command('load_countries')
            
            self.stdout.write(
                self.style.WARNING("\n✓ Checking countries...")
            )
            call_command('check_countries')
        else:
            self.stdout.write(
                self.style.WARNING("\n⊘ Skipping countries (--skip-countries)")
            )
        
        # 2. Завантажити типи регуляторів
        if not options['skip_regulators']:
            self.stdout.write(
                self.style.WARNING("\n📋 Step 2: Loading Regulator Types...")
            )
            self.stdout.write("-" * 80)
            call_command('load_regulator_types')
            
            self.stdout.write(
                self.style.WARNING("\n✓ Checking regulator types...")
            )
            call_command('check_regulator_types')
        else:
            self.stdout.write(
                self.style.WARNING("\n⊘ Skipping regulator types (--skip-regulators)")
            )
        
        # 3. Завантажити типи компаній
        if not options['skip_company_types']:
            self.stdout.write(
                self.style.WARNING("\n🏢 Step 3: Loading Company Types...")
            )
            self.stdout.write("-" * 80)
            call_command('load_company_types')
            
            self.stdout.write(
                self.style.WARNING("\n✓ Checking company types...")
            )
            call_command('check_company_types')
        else:
            self.stdout.write(
                self.style.WARNING("\n⊘ Skipping company types (--skip-company-types)")
            )
        
        # 4. Оновити країни без прапорів
        self.stdout.write(
            self.style.WARNING("\n🔄 Step 4: Updating missing data...")
        )
        self.stdout.write("-" * 80)
        call_command('update_missing_countries')
        
        # 4. Фінальна перевірка
        self.stdout.write(
            self.style.SUCCESS("\n" + "="*80)
        )
        self.stdout.write(
            self.style.SUCCESS("✅ SETUP COMPLETED!")
        )
        self.stdout.write(
            self.style.SUCCESS("="*80 + "\n")
        )
        
        self.stdout.write("📝 Next steps:")
        self.stdout.write("   1. Go to Admin → Compliance Management → Company Types")
        self.stdout.write("   2. Assign companies to company types")
        self.stdout.write("   3. Go to Admin → Compliance Management → Countries")
        self.stdout.write("   4. Assign companies to countries")
        self.stdout.write("   5. Go to Admin → Compliance Management → Regulator Types")
        self.stdout.write("   6. Assign companies to regulator types")
        self.stdout.write("   7. Create Local Compliance Regulators with proper Country and Type")
        
        self.stdout.write(
            self.style.SUCCESS("\n✓ All systems ready!")
        )

