#  SecBoard\SecBoard\app_gdpr\management\commands\generate_gdpr_report.py

from django.core.management.base import BaseCommand
from app_gdpr.utils import generate_compliance_report_data
from app_conf.models import Company
import json


class Command(BaseCommand):
    help = 'Generate GDPR compliance report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=int,
            help='Company ID to generate report for',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='console',
            help='Output format: console or json',
        )

    def handle(self, *args, **options):
        company_id = options.get('company')
        output_format = options.get('output')
        
        company = None
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Generating report for company: {company.name}'
                    )
                )
            except Company.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'Company with ID {company_id} not found'
                    )
                )
                return
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    'Generating report for all companies'
                )
            )
        
        # Генеруємо звіт
        report_data = generate_compliance_report_data(company=company)
        
        if output_format == 'json':
            # Конвертуємо datetime об'єкти в строки для JSON
            def convert_datetime(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return obj
            
            print(json.dumps(report_data, indent=2, default=convert_datetime))
        else:
            # Console output
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('GDPR COMPLIANCE REPORT'))
            self.stdout.write('='*60 + '\n')
            
            self.stdout.write(f"Company: {report_data['company']}")
            self.stdout.write(f"Report Date: {report_data['report_date']}\n")
            
            self.stdout.write(self.style.SUCCESS('\nData Subjects:'))
            self.stdout.write(f"  Total: {report_data['data_subjects']['total']}")
            self.stdout.write(f"  With Active Consent: {report_data['data_subjects']['with_active_consent']}")
            self.stdout.write(f"  Anonymized: {report_data['data_subjects']['anonymized']}")
            
            self.stdout.write(self.style.SUCCESS('\nConsents:'))
            self.stdout.write(f"  Total: {report_data['consents']['total']}")
            self.stdout.write(f"  Active: {report_data['consents']['active']}")
            self.stdout.write(f"  Withdrawn: {report_data['consents']['withdrawn']}")
            
            self.stdout.write(self.style.SUCCESS('\nData Subject Requests:'))
            self.stdout.write(f"  Total: {report_data['dsr']['total']}")
            self.stdout.write(f"  Pending: {report_data['dsr']['pending']}")
            self.stdout.write(f"  Completed: {report_data['dsr']['completed']}")
            self.stdout.write(
                self.style.WARNING(f"  Overdue: {report_data['dsr']['overdue']}")
            )
            
            self.stdout.write(self.style.SUCCESS('\nData Breaches:'))
            self.stdout.write(f"  Total: {report_data['breaches']['total']}")
            self.stdout.write(f"  Critical: {report_data['breaches']['by_severity']['critical']}")
            self.stdout.write(f"  High: {report_data['breaches']['by_severity']['high']}")
            self.stdout.write(f"  Reported to Authority: {report_data['breaches']['reported_to_authority']}")
            if report_data['breaches']['notification_overdue'] > 0:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Notification Overdue: {report_data['breaches']['notification_overdue']}"
                    )
                )
            
            self.stdout.write(self.style.SUCCESS('\nProcessing Activities:'))
            self.stdout.write(f"  Total: {report_data['processing_activities']['total']}")
            self.stdout.write(f"  Active: {report_data['processing_activities']['active']}")
            
            self.stdout.write(self.style.SUCCESS('\nDPIA Assessments:'))
            self.stdout.write(f"  Total: {report_data['dpias']['total']}")
            self.stdout.write(f"  Approved: {report_data['dpias']['approved']}")
            
            self.stdout.write('\n' + '='*60)
        
        self.stdout.write(
            self.style.SUCCESS('\nReport generated successfully')
        )

