from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Setup all periodic tasks for both key cert reminders and API synchronization'

    def handle(self, *args, **kwargs):
        try:
            # First setup key certificate tasks
            self.stdout.write(self.style.NOTICE('Setting up key certificate periodic tasks...'))
            call_command('setup_periodic_tasks')
            
            # Then setup API sync tasks
            self.stdout.write(self.style.NOTICE('Setting up API synchronization periodic tasks...'))
            call_command('setup_api_sync_tasks')
            
            self.stdout.write(self.style.SUCCESS('Successfully setup all periodic tasks for the application'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error setting up periodic tasks: {str(e)}'))
            raise 