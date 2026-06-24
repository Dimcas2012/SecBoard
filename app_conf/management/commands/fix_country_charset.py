"""
Management command to fix Country table charset for emoji support
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fix Country table charset to support emoji flags'
    
    def handle(self, *args, **options):
        """Fix charset for Country table"""
        
        with connection.cursor() as cursor:
            # Fix table charset to utf8mb4
            self.stdout.write("Fixing Country table charset...")
            
            cursor.execute("""
                ALTER TABLE app_conf_country 
                CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
            
            cursor.execute("""
                ALTER TABLE app_conf_country 
                MODIFY COLUMN flag_emoji VARCHAR(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
            
            cursor.execute("""
                ALTER TABLE app_conf_country 
                MODIFY COLUMN name VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
            
            cursor.execute("""
                ALTER TABLE app_conf_country 
                MODIFY COLUMN name_local VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """)
            
            self.stdout.write(self.style.SUCCESS("Charset fixed successfully!"))
            
            # Now reload flags
            from app_conf.models import Country
            
            country_data = {
                'UA': {'flag': '🇺🇦', 'name_local': 'Україна'},
                'PL': {'flag': '🇵🇱', 'name_local': 'Polska'},
                'US': {'flag': '🇺🇸', 'name_local': 'United States'},
                'GB': {'flag': '🇬🇧', 'name_local': 'United Kingdom'},
                'DE': {'flag': '🇩🇪', 'name_local': 'Deutschland'},
                'FR': {'flag': '🇫🇷', 'name_local': 'France'},
                'IT': {'flag': '🇮🇹', 'name_local': 'Italia'},
                'ES': {'flag': '🇪🇸', 'name_local': 'España'},
                'NL': {'flag': '🇳🇱', 'name_local': 'Nederland'},
                'BE': {'flag': '🇧🇪', 'name_local': 'België'},
                'CZ': {'flag': '🇨🇿', 'name_local': 'Česko'},
                'AT': {'flag': '🇦🇹', 'name_local': 'Österreich'},
                'CH': {'flag': '🇨🇭', 'name_local': 'Schweiz'},
                'SE': {'flag': '🇸🇪', 'name_local': 'Sverige'},
                'NO': {'flag': '🇳🇴', 'name_local': 'Norge'},
                'DK': {'flag': '🇩🇰', 'name_local': 'Danmark'},
                'FI': {'flag': '🇫🇮', 'name_local': 'Suomi'},
                'RO': {'flag': '🇷🇴', 'name_local': 'România'},
                'HU': {'flag': '🇭🇺', 'name_local': 'Magyarország'},
                'KZ': {'flag': '🇰🇿', 'name_local': 'Қазақстан'},
                'LT': {'flag': '🇱🇹', 'name_local': 'Lietuva'},
            }
            
            updated_count = 0
            for code, data in country_data.items():
                try:
                    country = Country.objects.get(code=code)
                    country.flag_emoji = data['flag']
                    if data.get('name_local'):
                        country.name_local = data['name_local']
                    country.save()
                    updated_count += 1
                    self.stdout.write(f"  Updated: {country.name} ({code})")
                except Country.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"  Not found: {code}"))
            
            self.stdout.write(
                self.style.SUCCESS(f"\nReloaded flags for {updated_count} countries!")
            )

