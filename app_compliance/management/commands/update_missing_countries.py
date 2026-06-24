"""
Management команда для оновлення країн без прапорів
"""
from django.core.management.base import BaseCommand
from app_conf.models import Country


class Command(BaseCommand):
    help = 'Update countries that are missing flags and local names'
    
    def handle(self, *args, **options):
        """Оновити країни без прапорів"""
        
        # Дані для країн що потребують оновлення
        country_updates = {
            'KZ': {
                'name': 'Kazakhstan',
                'name_local': 'Қазақстан',
                'flag_emoji': '🇰🇿',
                'color': '#00AFCA',
                'display_order': 19
            },
            'LT': {
                'name': 'Lithuania',
                'name_local': 'Lietuva',
                'flag_emoji': '🇱🇹',
                'color': '#FDB913',
                'display_order': 20
            },
        }
        
        updated_count = 0
        
        for code, data in country_updates.items():
            try:
                country = Country.objects.get(code=code)
                
                # Оновлюємо тільки якщо немає прапора
                if not country.flag_emoji:
                    country.name = data['name']
                    country.name_local = data['name_local']
                    country.flag_emoji = data['flag_emoji']
                    country.color = data['color']
                    country.display_order = data['display_order']
                    country.save()
                    
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Updated: {country.flag_emoji} {country.name} ({country.code})"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⊘ Skipped: {country.flag_emoji} {country.name} ({country.code}) - already has flag"
                        )
                    )
                    
            except Country.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"✗ Country {code} not found")
                )
        
        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Updated {updated_count} countries!")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✓ All countries already have flags!")
            )

