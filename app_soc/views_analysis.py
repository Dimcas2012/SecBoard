import json
import uuid
import logging
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import WazuhFIMAlert, AnalysisResult, AnalysisConfig
from .views import fim_access_required

logger = logging.getLogger(__name__)

# Import webhook sending functionality
try:
    from .outgoing_webhook_views import send_fim_alert_webhooks
except ImportError:
    # Fallback if import fails
    def send_fim_alert_webhooks(*args, **kwargs):
        pass


@csrf_exempt
@login_required
@fim_access_required()
def analysis_results_api(request, alert_id):
    """API endpoint for getting analysis results for a specific alert"""
    if request.method == 'GET':
        try:
            # Get the alert
            try:
                alert = WazuhFIMAlert.objects.get(alert_id=alert_id)
            except WazuhFIMAlert.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Alert not found'
                }, status=404)
            
            # Get analysis results for this alert
            results = AnalysisResult.objects.filter(alert=alert).order_by('-created_at')
            results_data = []
            
            for result in results:
                results_data.append({
                    'id': result.id,
                    'analysis_id': result.analysis_id,
                    'analysis_service': result.analysis_service,
                    'hash_type': result.hash_type,
                    'hash_value': result.hash_value,
                    'status': result.status,
                    'threat_level': result.threat_level,
                    'detections': result.detections,
                    'total_engines': result.total_engines,
                    'detection_rate': result.detection_rate,
                    'analysis_url': result.analysis_url,
                    'permalink': result.permalink,
                    'scan_date': result.scan_date.isoformat() if result.scan_date else None,
                    'created_at': result.created_at.isoformat(),
                    'analyzed_by': result.analyzed_by.username if result.analyzed_by else None,
                    'engine_results': result.engine_results,
                    'file_info': result.file_info,
                    'behavior_analysis': result.behavior_analysis,
                })
            
            return JsonResponse({
                'success': True,
                'results': results_data
            })
        except Exception as e:
            logger.error(f"Error getting analysis results: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis results'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def save_analysis_result_api(request):
    """API endpoint for saving analysis results"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['alert_id', 'analysis_service', 'hash_type', 'hash_value']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }, status=400)
            
            # Get the alert
            try:
                alert = WazuhFIMAlert.objects.get(alert_id=data['alert_id'])
            except WazuhFIMAlert.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Alert not found'
                }, status=404)
            
            # Generate unique analysis ID
            analysis_id = f"{data['hash_type']}_{data['hash_value'][:16]}_{uuid.uuid4().hex[:8]}"
            
            # Create analysis result
            result = AnalysisResult.objects.create(
                analysis_id=analysis_id,
                alert=alert,
                analysis_service=data['analysis_service'],
                hash_type=data['hash_type'],
                hash_value=data['hash_value'],
                status=data.get('status', 'completed'),
                threat_level=data.get('threat_level'),
                detections=data.get('detections', 0),
                total_engines=data.get('total_engines', 0),
                analysis_url=data.get('analysis_url', ''),
                permalink=data.get('permalink', ''),
                scan_date=data.get('scan_date'),
                engine_results=data.get('engine_results'),
                file_info=data.get('file_info'),
                behavior_analysis=data.get('behavior_analysis'),
                raw_response=data.get('raw_response'),
                analyzed_by=request.user,
            )
            
            
            # Send outgoing webhooks for analysis completion
            try:
                # Get all analysis results for this alert
                analysis_results = AnalysisResult.objects.filter(alert=alert)
                webhook_result = send_fim_alert_webhooks(alert, 'analysis_complete', analysis_results=analysis_results)
                if webhook_result['sent'] > 0:
                    logger.info(f"Sent {webhook_result['sent']} analysis webhooks for alert {alert.alert_id}")
                if webhook_result['failed'] > 0:
                    logger.warning(f"Failed to send {webhook_result['failed']} analysis webhooks")
            except Exception as e:
                logger.error(f"Error sending analysis webhooks: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'analysis_id': result.analysis_id,
                'result_id': result.id,
                'message': 'Analysis result saved successfully'
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error saving analysis result: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to save analysis result'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def analysis_result_detail_api(request, analysis_id):
    """API endpoint for getting detailed analysis result information"""
    if request.method == 'GET':
        try:
            # Get the analysis result
            try:
                result = AnalysisResult.objects.get(analysis_id=analysis_id)
            except AnalysisResult.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Analysis result not found'
                }, status=404)
            
            # Prepare detailed data
            detailed_data = {
                'id': result.id,
                'analysis_id': result.analysis_id,
                'alert': {
                    'alert_id': result.alert.alert_id,
                    'rule_name': result.alert.rule_name,
                    'description': result.alert.description,
                    'file_path': result.alert.file_path,
                    'file_name': result.alert.file_name,
                    'agent_name': result.alert.agent_name,
                    'agent_ip': result.alert.agent_ip,
                    'timestamp': result.alert.timestamp.isoformat(),
                    'received_at': result.alert.received_at.isoformat(),
                },
                'analysis_service': result.analysis_service,
                'hash_type': result.hash_type,
                'hash_value': result.hash_value,
                'status': result.status,
                'threat_level': result.threat_level,
                'detections': result.detections,
                'total_engines': result.total_engines,
                'detection_rate': result.detection_rate,
                'analysis_url': result.analysis_url,
                'permalink': result.permalink,
                'scan_date': result.scan_date.isoformat() if result.scan_date else None,
                'created_at': result.created_at.isoformat(),
                'updated_at': result.updated_at.isoformat(),
                'analyzed_by': {
                    'username': result.analyzed_by.username if result.analyzed_by else None,
                    'first_name': result.analyzed_by.first_name if result.analyzed_by else None,
                    'last_name': result.analyzed_by.last_name if result.analyzed_by else None,
                },
                'engine_results': result.engine_results,
                'file_info': result.file_info,
                'behavior_analysis': result.behavior_analysis,
                'raw_response': result.raw_response,
            }
            
            return JsonResponse({
                'success': True,
                'result': detailed_data
            })
        except Exception as e:
            logger.error(f"Error getting analysis result detail: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis result detail'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def analysis_results_by_hash_api(request, hash_type, hash_value):
    """API endpoint for getting analysis results for a specific hash with pagination"""
    if request.method == 'GET':
        try:
            from django.core.paginator import Paginator
            
            # Get pagination parameters
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 5))
            
            # Get analysis results for this hash
            results_queryset = AnalysisResult.objects.filter(
                hash_type=hash_type,
                hash_value=hash_value
            ).order_by('-created_at')
            
            # Apply pagination
            paginator = Paginator(results_queryset, per_page)
            page_obj = paginator.get_page(page)
            
            results_data = []
            
            for result in page_obj:
                results_data.append({
                    'id': result.id,
                    'analysis_id': result.analysis_id,
                    'alert': {
                        'alert_id': result.alert.alert_id,
                        'rule_name': result.alert.rule_name,
                        'description': result.alert.description,
                        'file_path': result.alert.file_path,
                        'file_name': result.alert.file_name,
                        'agent_name': result.alert.agent_name,
                        'agent_ip': result.alert.agent_ip,
                        'timestamp': result.alert.timestamp.isoformat(),
                        'received_at': result.alert.received_at.isoformat(),
                    },
                    'analysis_service': result.analysis_service,
                    'hash_type': result.hash_type,
                    'hash_value': result.hash_value,
                    'status': result.status,
                    'threat_level': result.threat_level,
                    'detections': result.detections,
                    'total_engines': result.total_engines,
                    'detection_rate': result.detection_rate,
                    'analysis_url': result.analysis_url,
                    'permalink': result.permalink,
                    'scan_date': result.scan_date.isoformat() if result.scan_date else None,
                    'created_at': result.created_at.isoformat(),
                    'analyzed_by': result.analyzed_by.username if result.analyzed_by else None,
                    'engine_results': result.engine_results,
                    'file_info': result.file_info,
                    'behavior_analysis': result.behavior_analysis,
                })
            
            return JsonResponse({
                'success': True,
                'hash_type': hash_type,
                'hash_value': hash_value,
                'results': results_data,
                'pagination': {
                    'current_page': page_obj.number,
                    'total_pages': paginator.num_pages,
                    'per_page': per_page,
                    'total_count': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                    'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                    'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
                }
            })
        except Exception as e:
            logger.error(f"Error getting analysis results by hash: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get analysis results by hash'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def debug_analysis_config_api(request, config_id):
    """Debug endpoint to check analysis configuration"""
    if request.method == 'GET':
        try:
            config = AnalysisConfig.objects.get(id=config_id)
            
            # Test credential decryption
            credential_status = "No credential"
            if config.encrypted_credential:
                try:
                    credential = config.get_credential()
                    if credential:
                        credential_status = f"Credential decrypted successfully (length: {len(credential)})"
                    else:
                        credential_status = "Failed to decrypt credential"
                except Exception as e:
                    credential_status = f"Error decrypting credential: {str(e)}"
            
            return JsonResponse({
                'success': True,
                'config': {
                    'id': config.id,
                    'name': config.name,
                    'url': config.url,
                    'method': config.method,
                    'enabled': config.enabled,
                    'timeout': config.timeout,
                    'has_encrypted_credential': bool(config.encrypted_credential),
                    'credential_status': credential_status
                }
            })
        except AnalysisConfig.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Configuration not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Debug error: {str(e)}'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


@csrf_exempt
@login_required
@fim_access_required()
def execute_analysis_api(request):
    """API endpoint for executing external analysis services (e.g., VirusTotal)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['config_id', 'hash_type', 'hash_value', 'alert_id']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }, status=400)
            
            # Get the analysis configuration
            try:
                config = AnalysisConfig.objects.get(id=data['config_id'], enabled=True)
            except AnalysisConfig.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Analysis configuration not found or disabled'
                }, status=404)
            
            # Get the alert
            try:
                alert = WazuhFIMAlert.objects.get(alert_id=data['alert_id'])
            except WazuhFIMAlert.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Alert not found'
                }, status=404)
            
            # Execute the analysis
            try:
                analysis_result = execute_external_analysis(config, data['hash_type'], data['hash_value'])
                
                if not analysis_result['success']:
                    # Check if it's a "not found" error (404) - this is normal, not an error
                    if 'not found' in analysis_result['error'].lower():
                        return JsonResponse({
                            'success': True,
                            'analysis_data': {
                                'service': config.name,
                                'hash_type': data['hash_type'].upper(),
                                'hash_value': data['hash_value'],
                                'status': 'not_found',
                                'threat_level': 'unknown',
                                'detections': 0,
                                'total_engines': 0,
                                'detection_rate': 0,
                                'scan_date': timezone.now().isoformat(),
                                'analysis_url': f"https://www.virustotal.com/gui/file/{data['hash_value']}",
                                'permalink': f"https://www.virustotal.com/gui/file/{data['hash_value']}",
                                'engine_results': {},
                                'file_info': {},
                                'behavior_analysis': {},
                                'raw_response': {'error': analysis_result['error']}
                            },
                            'message': 'Hash not found in analysis service database'
                        })
                    else:
                        # This is a real error
                        logger.error(f"Analysis execution failed: {analysis_result['error']}")
                        return JsonResponse({
                            'success': False,
                            'error': analysis_result['error']
                        }, status=500)
            except Exception as e:
                logger.error(f"Error executing external analysis: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Analysis execution failed: {str(e)}'
                }, status=500)
            
            # Save the analysis result
            try:
                # Generate unique analysis ID
                analysis_id = f"{data['hash_type']}_{data['hash_value'][:16]}_{uuid.uuid4().hex[:8]}"
                
                # Create analysis result
                result = AnalysisResult.objects.create(
                    analysis_id=analysis_id,
                    alert=alert,
                    analysis_service=config.name,
                    hash_type=data['hash_type'],
                    hash_value=data['hash_value'],
                    status=analysis_result['data'].get('status', 'completed'),
                    threat_level=analysis_result['data'].get('threat_level'),
                    detections=analysis_result['data'].get('detections', 0),
                    total_engines=analysis_result['data'].get('total_engines', 0),
                    analysis_url=analysis_result['data'].get('analysis_url', ''),
                    permalink=analysis_result['data'].get('permalink', ''),
                    scan_date=analysis_result['data'].get('scan_date'),
                    engine_results=analysis_result['data'].get('engine_results'),
                    file_info=analysis_result['data'].get('file_info'),
                    behavior_analysis=analysis_result['data'].get('behavior_analysis'),
                    raw_response=analysis_result['data'].get('raw_response'),
                    analyzed_by=request.user,
                )
                
                # Send outgoing webhooks for analysis completion
                try:
                    analysis_results = AnalysisResult.objects.filter(alert=alert)
                    webhook_result = send_fim_alert_webhooks(alert, 'analysis_complete', analysis_results=analysis_results)
                    if webhook_result['sent'] > 0:
                        logger.info(f"Sent {webhook_result['sent']} analysis webhooks for alert {alert.alert_id}")
                    if webhook_result['failed'] > 0:
                        logger.warning(f"Failed to send {webhook_result['failed']} analysis webhooks")
                except Exception as e:
                    logger.error(f"Error sending analysis webhooks: {str(e)}")
                
                return JsonResponse({
                    'success': True,
                    'analysis_id': result.analysis_id,
                    'result_id': result.id,
                    'analysis_data': analysis_result['data'],
                    'message': 'Analysis completed successfully'
                })
                
            except Exception as e:
                logger.error(f"Error saving analysis result: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to save analysis result'
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error executing analysis: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Failed to execute analysis: {str(e)}'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)


def execute_external_analysis(config, hash_type, hash_value):
    """Execute external analysis using the provided configuration"""
    try:
        # Check if requests library is available
        if not hasattr(requests, 'get'):
            return {
                'success': False,
                'error': 'Requests library not available'
            }
        # Build the URL by replacing template variables
        url = config.url
        
        # Validate URL
        if not url:
            return {
                'success': False,
                'error': 'Analysis configuration URL is empty'
            }
        
        # Replace template variables based on hash type
        if hash_type == 'sha256':
            url = url.replace('{{ json.sha256 }}', hash_value)
            url = url.replace('{{ $json.sha256 }}', hash_value)
        elif hash_type == 'sha1':
            url = url.replace('{{ json.sha1 }}', hash_value)
            url = url.replace('{{ $json.sha1 }}', hash_value)
        elif hash_type == 'md5':
            url = url.replace('{{ json.md5 }}', hash_value)
            url = url.replace('{{ $json.md5 }}', hash_value)
        
        # Generic hash replacement
        url = url.replace('{{ hash }}', hash_value)
        url = url.replace('{{ $hash }}', hash_value)
        
        # Validate final URL
        if not url or url == config.url:
            return {
                'success': False,
                'error': 'Failed to replace template variables in URL'
            }
        
        # Prepare headers
        headers = {
            'User-Agent': 'SecBoard/1.0'
        }
        
        # Add API key if configured
        if config.encrypted_credential:
            try:
                # Decrypt the credential
                credential = config.get_credential()
                if credential:
                    # For VirusTotal, add X-Apikey header
                    if 'virustotal' in config.name.lower():
                        headers['X-Apikey'] = credential
                    else:
                        # Generic API key header
                        headers['Authorization'] = f'Bearer {credential}'
                else:
                    logger.warning(f"Failed to decrypt credential for config {config.name}")
            except Exception as e:
                logger.error(f"Error decrypting credential for config {config.name}: {str(e)}")
                return {
                    'success': False,
                    'error': f'Failed to decrypt API credential: {str(e)}'
                }
        
        # Make the API request
        if config.method.upper() == 'GET':
            response = requests.get(url, headers=headers, timeout=config.timeout)
        elif config.method.upper() == 'POST':
            response = requests.post(url, headers=headers, timeout=config.timeout)
        else:
            return {
                'success': False,
                'error': f'Unsupported HTTP method: {config.method}'
            }
        
        # Check response status
        if response.status_code == 200:
            try:
                data = response.json()
                return parse_virustotal_response(data, config.name, hash_type, hash_value)
            except json.JSONDecodeError:
                return {
                    'success': False,
                    'error': 'Invalid JSON response from analysis service'
                }
        elif response.status_code == 404:
            return {
                'success': False,
                'error': 'Hash not found in analysis service database'
            }
        elif response.status_code == 429:
            return {
                'success': False,
                'error': 'Rate limit exceeded. Please try again later.'
            }
        elif response.status_code == 403:
            return {
                'success': False,
                'error': 'Access forbidden. Check API credentials.'
            }
        else:
            return {
                'success': False,
                'error': f'Analysis service returned status {response.status_code}: {response.text}'
            }
            
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': 'Analysis request timed out'
        }
    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': 'Failed to connect to analysis service'
        }
    except Exception as e:
        logger.error(f"Error executing external analysis: {str(e)}")
        return {
            'success': False,
            'error': f'Analysis execution failed: {str(e)}'
        }


