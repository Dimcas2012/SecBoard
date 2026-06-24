# app_gophish/tasks.py

import logging
from datetime import datetime
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from .models import (
    GophishServer, GophishGroup, GophishTemplate, GophishLandingPage,
    GophishSendingProfile, GophishCampaign, GophishEvent, GophishSyncLog
)
from .api_client import gophish_manager, GophishAPIError

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def sync_gophish_data(self, server_id, sync_type='full', force_update=False):
    """
    Synchronize data with Gophish server
    
    Args:
        server_id: ID of the GophishServer
        sync_type: Type of sync (full, campaigns, groups, templates, etc.)
        force_update: Whether to force update existing records
    """
    try:
        server = GophishServer.objects.get(id=server_id)
    except GophishServer.DoesNotExist:
        logger.error(f"Server with ID {server_id} not found")
        return {'status': 'error', 'message': 'Server not found'}
    
    # Create sync log
    sync_log = GophishSyncLog.objects.create(
        server=server,
        sync_type=sync_type,
        status='started',
        details={'task_id': self.request.id}
    )
    
    try:
        # Get API client
        client = gophish_manager.get_client(server)
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'status': 'Connecting to server...'})
        
        records_processed = 0
        records_created = 0
        records_updated = 0
        records_failed = 0
        
        if sync_type in ['full', 'groups']:
            records_processed, created, updated, failed = sync_groups(client, server, force_update)
            records_created += created
            records_updated += updated
            records_failed += failed
        
        if sync_type in ['full', 'templates']:
            records_processed, created, updated, failed = sync_templates(client, server, force_update)
            records_created += created
            records_updated += updated
            records_failed += failed
        
        if sync_type in ['full', 'landing_pages']:
            records_processed, created, updated, failed = sync_landing_pages(client, server, force_update)
            records_created += created
            records_updated += updated
            records_failed += failed
        
        if sync_type in ['full', 'sending_profiles']:
            records_processed, created, updated, failed = sync_sending_profiles(client, server, force_update)
            records_created += created
            records_updated += updated
            records_failed += failed
        
        if sync_type in ['full', 'campaigns']:
            records_processed, created, updated, failed = sync_campaigns(client, server, force_update)
            records_created += created
            records_updated += updated
            records_failed += failed
        
        if sync_type in ['full', 'campaigns', 'results']:
            records_processed, created, updated, failed = sync_campaign_results(client, server, force_update)
            records_created += created
            records_updated += updated
            records_failed += failed
        
        # Update sync log
        sync_log.status = 'completed' if records_failed == 0 else 'partial'
        sync_log.completed_at = timezone.now()
        sync_log.records_processed = records_processed
        sync_log.records_created = records_created
        sync_log.records_updated = records_updated
        sync_log.records_failed = records_failed
        sync_log.save()
        
        logger.info(f"Sync completed for server {server.name}: {records_created} created, {records_updated} updated, {records_failed} failed")
        
        return {
            'status': 'completed',
            'records_processed': records_processed,
            'records_created': records_created,
            'records_updated': records_updated,
            'records_failed': records_failed
        }
        
    except GophishAPIError as e:
        logger.error(f"API error during sync for server {server.name}: {str(e)}")
        sync_log.status = 'failed'
        sync_log.completed_at = timezone.now()
        sync_log.error_message = str(e)
        sync_log.save()
        
        return {'status': 'error', 'message': str(e)}
    
    except Exception as e:
        logger.error(f"Unexpected error during sync for server {server.name}: {str(e)}")
        sync_log.status = 'failed'
        sync_log.completed_at = timezone.now()
        sync_log.error_message = str(e)
        sync_log.save()
        
        return {'status': 'error', 'message': str(e)}


def sync_groups(client, server, force_update=False):
    """Synchronize groups from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    
    try:
        groups_data = client.get_groups()
        
        for group_data in groups_data:
            records_processed += 1
            
            try:
                with transaction.atomic():
                    group, created = GophishGroup.objects.get_or_create(
                        server=server,
                        gophish_id=group_data['id'],
                        defaults={
                            'name': group_data['name'],
                            'targets_data': group_data,
                        }
                    )
                    
                    if created:
                        records_created += 1
                    elif force_update or group.last_sync < timezone.now() - timezone.timedelta(minutes=5):
                        group.name = group_data['name']
                        group.targets_data = group_data
                        group.last_sync = timezone.now()
                        group.save()
                        records_updated += 1
                        
            except Exception as e:
                logger.error(f"Error syncing group {group_data['id']}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching groups: {str(e)}")
        records_failed += 1
    
    return records_processed, records_created, records_updated, records_failed


def sync_templates(client, server, force_update=False):
    """Synchronize templates from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    
    try:
        templates_data = client.get_templates()
        
        for template_data in templates_data:
            records_processed += 1
            
            try:
                with transaction.atomic():
                    template, created = GophishTemplate.objects.get_or_create(
                        server=server,
                        gophish_id=template_data['id'],
                        defaults={
                            'name': template_data['name'],
                            'subject': template_data['subject'],
                            'html_content': template_data['html'],
                            'text_content': template_data.get('text', ''),
                        }
                    )
                    
                    if created:
                        records_created += 1
                    elif force_update or template.last_sync < timezone.now() - timezone.timedelta(minutes=5):
                        template.name = template_data['name']
                        template.subject = template_data['subject']
                        template.html_content = template_data['html']
                        template.text_content = template_data.get('text', '')
                        template.last_sync = timezone.now()
                        template.save()
                        records_updated += 1
                        
            except Exception as e:
                logger.error(f"Error syncing template {template_data['id']}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching templates: {str(e)}")
        records_failed += 1
    
    return records_processed, records_created, records_updated, records_failed


