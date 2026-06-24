from django.core.management.base import BaseCommand
from app_soc.models import WazuhFIMAlert, WebhookClient


class Command(BaseCommand):
    help = 'Update existing FIM alerts to link them with webhook clients'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all alerts without client links
        alerts_without_client = WazuhFIMAlert.objects.filter(client__isnull=True)
        total_alerts = alerts_without_client.count()
        
        self.stdout.write(f"Found {total_alerts} alerts without client links")
        
        if total_alerts == 0:
            self.stdout.write(self.style.SUCCESS("All alerts already have client links!"))
            return
        
        # Get all enabled webhook clients
        clients = WebhookClient.objects.filter(enabled=True)
        if not clients.exists():
            self.stdout.write(self.style.WARNING("No enabled webhook clients found!"))
            return
        
        self.stdout.write(f"Found {clients.count()} enabled webhook clients:")
        for client in clients:
            self.stdout.write(f"  - {client.name} ({client.ip_address}:{client.port})")
        
        updated_count = 0
        
        for alert in alerts_without_client:
            # Try to find a client by agent IP
            matching_client = clients.filter(ip_address=alert.agent_ip).first()
            
            if not matching_client:
                # If no exact match, use the first enabled client as fallback
                matching_client = clients.first()
                self.stdout.write(
                    f"Alert {alert.alert_id}: No exact IP match for {alert.agent_ip}, "
                    f"using fallback client {matching_client.name}"
                )
            else:
                self.stdout.write(
                    f"Alert {alert.alert_id}: Found exact match with client {matching_client.name}"
                )
            
            if not dry_run:
                alert.client = matching_client
                alert.save()
            
            updated_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN: Would update {updated_count} alerts")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully updated {updated_count} alerts")
            )
