"""
Django management command to import template frameworks with controls from CSV files
Usage: python manage.py import_template_frameworks
"""
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from app_compliance.models import ComplianceFramework, ControlCategory, Control


def parse_null(value):
    """Parse NULL values from CSV (\\N or empty)"""
    if not value or value == '\\N' or value.strip() == '':
        return None
    return value.strip()


def parse_int(value, default=0):
    """Parse integer from CSV"""
    if not value or value == '\\N':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_bool(value):
    """Parse boolean from CSV (1/0 or "1"/"0")"""
    if not value or value == '\\N':
        return False
    if isinstance(value, str):
        return value.strip() == '1' or value.strip().lower() == 'true'
    return bool(value)


class Command(BaseCommand):
    help = 'Import template frameworks with controls from CSV files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--framework-csv',
            type=str,
            default='app_compliance/app_compliance_complianceframework.csv',
            help='Path to framework CSV file'
        )
        parser.add_argument(
            '--category-csv',
            type=str,
            default='app_compliance/app_compliance_controlcategory.csv',
            help='Path to category CSV file'
        )
        parser.add_argument(
            '--control-csv',
            type=str,
            default='app_compliance/app_compliance_control.csv',
            help='Path to control CSV file'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID for created_by (default: first user)'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing frameworks if they exist'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing template frameworks before import'
        )

    def handle(self, *args, **options):
        framework_csv = options['framework_csv']
        category_csv = options['category_csv']
        control_csv = options['control_csv']
        update_mode = options['update']
        clear_mode = options['clear']
        
        # Get user
        if options['user_id']:
            try:
                user = User.objects.get(id=options['user_id'])
            except User.DoesNotExist:
                raise CommandError(f'User with ID {options["user_id"]} not found')
        else:
            user = User.objects.first()
            if not user:
                raise CommandError('No user found! Create a user first.')
        
        # Check if files exist
        for csv_file in [framework_csv, category_csv, control_csv]:
            if not os.path.exists(csv_file):
                raise CommandError(f'CSV file not found: {csv_file}')
        
        self.stdout.write(self.style.SUCCESS('Starting import of template frameworks...'))
        self.stdout.write(f'User: {user.username}')
        
        try:
            with transaction.atomic():
                # Clear existing templates if requested
                if clear_mode:
                    deleted = ComplianceFramework.objects.filter(is_template=True).count()
                    ComplianceFramework.objects.filter(is_template=True).delete()
                    self.stdout.write(
                        self.style.WARNING(f'Cleared {deleted} existing template frameworks')
                    )
                
                # Step 1: Read frameworks CSV and filter templates
                self.stdout.write('\nReading frameworks...')
                template_frameworks = {}
                
                with open(framework_csv, 'r', encoding='utf-8-sig') as file:
                    csv_reader = csv.DictReader(file, delimiter=';')
                    
                    for row in csv_reader:
                        framework_id = parse_int(row.get('id'))
                        is_template = parse_bool(row.get('is_template', '0'))
                        template_id = parse_null(row.get('template_id'))
                        company_id = parse_null(row.get('company_id'))
                        
                        # Only process templates (is_template=1, no template_id, no company_id)
                        if not is_template or not framework_id:
                            continue
                        
                        # Skip if template_id is set (instances have template_id pointing to template)
                        if template_id:
                            continue
                        
                        # Skip if company_id is set (instances have company_id)
                        if company_id:
                            continue
                        
                        template_frameworks[framework_id] = {
                            'id': framework_id,
                            'name': parse_null(row.get('name')) or 'Unnamed Framework',
                            'framework_type': parse_null(row.get('framework_type')) or 'custom',
                            'version': parse_null(row.get('version')) or '1.0',
                            'description': parse_null(row.get('description')) or '',
                            'status': parse_null(row.get('status')) or 'active',
                            'is_mandatory': parse_bool(row.get('is_mandatory', '0')),
                            'review_frequency': parse_null(row.get('review_frequency')) or 'annual',
                            'created_by_id': parse_int(row.get('created_by_id')),
                        }
                
                self.stdout.write(f'Found {len(template_frameworks)} template frameworks')
                
                # Step 2: Read categories CSV
                self.stdout.write('\nReading categories...')
                categories_by_framework = {}
                
                with open(category_csv, 'r', encoding='utf-8-sig') as file:
                    csv_reader = csv.DictReader(file, delimiter=';')
                    
                    for row in csv_reader:
                        category_id = parse_int(row.get('id'))
                        framework_id = parse_int(row.get('framework_id'))
                        
                        if not category_id or not framework_id:
                            continue
                        
                        # Only process categories for template frameworks
                        if framework_id not in template_frameworks:
                            continue
                        
                        if framework_id not in categories_by_framework:
                            categories_by_framework[framework_id] = []
                        
                        categories_by_framework[framework_id].append({
                            'id': category_id,
                            'code': parse_null(row.get('code')) or f'CAT-{category_id}',
                            'name': parse_null(row.get('name')) or 'Unnamed Category',
                            'description': parse_null(row.get('description')) or '',
                            'order': parse_int(row.get('order'), 0),
                        })
                
                total_categories = sum(len(cats) for cats in categories_by_framework.values())
                self.stdout.write(f'Found {total_categories} categories')
                
                # Step 3: Create category_id -> framework_id mapping
                category_to_framework = {}
                for framework_id, cats in categories_by_framework.items():
                    for cat in cats:
                        category_to_framework[cat['id']] = framework_id
                
                # Step 4: Read controls CSV
                self.stdout.write('\nReading controls...')
                controls_by_category = {}
                
                with open(control_csv, 'r', encoding='utf-8-sig') as file:
                    csv_reader = csv.DictReader(file, delimiter=';')
                    
                    for row in csv_reader:
                        control_id = parse_int(row.get('id'))
                        category_id = parse_int(row.get('category_id'))
                        
                        if not control_id or not category_id:
                            continue
                        
                        # Find which framework this category belongs to
                        framework_id = category_to_framework.get(category_id)
                        
                        # Only process controls for template frameworks
                        if not framework_id:
                            continue
                        
                        if category_id not in controls_by_category:
                            controls_by_category[category_id] = []
                        
                        controls_by_category[category_id].append({
                            'id': control_id,
                            'identifier': parse_null(row.get('identifier')) or f'CTRL-{control_id}',
                            'code': parse_null(row.get('code')) or f'CTRL-{control_id}',
                            'name': parse_null(row.get('name')) or 'Unnamed Control',
                            'description': parse_null(row.get('description')) or '',
                            'framework_code': parse_null(row.get('framework_code')) or '',
                            'framework_requirement': parse_null(row.get('framework_requirement')) or '',
                            'title': parse_null(row.get('title')) or '',
                            'internal_id': parse_null(row.get('internal_id')) or '',
                            'domain': parse_null(row.get('domain')) or '',
                            'status': parse_null(row.get('status')) or 'not_started',
                            'priority': parse_null(row.get('priority')) or 'medium',
                            'required_evidence_count': parse_int(row.get('required_evidence_count'), 0),
                            'implementation_guidance': parse_null(row.get('implementation_guidance')) or '',
                            'testing_procedure': parse_null(row.get('testing_procedure')) or '',
                            'order': parse_int(row.get('order'), 0),
                        })
                
                total_controls = sum(len(ctrls) for ctrls in controls_by_category.values())
                self.stdout.write(f'Found {total_controls} controls')
                
                # Step 5: Import frameworks, categories, and controls
                self.stdout.write('\n' + '=' * 70)
                self.stdout.write('Importing template frameworks...')
                self.stdout.write('=' * 70)
                
                frameworks_created = 0
                frameworks_updated = 0
                total_categories_created = 0
                total_controls_created = 0
                
                for framework_id, fw_data in template_frameworks.items():
                    self.stdout.write(f'\nProcessing: {fw_data["name"]} {fw_data["version"]}')
                    
                    # Create or update framework
                    framework, created = ComplianceFramework.objects.get_or_create(
                        name=fw_data['name'],
                        framework_type=fw_data['framework_type'],
                        version=fw_data['version'],
                        is_template=True,
                        defaults={
                            'description': fw_data['description'],
                            'status': fw_data['status'],
                            'is_mandatory': fw_data['is_mandatory'],
                            'review_frequency': fw_data['review_frequency'],
                            'created_by': user,
                        }
                    )
                    
                    if created:
                        frameworks_created += 1
                        self.stdout.write(f'  ✓ Created framework template')
                    else:
                        if update_mode:
                            framework.description = fw_data['description']
                            framework.status = fw_data['status']
                            framework.is_mandatory = fw_data['is_mandatory']
                            framework.review_frequency = fw_data['review_frequency']
                            framework.save()
                            frameworks_updated += 1
                            self.stdout.write(f'  ✓ Updated framework template')
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  ⊗ Framework already exists. Use --update to update.'
                                )
                            )
                            continue
                    
                    # Import categories
                    categories_data = categories_by_framework.get(framework_id, [])
                    category_map = {}  # Map old category_id to new category object
                    categories_created = 0
                    
                    for cat_data in categories_data:
                        category, cat_created = ControlCategory.objects.get_or_create(
                            framework=framework,
                            code=cat_data['code'],
                            defaults={
                                'name': cat_data['name'],
                                'description': cat_data['description'],
                                'order': cat_data['order'],
                            }
                        )
                        
                        if cat_created:
                            categories_created += 1
                        
                        # Map old category_id to new category
                        category_map[cat_data['id']] = category
                    
                    total_categories_created += categories_created
                    self.stdout.write(f'  ✓ Created {categories_created} categories')
                    
                    # Import controls
                    controls_created = 0
                    for old_category_id, category in category_map.items():
                        controls_data = controls_by_category.get(old_category_id, [])
                        
                        for ctrl_data in controls_data:
                            # Use code for unique constraint (unique_together: category, code)
                            control_code = ctrl_data['code']
                            if not control_code:
                                control_code = f"CTRL-{ctrl_data['id']}"
                            
                            control, ctrl_created = Control.objects.get_or_create(
                                category=category,
                                code=control_code,
                                defaults={
                                    'identifier': ctrl_data['identifier'] or '',
                                    'name': ctrl_data['name'],
                                    'description': ctrl_data['description'],
                                    'framework_code': ctrl_data['framework_code'],
                                    'framework_requirement': ctrl_data['framework_requirement'],
                                    'title': ctrl_data['title'],
                                    'internal_id': ctrl_data['internal_id'],
                                    'domain': ctrl_data['domain'],
                                    'status': ctrl_data['status'],
                                    'priority': ctrl_data['priority'],
                                    'required_evidence_count': ctrl_data['required_evidence_count'],
                                    'implementation_guidance': ctrl_data['implementation_guidance'],
                                    'testing_procedure': ctrl_data['testing_procedure'],
                                    'order': ctrl_data['order'],
                                    'created_by': user,
                                }
                            )
                            
                            if ctrl_created:
                                controls_created += 1
                    
                    total_controls_created += controls_created
                    self.stdout.write(f'  ✓ Created {controls_created} controls')
                
                # Summary
                self.stdout.write('\n' + '=' * 70)
                self.stdout.write(self.style.SUCCESS('Import completed successfully!'))
                self.stdout.write('=' * 70)
                self.stdout.write(f'Template frameworks: {frameworks_created} created, {frameworks_updated} updated')
                self.stdout.write(f'Categories: {total_categories_created} created')
                self.stdout.write(f'Controls: {total_controls_created} created')
                self.stdout.write('=' * 70)
        
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'Import failed: {str(e)}'))
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise CommandError(f'Import failed: {str(e)}')

