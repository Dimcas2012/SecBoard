import json
import logging
import base64
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from .models import WazuhFIMAlert, WazuhAgent, WebhookClient, WebhookAuthConfig, AccessFIM, AnalysisConfig

logger = logging.getLogger(__name__)


def validate_webhook_authentication(request, auth_config):
    """
    Validate webhook authentication based on the configured auth type
    """
    try:
        auth_data = auth_config.get_auth_data()
        
        if auth_config.auth_type == 'basic':
            # Validate Basic Authentication
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Basic '):
                logger.warning("Missing or invalid Basic auth header")
                return False
            
            # Extract and decode credentials
            try:
                encoded_credentials = auth_header.split(' ')[1]
                decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
                username, password = decoded_credentials.split(':', 1)
                
                # Compare with stored credentials
                stored_username = auth_data.get('username', '')
                stored_password = auth_data.get('password', '')
                
                if username == stored_username and password == stored_password:
                    logger.info(f"Basic auth successful for user: {username}")
                    return True
                else:
                    logger.warning(f"Basic auth failed for user: {username}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error decoding Basic auth: {str(e)}")
                return False
        
        elif auth_config.auth_type == 'token':
            # Validate API Token
            header_name = auth_data.get('header_name', 'Authorization')
            expected_token = auth_data.get('token', '')
            
            if not expected_token:
                logger.warning("No token configured for token authentication")
                return False
            
            # Get token from header
            token_value = request.META.get(f'HTTP_{header_name.upper().replace("-", "_")}', '')
            
            # Also check Authorization header if header_name is Authorization
            if header_name.lower() == 'authorization' and not token_value:
                auth_header = request.META.get('HTTP_AUTHORIZATION', '')
                if auth_header.startswith('Bearer '):
                    token_value = auth_header.split(' ', 1)[1]
                elif auth_header.startswith('Token '):
                    token_value = auth_header.split(' ', 1)[1]
                else:
                    token_value = auth_header
            
            if token_value == expected_token:
                logger.info(f"Token auth successful for header: {header_name}")
                return True
            else:
                logger.warning(f"Token auth failed for header: {header_name}")
                return False
        
        elif auth_config.auth_type == 'custom':
            # Validate Custom Header
            header_name = auth_data.get('header_name', '')
            expected_value = auth_data.get('header_value', '')
            
            if not header_name or not expected_value:
                logger.warning("Custom header name or value not configured")
                return False
            
            # Get header value
            header_value = request.META.get(f'HTTP_{header_name.upper().replace("-", "_")}', '')
            
            if header_value == expected_value:
                logger.info(f"Custom header auth successful for header: {header_name}")
                return True
            else:
                logger.warning(f"Custom header auth failed for header: {header_name}")
                return False
        
        else:
            logger.warning(f"Unknown authentication type: {auth_config.auth_type}")
            return False
            
    except Exception as e:
        logger.error(f"Error validating webhook authentication: {str(e)}")
        return False


def get_user_accessible_companies(user):
    """
    Get companies accessible to user based on AccessFIM model
    Returns None if user has access to all companies, or set of companies if restricted
    """
    if not user.is_authenticated:
        return set()
    
    accessible_companies = set()
    user_groups = user.groups.all()
    
    for group in user_groups:
        try:
            access_fim = AccessFIM.objects.get(group=group)
            if access_fim.has_access:
                if not access_fim.companies.exists():
                    # User has access to all companies
                    return None
                else:
                    # User has access only to specific companies
                    accessible_companies.update(access_fim.companies.all())
        except AccessFIM.DoesNotExist:
            continue
    
    return accessible_companies


def check_fim_access(user, required_permission=None):
    """
    Check if user has access to FIM dashboard based on AccessFIM model
    """
    if not user.is_authenticated:
        return False
    
    # Get user groups
    user_groups = user.groups.all()
    if not user_groups.exists():
        return False
    
    # Check if any of user's groups have FIM access
    for group in user_groups:
        try:
            access_fim = AccessFIM.objects.get(group=group)
            if access_fim.has_access:
                # If specific permission is required, check it
                if required_permission:
                    if required_permission == 'edit' and not access_fim.can_edit:
                        continue
                    elif required_permission == 'add' and not access_fim.can_add:
                        continue
                    elif required_permission == 'delete' and not access_fim.can_delete:
                        continue
                    elif required_permission == 'configure' and not access_fim.can_configure:
                        continue
                
                return True
        except AccessFIM.DoesNotExist:
            continue
    
    return False


