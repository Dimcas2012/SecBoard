"""
Management команда для виправлення кодування текстів у LocalComplianceRegulator
"""
from django.core.management.base import BaseCommand
from django.db import connection
from app_compliance.models import LocalComplianceRegulator


class Command(BaseCommand):
    help = 'Fix charset encoding for LocalComplianceRegulator fields'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-data',
            action='store_true',
            help='Fix existing data encoding issues',
        )
    
    def handle(self, *args, **options):
        """Виправити charset таблиці та даних"""
        
        with connection.cursor() as cursor:
            # Отримати назву БД
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            
            self.stdout.write(f"Database: {db_name}")
            
            # Перевірити поточний charset таблиці
            cursor.execute("""
                SELECT TABLE_NAME, TABLE_COLLATION 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'app_compliance_localcomplianceregulator'
            """, [db_name])
            
            result = cursor.fetchone()
            if result:
                self.stdout.write(f"Current table collation: {result[1]}")
            
            # Конвертувати таблицю до utf8mb4
            self.stdout.write(self.style.WARNING("\nConverting table to utf8mb4..."))
            
            try:
                cursor.execute("""
                    ALTER TABLE app_compliance_localcomplianceregulator 
                    CONVERT TO CHARACTER SET utf8mb4 
                    COLLATE utf8mb4_unicode_ci
                """)
                
                self.stdout.write(
                    self.style.SUCCESS("✓ Table converted successfully!")
                )
                
                # Конвертувати текстові поля окремо
                text_fields = ['name', 'name_local', 'acronym', 'description']
                
                for field in text_fields:
                    cursor.execute(f"""
                        ALTER TABLE app_compliance_localcomplianceregulator 
                        MODIFY {field} VARCHAR(200) 
                        CHARACTER SET utf8mb4 
                        COLLATE utf8mb4_unicode_ci
                    """)
                    
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Field '{field}' updated!")
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Error: {str(e)}")
                )
                return
        
        # Виправити дані якщо потрібно
        if options['fix_data']:
            self.stdout.write(self.style.WARNING("\n📝 Fixing data encoding..."))
            
            regulators = LocalComplianceRegulator.objects.all()
            fixed_count = 0
            
            for regulator in regulators:
                changed = False
                
                # Спробувати виправити name_local
                if regulator.name_local:
                    try:
                        # Перевірити чи є проблема з кодуванням
                        if any(char in regulator.name_local for char in ['Р', 'Р†', 'Рѕ', 'Р°']):
                            # Спробувати декодувати
                            try:
                                # Latin-1 to UTF-8 fix
                                fixed_text = regulator.name_local.encode('latin1').decode('utf-8')
                                regulator.name_local = fixed_text
                                changed = True
                                self.stdout.write(
                                    self.style.SUCCESS(f"  Fixed: {regulator.name} - {fixed_text}")
                                )
                            except:
                                self.stdout.write(
                                    self.style.WARNING(f"  Cannot auto-fix: {regulator.name}")
                                )
                    except Exception as e:
                        pass
                
                if changed:
                    regulator.save()
                    fixed_count += 1
            
            if fixed_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"\n✓ Fixed {fixed_count} regulators!")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("\n✓ No data encoding issues found!")
                )
        else:
            self.stdout.write(
                self.style.WARNING("\n💡 To fix existing data, run: python manage.py fix_regulator_charset --fix-data")
            )
        
        self.stdout.write(
            self.style.SUCCESS("\n✓ Charset fix completed!")
        )

