"""
Comprehensive Server-Side Validation Service
Provides robust validation for risk reporting system with detailed error handling
"""

import re
import json
from datetime import datetime, date, timedelta, time
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
import logging
from django.core.exceptions import ValidationError
from django.core.validators import validate_email, EmailValidator, URLValidator
from django.utils.translation import gettext as _
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.utils.html import escape
import bleach

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Validation error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationError:
    """Represents a validation error with detailed information"""
    field: str
    message: str
    severity: ValidationSeverity
    code: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'field': self.field,
            'message': self.message,
            'severity': self.severity.value,
            'code': self.code,
            'details': self.details or {}
        }


@dataclass
class ValidationResult:
    """Represents the result of a validation operation"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    cleaned_data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_valid': self.is_valid,
            'errors': [error.to_dict() for error in self.errors],
            'warnings': [warning.to_dict() for warning in self.warnings],
            'cleaned_data': self.cleaned_data
        }
    
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    def get_error_messages(self) -> List[str]:
        return [error.message for error in self.errors]
    
    def get_warning_messages(self) -> List[str]:
        return [warning.message for warning in self.warnings]


class BaseValidator:
    """Base class for all validators"""
    
    def __init__(self, field_name: str, required: bool = False):
        self.field_name = field_name
        self.required = required
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> List[ValidationError]:
        """Validate a value and return list of errors"""
        errors = []
        
        # Check if field is required
        if self.required and self.is_empty(value):
            errors.append(ValidationError(
                field=self.field_name,
                message=_("This field is required"),
                severity=ValidationSeverity.ERROR,
                code="required"
            ))
            return errors
        
        # Skip validation if value is empty and not required
        if self.is_empty(value) and not self.required:
            return errors
        
        # Perform specific validation
        errors.extend(self._validate_value(value, context or {}))
        
        return errors
    
    def is_empty(self, value: Any) -> bool:
        """Check if value is considered empty"""
        if value is None:
            return True
        if isinstance(value, str):
            return len(value.strip()) == 0
        if isinstance(value, (list, dict)):
            return len(value) == 0
        return False
    
    def _validate_value(self, value: Any, context: Dict[str, Any]) -> List[ValidationError]:
        """Override this method in subclasses"""
        return []


class StringValidator(BaseValidator):
    """Validator for string fields"""
    
    def __init__(self, field_name: str, required: bool = False, 
                 min_length: int = None, max_length: int = None,
                 pattern: str = None, pattern_message: str = None):
        super().__init__(field_name, required)
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = re.compile(pattern) if pattern else None
        self.pattern_message = pattern_message
    
    def _validate_value(self, value: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        if not isinstance(value, str):
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Value must be a string"),
                severity=ValidationSeverity.ERROR,
                code="invalid_type"
            ))
            return errors
        
        # Length validation
        if self.min_length is not None and len(value) < self.min_length:
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Minimum length is {min_length} characters").format(min_length=self.min_length),
                severity=ValidationSeverity.ERROR,
                code="min_length",
                details={'min_length': self.min_length, 'actual_length': len(value)}
            ))
        
        if self.max_length is not None and len(value) > self.max_length:
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Maximum length is {max_length} characters").format(max_length=self.max_length),
                severity=ValidationSeverity.ERROR,
                code="max_length",
                details={'max_length': self.max_length, 'actual_length': len(value)}
            ))
        
        # Pattern validation
        if self.pattern and not self.pattern.match(value):
            message = self.pattern_message or _("Value does not match required pattern")
            errors.append(ValidationError(
                field=self.field_name,
                message=message,
                severity=ValidationSeverity.ERROR,
                code="pattern_mismatch"
            ))
        
        return errors


class EmailValidator(BaseValidator):
    """Validator for email fields"""
    
    def _validate_value(self, value: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        if not isinstance(value, str):
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Email must be a string"),
                severity=ValidationSeverity.ERROR,
                code="invalid_type"
            ))
            return errors
        
        try:
            validate_email(value)
        except ValidationError:
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Enter a valid email address"),
                severity=ValidationSeverity.ERROR,
                code="invalid_email"
            ))
        
        return errors


class DateValidator(BaseValidator):
    """Validator for date fields"""
    
    def __init__(self, field_name: str, required: bool = False,
                 min_date: date = None, max_date: date = None,
                 future_only: bool = False, past_only: bool = False):
        super().__init__(field_name, required)
        self.min_date = min_date
        self.max_date = max_date
        self.future_only = future_only
        self.past_only = past_only
    
    def _validate_value(self, value: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        # Convert string to date if needed
        if isinstance(value, str):
            try:
                if 'T' in value:  # ISO format with time
                    value = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                else:
                    value = datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                errors.append(ValidationError(
                    field=self.field_name,
                    message=_("Invalid date format. Use YYYY-MM-DD"),
                    severity=ValidationSeverity.ERROR,
                    code="invalid_date_format"
                ))
                return errors
        
        if not isinstance(value, (date, datetime)):
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Value must be a valid date"),
                severity=ValidationSeverity.ERROR,
                code="invalid_type"
            ))
            return errors
        
        if isinstance(value, datetime):
            value = value.date()
        
        today = timezone.now().date()
        
        # Future/past validation
        if self.future_only and value <= today:
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Date must be in the future"),
                severity=ValidationSeverity.ERROR,
                code="future_required"
            ))
        
        if self.past_only and value >= today:
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Date must be in the past"),
                severity=ValidationSeverity.ERROR,
                code="past_required"
            ))
        
        # Range validation
        if self.min_date and value < self.min_date:
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Date must be after {min_date}").format(min_date=self.min_date),
                severity=ValidationSeverity.ERROR,
                code="min_date",
                details={'min_date': self.min_date.isoformat()}
            ))
        
        if self.max_date and value > self.max_date:
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Date must be before {max_date}").format(max_date=self.max_date),
                severity=ValidationSeverity.ERROR,
                code="max_date",
                details={'max_date': self.max_date.isoformat()}
            ))
        
        return errors


class TimeValidator(BaseValidator):
    """Validator for time fields"""
    
    def __init__(self, field_name: str = None, required: bool = False):
        super().__init__(field_name, required)
    
    def _validate_value(self, value: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        # Convert string to time if needed
        if isinstance(value, str):
            try:
                # Try parsing HH:MM:SS or HH:MM format
                if len(value.split(':')) == 2:
                    value = datetime.strptime(value, '%H:%M').time()
                else:
                    value = datetime.strptime(value, '%H:%M:%S').time()
            except ValueError:
                errors.append(ValidationError(
                    field=self.field_name,
                    message=_("Invalid time format. Use HH:MM or HH:MM:SS"),
                    severity=ValidationSeverity.ERROR,
                    code="invalid_time_format"
                ))
                return errors
        
        if not isinstance(value, time):
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Value must be a valid time"),
                severity=ValidationSeverity.ERROR,
                code="invalid_type"
            ))
        
        return errors


class ChoiceValidator(BaseValidator):
    """Validator for choice fields"""
    
    def __init__(self, field_name: str, required: bool = False,
                 choices: List[Any] = None, allow_multiple: bool = False):
        super().__init__(field_name, required)
        self.choices = choices or []
        self.allow_multiple = allow_multiple
    
    def _validate_value(self, value: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        if self.allow_multiple:
            if not isinstance(value, (list, tuple)):
                errors.append(ValidationError(
                    field=self.field_name,
                    message=_("Value must be a list"),
                    severity=ValidationSeverity.ERROR,
                    code="invalid_type"
                ))
                return errors
            
            for item in value:
                if item not in self.choices:
                    errors.append(ValidationError(
                        field=self.field_name,
                        message=_("'{value}' is not a valid choice").format(value=item),
                        severity=ValidationSeverity.ERROR,
                        code="invalid_choice",
                        details={'invalid_value': item, 'valid_choices': self.choices}
                    ))
        else:
            if value not in self.choices:
                errors.append(ValidationError(
                    field=self.field_name,
                    message=_("'{value}' is not a valid choice").format(value=value),
                    severity=ValidationSeverity.ERROR,
                    code="invalid_choice",
                    details={'invalid_value': value, 'valid_choices': self.choices}
                ))
        
        return errors


class NumberValidator(BaseValidator):
    """Validator for numeric fields"""
    
    def __init__(self, field_name: str, required: bool = False,
                 min_value: Union[int, float] = None, max_value: Union[int, float] = None,
                 integer_only: bool = False):
        super().__init__(field_name, required)
        self.min_value = min_value
        self.max_value = max_value
        self.integer_only = integer_only
    
    def _validate_value(self, value: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        # Convert string to number if needed
        if isinstance(value, str):
            try:
                value = int(value) if self.integer_only else float(value)
            except ValueError:
                errors.append(ValidationError(
                    field=self.field_name,
                    message=_("Enter a valid number"),
                    severity=ValidationSeverity.ERROR,
                    code="invalid_number"
                ))
                return errors
        
        if not isinstance(value, (int, float)):
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Value must be a number"),
                severity=ValidationSeverity.ERROR,
                code="invalid_type"
            ))
            return errors
        
        if self.integer_only and not isinstance(value, int):
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Value must be an integer"),
                severity=ValidationSeverity.ERROR,
                code="integer_required"
            ))
        
        if self.min_value is not None and value < self.min_value:
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Value must be at least {min_value}").format(min_value=self.min_value),
                severity=ValidationSeverity.ERROR,
                code="min_value",
                details={'min_value': self.min_value}
            ))
        
        if self.max_value is not None and value > self.max_value:
            errors.append(ValidationError(
                field=self.field_name,
                message=_("Value must be at most {max_value}").format(max_value=self.max_value),
                severity=ValidationSeverity.ERROR,
                code="max_value",
                details={'max_value': self.max_value}
            ))
        
        return errors


class FileValidator(BaseValidator):
    """Validator for file fields"""
    
    def __init__(self, field_name: str, required: bool = False,
                 max_size: int = None, allowed_extensions: List[str] = None,
                 allowed_mime_types: List[str] = None):
        super().__init__(field_name, required)
        self.max_size = max_size  # in bytes
        self.allowed_extensions = [ext.lower() for ext in (allowed_extensions or [])]
        self.allowed_mime_types = [mime.lower() for mime in (allowed_mime_types or [])]
    
    def _validate_value(self, value: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        # Handle Django UploadedFile
        if hasattr(value, 'size') and hasattr(value, 'name'):
            # File size validation
            if self.max_size and value.size > self.max_size:
                errors.append(ValidationError(
                    field=self.field_name,
                    message=_("File size ({size}) exceeds maximum allowed size ({max_size})").format(
                        size=self._format_file_size(value.size),
                        max_size=self._format_file_size(self.max_size)
                    ),
                    severity=ValidationSeverity.ERROR,
                    code="file_too_large",
                    details={'file_size': value.size, 'max_size': self.max_size}
                ))
            
            # File extension validation
            if self.allowed_extensions:
                file_ext = value.name.split('.')[-1].lower() if '.' in value.name else ''
                if file_ext not in self.allowed_extensions:
                    errors.append(ValidationError(
                        field=self.field_name,
                        message=_("File extension '{ext}' is not allowed. Allowed extensions: {allowed}").format(
                            ext=file_ext,
                            allowed=', '.join(self.allowed_extensions)
                        ),
                        severity=ValidationSeverity.ERROR,
                        code="invalid_extension",
                        details={'file_extension': file_ext, 'allowed_extensions': self.allowed_extensions}
                    ))
            
            # MIME type validation
            if self.allowed_mime_types and hasattr(value, 'content_type'):
                if value.content_type.lower() not in self.allowed_mime_types:
                    errors.append(ValidationError(
                        field=self.field_name,
                        message=_("File type '{type}' is not allowed").format(type=value.content_type),
                        severity=ValidationSeverity.ERROR,
                        code="invalid_mime_type",
                        details={'file_type': value.content_type, 'allowed_types': self.allowed_mime_types}
                    ))
        
        return errors
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class ValidationService:
    """Main validation service"""
    
    def __init__(self):
        self.report_validator = ReportConfigValidator()
        self.schedule_validator = ScheduleValidator()
    
    def validate_report_config(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate report configuration"""
        try:
            return self.report_validator.validate(data)
        except Exception as e:
            logger.error(f"Error validating report config: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    field='general',
                    message=_("Validation error occurred"),
                    severity=ValidationSeverity.CRITICAL,
                    code="validation_exception",
                    details={'exception': str(e)}
                )],
                warnings=[],
                cleaned_data={}
            )
    
    def validate_schedule_config(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate schedule configuration"""
        try:
            return self.schedule_validator.validate(data)
        except Exception as e:
            logger.error(f"Error validating schedule config: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    field='general',
                    message=_("Validation error occurred"),
                    severity=ValidationSeverity.CRITICAL,
                    code="validation_exception",
                    details={'exception': str(e)}
                )],
                warnings=[],
                cleaned_data={}
            )
    
    def validate_file_upload(self, file_data: Any, field_name: str = 'file') -> ValidationResult:
        """Validate file upload"""
        try:
            validator = FileValidator(
                field_name=field_name,
                required=True,
                max_size=10 * 1024 * 1024,  # 10MB
                allowed_extensions=['pdf', 'docx', 'xlsx', 'csv', 'txt'],
                allowed_mime_types=[
                    'application/pdf',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'text/csv',
                    'text/plain'
                ]
            )
            
            errors = validator.validate(file_data)
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=[],
                cleaned_data={'file': file_data} if len(errors) == 0 else {}
            )
        except Exception as e:
            logger.error(f"Error validating file upload: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    field=field_name,
                    message=_("File validation error occurred"),
                    severity=ValidationSeverity.CRITICAL,
                    code="file_validation_exception",
                    details={'exception': str(e)}
                )],
                warnings=[],
                cleaned_data={}
            )
    
    def validate_email_list(self, emails: List[str], field_name: str = 'emails') -> ValidationResult:
        """Validate list of email addresses"""
        try:
            errors = []
            cleaned_emails = []
            
            if not emails:
                errors.append(ValidationError(
                    field=field_name,
                    message=_("At least one email address is required"),
                    severity=ValidationSeverity.ERROR,
                    code="no_emails"
                ))
            else:
                email_validator = EmailValidator(field_name)
                for i, email in enumerate(emails):
                    email_errors = email_validator.validate(email)
                    if email_errors:
                        for error in email_errors:
                            error.field = f"{field_name}[{i}]"
                            errors.append(error)
                    else:
                        cleaned_emails.append(email)
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=[],
                cleaned_data={field_name: cleaned_emails}
            )
        except Exception as e:
            logger.error(f"Error validating email list: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    field=field_name,
                    message=_("Email validation error occurred"),
                    severity=ValidationSeverity.CRITICAL,
                    code="email_validation_exception",
                    details={'exception': str(e)}
                )],
                warnings=[],
                cleaned_data={}
            )
    
    def create_custom_validator(self, field_name: str, validator_func: callable, 
                              error_message: str = None) -> BaseValidator:
        """Create a custom validator"""
        class CustomValidator(BaseValidator):
            def _validate_value(self, value: Any, context: Dict[str, Any]) -> List[ValidationError]:
                try:
                    is_valid = validator_func(value, context)
                    if not is_valid:
                        return [ValidationError(
                            field=field_name,
                            message=error_message or _("Custom validation failed"),
                            severity=ValidationSeverity.ERROR,
                            code="custom_validation_failed"
                        )]
                    return []
                except Exception as e:
                    return [ValidationError(
                        field=field_name,
                        message=_("Custom validation error: {error}").format(error=str(e)),
                        severity=ValidationSeverity.ERROR,
                        code="custom_validation_exception"
                    )]
        
        return CustomValidator(field_name)


# Global validation service instance
validation_service = ValidationService()


class ReportConfigValidator:
    """Validator for report configuration"""
    
    def __init__(self):
        self.validators = {
            'reportType': ChoiceValidator('reportType', required=True, 
                                       choices=['full', 'summary', 'compliance']),
            'reportFormat': ChoiceValidator('reportFormat', required=True, 
                                         choices=['pdf', 'word']),
            'reportLanguage': ChoiceValidator('reportLanguage', required=True, 
                                           choices=['uk', 'en', 'ru']),
            'reportCompany': StringValidator('reportCompany', required=False),
            'reportNotes': StringValidator('reportNotes', required=False, max_length=1000),
        }
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate report configuration data"""
        errors = []
        warnings = []
        cleaned_data = {}
        
        for field_name, validator in self.validators.items():
            value = data.get(field_name)
            field_errors = validator.validate(value, data)
            
            # Add field errors
            for error in field_errors:
                if error.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
                    errors.append(error)
                else:
                    warnings.append(error)
            
            # Add cleaned value
            if not field_errors or all(e.severity not in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] for e in field_errors):
                cleaned_data[field_name] = value
        
        # Cross-field validation
        cross_field_errors = self._validate_cross_fields(cleaned_data)
        errors.extend(cross_field_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data=cleaned_data
        )
    
    def _validate_cross_fields(self, data: Dict[str, Any]) -> List[ValidationError]:
        """Validate relationships between fields"""
        errors = []
        
        # Example: If report type is compliance, company should be specified
        if data.get('reportType') == 'compliance' and not data.get('reportCompany'):
            errors.append(ValidationError(
                field='reportCompany',
                message=_("Company must be specified for compliance reports"),
                severity=ValidationSeverity.WARNING,
                code="company_recommended"
            ))
        
        return errors


