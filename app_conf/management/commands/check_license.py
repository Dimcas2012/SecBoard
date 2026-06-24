# SecBoard\app_conf\management\commands\check_license.py
"""
Management command to check license status
"""

from django.core.management.base import BaseCommand
from app_conf.license_manager import LicenseStatusChecker, LicenseValidator
from app_conf.models import SecureLicense


class Command(BaseCommand):
    help = 'Check SecBoard license status'
    
    def handle(self, *args, **options):
        """Check and display license status"""
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SecBoard License Status'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Отримання статусу ліцензії
        status = LicenseStatusChecker.get_license_status()
        
        if status['valid']:
            self.stdout.write('\n' + self.style.SUCCESS('[OK] License Status: VALID'))
            
            # Деталі ліцензії
            self.stdout.write('\n' + self.style.WARNING('License Details:'))
            self.stdout.write(f"  Company: {status.get('company', 'N/A')}")
            self.stdout.write(f"  Expiration Date: {status.get('expiration_date', 'N/A')}")
            self.stdout.write(f"  Days Remaining: {status.get('days_remaining', 0)}")
            self.stdout.write(f"  Max Users: {status.get('max_users', 0)}")
            self.stdout.write(f"  Current Active Users: {status.get('current_users', 0)}")
            
            # Статус
            license_status = status.get('status', 'UNKNOWN')
            if license_status == 'ACTIVE':
                status_msg = self.style.SUCCESS(f"  Status: {license_status}")
            elif license_status in ['EXPIRING', 'EXPIRING_SOON']:
                status_msg = self.style.WARNING(f"  Status: {license_status}")
            else:
                status_msg = self.style.ERROR(f"  Status: {license_status}")
            
            self.stdout.write(status_msg)
            
            # Увімкнені модулі
            enabled_modules = status.get('enabled_modules', [])
            if enabled_modules:
                self.stdout.write('\n' + self.style.WARNING('Enabled Modules:'))
                for module in enabled_modules:
                    self.stdout.write(f"  - {module['name_uk']} ({module['key']})")
            
            # Попередження якщо ліцензія скоро закінчиться
            days_remaining = status.get('days_remaining', 0)
            if days_remaining <= 30:
                self.stdout.write('\n' + self.style.WARNING('[!] WARNING:'))
                if days_remaining <= 0:
                    self.stdout.write(self.style.ERROR('  License has EXPIRED!'))
                elif days_remaining <= 7:
                    self.stdout.write(self.style.ERROR(f'  License expires in {days_remaining} days!'))
                else:
                    self.stdout.write(self.style.WARNING(f'  License expires in {days_remaining} days'))
                self.stdout.write('  Please contact support to renew: support@secboard.online')
            
        else:
            self.stdout.write('\n' + self.style.ERROR('[X] License Status: INVALID'))
            self.stdout.write(self.style.ERROR(f"Error: {status.get('error', 'Unknown error')}"))
            self.stdout.write(self.style.ERROR(f"Status: {status.get('status', 'UNKNOWN')}"))
            
            self.stdout.write('\n' + self.style.WARNING('Possible Issues:'))
            self.stdout.write('  - No license activated')
            self.stdout.write('  - License has expired')
            self.stdout.write('  - Hardware mismatch (server changed)')
            self.stdout.write('  - License validation failed')
            
            self.stdout.write('\n' + self.style.WARNING('Solutions:'))
            self.stdout.write('  1. Check if license is activated:')
            self.stdout.write(self.style.SUCCESS('     python manage.py check_license'))
            self.stdout.write('  2. Activate license if needed:')
            self.stdout.write(self.style.SUCCESS('     python manage.py activate_license <LICENSE_KEY>'))
            self.stdout.write('  3. Contact support: support@secboard.online')
        
        self.stdout.write('\n' + self.style.SUCCESS('=' * 70))

