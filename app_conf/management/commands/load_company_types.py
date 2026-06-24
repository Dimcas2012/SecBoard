"""
Management command to load initial Company Type data
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from app_conf.models import CompanyType


class Command(BaseCommand):
    help = 'Load initial Company Type data into the database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Loading Company Types...'))
        
        company_types_data = [
            {
                'name': 'Bank',
                'name_local': 'Банк',
                'code': 'bank',
                'color': '#1e3a8a',  # Dark blue
                'display_order': 1,
                'description': 'Financial institution that accepts deposits and provides loans',
            },
            {
                'name': 'Payment System',
                'name_local': 'Платіжна система',
                'code': 'payment_system',
                'color': '#7c3aed',  # Purple
                'display_order': 2,
                'description': 'System for processing payment transactions',
            },
            {
                'name': 'Credit Bureau',
                'name_local': 'Кредитне бюро',
                'code': 'credit_bureau',
                'color': '#0891b2',  # Cyan
                'display_order': 3,
                'description': 'Agency that collects and maintains credit information',
            },
            {
                'name': 'Insurance Company',
                'name_local': 'Страхова компанія',
                'code': 'insurance',
                'color': '#059669',  # Green
                'display_order': 4,
                'description': 'Company providing insurance services',
            },
            {
                'name': 'Investment Fund',
                'name_local': 'Інвестиційний фонд',
                'code': 'investment_fund',
                'color': '#dc2626',  # Red
                'display_order': 5,
                'description': 'Fund that pools money from investors',
            },
            {
                'name': 'Brokerage Firm',
                'name_local': 'Брокерська компанія',
                'code': 'brokerage',
                'color': '#ea580c',  # Orange
                'display_order': 6,
                'description': 'Company facilitating buying and selling of securities',
            },
            {
                'name': 'Leasing Company',
                'name_local': 'Лізингова компанія',
                'code': 'leasing',
                'color': '#4f46e5',  # Indigo
                'display_order': 7,
                'description': 'Company providing leasing services',
            },
            {
                'name': 'Microfinance Organization',
                'name_local': 'Мікрофінансова організація',
                'code': 'microfinance',
                'color': '#0d9488',  # Teal
                'display_order': 8,
                'description': 'Organization providing small loans and financial services',
            },
            {
                'name': 'Credit Union',
                'name_local': 'Кредитна спілка',
                'code': 'credit_union',
                'color': '#2563eb',  # Blue
                'display_order': 9,
                'description': 'Member-owned financial cooperative',
            },
            {
                'name': 'Fintech Company',
                'name_local': 'Фінтех компанія',
                'code': 'fintech',
                'color': '#8b5cf6',  # Violet
                'display_order': 10,
                'description': 'Technology company in financial services',
            },
            {
                'name': 'Asset Management',
                'name_local': 'Управління активами',
                'code': 'asset_management',
                'color': '#be123c',  # Rose
                'display_order': 11,
                'description': 'Company managing investments on behalf of clients',
            },
            {
                'name': 'Collection Agency',
                'name_local': 'Колекторське агентство',
                'code': 'collection',
                'color': '#b91c1c',  # Dark red
                'display_order': 12,
                'description': 'Agency collecting debts on behalf of creditors',
            },
            {
                'name': 'Currency Exchange',
                'name_local': 'Обмін валют',
                'code': 'currency_exchange',
                'color': '#65a30d',  # Lime
                'display_order': 13,
                'description': 'Service for exchanging currencies',
            },
            {
                'name': 'Financial Regulator',
                'name_local': 'Фінансовий регулятор',
                'code': 'regulator',
                'color': '#334155',  # Slate
                'display_order': 14,
                'description': 'Government agency overseeing financial institutions',
            },
            {
                'name': 'Rating Agency',
                'name_local': 'Рейтингове агентство',
                'code': 'rating_agency',
                'color': '#78716c',  # Stone
                'display_order': 15,
                'description': 'Agency assessing creditworthiness',
            },
            {
                'name': 'Stock Exchange',
                'name_local': 'Фондова біржа',
                'code': 'stock_exchange',
                'color': '#1f2937',  # Gray
                'display_order': 16,
                'description': 'Marketplace for trading securities',
            },
            {
                'name': 'Pawn Shop',
                'name_local': 'Ломбард',
                'code': 'pawn_shop',
                'color': '#b45309',  # Amber
                'display_order': 17,
                'description': 'Business offering secured loans',
            },
            {
                'name': 'Financial Advisor',
                'name_local': 'Фінансовий консультант',
                'code': 'financial_advisor',
                'color': '#0369a1',  # Sky
                'display_order': 18,
                'description': 'Professional providing financial advice',
            },
            {
                'name': 'Pension Fund',
                'name_local': 'Пенсійний фонд',
                'code': 'pension_fund',
                'color': '#047857',  # Emerald
                'display_order': 19,
                'description': 'Fund for retirement savings',
            },
            {
                'name': 'Other Financial Institution',
                'name_local': 'Інша фінансова установа',
                'code': 'other',
                'color': '#6b7280',  # Neutral gray
                'display_order': 99,
                'description': 'Other types of financial institutions',
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
                    'color': data['color'],
                    'display_order': data['display_order'],
                    'description': data['description'],
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {company_type.name} ({company_type.name_local})')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {company_type.name} ({company_type.name_local})')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Successfully loaded {created_count + updated_count} Company Types'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'   Created: {created_count} | Updated: {updated_count}'
            )
        )

