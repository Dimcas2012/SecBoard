"""
FIM Settings API views
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import FIMSettings, WazuhFIMAlert
from .views import fim_access_required, check_fim_access

logger = logging.getLogger(__name__)


@csrf_exempt
@login_required
@fim_access_required('configure')
def fim_settings_api(request):
    """API endpoint for FIM settings management"""
    if request.method == 'GET':
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to view FIM settings'
                }, status=403)
            
            # Get or create FIM settings
            settings = FIMSettings.get_settings()
            
            # Get current count of FIM alerts
            current_count = WazuhFIMAlert.objects.count()
            
            return JsonResponse({
                'success': True,
                'settings': {
                    'max_records': settings.max_records,
                    'created_at': settings.created_at.isoformat(),
                    'updated_at': settings.updated_at.isoformat(),
                },
                'current_count': current_count
            })
            
        except Exception as e:
            logger.error(f"Error getting FIM settings: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to get FIM settings'
            }, status=500)
    
    elif request.method == 'PUT':
        try:
            # Check if user has configure permission
            if not check_fim_access(request.user, 'configure'):
                return JsonResponse({
                    'success': False,
                    'error': 'Permission denied: You need configure permission to update FIM settings'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Validate required fields
            if 'max_records' not in data:
                return JsonResponse({
                    'success': False,
                    'error': 'Required field missing: max_records'
                }, status=400)
            
            max_records = int(data['max_records'])
            
            # Validate range
            if max_records < 1000 or max_records > 1000000:
                return JsonResponse({
                    'success': False,
                    'error': 'max_records must be between 1000 and 1000000'
                }, status=400)
            
            # Get or create FIM settings
            settings = FIMSettings.get_settings()
            settings.max_records = max_records
            settings.created_by = request.user
            settings.save()
            
            # Perform cleanup if needed
            deleted_count = settings.cleanup_old_records()
            
            # Get updated current count
            current_count = WazuhFIMAlert.objects.count()
            
            return JsonResponse({
                'success': True,
                'settings': {
                    'max_records': settings.max_records,
                    'updated_at': settings.updated_at.isoformat(),
                },
                'current_count': current_count,
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            logger.error(f"Error updating FIM settings: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update FIM settings'
            }, status=500)
    
    else:
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed'
        }, status=405)
