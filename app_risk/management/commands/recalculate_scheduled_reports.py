from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from app_risk.models import ScheduledReport


class Command(BaseCommand):
    help = 'Recalculate next_run for all active scheduled reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--report-name',
            type=str,
            help='Recalculate only for a specific report (by name)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Recalculate for all reports (including inactive)',
        )

    def handle(self, *args, **options):
        try:
            if options['report_name']:
                reports = ScheduledReport.objects.filter(name__icontains=options['report_name'])
                self.stdout.write(f"Recalculating next_run for reports matching: {options['report_name']}")
            elif options['all']:
                reports = ScheduledReport.objects.all()
                self.stdout.write("Recalculating next_run for all reports")
            else:
                reports = ScheduledReport.objects.filter(status='active')
                self.stdout.write("Recalculating next_run for active reports only")
            
            count = 0
            for report in reports:
                try:
                    old_next_run = report.next_run
                    # Trigger recalculation by calling save() which calls calculate_next_run()
                    report.save()
                    new_next_run = report.next_run
                    
                    if old_next_run != new_next_run:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ {report.name}: {old_next_run} → {new_next_run}"
                            )
                        )
                    else:
                        self.stdout.write(
                            f"  {report.name}: {new_next_run} (unchanged)"
                        )
                    count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Error recalculating {report.name}: {str(e)}")
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully recalculated {count} report(s)')
            )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            raise

