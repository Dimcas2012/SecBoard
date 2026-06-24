"""
Security validators and utilities for Personal Cabinet functionality
Prevents XSS, SQL Injection, and Privilege Escalation attacks
"""

import re
import html
import bleach
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.core.validators import validate_email
import logging

logger = logging.getLogger(__name__)

# Allowed HTML tags and attributes for sanitization
ALLOWED_TAGS = []  # No HTML tags allowed in user input
ALLOWED_ATTRIBUTES = {}
ALLOWED_PROTOCOLS = ['http', 'https']

class PersonalCabinetSecurityValidator:
    """Comprehensive security validator for personal cabinet operations"""
    
    @staticmethod
    def validate_and_sanitize_text_field(value, field_name, max_length=100):
        """
        Validate and sanitize text input fields to prevent XSS and injection attacks
        
        Args:
            value: Input value to validate
            field_name: Name of the field for error messages
            max_length: Maximum allowed length
            
        Returns:
            str: Sanitized and validated value
            
        Raises:
            ValidationError: If validation fails
        """
        if not value:
            return value
            
        # Strip whitespace
        value = value.strip()
        
        # Check length
        if len(value) > max_length:
            raise ValidationError(
                _('%(field)s must be no more than %(max)d characters.'),
                params={'field': field_name, 'max': max_length}
            )
        
        # Check for malicious patterns
        malicious_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',  # JavaScript protocol
            r'vbscript:',  # VBScript protocol
            r'onload\s*=',  # Event handlers
            r'onerror\s*=',
            r'onclick\s*=',
            r'onmouseover\s*=',
            r'<iframe[^>]*>',  # Iframe tags
            r'<object[^>]*>',  # Object tags
            r'<embed[^>]*>',  # Embed tags
            r'<link[^>]*>',  # Link tags
            r'<meta[^>]*>',  # Meta tags
            r'<style[^>]*>',  # Style tags
            r'expression\s*\(',  # CSS expressions
            r'url\s*\(',  # CSS url() function
            r'@import',  # CSS imports
            r'<\?php',  # PHP tags
            r'<%',  # ASP tags
            r'\$\{',  # Template injection
            r'\#\{',  # Template injection
            r'union\s+select',  # SQL injection
            r'drop\s+table',  # SQL injection
            r'delete\s+from',  # SQL injection
            r'insert\s+into',  # SQL injection
            r'update\s+.*\s+set',  # SQL injection
        ]
        
        for pattern in malicious_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Malicious pattern detected in {field_name}: {pattern}")
                raise ValidationError(
                    _('Invalid characters detected in %(field)s. Please use only alphanumeric characters and basic punctuation.'),
                    params={'field': field_name}
                )
        
        # Sanitize HTML entities and tags
        value = html.escape(value)
        value = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, protocols=ALLOWED_PROTOCOLS)
        
        # Additional character validation for names
        if field_name.lower() in ['first_name', 'last_name']:
            if not re.match(r'^[a-zA-ZА-Яа-яІіЇїЄєґҐ\s\-\'\.]+$', value):
                raise ValidationError(
                    _('%(field)s can only contain letters, spaces, hyphens, apostrophes, and periods.'),
                    params={'field': field_name}
                )
        
        return value
    
    @staticmethod
    def validate_phone_number(phone):
        """
        Validate phone number format and prevent injection attacks
        
        Args:
            phone: Phone number string
            
        Returns:
            str: Validated phone number
            
        Raises:
            ValidationError: If validation fails
        """
        if not phone:
            return phone
            
        phone = phone.strip()
        
        # Remove common formatting characters
        cleaned_phone = re.sub(r'[\s\-\(\)\+]', '', phone)
        
        # Check if contains only digits after cleaning
        if not re.match(r'^\+?[\d\s\-\(\)]+$', phone):
            raise ValidationError(_('Phone number contains invalid characters.'))
        
        # Check length (international format)
        if len(cleaned_phone) < 7 or len(cleaned_phone) > 15:
            raise ValidationError(_('Phone number must be between 7 and 15 digits.'))
        
        return phone
    
    @staticmethod
    def validate_telegram_chat_id(chat_id):
        if not chat_id:
            return ''
        chat_id = chat_id.strip()
        if not re.match(r'^-?\d+$', chat_id):
            raise ValidationError(_('Telegram Chat ID must contain digits only.'))
        return chat_id
    
    @staticmethod
    def validate_email_security(email):
        """
        Enhanced email validation with security checks
        
        Args:
            email: Email address string
            
        Returns:
            str: Validated email
            
        Raises:
            ValidationError: If validation fails
        """
        if not email:
            raise ValidationError(_('Email is required.'))
        
        email = email.strip().lower()
        
        # Basic email validation
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError(_('Enter a valid email address.'))
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'[<>"\'\(\)]',  # Potentially dangerous characters
            r'javascript:',
            r'vbscript:',
            r'data:',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, email, re.IGNORECASE):
                raise ValidationError(_('Email contains invalid characters.'))
        
        return email
    
    @staticmethod
    def validate_privilege_escalation_attempt(request_user, target_user_id=None, 
                                            company_change=None, department_change=None, 
                                            position_change=None):
        """
        Validate that user is not attempting privilege escalation
        
        Args:
            request_user: User making the request
            target_user_id: ID of user being modified (None for self-update)
            company_change: New company value
            department_change: New department value
            position_change: New position value
            
        Raises:
            ValidationError: If privilege escalation is detected
        """
        # Users can only modify their own profile unless they're staff
        if target_user_id and target_user_id != request_user.id and not request_user.is_staff:
            logger.warning(f"User {request_user.username} attempted to modify user {target_user_id}")
            raise ValidationError(_('You can only modify your own profile.'))
        
        # Regular users cannot change sensitive fields
        if not request_user.is_staff:
            if company_change:
                logger.warning(f"User {request_user.username} attempted to change company")
                raise ValidationError(_('You cannot change your company assignment.'))
            
            if department_change:
                logger.warning(f"User {request_user.username} attempted to change department")
                raise ValidationError(_('You cannot change your department assignment.'))
            
            if position_change:
                logger.warning(f"User {request_user.username} attempted to change position")
                raise ValidationError(_('You cannot change your position assignment.'))
    
    @staticmethod
    def validate_avatar_upload(avatar_file):
        """
        Validate avatar upload for security issues
        
        Args:
            avatar_file: Uploaded file object
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If validation fails
        """
        if not avatar_file:
            return True
        
        # Check file size (2MB limit)
        if avatar_file.size > 2 * 1024 * 1024:
            raise ValidationError(_('Avatar file size must not exceed 2MB.'))
        
        # Check file type
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'image/gif']
        if avatar_file.content_type not in allowed_types:
            raise ValidationError(_('Avatar must be a JPEG, PNG, or GIF image.'))
        
        # Check file extension
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        file_extension = avatar_file.name.lower().split('.')[-1]
        if f'.{file_extension}' not in allowed_extensions:
            raise ValidationError(_('Invalid file extension for avatar.'))
        
        # Check for potentially malicious file names
        if re.search(r'[<>:"/\\|?*]', avatar_file.name):
            raise ValidationError(_('Avatar filename contains invalid characters.'))
        
        return True


