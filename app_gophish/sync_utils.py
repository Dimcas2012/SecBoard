# app_gophish/sync_utils.py

import logging
import urllib3
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from .models import (
    GophishServer, GophishGroup, GophishTemplate, GophishLandingPage,
    GophishSendingProfile, GophishCampaign, GophishEvent, GophishSyncLog
)
from django.contrib.auth.models import User
from .api_client import gophish_manager, GophishAPIError

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def sync_gophish_data_direct(server_id, sync_type='full', force_update=False):
    """
    Direct synchronization without Celery dependency
    
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
        details={'task_id': 'direct-sync', 'method': 'direct'}
    )
    
    try:
        # Clear client cache to ensure fresh SSL settings
        server_key = f"{server.id}_{server.base_url}"
        if server_key in gophish_manager.clients:
            del gophish_manager.clients[server_key]
        
        # Get API client with fresh SSL settings
        client = gophish_manager.get_client(server)
        # Ensure SSL verification is disabled
        client.session.verify = False
        
        records_processed = 0
        records_created = 0
        records_updated = 0
        records_failed = 0
        records_deleted = 0
        
        logger.info(f"Starting {sync_type} sync for server {server.name}")
        
        if sync_type in ['full', 'groups']:
            processed, created, updated, failed, deleted = sync_groups_direct(client, server, force_update)
            records_processed += processed
            records_created += created
            records_updated += updated
            records_failed += failed
            records_deleted += deleted
        
        if sync_type in ['full', 'templates']:
            processed, created, updated, failed, deleted = sync_templates_direct(client, server, force_update)
            records_processed += processed
            records_created += created
            records_updated += updated
            records_failed += failed
            records_deleted += deleted
        
        if sync_type in ['full', 'landing_pages']:
            processed, created, updated, failed, deleted = sync_landing_pages_direct(client, server, force_update)
            records_processed += processed
            records_created += created
            records_updated += updated
            records_failed += failed
            records_deleted += deleted
        
        if sync_type in ['full', 'sending_profiles']:
            processed, created, updated, failed, deleted = sync_sending_profiles_direct(client, server, force_update)
            records_processed += processed
            records_created += created
            records_updated += updated
            records_failed += failed
            records_deleted += deleted
        
        if sync_type in ['full', 'campaigns']:
            processed, created, updated, failed, deleted = sync_campaigns_direct(client, server, force_update)
            records_processed += processed
            records_created += created
            records_updated += updated
            records_failed += failed
            records_deleted += deleted
        
        if sync_type in ['full', 'campaigns', 'results']:
            processed, created, updated, failed = sync_campaign_results_direct(client, server, force_update)
            records_processed += processed
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
        
        logger.info(f"Direct sync completed for server {server.name}: {records_processed} processed, {records_created} created, {records_updated} updated, {records_deleted} deleted, {records_failed} failed")
        
        # Log detailed summary
        if records_failed > 0:
            logger.warning(f"Sync completed with {records_failed} failures for server {server.name}")
        else:
            logger.info(f"Sync completed successfully for server {server.name}")
        
        if records_deleted > 0:
            logger.info(f"Cleaned up {records_deleted} deleted records from server {server.name}")
        
        return {
            'status': 'completed',
            'records_processed': records_processed,
            'records_created': records_created,
            'records_updated': records_updated,
            'records_deleted': records_deleted,
            'records_failed': records_failed
        }
        
    except GophishAPIError as e:
        logger.error(f"API error during direct sync for server {server.name}: {str(e)}")
        sync_log.status = 'failed'
        sync_log.completed_at = timezone.now()
        sync_log.error_message = str(e)
        sync_log.save()
        
        return {'status': 'error', 'message': str(e)}
    
    except Exception as e:
        logger.error(f"Unexpected error during direct sync for server {server.name}: {str(e)}")
        sync_log.status = 'failed'
        sync_log.completed_at = timezone.now()
        sync_log.error_message = str(e)
        sync_log.save()
        
        return {'status': 'error', 'message': str(e)}


def cleanup_deleted_groups(server, existing_gophish_ids):
    """Remove groups that no longer exist on the Gophish server"""
    deleted_count = 0
    
    # Find groups that exist locally but not on the server
    local_groups = GophishGroup.objects.filter(server=server, gophish_id__isnull=False)
    for group in local_groups:
        if group.gophish_id not in existing_gophish_ids:
            logger.info(f"Removing deleted group: {group.name} (ID: {group.gophish_id})")
            group.delete()
            deleted_count += 1
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} deleted groups from server {server.name}")
    
    return deleted_count


def sync_groups_direct(client, server, force_update=False):
    """Synchronize groups from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    records_deleted = 0
    
    try:
        groups_data = client.get_groups()
        
        # Get list of existing group IDs for cleanup
        existing_group_ids = [str(group['id']) for group in groups_data]
        
        # Clean up deleted groups
        records_deleted = cleanup_deleted_groups(server, existing_group_ids)
        
        # Ensure groups_data is a list
        if not isinstance(groups_data, list):
            logger.error(f"get_groups returned non-list: {type(groups_data)}")
            groups_data = []
        
        logger.info(f"Found {len(groups_data)} groups on server {server.name}")
        
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
                    else:
                        # Always update existing groups to ensure data consistency
                        group.name = group_data['name']
                        group.targets_data = group_data
                        group.last_sync = timezone.now()
                        group.save()
                        records_updated += 1
                        
            except Exception as e:
                group_id = group_data.get('id', 'unknown') if isinstance(group_data, dict) else 'unknown'
                group_name = group_data.get('name', 'unknown') if isinstance(group_data, dict) else 'unknown'
                logger.error(f"Error syncing group {group_name}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching groups from server {server.name}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        records_failed += 1
    
    logger.info(f"Groups sync completed: {records_processed} processed, {records_created} created, {records_updated} updated, {records_deleted} deleted, {records_failed} failed")
    return records_processed, records_created, records_updated, records_failed, records_deleted


def cleanup_deleted_templates(server, existing_gophish_ids):
    """Remove templates that no longer exist on the Gophish server"""
    deleted_count = 0
    
    # Find templates that exist locally but not on the server
    local_templates = GophishTemplate.objects.filter(server=server, gophish_id__isnull=False)
    for template in local_templates:
        if template.gophish_id not in existing_gophish_ids:
            logger.info(f"Removing deleted template: {template.name} (ID: {template.gophish_id})")
            template.delete()
            deleted_count += 1
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} deleted templates from server {server.name}")
    
    return deleted_count