def parse_virustotal_response(data, service_name, hash_type, hash_value):
    """Parse VirusTotal API response and extract relevant information"""
    try:
        # Extract basic information
        stats = data.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
        engines = data.get('data', {}).get('attributes', {}).get('last_analysis_results', {})
        file_info = data.get('data', {}).get('attributes', {})
        
        # Calculate detection rate
        detections = stats.get('malicious', 0) + stats.get('suspicious', 0)
        total_engines = sum(stats.values())
        detection_rate = (detections / total_engines * 100) if total_engines > 0 else 0
        
        # Determine threat level
        if detections == 0:
            threat_level = 'clean'
        elif detections <= 2:
            threat_level = 'low'
        elif detections <= 5:
            threat_level = 'medium'
        else:
            threat_level = 'high'
        
        # Format engine results
        engine_results = {}
        for engine, result in engines.items():
            if isinstance(result, dict):
                engine_results[engine] = {
                    'category': result.get('category', 'clean'),
                    'result': result.get('result', 'Clean'),
                    'method': result.get('method', ''),
                    'engine_version': result.get('engine_version', ''),
                    'engine_update': result.get('engine_update', '')
                }
            else:
                engine_results[engine] = {'result': str(result)}
        
        # Extract file information
        file_info_data = {
            'size': file_info.get('size'),
            'type': file_info.get('type_description', file_info.get('type_extension')),
            'magic': file_info.get('magic'),
            'md5': file_info.get('md5'),
            'sha1': file_info.get('sha1'),
            'sha256': file_info.get('sha256'),
            'first_seen': file_info.get('first_submission_date'),
            'last_seen': file_info.get('last_analysis_date')
        }
        
        # Extract behavior analysis if available
        behavior_analysis = {}
        if 'behaviour' in file_info:
            behavior_analysis['behavior'] = file_info['behaviour']
        if 'network' in file_info:
            behavior_analysis['network'] = file_info['network']
        
        # Convert scan_date to proper format
        scan_date = file_info.get('last_analysis_date')
        if scan_date:
            try:
                # If it's a timestamp (integer), convert to datetime
                if isinstance(scan_date, (int, float)):
                    from datetime import datetime
                    scan_date = datetime.fromtimestamp(scan_date).isoformat()
                elif isinstance(scan_date, str):
                    # If it's already a string, try to parse and reformat
                    try:
                        from datetime import datetime
                        # Try to parse various formats
                        for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']:
                            try:
                                dt = datetime.strptime(scan_date, fmt)
                                scan_date = dt.isoformat()
                                break
                            except ValueError:
                                continue
                    except:
                        # If parsing fails, use current time
                        scan_date = timezone.now().isoformat()
                else:
                    scan_date = timezone.now().isoformat()
            except Exception as e:
                logger.warning(f"Error processing scan_date: {e}")
                scan_date = timezone.now().isoformat()
        else:
            scan_date = timezone.now().isoformat()
        
        return {
            'success': True,
            'data': {
                'service': service_name,
                'hash_type': hash_type.upper(),
                'hash_value': hash_value,
                'status': 'completed',
                'threat_level': threat_level,
                'detections': detections,
                'total_engines': total_engines,
                'detection_rate': round(detection_rate, 2),
                'scan_date': scan_date,
                'analysis_url': f"https://www.virustotal.com/gui/file/{hash_value}",
                'permalink': f"https://www.virustotal.com/gui/file/{hash_value}",
                'engine_results': engine_results,
                'file_info': file_info_data,
                'behavior_analysis': behavior_analysis,
                'raw_response': data
            }
        }
        
    except Exception as e:
        logger.error(f"Error parsing VirusTotal response: {str(e)}")
        return {
            'success': False,
            'error': f'Failed to parse analysis response: {str(e)}'
        }