def sync_landing_pages(client, server, force_update=False):
    """Synchronize landing pages from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    
    try:
        pages_data = client.get_landing_pages()
        
        for page_data in pages_data:
            records_processed += 1
            
            try:
                with transaction.atomic():
                    page, created = GophishLandingPage.objects.get_or_create(
                        server=server,
                        gophish_id=page_data['id'],
                        defaults={
                            'name': page_data['name'],
                            'html_content': page_data['html'],
                            'capture_credentials': page_data.get('capture_credentials', False),
                            'capture_passwords': page_data.get('capture_passwords', False),
                            'redirect_url': page_data.get('redirect_url', ''),
                        }
                    )
                    
                    if created:
                        records_created += 1
                    elif force_update or page.last_sync < timezone.now() - timezone.timedelta(minutes=5):
                        page.name = page_data['name']
                        page.html_content = page_data['html']
                        page.capture_credentials = page_data.get('capture_credentials', False)
                        page.capture_passwords = page_data.get('capture_passwords', False)
                        page.redirect_url = page_data.get('redirect_url', '')
                        page.last_sync = timezone.now()
                        page.save()
                        records_updated += 1
                        
            except Exception as e:
                logger.error(f"Error syncing landing page {page_data['id']}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching landing pages: {str(e)}")
        records_failed += 1
    
    return records_processed, records_created, records_updated, records_failed


def sync_sending_profiles(client, server, force_update=False):
    """Synchronize sending profiles from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    
    try:
        profiles_data = client.get_sending_profiles()
        
        for profile_data in profiles_data:
            records_processed += 1
            
            try:
                with transaction.atomic():
                    profile, created = GophishSendingProfile.objects.get_or_create(
                        server=server,
                        gophish_id=profile_data['id'],
                        defaults={
                            'name': profile_data['name'],
                            'from_address': profile_data['from_address'],
                            'from_name': profile_data['from_name'],
                            'smtp_host': profile_data['host'],
                            'smtp_port': profile_data['port'],
                            'smtp_username': profile_data['username'],
                            'smtp_password': profile_data.get('password', ''),
                            'ignore_cert_errors': profile_data.get('ignore_cert_errors', False),
                        }
                    )
                    
                    if created:
                        records_created += 1
                    elif force_update or profile.last_sync < timezone.now() - timezone.timedelta(minutes=5):
                        profile.name = profile_data['name']
                        profile.from_address = profile_data['from_address']
                        profile.from_name = profile_data['from_name']
                        profile.smtp_host = profile_data['host']
                        profile.smtp_port = profile_data['port']
                        profile.smtp_username = profile_data['username']
                        profile.smtp_password = profile_data.get('password', '')
                        profile.ignore_cert_errors = profile_data.get('ignore_cert_errors', False)
                        profile.last_sync = timezone.now()
                        profile.save()
                        records_updated += 1
                        
            except Exception as e:
                logger.error(f"Error syncing sending profile {profile_data['id']}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching sending profiles: {str(e)}")
        records_failed += 1
    
    return records_processed, records_created, records_updated, records_failed


