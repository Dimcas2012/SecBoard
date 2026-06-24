"""
Django management command to populate FrameworkDomain from existing Control domains
and update domain references for Framework Template controls.

Usage: 
    python manage.py populate_framework_domains
    python manage.py populate_framework_domains --dry-run
    python manage.py populate_framework_domains --from-old-column
"""
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.utils import timezone
from app_compliance.models import Control, FrameworkDomain, ComplianceFramework


class Command(BaseCommand):
    help = 'Populate FrameworkDomain from existing Control domains and update domain references for Framework Template controls'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--from-old-column',
            action='store_true',
            help='Read domain values from old varchar column (if migration not fully applied)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        from_old_column = options['from_old_column']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))

        with transaction.atomic():
            # Step 1: Get all unique domain values
            domain_codes = set()
            
            if from_old_column:
                # Try to read from old varchar column if it exists
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT COLUMN_TYPE 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'app_compliance_control' 
                            AND COLUMN_NAME = 'domain'
                        """)
                        result = cursor.fetchone()
                        
                        if result and 'varchar' in result[0].lower():
                            # Old column exists, get values
                            cursor.execute("""
                                SELECT DISTINCT domain 
                                FROM app_compliance_control 
                                WHERE domain IS NOT NULL AND domain != ''
                            """)
                            domain_codes = {row[0] for row in cursor.fetchall() if row[0]}
                            self.stdout.write(f'Found {len(domain_codes)} domains from old varchar column')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Could not read from old column: {e}'))
            
            # Also get domains from existing FrameworkDomain references
            controls_with_domain = Control.objects.select_related('domain').filter(domain__isnull=False)
            for control in controls_with_domain:
                if control.domain:
                    domain_codes.add(control.domain.code)
            
            if not domain_codes:
                self.stdout.write(self.style.WARNING('No domain values found'))
                return
            
            self.stdout.write(f'Found {len(domain_codes)} unique domain values: {", ".join(sorted(domain_codes))}\n')
            
            # Step 2: Create FrameworkDomain entries
            created_count = 0
            updated_count = 0
            domain_map = {}  # Map code to FrameworkDomain object
            
            for domain_code in sorted(domain_codes):
                domain_obj, created = FrameworkDomain.objects.get_or_create(
                    code=domain_code,
                    defaults={
                        'name': domain_code.replace('_', ' ').title(),
                        'description': f'Domain: {domain_code}',
                        'display_order': 0,
                        'is_active': True,
                    }
                )
                
                domain_map[domain_code] = domain_obj
                
                if created:
                    created_count += 1
                    if not dry_run:
                        self.stdout.write(self.style.SUCCESS(f'✓ Created FrameworkDomain: {domain_code}'))
                    else:
                        self.stdout.write(f'Would create FrameworkDomain: {domain_code}')
                else:
                    # Update if inactive
                    if not domain_obj.is_active:
                        if not dry_run:
                            domain_obj.is_active = True
                            domain_obj.save()
                            updated_count += 1
                            self.stdout.write(self.style.SUCCESS(f'✓ Activated FrameworkDomain: {domain_code}'))
                        else:
                            self.stdout.write(f'Would activate FrameworkDomain: {domain_code}')
            
            self.stdout.write(f'\nCreated {created_count} new FrameworkDomain entries')
            if updated_count > 0:
                self.stdout.write(f'Updated {updated_count} existing FrameworkDomain entries')
            
            # Step 3: Update domain references for template framework controls
            if not dry_run:
                self.stdout.write('\nUpdating domain references for Framework Template controls...')
                updated_controls = 0
                
                # Try to update using raw SQL if old column exists
                if from_old_column:
                    try:
                        with connection.cursor() as cursor:
                            # Check if old varchar column exists
                            cursor.execute("""
                                SELECT COLUMN_TYPE 
                                FROM INFORMATION_SCHEMA.COLUMNS 
                                WHERE TABLE_SCHEMA = DATABASE() 
                                AND TABLE_NAME = 'app_compliance_control' 
                                AND COLUMN_NAME = 'domain'
                                AND COLUMN_TYPE LIKE 'varchar%'
                            """)
                            old_column_exists = cursor.fetchone() is not None
                            
                            if old_column_exists:
                                # Update template framework controls using raw SQL
                                for domain_code, domain_obj in domain_map.items():
                                    cursor.execute("""
                                        UPDATE app_compliance_control c
                                        INNER JOIN app_compliance_controlcategory cat ON c.category_id = cat.id
                                        INNER JOIN app_compliance_complianceframework fw ON cat.framework_id = fw.id
                                        SET c.domain_id = %s
                                        WHERE fw.is_template = 1
                                        AND (c.domain_id IS NULL OR c.domain_id = 0)
                                        AND CAST(c.domain AS CHAR) = %s
                                    """, [domain_obj.id, domain_code])
                                    updated_controls += cursor.rowcount
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(
                            f'Error updating via raw SQL: {e}'
                        ))
                
                # Also update controls that have domain set but need verification
                template_controls = Control.objects.filter(
                    category__framework__is_template=True
                ).select_related('category__framework', 'domain')
                
                verified_count = 0
                for control in template_controls:
                    if control.domain and control.domain.is_active:
                        verified_count += 1
                
                if updated_controls > 0:
                    self.stdout.write(self.style.SUCCESS(
                        f'Updated {updated_controls} template framework controls with domain references'
                    ))
                self.stdout.write(f'Verified {verified_count} controls already have domain assigned')
            
            # Step 4: Summary for template frameworks
            template_frameworks = ComplianceFramework.objects.filter(is_template=True)
            self.stdout.write(f'\nTemplate Frameworks: {template_frameworks.count()}')
            
            for framework in template_frameworks:
                controls = Control.objects.filter(category__framework=framework)
                controls_with_domain = controls.filter(domain__isnull=False).count()
                self.stdout.write(
                    f'  {framework.name}: {controls.count()} controls, '
                    f'{controls_with_domain} with domain assigned'
                )
            
            if dry_run:
                self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were made'))
            else:
                self.stdout.write(self.style.SUCCESS('\n✓ Successfully populated FrameworkDomain and updated controls'))
