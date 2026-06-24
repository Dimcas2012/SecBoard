# app_keycert/management/commands/setup_periodic_tasks.py
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
from django.db import transaction

from django.core.management.base import BaseCommand
from django.utils.timezone import now
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
from django.db import transaction


class Command(BaseCommand):
    help = 'Setup periodic tasks for key certificate reminders'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                # Create check_reminders schedule (every 30 minutes)
                check_schedule, created = IntervalSchedule.objects.get_or_create(
                    every=30,
                    period=IntervalSchedule.MINUTES,
                )
                self.stdout.write(
                    self.style.SUCCESS('Created check_reminders schedule') if created
                    else self.style.WARNING('check_reminders schedule already exists')
                )

                # Create or update check_reminders task
                check_task, created = PeriodicTask.objects.update_or_create(
                    name='Check Certificate Reminders',
                    defaults={
                        'task': 'app_keycert.tasks.check_reminders',
                        'interval': check_schedule,
                        'enabled': True,
                        'description': 'Check for certificate reminders every 30 minutes',
                        'last_run_at': now()  # Set last_run_at to now
                    }
                )

                self.stdout.write(
                    self.style.SUCCESS('Created check_reminders task') if created
                    else self.style.WARNING('Updated check_reminders task')
                )

                # Create cleanup schedule (midnight)
                cleanup_schedule, created = CrontabSchedule.objects.get_or_create(
                    minute='0',
                    hour='0',
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
                cleanup_task, created = PeriodicTask.objects.update_or_create(
                    name='Cleanup Old Reminders',
                    defaults={
                        'task': 'app_keycert.tasks.cleanup_old_reminders',
                        'crontab': cleanup_schedule,
                        'enabled': True,
                        'description': 'Cleanup old reminders daily at midnight',
                        'last_run_at': now()  # Set last_run_at to now
                    }
                )

                self.stdout.write(
                    self.style.SUCCESS('Created cleanup task') if created
                    else self.style.WARNING('Updated cleanup task')
                )

                self.stdout.write(self.style.SUCCESS('Successfully setup all periodic tasks'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error setting up periodic tasks: {str(e)}'))
            raise