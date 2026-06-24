# SecBoard\app_conf\management\commands\test_license_server.py
"""
Management command to test connection to license server
"""

from django.core.management.base import BaseCommand
from app_conf.license_server_api import LicenseServerAPI


class Command(BaseCommand):
    help = 'Test connection to SecBoard license server'
    
    def handle(self, *args, **options):
        """Test license server connection"""
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SecBoard License Server Connection Test'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        self.stdout.write('\nTesting connection to license server...')
        
        # Тест з'єднання
        success, message = LicenseServerAPI.test_connection()
        
        if success:
            self.stdout.write('\n' + self.style.SUCCESS('[OK] Connection successful!'))
            self.stdout.write(f"Message: {message}")
            self.stdout.write('\nLicense server is reachable.')
            self.stdout.write('Online license validation is available.')
            
        else:
            self.stdout.write('\n' + self.style.WARNING('[X] Connection failed'))
            self.stdout.write(f"Message: {message}")
            self.stdout.write('\n' + self.style.WARNING('Note:'))
            self.stdout.write('  The platform will work in offline mode.')
            self.stdout.write('  Offline grace period applies (7 days by default).')
            self.stdout.write('\nPossible issues:')
            self.stdout.write('  - No internet connection')
            self.stdout.write('  - Firewall blocking outbound connections')
            self.stdout.write('  - License server is down (rare)')
            
        self.stdout.write('\n' + self.style.SUCCESS('=' * 70))

