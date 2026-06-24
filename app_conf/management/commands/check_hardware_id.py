# SecBoard\app_conf\management\commands\check_hardware_id.py
"""
Management command to check Hardware ID stability and components
"""

from django.core.management.base import BaseCommand
from app_conf.hardware_binding import HardwareFingerprint
from pathlib import Path
from django.conf import settings
import json


class Command(BaseCommand):
    help = 'Check Hardware ID stability and components'
    
    def handle(self, *args, **options):
        """Check Hardware ID and its components"""
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Hardware ID Stability Check'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Отримати компоненти
        components = HardwareFingerprint.get_hardware_components(include_server_id=True)  # Включаємо server_id для відображення
        fingerprint = HardwareFingerprint.generate_fingerprint()
        
        # Перевірити файли
        base_dir = getattr(settings, 'BASE_DIR', '')
        host_file = Path(base_dir) / '.secboard_first_host'
        
        self.stdout.write('\n' + self.style.WARNING('Hardware ID:'))
        self.stdout.write(self.style.SUCCESS(f"  {fingerprint}"))
        
        self.stdout.write('\n' + self.style.WARNING('Installation Files:'))
        self.stdout.write(f"  First Host File: {host_file}")
        if host_file.exists():
            try:
                with open(host_file, 'r') as f:
                    host = f.read().strip()
                    self.stdout.write(self.style.SUCCESS(f"    ✓ Exists: {host}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    ✗ Error reading: {str(e)}"))
        else:
            self.stdout.write(self.style.WARNING(f"    ✗ Not found (will use hostname or environment variable)"))
        
        self.stdout.write('\n' + self.style.WARNING('Key Components:'))
        self.stdout.write(f"  Server ID: {components.get('server_id', 'NOT FOUND')[:32]}...")
        self.stdout.write(f"    (HTTP_HOST from first request + Hardware ID)")
        self.stdout.write(f"  Hostname: {components.get('hostname', 'N/A')}")
        self.stdout.write(f"  FQDN: {components.get('fqdn', 'N/A')}")
        self.stdout.write(f"  Machine ID: {components.get('machine_id', 'N/A')[:32] if components.get('machine_id') else 'N/A'}...")
        self.stdout.write(f"  MAC Addresses: {len(components.get('mac_addresses', []))} interfaces")
        
        # Перевірити чи є активна ліцензія
        try:
            from app_conf.models import SecureLicense
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            if license_obj:
                self.stdout.write('\n' + self.style.WARNING('Active License:'))
                self.stdout.write(f"  License Hardware ID: {license_obj.hardware_fingerprint}")
                self.stdout.write(f"  Current Hardware ID: {fingerprint}")
                if license_obj.hardware_fingerprint == fingerprint:
                    self.stdout.write(self.style.SUCCESS("  ✓ Hardware IDs MATCH"))
                else:
                    self.stdout.write(self.style.ERROR("  ✗ Hardware IDs DO NOT MATCH!"))
                    self.stdout.write(self.style.ERROR("  This indicates a problem with component stability."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  Could not check license: {str(e)}"))

