from django.core.management.base import BaseCommand
from app_conf.models import Company
from app_compliance.models import ComplianceFramework


class Command(BaseCommand):
    help = 'Apply framework template to company/companies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--template-id',
            type=int,
            required=True,
            help='Template framework ID'
        )
        parser.add_argument(
            '--company-id',
            type=int,
            help='Company ID to apply template to'
        )
        parser.add_argument(
            '--all-companies',
            action='store_true',
            help='Apply template to all companies'
        )

    def handle(self, *args, **options):
        template_id = options['template_id']
        
        # Get template
        try:
            template = ComplianceFramework.objects.get(id=template_id)
        except ComplianceFramework.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'Template with ID {template_id} not found'
            ))
            return
        
        if not template.is_template:
            self.stdout.write(self.style.ERROR(
                f'Framework {template.name} is not a template!'
            ))
            return
        
        self.stdout.write(f'Template: {template.name} {template.version}')
        self.stdout.write('='*60)
        
        # Apply to specific company or all
        if options['company_id']:
            self.apply_to_company(template, options['company_id'])
        elif options['all_companies']:
            self.apply_to_all(template)
        else:
            self.stdout.write(self.style.WARNING(
                'Please specify --company-id ID or --all-companies'
            ))

    def apply_to_company(self, template, company_id):
        """Apply template to specific company"""
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'Company with ID {company_id} not found'
            ))
            return
        
        # Check if already exists
        existing = ComplianceFramework.objects.filter(
            company=company,
            template=template
        ).first()
        
        if existing:
            self.stdout.write(self.style.WARNING(
                f'Company {company.name} already has this framework applied'
            ))
            return
        
        # Apply template
        instance = template.apply_to_company(company)
        self.stdout.write(self.style.SUCCESS(
            f'[OK] Applied {template.name} to {company.name} (ID: {instance.id})'
        ))

    def apply_to_all(self, template):
        """Apply template to all companies"""
        companies = Company.objects.all()
        
        if not companies.exists():
            self.stdout.write(self.style.WARNING('No companies found'))
            return
        
        count = 0
        skipped = 0
        
        for company in companies:
            # Check if already exists
            existing = ComplianceFramework.objects.filter(
                company=company,
                template=template
            ).first()
            
            if existing:
                self.stdout.write(self.style.WARNING(
                    f'[SKIP] {company.name} already has this framework'
                ))
                skipped += 1
                continue
            
            # Apply template
            instance = template.apply_to_company(company)
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Applied {template.name} to {company.name} (ID: {instance.id})'
            ))
            count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'\n[DONE] Applied to {count} companies, skipped {skipped}'
        ))

