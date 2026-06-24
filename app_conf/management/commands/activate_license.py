# SecBoard\app_conf\management\commands\activate_license.py
"""
Management command to activate SecBoard license
"""

from django.core.management.base import BaseCommand, CommandError
from app_conf.license_manager import LicenseActivator


class Command(BaseCommand):
    help = 'Activate SecBoard license'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'license_key',
            type=str,
            help='License key to activate'
        )
    
    def handle(self, *args, **options):
        """Activate license with provided key"""
        
        license_key = options['license_key']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SecBoard License Activation'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        self.stdout.write('\nActivating license...')
        
        # Активація ліцензії
        success, license_obj, error_message = LicenseActivator.activate_license(
            license_key,
            request=None
        )
        
        if success and license_obj:
            # Отримання даних ліцензії
            license_data = license_obj.get_license_data()
            
            self.stdout.write('\n' + self.style.SUCCESS('[OK] License activated successfully!'))
            self.stdout.write('\n' + self.style.WARNING('License Details:'))
            self.stdout.write(f"  Company: {license_data.get('company', 'N/A')}")
            self.stdout.write(f"  Expiration Date: {license_data.get('expiration_date', 'N/A')}")
            self.stdout.write(f"  Maximum Users: {license_data.get('max_users', 'N/A')}")
            
            # Відображення увімкнених модулів
            modules = license_data.get('modules', {})
            enabled_modules = [k for k, v in modules.items() if v]
            
            if enabled_modules:
                self.stdout.write(f"\n  Enabled Modules:")
                for module in enabled_modules:
                    self.stdout.write(f"    - {module}")
            
            self.stdout.write('\n' + self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS('License is now active. Please restart the server.'))
            self.stdout.write(self.style.SUCCESS('=' * 70))
            
        else:
            self.stdout.write('\n' + self.style.ERROR('[X] License activation failed!'))
            self.stdout.write(self.style.ERROR(f"Error: {error_message}"))
            self.stdout.write('\n' + self.style.WARNING('Please check:'))
            self.stdout.write('  - License key is correct (copy-paste entire key)')
            self.stdout.write('  - License is intended for this server (Hardware ID match)')
            self.stdout.write('  - License has not expired')
            self.stdout.write('\nFor support, contact: support@secboard.online')
            self.stdout.write(self.style.ERROR('=' * 70))
            
            raise CommandError('License activation failed')

