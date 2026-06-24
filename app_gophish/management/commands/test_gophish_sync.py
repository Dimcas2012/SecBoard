# app_gophish/management/commands/test_gophish_sync.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from app_gophish.models import GophishServer, GophishCampaign
from app_gophish.sync_utils import sync_gophish_data_direct
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test Gophish synchronization and debug campaign metrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--server-id',
            type=int,
            help='Specific server ID to sync (if not provided, syncs all servers)',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Enable debug logging',
        )

    def handle(self, *args, **options):
        if options['debug']:
            logging.getLogger('app_gophish').setLevel(logging.DEBUG)
        
        server_id = options.get('server_id')
        
        if server_id:
            try:
                server = GophishServer.objects.get(id=server_id)
                servers = [server]
            except GophishServer.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Server with ID {server_id} not found')
                )
                return
        else:
            servers = GophishServer.objects.filter(is_active=True)
        
        if not servers:
            self.stdout.write(
                self.style.WARNING('No active Gophish servers found')
            )
            return
        
        for server in servers:
            self.stdout.write(f'\n=== Syncing server: {server.name} ===')
            
            # Test connection first
            try:
                from app_gophish.api_client import gophish_manager
                client = gophish_manager.get_client(server)
                campaigns = client.get_campaigns()
                self.stdout.write(f'✅ Connection successful. Found {len(campaigns)} campaigns.')
                
                # Show sample campaign data
                if campaigns:
                    sample = campaigns[0]
                    self.stdout.write(f'Sample campaign data: {sample}')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Connection failed: {str(e)}')
                )
                continue
            
            # Run sync
            try:
                result = sync_gophish_data_direct(server.id, sync_type='full')
                
                if result['status'] == 'completed':
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Sync completed: {result["records_processed"]} processed, '
                            f'{result["records_created"]} created, '
                            f'{result["records_updated"]} updated'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Sync failed: {result.get("message", "Unknown error")}')
                    )
                    continue
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Sync error: {str(e)}')
                )
                continue
            
            # Show campaign metrics after sync
            campaigns = GophishCampaign.objects.filter(server=server)
            self.stdout.write(f'\nCampaign metrics after sync:')
            for campaign in campaigns:
                self.stdout.write(
                    f'  {campaign.name}: '
                    f'Status={campaign.status}, '
                    f'Targets={campaign.total_targets}, '
                    f'Emails Sent={campaign.emails_sent}, '
                    f'Emails Opened={campaign.emails_opened}, '
                    f'Credentials Submitted={campaign.credentials_submitted}'
                )
                
                # Show raw results data for debugging
                if campaign.results_data:
                    self.stdout.write(f'    Raw results data: {campaign.results_data}')
                else:
                    self.stdout.write(f'    No results data available')
        
        self.stdout.write('\n=== Sync test completed ===')
