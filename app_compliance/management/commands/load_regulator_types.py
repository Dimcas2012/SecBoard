"""
Management команда для завантаження типів регуляторів для Local Compliance
"""
from django.core.management.base import BaseCommand
from app_compliance.models import RegulatorType


class Command(BaseCommand):
    help = 'Load regulator types for Local Compliance'
    
    def handle(self, *args, **options):
        """Завантажити базові типи регуляторів"""
        
        regulator_types_data = [
            {
                'code': 'financial',
                'name': 'Financial Regulator',
                'name_local': 'Фінансовий регулятор',
                'icon': 'fa-coins',
                'color': '#28a745',
                'display_order': 1
            },
            {
                'code': 'banking',
                'name': 'Banking Regulator',
                'name_local': 'Банківський регулятор',
                'icon': 'fa-university',
                'color': '#007bff',
                'display_order': 2
            },
            {
                'code': 'securities',
                'name': 'Securities Regulator',
                'name_local': 'Регулятор цінних паперів',
                'icon': 'fa-chart-line',
                'color': '#17a2b8',
                'display_order': 3
            },
            {
                'code': 'insurance',
                'name': 'Insurance Regulator',
                'name_local': 'Регулятор страхування',
                'icon': 'fa-shield-alt',
                'color': '#6610f2',
                'display_order': 4
            },
            {
                'code': 'government',
                'name': 'Government Authority',
                'name_local': 'Державний орган',
                'icon': 'fa-landmark',
                'color': '#6c757d',
                'display_order': 5
            },
            {
                'code': 'data_protection',
                'name': 'Data Protection Authority',
                'name_local': 'Орган захисту даних',
                'icon': 'fa-lock',
                'color': '#fd7e14',
                'display_order': 6
            },
            {
                'code': 'tax',
                'name': 'Tax Authority',
                'name_local': 'Податковий орган',
                'icon': 'fa-file-invoice-dollar',
                'color': '#20c997',
                'display_order': 7
            },
            {
                'code': 'cyber_security',
                'name': 'Cyber Security Authority',
                'name_local': 'Орган кібербезпеки',
                'icon': 'fa-shield-virus',
                'color': '#e83e8c',
                'display_order': 8
            },
            {
                'code': 'telecommunications',
                'name': 'Telecommunications Regulator',
                'name_local': 'Регулятор телекомунікацій',
                'icon': 'fa-broadcast-tower',
                'color': '#6f42c1',
                'display_order': 9
            },
            {
                'code': 'energy',
                'name': 'Energy Regulator',
                'name_local': 'Регулятор енергетики',
                'icon': 'fa-bolt',
                'color': '#ffc107',
                'display_order': 10
            },
            {
                'code': 'healthcare',
                'name': 'Healthcare Authority',
                'name_local': 'Орган охорони здоров\'я',
                'icon': 'fa-hospital',
                'color': '#dc3545',
                'display_order': 11
            },
            {
                'code': 'other',
                'name': 'Other',
                'name_local': 'Інше',
                'icon': 'fa-ellipsis-h',
                'color': '#adb5bd',
                'display_order': 99
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for data in regulator_types_data:
            regulator_type, created = RegulatorType.objects.update_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'name_local': data['name_local'],
                    'icon': data['icon'],
                    'color': data['color'],
                    'display_order': data['display_order'],
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