def sync_templates_direct(client, server, force_update=False):
    """Synchronize templates from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    records_deleted = 0
    
    try:
        templates_data = client.get_templates()
        
        # Get list of existing template IDs for cleanup
        existing_template_ids = [str(template['id']) for template in templates_data]
        
        # Clean up deleted templates
        records_deleted = cleanup_deleted_templates(server, existing_template_ids)
        
        # Ensure templates_data is a list
        if not isinstance(templates_data, list):
            logger.error(f"get_templates returned non-list: {type(templates_data)}")
            templates_data = []
        
        logger.info(f"Found {len(templates_data)} templates on server {server.name}")
        
        for template_data in templates_data:
            records_processed += 1
            
            try:
                with transaction.atomic():
                    template, created = GophishTemplate.objects.get_or_create(
                        server=server,
                        gophish_id=template_data['id'],
                        defaults={
                            'name': template_data['name'],
                            'subject': template_data.get('subject', ''),
                            'text_content': template_data.get('text', ''),
                            'html_content': template_data.get('html', ''),
                        }
                    )
                    
                    if created:
                        records_created += 1
                    else:
                        # Always update existing templates to ensure data consistency
                        template.name = template_data['name']
                        template.subject = template_data.get('subject', '')
                        template.text_content = template_data.get('text', '')
                        template.html_content = template_data.get('html', '')
                        template.last_sync = timezone.now()
                        template.save()
                        records_updated += 1
                        
            except Exception as e:
                template_id = template_data.get('id', 'unknown') if isinstance(template_data, dict) else 'unknown'
                template_name = template_data.get('name', 'unknown') if isinstance(template_data, dict) else 'unknown'
                logger.error(f"Error syncing template {template_name}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching templates from server {server.name}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        records_failed += 1
    
    logger.info(f"Templates sync completed: {records_processed} processed, {records_created} created, {records_updated} updated, {records_deleted} deleted, {records_failed} failed")
    return records_processed, records_created, records_updated, records_failed, records_deleted


def cleanup_deleted_landing_pages(server, existing_gophish_ids):
    """Remove landing pages that no longer exist on the Gophish server"""
    deleted_count = 0
    
    # Find landing pages that exist locally but not on the server
    local_pages = GophishLandingPage.objects.filter(server=server, gophish_id__isnull=False)
    for page in local_pages:
        if page.gophish_id not in existing_gophish_ids:
            logger.info(f"Removing deleted landing page: {page.name} (ID: {page.gophish_id})")
            page.delete()
            deleted_count += 1
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} deleted landing pages from server {server.name}")
    
    return deleted_count


def sync_landing_pages_direct(client, server, force_update=False):
    """Synchronize landing pages from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    records_deleted = 0
    
    try:
        pages_data = client.get_landing_pages()
        
        # Get list of existing landing page IDs for cleanup
        existing_page_ids = [str(page['id']) for page in pages_data]
        
        # Clean up deleted landing pages
        records_deleted = cleanup_deleted_landing_pages(server, existing_page_ids)
        
        # Ensure pages_data is a list
        if not isinstance(pages_data, list):
            logger.error(f"get_landing_pages returned non-list: {type(pages_data)}")
            pages_data = []
        
        logger.info(f"Found {len(pages_data)} landing pages on server {server.name}")
        
        for page_data in pages_data:
            records_processed += 1
            
            # Ensure page_data is a dict
            if not isinstance(page_data, dict):
                logger.error(f"page_data is not a dict: {type(page_data)}, skipping")
                records_failed += 1
                continue
            
            try:
                with transaction.atomic():
                    page, created = GophishLandingPage.objects.get_or_create(
                        server=server,
                        gophish_id=page_data.get('id'),
                        defaults={
                            'name': page_data.get('name', ''),
                            'html_content': page_data.get('html', ''),
                            'capture_credentials': page_data.get('capture_credentials', False),
                            'capture_passwords': page_data.get('capture_passwords', False),
                            'redirect_url': page_data.get('redirect_url', ''),
                        }
                    )
                    
                    if created:
                        records_created += 1
                    else:
                        # Always update existing landing pages to ensure data consistency
                        page.name = page_data.get('name', '')
                        page.html_content = page_data.get('html', '')
                        page.capture_credentials = page_data.get('capture_credentials', False)
                        page.capture_passwords = page_data.get('capture_passwords', False)
                        page.redirect_url = page_data.get('redirect_url', '')
                        page.last_sync = timezone.now()
                        page.save()
                        records_updated += 1
                        
            except Exception as e:
                page_id = page_data.get('id', 'unknown') if isinstance(page_data, dict) else 'unknown'
                page_name = page_data.get('name', 'unknown') if isinstance(page_data, dict) else 'unknown'
                import traceback
                logger.error(f"Error syncing landing page {page_name}: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching landing pages from server {server.name}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        records_failed += 1
    
    logger.info(f"Landing pages sync completed: {records_processed} processed, {records_created} created, {records_updated} updated, {records_deleted} deleted, {records_failed} failed")
    return records_processed, records_created, records_updated, records_failed, records_deleted


def cleanup_deleted_sending_profiles(server, existing_gophish_ids):
    """Remove sending profiles that no longer exist on the Gophish server"""
    deleted_count = 0
    
    # Find sending profiles that exist locally but not on the server
    local_profiles = GophishSendingProfile.objects.filter(server=server, gophish_id__isnull=False)
    for profile in local_profiles:
        if profile.gophish_id not in existing_gophish_ids:
            logger.info(f"Removing deleted sending profile: {profile.name} (ID: {profile.gophish_id})")
            profile.delete()
            deleted_count += 1
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} deleted sending profiles from server {server.name}")
    
    return deleted_count


