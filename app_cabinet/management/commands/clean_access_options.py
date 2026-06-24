from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from app_cabinet.models import AccessOptions


class Command(BaseCommand):
    help = 'Clean up AccessOptions records and handle deletion issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-group',
            type=str,
            help='Delete AccessOptions for specific group name'
        )
        parser.add_argument(
            '--list-all',
            action='store_true',
            help='List all AccessOptions records'
        )
        parser.add_argument(
            '--delete-test-groups',
            action='store_true',
            help='Delete all test groups (groups starting with "Test")'
        )

    def handle(self, *args, **options):
        if options['list_all']:
            self.list_all_access_options()
        
        if options['delete_group']:
            self.delete_group_access_options(options['delete_group'])
        
        if options['delete_test_groups']:
            self.delete_test_groups()

    def list_all_access_options(self):
        """List all AccessOptions records"""
        self.stdout.write(self.style.SUCCESS('AccessOptions records:'))
        
        access_options = AccessOptions.objects.all().select_related('group')
        
        if not access_options.exists():
            self.stdout.write(self.style.WARNING('No AccessOptions records found.'))
            return
        
        for option in access_options:
            companies = ', '.join([c.name for c in option.companies.all()])
            self.stdout.write(f'ID: {option.id}, Group: {option.group.name}, Companies: {companies}')

    def delete_group_access_options(self, group_name):
        """Delete AccessOptions for a specific group"""
        try:
            group = Group.objects.get(name=group_name)
            access_options = AccessOptions.objects.filter(group=group)
            
            if access_options.exists():
                count = access_options.count()
                access_options.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully deleted {count} AccessOptions record(s) for group "{group_name}"')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'No AccessOptions records found for group "{group_name}"')
                )
                
        except Group.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Group "{group_name}" does not exist')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error deleting AccessOptions for group "{group_name}": {str(e)}')
            )

    def delete_test_groups(self):
        """Delete all test groups and their AccessOptions"""
        try:
            # Find all groups starting with "Test"
            test_groups = Group.objects.filter(name__startswith='Test')
            
            if not test_groups.exists():
                self.stdout.write(self.style.WARNING('No test groups found.'))
                return
            
            total_deleted = 0
            for group in test_groups:
                # Delete AccessOptions first
                access_options = AccessOptions.objects.filter(group=group)
                if access_options.exists():
                    count = access_options.count()
                    access_options.delete()
                    total_deleted += count
                    self.stdout.write(f'Deleted {count} AccessOptions for group "{group.name}"')
                
                # Delete the group itself
                group.delete()
                self.stdout.write(f'Deleted group "{group.name}"')
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {total_deleted} AccessOptions records and all test groups')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error deleting test groups: {str(e)}')
            ) 