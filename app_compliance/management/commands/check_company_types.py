"""
Management команда для перевірки типів компаній
"""
from django.core.management.base import BaseCommand
from app_compliance.models import CompanyType


class Command(BaseCommand):
    help = 'Check and display company types configuration'
    
    def handle(self, *args, **options):
        """Перевірити та показати налаштування типів компаній"""
        
        company_types = CompanyType.objects.all().order_by('display_order', 'name')
        
        if not company_types.exists():
            self.stdout.write(
                self.style.ERROR("✗ No company types found in database!")
            )
            self.stdout.write("Run: python manage.py load_company_types")
            return
        
        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Found {company_types.count()} company types:\n")
        )
        
        # Table header
        self.stdout.write(
            f"{'Order':<6} {'Icon':<20} {'Code':<20} {'Name':<35} {'Local Name':<35} {'Color':<10} {'Active':<7} {'Companies':<10}"
        )
        self.stdout.write("-" * 155)
        
        for comp_type in company_types:
            companies_count = comp_type.companies.count()
            active_status = "✓ Yes" if comp_type.is_active else "✗ No"
            
            # Icon display
            icon_display = f"<i {comp_type.icon}>" if comp_type.icon else "-"
            
            self.stdout.write(
                f"{comp_type.display_order:<6} "
                f"{icon_display:<20} "
                f"{comp_type.code:<20} "
                f"{comp_type.name[:34]:<35} "
                f"{comp_type.name_local[:34] if comp_type.name_local else '-':<35} "
                f"{comp_type.color:<10} "
                f"{active_status:<7} "
                f"{companies_count:<10}"
            )
        
        # Summary
        self.stdout.write("\n" + "=" * 155)
        active_count = company_types.filter(is_active=True).count()
        with_companies = company_types.filter(companies__isnull=False).distinct().count()
        
        self.stdout.write(f"\n📊 Summary:")
        self.stdout.write(f"   Total types: {company_types.count()}")
        self.stdout.write(f"   Active: {active_count}")
        self.stdout.write(f"   With companies: {with_companies}")
        
        # Check for issues
        issues = []
        
        if company_types.filter(icon='').exists():
            missing_icons = company_types.filter(icon='').count()
            issues.append(f"⚠️  {missing_icons} types without icon")
        
        if company_types.filter(name_local='').exists():
            missing_local = company_types.filter(name_local='').count()
            issues.append(f"⚠️  {missing_local} types without local name")
        
        if issues:
            self.stdout.write("\n⚠️  Issues found:")
            for issue in issues:
                self.stdout.write(f"   {issue}")
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ All company types are properly configured!")
            )

