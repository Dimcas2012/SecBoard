from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext as _
from app_risk.models import ScheduledReport
from app_risk.tasks import execute_scheduled_report, check_scheduled_reports


class Command(BaseCommand):
    help = 'Manually run scheduled reports (for testing)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--report-id',
            type=str,
            help='Run a specific report by ID',
        )
        parser.add_argument(
            '--check-all',
            action='store_true',
            help='Check all scheduled reports for execution',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all scheduled reports',
        )

    def handle(self, *args, **options):
        try:
            if options['list']:
                self.list_scheduled_reports()
            elif options['check_all']:
                self.check_all_reports()
            elif options['report_id']:
                self.run_specific_report(options['report_id'])
            else:
                self.stdout.write(
                    self.style.WARNING('Please specify --list, --check-all, or --report-id')
                )
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error running scheduled reports: {str(e)}'))
            raise

    def list_scheduled_reports(self):
        """List all scheduled reports"""
        self.stdout.write(self.style.NOTICE('Listing all scheduled reports:'))
        
        reports = ScheduledReport.objects.all().order_by('name')
        
        if not reports:
            self.stdout.write(self.style.WARNING('No scheduled reports found'))
            return
        
        for report in reports:
            status_color = self.style.SUCCESS if report.status == 'active' else self.style.WARNING
            self.stdout.write(
                f"ID: {report.id} | "
                f"Name: {report.name} | "
                f"Status: {status_color(report.status)} | "
                f"Frequency: {report.frequency} | "
                f"Next Run: {report.next_run.strftime('%Y-%m-%d %H:%M') if report.next_run else 'Not scheduled'} | "
                f"Last Run: {report.last_run.strftime('%Y-%m-%d %H:%M') if report.last_run else 'Never'}"
            )

    def check_all_reports(self):
        """Check all reports for execution"""
        self.stdout.write(self.style.NOTICE('Checking all scheduled reports for execution...'))
        
        # Run the check task synchronously
        result = check_scheduled_reports.apply()
        
        self.stdout.write(self.style.SUCCESS(f'Check completed: {result.result}'))

    def run_specific_report(self, report_id):
        """Run a specific report by ID"""
        try:
            report = ScheduledReport.objects.get(id=report_id)
            self.stdout.write(
                self.style.NOTICE(f'Running scheduled report: {report.name}')
            )
            
            # Run the execution task synchronously
            result = execute_scheduled_report.apply(args=[report_id])
            
            self.stdout.write(self.style.SUCCESS(f'Execution completed: {result.result}'))
            
        except ScheduledReport.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Scheduled report with ID {report_id} not found')
            ) 