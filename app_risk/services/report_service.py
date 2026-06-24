# SecBoard/app_risk/services/report_service.py

import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext as _
from django.core.cache import cache
from django.http import HttpResponse
from django.core.exceptions import ValidationError

from .report_config import ReportConfig
from .report_data_service import ReportDataService
from .report_generator_factory import ReportGeneratorFactory
from .report_validators import validate_report_config, ReportConfigValidator

logger = logging.getLogger(__name__)


class ReportService:
    """Main service for report generation and management"""
    
    def __init__(self, user: User):
        self.user = user
        self.logger = logging.getLogger(f"{__name__}.{user.username}")
    
    def generate_report(self, config: ReportConfig) -> Dict[str, Any]:
        """Generate a report based on configuration"""
        try:
            # Validate configuration
            validation_result = self._validate_config(config)
            if not validation_result['is_valid']:
                return {
                    'success': False,
                    'errors': validation_result['errors'],
                    'warnings': validation_result.get('warnings', [])
                }
            
            # Create data service
            data_service = ReportDataService(self.user, config)
            
            # Validate format availability
            if not ReportGeneratorFactory.is_format_available(config.format):
                return {
                    'success': False,
                    'errors': [_('Selected format is not available. Please install required dependencies.')]
                }
            
            # Create generator
            generator = ReportGeneratorFactory.create_generator(config, data_service)
            
            # Generate report
            self.logger.info(f"Starting report generation for user {self.user.username}")
            start_time = timezone.now()
            
            report_result = generator.generate()
            
            end_time = timezone.now()
            generation_time = (end_time - start_time).total_seconds()
            
            self.logger.info(f"Report generated successfully in {generation_time:.2f} seconds")
            
            # Log report generation
            self._log_report_generation(config, generation_time, True)
            
            return {
                'success': True,
                'report': report_result,
                'generation_time': generation_time,
                'config': config,
                'warnings': validation_result.get('warnings', [])
            }
        
        except Exception as e:
            self.logger.error(f"Error generating report: {e}")
            self._log_report_generation(config, 0, False, str(e))
            
            return {
                'success': False,
                'errors': [_('Error generating report: {}').format(str(e))]
            }
    
    def generate_report_response(self, config: ReportConfig) -> HttpResponse:
        """Generate report and return HTTP response"""
        result = self.generate_report(config)
        
        if not result['success']:
            # Return error response
            response = HttpResponse(
                content=_('Error generating report: {}').format(', '.join(result['errors'])),
                status=400
            )
            return response
        
        # Return file response
        report_data = result['report']
        response = HttpResponse(
            content=report_data['content'],
            content_type=report_data['content_type']
        )
        response['Content-Disposition'] = f'attachment; filename="{report_data["filename"]}"'
        
        return response
    
    def get_report_preview(self, config: ReportConfig) -> Dict[str, Any]:
        """Get report preview/statistics without generating full report"""
        try:
            # Validate configuration
            validation_result = self._validate_config(config)
            if not validation_result['is_valid']:
                return {
                    'success': False,
                    'errors': validation_result['errors']
                }
            
            # Create data service
            data_service = ReportDataService(self.user, config)
            
            # Get quick statistics
            stats = data_service.get_quick_statistics()
            
            return {
                'success': True,
                'preview': {
                    'statistics': stats,
                    'estimated_size': self._estimate_report_size(stats),
                    'available_formats': self._get_available_formats(),
                    'generation_time_estimate': self._estimate_generation_time(stats)
                }
            }
        
        except Exception as e:
            self.logger.error(f"Error getting report preview: {e}")
            return {
                'success': False,
                'errors': [_('Error getting report preview: {}').format(str(e))]
            }
    
    def validate_report_config(self, config: ReportConfig) -> Dict[str, Any]:
        """Validate report configuration"""
        return self._validate_config(config)
    
    def get_supported_formats(self) -> List[Dict[str, Any]]:
        """Get list of supported formats with availability status"""
        formats = []
        
        for format_type in ReportGeneratorFactory.get_supported_formats():
            is_available = ReportGeneratorFactory.is_format_available(format_type)
            
            formats.append({
                'format': format_type,
                'name': self._get_format_display_name(format_type),
                'available': is_available,
                'description': self._get_format_description(format_type),
                'file_extension': self._get_format_extension(format_type)
            })
        
        return formats
    
    def get_report_templates(self) -> List[Dict[str, Any]]:
        """Get available report templates"""
        return [
            {
                'id': 'full',
                'name': _('Full Report'),
                'description': _('Complete risk assessment report with all sections'),
                'sections': {
                    'executive_summary': True,
                    'risk_statistics': True,
                    'vulnerability_analysis': True,
                    'compliance_status': True,
                    'risk_treatments': True,
                    'recommendations': True,
                    'appendices': True
                }
            },
            {
                'id': 'summary',
                'name': _('Summary Report'),
                'description': _('Executive summary with key statistics'),
                'sections': {
                    'executive_summary': True,
                    'risk_statistics': True,
                    'vulnerability_analysis': False,
                    'compliance_status': False,
                    'risk_treatments': False,
                    'recommendations': True,
                    'appendices': False
                }
            },
            {
                'id': 'compliance',
                'name': _('Compliance Report'),
                'description': _('Focus on compliance status and gaps'),
                'sections': {
                    'executive_summary': True,
                    'risk_statistics': False,
                    'vulnerability_analysis': False,
                    'compliance_status': True,
                    'risk_treatments': True,
                    'recommendations': True,
                    'appendices': True
                }
            }
        ]
    
    def _validate_config(self, config: ReportConfig) -> Dict[str, Any]:
        """Validate report configuration"""
        validator = ReportConfigValidator(config, self.user)
        return validator.validate()
    
    def _log_report_generation(self, config: ReportConfig, generation_time: float, success: bool, error_message: str = None):
        """Log report generation event"""
        try:
            # This would typically save to a ReportLog model
            # For now, just log to application log
            log_data = {
                'user': self.user.username,
                'report_type': config.report_type,
                'format': config.format,
                'language': config.language,
                'generation_time': generation_time,
                'success': success,
                'error_message': error_message,
                'timestamp': timezone.now()
            }
            
            if success:
                self.logger.info(f"Report generated successfully: {log_data}")
            else:
                self.logger.error(f"Report generation failed: {log_data}")
        
        except Exception as e:
            self.logger.error(f"Error logging report generation: {e}")
    
    def _estimate_report_size(self, stats: Dict[str, Any]) -> str:
        """Estimate report file size based on statistics"""
        total_assets = stats.get('total_assets', 0)
        
        # Rough estimation based on content
        if total_assets < 10:
            return "< 1 MB"
        elif total_assets < 100:
            return "1-5 MB"
        elif total_assets < 1000:
            return "5-20 MB"
        else:
            return "> 20 MB"
    
    def _estimate_generation_time(self, stats: Dict[str, Any]) -> str:
        """Estimate report generation time"""
        total_assets = stats.get('total_assets', 0)
        
        if total_assets < 10:
            return "< 30 seconds"
        elif total_assets < 100:
            return "30 seconds - 2 minutes"
        elif total_assets < 1000:
            return "2-10 minutes"
        else:
            return "> 10 minutes"
    
    def _get_available_formats(self) -> List[str]:
        """Get list of available formats"""
        return [
            format_type for format_type in ReportGeneratorFactory.get_supported_formats()
            if ReportGeneratorFactory.is_format_available(format_type)
        ]
    
    def _get_format_display_name(self, format_type: str) -> str:
        """Get display name for format"""
        format_names = {
            'pdf': _('PDF Document'),
            'word': _('Word Document')
        }
        return format_names.get(format_type, format_type.upper())
    
    def _get_format_description(self, format_type: str) -> str:
        """Get description for format"""
        descriptions = {
            'pdf': _('Portable Document Format - best for sharing and printing'),
            'word': _('Microsoft Word format - best for editing and collaboration')
        }
        return descriptions.get(format_type, '')
    
    def _get_format_extension(self, format_type: str) -> str:
        """Get file extension for format"""
        extensions = {
            'pdf': '.pdf',
            'word': '.docx'
        }
        return extensions.get(format_type, '')