"""
Django management command to import ISO 27001:2022 controls from CSV file
Usage: python manage.py import_iso27001_csv <path_to_csv>
"""
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from app_compliance.models import ComplianceFramework, ControlCategory, Control


class Command(BaseCommand):
    help = 'Import ISO 27001:2022 controls from CSV file'
    
    # ISO 27001:2022 Control Categories with descriptions
    CATEGORY_DESCRIPTIONS = {
        'C.4': 'Clause 4: Context of the Organization',
        'C.5': 'Clause 5: Leadership',
        'C.6': 'Clause 6: Planning',
        'C.7': 'Clause 7: Support',
        'C.8': 'Clause 8: Operation',
        'C.9': 'Clause 9: Performance Evaluation',
        'C.10': 'Clause 10: Improvement',
        'A.5': 'Annex A.5: Organizational Controls',
        'A.6': 'Annex A.6: People Controls',
        'A.7': 'Annex A.7: Physical Controls',
        'A.8': 'Annex A.8: Technological Controls',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            nargs='?',
            type=str,
            default='app_compliance/ISO 27001_2022 controls.csv',
            help='Path to the CSV file (default: app_compliance/ISO 27001_2022 controls.csv)'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing framework if it exists'
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

        # Check if file exists
        if not os.path.exists(csv_file):
            raise CommandError(f'CSV file not found: {csv_file}')

        self.stdout.write(self.style.SUCCESS(f'Starting import from: {csv_file}'))

        try:
            with transaction.atomic():
                # Create or get framework
                framework, created = ComplianceFramework.objects.get_or_create(
                    name='ISO 27001:2022',
                    defaults={
                        'framework_type': 'iso_27001',
                        'version': '2022',
                        'description': 'ISO/IEC 27001:2022 - Information Security Management System Requirements',
                        'status': 'active',
                        'is_template': True,
                    }
                )

                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created new framework: {framework.name}'))
                else:
                    if not update_mode:
                        raise CommandError(
                            f'Framework "{framework.name}" already exists. '
                            f'Use --update flag to update it.'
                        )
                    self.stdout.write(self.style.WARNING(f'Updating existing framework: {framework.name}'))

                if clear_mode and not created:
                    # Clear existing controls and categories
                    deleted_controls = Control.objects.filter(category__framework=framework).count()
                    deleted_categories = ControlCategory.objects.filter(framework=framework).count()
                    
                    Control.objects.filter(category__framework=framework).delete()
                    ControlCategory.objects.filter(framework=framework).delete()
                    
                    self.stdout.write(
                        self.style.WARNING(
                            f'Cleared {deleted_controls} controls and {deleted_categories} categories'
                        )
                    )

                # Read CSV and import data
                categories_dict = {}
                controls_created = 0
                controls_updated = 0
                controls_skipped = 0
                
                # Track unique controls by UID to handle duplicates
                seen_controls = {}

                with open(csv_file, 'r', encoding='utf-8') as file:
                    csv_reader = csv.DictReader(file)
                    
                    for row_num, row in enumerate(csv_reader, start=2):
                        try:
                            framework_requirement = row.get('Framework requirement', '').strip()
                            framework_code = row.get('Framework code', '').strip()
                            title = row.get('Title', '').strip()
                            control_id = row.get('ID', '').strip()
                            uid = row.get('UID', '').strip()
                            url = row.get('Url', '').strip()
                            description = row.get('Description', '').strip()
                            description_modified = row.get('Description modified?', '').strip()
                            evidence_status = row.get('Evidence status', '').strip()
                            domain = row.get('Domain', '').strip()
                            owner = row.get('Owner', '').strip()
                            note = row.get('Note', '').strip()
                            test_name = row.get('Test name', '').strip()
                            test_url = row.get('Test url', '').strip()
                            test_description = row.get('Test description', '').strip()
                            test_outcome = row.get('Test outcome', '').strip()

                            if not framework_requirement or not uid:
                                self.stdout.write(
                                    self.style.WARNING(f'Row {row_num}: Skipping - missing required fields')
                                )
                                controls_skipped += 1
                                continue

                            # Extract category (e.g., "C.4", "A.5" from "C.4.1" or "A.5.1")
                            # Split by '.' and take first two parts
                            parts = framework_code.split('.')
                            if len(parts) >= 2:
                                category_code = f"{parts[0]}.{parts[1]}"
                            else:
                                category_code = parts[0] if parts else framework_requirement
                            
                            # Get or create category
                            if category_code not in categories_dict:
                                category_name = self.CATEGORY_DESCRIPTIONS.get(
                                    category_code,
                                    f'ISO 27001 {category_code}'
                                )
                                
                                # Determine order
                                if category_code.startswith('C.'):
                                    order = int(category_code.split('.')[1]) if len(category_code.split('.')) > 1 else 0
                                elif category_code.startswith('A.'):
                                    # A.5, A.6, A.7, A.8 come after C.x clauses
                                    order = 10 + int(category_code.split('.')[1]) if len(category_code.split('.')) > 1 else 10
                                else:
                                    order = 100
                                
                                category, cat_created = ControlCategory.objects.get_or_create(
                                    framework=framework,
                                    code=category_code,
                                    defaults={
                                        'name': category_name,
                                        'description': self.CATEGORY_DESCRIPTIONS.get(category_code, ''),
                                        'order': order,
                                    }
                                )
                                categories_dict[category_code] = category
                                
                                if cat_created:
                                    self.stdout.write(f'  Created category: {category_code} - {category_name}')
                            else:
                                category = categories_dict[category_code]

                            # Check if we've already processed this control (same UID)
                            # ISO 27001 CSV has duplicates for different test procedures
                            if uid in seen_controls:
                                # Skip duplicate entries
                                controls_skipped += 1
                                continue

                            # Map evidence status to control status
                            status_mapping = {
                                'OK': 'completed',
                                'Needs evidence': 'not_started',
                                'Not applicable': 'not_applicable',
                                'Fail': 'failed',
                                '': 'not_started',
                            }
                            control_status = status_mapping.get(evidence_status, 'not_started')

                            # Determine priority based on domain
                            priority_mapping = {
                                'SECURITY_PRIVACY_GOVERNANCE': 'high',
                                'IDENTIFICATION_AUTHENTICATION': 'high',
                                'CRYPTOGRAPHIC_PROTECTIONS': 'high',
                                'NETWORK_SECURITY': 'high',
                                'ASSET_MANAGEMENT': 'medium',
                                'ACCESS_MANAGEMENT': 'high',
                                'CONTINUOUS_MONITORING': 'medium',
                                'CONFIGURATION_MANAGEMENT': 'medium',
                                'INCIDENT_RESPONSE': 'high',
                                'DATA_PROTECTION': 'high',
                            }
                            priority = priority_mapping.get(domain, 'medium')

                            # Create unique identifier using UID
                            unique_identifier = uid if uid else f'{control_id}_{framework_code}_{row_num}'
                            
                            # Prepare testing procedure (empty by default, can be filled manually)
                            testing_info = ''
                            
                            # Create or update control
                            control, ctrl_created = Control.objects.update_or_create(
                                category=category,
                                identifier=unique_identifier,  # Using UID as unique key
                                defaults={
                                    # Display fields (visible in UI)
                                    'framework_requirement': framework_requirement,  # e.g., "C.4.1"
                                    'framework_code': framework_code,  # e.g., "C.4.1"
                                    'title': title,  # e.g., "Understanding the organization and its context"
                                    'code': framework_code if framework_code else control_id,  # For display
                                    'name': title if title else (description[:200] if description else f'Control {control_id}'),
                                    'description': description,
                                    
                                    # Internal fields (hidden)
                                    'internal_id': control_id,  # e.g., "GOV-89" (hidden)
                                    'domain': domain,  # e.g., "SECURITY_PRIVACY_GOVERNANCE"
                                    
                                    # Status and priority
                                    'status': control_status,
                                    'priority': priority,
                                    
                                    # Additional info
                                    'testing_procedure': testing_info,
                                    'implementation_guidance': note if note else '',
                                }
                            )
                            
                            # Track this control
                            seen_controls[uid] = control

                            if ctrl_created:
                                controls_created += 1
                            else:
                                controls_updated += 1

                            # Progress indicator
                            if (controls_created + controls_updated) % 50 == 0:
                                self.stdout.write(
                                    f'  Processed {controls_created + controls_updated} controls...'
                                )

                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'Row {row_num}: Error - {str(e)}')
                            )
                            controls_skipped += 1
                            continue

                # Summary
                self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
                self.stdout.write(self.style.SUCCESS('Import completed successfully!'))
                self.stdout.write(self.style.SUCCESS('=' * 70))
                self.stdout.write(f'Framework: {framework.name}')
                self.stdout.write(f'Categories: {len(categories_dict)}')
                self.stdout.write(f'Controls created: {controls_created}')
                self.stdout.write(f'Controls updated: {controls_updated}')
                self.stdout.write(f'Controls skipped (duplicates/invalid): {controls_skipped}')
                self.stdout.write(f'Total unique controls: {controls_created + controls_updated}')
                self.stdout.write(self.style.SUCCESS('=' * 70))

        except Exception as e:
            raise CommandError(f'Import failed: {str(e)}')

