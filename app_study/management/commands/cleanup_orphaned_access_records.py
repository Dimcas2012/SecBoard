from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps


class Command(BaseCommand):
    help = 'Clean up orphaned records in app_quiz_accesspage_companies and app_quiz_accessquiz_companies tables'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Clean up both tables
        self.cleanup_accesspage_companies(dry_run)
        self.cleanup_accessquiz_companies(dry_run)
    
    def cleanup_accesspage_companies(self, dry_run):
        """Clean up orphaned records in app_quiz_accesspage_companies table"""
        try:
            with connection.cursor() as cursor:
                # Check if the table exists
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'app_quiz_accesspage_companies'
                """)
                
                if cursor.fetchone()[0] == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            'Table app_quiz_accesspage_companies does not exist. Nothing to clean up.'
                        )
                    )
                    return
                
                # Find orphaned records (records that reference non-existent accesspage_id)
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM app_quiz_accesspage_companies apc
                    LEFT JOIN app_study_accesspage ap ON apc.accesspage_id = ap.id
                    WHERE ap.id IS NULL
                """)
                
                orphaned_count = cursor.fetchone()[0]
                
                if orphaned_count == 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            'No orphaned records found in app_quiz_accesspage_companies table.'
                        )
                    )
                    return
                
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Would delete {orphaned_count} orphaned records from app_quiz_accesspage_companies table.'
                        )
                    )
                    
                    # Show some examples of orphaned records
                    cursor.execute("""
                        SELECT apc.accesspage_id, apc.company_id
                        FROM app_quiz_accesspage_companies apc
                        LEFT JOIN app_study_accesspage ap ON apc.accesspage_id = ap.id
                        WHERE ap.id IS NULL
                        LIMIT 5
                    """)
                    
                    examples = cursor.fetchall()
                    if examples:
                        self.stdout.write('Examples of orphaned records in app_quiz_accesspage_companies:')
                        for accesspage_id, company_id in examples:
                            self.stdout.write(f'  - accesspage_id: {accesspage_id}, company_id: {company_id}')
                else:
                    # Delete orphaned records
                    cursor.execute("""
                        DELETE apc FROM app_quiz_accesspage_companies apc
                        LEFT JOIN app_study_accesspage ap ON apc.accesspage_id = ap.id
                        WHERE ap.id IS NULL
                    """)
                    
                    deleted_count = cursor.rowcount
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Successfully deleted {deleted_count} orphaned records from app_quiz_accesspage_companies table.'
                        )
                    )
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error cleaning up orphaned records in app_quiz_accesspage_companies: {str(e)}'
                )
            )
    
    def cleanup_accessquiz_companies(self, dry_run):
        """Clean up orphaned records in app_quiz_accessquiz_companies table"""
        try:
            with connection.cursor() as cursor:
                # Check if the table exists
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'app_quiz_accessquiz_companies'
                """)
                
                if cursor.fetchone()[0] == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            'Table app_quiz_accessquiz_companies does not exist. Nothing to clean up.'
                        )
                    )
                    return
                
                # Find orphaned records (records that reference non-existent accessquiz_id)
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM app_quiz_accessquiz_companies aqc
                    LEFT JOIN app_study_accessquiz aq ON aqc.accessquiz_id = aq.id
                    WHERE aq.id IS NULL
                """)
                
                orphaned_count = cursor.fetchone()[0]
                
                if orphaned_count == 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            'No orphaned records found in app_quiz_accessquiz_companies table.'
                        )
                    )
                    return
                
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Would delete {orphaned_count} orphaned records from app_quiz_accessquiz_companies table.'
                        )
                    )
                    
                    # Show some examples of orphaned records
                    cursor.execute("""
                        SELECT aqc.accessquiz_id, aqc.company_id
                        FROM app_quiz_accessquiz_companies aqc
                        LEFT JOIN app_study_accessquiz aq ON aqc.accessquiz_id = aq.id
                        WHERE aq.id IS NULL
                        LIMIT 5
                    """)
                    
                    examples = cursor.fetchall()
                    if examples:
                        self.stdout.write('Examples of orphaned records in app_quiz_accessquiz_companies:')
                        for accessquiz_id, company_id in examples:
                            self.stdout.write(f'  - accessquiz_id: {accessquiz_id}, company_id: {company_id}')
                else:
                    # Delete orphaned records
                    cursor.execute("""
                        DELETE aqc FROM app_quiz_accessquiz_companies aqc
                        LEFT JOIN app_study_accessquiz aq ON aqc.accessquiz_id = aq.id
                        WHERE aq.id IS NULL
                    """)
                    
                    deleted_count = cursor.rowcount
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Successfully deleted {deleted_count} orphaned records from app_quiz_accessquiz_companies table.'
                        )
                    )
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error cleaning up orphaned records in app_quiz_accessquiz_companies: {str(e)}'
                )
            )
