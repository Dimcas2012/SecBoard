"""
Management команда для завантаження типів компаній
"""
from django.core.management.base import BaseCommand
from app_compliance.models import CompanyType


class Command(BaseCommand):
    help = 'Load company types for Local Compliance'
    
    def handle(self, *args, **options):
        """Завантажити базові типи компаній"""
        
        company_types_data = [
            {
                'code': 'bank',
                'name': 'Bank',
                'name_local': 'Банк',
                'icon': 'fa-university',
                'color': '#007bff',
                'display_order': 1,
                'description': 'Banking institution',
                'regulatory_requirements': 'Subject to banking regulations, capital requirements, AML/KYC compliance'
            },
            {
                'code': 'credit_bureau',
                'name': 'Credit Bureau',
                'name_local': 'Кредитне бюро',
                'icon': 'fa-clipboard-check',
                'color': '#28a745',
                'display_order': 2,
                'description': 'Credit reporting agency',
                'regulatory_requirements': 'Data protection, credit reporting regulations'
            },
            {
                'code': 'payment_system',
                'name': 'Payment System',
                'name_local': 'Платіжна система',
                'icon': 'fa-credit-card',
                'color': '#17a2b8',
                'display_order': 3,
                'description': 'Payment processing system operator',
                'regulatory_requirements': 'PCI DSS, payment system regulations, cyber security'
            },
            {
                'code': 'microfinance',
                'name': 'Microfinance Organization',
                'name_local': 'Мікрофінансова організація',
                'icon': 'fa-hand-holding-usd',
                'color': '#ffc107',
                'display_order': 4,
                'description': 'Microfinance institution',
                'regulatory_requirements': 'Microfinance regulations, consumer protection'
            },
            {
                'code': 'insurance',
                'name': 'Insurance Company',
                'name_local': 'Страхова компанія',
                'icon': 'fa-shield-alt',
                'color': '#6610f2',
                'display_order': 5,
                'description': 'Insurance provider',
                'regulatory_requirements': 'Insurance regulations, solvency requirements'
            },
            {
                'code': 'investment_fund',
                'name': 'Investment Fund',
                'name_local': 'Інвестиційний фонд',
                'icon': 'fa-chart-line',
                'color': '#20c997',
                'display_order': 6,
                'description': 'Investment fund manager',
                'regulatory_requirements': 'Securities regulations, investor protection'
            },
            {
                'code': 'broker_dealer',
                'name': 'Broker-Dealer',
                'name_local': 'Брокер-дилер',
                'icon': 'fa-briefcase',
                'color': '#fd7e14',
                'display_order': 7,
                'description': 'Securities broker or dealer',
                'regulatory_requirements': 'Securities regulations, trading compliance'
            },
            {
                'code': 'state_enterprise',
                'name': 'State Enterprise',
                'name_local': 'Державне підприємство',
                'icon': 'fa-landmark',
                'color': '#6c757d',
                'display_order': 8,
                'description': 'Government-owned enterprise',
                'regulatory_requirements': 'Public sector compliance, transparency requirements'
            },
            {
                'code': 'fintech',
                'name': 'FinTech Company',
                'name_local': 'FinTech компанія',
                'icon': 'fa-mobile-alt',
                'color': '#e83e8c',
                'display_order': 9,
                'description': 'Financial technology company',
                'regulatory_requirements': 'Varies based on services, e-money regulations'
            },
            {
                'code': 'leasing',
                'name': 'Leasing Company',
                'name_local': 'Лізингова компанія',
                'icon': 'fa-file-contract',
                'color': '#6f42c1',
                'display_order': 10,
                'description': 'Equipment or property leasing',
                'regulatory_requirements': 'Leasing regulations, consumer protection'
            },
            {
                'code': 'exchange',
                'name': 'Stock Exchange',
                'name_local': 'Фондова біржа',
                'icon': 'fa-exchange-alt',
                'color': '#dc3545',
                'display_order': 11,
                'description': 'Securities exchange operator',
                'regulatory_requirements': 'Exchange regulations, market oversight'
            },
            {
                'code': 'credit_union',
                'name': 'Credit Union',
                'name_local': 'Кредитна спілка',
                'icon': 'fa-users',
                'color': '#17a2b8',
                'display_order': 12,
                'description': 'Member-owned financial cooperative',
                'regulatory_requirements': 'Credit union regulations, member protection'
            },
            {
                'code': 'pension_fund',
                'name': 'Pension Fund',
                'name_local': 'Пенсійний фонд',
                'icon': 'fa-piggy-bank',
                'color': '#28a745',
                'display_order': 13,
                'description': 'Pension fund manager',
                'regulatory_requirements': 'Pension regulations, fiduciary duties'
            },
            {
                'code': 'other',
                'name': 'Other Financial Institution',
                'name_local': 'Інша фінансова установа',
                'icon': 'fa-building',
                'color': '#adb5bd',
                'display_order': 99,
                'description': 'Other type of financial institution',
                'regulatory_requirements': 'Varies based on activities'
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for data in company_types_data:
            company_type, created = CompanyType.objects.update_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'name_local': data['name_local'],
                    'icon': data['icon'],
                    'color': data['color'],
                    'display_order': data['display_order'],
                    'description': data['description'],
                    'regulatory_requirements': data['regulatory_requirements'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                icon_display = f"({data['icon']})" if data['icon'] else ""
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created: {data['name']} {icon_display}")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"↻ Updated: {data['name']}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Completed! Created: {created_count}, Updated: {updated_count}")
        )

