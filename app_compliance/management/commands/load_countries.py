"""
Management команда для завантаження країн для Local Compliance
"""
from django.core.management.base import BaseCommand
from app_conf.models import Country


class Command(BaseCommand):
    help = 'Load countries for Local Compliance'
    
    def handle(self, *args, **options):
        """Завантажити базові країни"""
        
        countries_data = [
            {
                'code': 'UA',
                'name': 'Ukraine',
                'name_local': 'Україна',
                'flag_emoji': '🇺🇦',
                'color': '#0057B7',
                'display_order': 1
            },
            {
                'code': 'PL',
                'name': 'Poland',
                'name_local': 'Polska',
                'flag_emoji': '🇵🇱',
                'color': '#DC143C',
                'display_order': 2
            },
            {
                'code': 'US',
                'name': 'United States',
                'name_local': 'United States',
                'flag_emoji': '🇺🇸',
                'color': '#B22234',
                'display_order': 3
            },
            {
                'code': 'GB',
                'name': 'United Kingdom',
                'name_local': 'United Kingdom',
                'flag_emoji': '🇬🇧',
                'color': '#012169',
                'display_order': 4
            },
            {
                'code': 'DE',
                'name': 'Germany',
                'name_local': 'Deutschland',
                'flag_emoji': '🇩🇪',
                'color': '#000000',
                'display_order': 5
            },
            {
                'code': 'FR',
                'name': 'France',
                'name_local': 'France',
                'flag_emoji': '🇫🇷',
                'color': '#0055A4',
                'display_order': 6
            },
            {
                'code': 'IT',
                'name': 'Italy',
                'name_local': 'Italia',
                'flag_emoji': '🇮🇹',
                'color': '#009246',
                'display_order': 7
            },
            {
                'code': 'ES',
                'name': 'Spain',
                'name_local': 'España',
                'flag_emoji': '🇪🇸',
                'color': '#AA151B',
                'display_order': 8
            },
            {
                'code': 'EU',
                'name': 'European Union',
                'name_local': 'European Union',
                'flag_emoji': '🇪🇺',
                'color': '#003399',
                'display_order': 10
            },
            {
                'code': 'CA',
                'name': 'Canada',
                'name_local': 'Canada',
                'flag_emoji': '🇨🇦',
                'color': '#FF0000',
                'display_order': 11
            },
            {
                'code': 'AU',
                'name': 'Australia',
                'name_local': 'Australia',
                'flag_emoji': '🇦🇺',
                'color': '#00008B',
                'display_order': 12
            },
            {
                'code': 'JP',
                'name': 'Japan',
                'name_local': '日本',
                'flag_emoji': '🇯🇵',
                'color': '#BC002D',
                'display_order': 13
            },
            {
                'code': 'CN',
                'name': 'China',
                'name_local': '中国',
                'flag_emoji': '🇨🇳',
                'color': '#DE2910',
                'display_order': 14
            },
            {
                'code': 'IN',
                'name': 'India',
                'name_local': 'भारत',
                'flag_emoji': '🇮🇳',
                'color': '#FF9933',
                'display_order': 15
            },
            {
                'code': 'BR',
                'name': 'Brazil',
                'name_local': 'Brasil',
                'flag_emoji': '🇧🇷',
                'color': '#009739',
                'display_order': 16
            },
            {
                'code': 'SG',
                'name': 'Singapore',
                'name_local': 'Singapore',
                'flag_emoji': '🇸🇬',
                'color': '#EF3340',
                'display_order': 17
            },
            {
                'code': 'CH',
                'name': 'Switzerland',
                'name_local': 'Schweiz',
                'flag_emoji': '🇨🇭',
                'color': '#FF0000',
                'display_order': 18
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for data in countries_data:
            country, created = Country.objects.update_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'name_local': data['name_local'],
                    'flag_emoji': data['flag_emoji'],
                    'color': data['color'],
                    'display_order': data['display_order'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created: {country.flag_emoji} {country.name} ({country.code})")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"↻ Updated: {country.flag_emoji} {country.name} ({country.code})")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Completed! Created: {created_count}, Updated: {updated_count}")
        )