class ScheduleValidator:
    """Validator for scheduled report configuration"""
    
    def __init__(self):
        self.validators = {
            'name': StringValidator('name', required=True, min_length=3, max_length=100),
            'description': StringValidator('description', required=False, max_length=500),
            'report_type': ChoiceValidator('report_type', required=True, 
                                        choices=['full', 'summary', 'compliance']),
            'report_format': ChoiceValidator('report_format', required=True, 
                                          choices=['pdf', 'word']),
            'report_language': ChoiceValidator('report_language', required=True, 
                                            choices=['uk', 'en', 'ru']),
            'frequency': ChoiceValidator('frequency', required=True, 
                                       choices=['once', 'daily', 'weekly', 'monthly', 'quarterly', 'yearly']),
            'start_date': DateValidator('start_date', required=True, future_only=True),
            'end_date': DateValidator('end_date', required=False),
            'execution_time': StringValidator('execution_time', required=True, 
                                            pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
                                            pattern_message=_("Time must be in HH:MM format")),
            'send_email': BaseValidator('send_email', required=False),
            'email_subject': StringValidator('email_subject', required=False, max_length=200),
            'email_body': StringValidator('email_body', required=False, max_length=2000),
            'status': ChoiceValidator('status', required=True, 
                                   choices=['active', 'paused', 'completed']),
        }
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate schedule configuration data"""
        errors = []
        warnings = []
        cleaned_data = {}
        
        for field_name, validator in self.validators.items():
            value = data.get(field_name)
            field_errors = validator.validate(value, data)
            
            # Add field errors
            for error in field_errors:
                if error.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
                    errors.append(error)
                else:
                    warnings.append(error)
            
            # Add cleaned value
            if not field_errors or all(e.severity not in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL] for e in field_errors):
                cleaned_data[field_name] = value
        
        # Cross-field validation
        cross_field_errors = self._validate_cross_fields(cleaned_data)
        errors.extend(cross_field_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data=cleaned_data
        )
    
    def _validate_cross_fields(self, data: Dict[str, Any]) -> List[ValidationError]:
        """Validate relationships between fields"""
        errors = []
        
        # Validate date range
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if end_date <= start_date:
                errors.append(ValidationError(
                    field='end_date',
                    message=_("End date must be after start date"),
                    severity=ValidationSeverity.ERROR,
                    code="invalid_date_range"
                ))
        
        # Validate weekly frequency
        if data.get('frequency') == 'weekly':
            weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            selected_days = [day for day in weekdays if data.get(day)]
            
            if not selected_days:
                errors.append(ValidationError(
                    field='weekdays',
                    message=_("At least one day must be selected for weekly frequency"),
                    severity=ValidationSeverity.ERROR,
                    code="no_weekdays_selected"
                ))
        
        # Validate monthly frequency
        if data.get('frequency') == 'monthly':
            day_of_month = data.get('day_of_month')
            if not day_of_month or not (1 <= int(day_of_month) <= 31):
                errors.append(ValidationError(
                    field='day_of_month',
                    message=_("Day of month must be between 1 and 31"),
                    severity=ValidationSeverity.ERROR,
                    code="invalid_day_of_month"
                ))
        
        # Validate email settings
        if data.get('send_email'):
            if not data.get('email_subject'):
                errors.append(ValidationError(
                    field='email_subject',
                    message=_("Email subject is required when sending email"),
                    severity=ValidationSeverity.ERROR,
                    code="email_subject_required"
                ))
            
            email_recipients = data.get('email_recipients', [])
            if not email_recipients:
                errors.append(ValidationError(
                    field='email_recipients',
                    message=_("At least one email recipient is required"),
                    severity=ValidationSeverity.ERROR,
                    code="no_email_recipients"
                ))
        
        return errors


# Pre-configured validators for common use cases
class ReportConfigValidator:
    """Validator for report configuration"""
    
    def __init__(self):
        self.service = ValidationService()
        self._setup_validators()
    
    def _setup_validators(self):
        # Report type validator
        self.service.register_validator(
            'report_type',
            ChoiceValidator(choices=['full', 'summary', 'compliance'], required=True)
        )
        
        # Format validator
        self.service.register_validator(
            'format',
            ChoiceValidator(choices=['pdf', 'word'], required=True)
        )
        
        # Language validator
        self.service.register_validator(
            'language',
            ChoiceValidator(choices=['uk', 'en', 'ru'], required=True)
        )
        
        # Date validators
        self.service.register_validator(
            'start_date',
            DateValidator(min_date=date(2020, 1, 1))
        )
        
        self.service.register_validator(
            'end_date',
            DateValidator(min_date=date(2020, 1, 1))
        )
        
        # Notes validator
        self.service.register_validator(
            'notes',
            StringValidator(max_length=1000)
        )
        
        # Cross-field validator for date range
        self.service.register_cross_field_validator(
            'date_range',
            self._validate_date_range
        )
    
    def _validate_date_range(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate that start_date is before end_date"""
        result = ValidationResult(valid=True)
        
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            if isinstance(start_date, str):
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                except ValueError:
                    return result
            
            if isinstance(end_date, str):
                try:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    return result
            
            if start_date > end_date:
                result.add_error(
                    _("Start date must be before end date"),
                    field='start_date'
                )
            
            # Check if date range is too large
            if (end_date - start_date).days > 365 * 3:
                result.add_warning(
                    _("Date range is very large (more than 3 years). This may impact performance"),
                    field='date_range'
                )
        
        return result
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate report configuration"""
        result = self.service.validate_form('report_config', data)
        
        # Run cross-field validations
        date_range_result = self.service.validate_cross_fields('date_range', data)
        result.merge(date_range_result)
        
        return result


class ScheduleValidator:
    """Validator for scheduled reports"""
    
    def __init__(self):
        self.service = ValidationService()
        self._setup_validators()
    
    def _setup_validators(self):
        # Schedule name validator
        self.service.register_validator(
            'name',
            StringValidator(min_length=1, max_length=100, required=True)
        )
        
        # Frequency validator
        self.service.register_validator(
            'frequency',
            ChoiceValidator(choices=['daily', 'weekly', 'monthly', 'yearly'], required=True)
        )
        
        # Time validator
        self.service.register_validator(
            'execution_time',
            TimeValidator(field_name='execution_time', required=True)
        )
        
        # Email validators
        self.service.register_validator(
            'email_subject',
            StringValidator(max_length=200)
        )
        
        self.service.register_validator(
            'email_body',
            StringValidator(max_length=2000)
        )
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate schedule configuration"""
        return self.service.validate_form('schedule_config', data)


# Global validation service instance
validation_service = ValidationService() 