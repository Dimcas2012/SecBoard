"""
Management command to load Requirement Type, Status, and Priority data
"""
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from app_compliance.models import RequirementType, RequirementStatus, RequirementPriority


class Command(BaseCommand):
    help = 'Load Requirement Type, Status, and Priority data into the database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n📋 Loading Requirement Dictionaries...'))
        
        # Requirement Types
        self.stdout.write(self.style.SUCCESS('\n1️⃣ Loading Requirement Types...'))
        requirement_types_data = [
            {
                'name': 'Law',
                'name_local': 'Закон',
                'code': 'law',
                'color': '#1e3a8a',  # Dark blue
                'display_order': 1,
                'description': 'Legislative act passed by parliament',
            },
            {
                'name': 'Regulation',
                'name_local': 'Постанова',
                'code': 'regulation',
                'color': '#7c3aed',  # Purple
                'display_order': 2,
                'description': 'Regulatory document issued by government body',
            },
            {
                'name': 'Directive',
                'name_local': 'Директива',
                'code': 'directive',
                'color': '#2563eb',  # Blue
                'display_order': 3,
                'description': 'Directive requiring implementation',
            },
            {
                'name': 'Resolution',
                'name_local': 'Рішення',
                'code': 'resolution',
                'color': '#0891b2',  # Cyan
                'display_order': 4,
                'description': 'Official decision or resolution',
            },
            {
                'name': 'Ordinance',
                'name_local': 'Розпорядження',
                'code': 'ordinance',
                'color': '#059669',  # Green
                'display_order': 5,
                'description': 'Administrative order',
            },
            {
                'name': 'Guideline',
                'name_local': 'Методичні рекомендації',
                'code': 'guideline',
                'color': '#10b981',  # Emerald
                'display_order': 6,
                'description': 'Guidelines and recommendations',
            },
            {
                'name': 'Standard',
                'name_local': 'Стандарт',
                'code': 'standard',
                'color': '#f59e0b',  # Amber
                'display_order': 7,
                'description': 'Technical or industry standard',
            },
            {
                'name': 'Circular',
                'name_local': 'Лист',
                'code': 'circular',
                'color': '#ea580c',  # Orange
                'display_order': 8,
                'description': 'Circular letter or communication',
            },
            {
                'name': 'Instruction',
                'name_local': 'Інструкція',
                'code': 'instruction',
                'color': '#8b5cf6',  # Violet
                'display_order': 9,
                'description': 'Detailed instructions',
            },
            {
                'name': 'Other',
                'name_local': 'Інше',
                'code': 'other',
                'color': '#6b7280',  # Gray
                'display_order': 99,
                'description': 'Other types of requirements',
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for data in requirement_types_data:
            req_type, created = RequirementType.objects.update_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'name_local': data['name_local'],
                    'color': data['color'],
                    'display_order': data['display_order'],
                    'description': data['description'],
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {req_type.name} ({req_type.name_local})')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {req_type.name} ({req_type.name_local})')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'   ✅ Requirement Types: Created {created_count}, Updated {updated_count}'
            )
        )
        
        # Requirement Statuses
        self.stdout.write(self.style.SUCCESS('\n2️⃣ Loading Requirement Statuses...'))
        requirement_statuses_data = [
            {
                'name': 'Draft',
                'name_local': 'Чернетка',
                'code': 'draft',
                'color': '#6b7280',  # Gray
                'display_order': 1,
                'description': 'Requirement is in draft status',
            },
            {
                'name': 'Active',
                'name_local': 'Активна',
                'code': 'active',
                'color': '#059669',  # Green
                'display_order': 2,
                'description': 'Requirement is active and in force',
            },
            {
                'name': 'Under Review',
                'name_local': 'На розгляді',
                'code': 'under_review',
                'color': '#f59e0b',  # Amber
                'display_order': 3,
                'description': 'Requirement is under review',
            },
            {
                'name': 'Suspended',
                'name_local': 'Призупинена',
                'code': 'suspended',
                'color': '#ea580c',  # Orange
                'display_order': 4,
                'description': 'Requirement is temporarily suspended',
            },
            {
                'name': 'Archived',
                'name_local': 'Архівована',
                'code': 'archived',
                'color': '#475569',  # Slate
                'display_order': 5,
                'description': 'Requirement is archived and no longer in effect',
            },
            {
                'name': 'Cancelled',
                'name_local': 'Скасована',
                'code': 'cancelled',
                'color': '#dc2626',  # Red
                'display_order': 6,
                'description': 'Requirement has been cancelled',
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for data in requirement_statuses_data:
            status, created = RequirementStatus.objects.update_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'name_local': data['name_local'],
                    'color': data['color'],
                    'display_order': data['display_order'],
                    'description': data['description'],
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {status.name} ({status.name_local})')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {status.name} ({status.name_local})')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'   ✅ Requirement Statuses: Created {created_count}, Updated {updated_count}'
            )
        )
        
        # Requirement Priorities
        self.stdout.write(self.style.SUCCESS('\n3️⃣ Loading Requirement Priorities...'))
        requirement_priorities_data = [
            {
                'name': 'Low',
                'name_local': 'Низький',
                'code': 'low',
                'color': '#10b981',  # Green
                'display_order': 1,
                'description': 'Low priority requirement',
            },
            {
                'name': 'Medium',
                'name_local': 'Середній',
                'code': 'medium',
                'color': '#f59e0b',  # Amber
                'display_order': 2,
                'description': 'Medium priority requirement',
            },
            {
                'name': 'High',
                'name_local': 'Високий',
                'code': 'high',
                'color': '#ea580c',  # Orange
                'display_order': 3,
                'description': 'High priority requirement',
            },
            {
                'name': 'Critical',
                'name_local': 'Критичний',
                'code': 'critical',
                'color': '#dc2626',  # Red
                'display_order': 4,
                'description': 'Critical priority requirement - immediate action required',
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for data in requirement_priorities_data:
            priority, created = RequirementPriority.objects.update_or_create(
                code=data['code'],
                defaults={
                    'name': data['name'],
                    'name_local': data['name_local'],
                    'color': data['color'],
                    'display_order': data['display_order'],
                    'description': data['description'],
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {priority.name} ({priority.name_local})')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {priority.name} ({priority.name_local})')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'   ✅ Requirement Priorities: Created {created_count}, Updated {updated_count}\n'
            )
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                '\n✅ Successfully loaded all Requirement Dictionaries!'
            )
        )

