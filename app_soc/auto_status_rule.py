import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import AutoStatusRule, WazuhFIMAlert

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
@login_required
def set_auto_status_rule(request):
    """
    Set auto-status rule for FIM alerts based on file name, path, or hash
    """
    try:
        data = json.loads(request.body)
        
        rule_type = data.get('type')
        rule_value = data.get('value')
        agent_name = data.get('agent')
        status = data.get('status')
        risk_assessment = data.get('risk_assessment', '')
        notes = data.get('notes', '')
        apply_to_existing = data.get('apply_to_existing', False)
        
        if not all([rule_type, rule_value, agent_name, status]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)
        
        # Create or update auto-status rule
        rule, created = AutoStatusRule.objects.get_or_create(
            rule_type=rule_type,
            rule_value=rule_value,
            agent_name=agent_name,
            defaults={
                'status': status,
                'risk_assessment': risk_assessment,
                'notes': notes,
                'created_by': request.user,
                'is_active': True
            }
        )
        
        if not created:
            # Update existing rule
            rule.status = status
            rule.risk_assessment = risk_assessment
            rule.notes = notes
            rule.is_active = True
            rule.save()
        
        # Apply to existing unprocessed alerts if requested
        if apply_to_existing:
            alerts_updated = 0
            
            # Get unprocessed alerts matching the rule
            alerts_query = WazuhFIMAlert.objects.filter(
                agent_name=agent_name,
                processing_status__in=['pending', 'unprocessed']
            )
            
            if rule_type == 'file_name':
                alerts_query = alerts_query.filter(file_name=rule_value)
            elif rule_type == 'file_path':
                alerts_query = alerts_query.filter(file_path=rule_value)
            elif rule_type == 'file_hash_md5':
                alerts_query = alerts_query.filter(file_hash_md5=rule_value)
            elif rule_type == 'file_hash_sha1':
                alerts_query = alerts_query.filter(file_hash_sha1=rule_value)
            elif rule_type == 'file_hash_sha256':
                alerts_query = alerts_query.filter(file_hash_sha256=rule_value)
            
            # Update matching alerts
            for alert in alerts_query:
                alert.processing_status = status
                if risk_assessment:
                    alert.risk_assessment = risk_assessment
                if notes:
                    alert.investigation_notes = notes
                alert.save()
                alerts_updated += 1
        
        return JsonResponse({
            'success': True,
            'rule_id': rule.id,
            'created': created,
            'alerts_updated': alerts_updated if apply_to_existing else 0,
            'message': f'Auto-status rule {"created" if created else "updated"} successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error setting auto-status rule: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to set auto-status rule'
        }, status=500)


@require_http_methods(["GET"])
@login_required
def get_alert_status_history(request, alert_id):
    """
    Get status history for a specific FIM alert
    """
    try:
        # Get the alert
        alert = WazuhFIMAlert.objects.get(alert_id=alert_id)
        
        # Create status history entries
        status_history = []
        
        # Add creation entry
        status_history.append({
            'status': 'created',
            'status_display': 'Alert Created',
            'timestamp': alert.timestamp.isoformat() if alert.timestamp else None,
            'processed_by': 'System',
            'notes': 'FIM alert received from Wazuh'
        })
        
        # Add processing status changes
        if alert.processing_status and alert.processing_status != 'pending':
            processed_by_name = 'Auto-Status Rule'
            if alert.processed_by:
                if hasattr(alert.processed_by, 'get_full_name'):
                    full_name = alert.processed_by.get_full_name()
                    if full_name and full_name.strip():
                        processed_by_name = f"{full_name} (Auto-Rule)"
                    else:
                        processed_by_name = f"{alert.processed_by.username} (Auto-Rule)"
                elif hasattr(alert.processed_by, 'username'):
                    processed_by_name = f"{alert.processed_by.username} (Auto-Rule)"
                else:
                    processed_by_name = f"{str(alert.processed_by)} (Auto-Rule)"
            
            status_history.append({
                'status': alert.processing_status,
                'status_display': alert.get_processing_status_display(),
                'timestamp': alert.processed_at.isoformat() if alert.processed_at else alert.timestamp.isoformat() if alert.timestamp else None,
                'processed_by': processed_by_name,
                'notes': alert.investigation_notes or 'Status updated by auto-status rule'
            })
        
        # Add risk assessment if available
        if alert.risk_assessment:
            processed_by_name = 'Auto-Status Rule'
            if alert.processed_by:
                if hasattr(alert.processed_by, 'get_full_name'):
                    full_name = alert.processed_by.get_full_name()
                    if full_name and full_name.strip():
                        processed_by_name = f"{full_name} (Auto-Rule)"
                    else:
                        processed_by_name = f"{alert.processed_by.username} (Auto-Rule)"
                elif hasattr(alert.processed_by, 'username'):
                    processed_by_name = f"{alert.processed_by.username} (Auto-Rule)"
                else:
                    processed_by_name = f"{str(alert.processed_by)} (Auto-Rule)"
            
            status_history.append({
                'status': 'risk_assessed',
                'status_display': f'Risk Assessed: {alert.get_risk_assessment_display()}',
                'timestamp': alert.processed_at.isoformat() if alert.processed_at else alert.timestamp.isoformat() if alert.timestamp else None,
                'processed_by': processed_by_name,
                'notes': f'Risk level set to {alert.get_risk_assessment_display()} by auto-status rule'
            })
        
        # Sort by timestamp (newest first)
        status_history.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        
        # Get processed by name safely
        processed_by_name = 'Auto-Status Rule'
        if alert.processed_by:
            if hasattr(alert.processed_by, 'get_full_name'):
                full_name = alert.processed_by.get_full_name()
                if full_name and full_name.strip():
                    processed_by_name = f"{full_name} (Auto-Rule)"
                else:
                    processed_by_name = f"{alert.processed_by.username} (Auto-Rule)"
            elif hasattr(alert.processed_by, 'username'):
                processed_by_name = f"{alert.processed_by.username} (Auto-Rule)"
            else:
                processed_by_name = f"{str(alert.processed_by)} (Auto-Rule)"
        
        return JsonResponse({
            'success': True,
            'alert_id': alert_id,
            'current_status': alert.processing_status or 'pending',
            'current_risk': alert.risk_assessment or '',
            'processed_by': processed_by_name,
            'processed_at': alert.processed_at.isoformat() if alert.processed_at else None,
            'status_history': status_history
        })
        
    except WazuhFIMAlert.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Alert not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting status history for alert {alert_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to get status history'
        }, status=500)