class PersonalCabinetAuditLogger:
    """Audit logging for personal cabinet security events"""
    
    @staticmethod
    def log_profile_update(user, changed_fields, ip_address, target_user=None):
        """
        Log profile update events for security monitoring
        
        Args:
            user: User performing the update
            changed_fields: List of fields that were changed
            ip_address: IP address of the request
            target_user: User being updated (if different from requesting user)
        """
        if target_user and target_user != user:
            logger.warning(
                f"AUDIT: User {user.username} updated profile for user {target_user.username} "
                f"(Fields: {', '.join(changed_fields)}, IP: {ip_address})"
            )
        else:
            logger.info(
                f"AUDIT: User {user.username} updated own profile "
                f"(Fields: {', '.join(changed_fields)}, IP: {ip_address})"
            )
    
    @staticmethod
    def log_privilege_escalation_attempt(user, attempted_action, ip_address, details=None):
        """
        Log privilege escalation attempts
        
        Args:
            user: User attempting escalation
            attempted_action: Description of the attempted action
            ip_address: IP address of the request
            details: Additional details about the attempt
        """
        logger.warning(
            f"SECURITY ALERT: Privilege escalation attempt by user {user.username} "
            f"(Action: {attempted_action}, IP: {ip_address}, Details: {details or 'None'})"
        )
    
    @staticmethod
    def log_malicious_input_attempt(user, field_name, input_value, ip_address):
        """
        Log malicious input attempts
        
        Args:
            user: User submitting malicious input
            field_name: Name of the field
            input_value: The malicious input (truncated for logging)
            ip_address: IP address of the request
        """
        truncated_input = input_value[:100] + '...' if len(input_value) > 100 else input_value
        logger.warning(
            f"SECURITY ALERT: Malicious input detected from user {user.username} "
            f"(Field: {field_name}, Input: {truncated_input}, IP: {ip_address})"
        )


def get_client_ip(request):
    """Get the real client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def sanitize_user_input(data_dict):
    """
    Sanitize a dictionary of user input data
    
    Args:
        data_dict: Dictionary of user input
        
    Returns:
        dict: Sanitized data dictionary
    """
    sanitized = {}
    validator = PersonalCabinetSecurityValidator()
    
    for key, value in data_dict.items():
        if isinstance(value, str):
            if key in ['first_name', 'last_name']:
                sanitized[key] = validator.validate_and_sanitize_text_field(value, key, 30)
            elif key == 'phone':
                sanitized[key] = validator.validate_phone_number(value)
            elif key == 'email':
                sanitized[key] = validator.validate_email_security(value)
            else:
                sanitized[key] = validator.validate_and_sanitize_text_field(value, key, 100)
        else:
            sanitized[key] = value
    
    return sanitized 