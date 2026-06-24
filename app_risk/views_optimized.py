# SecBoard/app_risk/views_optimized.py

import json
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _, get_language, activate
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.conf import settings

# Import existing functionality
from .report_views import (
    check_risk_report_access, get_user_companies, get_available_formats,
    is_format_available, generate_report_file, get_report_translations
)

# Import optimized services
from .services import (
    get_cache_service,
    get_async_report_service,
    get_performance_monitor_service,
    ReportConfig,
    OptimizedReportDataService,
    performance_monitor,
    monitor_operation,
    add_metric
)

logger = logging.getLogger(__name__)


class OptimizedReportController:
    """Controller for optimized report generation with caching and async processing"""
    
    def __init__(self):
        self.cache_service = get_cache_service()
        self.async_service = get_async_report_service()
        self.performance_service = get_performance_monitor_service()
        
        # Start performance monitoring
        self.performance_service.start()
    
    @performance_monitor(category="report_generation")
    def get_cached_report_data(self, user, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached report data if available"""
        
        # Create cache key based on user and parameters
        cache_key = self._generate_cache_key(user, params)
        
        # Try to get from cache
        cached_data = self.cache_service.get(cache_key)
        
        if cached_data:
            add_metric("report_cache_hit", 1, "count", "caching")
            logger.info(f"Cache hit for report: {cache_key}")
            return cached_data
        
        add_metric("report_cache_miss", 1, "count", "caching")
        logger.info(f"Cache miss for report: {cache_key}")
        return None
    
    def cache_report_data(self, user, params: Dict[str, Any], data: Dict[str, Any], timeout: int = 1800):
        """Cache report data with compression"""
        
        cache_key = self._generate_cache_key(user, params)
        
        # Cache with compression for large reports
        self.cache_service.set(
            cache_key,
            data,
            timeout=timeout,
            strategy='compressed' if len(str(data)) > 10000 else 'lru'
        )
        
        logger.info(f"Cached report data: {cache_key}")
        add_metric("report_cached", 1, "count", "caching")
    
    def _generate_cache_key(self, user, params: Dict[str, Any]) -> str:
        """Generate cache key based on user and parameters"""
        
        # Extract relevant parameters for cache key
        key_params = {
            'user_id': user.id,
            'report_type': params.get('reportType', 'full'),
            'format': params.get('format', 'pdf'),
            'language': params.get('language', 'en'),
            'company_id': params.get('company_id', ''),
            'start_date': params.get('startDate', ''),
            'end_date': params.get('endDate', ''),
        }
        
        # Create hash from parameters
        import hashlib
        key_string = json.dumps(key_params, sort_keys=True)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"risk_report_{key_hash}"
    
    @performance_monitor(category="report_generation")
    def generate_optimized_report_data(self, user, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate report data using optimized services"""
        
        # Check cache first
        cached_data = self.get_cached_report_data(user, params)
        if cached_data:
            return cached_data
        
        # Create report configuration
        config = ReportConfig(
            user=user,
            report_type=params.get('reportType', 'full'),
            format=params.get('format', 'pdf'),
            language=params.get('language', get_language()[:2]),
            company_id=params.get('company_id'),
            notes=params.get('notes', ''),
            date_range=self._get_date_range(params),
            include_assets=True,
            include_vulnerabilities=True,
            include_treatments=True,
            include_statistics=True,
            enable_caching=True
        )
        
        # Generate data using optimized service
        with monitor_operation("optimized_data_generation", "report_generation"):
            data_service = OptimizedReportDataService(config)
            report_data = data_service.get_optimized_report_data()
        
        # Cache the generated data
        self.cache_report_data(user, params, report_data)
        
        return report_data
    
    def _get_date_range(self, params: Dict[str, Any]) -> tuple:
        """Extract date range from parameters"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)
        
        if params.get('startDate'):
            start_date = datetime.strptime(params['startDate'], '%Y-%m-%d').date()
        if params.get('endDate'):
            end_date = datetime.strptime(params['endDate'], '%Y-%m-%d').date()
        
        return (start_date, end_date)
    
    async def generate_async_report(self, user, params: Dict[str, Any]) -> str:
        """Generate report asynchronously for large datasets"""
        
        # Create report configuration
        config = ReportConfig(
            user=user,
            report_type=params.get('reportType', 'full'),
            format=params.get('format', 'pdf'),
            language=params.get('language', get_language()[:2]),
            company_id=params.get('company_id'),
            notes=params.get('notes', ''),
            date_range=self._get_date_range(params),
            include_assets=True,
            include_vulnerabilities=True,
            include_treatments=True,
            include_statistics=True,
            enable_caching=True
        )
        
        # Submit async job
        job_id = await self.async_service.submit_report_job(
            config=config,
            priority="normal",
            notification_methods=["cache", "email"] if user.email else ["cache"]
        )
        
        logger.info(f"Async report job submitted: {job_id} for user {user.username}")
        return job_id
    
    def invalidate_user_cache(self, user):
        """Invalidate all cached reports for a user"""
        pattern = f"risk_report_*{user.id}*"
        self.cache_service.invalidate_pattern(pattern)
        logger.info(f"Invalidated cache for user {user.username}")


# Global controller instance
report_controller = OptimizedReportController()


@login_required
@user_passes_test(check_risk_report_access)
@require_http_methods(["GET", "POST"])
def generate_risk_report_optimized(request):
    """Optimized version of generate_risk_report with caching and async processing"""
    
    # Check permissions
    if not check_risk_report_access(request.user, 'view'):
        raise PermissionDenied(_("You don't have permission to generate reports"))
    
    if request.method == 'GET':
        return _handle_get_request(request)
    elif request.method == 'POST':
        return _handle_post_request(request)


def _handle_get_request(request):
    """Handle GET request for report generation"""
    
    # Check if this is a direct report generation request
    report_type = request.GET.get('reportType', 'summary')
    report_format = request.GET.get('format', 'word')
    report_language = request.GET.get('language', get_language()[:2])
    
    if report_type and report_format:
        try:
            # Activate the selected language
            activate(report_language)
            
            # Validate format availability
            if not is_format_available(report_format):
                return JsonResponse({
                    'status': 'error',
                    'message': _('Selected format is not available. Please install required dependencies.')
                })
            
            # Check if this should be processed asynchronously
            async_threshold = getattr(settings, 'REPORT_ASYNC_THRESHOLD', 1000)
            should_use_async = request.GET.get('async', 'false').lower() == 'true'
            
            if should_use_async:
                # Generate async report
                params = {
                    'reportType': report_type,
                    'format': report_format,
                    'language': report_language
                }
                
                # This would need to be handled differently in a real Django view
                # For now, we'll use sync processing but with caching
                report_data = report_controller.generate_optimized_report_data(request.user, params)
                response = generate_report_file(report_data, report_type, report_format)
                return response
            else:
                # Generate report with caching
                params = {
                    'reportType': report_type,
                    'format': report_format,
                    'language': report_language
                }
                
                report_data = report_controller.generate_optimized_report_data(request.user, params)
                response = generate_report_file(report_data, report_type, report_format)
                return response
                
        except Exception as e:
            logger.error(f"Error generating optimized risk report: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': _('Error generating report: {}').format(str(e))
            })
    else:
        # Return report configuration page with cache stats
        cache_stats = report_controller.cache_service.get_cache_stats()
        
        return render(request, 'app_risk/reports/report_config_optimized.html', {
            'available_formats': get_available_formats(),
            'companies': get_user_companies(request.user),
            'cache_stats': cache_stats,
            'async_enabled': True,
        })


def _handle_post_request(request):
    """Handle POST request for report generation"""
    
    try:
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body) if request.body else {}
        else:
            data = {
                'reportType': request.POST.get('reportType', 'full'),
                'format': request.POST.get('reportFormat', 'pdf'),
                'language': request.POST.get('reportLanguage', get_language()[:2]),
                'company_id': request.POST.get('reportCompany', ''),
                'notes': request.POST.get('reportNotes', ''),
                'startDate': request.POST.get('startDate', ''),
                'endDate': request.POST.get('endDate', ''),
                'async': request.POST.get('async', 'false'),
            }
        
        report_type = data.get('reportType', 'full')
        report_format = data.get('format', data.get('reportFormat', 'pdf'))
        report_language = data.get('language', data.get('reportLanguage', get_language()[:2]))
        use_async = data.get('async', 'false').lower() == 'true'
        
        # Activate the selected language
        activate(report_language)
        
        # Validate format availability
        if not is_format_available(report_format):
            return JsonResponse({
                'status': 'error',
                'message': _('Selected format is not available. Please install required dependencies.')
            })
        
        # Check if async processing is requested
        if use_async:
            return _handle_async_request(request, data)
        else:
            return _handle_sync_request(request, data)
            
    except Exception as e:
        logger.error(f"Error generating optimized risk report: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': _('Error generating report: {}').format(str(e))
        })


def _handle_sync_request(request, data):
    """Handle synchronous report generation with caching"""
    
    # Generate report data with caching
    report_data = report_controller.generate_optimized_report_data(request.user, data)
    
    # Generate report file
    response = generate_report_file(
        report_data, 
        data.get('reportType', 'full'), 
        data.get('format', 'pdf')
    )
    
    return response


def _handle_async_request(request, data):
    """Handle asynchronous report generation"""
    
    # This is a simplified version - in a real implementation you'd use Celery
    # For now, we'll simulate async by using threading
    import threading
    import uuid
    
    job_id = str(uuid.uuid4())
    
    # Store job info in cache
    job_info = {
        'id': job_id,
        'status': 'pending',
        'progress': 0,
        'created_at': timezone.now().isoformat(),
        'user_id': request.user.id,
        'params': data
    }
    
    cache_key = f"async_job_{job_id}"
    cache.set(cache_key, job_info, timeout=3600)  # 1 hour
    
    # Start background processing
    def process_async_report():
        try:
            # Update status
            job_info['status'] = 'processing'
            job_info['progress'] = 10
            cache.set(cache_key, job_info, timeout=3600)
            
            # Generate report data
            report_data = report_controller.generate_optimized_report_data(request.user, data)
            
            job_info['progress'] = 70
            cache.set(cache_key, job_info, timeout=3600)
            
            # Generate report file (simplified - in real implementation would save to file)
            response = generate_report_file(
                report_data, 
                data.get('reportType', 'full'), 
                data.get('format', 'pdf')
            )
            
            # Store result
            job_info['status'] = 'completed'
            job_info['progress'] = 100
            job_info['completed_at'] = timezone.now().isoformat()
            job_info['result'] = 'Report generated successfully'
            cache.set(cache_key, job_info, timeout=3600)
            
        except Exception as e:
            job_info['status'] = 'failed'
            job_info['error'] = str(e)
            cache.set(cache_key, job_info, timeout=3600)
            logger.error(f"Async report generation failed: {str(e)}")
    
    # Start background thread
    thread = threading.Thread(target=process_async_report)
    thread.daemon = True
    thread.start()
    
    return JsonResponse({
        'status': 'accepted',
        'job_id': job_id,
        'message': _('Report generation started. You can check the status using the job ID.')
    })


@login_required
@user_passes_test(check_risk_report_access)
@require_http_methods(["GET"])
def get_async_job_status(request, job_id):
    """Get status of asynchronous report generation job"""
    
    cache_key = f"async_job_{job_id}"
    job_info = cache.get(cache_key)
    
    if not job_info:
        return JsonResponse({
            'status': 'error',
            'message': _('Job not found or expired')
        }, status=404)
    
    # Check if user has permission to view this job
    if job_info['user_id'] != request.user.id and not request.user.is_superuser:
        return JsonResponse({
            'status': 'error',
            'message': _('Permission denied')
        }, status=403)
    
    return JsonResponse({
        'status': 'success',
        'job': job_info
    })


@login_required
@user_passes_test(check_risk_report_access)
@require_http_methods(["POST"])
def clear_report_cache(request):
    """Clear cached reports for the current user"""
    
    try:
        report_controller.invalidate_user_cache(request.user)
        
        return JsonResponse({
            'status': 'success',
            'message': _('Cache cleared successfully')
        })
        
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _('Error clearing cache: {}').format(str(e))
        })


@login_required
@user_passes_test(check_risk_report_access)
@require_http_methods(["GET"])
def get_cache_stats(request):
    """Get cache statistics"""
    
    try:
        stats = report_controller.cache_service.get_cache_stats()
        
        return JsonResponse({
            'status': 'success',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _('Error getting cache stats: {}').format(str(e))
        })


@login_required
@user_passes_test(check_risk_report_access)
@require_http_methods(["GET"])
def get_performance_stats(request):
    """Get performance statistics"""
    
    try:
        performance_report = report_controller.performance_service.get_performance_report(
            time_window=timedelta(hours=1)
        )
        
        return JsonResponse({
            'status': 'success',
            'performance': performance_report
        })
        
    except Exception as e:
        logger.error(f"Error getting performance stats: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _('Error getting performance stats: {}').format(str(e))
        })


@login_required
@user_passes_test(check_risk_report_access)
@require_http_methods(["POST"])
def preview_risk_report_optimized(request):
    """Optimized version of preview_risk_report with caching"""
    
    try:
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body) if request.body else {}
        else:
            data = {
                'reportType': request.POST.get('reportType', 'full'),
                'language': request.POST.get('reportLanguage', get_language()[:2]),
                'company_id': request.POST.get('reportCompany', ''),
                'startDate': request.POST.get('startDate', ''),
                'endDate': request.POST.get('endDate', ''),
            }
        
        # Check cache for preview
        cache_key = f"preview_{report_controller._generate_cache_key(request.user, data)}"
        cached_preview = cache.get(cache_key)
        
        if cached_preview:
            add_metric("preview_cache_hit", 1, "count", "caching")
            return JsonResponse({
                'status': 'success',
                'html': cached_preview,
                'cached': True
            })
        
        add_metric("preview_cache_miss", 1, "count", "caching")
        
        # Generate preview data
        report_data = report_controller.generate_optimized_report_data(request.user, data)
        
        # Generate HTML preview
        from .report_views import generate_html_preview
        html_preview = generate_html_preview(
            report_data, 
            data.get('reportType', 'full'),
            data.get('language', get_language()[:2])
        )
        
        # Cache preview for 5 minutes
        cache.set(cache_key, html_preview, timeout=300)
        
        return JsonResponse({
            'status': 'success',
            'html': html_preview,
            'cached': False
        })
        
    except Exception as e:
        logger.error(f"Error generating optimized preview: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': _('Error generating preview: {}').format(str(e))
        })


# URL patterns helper
def get_optimized_url_patterns():
    """Get URL patterns for optimized views"""
    from django.urls import path
    
    return [
        path('reports/generate-optimized/', generate_risk_report_optimized, name='generate_risk_report_optimized'),
        path('reports/preview-optimized/', preview_risk_report_optimized, name='preview_risk_report_optimized'),
        path('reports/async-status/<str:job_id>/', get_async_job_status, name='get_async_job_status'),
        path('reports/clear-cache/', clear_report_cache, name='clear_report_cache'),
        path('reports/cache-stats/', get_cache_stats, name='get_cache_stats'),
        path('reports/performance-stats/', get_performance_stats, name='get_performance_stats'),
    ]