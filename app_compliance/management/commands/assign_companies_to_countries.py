"""
Management команда для автоматичного призначення компаній до країн
"""
from django.core.management.base import BaseCommand
from app_conf.models import Country
from app_conf.models import Company


class Command(BaseCommand):
    help = 'Assign companies to countries automatically'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--country',
            type=str,
            help='Country code (e.g., UA, PL)',
        )
        parser.add_argument(
            '--all-countries',
            action='store_true',
            help='Assign all companies to all countries',
        )
        parser.add_argument(
            '--company',
            type=str,
            help='Company name or ID',
        )
    
    def handle(self, *args, **options):
        """Призначити компанії до країн"""
        
        country_code = options.get('country')
        all_countries = options.get('all_countries')
        company_name = options.get('company')
        
        # Get companies
        if company_name:
            companies = Company.objects.filter(name__icontains=company_name)
            if not companies.exists():
                self.stdout.write(
                    self.style.ERROR(f"✗ No companies found matching '{company_name}'")
                )
                return
        else:
            companies = Company.objects.all()
        
        self.stdout.write(
            self.style.SUCCESS(f"Found {companies.count()} companies")
        )
        
        # Get countries
        if all_countries:
            countries = Country.objects.filter(is_active=True)
        elif country_code:
            try:
                countries = [Country.objects.get(code=country_code.upper())]
            except Country.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"✗ Country with code '{country_code}' not found")
                )
                return
        else:
            self.stdout.write(
                self.style.ERROR("✗ Please specify --country=CODE or --all-countries")
            )
            return
        
        # Assign companies to countries
        total_assigned = 0
        
        for country in countries:
            # Add companies to country
            existing_count = country.companies.count()
            country.companies.add(*companies)
            new_count = country.companies.count()
            added = new_count - existing_count
            
            total_assigned += added
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {country.flag_emoji} {country.name} ({country.code}): "
                    f"added {added} companies (total: {new_count})"
                )
            )
        
        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Completed! Assigned {total_assigned} company-country relationships"
            )
        )
        
        # Show statistics
        self.stdout.write("\n📊 Statistics:")
        for country in countries:
            companies_list = ', '.join([
                c.name for c in country.companies.all()[:3]
            ])
            if country.companies.count() > 3:
                companies_list += f" (+{country.companies.count() - 3} more)"
            
            self.stdout.write(
                f"   {country.flag_emoji} {country.name}: {companies_list}"
            )