def get_previous_analysis_for_prompt(alert_data, previous_analysis_details):
    """Get previous analysis results formatted for AI prompt inclusion"""
    try:
        # Get available hashes from alert data
        hashes = []
        if alert_data.get('file_hash_sha256'):
            hashes.append(('SHA256', alert_data['file_hash_sha256']))
        if alert_data.get('file_hash_sha1'):
            hashes.append(('SHA1', alert_data['file_hash_sha1']))
        if alert_data.get('file_hash_md5'):
            hashes.append(('MD5', alert_data['file_hash_md5']))
        
        if not hashes:
            return None
            
        results_text = ""
        found_results = False
        
        for hash_type, hash_value in hashes:
            # Get previous analysis results for this hash
            previous_results = AnalysisResult.objects.filter(
                hash_type=hash_type,
                hash_value=hash_value
            ).order_by('-created_at')[:3]  # Get latest 3 results
            
            if previous_results:
                found_results = True
                results_text += f"\nPrevious Analysis Results ({hash_type}: {hash_value}):\n"
                
                for i, result in enumerate(previous_results, 1):
                    results_text += f"\nAnalysis #{i} ({result.created_at.strftime('%Y-%m-%d %H:%M')}):\n"
                    
                    # Include analysis services if requested
                    if previous_analysis_details.get('analysis_services', False):
                        results_text += f"- Service: {result.analysis_service}\n"
                        if result.analyzed_by:
                            results_text += f"- Analyzed by: {result.analyzed_by.username}\n"
                    
                    # Include hash information if requested
                    if previous_analysis_details.get('hash_info', False):
                        results_text += f"- Hash Type: {result.hash_type}\n"
                        results_text += f"- Hash Value: {result.hash_value}\n"
                    
                    # Include detection rate if requested
                    if previous_analysis_details.get('detection_rate', False):
                        if result.detections is not None and result.total_engines is not None:
                            results_text += f"- Detection Rate: {result.detections}/{result.total_engines} engines ({result.detection_rate}%)\n"
                        results_text += f"- Threat Level: {result.threat_level}\n"
                        results_text += f"- Status: {result.status}\n"
                    
                    # Include engine results if requested
                    if previous_analysis_details.get('engine_results', False) and result.engine_results:
                        try:
                            engine_results = json.loads(result.engine_results) if isinstance(result.engine_results, str) else result.engine_results
                            if engine_results:
                                results_text += "- Engine Results:\n"
                                for engine, details in list(engine_results.items())[:5]:  # Limit to first 5 engines
                                    if isinstance(details, dict):
                                        detection = details.get('category', details.get('result', 'Clean'))
                                    else:
                                        detection = str(details)
                                    results_text += f"  • {engine}: {detection}\n"
                        except (json.JSONDecodeError, AttributeError):
                            results_text += "- Engine Results: Available but not parseable\n"
                    
                    # Include file information if requested
                    if previous_analysis_details.get('file_information', False) and result.file_info:
                        try:
                            file_info = json.loads(result.file_info) if isinstance(result.file_info, str) else result.file_info
                            if file_info:
                                results_text += "- File Information:\n"
                                for key, value in file_info.items():
                                    if key in ['size', 'type', 'magic', 'md5', 'sha1', 'sha256']:
                                        results_text += f"  • {key}: {value}\n"
                        except (json.JSONDecodeError, AttributeError):
                            results_text += "- File Information: Available but not parseable\n"
                    
                    # Include behavior analysis if requested
                    if previous_analysis_details.get('behavior_analysis', False) and result.behavior_analysis:
                        try:
                            behavior_info = json.loads(result.behavior_analysis) if isinstance(result.behavior_analysis, str) else result.behavior_analysis
                            if behavior_info:
                                results_text += "- Behavior Analysis:\n"
                                # Include key behavioral indicators
                                for key, value in behavior_info.items():
                                    if key in ['behavior', 'network', 'filesystem', 'registry', 'processes']:
                                        results_text += f"  • {key}: {value}\n"
                        except (json.JSONDecodeError, AttributeError):
                            results_text += "- Behavior Analysis: Available but not parseable\n"
                    
                    # Add scan date and URLs if available
                    if result.scan_date:
                        results_text += f"- Scan Date: {result.scan_date.strftime('%Y-%m-%d %H:%M')}\n"
                    if result.analysis_url:
                        results_text += f"- Analysis URL: {result.analysis_url}\n"
                
                # Stop after finding results for first hash type to avoid too much data
                break
        
        if not found_results:
            return None
            
        return results_text
        
    except Exception as e:
        logger.error(f"Error getting previous analysis for prompt: {str(e)}")
        return None