def sync_campaigns(client, server, force_update=False):
    """Synchronize campaigns from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    
    try:
        campaigns_data = client.get_campaigns()
        
        for campaign_data in campaigns_data:
            records_processed += 1
            
            try:
                with transaction.atomic():
                    # Map status
                    status_mapping = {
                        'Draft': 'draft',
                        'Sending': 'running',
                        'Sent': 'completed',
                        'Completed': 'completed',
                        'Error': 'error',
                    }
                    status = status_mapping.get(campaign_data.get('status', ''), 'draft')
                    
                    campaign, created = GophishCampaign.objects.get_or_create(
                        server=server,
                        gophish_id=campaign_data['id'],
                        defaults={
                            'name': campaign_data['name'],
                            'status': status,
                            'url': campaign_data.get('url', ''),
                            'results_data': campaign_data.get('results', {}),
                        }
                    )
                    
                    if created:
                        records_created += 1
                        
                        # Link campaign components
                        try:
                            if 'template' in campaign_data and campaign_data['template']:
                                template = GophishTemplate.objects.filter(
                                    server=server,
                                    gophish_id=campaign_data['template']['id']
                                ).first()
                                if template:
                                    campaign.template = template
                            
                            if 'page' in campaign_data and campaign_data['page']:
                                landing_page = GophishLandingPage.objects.filter(
                                    server=server,
                                    gophish_id=campaign_data['page']['id']
                                ).first()
                                if landing_page:
                                    campaign.landing_page = landing_page
                            
                            if 'smtp' in campaign_data and campaign_data['smtp']:
                                sending_profile = GophishSendingProfile.objects.filter(
                                    server=server,
                                    gophish_id=campaign_data['smtp']['id']
                                ).first()
                                if sending_profile:
                                    campaign.sending_profile = sending_profile
                            
                            if 'groups' in campaign_data:
                                for group_data in campaign_data['groups']:
                                    group = GophishGroup.objects.filter(
                                        server=server,
                                        gophish_id=group_data['id']
                                    ).first()
                                    if group:
                                        campaign.groups.add(group)
                            
                            campaign.save()
                            
                        except Exception as e:
                            logger.error(f"Error linking campaign components: {str(e)}")
                    
                    elif force_update or campaign.last_sync < timezone.now() - timezone.timedelta(minutes=5):
                        campaign.name = campaign_data['name']
                        campaign.status = status
                        campaign.url = campaign_data.get('url', '')
                        campaign.results_data = campaign_data.get('results', {})
                        campaign.last_sync = timezone.now()
                        campaign.save()
                        records_updated += 1
                        
            except Exception as e:
                logger.error(f"Error syncing campaign {campaign_data['id']}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching campaigns: {str(e)}")
        records_failed += 1
    
    return records_processed, records_created, records_updated, records_failed


def sync_campaign_results(client, server, force_update=False):
    """Synchronize campaign results from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    
    try:
        campaigns = GophishCampaign.objects.filter(server=server, gophish_id__isnull=False)
        
        for campaign in campaigns:
            records_processed += 1
            
            try:
                # Get campaign results
                results_data = client.get_campaign_results(campaign.gophish_id)
                
                if results_data:
                    campaign.results_data = results_data
                    campaign.last_sync = timezone.now()
                    campaign.save()
                    records_updated += 1
                    
                    # Process events
                    events_data = results_data.get('timeline', [])
                    for event_data in events_data:
                        try:
                            # Map event types
                            event_type_mapping = {
                                'Email Sent': 'email_sent',
                                'Email Opened': 'email_opened',
                                'Clicked Link': 'link_clicked',
                                'Submitted Data': 'data_submitted',
                                'Captured Credentials': 'credentials_submitted',
                            }
                            
                            event_type = event_type_mapping.get(event_data.get('message', ''), 'unknown')
                            
                            if event_type != 'unknown':
                                GophishEvent.objects.get_or_create(
                                    campaign=campaign,
                                    event_type=event_type,
                                    target_email=event_data.get('email', ''),
                                    timestamp=datetime.fromisoformat(event_data.get('time', '').replace('Z', '+00:00')),
                                    defaults={
                                        'target_name': event_data.get('detail', ''),
                                        'details': event_data,
                                        'ip_address': event_data.get('ip', ''),
                                    }
                                )
                        except Exception as e:
                            logger.error(f"Error processing event: {str(e)}")
                            
            except Exception as e:
                logger.error(f"Error syncing campaign results for {campaign.id}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error syncing campaign results: {str(e)}")
        records_failed += 1
    
    return records_processed, records_created, records_updated, records_failed


@shared_task
def periodic_sync_all_servers():
    """Periodic task to sync all active servers"""
    servers = GophishServer.objects.filter(is_active=True)
    
    for server in servers:
        sync_gophish_data.delay(server.id, 'full', False)
    
    logger.info(f"Started sync tasks for {servers.count()} servers")


@shared_task
def cleanup_old_sync_logs():
    """Clean up old sync logs (keep last 30 days)"""
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=30)
    deleted_count = GophishSyncLog.objects.filter(started_at__lt=cutoff_date).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old sync logs")
    return deleted_count


@shared_task
def cleanup_old_events():
    """Clean up old events (keep last 90 days)"""
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=90)
    deleted_count = GophishEvent.objects.filter(timestamp__lt=cutoff_date).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old events")
    return deleted_count
