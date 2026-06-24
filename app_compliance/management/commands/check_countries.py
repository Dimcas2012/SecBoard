"""
Management команда для перевірки країн та їх відображення
"""
from django.core.management.base import BaseCommand
from app_conf.models import Country


class Command(BaseCommand):
    help = 'Check and display countries configuration'
    
    def handle(self, *args, **options):
        """Перевірити та показати налаштування країн"""
        
        countries = Country.objects.all().order_by('display_order', 'name')
        
        if not countries.exists():
            self.stdout.write(
                self.style.ERROR("✗ No countries found in database!")
            )
            self.stdout.write("Run: python manage.py load_countries")
            return
        
        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Found {countries.count()} countries:\n")
        )
        
        # Table header
        self.stdout.write(
            f"{'Order':<6} {'Flag':<6} {'Code':<5} {'Name':<25} {'Local Name':<25} {'Color':<10} {'Active':<7} {'Regulators':<10}"
        )
        self.stdout.write("-" * 120)
        
        for country in countries:
            regulators_count = country.regulators.count()
            active_status = "✓ Yes" if country.is_active else "✗ No"
            
            # Emoji display
            flag_display = country.flag_emoji if country.flag_emoji else "-"
            
            self.stdout.write(
                f"{country.display_order:<6} "
                f"{flag_display:<6} "
                f"{country.code:<5} "
                f"{country.name[:24]:<25} "
                f"{country.name_local[:24] if country.name_local else '-':<25} "
                f"{country.color:<10} "
                f"{active_status:<7} "
                f"{regulators_count:<10}"
            )
        
        # Summary
        self.stdout.write("\n" + "=" * 120)
        active_count = countries.filter(is_active=True).count()
        with_flags = countries.exclude(flag_emoji='').count()
        with_regulators = countries.filter(regulators__isnull=False).distinct().count()
        
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   Total countries: {countries.count()}")
        self.stdout.write(f"   Active: {active_count}")
        self.stdout.write(f"   With flags: {with_flags}")
        self.stdout.write(f"   With regulators: {with_regulators}")
        
        # Check for issues
        issues = []
        
        if countries.filter(flag_emoji='').exists():
            missing_flags = countries.filter(flag_emoji='').count()
            issues.append(f"⚠️  {missing_flags} countries without flag emoji")
        
        if countries.filter(name_local='').exists():
            missing_local = countries.filter(name_local='').count()
            issues.append(f"⚠️  {missing_local} countries without local name")
        
        if issues:
            self.stdout.write("\n⚠️  Issues found:")
            for issue in issues:
                self.stdout.write(f"   {issue}")
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ All countries are properly configured!")
            )

