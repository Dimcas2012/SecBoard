# SecBoard/app_risk/views/report_views_refactored.py

import json
import logging
from typing import Dict, Any

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _

from ..services.report_service import ReportService
from ..services.report_config import ReportConfig
from ..services.report_validators import validate_report_config

logger = logging.getLogger(__name__)


class ReportGenerationView(LoginRequiredMixin, View):
    """Modernized report generation view using service layer"""
    
    def get(self, request):
        """Display report generation form"""
        try:
            report_service = ReportService(request.user)
            
            context = {
                'supported_formats': report_service.get_supported_formats(),
                'report_templates': report_service.get_report_templates(),
                'user': request.user,
                'page_title': _('Generate Risk Report')
            }
            
            return render(request, 'app_risk/report_generation.html', context)
        
        except Exception as e:
            logger.error(f"Error displaying report generation form: {e}")
            return render(request, 'app_risk/error.html', {
                'error_message': _('Error loading report generation form')
            })
    
    def post(self, request):
        """Generate report based on form data"""
        try:
            # Create configuration from request
            config = ReportConfig.from_request(request)
            
            # Create report service
            report_service = ReportService(request.user)
            
            # Generate report
            result = report_service.generate_report(config)
            
            if result['success']:
                # Return file response
                report_data = result['report']
                response = HttpResponse(
                    content=report_data['content'],
                    content_type=report_data['content_type']
                )
                response['Content-Disposition'] = f'attachment; filename="{report_data["filename"]}"'
                
                return response
            else:
                # Return error response
                return JsonResponse({
                    'success': False,
                    'errors': result['errors'],
                    'warnings': result.get('warnings', [])
                }, status=400)
        
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return JsonResponse({
                'success': False,
                'errors': [_('Unexpected error generating report')]
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ReportPreviewView(LoginRequiredMixin, View):
    """Get report preview/statistics"""
    
    def post(self, request):
        """Get report preview"""
        try:
            # Parse request data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST.dict()
            
            # Create configuration
            config = ReportConfig.from_dict(data)
            
            # Create report service
            report_service = ReportService(request.user)
            
            # Get preview
            result = report_service.get_report_preview(config)
            
            return JsonResponse(result)
        
        except Exception as e:
            logger.error(f"Error getting report preview: {e}")
            return JsonResponse({
                'success': False,
                'errors': [_('Error getting report preview')]
            }, status=500)


# Legacy function-based views for backward compatibility
@login_required
@require_http_methods(["GET", "POST"])
def generate_risk_report(request):
    """Legacy function-based view for report generation"""
    view = ReportGenerationView()
    view.setup(request)
    
    if request.method == 'GET':
        return view.get(request)
    else:
        return view.post(request)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def get_report_preview(request):
    """Legacy function-based view for report preview"""
    view = ReportPreviewView()
    view.setup(request)
    return view.post(request)


# API endpoints for AJAX requests
@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_generate_report(request):
    """API endpoint for report generation"""
    try:
        # Parse JSON data
        data = json.loads(request.body)
        
        # Create configuration
        config = ReportConfig.from_dict(data)
        
        # Create report service
        report_service = ReportService(request.user)
        
        # Generate report
        result = report_service.generate_report(config)
        
        if result['success']:
            # For API, return success with download info
            report_data = result['report']
            return JsonResponse({
                'success': True,
                'filename': report_data['filename'],
                'content_type': report_data['content_type'],
                'generation_time': result['generation_time'],
                'message': _('Report generated successfully')
            })
        else:
            return JsonResponse(result, status=400)
    
    except Exception as e:
        logger.error(f"API error generating report: {e}")
        return JsonResponse({
            'success': False,
            'errors': [_('API error generating report')]
        }, status=500)


# Utility functions
def create_report_config_from_request(request) -> ReportConfig:
    """Create ReportConfig from request data"""
    if request.method == 'POST':
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
    else:
        data = request.GET.dict()
    
    return ReportConfig.from_dict(data)


def handle_report_error(error: Exception, context: str = "") -> JsonResponse:
    """Handle report generation errors consistently"""
    logger.error(f"Report error {context}: {error}")
    
    return JsonResponse({
        'success': False,
        'errors': [_('Error in report generation')],
        'context': context
    }, status=500)


def validate_report_permissions(user, report_type: str = None) -> bool:
    """Validate user permissions for report generation"""
    if not user.is_authenticated:
        return False
    
    # Basic permission check
    if not user.has_perm('app_risk.view_riskreport'):
        return False
    
    # Report type specific checks
    if report_type == 'compliance':
        if not user.has_perm('app_risk.view_compliance'):
            return False
    
    return True