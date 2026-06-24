from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.utils.timezone import now
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from django.db import transaction

class Command(BaseCommand):
    help = 'Setup periodic tasks for API synchronization'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                # Create heartbeat schedule (runs every minute)
                heartbeat_schedule, created = CrontabSchedule.objects.get_or_create(
                    minute='*',
                    hour='*',
                    day_of_week='*',
                    day_of_month='*',
                    month_of_year='*',
                )
                self.stdout.write(
                    self.style.SUCCESS('Created beat_heartbeat schedule') if created
                    else self.style.WARNING('beat_heartbeat schedule already exists')
                )

                # Create or update beat_heartbeat task
                heartbeat_task, created = PeriodicTask.objects.update_or_create(
                    name='Beat Heartbeat',
                    defaults={
                        'task': 'app_access.tasks.beat_heartbeat',
                        'crontab': heartbeat_schedule,
                        'enabled': True,
                        'description': 'Updates Redis with current timestamp every minute to verify Beat is running',
                        'last_run_at': now()
                    }
                )

                self.stdout.write(
                    self.style.SUCCESS('Created beat_heartbeat task') if created
                    else self.style.WARNING('Updated beat_heartbeat task')
                )

                # Create a default daily API sync task schedule
                daily_sync_schedule, created = CrontabSchedule.objects.get_or_create(
                    minute='0',
                    hour='3',  # Run at 3 AM
                    day_of_week='*',
                    day_of_month='*',
                    month_of_year='*',
                )
                self.stdout.write(
                    self.style.SUCCESS('Created daily API sync schedule') if created
                    else self.style.WARNING('daily API sync schedule already exists')
                )

                # Create hourly interval schedules for different cycles
                hourly_cycles = [1, 2, 3, 4, 6, 8, 12]
                hourly_schedules = {}
                
                for cycle in hourly_cycles:
                    hourly_schedule, created = IntervalSchedule.objects.get_or_create(
                        every=cycle,
                        period=IntervalSchedule.HOURS
                    )
                    hourly_schedules[cycle] = hourly_schedule
                    self.stdout.write(
                        self.style.SUCCESS(f'Created {cycle}-hour interval schedule') if created
                        else self.style.WARNING(f'{cycle}-hour interval schedule already exists')
                    )

                # Setup tasks for any existing schedules in the database
                from app_access.models import ScheduledSync
                sync_schedules = ScheduledSync.objects.filter(is_active=True)
                
                for schedule in sync_schedules:
                    try:
                        schedule.update_or_create_task()
                        self.stdout.write(self.style.SUCCESS(
                            f'Updated periodic task for {schedule.name} ({schedule.get_frequency_display()})'
                            + (f" (every {schedule.hourly_cycle} hours)" if schedule.frequency == 'hourly' else "")
                        ))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f'Error updating task for {schedule.name}: {str(e)}'
                        ))

                self.stdout.write(self.style.SUCCESS('Successfully setup all API sync periodic tasks'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error setting up API sync periodic tasks: {str(e)}'))
            raise 