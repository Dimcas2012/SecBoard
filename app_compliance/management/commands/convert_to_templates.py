from django.core.management.base import BaseCommand
from app_compliance.models import ComplianceFramework


class Command(BaseCommand):
    help = 'Convert existing frameworks to template system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--framework-id',
            type=int,
            help='Convert specific framework to template'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Convert all frameworks without company to templates'
        )

    def handle(self, *args, **options):
        if options['framework_id']:
            self.convert_framework(options['framework_id'])
        elif options['all']:
            self.convert_all()
        else:
            self.stdout.write(self.style.WARNING(
                'Please specify --framework-id ID or --all'
            ))

    def convert_framework(self, framework_id):
        """Convert specific framework to template"""
        try:
            framework = ComplianceFramework.objects.get(id=framework_id)
            
            if framework.is_template:
                self.stdout.write(self.style.WARNING(
                    f'Framework {framework.name} is already a template'
                ))
                return
            
            # Mark as template
            framework.is_template = True
            framework.company = None  # Templates don't have companies
            framework.save()
            
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Converted {framework.name} to template (ID: {framework.id})'
            ))
            
        except ComplianceFramework.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'Framework with ID {framework_id} not found'
            ))

    def convert_all(self):
        """Convert all frameworks without company to templates"""
        frameworks = ComplianceFramework.objects.filter(
            company__isnull=True,
            is_template=False
        )
        
        count = 0
        for framework in frameworks:
            framework.is_template = True
            framework.save()
            count += 1
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Converted {framework.name} to template (ID: {framework.id})'
            ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n[DONE] Converted {count} frameworks to templates'
        ))

