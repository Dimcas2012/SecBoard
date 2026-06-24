# Management command to manually send heartbeat to license server
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext as _
from app_conf.models import SecureLicense
from app_conf.license_server_api import LicenseServerAPI
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manually send heartbeat to license server'

    def add_arguments(self, parser):
        parser.add_argument(
            '--license-id',
            type=int,
            help='Send heartbeat for specific license ID (if not specified, uses active license)',
        )

    def handle(self, *args, **options):
        try:
            # Get license
            if options.get('license_id'):
                license_obj = SecureLicense.objects.get(pk=options['license_id'])
            else:
                license_obj = SecureLicense.objects.filter(is_active=True).first()
            
            if not license_obj:
                self.stdout.write(
                    self.style.ERROR('No active license found. Use --license-id to specify a license.')
                )
                return
            
            self.stdout.write(f'Sending heartbeat for license ID: {license_obj.id}')
            self.stdout.write(f'License key: {license_obj.license_key[:50]}...')
            
            # Send heartbeat
            success, response_data = LicenseServerAPI.send_heartbeat(
                license_obj.license_key
            )
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS('✓ Heartbeat sent successfully!')
                )
                if response_data:
                    self.stdout.write(f'Response: {response_data}')
                
                # Show updated license info
                license_obj.refresh_from_db()
                if license_obj.heartbeats.exists():
                    last_hb = license_obj.heartbeats.order_by('-timestamp').first()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Last heartbeat: {last_hb.timestamp.strftime("%Y-%m-%d %H:%M:%S")}'
                        )
                    )
            else:
                self.stdout.write(
                    self.style.ERROR('✗ Failed to send heartbeat')
                )
                if response_data:
                    error_msg = response_data.get('message', 'Unknown error')
                    self.stdout.write(
                        self.style.ERROR(f'Error: {error_msg}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING('License server may be unreachable (offline mode)')
                    )
                    
        except SecureLicense.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'License with ID {options.get("license_id")} not found.')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error sending heartbeat: {str(e)}')
            )
            logger.exception("Error in send_heartbeat command")

