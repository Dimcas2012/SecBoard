"""
Management команда для виправлення charset/collation таблиці Country
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fix charset and collation for Country table to support emoji'
    
    def handle(self, *args, **options):
        """Виправити charset таблиці Country"""
        
        with connection.cursor() as cursor:
            # Отримати назву БД
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            
            self.stdout.write(f"Database: {db_name}")
            
            # Перевірити поточний charset таблиці
            cursor.execute("""
                SELECT TABLE_NAME, TABLE_COLLATION 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'app_compliance_country'
            """, [db_name])
            
            result = cursor.fetchone()
            if result:
                self.stdout.write(f"Current collation: {result[1]}")
            
            # Конвертувати таблицю до utf8mb4
            self.stdout.write(self.style.WARNING("Converting table to utf8mb4..."))
            
            try:
                cursor.execute("""
                    ALTER TABLE app_compliance_country 
                    CONVERT TO CHARACTER SET utf8mb4 
                    COLLATE utf8mb4_unicode_ci
                """)
                
                self.stdout.write(
                    self.style.SUCCESS("✓ Table converted successfully!")
                )
                
                # Конвертувати поле flag_emoji окремо для впевненості
                cursor.execute("""
                    ALTER TABLE app_compliance_country 
                    MODIFY flag_emoji VARCHAR(10) 
                    CHARACTER SET utf8mb4 
                    COLLATE utf8mb4_unicode_ci
                """)
                
                self.stdout.write(
                    self.style.SUCCESS("✓ Flag emoji field updated!")
                )
                
                # Перевірити після змін
                cursor.execute("""
                    SELECT COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME 
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = %s 
                    AND TABLE_NAME = 'app_compliance_country' 
                    AND COLUMN_NAME = 'flag_emoji'
                """, [db_name])
                
                result = cursor.fetchone()
                if result:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Verified: flag_emoji - charset: {result[1]}, collation: {result[2]}"
                        )
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Error: {str(e)}")
                )
                return
        
        self.stdout.write(
            self.style.SUCCESS("\n✓ Charset fix completed! Try adding emoji flags now.")
        )

