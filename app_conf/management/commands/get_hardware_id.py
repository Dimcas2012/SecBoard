# SecBoard\app_conf\management\commands\get_hardware_id.py
"""
Management command to get hardware fingerprint for license activation
"""

from django.core.management.base import BaseCommand
from app_conf.hardware_binding import HardwareFingerprint


class Command(BaseCommand):
    help = 'Get hardware fingerprint for license activation'
    
    def handle(self, *args, **options):
        """Generate and display hardware fingerprint"""
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SecBoard Hardware Fingerprint'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Отримання детальної інформації
        info = HardwareFingerprint.get_fingerprint_info()
        
        # Відображення Hardware ID
        self.stdout.write('\n' + self.style.WARNING('Hardware ID (send this to SecBoard support):'))
        self.stdout.write(self.style.SUCCESS(f"  {info['fingerprint']}"))
        
        # Відображення компонентів системи
        self.stdout.write('\n' + self.style.WARNING('System Components:'))
        components = info['components']
        self.stdout.write(f"  Hostname: {components['hostname']}")
        self.stdout.write(f"  Platform: {components['platform']}")
        self.stdout.write(f"  Architecture: {components['machine']}")
        self.stdout.write(f"  CPU ID: {components['cpu_id']}")
        self.stdout.write(f"  Network Interfaces: {components['mac_addresses_count']}")
        self.stdout.write(f"  Has Disk Serial: {'Yes' if components['has_disk_serial'] else 'No'}")
        self.stdout.write(f"  Has System UUID: {'Yes' if components['has_system_uuid'] else 'No'}")
        
        # Інструкції
        self.stdout.write('\n' + self.style.WARNING('Next Steps:'))
        self.stdout.write('  1. Send the Hardware ID above to SecBoard support')
        self.stdout.write('  2. Wait for your license key to be generated')
        self.stdout.write('  3. Activate the license using:')
        self.stdout.write(self.style.SUCCESS('     python manage.py activate_license <YOUR_LICENSE_KEY>'))
        
        self.stdout.write('\n' + self.style.SUCCESS('=' * 70))

