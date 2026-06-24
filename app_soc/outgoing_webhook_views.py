import json
import logging
import requests
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from .models import OutgoingWebhook, OutgoingWebhookLog, WazuhFIMAlert, WebhookClient
from .views import fim_access_required, check_fim_access

logger = logging.getLogger(__name__)


def fim_api_access_required(permission=None):
    """
    Decorator for API endpoints that returns JSON errors instead of HTML redirects
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required'
                }, status=401)
            
            if not check_fim_access(request.user, permission):
                return JsonResponse({
                    'success': False,
                    'error': 'You don\'t have permission to access FIM dashboard configuration. Please contact administrator.'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@require_http_methods(["GET", "POST"])
@csrf_exempt
@fim_api_access_required('configure')
def outgoing_webhooks_api(request):
    """API endpoint for managing outgoing webhooks"""
    
    if request.method == 'GET':
        try:
            from .views import get_user_accessible_companies
            
            # Get user's accessible companies based on AccessFIM configuration
            accessible_companies = get_user_accessible_companies(request.user)
            
            if accessible_companies is None:
                # User has access to all companies
                webhooks = OutgoingWebhook.objects.all()
            elif accessible_companies:
                # User has access only to specific companies
                webhooks = OutgoingWebhook.objects.filter(company__in=accessible_companies)
            else:
                # User has no access to any companies
                webhooks = OutgoingWebhook.objects.none()
            
            webhooks_data = []
            for webhook in webhooks:
                webhooks_data.append({
                    'id': webhook.id,
                    'name': webhook.name,
                    'url': webhook.url,
                    'method': webhook.method,
                    'content_type': webhook.content_type,
                    'enabled': webhook.enabled,
                    'auth_type': webhook.auth_type,
                    'trigger_events': webhook.trigger_events,
                    'include_alert_data': webhook.include_alert_data,
                    'include_analysis_data': webhook.include_analysis_data,
                    'include_ai_analysis': webhook.include_ai_analysis,
                    'description': webhook.description,
                    'company_id': webhook.company_id,
                    'company_name': webhook.company.name if webhook.company else None,
                    # Filter fields
                    'filter_clients': [c.id for c in webhook.filter_clients.all()],
                    'filter_alert_types': webhook.filter_alert_types,
                    'filter_severity_levels': webhook.filter_severity_levels,
                    'filter_rule_ids': webhook.filter_rule_ids,
                    'filter_agent_ids': webhook.filter_agent_ids,
                    'filter_statuses': webhook.filter_statuses,
                    # Stats
                    'total_sent': webhook.total_sent,
                    'last_sent_at': webhook.last_sent_at.isoformat() if webhook.last_sent_at else None,
                    'created_at': webhook.created_at.isoformat(),
                })
            
            return JsonResponse({
                'success': True,
                'webhooks': webhooks_data
            })
            
        except Exception as e:
            logger.error(f"Error loading outgoing webhooks: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to load outgoing webhooks'
            }, status=500)
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'url', 'method', 'trigger_events', 'company_id']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }, status=400)
            
            # Get company from data and validate user access
            from app_conf.models import Company
            from .views import get_user_accessible_companies
            
            try:
                company = Company.objects.get(id=data['company_id'])
            except Company.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid company ID'
                }, status=400)
            
            # Check if user has access to this company
            accessible_companies = get_user_accessible_companies(request.user)
            if accessible_companies is not None:  # Not a superuser with full access
                if not accessible_companies or company not in accessible_companies:
                    return JsonResponse({
                        'success': False,
                        'error': 'You do not have permission to create webhooks for this company'
                    }, status=403)
            
            # Create webhook
            webhook = OutgoingWebhook.objects.create(
                name=data['name'],
                url=data['url'],
                method=data['method'],
                content_type=data.get('content_type', 'application/json'),
                enabled=data.get('enabled', True),
                auth_type=data.get('auth_type', 'none'),
                trigger_events=data['trigger_events'],
                custom_payload_template=data.get('custom_payload_template', ''),
                include_alert_data=data.get('include_alert_data', True),
                include_analysis_data=data.get('include_analysis_data', True),
                include_ai_analysis=data.get('include_ai_analysis', False),
                custom_headers=data.get('custom_headers', {}),
                description=data.get('description', ''),
                company=company,
                created_by=request.user,
                # Filter fields
                filter_alert_types=data.get('filter_alert_types', []),
                filter_severity_levels=data.get('filter_severity_levels', []),
                filter_rule_ids=data.get('filter_rule_ids', []),
                filter_agent_ids=data.get('filter_agent_ids', []),
                filter_statuses=data.get('filter_statuses', []),
            )
            
            # Set filter clients (ManyToMany field)
            if 'filter_clients' in data and data['filter_clients']:
                webhook.filter_clients.set(data['filter_clients'])
            
            # Set authentication data if provided
            if 'auth_data' in data and data['auth_data']:
                webhook.set_auth_data(data['auth_data'])
                webhook.save()
            
            logger.info(f"Created outgoing webhook: {webhook.name} by {request.user.username}")
            
            return JsonResponse({
                'success': True,
                'webhook_id': webhook.id,
                'message': 'Outgoing webhook created successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error creating outgoing webhook: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create outgoing webhook'
            }, status=500)


@require_http_methods(["GET", "PUT", "DELETE"])
@csrf_exempt
@fim_api_access_required('configure')
def outgoing_webhook_detail_api(request, webhook_id):
    """API endpoint for managing individual outgoing webhook"""
    
    try:
        from .views import get_user_accessible_companies
        
        # Get user's accessible companies based on AccessFIM configuration
        accessible_companies = get_user_accessible_companies(request.user)
        
        if accessible_companies is None:
            # User has access to all companies
            webhook = OutgoingWebhook.objects.get(id=webhook_id)
        elif accessible_companies:
            # User has access only to specific companies
            webhook = OutgoingWebhook.objects.get(id=webhook_id, company__in=accessible_companies)
        else:
            # User has no access to any companies
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to access webhooks'
            }, status=403)
            
    except OutgoingWebhook.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Webhook not found or you do not have permission to access it'
        }, status=404)
    
    if request.method == 'GET':
        try:
            webhook_data = {
                'id': webhook.id,
                'name': webhook.name,
                'url': webhook.url,
                'method': webhook.method,
                'content_type': webhook.content_type,
                'enabled': webhook.enabled,
                'auth_type': webhook.auth_type,
                'trigger_events': webhook.trigger_events,
                'custom_payload_template': webhook.custom_payload_template,
                'include_alert_data': webhook.include_alert_data,
                'include_analysis_data': webhook.include_analysis_data,
                'include_ai_analysis': webhook.include_ai_analysis,
                'custom_headers': webhook.custom_headers,
                'max_retries': webhook.max_retries,
                'retry_delay': webhook.retry_delay,
                'timeout': webhook.timeout,
                'description': webhook.description,
                'company_id': webhook.company_id,
                'company_name': webhook.company.name if webhook.company else None,
                # Filter fields
                'filter_clients': [c.id for c in webhook.filter_clients.all()],
                'filter_alert_types': webhook.filter_alert_types,
                'filter_severity_levels': webhook.filter_severity_levels,
                'filter_rule_ids': webhook.filter_rule_ids,
                'filter_agent_ids': webhook.filter_agent_ids,
                'filter_statuses': webhook.filter_statuses,
                # Stats
                'total_sent': webhook.total_sent,
                'last_sent_at': webhook.last_sent_at.isoformat() if webhook.last_sent_at else None,
                'last_error': webhook.last_error,
                'created_at': webhook.created_at.isoformat(),
                'updated_at': webhook.updated_at.isoformat(),
            }
            
            return JsonResponse({
                'success': True,
                'webhook': webhook_data
            })
            
        except Exception as e:
            logger.error(f"Error loading webhook details: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to load webhook details'
            }, status=500)
    
    elif request.method == 'PUT':
        try:
            from .views import get_user_accessible_companies
            data = json.loads(request.body)
            
            # Update webhook fields
            if 'name' in data:
                webhook.name = data['name']
            if 'url' in data:
                webhook.url = data['url']
            if 'method' in data:
                webhook.method = data['method']
            if 'content_type' in data:
                webhook.content_type = data['content_type']
            if 'enabled' in data:
                webhook.enabled = data['enabled']
            if 'auth_type' in data:
                webhook.auth_type = data['auth_type']
            if 'trigger_events' in data:
                webhook.trigger_events = data['trigger_events']
            if 'custom_payload_template' in data:
                webhook.custom_payload_template = data['custom_payload_template']
            if 'include_alert_data' in data:
                webhook.include_alert_data = data['include_alert_data']
            if 'include_analysis_data' in data:
                webhook.include_analysis_data = data['include_analysis_data']
            if 'include_ai_analysis' in data:
                webhook.include_ai_analysis = data['include_ai_analysis']
            if 'custom_headers' in data:
                webhook.custom_headers = data['custom_headers']
            if 'max_retries' in data:
                webhook.max_retries = data['max_retries']
            if 'retry_delay' in data:
                webhook.retry_delay = data['retry_delay']
            if 'timeout' in data:
                webhook.timeout = data['timeout']
            if 'description' in data:
                webhook.description = data['description']
            
            # Update company if provided
            if 'company_id' in data:
                from app_conf.models import Company
                try:
                    company = Company.objects.get(id=data['company_id'])
                    
                    # Check if user has access to this company
                    accessible_companies = get_user_accessible_companies(request.user)
                    if accessible_companies is not None:  # Not a superuser with full access
                        if not accessible_companies or company not in accessible_companies:
                            return JsonResponse({
                                'success': False,
                                'error': 'You do not have permission to assign webhooks to this company'
                            }, status=403)
                    
                    webhook.company = company
                except Company.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid company ID'
                    }, status=400)
            
            # Update filter fields
            if 'filter_alert_types' in data:
                webhook.filter_alert_types = data['filter_alert_types']
            if 'filter_severity_levels' in data:
                webhook.filter_severity_levels = data['filter_severity_levels']
            if 'filter_rule_ids' in data:
                webhook.filter_rule_ids = data['filter_rule_ids']
            if 'filter_agent_ids' in data:
                webhook.filter_agent_ids = data['filter_agent_ids']
            if 'filter_statuses' in data:
                webhook.filter_statuses = data['filter_statuses']
            
            webhook.save()
            
            # Update filter clients (ManyToMany field) after save
            if 'filter_clients' in data:
                webhook.filter_clients.set(data['filter_clients'])
            
            # Update authentication data if provided
            if 'auth_data' in data:
                webhook.set_auth_data(data['auth_data'])
                webhook.save()
            
            logger.info(f"Updated outgoing webhook: {webhook.name} by {request.user.username}")
            
            return JsonResponse({
                'success': True,
                'message': 'Webhook updated successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error updating webhook: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update webhook'
            }, status=500)
    
    elif request.method == 'DELETE':
        try:
            webhook_name = webhook.name
            webhook.delete()
            
            logger.info(f"Deleted outgoing webhook: {webhook_name} by {request.user.username}")
            
            return JsonResponse({
                'success': True,
                'message': 'Webhook deleted successfully'
            })
            
        except Exception as e:
            logger.error(f"Error deleting webhook: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete webhook'
            }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
@fim_api_access_required('configure')
def test_outgoing_webhook_api(request, webhook_id):
    """API endpoint for testing an outgoing webhook"""
    
    try:
        from .views import get_user_accessible_companies
        
        # Get user's accessible companies based on AccessFIM configuration
        accessible_companies = get_user_accessible_companies(request.user)
        
        if accessible_companies is None:
            # User has access to all companies
            webhook = OutgoingWebhook.objects.get(id=webhook_id, enabled=True)
        elif accessible_companies:
            # User has access only to specific companies
            webhook = OutgoingWebhook.objects.get(id=webhook_id, enabled=True, company__in=accessible_companies)
        else:
            # User has no access to any companies
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to test webhooks'
            }, status=403)
            
    except OutgoingWebhook.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Webhook not found, disabled, or you do not have permission to access it'
        }, status=404)
    
    try:
        # Create test alert data
        test_alert_data = {
            'alert_id': 'test_alert_' + str(int(time.time())),
            'rule_name': 'Test FIM Alert',
            'description': 'This is a test FIM alert for webhook testing',
            'level': 2,
            'file_path': '/etc/test/sample.conf',
            'file_name': 'sample.conf',
            'operation': 'modified',
            'agent_name': 'test-agent',
            'agent_ip': '192.168.1.100',
            'timestamp': timezone.now().isoformat(),
            'received_at': timezone.now().isoformat(),
            'file_hash_md5': 'test_md5_hash',
            'file_hash_sha1': 'test_sha1_hash',
            'file_hash_sha256': 'test_sha256_hash',
        }
        
        # Build test payload
        test_payload = {
            'event_type': 'fim_alert_test',
            'test': True,
            'timestamp': timezone.now().isoformat(),
            'webhook_name': webhook.name,
            'alert': test_alert_data,
            'message': 'This is a test webhook from SecBoard FIM system'
        }
        
        # Send webhook
        result = send_webhook(webhook, test_payload, test_alert=True)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'message': 'Test webhook sent successfully',
                'response_time_ms': result.get('response_time_ms'),
                'status_code': result.get('status_code')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f"Test webhook failed: {result['error']}"
            }, status=400)
            
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to test webhook'
        }, status=500)


def send_webhook(webhook, payload, test_alert=False, alert=None):
    """Send webhook with payload"""
    start_time = time.time()
    
    try:
        # Prepare headers
        headers = webhook.get_headers()
        
        # Prepare payload based on content type
        if webhook.content_type == 'application/json':
            data = json.dumps(payload)
        elif webhook.content_type == 'application/x-www-form-urlencoded':
            import urllib.parse
            data = urllib.parse.urlencode(payload)
        else:  # text/plain
            data = str(payload)
        
        # Send request
        response = requests.request(
            method=webhook.method,
            url=webhook.url,
            data=data,
            headers=headers,
            timeout=webhook.timeout
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Update webhook statistics
        if not test_alert:
            webhook.total_sent += 1
            webhook.last_sent_at = timezone.now()
            webhook.last_error = ''  # Clear previous error
            webhook.save()
        
        # Log the webhook attempt
        log_entry = OutgoingWebhookLog.objects.create(
            webhook=webhook,
            alert=alert,
            url=webhook.url,
            method=webhook.method,
            payload=payload,
            headers=dict(headers),
            status_code=response.status_code,
            response_body=response.text[:1000],  # Limit response body
            response_time_ms=response_time_ms,
            status='success' if response.status_code < 400 else 'failed',
            error_message='' if response.status_code < 400 else f'HTTP {response.status_code}: {response.text[:500]}'
        )
        
        if response.status_code >= 400:
            error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
            if not test_alert:
                webhook.last_error = error_msg
                webhook.save()
            
            logger.warning(f"Webhook {webhook.name} failed: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'status_code': response.status_code,
                'response_time_ms': response_time_ms
            }
        
        logger.info(f"Webhook {webhook.name} sent successfully: {response.status_code}")
        return {
            'success': True,
            'status_code': response.status_code,
            'response_time_ms': response_time_ms,
            'response_body': response.text[:200]
        }
        
    except requests.exceptions.Timeout:
        error_msg = f'Webhook timeout after {webhook.timeout} seconds'
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Log failed attempt
        OutgoingWebhookLog.objects.create(
            webhook=webhook,
            alert=alert,
            url=webhook.url,
            method=webhook.method,
            payload=payload,
            headers=webhook.get_headers(),
            status='failed',
            error_message=error_msg,
            response_time_ms=response_time_ms
        )
        
        if not test_alert:
            webhook.last_error = error_msg
            webhook.save()
        
        logger.error(f"Webhook {webhook.name} timeout: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'response_time_ms': response_time_ms
        }
        
    except Exception as e:
        error_msg = f'Webhook error: {str(e)}'
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Log failed attempt
        OutgoingWebhookLog.objects.create(
            webhook=webhook,
            alert=alert,
            url=webhook.url,
            method=webhook.method,
            payload=payload,
            headers=webhook.get_headers(),
            status='failed',
            error_message=error_msg,
            response_time_ms=response_time_ms
        )
        
        if not test_alert:
            webhook.last_error = error_msg
            webhook.save()
        
        logger.error(f"Webhook {webhook.name} error: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'response_time_ms': response_time_ms
        }


def send_fim_alert_webhooks(alert, event_type='new_alert', analysis_results=None, ai_analysis=None):
    """Send webhooks for FIM alert events"""
    
    try:
        # Get all enabled webhooks that should trigger for this event
        webhooks = OutgoingWebhook.objects.filter(enabled=True)
        
        sent_count = 0
        failed_count = 0
        
        for webhook in webhooks:
            if webhook.should_trigger_for_alert(alert, event_type):
                try:
                    # Build payload for this webhook
                    payload = webhook.build_payload(alert, analysis_results, ai_analysis)
                    payload['event_type'] = event_type
                    
                    # Send webhook
                    result = send_webhook(webhook, payload, alert=alert)
                    
                    if result['success']:
                        sent_count += 1
                        logger.info(f"Sent webhook {webhook.name} for alert {alert.alert_id}")
                    else:
                        failed_count += 1
                        logger.error(f"Failed to send webhook {webhook.name} for alert {alert.alert_id}: {result['error']}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error sending webhook {webhook.name} for alert {alert.alert_id}: {str(e)}")
        
        if sent_count > 0 or failed_count > 0:
            logger.info(f"FIM alert {alert.alert_id} webhooks: {sent_count} sent, {failed_count} failed")
        
        return {
            'sent': sent_count,
            'failed': failed_count
        }
        
    except Exception as e:
        logger.error(f"Error sending FIM alert webhooks: {str(e)}")
        return {
            'sent': 0,
            'failed': 1
        }


@require_http_methods(["GET"])
@fim_api_access_required('configure')
def companies_api(request):
    """API endpoint for getting list of companies accessible to user based on AccessFIM"""
    try:
        from app_conf.models import Company
        from .views import get_user_accessible_companies
        
        # Get user's accessible companies based on AccessFIM configuration
        accessible_companies = get_user_accessible_companies(request.user)
        
        if accessible_companies is None:
            # User has access to all companies (superuser or no restrictions)
            companies = Company.objects.all().order_by('name')
            companies_data = []
            for company in companies:
                companies_data.append({
                    'id': company.id,
                    'name': company.name,
                })
        elif accessible_companies:
            # User has access only to specific companies defined in AccessFIM
            companies_data = []
            for company in accessible_companies:
                companies_data.append({
                    'id': company.id,
                    'name': company.name,
                })
            companies_data.sort(key=lambda x: x['name'])  # Sort by name
        else:
            # User has no access to any companies
            companies_data = []
        
        return JsonResponse({
            'success': True,
            'companies': companies_data
        })
        
    except Exception as e:
        logger.error(f"Error loading companies: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to load companies'
        }, status=500)


@require_http_methods(["GET"])
@fim_api_access_required('configure')
def alert_webhooks_api(request, alert_id):
    """API endpoint for getting webhook logs for a specific alert"""
    try:
        from app_soc.models import WazuhFIMAlert
        
        # Get the alert
        try:
            alert = WazuhFIMAlert.objects.get(alert_id=alert_id)
        except WazuhFIMAlert.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Alert not found'
            }, status=404)
        
        # Get webhook logs for this alert
        webhook_logs = OutgoingWebhookLog.objects.filter(
            alert=alert
        ).order_by('-created_at')
        
        webhook_data = []
        for log in webhook_logs:
            webhook_data.append({
                'webhook_name': log.webhook.name,
                'webhook_url': log.webhook.url,
                'sent_at': log.created_at.isoformat(),
                'status_code': log.status_code,
                'success': log.status == 'success',
                'response_time_ms': log.response_time_ms,
                'error_message': log.error_message
            })
        
        return JsonResponse({
            'success': True,
            'alert_id': alert_id,
            'webhook_logs': webhook_data,
            'total_sent': len([w for w in webhook_data if w['success']]),
            'total_failed': len([w for w in webhook_data if not w['success']])
        })
        
    except Exception as e:
        logger.error(f"Error loading alert webhook logs: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to load webhook logs'
        }, status=500)


@require_http_methods(["GET"])
@fim_api_access_required('configure')
def webhook_clients_api(request):
    """API endpoint for getting list of webhook clients accessible to user"""
    try:
        from .views import get_user_accessible_companies
        
        # Get user's accessible companies based on AccessFIM configuration
        accessible_companies = get_user_accessible_companies(request.user)
        
        if accessible_companies is None:
            # User has access to all companies
            clients = WebhookClient.objects.all().order_by('name')
        elif accessible_companies:
            # User has access only to specific companies
            clients = WebhookClient.objects.filter(company__in=accessible_companies).order_by('name')
        else:
            # User has no access to any companies
            clients = WebhookClient.objects.none()
        
        clients_data = []
        for client in clients:
            clients_data.append({
                'id': client.id,
                'name': client.name,
                'description': client.description or '',
                'company_name': client.company.name if client.company else 'No Company',
            })
        
        return JsonResponse({
            'success': True,
            'clients': clients_data
        })
        
    except Exception as e:
        logger.error(f"Error loading webhook clients: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to load webhook clients'
        }, status=500)
