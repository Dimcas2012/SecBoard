from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.utils.timezone import now
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from django.db import transaction


class Command(BaseCommand):
    help = 'Setup periodic tasks for scheduled reports execution'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                # Create interval schedule for checking scheduled reports (every minute)
                check_schedule, created = IntervalSchedule.objects.get_or_create(
                    every=1,
                    period=IntervalSchedule.MINUTES,
                )
                self.stdout.write(
                    self.style.SUCCESS('Created check_scheduled_reports schedule') if created
                    else self.style.WARNING('check_scheduled_reports schedule already exists')
                )

                # Create or update check_scheduled_reports task
                # First, try to get existing task and delete it to avoid conflicts
                try:
                    existing_task = PeriodicTask.objects.get(name='Check Scheduled Reports')
                    existing_task.delete()
                except PeriodicTask.DoesNotExist:
                    pass
                
                check_task = PeriodicTask.objects.create(
                    name='Check Scheduled Reports',
                    task='app_risk.tasks.check_scheduled_reports',
                    interval=check_schedule,
                    enabled=True,
                    description='Check for scheduled reports that need to be executed every minute',
                    last_run_at=now()
                )
                created = True

                self.stdout.write(
                    self.style.SUCCESS('Created check_scheduled_reports task') if created
                    else self.style.WARNING('Updated check_scheduled_reports task')
                )

                # Create cleanup schedule (daily at 2 AM)
                cleanup_schedule, created = CrontabSchedule.objects.get_or_create(
                    minute='0',
                    hour='2',
                    day_of_week='*',
                    day_of_month='*',
                    month_of_year='*',
                    timezone='Europe/Kiev'
                )
                self.stdout.write(
                    self.style.SUCCESS('Created cleanup schedule') if created
                    else self.style.WARNING('cleanup schedule already exists')
                )

                # Create or update cleanup task
                # First, try to get existing task and delete it to avoid conflicts
                try:
                    existing_cleanup_task = PeriodicTask.objects.get(name='Cleanup Old Report Files')
                    existing_cleanup_task.delete()
                except PeriodicTask.DoesNotExist:
                    pass
                
                cleanup_task = PeriodicTask.objects.create(
                    name='Cleanup Old Report Files',
                    task='app_risk.tasks.cleanup_old_report_files',
                    crontab=cleanup_schedule,
                    enabled=True,
                    description='Cleanup old report files daily at 2 AM',
                    last_run_at=now()
                )
                created = True

                self.stdout.write(
                    self.style.SUCCESS('Created cleanup task') if created
                    else self.style.WARNING('Updated cleanup task')
                )

                self.stdout.write(self.style.SUCCESS('Successfully setup all scheduled reports tasks'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error setting up scheduled reports tasks: {str(e)}'))
            raise
