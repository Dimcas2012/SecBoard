from django.core.management.base import BaseCommand
from app_compliance.models import ComplianceFramework


class Command(BaseCommand):
    help = 'Sync framework instances from their templates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--template-id',
            type=int,
            help='Sync all instances of specific template'
        )
        parser.add_argument(
            '--instance-id',
            type=int,
            help='Sync specific instance'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all instances from all templates'
        )

    def handle(self, *args, **options):
        if options['instance_id']:
            self.sync_instance(options['instance_id'])
        elif options['template_id']:
            self.sync_template_instances(options['template_id'])
        elif options['all']:
            self.sync_all()
        else:
            self.stdout.write(self.style.WARNING(
                'Please specify --instance-id, --template-id, or --all'
            ))

    def sync_instance(self, instance_id):
        """Sync specific instance from its template"""
        try:
            instance = ComplianceFramework.objects.get(id=instance_id)
        except ComplianceFramework.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'Instance with ID {instance_id} not found'
            ))
            return
        
        if instance.is_template:
            self.stdout.write(self.style.ERROR(
                f'{instance.name} is a template, not an instance!'
            ))
            return
        
        if not instance.template:
            self.stdout.write(self.style.ERROR(
                f'{instance.name} is not linked to a template!'
            ))
            return
        
        # Sync from template
        if instance.sync_from_template():
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Synced {instance.name} for {instance.company.name} from template'
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f'[ERROR] Failed to sync {instance.name}'
            ))

    def sync_template_instances(self, template_id):
        """Sync all instances of specific template"""
        try:
            template = ComplianceFramework.objects.get(id=template_id)
        except ComplianceFramework.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'Template with ID {template_id} not found'
            ))
            return
        
        if not template.is_template:
            self.stdout.write(self.style.ERROR(
                f'{template.name} is not a template!'
            ))
            return
        
        instances = ComplianceFramework.objects.filter(template=template)
        
        if not instances.exists():
            self.stdout.write(self.style.WARNING(
                f'No instances found for template {template.name}'
            ))
            return
        
        self.stdout.write(f'Syncing instances of {template.name} {template.version}')
        self.stdout.write('='*60)
        
        count = 0
        for instance in instances:
            if instance.sync_from_template():
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Synced for {instance.company.name if instance.company else "Unknown"}'
                ))
                count += 1
            else:
                self.stdout.write(self.style.ERROR(
                    f'[ERROR] Failed to sync for {instance.company.name if instance.company else "Unknown"}'
                ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n[DONE] Synced {count} instances'
        ))

    def sync_all(self):
        """Sync all instances from all templates"""
        instances = ComplianceFramework.objects.filter(
            is_template=False,
            template__isnull=False
        )
        
        if not instances.exists():
            self.stdout.write(self.style.WARNING('No instances found'))
            return
        
        self.stdout.write('Syncing all instances from templates')
        self.stdout.write('='*60)
        
        count = 0
        for instance in instances:
            if instance.sync_from_template():
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Synced {instance.name} for {instance.company.name if instance.company else "Unknown"}'
                ))
                count += 1
            else:
                self.stdout.write(self.style.ERROR(
                    f'[ERROR] Failed to sync {instance.name}'
                ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n[DONE] Synced {count} instances'
        ))

