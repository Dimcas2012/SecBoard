"""
Django management command to import frameworks with controls from controls_themes.csv
Usage: python manage.py import_frameworks_from_csv
"""
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from app_compliance.models import ComplianceFramework, ControlCategory, Control


class Command(BaseCommand):
    help = 'Import frameworks with controls from controls_themes.csv file'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-file',
            type=str,
            default='app_compliance/сontrols_themes.csv',
            help='Path to the CSV file (default: app_compliance/controls_themes.csv)'
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
            help='Clear existing controls before import'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
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
        
        # Check if file exists
        if not os.path.exists(csv_file):
            raise CommandError(f'CSV file not found: {csv_file}')
        
        self.stdout.write(self.style.SUCCESS(f'Starting import from: {csv_file}'))
        self.stdout.write(f'User: {user.username}')
        
        try:
            with transaction.atomic():
                # Read CSV and group by framework type (PCI DSS, ISO 27001, SOC 2, etc.)
                frameworks_data = {}
                
                with open(csv_file, 'r', encoding='utf-8-sig') as file:
                    csv_reader = csv.DictReader(file, delimiter=';')
                    
                    for row_num, row in enumerate(csv_reader, start=2):
                        framework_code = row.get('framework_code', '').strip()
                        if not framework_code or framework_code == '\\N':
                            continue
                        
                        # Determine framework type and group accordingly
                        framework_key = self._determine_framework_key(framework_code)
                        
                        if framework_key not in frameworks_data:
                            frameworks_data[framework_key] = {
                                'name': self._determine_framework_name(framework_code, row.get('domain', '')),
                                'type': self._determine_framework_type(framework_code, row.get('domain', '')),
                                'version': self._determine_framework_version(framework_code),
                                'controls': []
                            }
                        
                        frameworks_data[framework_key]['controls'].append(row)
                
                self.stdout.write(f'\nFound {len(frameworks_data)} frameworks to import')
                
                # Process each framework
                for framework_key, framework_info in frameworks_data.items():
                    framework_name = framework_info['name']
                    framework_type = framework_info['type']
                    framework_version = framework_info['version']
                    controls_data = framework_info['controls']
                    
                    self.stdout.write(f'\nProcessing framework: {framework_name} ({len(controls_data)} controls)')
                    self.stdout.write(f'\nProcessing framework: {framework_code} ({len(controls_data)} controls)')
                    
                    # Create or get framework template
                    framework, created = ComplianceFramework.objects.get_or_create(
                        name=framework_name,
                        framework_type=framework_type,
                        version=framework_version,
                        is_template=True,
                        defaults={
                            'description': f'Framework imported from controls_themes.csv - {framework_key}',
                            'status': 'draft',
                            'created_by': user,
                        }
                    )
                    
                    if created:
                        self.stdout.write(f'  Created framework template: {framework_name} {framework_version}')
                    else:
                        if not update_mode:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  Framework "{framework_name}" already exists. Skipping. Use --update to update.'
                                )
                            )
                            continue
                        self.stdout.write(f'  Updating existing framework: {framework_name}')
                    
                    if clear_mode and not created:
                        # Clear existing controls and categories
                        deleted_controls = Control.objects.filter(category__framework=framework).count()
                        deleted_categories = ControlCategory.objects.filter(framework=framework).count()
                        
                        Control.objects.filter(category__framework=framework).delete()
                        ControlCategory.objects.filter(framework=framework).delete()
                        
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Cleared {deleted_controls} controls and {deleted_categories} categories'
                            )
                        )
                    
                    # Group controls by category (based on framework_requirement)
                    categories_dict = {}
                    controls_created = 0
                    controls_updated = 0
                    
                    for row in controls_data:
                        framework_code = row.get('framework_code', '').strip()
                        framework_requirement = row.get('framework_requirement', '').strip()
                        
                        # Determine category based on framework type
                        if framework_type == 'pci_dss':
                            # For PCI DSS, group by requirement number (e.g., "06" from "06.???")
                            if framework_code and '.' in framework_code:
                                category_key = framework_code.split('.')[0]
                                category_code = f'REQ-{category_key}'
                                category_name = f'Requirement {category_key}'
                            elif framework_requirement and framework_requirement != '\\N':
                                parts = framework_requirement.split('.')
                                category_key = parts[0] if parts else framework_requirement
                                category_code = f'REQ-{category_key}'
                                category_name = f'Requirement {category_key}'
                            else:
                                category_key = 'OTHER'
                                category_code = 'REQ-OTHER'
                                category_name = 'Other Requirements'
                        elif framework_type == 'iso_27001':
                            # For ISO 27001, group by main control category (e.g., "A.5" from "A.5.1")
                            if framework_code and '.' in framework_code:
                                parts = framework_code.split('.')
                                if len(parts) >= 2:
                                    category_key = f"{parts[0]}.{parts[1]}"
                                    category_code = category_key
                                    category_name = f'Control {category_key}'
                                else:
                                    category_key = parts[0]
                                    category_code = category_key
                                    category_name = f'Control {category_key}'
                            else:
                                category_key = 'OTHER'
                                category_code = 'A.OTHER'
                                category_name = 'Other Controls'
                        elif framework_type == 'soc2':
                            # For SOC 2, group by main control (e.g., "C.6" from "C.6.1.1")
                            if framework_code and '.' in framework_code:
                                parts = framework_code.split('.')
                                if len(parts) >= 2:
                                    category_key = f"{parts[0]}.{parts[1]}"
                                    category_code = category_key
                                    category_name = f'Control {category_key}'
                                else:
                                    category_key = parts[0]
                                    category_code = category_key
                                    category_name = f'Control {category_key}'
                            else:
                                category_key = 'OTHER'
                                category_code = 'C.OTHER'
                                category_name = 'Other Controls'
                        else:
                            # Default grouping
                            if not framework_requirement or framework_requirement == '\\N':
                                category_key = framework_code if framework_code else 'OTHER'
                                category_code = category_key
                                category_name = f'{category_key} Controls'
                            else:
                                parts = framework_requirement.split('.')
                                category_key = parts[0] if parts else framework_requirement
                                category_code = category_key
                                category_name = f'Requirement {category_key}'
                        
                        # Get or create category
                        if category_key not in categories_dict:
                            category, cat_created = ControlCategory.objects.get_or_create(
                                framework=framework,
                                code=category_code,
                                defaults={
                                    'name': category_name,
                                    'description': f'Category for {category_code}',
                                    'order': self._extract_order(category_code),
                                }
                            )
                            categories_dict[category_key] = category
                            
                            if cat_created:
                                self.stdout.write(f'    Created category: {category_code}')
                        else:
                            category = categories_dict[category_key]
                        
                        # Create or update control
                        identifier = row.get('identifier', '').strip()
                        if not identifier or identifier == '\\N':
                            identifier = f"{framework_code}_{row.get('id', '')}"
                        
                        control_code = row.get('code', '').strip()
                        if not control_code or control_code == '\\N':
                            control_code = framework_requirement if framework_requirement else framework_code
                        
                        control_name = row.get('name', '').strip()
                        if not control_name or control_name == '\\N':
                            control_name = row.get('title', '').strip() or f'Control {control_code}'
                        
                        control_description = row.get('description', '').strip()
                        if not control_description or control_description == '\\N':
                            control_description = control_name
                        
                        # Map status
                        status_str = row.get('status', '').strip()
                        status_mapping = {
                            'not_started': 'not_started',
                            'in_progress': 'in_progress',
                            'completed': 'completed',
                            'failed': 'failed',
                            'not_applicable': 'not_applicable',
                        }
                        control_status = status_mapping.get(status_str, 'not_started')
                        
                        # Map priority
                        priority_str = row.get('priority', '').strip()
                        priority_mapping = {
                            'low': 'low',
                            'medium': 'medium',
                            'high': 'high',
                            'critical': 'critical',
                        }
                        control_priority = priority_mapping.get(priority_str, 'medium')
                        
                        # Get required evidence count
                        try:
                            evidence_count = int(row.get('required_evidence_count', 0) or 0)
                        except (ValueError, TypeError):
                            evidence_count = 0
                        
                        # Create or update control
                        control, ctrl_created = Control.objects.update_or_create(
                            category=category,
                            identifier=identifier,
                            defaults={
                                'code': control_code,
                                'name': control_name,
                                'description': control_description,
                                'framework_requirement': framework_requirement if framework_requirement != '\\N' else '',
                                'framework_code': framework_code if framework_code != '\\N' else '',
                                'title': row.get('title', '').strip() or '',
                                'internal_id': row.get('internal_id', '').strip() or '',
                                'domain': domain or '',
                                'status': control_status,
                                'priority': control_priority,
                                'required_evidence_count': evidence_count,
                                'implementation_guidance': row.get('implementation_guidance', '').strip() or '',
                                'testing_procedure': row.get('testing_procedure', '').strip() or '',
                                'created_by': user,
                            }
                        )
                        
                        if ctrl_created:
                            controls_created += 1
                        else:
                            controls_updated += 1
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  Framework {framework_name}: {controls_created} created, {controls_updated} updated, '
                            f'{len(categories_dict)} categories'
                        )
                    )
                
                # Summary
                self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
                self.stdout.write(self.style.SUCCESS('Import completed successfully!'))
                self.stdout.write(self.style.SUCCESS('=' * 70))
                self.stdout.write(f'Total frameworks processed: {len(frameworks_data)}')
                self.stdout.write(self.style.SUCCESS('=' * 70))
        
        except Exception as e:
            raise CommandError(f'Import failed: {str(e)}')
    
    def _determine_framework_key(self, framework_code):
        """Determine framework key for grouping controls"""
        if not framework_code:
            return 'OTHER'
        
        # PCI DSS requirements (01.???, 02.???, etc.)
        if framework_code and '.' in framework_code:
            parts = framework_code.split('.')
            if parts[0].isdigit():
                return 'PCI_DSS'
        
        # ISO 27001 controls (A.5.x, A.6.x, A.7.x, A.8.x)
        if framework_code.startswith('A.'):
            return 'ISO_27001'
        
        # SOC 2 controls (C.x.x)
        if framework_code.startswith('C.'):
            return 'SOC_2'
        
        # Appendix A controls (PCI DSS)
        if framework_code.startswith('Appendix'):
            return 'PCI_DSS'
        
        return 'OTHER'
    
    def _determine_framework_name(self, framework_code, domain):
        """Determine framework name from code and domain"""
        framework_key = self._determine_framework_key(framework_code)
        
        if framework_key == 'PCI_DSS':
            return 'PCI DSS 4.0'
        elif framework_key == 'ISO_27001':
            return 'ISO/IEC 27001:2022'
        elif framework_key == 'SOC_2':
            return 'SOC 2'
        else:
            return f'Framework {framework_code}'
    
    def _determine_framework_type(self, framework_code, domain):
        """Determine framework type"""
        framework_key = self._determine_framework_key(framework_code)
        
        if framework_key == 'PCI_DSS':
            return 'pci_dss'
        elif framework_key == 'ISO_27001':
            return 'iso_27001'
        elif framework_key == 'SOC_2':
            return 'soc2'
        elif 'HIPAA' in domain:
            return 'hipaa'
        elif 'GDPR' in domain:
            return 'gdpr'
        else:
            return 'custom'
    
    def _determine_framework_version(self, framework_code):
        """Determine framework version"""
        framework_key = self._determine_framework_key(framework_code)
        
        if framework_key == 'PCI_DSS':
            return '4.0'
        elif framework_key == 'ISO_27001':
            return '2022'
        elif framework_key == 'SOC_2':
            return '2023'
        else:
            return '1.0'
    
    def _extract_order(self, category_code):
        """Extract order number from category code"""
        try:
            # Try to extract number from code (e.g., "06" from "06.???")
            if '.' in category_code:
                num_str = category_code.split('.')[0]
                if num_str.isdigit():
                    return int(num_str)
            elif category_code.isdigit():
                return int(category_code)
        except (ValueError, AttributeError):
            pass
        return 0

