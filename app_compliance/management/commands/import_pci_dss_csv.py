"""
Django management command to import PCI DSS 4.0.1 controls from CSV file
Usage: python manage.py import_pci_dss_csv <path_to_csv>
"""
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from app_compliance.models import ComplianceFramework, ControlCategory, Control


class Command(BaseCommand):
    help = 'Import PCI DSS 4.0.1 Service Provider controls from CSV file'
    
    # PCI DSS Requirements with FULL OFFICIAL descriptions
    REQUIREMENT_DESCRIPTIONS = {
        '1': 'Install and Maintain Network Security Controls (NSCs)',
        '2': 'Apply Secure Configurations to All System Components',
        '3': 'Protect Stored Account Data',
        '4': 'Protect Cardholder Data with Strong Cryptography During Transmission Over Open, Public Networks',
        '5': 'Protect All Systems and Networks from Malicious Software',
        '6': 'Develop and Maintain Secure Systems and Software',
        '7': 'Restrict Access to System Components and Cardholder Data by Business Need to Know',
        '8': 'Identify Users and Authenticate Access to System Components',
        '9': 'Restrict Physical Access to Cardholder Data',
        '10': 'Log and Monitor All Access to System Components and Cardholder Data',
        '11': 'Test Security of Systems and Networks Regularly',
        '12': 'Support Information Security with Organizational Policies and Programs',
        'Appendix A1': 'Additional PCI DSS Requirements for Multi-Tenant Service Providers',
        'Appendix A2': 'Additional PCI DSS Requirements for Entities Using SSL/Early TLS for Card-Present POS POI Terminal Connections',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            nargs='?',
            type=str,
            default='app_compliance/PCI DSS 4.0.1 - ROC - Service Provider controls.csv',
            help='Path to the CSV file (default: app_compliance/PCI DSS 4.0.1 - ROC - Service Provider controls.csv)'
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
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID for created_by (default: first user)'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        update_mode = options['update']
        clear_mode = options['clear']
        
        # Get user
        if options.get('user_id'):
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
                # Create or get framework
                framework, created = ComplianceFramework.objects.get_or_create(
                    name='PCI DSS 4.0.1 - Service Provider',
                    framework_type='pci_dss',
                    version='4.0.1',
                    is_template=True,
                    defaults={
                        'description': 'PCI DSS 4.0.1 - Report on Compliance - Service Provider Controls',
                        'status': 'active',
                        'created_by': user,
                    }
                )
                
                # Update framework if it exists and update_mode is enabled
                if not created and update_mode:
                    framework.description = 'PCI DSS 4.0.1 - Report on Compliance - Service Provider Controls'
                    framework.status = 'active'
                    framework.save()

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

                with open(csv_file, 'r', encoding='utf-8-sig') as file:
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

                            if not framework_requirement or not control_id:
                                self.stdout.write(
                                    self.style.WARNING(f'Row {row_num}: Skipping - missing required fields')
                                )
                                controls_skipped += 1
                                continue

                            # Get or create category (ONE category per main Requirement)
                            # Extract main requirement number (e.g., "1" from "1.1", "1.2", "1.3")
                            if framework_requirement.startswith('Appendix A2'):
                                main_requirement = 'Appendix A2'
                                category_code = 'Appendix A2'
                                category_name = self.REQUIREMENT_DESCRIPTIONS.get('Appendix A2', 'Appendix A2')
                            elif framework_requirement.startswith('Appendix A'):
                                main_requirement = 'Appendix A1'
                                category_code = 'Appendix A1'
                                category_name = self.REQUIREMENT_DESCRIPTIONS.get('Appendix A1', 'Appendix A1')
                            else:
                                # Extract main requirement number (e.g., "1" from "1.1" or "1.2.3")
                                main_requirement = framework_requirement.split('.')[0] if '.' in framework_requirement else framework_requirement
                                category_code = main_requirement
                                
                                # Get full requirement description
                                requirement_desc = self.REQUIREMENT_DESCRIPTIONS.get(main_requirement, '')
                                if requirement_desc:
                                    category_name = f'Requirement {main_requirement}: {requirement_desc}'
                                else:
                                    category_name = f'Requirement {main_requirement}'
                            
                            # Use main_requirement as key (so 1.1, 1.2, 1.3 all use same category "1")
                            if main_requirement not in categories_dict:
                                category, cat_created = ControlCategory.objects.get_or_create(
                                    framework=framework,
                                    code=category_code,
                                    defaults={
                                        'name': category_name,
                                        'description': self.REQUIREMENT_DESCRIPTIONS.get(main_requirement, f'PCI DSS Requirement {main_requirement}'),
                                        'order': int(main_requirement) if main_requirement.isdigit() else 100,
                                    }
                                )
                                categories_dict[main_requirement] = category
                                
                                if cat_created:
                                    self.stdout.write(f'  Created category: {category_code} - {category_name}')
                            else:
                                category = categories_dict[main_requirement]

                            # Map evidence status to control status
                            status_mapping = {
                                'OK': 'completed',
                                'Needs evidence': 'not_started',
                                'Not applicable': 'not_applicable',
                                '': 'not_started',
                            }
                            control_status = status_mapping.get(evidence_status, 'not_started')

                            # Determine priority based on domain
                            priority_mapping = {
                                'NETWORK_SECURITY': 'high',
                                'CRYPTOGRAPHIC_PROTECTIONS': 'high',
                                'IDENTIFICATION_AUTHENTICATION': 'high',
                                'CONTINUOUS_MONITORING': 'medium',
                                'CONFIGURATION_MANAGEMENT': 'medium',
                            }
                            priority = priority_mapping.get(domain, 'medium')

                            # Create unique identifier using UID
                            unique_identifier = uid if uid else f'{control_id}_{framework_code}_{row_num}'
                            
                            # Use framework_code as display code (unique within category)
                            control_code = framework_code if framework_code else title if title else control_id
                            
                            # Create or update control
                            # Use code for unique constraint (unique_together: category, code)
                            control, ctrl_created = Control.objects.update_or_create(
                                category=category,
                                code=control_code,
                                defaults={
                                    # Unique identifier field (from UID)
                                    'identifier': unique_identifier,
                                    
                                    # Display fields (visible in UI)
                                    'framework_requirement': framework_requirement,  # e.g., "1.1"
                                    'framework_code': framework_code,  # e.g., "1.1.1.a"
                                    'title': title,  # e.g., "1.1.1"
                                    'name': description if description else (title if title else f'Control {control_id}'),
                                    'description': description,
                                    
                                    # Internal fields (hidden)
                                    'internal_id': control_id,  # e.g., "NET-192" (hidden)
                                    'domain': domain,  # e.g., "NETWORK_SECURITY"
                                    
                                    # Status and priority
                                    'status': control_status,
                                    'priority': priority,
                                    
                                    # Additional info
                                    'testing_procedure': f'Domain: {domain}\nUID: {uid}\nReference: {url}',
                                    'implementation_guidance': note if note else '',
                                    'created_by': user,
                                }
                            )

                            if ctrl_created:
                                controls_created += 1
                            else:
                                controls_updated += 1

                            # Progress indicator
                            if (controls_created + controls_updated) % 100 == 0:
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
                self.stdout.write(f'Controls skipped: {controls_skipped}')
                self.stdout.write(f'Total controls: {controls_created + controls_updated}')
                self.stdout.write(self.style.SUCCESS('=' * 70))

        except Exception as e:
            raise CommandError(f'Import failed: {str(e)}')

