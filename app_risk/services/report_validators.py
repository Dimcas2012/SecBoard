# SecBoard/app_risk/services/report_validators.py

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class ReportConfigValidator:
    """Validator for report configuration"""
    
    def __init__(self, config, user: Optional[User] = None):
        self.config = config
        self.user = user
        self.errors = []
        self.warnings = []
    
    def validate(self) -> Dict[str, List[str]]:
        """Perform full validation and return errors and warnings"""
        self.errors = []
        self.warnings = []
        
        # Basic validation
        self._validate_report_type()
        self._validate_format()
        self._validate_language()
        self._validate_date_range()
        self._validate_sections()
        
        # User-specific validation
        if self.user:
            self._validate_permissions()
            self._validate_company_access()
        
        # Format-specific validation
        self._validate_format_availability()
        
        # Business logic validation
        self._validate_business_rules()
        
        return {
            'errors': self.errors,
            'warnings': self.warnings,
            'is_valid': len(self.errors) == 0
        }
    
    def _validate_report_type(self):
        """Validate report type"""
        valid_types = ['full', 'summary', 'compliance']
        report_type = getattr(self.config, 'report_type', None)
        
        if not report_type:
            self.errors.append(_('Report type is required'))
        elif report_type not in valid_types:
            self.errors.append(_('Invalid report type: {}. Valid types are: {}').format(
                report_type, ', '.join(valid_types)
            ))
    
    def _validate_format(self):
        """Validate report format"""
        valid_formats = ['pdf', 'word']
        format_type = getattr(self.config, 'format', None)
        
        if not format_type:
            self.errors.append(_('Report format is required'))
        elif format_type not in valid_formats:
            self.errors.append(_('Invalid format: {}. Valid formats are: {}').format(
                format_type, ', '.join(valid_formats)
            ))
    
    def _validate_language(self):
        """Validate report language"""
        valid_languages = ['uk', 'en', 'ru']
        language = getattr(self.config, 'language', None)
        
        if not language:
            self.errors.append(_('Report language is required'))
        elif language not in valid_languages:
            self.errors.append(_('Invalid language: {}. Valid languages are: {}').format(
                language, ', '.join(valid_languages)
            ))
    
    def _validate_date_range(self):
        """Validate date range"""
        start_date = getattr(self.config, 'start_date', None)
        end_date = getattr(self.config, 'end_date', None)
        
        if start_date and end_date:
            # Convert to date objects if they're strings
            if isinstance(start_date, str):
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                except ValueError:
                    self.errors.append(_('Invalid start date format. Use YYYY-MM-DD'))
                    return
            
            if isinstance(end_date, str):
                try:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    self.errors.append(_('Invalid end date format. Use YYYY-MM-DD'))
                    return
            
            # Validate date logic
            if start_date > end_date:
                self.errors.append(_('Start date cannot be after end date'))
            
            # Check if date range is too large
            date_diff = (end_date - start_date).days
            if date_diff > 365 * 3:  # 3 years
                self.warnings.append(_('Date range is very large ({}+ days). This may impact performance').format(date_diff))
    
    def _validate_sections(self):
        """Validate report sections"""
        sections = getattr(self.config, 'sections', {})
        
        if not sections:
            self.warnings.append(_('No report sections specified. Using default sections'))
            return
        
        if not isinstance(sections, dict):
            self.errors.append(_('Report sections must be a dictionary'))
            return
        
        # Check if at least one section is enabled
        if not any(sections.values()):
            self.errors.append(_('At least one report section must be selected'))
    
    def _validate_permissions(self):
        """Validate user permissions"""
        if not self.user:
            return
        
        # Check basic report permissions
        if not self.user.has_perm('app_risk.view_riskreport'):
            self.errors.append(_('User does not have permission to generate reports'))
        
        # Check specific report type permissions
        report_type = getattr(self.config, 'report_type', None)
        if report_type == 'compliance':
            if not self.user.has_perm('app_risk.view_compliance'):
                self.errors.append(_('User does not have permission to generate compliance reports'))
    
    def _validate_company_access(self):
        """Validate company access"""
        if not self.user:
            return
        
        company_id = getattr(self.config, 'company_id', None)
        if company_id:
            # This should be replaced with actual company access logic
            pass
    
    def _validate_format_availability(self):
        """Validate if the selected format is available"""
        format_type = getattr(self.config, 'format', None)
        
        if format_type == 'pdf':
            if not self._is_pdf_available():
                self.errors.append(_('PDF generation is not available'))
        elif format_type == 'word':
            if not self._is_word_available():
                self.errors.append(_('Word generation is not available'))
        elif format_type == 'excel':
            if not self._is_excel_available():
                self.errors.append(_('Excel generation is not available'))
    
    def _validate_business_rules(self):
        """Validate business-specific rules"""
        # Validate email settings for scheduled reports
        if getattr(self.config, 'is_scheduled', False):
            self._validate_scheduled_report_settings()
        
        # Validate email recipients
        if getattr(self.config, 'send_email', False):
            self._validate_email_settings()
    
    def _validate_scheduled_report_settings(self):
        """Validate scheduled report specific settings"""
        schedule_name = getattr(self.config, 'schedule_name', '')
        
        if not schedule_name or not schedule_name.strip():
            self.errors.append(_('Schedule name is required for scheduled reports'))
    
    def _validate_email_settings(self):
        """Validate email settings"""
        email_recipients = getattr(self.config, 'email_recipients', [])
        
        if not email_recipients:
            self.errors.append(_('Email recipients are required when email sending is enabled'))
    
    def _is_pdf_available(self) -> bool:
        """Check if PDF generation dependencies are available"""
        try:
            import reportlab
            return True
        except ImportError:
            try:
                import weasyprint
                return True
            except ImportError:
                return False
    
    def _is_word_available(self) -> bool:
        """Check if Word generation dependencies are available"""
        try:
            import docx
            return True
        except ImportError:
            return False
    
    def _is_excel_available(self) -> bool:
        """Check if Excel generation dependencies are available"""
        try:
            import xlsxwriter
            return True
        except ImportError:
            try:
                import openpyxl
                return True
            except ImportError:
                return False


def validate_report_config(config, user: Optional[User] = None) -> Dict[str, Any]:
    """Convenience function to validate report configuration"""
    validator = ReportConfigValidator(config, user)
    return validator.validate()