def fim_access_required(permission=None):
    """
    Decorator to check FIM dashboard access
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not check_fim_access(request.user, permission):
                raise PermissionDenied("You don't have permission to access FIM dashboard")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@csrf_exempt
def wazuh_fim_webhook(request):
    """
    Webhook endpoint to receive FIM alerts from Wazuh
    """
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken'
        return response
    
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


# Analysis Configuration API Views
@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_api(request):
    """API endpoint for analysis configuration CRUD operations"""
    if request.method == 'GET':
        # Get all analysis configurations
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            configs = AnalysisConfig.objects.all().order_by('name')
            configs_data = []
            
            for config in configs:
                configs_data.append({
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                })
            
            return JsonResponse({
                'success': True,
                'configurations': configs_data
            })
        except Exception as e:
            logger.error(f"Error getting analysis configurations: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configurations'
            }, status=500)
    
    elif request.method == 'POST':
        # Create new analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to create analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists
            if AnalysisConfig.objects.filter(name=data['name']).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Create configuration
            config = AnalysisConfig.objects.create(
                name=data['name'],
                method=data['method'],
                url=data['url'],
                enabled=data.get('enabled', True),
                timeout=data.get('timeout', 30),
                created_by=request.user
            )
            
            # Set credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
                config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error creating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_detail_api(request, config_id):
    """API endpoint for individual analysis configuration operations"""
    try:
        config = AnalysisConfig.objects.get(id=config_id)
    except AnalysisConfig.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Analysis configuration not found'
        }, status=404)
    
    if request.method == 'GET':
        # Get analysis configuration details
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                }
            })
        except Exception as e:
            logger.error(f"Error getting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configuration'
            }, status=500)
    
    elif request.method == 'PUT':
        # Update analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to update analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists (excluding current config)
            if AnalysisConfig.objects.filter(name=data['name']).exclude(id=config.id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Update configuration
            config.name = data['name']
            config.method = data['method']
            config.url = data['url']
            config.enabled = data.get('enabled', True)
            config.timeout = data.get('timeout', 30)
            
            # Update credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
            
            config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'updated_at': config.updated_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error updating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update analysis configuration'
            }, status=500)
    
    elif request.method == 'DELETE':
        # Delete analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to delete analysis configurations'
                }, status=403)
            
            config.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Analysis configuration deleted successfully'
            })
        except Exception as e:
            logger.error(f"Error deleting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)
    
    try:
        # Parse JSON data from request
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                # Try to handle malformed JSON or different encodings
                print("❌ JSON Parse Error - trying alternative parsing...")
                print(f"🔍 Error: {str(e)}")
                print(f"📦 Raw body: {request.body}")
                
                # Try different encodings
                try:
                    body_text = request.body.decode('utf-8')
                    data = json.loads(body_text)
                except UnicodeDecodeError:
                    try:
                        body_text = request.body.decode('latin-1')
                        data = json.loads(body_text)
                    except:
                        raise e
                except json.JSONDecodeError:
                    raise e
        else:
            print(f"❌ Wrong Content-Type: {request.content_type}")
            print("📋 Expected: application/json")
            print("🔍 Trying to parse as form data...")
            
            # Try to handle form data or URL-encoded data
            try:
                if request.content_type == 'application/x-www-form-urlencoded':
                    # Handle URL-encoded data
                    form_data = request.POST
                    if 'data' in form_data:
                        data = json.loads(form_data['data'])
                    else:
                        return JsonResponse({'error': 'No data field in form'}, status=400)
                elif 'multipart/form-data' in request.content_type:
                    # Handle multipart form data
                    if 'data' in request.POST:
                        data = json.loads(request.POST['data'])
                    else:
                        return JsonResponse({'error': 'No data field in multipart form'}, status=400)
                else:
                    return JsonResponse({'error': 'Content-Type must be application/json'}, status=400)
            except Exception as e:
                print(f"❌ Failed to parse form data: {str(e)}")
                return JsonResponse({'error': 'Invalid data format'}, status=400)
        
        # Log ALL incoming data without filtering
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        
        print("=" * 80)
        print(f"🔔 WEBHOOK REQUEST RECEIVED")
        print(f"📅 Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 From IP: {client_ip}")
        print(f"🔧 User-Agent: {user_agent}")
        print(f"📏 Content-Length: {len(request.body)} bytes")
        print(f"📋 Content-Type: {request.content_type}")
        print("=" * 80)
        
        # Log complete raw data
        print("📦 COMPLETE RAW DATA:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("=" * 80)
        
        # Also log to Django logger
        logger.info(f"WEBHOOK REQUEST from {client_ip} - Data keys: {list(data.keys())}")
        logger.info(f"Complete data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Handle Wazuh Elasticsearch format - check for _source wrapper
        if '_source' in data:
            # Wazuh sends data in Elasticsearch format with _source wrapper
            source_data = data['_source']
            print("🔍 FORMAT: Elasticsearch with _source wrapper")
            print(f"📋 Alert ID: {source_data.get('id', 'unknown')}")
            logger.info(f"Received Wazuh Elasticsearch format alert: {source_data.get('id', 'unknown')}")
        else:
            # Direct format (for testing)
            source_data = data
            print("🔍 FORMAT: Direct format")
            print(f"📋 Alert ID: {source_data.get('id', 'unknown')}")
            logger.info(f"Received direct format alert: {source_data.get('id', 'unknown')}")
        
        # Validate required fields
        required_fields = ['id', 'rule', 'agent', 'timestamp']
        for field in required_fields:
            if field not in source_data:
                print("❌ VALIDATION ERROR: Missing required field")
                print(f"🔍 Missing field: {field}")
                print(f"📋 Available fields: {list(source_data.keys())}")
                print("=" * 80)
                return JsonResponse({'error': f'Missing required field: {field}'}, status=400)
        
        # Extract alert data from source
        alert_id = str(source_data['id'])
        rule_data = source_data.get('rule', {})
        agent_data = source_data.get('agent', {})
        timestamp_str = source_data.get('timestamp')
        
        # Parse timestamp
        try:
            # Wazuh timestamps are typically in format: "2024-01-15T10:30:45.123Z"
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except ValueError:
            timestamp = timezone.now()
        
        # Extract file information
        file_data = source_data.get('syscheck', {})
        file_path = file_data.get('path', '')
        file_name = file_data.get('name', '')
        
        # Determine alert type based on Wazuh data
        alert_type = 'modified'  # default
        
        # First try to get from syscheck event field
        syscheck_event = file_data.get('event', '')
        if syscheck_event in ['added', 'modified', 'deleted', 'read']:
            alert_type = syscheck_event
        else:
            # Fallback to description parsing
            description = source_data.get('description', '').lower()
            if 'added' in description:
                alert_type = 'added'
            elif 'deleted' in description:
                alert_type = 'deleted'
            elif 'read' in description:
                alert_type = 'read'
        
        # Check if alert already exists
        if WazuhFIMAlert.objects.filter(alert_id=alert_id).exists():
            print("⚠️  DUPLICATE: Alert already exists, skipping")
            print(f"📋 Alert ID: {alert_id}")
            print("=" * 80)
            logger.warning(f"Alert {alert_id} already exists, skipping")
            return JsonResponse({'status': 'duplicate', 'message': 'Alert already exists'})
        
        # Create or update agent information
        agent_id = str(agent_data.get('id', ''))
        agent_name = agent_data.get('name', 'Unknown Agent')
        agent_ip = agent_data.get('ip', '127.0.0.1')
        
        # Handle empty agent_id
        if not agent_id or agent_id == 'None':
            agent_id = f"unknown_{int(timezone.now().timestamp())}"
            print(f"⚠️  Empty agent_id detected, using generated ID: {agent_id}")
        
        agent, created = WazuhAgent.objects.get_or_create(
            agent_id=agent_id,
            defaults={
                'agent_name': agent_name,
                'agent_ip': agent_ip,
                'agent_version': agent_data.get('version'),
                'platform': agent_data.get('platform'),
                'os_name': agent_data.get('os', {}).get('name'),
                'os_version': agent_data.get('os', {}).get('version'),
                'metadata': agent_data,
            }
        )
        
        if not created:
            # Update last seen timestamp
            agent.last_seen = timezone.now()
            agent.save()
        
        # Try to find webhook client by agent IP (for legacy webhook)
        webhook_client = None
        try:
            webhook_client = WebhookClient.objects.filter(ip_address=agent_ip).first()
            
            # If webhook client found, validate authentication
            if webhook_client:
                auth_config = webhook_client.get_auth_config()
                if auth_config and auth_config.enabled and auth_config.auth_type != 'none':
                    logger.info(f"Legacy webhook: Client {webhook_client.client_id} has authentication configured: {auth_config.auth_type}")
                    
                    # Validate authentication
                    if not validate_webhook_authentication(request, auth_config):
                        logger.warning(f"Legacy webhook: Authentication failed for client {webhook_client.client_id}")
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Authentication failed'
                        }, status=401)
                    
                    logger.info(f"Legacy webhook: Authentication successful for client {webhook_client.client_id}")
                    
        except Exception as e:
            logger.error(f"Error finding webhook client: {str(e)}")
            pass
        
        # Create FIM alert
        fim_alert = WazuhFIMAlert.objects.create(
            alert_id=alert_id,
            rule_id=rule_data.get('id', 0),
            rule_name=rule_data.get('description', 'Unknown Rule'),
            level=rule_data.get('level', 5),
            description=rule_data.get('description', ''),
            file_path=file_path,
            file_name=file_name,
            file_size=file_data.get('size_after') or file_data.get('size'),
            file_hash_md5=file_data.get('md5_after') or file_data.get('md5'),
            file_hash_sha1=file_data.get('sha1_after') or file_data.get('sha1'),
            file_hash_sha256=file_data.get('sha256_after') or file_data.get('sha256'),
            alert_type=alert_type,
            agent_id=agent_id,
            agent_name=agent_name,
            agent_ip=agent_ip,
            client=webhook_client,  # Link to webhook client if found
            timestamp=timestamp,
            raw_data=data,  # Keep original data for debugging
            tags=source_data.get('tags', []),
        )
        
        logger.info(f"Created FIM alert {alert_id} for file {file_name}")
        
        # Log success result
        print("✅ SUCCESS: Alert processed and stored")
        print(f"📋 Alert ID: {alert_id}")
        print(f"📁 File: {file_name}")
        print(f"🤖 Agent: {agent_name} ({agent_id})")
        print(f"📊 Level: {rule_data.get('level', 'unknown')}")
        print(f"📝 Rule Description: {rule_data.get('description', 'No description')}")
        print("=" * 80)
        
        # Return success response
        response = JsonResponse({
            'status': 'success',
            'message': 'Alert received and stored',
            'alert_id': alert_id,
            'created_at': fim_alert.received_at.isoformat()
        })
        response['Access-Control-Allow-Origin'] = '*'
        return response
        
    except json.JSONDecodeError as e:
        print("❌ ERROR: Invalid JSON data received")
        print(f"🔍 JSON Error: {str(e)}")
        print(f"📦 Raw body (first 1000 chars):")
        print(request.body.decode('utf-8', errors='ignore')[:1000])
        print("=" * 80)
        print(f"📏 Total body length: {len(request.body)} bytes")
        print(f"📋 Content-Type: {request.content_type}")
        print("=" * 80)
        logger.error(f"Invalid JSON data received: {str(e)}")
        logger.error(f"Raw body: {request.body.decode('utf-8', errors='ignore')}")
        response = JsonResponse({'error': 'Invalid JSON data'}, status=400)
        response['Access-Control-Allow-Origin'] = '*'
        return response
    
    except Exception as e:
        print("❌ ERROR: Exception occurred during processing")
        print(f"🔍 Error: {str(e)}")
        print(f"📦 Request data: {request.body.decode('utf-8', errors='ignore')[:1000]}...")
        print("=" * 80)
        logger.error(f"Error processing Wazuh FIM alert: {str(e)}")
        logger.error(f"Request data: {request.body.decode('utf-8', errors='ignore')[:1000]}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        response = JsonResponse({'error': 'Internal server error'}, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        return response


@login_required
@fim_access_required()
def fim_alerts_dashboard(request):
    """
    Dashboard view to display FIM alerts with pagination
    """
    try:
        from django.core.paginator import Paginator
        
        # Get pagination parameters
        page = request.GET.get('page', 1)
        per_page = request.GET.get('per_page', 50)
        
        # Validate per_page parameter
        try:
            per_page = int(per_page)
            if per_page < 10:
                per_page = 10
            elif per_page > 200:
                per_page = 200
        except (ValueError, TypeError):
            per_page = 50
        
        # Get user's accessible companies
        accessible_companies = get_user_accessible_companies(request.user)
        
        if accessible_companies is None:
            # User has access to all companies
            alerts_queryset = WazuhFIMAlert.objects.all().order_by('-timestamp')
            agents = WazuhAgent.objects.all()
            
            # Statistics for all companies
            total_alerts = WazuhFIMAlert.objects.count()
            critical_alerts = WazuhFIMAlert.objects.filter(level__lte=3).count()
            unprocessed_alerts = WazuhFIMAlert.objects.filter(processed=False).count()
        else:
            # User has access only to specific companies
            if accessible_companies:
                # Filter alerts by accessible companies
                alerts_queryset = WazuhFIMAlert.objects.filter(
                    client__company__in=accessible_companies
                ).order_by('-timestamp')
                
                # Get agents from accessible companies
                agents = WazuhAgent.objects.filter(
                    agent_id__in=WazuhFIMAlert.objects.filter(
                        client__company__in=accessible_companies
                    ).values_list('agent_id', flat=True).distinct()
                )
                
                # Statistics for accessible companies only
                total_alerts = WazuhFIMAlert.objects.filter(
                    client__company__in=accessible_companies
                ).count()
                critical_alerts = WazuhFIMAlert.objects.filter(
                    client__company__in=accessible_companies,
                    level__lte=3
                ).count()
                unprocessed_alerts = WazuhFIMAlert.objects.filter(
                    client__company__in=accessible_companies,
                    processed=False
                ).count()
            else:
                # User has no access to any companies
                alerts_queryset = WazuhFIMAlert.objects.none()
                agents = WazuhAgent.objects.none()
                total_alerts = 0
                critical_alerts = 0
                unprocessed_alerts = 0
        
        # Apply pagination
        paginator = Paginator(alerts_queryset, per_page)
        alerts = paginator.get_page(page)
        
        # Get user permissions
        user_permissions = {
            'can_configure': check_fim_access(request.user, 'configure'),
            'can_add': check_fim_access(request.user, 'add'),
            'can_delete': check_fim_access(request.user, 'delete'),
            'can_edit': check_fim_access(request.user, 'edit'),
        }
        
        context = {
            'alerts': alerts,
            'agents': agents,
            'total_alerts': total_alerts,
            'critical_alerts': critical_alerts,
            'unprocessed_alerts': unprocessed_alerts,
            'user_permissions': user_permissions,
            'current_page': page,
            'per_page': per_page,
            'paginator': paginator,
        }
        
        return render(request, 'app_soc/fim_dashboard.html', context)
    except Exception as e:
        logger.error(f"Error in fim_alerts_dashboard: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': 'Dashboard error'}, status=500)


def fim_alert_detail(request, alert_id):
    """
    Detailed view of a specific FIM alert
    """
    try:
        alert = WazuhFIMAlert.objects.get(alert_id=alert_id)
        context = {'alert': alert}
        return render(request, 'app_soc/fim_alert_detail.html', context)
    except WazuhFIMAlert.DoesNotExist:
        return JsonResponse({'error': 'Alert not found'}, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def mark_alert_processed(request, alert_id):
    """
    Mark an alert as processed
    """
    try:
        # Handle empty or invalid alert_id
        if not alert_id or alert_id == 'None':
            return JsonResponse({'error': 'Invalid alert ID'}, status=400)
            
        alert = WazuhFIMAlert.objects.get(alert_id=alert_id)
        alert.processed = True
        alert.processed_at = timezone.now()
        alert.save()
        
        logger.info(f"Alert {alert_id} marked as processed")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Alert marked as processed',
            'alert_id': alert_id,
            'processed_at': alert.processed_at.isoformat()
        })
    except WazuhFIMAlert.DoesNotExist:
        logger.warning(f"Attempted to mark non-existent alert as processed: {alert_id}")
        return JsonResponse({'error': 'Alert not found'}, status=404)
    except Exception as e:
        logger.error(f"Error marking alert as processed: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def agent_detail(request, agent_id):
    """
    Detailed view of a specific agent and its alerts
    """
    try:
        # Handle empty or invalid agent_id
        if not agent_id or agent_id == 'None':
            return JsonResponse({'error': 'Invalid agent ID'}, status=400)
            
        agent = WazuhAgent.objects.get(agent_id=agent_id)
        recent_alerts = agent.get_recent_alerts(days=30)
        
        context = {
            'agent': agent,
            'recent_alerts': recent_alerts,
            'alert_count': agent.get_alert_count(),
        }
        return render(request, 'app_soc/agent_detail.html', context)
    except WazuhAgent.DoesNotExist:
        return JsonResponse({'error': 'Agent not found'}, status=404)


def alert_stats_api(request):
    """
    API endpoint to get current alert statistics for real-time updates
    """
    try:
        # Get current statistics
        total_alerts = WazuhFIMAlert.objects.count()
        critical_alerts = WazuhFIMAlert.objects.filter(level__lte=3).count()
        unprocessed_alerts = WazuhFIMAlert.objects.filter(processed=False).count()
        active_agents = WazuhAgent.objects.count()
        
        # Get recent alerts (last 5 minutes)
        from datetime import timedelta
        recent_time = timezone.now() - timedelta(minutes=5)
        recent_alerts = WazuhFIMAlert.objects.filter(
            received_at__gte=recent_time
        ).count()
        
        return JsonResponse({
            'success': True,
            'total_alerts': total_alerts,
            'critical_alerts': critical_alerts,
            'unprocessed_alerts': unprocessed_alerts,
            'active_agents': active_agents,
            'recent_alerts': recent_alerts,
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error in alert_stats_api: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get alert statistics'
        }, status=500)


# Webhook Client API Views
@csrf_exempt
@login_required
@fim_access_required()
def webhook_clients_api(request):
    """API endpoint for webhook clients CRUD operations"""
    if request.method == 'GET':
        # Get webhook clients accessible to user
        try:
            # Get user's accessible companies
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
                auth_config = client.get_auth_config()
                clients_data.append({
                    'id': client.client_id,
                    'name': client.name,
                    'ip_address': client.ip_address,
                    'port': client.port,
                    'protocol': client.protocol,
                    'client_type': client.client_type,
                    'environment': client.environment,
                    'description': client.description,
                    'enabled': client.enabled,
                    'webhook_url': client.get_webhook_url(),
                    'auth_type': auth_config.auth_type if auth_config else 'none',
                    'auth_enabled': auth_config.enabled if auth_config else False,
                    'company_id': client.company_id,
                    'company_name': client.company.name if client.company else None,
                    'created_at': client.created_at.isoformat(),
                    'updated_at': client.updated_at.isoformat(),
                })
            
            return JsonResponse({
                'success': True,
                'clients': clients_data
            })
        except Exception as e:
            logger.error(f"Error getting webhook clients: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get webhook clients'
            }, status=500)
    
    elif request.method == 'POST':
        # Create new webhook client - requires 'add' permission
        if not check_fim_access(request.user, 'add'):
            return JsonResponse({
                'success': False,
                'error': 'Permission denied: You need add permission to create webhook clients'
            }, status=403)
        
        try:
            data = json.loads(request.body)
            
            # Check if user has access to the selected company
            company_id = data.get('company_id')
            if company_id:
                from app_conf.models import Company
                try:
                    company = Company.objects.get(id=company_id)
                    # Check if user has access to this company
                    accessible_companies = get_user_accessible_companies(request.user)
                    
                    if accessible_companies is not None and company not in accessible_companies:
                        return JsonResponse({
                            'success': False,
                            'error': 'Permission denied: You do not have access to the selected company'
                        }, status=403)
                except Company.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid company selected'
                    }, status=400)
            
            # Generate unique client_id
            client_id = f"client_{int(timezone.now().timestamp())}"
            
            # Create client
            client = WebhookClient.objects.create(
                client_id=client_id,
                name=data.get('name'),
                ip_address=data.get('ip_address'),
                port=data.get('port', 8000),
                protocol=data.get('protocol', 'http'),
                client_type=data.get('client_type', 'wazuh'),
                environment=data.get('environment', 'production'),
                description=data.get('description', ''),
                enabled=data.get('enabled', True),
                company_id=company_id,
            )
            
            # Create default auth config
            WebhookAuthConfig.objects.create(
                client=client,
                auth_type='none',
                enabled=False
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Client created successfully',
                'client': {
                    'id': client.client_id,
                    'name': client.name,
                    'ip_address': client.ip_address,
                    'port': client.port,
                    'protocol': client.protocol,
                    'client_type': client.client_type,
                    'environment': client.environment,
                    'description': client.description,
                    'enabled': client.enabled,
                    'webhook_url': client.get_webhook_url(),
                    'company_id': client.company_id,
                    'company_name': client.company.name if client.company else None,
                }
            })
        except Exception as e:
            logger.error(f"Error creating webhook client: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to create client: {str(e)}'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


# Analysis Configuration API Views
@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_api(request):
    """API endpoint for analysis configuration CRUD operations"""
    if request.method == 'GET':
        # Get all analysis configurations
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            configs = AnalysisConfig.objects.all().order_by('name')
            configs_data = []
            
            for config in configs:
                configs_data.append({
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                })
            
            return JsonResponse({
                'success': True,
                'configurations': configs_data
            })
        except Exception as e:
            logger.error(f"Error getting analysis configurations: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configurations'
            }, status=500)
    
    elif request.method == 'POST':
        # Create new analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to create analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists
            if AnalysisConfig.objects.filter(name=data['name']).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Create configuration
            config = AnalysisConfig.objects.create(
                name=data['name'],
                method=data['method'],
                url=data['url'],
                enabled=data.get('enabled', True),
                timeout=data.get('timeout', 30),
                created_by=request.user
            )
            
            # Set credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
                config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error creating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_detail_api(request, config_id):
    """API endpoint for individual analysis configuration operations"""
    try:
        config = AnalysisConfig.objects.get(id=config_id)
    except AnalysisConfig.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Analysis configuration not found'
        }, status=404)
    
    if request.method == 'GET':
        # Get analysis configuration details
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                }
            })
        except Exception as e:
            logger.error(f"Error getting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configuration'
            }, status=500)
    
    elif request.method == 'PUT':
        # Update analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to update analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists (excluding current config)
            if AnalysisConfig.objects.filter(name=data['name']).exclude(id=config.id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Update configuration
            config.name = data['name']
            config.method = data['method']
            config.url = data['url']
            config.enabled = data.get('enabled', True)
            config.timeout = data.get('timeout', 30)
            
            # Update credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
            
            config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'updated_at': config.updated_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error updating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update analysis configuration'
            }, status=500)
    
    elif request.method == 'DELETE':
        # Delete analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to delete analysis configurations'
                }, status=403)
            
            config.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Analysis configuration deleted successfully'
            })
        except Exception as e:
            logger.error(f"Error deleting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required('configure')
def webhook_client_detail_api(request, client_id):
    """API endpoint for individual webhook client operations"""
    try:
        client = WebhookClient.objects.get(client_id=client_id)
    except WebhookClient.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Client not found'
        }, status=404)
    
    if request.method == 'GET':
        # Get client details
        auth_config = client.get_auth_config()
        return JsonResponse({
            'success': True,
            'client': {
                'id': client.client_id,
                'name': client.name,
                'ip_address': client.ip_address,
                'port': client.port,
                'protocol': client.protocol,
                'client_type': client.client_type,
                'environment': client.environment,
                'description': client.description,
                'enabled': client.enabled,
                'webhook_url': client.get_webhook_url(),
                'auth_type': auth_config.auth_type if auth_config else 'none',
                'auth_enabled': auth_config.enabled if auth_config else False,
                'company_id': client.company_id,
                'company_name': client.company.name if client.company else None,
                'created_at': client.created_at.isoformat(),
                'updated_at': client.updated_at.isoformat(),
            }
        })
    
    elif request.method == 'PUT':
        # Update client - requires 'configure' permission
        if not check_fim_access(request.user, 'configure'):
            return JsonResponse({
                'success': False,
                'error': 'Permission denied: You need configure permission to update webhook clients'
            }, status=403)
        
        try:
            data = json.loads(request.body)
            
            # Check if user has access to the selected company
            company_id = data.get('company_id', client.company_id)
            if company_id:
                from app_conf.models import Company
                try:
                    company = Company.objects.get(id=company_id)
                    # Check if user has access to this company
                    accessible_companies = get_user_accessible_companies(request.user)
                    
                    if accessible_companies is not None and company not in accessible_companies:
                        return JsonResponse({
                            'success': False,
                            'error': 'Permission denied: You do not have access to the selected company'
                        }, status=403)
                except Company.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Invalid company selected'
                    }, status=400)
            
            client.name = data.get('name', client.name)
            client.ip_address = data.get('ip_address', client.ip_address)
            client.port = data.get('port', client.port)
            client.protocol = data.get('protocol', client.protocol)
            client.client_type = data.get('client_type', client.client_type)
            client.environment = data.get('environment', client.environment)
            client.description = data.get('description', client.description)
            client.enabled = data.get('enabled', client.enabled)
            client.company_id = company_id
            client.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Client updated successfully',
                'client': {
                    'id': client.client_id,
                    'name': client.name,
                    'ip_address': client.ip_address,
                    'port': client.port,
                    'protocol': client.protocol,
                    'client_type': client.client_type,
                    'environment': client.environment,
                    'description': client.description,
                    'enabled': client.enabled,
                    'webhook_url': client.get_webhook_url(),
                    'company_id': client.company_id,
                    'company_name': client.company.name if client.company else None,
                }
            })
        except Exception as e:
            logger.error(f"Error updating webhook client: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to update client: {str(e)}'
            }, status=500)
    
    elif request.method == 'DELETE':
        # Delete client - requires 'delete' permission
        if not check_fim_access(request.user, 'delete'):
            return JsonResponse({
                'success': False,
                'error': 'Permission denied: You need delete permission to remove webhook clients'
            }, status=403)
        
        try:
            client.delete()
            return JsonResponse({
                'success': True,
                'message': 'Client deleted successfully'
            })
        except Exception as e:
            logger.error(f"Error deleting webhook client: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to delete client: {str(e)}'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


# Analysis Configuration API Views
@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_api(request):
    """API endpoint for analysis configuration CRUD operations"""
    if request.method == 'GET':
        # Get all analysis configurations
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            configs = AnalysisConfig.objects.all().order_by('name')
            configs_data = []
            
            for config in configs:
                configs_data.append({
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                })
            
            return JsonResponse({
                'success': True,
                'configurations': configs_data
            })
        except Exception as e:
            logger.error(f"Error getting analysis configurations: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configurations'
            }, status=500)
    
    elif request.method == 'POST':
        # Create new analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to create analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists
            if AnalysisConfig.objects.filter(name=data['name']).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Create configuration
            config = AnalysisConfig.objects.create(
                name=data['name'],
                method=data['method'],
                url=data['url'],
                enabled=data.get('enabled', True),
                timeout=data.get('timeout', 30),
                created_by=request.user
            )
            
            # Set credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
                config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error creating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_detail_api(request, config_id):
    """API endpoint for individual analysis configuration operations"""
    try:
        config = AnalysisConfig.objects.get(id=config_id)
    except AnalysisConfig.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Analysis configuration not found'
        }, status=404)
    
    if request.method == 'GET':
        # Get analysis configuration details
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                }
            })
        except Exception as e:
            logger.error(f"Error getting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configuration'
            }, status=500)
    
    elif request.method == 'PUT':
        # Update analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to update analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists (excluding current config)
            if AnalysisConfig.objects.filter(name=data['name']).exclude(id=config.id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Update configuration
            config.name = data['name']
            config.method = data['method']
            config.url = data['url']
            config.enabled = data.get('enabled', True)
            config.timeout = data.get('timeout', 30)
            
            # Update credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
            
            config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'updated_at': config.updated_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error updating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update analysis configuration'
            }, status=500)
    
    elif request.method == 'DELETE':
        # Delete analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to delete analysis configurations'
                }, status=403)
            
            config.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Analysis configuration deleted successfully'
            })
        except Exception as e:
            logger.error(f"Error deleting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def companies_api(request):
    """API endpoint to get list of companies accessible to user"""
    if request.method == 'GET':
        try:
            from app_conf.models import Company
            
            # Get user's accessible companies
            accessible_companies = get_user_accessible_companies(request.user)
            
            if accessible_companies is None:
                # User has access to all companies
                companies = Company.objects.all().order_by('name')
                companies_data = []
                for company in companies:
                    companies_data.append({
                        'id': company.id,
                        'name': company.name,
                    })
            elif accessible_companies:
                # User has access only to specific companies
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
            logger.error(f"Error getting companies: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get companies'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


# Analysis Configuration API Views
@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_api(request):
    """API endpoint for analysis configuration CRUD operations"""
    if request.method == 'GET':
        # Get all analysis configurations
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            configs = AnalysisConfig.objects.all().order_by('name')
            configs_data = []
            
            for config in configs:
                configs_data.append({
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                })
            
            return JsonResponse({
                'success': True,
                'configurations': configs_data
            })
        except Exception as e:
            logger.error(f"Error getting analysis configurations: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configurations'
            }, status=500)
    
    elif request.method == 'POST':
        # Create new analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to create analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists
            if AnalysisConfig.objects.filter(name=data['name']).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Create configuration
            config = AnalysisConfig.objects.create(
                name=data['name'],
                method=data['method'],
                url=data['url'],
                enabled=data.get('enabled', True),
                timeout=data.get('timeout', 30),
                created_by=request.user
            )
            
            # Set credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
                config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error creating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_detail_api(request, config_id):
    """API endpoint for individual analysis configuration operations"""
    try:
        config = AnalysisConfig.objects.get(id=config_id)
    except AnalysisConfig.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Analysis configuration not found'
        }, status=404)
    
    if request.method == 'GET':
        # Get analysis configuration details
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                }
            })
        except Exception as e:
            logger.error(f"Error getting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configuration'
            }, status=500)
    
    elif request.method == 'PUT':
        # Update analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to update analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists (excluding current config)
            if AnalysisConfig.objects.filter(name=data['name']).exclude(id=config.id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Update configuration
            config.name = data['name']
            config.method = data['method']
            config.url = data['url']
            config.enabled = data.get('enabled', True)
            config.timeout = data.get('timeout', 30)
            
            # Update credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
            
            config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'updated_at': config.updated_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error updating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update analysis configuration'
            }, status=500)
    
    elif request.method == 'DELETE':
        # Delete analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to delete analysis configurations'
                }, status=403)
            
            config.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Analysis configuration deleted successfully'
            })
        except Exception as e:
            logger.error(f"Error deleting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required('configure')
def webhook_client_auth_api(request, client_id):
    """API endpoint for webhook client authentication configuration"""
    try:
        client = WebhookClient.objects.get(client_id=client_id)
    except WebhookClient.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Client not found'
        }, status=404)
    
    if request.method == 'GET':
        # Get auth configuration
        auth_config = client.get_auth_config()
        if auth_config:
            return JsonResponse({
                'success': True,
                'auth_config': {
                    'auth_type': auth_config.auth_type,
                    'enabled': auth_config.enabled,
                    'auth_data': auth_config.get_auth_data() if auth_config.enabled else {}
                }
            })
        else:
            return JsonResponse({
                'success': True,
                'auth_config': {
                    'auth_type': 'none',
                    'enabled': False,
                    'auth_data': {}
                }
            })
    
    elif request.method == 'POST':
        # Update auth configuration
        try:
            data = json.loads(request.body)
            
            # Get or create auth config
            auth_config, created = WebhookAuthConfig.objects.get_or_create(
                client=client,
                defaults={
                    'auth_type': 'none',
                    'enabled': False
                }
            )
            
            # Update auth config
            auth_config.auth_type = data.get('auth_type', 'none')
            auth_config.enabled = data.get('enabled', False)
            
            # Set auth data if provided
            auth_data = data.get('auth_data', {})
            if auth_data:
                auth_config.set_auth_data(auth_data)
            
            auth_config.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Authentication configuration updated successfully',
                'auth_config': {
                    'auth_type': auth_config.auth_type,
                    'enabled': auth_config.enabled,
                }
            })
        except Exception as e:
            logger.error(f"Error updating auth config: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to update auth config: {str(e)}'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


# Analysis Configuration API Views
@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_api(request):
    """API endpoint for analysis configuration CRUD operations"""
    if request.method == 'GET':
        # Get all analysis configurations
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            configs = AnalysisConfig.objects.all().order_by('name')
            configs_data = []
            
            for config in configs:
                configs_data.append({
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                })
            
            return JsonResponse({
                'success': True,
                'configurations': configs_data
            })
        except Exception as e:
            logger.error(f"Error getting analysis configurations: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configurations'
            }, status=500)
    
    elif request.method == 'POST':
        # Create new analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to create analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists
            if AnalysisConfig.objects.filter(name=data['name']).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Create configuration
            config = AnalysisConfig.objects.create(
                name=data['name'],
                method=data['method'],
                url=data['url'],
                enabled=data.get('enabled', True),
                timeout=data.get('timeout', 30),
                created_by=request.user
            )
            
            # Set credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
                config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error creating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_detail_api(request, config_id):
    """API endpoint for individual analysis configuration operations"""
    try:
        config = AnalysisConfig.objects.get(id=config_id)
    except AnalysisConfig.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Analysis configuration not found'
        }, status=404)
    
    if request.method == 'GET':
        # Get analysis configuration details
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                }
            })
        except Exception as e:
            logger.error(f"Error getting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configuration'
            }, status=500)
    
    elif request.method == 'PUT':
        # Update analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to update analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists (excluding current config)
            if AnalysisConfig.objects.filter(name=data['name']).exclude(id=config.id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Update configuration
            config.name = data['name']
            config.method = data['method']
            config.url = data['url']
            config.enabled = data.get('enabled', True)
            config.timeout = data.get('timeout', 30)
            
            # Update credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
            
            config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'updated_at': config.updated_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error updating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update analysis configuration'
            }, status=500)
    
    elif request.method == 'DELETE':
        # Delete analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to delete analysis configurations'
                }, status=403)
            
            config.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Analysis configuration deleted successfully'
            })
        except Exception as e:
            logger.error(f"Error deleting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
def client_fim_webhook(request, client_id):
    """
    Webhook endpoint for individual client FIM alerts
    This endpoint receives FIM alerts from a specific webhook client
    """
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken'
        return response
    
    if request.method != 'POST':
        response = JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)
        response['Access-Control-Allow-Origin'] = '*'
        return response
    
    try:
        # Get the webhook client
        try:
            client = WebhookClient.objects.get(client_id=client_id)
        except WebhookClient.DoesNotExist:
            logger.error(f"Webhook client not found: {client_id}")
            response = JsonResponse({
                'success': False,
                'error': f'Client {client_id} not found'
            }, status=404)
            response['Access-Control-Allow-Origin'] = '*'
            return response
        
        # Check if client is enabled
        if not client.enabled:
            logger.warning(f"Webhook client {client_id} is disabled")
            response = JsonResponse({
                'success': False,
                'error': f'Client {client_id} is disabled'
            }, status=403)
            response['Access-Control-Allow-Origin'] = '*'
            return response
        
        # Get authentication configuration and validate
        auth_config = client.get_auth_config()
        if auth_config and auth_config.enabled and auth_config.auth_type != 'none':
            logger.info(f"Client {client_id} has authentication configured: {auth_config.auth_type}")
            
            # Validate authentication
            if not validate_webhook_authentication(request, auth_config):
                logger.warning(f"Authentication failed for client {client_id}")
                response = JsonResponse({
                    'success': False,
                    'error': 'Authentication failed'
                }, status=401)
                response['Access-Control-Allow-Origin'] = '*'
                return response
            
            logger.info(f"Authentication successful for client {client_id}")
        
        # Process the webhook data (reuse existing logic from wazuh_fim_webhook)
        logger.info(f"Received FIM webhook from client: {client.name} ({client_id})")
        
        # Get the raw data
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                # Try to decode as JSON anyway
                data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON data received from client {client_id}: {str(e)}")
            logger.error(f"Raw body: {request.body}")
            logger.error(f"Content-Type: {request.content_type}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data received'
            }, status=400)
        
        # Check for _source wrapper (Elasticsearch format)
        if '_source' in data:
            source_data = data['_source']
            logger.info(f"Processing Elasticsearch format data from client {client_id}")
        else:
            source_data = data
            logger.info(f"Processing direct format data from client {client_id}")
        
        # Extract alert information
        alert_id = source_data.get('id', f"alert_{int(timezone.now().timestamp())}")
        rule_data = source_data.get('rule', {})
        file_data = source_data.get('syscheck', {})
        
        logger.info(f"Parsed alert info: alert_id={alert_id}, rule_id={rule_data.get('id')}, rule_desc={rule_data.get('description')}")
        
        # Extract file information
        file_path = file_data.get('path', 'Unknown')
        file_name = file_data.get('name', 'Unknown')
        
        # If name is not available, extract from path
        if file_name == 'Unknown' and file_path != 'Unknown':
            import os
            file_name = os.path.basename(file_path)
        
        logger.info(f"Parsed file info: path={file_path}, name={file_name}, size={file_data.get('size_after') or file_data.get('size')}")
        
        # Extract agent information
        agent_data = source_data.get('agent', {})
        agent_id = agent_data.get('id', f"unknown_{int(timezone.now().timestamp())}")
        agent_name = agent_data.get('name', 'Unknown Agent')
        agent_ip = agent_data.get('ip', '0.0.0.0')
        
        # Extract timestamp
        timestamp_str = source_data.get('@timestamp', source_data.get('timestamp'))
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                timestamp = timezone.now()
        else:
            timestamp = timezone.now()
        
        # Determine alert type
        alert_type = 'modified'  # Default
        
        # First try to get from syscheck event field
        syscheck_event = file_data.get('event', '')
        if syscheck_event in ['added', 'modified', 'deleted', 'read']:
            alert_type = syscheck_event
        else:
            # Fallback to description parsing
            description = source_data.get('description', '').lower()
            if 'added' in description:
                alert_type = 'added'
            elif 'deleted' in description:
                alert_type = 'deleted'
            elif 'read' in description:
                alert_type = 'read'
        
        # Create or update agent
        agent, created = WazuhAgent.objects.get_or_create(
            agent_id=agent_id,
            defaults={
                'agent_name': agent_name,
                'agent_ip': agent_ip,
                'status': 'active',
                'last_seen': timezone.now()
            }
        )
        
        if not created:
            agent.agent_name = agent_name
            agent.agent_ip = agent_ip
            agent.last_seen = timezone.now()
            agent.save()
        
        # Create FIM alert
        fim_alert = WazuhFIMAlert.objects.create(
            alert_id=alert_id,
            rule_id=rule_data.get('id', 0),
            rule_name=rule_data.get('description', 'Unknown Rule'),
            level=rule_data.get('level', 5),
            description=rule_data.get('description', ''),
            file_path=file_path,
            file_name=file_name,
            file_size=file_data.get('size_after') or file_data.get('size'),
            file_hash_md5=file_data.get('md5_after') or file_data.get('md5'),
            file_hash_sha1=file_data.get('sha1_after') or file_data.get('sha1'),
            file_hash_sha256=file_data.get('sha256_after') or file_data.get('sha256'),
            alert_type=alert_type,
            agent_id=agent_id,
            agent_name=agent_name,
            agent_ip=agent_ip,
            client=client,  # Link to the webhook client
            timestamp=timestamp,
            raw_data=data,
            tags=source_data.get('tags', []),
        )
        
        logger.info(f"Created FIM alert {alert_id} for file {file_name} from client {client.name}")
        
        # Log success result
        print("✅ SUCCESS: Alert processed and stored")
        print(f"📋 Alert ID: {alert_id}")
        print(f"📁 File: {file_name}")
        print(f"🤖 Agent: {agent_name} ({agent_id})")
        print(f"👤 Client: {client.name} ({client_id})")
        print(f"📊 Level: {rule_data.get('level', 'unknown')}")
        print(f"📝 Rule Description: {rule_data.get('description', 'No description')}")
        print("=" * 80)
        
        response = JsonResponse({
            'success': True,
            'message': 'Alert processed successfully',
            'alert_id': alert_id,
            'client_id': client_id,
            'client_name': client.name
        })
        response['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Exception as e:
        logger.error(f"Error processing webhook from client {client_id}: {str(e)}")
        response = JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        return response


@csrf_exempt
@login_required
@fim_access_required('edit')
def alert_details_api(request, alert_id):
    """API endpoint to get alert details for processing"""
    if request.method == 'GET':
        try:
            alert = WazuhFIMAlert.objects.get(alert_id=alert_id)
            logger.info(f"Retrieved alert {alert_id}: file_name={alert.file_name}, file_size={alert.file_size}, rule_id={alert.rule_id}")
            
            # Check if user has access to this alert's company
            accessible_companies = get_user_accessible_companies(request.user)
            if accessible_companies is not None and alert.client and alert.client.company:
                if alert.client.company not in accessible_companies:
                    return JsonResponse({
                        'success': False,
                        'error': 'Permission denied: You do not have access to this alert'
                    }, status=403)
            
            alert_data = {
                'alert_id': alert.alert_id,
                'file_name': alert.file_name,
                'file_path': alert.file_path,
                'file_size': alert.file_size,
                'file_hash_md5': alert.file_hash_md5,
                'file_hash_sha1': alert.file_hash_sha1,
                'file_hash_sha256': alert.file_hash_sha256,
                'alert_type': alert.alert_type,
                'rule_id': alert.rule_id,
                'rule_name': alert.rule_name,
                'level': alert.level,
                'description': alert.description,
                'agent_id': alert.agent_id,
                'agent_name': alert.agent_name,
                'agent_ip': alert.agent_ip,
                'timestamp': alert.timestamp.isoformat(),
                'client_name': alert.client.name if alert.client else 'Unknown',
                'client_type': alert.client.client_type if alert.client else 'Unknown',
                'environment': alert.client.environment if alert.client else 'Unknown',
                'company_name': alert.client.company.name if alert.client and alert.client.company else 'Unknown',
                'processing_status': alert.processing_status,
                'risk_assessment': alert.risk_assessment,
                'processed': alert.processed,
                'processed_by': alert.processed_by.username if alert.processed_by else None,
                'investigation_notes': alert.investigation_notes,
                'false_positive_reason': alert.false_positive_reason,
                'resolution_notes': alert.resolution_notes,
                'impact_description': alert.impact_description,
                'business_impact': alert.business_impact,
                'remediation_actions': alert.remediation_actions,
                'prevention_measures': alert.prevention_measures,
                'requires_followup': alert.requires_followup,
                'followup_date': alert.followup_date.isoformat() if alert.followup_date else None,
                'followup_notes': alert.followup_notes,
                'raw_data': alert.raw_data,
            }
            
            return JsonResponse({
                'success': True,
                'alert': alert_data
            })
        except WazuhFIMAlert.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Alert not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error getting alert details: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get alert details'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


# Analysis Configuration API Views
@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_api(request):
    """API endpoint for analysis configuration CRUD operations"""
    if request.method == 'GET':
        # Get all analysis configurations
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            configs = AnalysisConfig.objects.all().order_by('name')
            configs_data = []
            
            for config in configs:
                configs_data.append({
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                })
            
            return JsonResponse({
                'success': True,
                'configurations': configs_data
            })
        except Exception as e:
            logger.error(f"Error getting analysis configurations: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configurations'
            }, status=500)
    
    elif request.method == 'POST':
        # Create new analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to create analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists
            if AnalysisConfig.objects.filter(name=data['name']).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Create configuration
            config = AnalysisConfig.objects.create(
                name=data['name'],
                method=data['method'],
                url=data['url'],
                enabled=data.get('enabled', True),
                timeout=data.get('timeout', 30),
                created_by=request.user
            )
            
            # Set credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
                config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error creating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_detail_api(request, config_id):
    """API endpoint for individual analysis configuration operations"""
    try:
        config = AnalysisConfig.objects.get(id=config_id)
    except AnalysisConfig.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Analysis configuration not found'
        }, status=404)
    
    if request.method == 'GET':
        # Get analysis configuration details
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                }
            })
        except Exception as e:
            logger.error(f"Error getting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configuration'
            }, status=500)
    
    elif request.method == 'PUT':
        # Update analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to update analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists (excluding current config)
            if AnalysisConfig.objects.filter(name=data['name']).exclude(id=config.id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Update configuration
            config.name = data['name']
            config.method = data['method']
            config.url = data['url']
            config.enabled = data.get('enabled', True)
            config.timeout = data.get('timeout', 30)
            
            # Update credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
            
            config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'updated_at': config.updated_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error updating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update analysis configuration'
            }, status=500)
    
    elif request.method == 'DELETE':
        # Delete analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to delete analysis configurations'
                }, status=403)
            
            config.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Analysis configuration deleted successfully'
            })
        except Exception as e:
            logger.error(f"Error deleting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required('edit')
def alert_process_api(request, alert_id):
    """API endpoint to process an alert"""
    if request.method == 'POST':
        try:
            alert = WazuhFIMAlert.objects.get(alert_id=alert_id)
            
            # Check if user has access to this alert's company
            accessible_companies = get_user_accessible_companies(request.user)
            if accessible_companies is not None and alert.client and alert.client.company:
                if alert.client.company not in accessible_companies:
                    return JsonResponse({
                        'success': False,
                        'error': 'Permission denied: You do not have access to this alert'
                    }, status=403)
            
            data = json.loads(request.body)
            
            # Update alert fields
            alert.processing_status = data.get('processing_status', alert.processing_status)
            alert.risk_assessment = data.get('risk_assessment', alert.risk_assessment)
            alert.investigation_notes = data.get('investigation_notes', alert.investigation_notes)
            alert.false_positive_reason = data.get('false_positive_reason', alert.false_positive_reason)
            alert.resolution_notes = data.get('resolution_notes', alert.resolution_notes)
            alert.impact_description = data.get('impact_description', alert.impact_description)
            alert.business_impact = data.get('business_impact', alert.business_impact)
            alert.remediation_actions = data.get('remediation_actions', alert.remediation_actions)
            alert.prevention_measures = data.get('prevention_measures', alert.prevention_measures)
            alert.requires_followup = data.get('requires_followup', alert.requires_followup)
            alert.followup_notes = data.get('followup_notes', alert.followup_notes)
            
            # Handle followup date
            followup_date = data.get('followup_date')
            if followup_date:
                from datetime import datetime
                alert.followup_date = datetime.fromisoformat(followup_date)
            else:
                alert.followup_date = None
            
            # Mark as processed if status is resolved, false_positive, or ignored
            if alert.processing_status in ['resolved', 'false_positive', 'ignored']:
                alert.processed = True
                alert.processed_at = timezone.now()
                alert.processed_by = request.user
            
            alert.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Alert processing saved successfully'
            })
        except WazuhFIMAlert.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Alert not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error processing alert: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to process alert'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


# Analysis Configuration API Views
@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_api(request):
    """API endpoint for analysis configuration CRUD operations"""
    if request.method == 'GET':
        # Get all analysis configurations
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            configs = AnalysisConfig.objects.all().order_by('name')
            configs_data = []
            
            for config in configs:
                configs_data.append({
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                })
            
            return JsonResponse({
                'success': True,
                'configurations': configs_data
            })
        except Exception as e:
            logger.error(f"Error getting analysis configurations: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configurations'
            }, status=500)
    
    elif request.method == 'POST':
        # Create new analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to create analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists
            if AnalysisConfig.objects.filter(name=data['name']).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Create configuration
            config = AnalysisConfig.objects.create(
                name=data['name'],
                method=data['method'],
                url=data['url'],
                enabled=data.get('enabled', True),
                timeout=data.get('timeout', 30),
                created_by=request.user
            )
            
            # Set credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
                config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error creating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def analysis_config_detail_api(request, config_id):
    """API endpoint for individual analysis configuration operations"""
    try:
        config = AnalysisConfig.objects.get(id=config_id)
    except AnalysisConfig.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Analysis configuration not found'
        }, status=404)
    
    if request.method == 'GET':
        # Get analysis configuration details
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view analysis configurations'
                }, status=403)
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'created_at': config.created_at.isoformat(),
                    'updated_at': config.updated_at.isoformat(),
                    'created_by': config.created_by.username if config.created_by else None,
                }
            })
        except Exception as e:
            logger.error(f"Error getting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis configuration'
            }, status=500)
    
    elif request.method == 'PUT':
        # Update analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to update analysis configurations'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'method', 'url']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'success': False,
                        'error': f'Required field missing: {field}'
                    }, status=400)
            
            # Check if name already exists (excluding current config)
            if AnalysisConfig.objects.filter(name=data['name']).exclude(id=config.id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Configuration with this name already exists'
                }, status=400)
            
            # Update configuration
            config.name = data['name']
            config.method = data['method']
            config.url = data['url']
            config.enabled = data.get('enabled', True)
            config.timeout = data.get('timeout', 30)
            
            # Update credential if provided
            if data.get('credential'):
                config.set_credential(data['credential'])
            
            config.save()
            
            return JsonResponse({
                'success': True,
                'configuration': {
                    'id': config.id,
                    'name': config.name,
                    'method': config.method,
                    'url': config.url,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_credential': bool(config.encrypted_credential),
                    'updated_at': config.updated_at.isoformat(),
                }
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error updating analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update analysis configuration'
            }, status=500)
    
    elif request.method == 'DELETE':
        # Delete analysis configuration
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to delete analysis configurations'
                }, status=403)
            
            config.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Analysis configuration deleted successfully'
            })
        except Exception as e:
            logger.error(f"Error deleting analysis configuration: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete analysis configuration'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)