def sync_sending_profiles_direct(client, server, force_update=False):
    """Synchronize sending profiles from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    records_deleted = 0
    
    try:
        profiles_data = client.get_sending_profiles()
        
        # Get list of existing sending profile IDs for cleanup
        existing_profile_ids = [str(profile['id']) for profile in profiles_data]
        
        # Clean up deleted sending profiles
        records_deleted = cleanup_deleted_sending_profiles(server, existing_profile_ids)
        
        # Ensure profiles_data is a list
        if not isinstance(profiles_data, list):
            logger.error(f"get_sending_profiles returned non-list: {type(profiles_data)}")
            profiles_data = []
        
        logger.info(f"Found {len(profiles_data)} sending profiles on server {server.name}")
        logger.debug(f"DEBUG: Found {len(profiles_data)} sending profiles on server {server.name}")
        
        # Log the IDs of sending profiles found
        for profile in profiles_data:
            logger.debug(f"  - Sending Profile ID {profile.get('id')}: {profile.get('name', 'NO NAME')}")
        
        for profile_data in profiles_data:
            records_processed += 1
            
            try:
                with transaction.atomic():
                    profile, created = GophishSendingProfile.objects.get_or_create(
                        server=server,
                        gophish_id=profile_data['id'],
                        defaults={
                            'name': profile_data['name'],
                            'from_address': profile_data.get('from_address', ''),
                            'from_name': profile_data.get('from_name', ''),
                            'smtp_host': profile_data.get('host', ''),
                            'smtp_port': profile_data.get('port', 587),
                            'smtp_username': profile_data.get('username', ''),
                            'smtp_password': profile_data.get('password', ''),
                            'ignore_cert_errors': profile_data.get('ignore_cert_errors', False),
                        }
                    )
                    
                    if created:
                        records_created += 1
                    else:
                        # Always update existing sending profiles to ensure data consistency
                        profile.name = profile_data['name']
                        profile.from_address = profile_data.get('from_address', '')
                        profile.from_name = profile_data.get('from_name', '')
                        profile.smtp_host = profile_data.get('host', '')
                        profile.smtp_port = profile_data.get('port', 587)
                        profile.smtp_username = profile_data.get('username', '')
                        profile.smtp_password = profile_data.get('password', '')
                        profile.ignore_cert_errors = profile_data.get('ignore_cert_errors', False)
                        profile.last_sync = timezone.now()
                        profile.save()
                        records_updated += 1
                        
            except Exception as e:
                profile_id = profile_data.get('id', 'unknown') if isinstance(profile_data, dict) else 'unknown'
                profile_name = profile_data.get('name', 'unknown') if isinstance(profile_data, dict) else 'unknown'
                logger.error(f"Error syncing sending profile {profile_name}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching sending profiles from server {server.name}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        records_failed += 1
    
    logger.info(f"Sending profiles sync completed: {records_processed} processed, {records_created} created, {records_updated} updated, {records_deleted} deleted, {records_failed} failed")
    return records_processed, records_created, records_updated, records_failed, records_deleted


def validate_campaign_components(server, campaign_data):
    """
    Validate that all required components exist for a campaign
    
    Returns:
        tuple: (is_valid, missing_components, warnings)
    """
    missing_components = []
    warnings = []
    
    # Check template
    template = None
    if campaign_data.get('template', {}).get('id'):
        try:
            template = GophishTemplate.objects.get(
                server=server,
                gophish_id=campaign_data['template']['id']
            )
        except GophishTemplate.DoesNotExist:
            missing_components.append('template')
            warnings.append(f"Template {campaign_data['template']['id']} not found")
    
    # Check landing page
    landing_page = None
    if campaign_data.get('page', {}).get('id'):
        try:
            landing_page = GophishLandingPage.objects.get(
                server=server,
                gophish_id=campaign_data['page']['id']
            )
        except GophishLandingPage.DoesNotExist:
            missing_components.append('landing_page')
            warnings.append(f"Landing page {campaign_data['page']['id']} not found")
    
    # Check sending profile
    sending_profile = None
    if campaign_data.get('smtp', {}).get('id'):
        try:
            sending_profile = GophishSendingProfile.objects.get(
                server=server,
                gophish_id=campaign_data['smtp']['id']
            )
        except GophishSendingProfile.DoesNotExist:
            missing_components.append('sending_profile')
            warnings.append(f"Sending profile {campaign_data['smtp']['id']} not found")
    
    is_valid = len(missing_components) == 0
    return is_valid, missing_components, warnings, template, landing_page, sending_profile


def cleanup_deleted_campaigns(server, existing_gophish_ids):
    """Remove campaigns that no longer exist on the Gophish server"""
    deleted_count = 0
    
    # Find campaigns that exist locally but not on the server
    local_campaigns = GophishCampaign.objects.filter(server=server, gophish_id__isnull=False)
    for campaign in local_campaigns:
        if campaign.gophish_id not in existing_gophish_ids:
            logger.info(f"Removing deleted campaign: {campaign.name} (ID: {campaign.gophish_id})")
            campaign.delete()
            deleted_count += 1
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} deleted campaigns from server {server.name}")
    
    return deleted_count


def sync_campaigns_direct(client, server, force_update=False):
    """Synchronize campaigns from Gophish"""
    records_processed = 0
    records_created = 0
    records_updated = 0
    records_failed = 0
    records_deleted = 0
    
    try:
        campaigns_data = client.get_campaigns()
        
        # Get list of existing campaign IDs for cleanup
        existing_campaign_ids = [str(campaign['id']) for campaign in campaigns_data]
        
        # Clean up deleted campaigns
        records_deleted = cleanup_deleted_campaigns(server, existing_campaign_ids)
        
        logger.info(f"Found {len(campaigns_data)} campaigns on server {server.name}")
        logger.debug(f"DEBUG: Found {len(campaigns_data)} campaigns on server {server.name}")
        
        # Log sample campaign data structure for debugging
        if campaigns_data:
            sample_campaign = campaigns_data[0]
            logger.debug(f"Sample campaign data structure: {sample_campaign}")
            logger.debug(f"Sample campaign keys: {list(sample_campaign.keys())}")
            if 'results' in sample_campaign:
                logger.debug(f"Sample campaign results: {sample_campaign['results']}")
        
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
                    
                    # Log the status mapping for debugging
                    logger.debug(f"Campaign {campaign_data['id']} status: '{campaign_data.get('status', '')}' -> '{status}'")
                    
                    # Validate campaign components
                    is_valid, missing_components, warnings, template, landing_page, sending_profile = validate_campaign_components(server, campaign_data)
                    
                    # Log detailed component information
                    logger.info(f"Campaign {campaign_data['id']} ({campaign_data['name']}):")
                    logger.info(f"  - Template: {template.name if template else 'NOT FOUND'}")
                    logger.info(f"  - Landing Page: {landing_page.name if landing_page else 'NOT FOUND'}")
                    logger.info(f"  - Sending Profile: {sending_profile.name if sending_profile else 'NOT FOUND'}")
                    
                    logger.debug(f"DEBUG: Campaign {campaign_data['id']} ({campaign_data['name']}):")
                    logger.debug(f"  - Template: {template.name if template else 'NOT FOUND'}")
                    logger.debug(f"  - Landing Page: {landing_page.name if landing_page else 'NOT FOUND'}")
                    logger.debug(f"  - Sending Profile: {sending_profile.name if sending_profile else 'NOT FOUND'}")
                    
                    # Log the actual template ID from campaign data
                    if 'template' in campaign_data:
                        template_id = campaign_data['template'].get('id', 'NO ID')
                        template_name = campaign_data['template'].get('name', 'NO NAME')
                        logger.debug(f"  - Campaign Template ID: {template_id}")
                        logger.debug(f"  - Campaign Template Name: {template_name}")
                    else:
                        logger.debug(f"  - Campaign Template: NO TEMPLATE DATA")
                    
                    # Log the actual sending profile ID from campaign data
                    if 'smtp' in campaign_data:
                        smtp_id = campaign_data['smtp'].get('id', 'NO ID')
                        smtp_name = campaign_data['smtp'].get('name', 'NO NAME')
                        logger.debug(f"  - Campaign SMTP ID: {smtp_id}")
                        logger.debug(f"  - Campaign SMTP Name: {smtp_name}")
                        
                        # Check if sending profile is deleted
                        if smtp_id == 0 or smtp_name == '[Deleted]':
                            logger.warning(f"Campaign {campaign_data['id']} uses deleted sending profile (ID: {smtp_id}, Name: {smtp_name})")
                    else:
                        logger.debug(f"  - Campaign SMTP: NO SMTP DATA")
                    
                    # Log warnings for missing components
                    for warning in warnings:
                        logger.warning(f"Campaign {campaign_data['id']}: {warning}")
                    
                    # Log missing components
                    if missing_components:
                        logger.warning(f"Campaign {campaign_data['id']} missing components: {', '.join(missing_components)}")
                    
                    # Validate required fields
                    if not campaign_data.get('name'):
                        logger.error(f"Campaign {campaign_data['id']} has no name, skipping")
                        records_failed += 1
                        continue
                    
                    # Check for deleted components but don't skip - sync as is
                    smtp_deleted = False
                    template_deleted = False
                    
                    if 'smtp' in campaign_data:
                        smtp_id = campaign_data['smtp'].get('id', 'NO ID')
                        smtp_name = campaign_data['smtp'].get('name', 'NO NAME')
                        if smtp_id == 0 or smtp_name == '[Deleted]':
                            smtp_deleted = True
                            logger.warning(f"Campaign {campaign_data['id']} uses deleted sending profile (ID: {smtp_id}, Name: {smtp_name}) - will sync with NULL")
                    
                    if 'template' in campaign_data:
                        template_id = campaign_data['template'].get('id', 'NO ID')
                        template_name = campaign_data['template'].get('name', 'NO NAME')
                        if template_id == 0 or template_name == '[Deleted]':
                            template_deleted = True
                            logger.warning(f"Campaign {campaign_data['id']} uses deleted template (ID: {template_id}, Name: {template_name}) - will sync with NULL")
                    
                    # Log missing components but don't skip - sync as is
                    missing_components = []
                    if not template:
                        missing_components.append('template')
                    if not landing_page:
                        missing_components.append('landing_page')
                    if not sending_profile:
                        missing_components.append('sending_profile')
                    
                    if missing_components:
                        logger.warning(f"Campaign {campaign_data['id']} missing components: {', '.join(missing_components)} - will sync with NULL values")
                    
                    # Continue with sync even if components are missing - sync exactly as on server
                    
                    # Get or create a default user for campaigns
                    default_user = User.objects.filter(is_superuser=True).first()
                    if not default_user:
                        default_user = User.objects.first()
                    
                    if not default_user:
                        logger.error(f"No user available for campaign creation, skipping campaign {campaign_data['id']}")
                        records_failed += 1
                        continue
                    
                    # Prepare campaign data - sync exactly as on server, even with NULL values
                    campaign_defaults = {
                        'name': campaign_data['name'],
                        'status': status,
                        'url': campaign_data.get('url', ''),
                        'template': template,  # Can be None for deleted templates
                        'landing_page': landing_page,  # Can be None for deleted landing pages
                        'sending_profile': sending_profile,  # Can be None for deleted sending profiles
                        'results_data': campaign_data.get('results', {}),
                        'created_by': default_user,
                    }
                    
                    try:
                        campaign, created = GophishCampaign.objects.get_or_create(
                            server=server,
                            gophish_id=campaign_data['id'],
                            defaults=campaign_defaults
                        )
                        
                        if created:
                            records_created += 1
                            logger.info(f"Created campaign: {campaign.name}")
                        else:
                            # Always update existing campaigns to ensure data consistency
                            campaign.name = campaign_data['name']
                            campaign.status = status
                            campaign.url = campaign_data.get('url', '')
                            campaign.template = template  # Can be None for deleted templates
                            campaign.landing_page = landing_page  # Can be None for deleted landing pages
                            campaign.sending_profile = sending_profile  # Can be None for deleted sending profiles
                            campaign.results_data = campaign_data.get('results', {})
                            campaign.last_sync = timezone.now()
                            campaign.save()
                            records_updated += 1
                            logger.info(f"Updated campaign: {campaign.name}")
                    except Exception as db_error:
                        logger.error(f"Database error creating/updating campaign {campaign_data['name']}: {str(db_error)}")
                        records_failed += 1
                        continue
                        
            except Exception as e:
                campaign_id = campaign_data.get('id', 'unknown') if isinstance(campaign_data, dict) else 'unknown'
                campaign_name = campaign_data.get('name', 'unknown') if isinstance(campaign_data, dict) else 'unknown'
                logger.error(f"Error syncing campaign {campaign_name}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching campaigns from server {server.name}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        records_failed += 1
    
    logger.info(f"Campaigns sync completed: {records_processed} processed, {records_created} created, {records_updated} updated, {records_deleted} deleted, {records_failed} failed")
    return records_processed, records_created, records_updated, records_failed, records_deleted


def sync_campaign_results_direct(client, server, force_update=False):
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
                    # Log the results data structure for debugging
                    logger.debug(f"Campaign {campaign.gophish_id} results data structure: {results_data}")
                    logger.debug(f"Campaign {campaign.gophish_id} results keys: {list(results_data.keys())}")
                    if 'timeline' in results_data:
                        logger.debug(f"Campaign {campaign.gophish_id} timeline events: {len(results_data['timeline'])}")
                        if results_data['timeline']:
                            logger.debug(f"Sample timeline event: {results_data['timeline'][0]}")
                    # Store the raw results data
                    campaign.results_data = results_data
                    
                    # Extract and store individual metrics for better display
                    # The Gophish API returns results in different formats, so we need to handle both
                    metrics = {}
                    
                    # Check if results_data has direct metric fields
                    if 'emails_sent' in results_data:
                        metrics['emails_sent'] = results_data.get('emails_sent', 0)
                    if 'emails_opened' in results_data:
                        metrics['emails_opened'] = results_data.get('emails_opened', 0)
                    if 'links_clicked' in results_data:
                        metrics['links_clicked'] = results_data.get('links_clicked', 0)
                    if 'credentials_submitted' in results_data:
                        metrics['credentials_submitted'] = results_data.get('credentials_submitted', 0)
                    if 'data_submitted' in results_data:
                        metrics['data_submitted'] = results_data.get('data_submitted', 0)
                    
                    # If direct metrics are not available, try to calculate from timeline events
                    if not metrics:
                        timeline = results_data.get('timeline', [])
                        if timeline:
                            # Count events by type
                            emails_sent = sum(1 for event in timeline if event.get('message') == 'Email Sent')
                            emails_opened = sum(1 for event in timeline if event.get('message') == 'Email Opened')
                            links_clicked = sum(1 for event in timeline if event.get('message') == 'Clicked Link')
                            credentials_submitted = sum(1 for event in timeline if event.get('message') == 'Submitted Data')
                            
                            metrics = {
                                'emails_sent': emails_sent,
                                'emails_opened': emails_opened,
                                'links_clicked': links_clicked,
                                'credentials_submitted': credentials_submitted,
                                'data_submitted': credentials_submitted  # Same as credentials_submitted in Gophish
                            }
                    
                    # Update the results_data with calculated metrics
                    campaign.results_data.update(metrics)
                    
                    campaign.last_sync = timezone.now()
                    campaign.save()
                    records_updated += 1
                    
                    logger.info(f"Updated campaign {campaign.name} with metrics: {metrics}")
                    
                    # Process events
                    events_data = results_data.get('timeline', [])
                    for event_data in events_data:
                        try:
                            # Map event types to our model choices
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
                            logger.warning(f"Error creating event: {str(e)}")
                            continue
                else:
                    logger.info(f"No results data available for campaign {campaign.gophish_id}")
                    records_updated += 1  # Still count as processed
                            
            except GophishAPIError as e:
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.info(f"Campaign results not available for {campaign.gophish_id} (campaign may not have been launched yet)")
                    records_updated += 1  # Count as processed, not failed
                else:
                    logger.error(f"API error syncing campaign results for {campaign.gophish_id}: {str(e)}")
                    records_failed += 1
            except Exception as e:
                logger.error(f"Error syncing campaign results for {campaign.gophish_id}: {str(e)}")
                records_failed += 1
    
    except Exception as e:
        logger.error(f"Error fetching campaign results from server {server.name}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        records_failed += 1
    
    logger.info(f"Campaign results sync completed: {records_processed} processed, {records_created} created, {records_updated} updated, {records_failed} failed")
    return records_processed, records_created, records_updated, records_failed
