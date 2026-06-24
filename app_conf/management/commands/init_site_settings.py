#  SecBoard\SecBoard\app_conf\management\commands\init_site_settings.py
from django.core.management.base import BaseCommand
from app_conf.models import SiteSettings


class Command(BaseCommand):
    help = 'Initialize Site Settings with default values'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-type',
            type=str,
            choices=['prod', 'test', 'demo'],
            default='prod',
            help='Set project type (prod, test, demo)'
        )
        parser.add_argument(
            '--site-name',
            type=str,
            default='SecBoard',
            help='Set site name'
        )

    def handle(self, *args, **options):
        project_type = options['project_type']
        site_name = options['site_name']
        
        settings, created = SiteSettings.objects.get_or_create(pk=1)
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created new SiteSettings'))
        else:
            self.stdout.write(self.style.WARNING('SiteSettings already exists, updating...'))
        
        settings.project_type = project_type
        settings.site_name = site_name
        settings.save()
        
        self.stdout.write(self.style.SUCCESS(f'Site Settings configured:'))
        self.stdout.write(f'  Project Type: {settings.get_project_type_display()}')
        self.stdout.write(f'  Site Name: {settings.site_name}')
        self.stdout.write(f'  Display Name: {settings.get_project_display_name()}')
        self.stdout.write(f'  Navbar Color: {settings.get_navbar_color()}')
        self.stdout.write(self.style.SUCCESS('\n✓ Configuration complete!'))
        
        if project_type == 'demo':
            self.stdout.write(self.style.SUCCESS('\n🟢 Demo mode activated - Green navbar'))
        elif project_type == 'test':
            self.stdout.write(self.style.WARNING('\n🔴 Test mode activated - Red navbar'))
        else:
            self.stdout.write(self.style.SUCCESS('\n🔵 Production mode - Default navbar'))

