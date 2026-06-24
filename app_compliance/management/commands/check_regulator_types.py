"""
Management команда для перевірки типів регуляторів
"""
from django.core.management.base import BaseCommand
from app_compliance.models import RegulatorType


class Command(BaseCommand):
    help = 'Check and display regulator types configuration'
    
    def handle(self, *args, **options):
        """Перевірити та показати налаштування типів регуляторів"""
        
        regulator_types = RegulatorType.objects.all().order_by('display_order', 'name')
        
        if not regulator_types.exists():
            self.stdout.write(
                self.style.ERROR("✗ No regulator types found in database!")
            )
            self.stdout.write("Run: python manage.py load_regulator_types")
            return
        
        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Found {regulator_types.count()} regulator types:\n")
        )
        
        # Table header
        self.stdout.write(
            f"{'Order':<6} {'Icon':<20} {'Code':<20} {'Name':<30} {'Local Name':<30} {'Color':<10} {'Active':<7} {'Companies':<10} {'Regulators':<10}"
        )
        self.stdout.write("-" * 145)
        
        for reg_type in regulator_types:
            regulators_count = reg_type.regulators.count()
            companies_count = reg_type.companies.count()
            active_status = "✓ Yes" if reg_type.is_active else "✗ No"
            
            # Icon display
            icon_display = f"<i {reg_type.icon}>" if reg_type.icon else "-"
            
            self.stdout.write(
                f"{reg_type.display_order:<6} "
                f"{icon_display:<20} "
                f"{reg_type.code:<20} "
                f"{reg_type.name[:29]:<30} "
                f"{reg_type.name_local[:29] if reg_type.name_local else '-':<30} "
                f"{reg_type.color:<10} "
                f"{active_status:<7} "
                f"{companies_count:<10} "
                f"{regulators_count:<10}"
            )
        
        # Summary
        self.stdout.write("\n" + "=" * 145)
        active_count = regulator_types.filter(is_active=True).count()
        with_companies = regulator_types.filter(companies__isnull=False).distinct().count()
        with_regulators = regulator_types.filter(regulators__isnull=False).distinct().count()
        
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   Total types: {regulator_types.count()}")
        self.stdout.write(f"   Active: {active_count}")
        self.stdout.write(f"   With companies: {with_companies}")
        self.stdout.write(f"   With regulators: {with_regulators}")
        
        # Check for issues
        issues = []
        
        if regulator_types.filter(icon='').exists():
            missing_icons = regulator_types.filter(icon='').count()
            issues.append(f"⚠️  {missing_icons} types without icon")
        
        if regulator_types.filter(name_local='').exists():
            missing_local = regulator_types.filter(name_local='').count()
            issues.append(f"⚠️  {missing_local} types without local name")
        
        if issues:
            self.stdout.write("\n⚠️  Issues found:")
            for issue in issues:
                self.stdout.write(f"   {issue}")
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ All regulator types are properly configured!")
            )

