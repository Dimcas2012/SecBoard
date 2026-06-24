"""
Security validators and utilities for Personal Cabinet functionality
Prevents XSS, SQL Injection, and Privilege Escalation attacks
"""

import re
import html
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.core.validators import validate_email
import logging

# Try to import bleach, fall back to basic HTML escaping if not available
try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    # Fallback: use basic HTML escaping

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
        
        # Use bleach if available, otherwise rely on html.escape
        if BLEACH_AVAILABLE:
            value = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, protocols=ALLOWED_PROTOCOLS)
        else:
            # Fallback: remove any remaining HTML-like patterns
            value = re.sub(r'<[^>]+>', '', value)
        
        # Additional character validation for names
        if field_name.lower() in ['first_name', 'last_name']:
            if not re.match(r'^[a-zA-ZА-Яа-яІіЇїЄєґҐ\s\-\'\.]+$', value):
                raise ValidationError(
                    _('%(field)s can only contain letters, spaces, hyphens, apostrophes, and periods.'),
                    params={'field': field_name}
                )
        
        return value
    
    @staticmethod
    def validate_privilege_escalation_attempt(request_user, target_user_id=None, 
                                            company_change=None, department_change=None, 
                                            position_change=None):
        """
        Validate that user is not attempting privilege escalation
        """
        # Check if user has permission to edit users
        from .permissions import has_permission
        
        # Users can only modify their own profile unless they have proper permissions
        if target_user_id and target_user_id != request_user.id:
            # Check if user has permission to edit users or is staff
            if not (request_user.is_staff or has_permission(request_user, 'users', 'edit')):
                logger.warning(f"User {request_user.username} attempted to modify user {target_user_id}")
                raise ValidationError(_('You can only modify your own profile.'))
        
        # Regular users without proper permissions cannot change sensitive fields
        if not (request_user.is_staff or has_permission(request_user, 'users', 'edit')):
            if company_change:
                logger.warning(f"User {request_user.username} attempted to change company")
                raise ValidationError(_('You cannot change your company assignment.'))
            
            if department_change:
                logger.warning(f"User {request_user.username} attempted to change department")
                raise ValidationError(_('You cannot change your department assignment.'))
            
            if position_change:
                logger.warning(f"User {request_user.username} attempted to change position")
                raise ValidationError(_('You cannot change your position assignment.'))


class PersonalCabinetAuditLogger:
    """Audit logging for personal cabinet security events"""
    
    @staticmethod
    def log_profile_update(user, changed_fields, ip_address, target_user=None):
        """Log profile update events for security monitoring"""
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
        """Log privilege escalation attempts"""
        logger.warning(
            f"SECURITY ALERT: Privilege escalation attempt by user {user.username} "
            f"(Action: {attempted_action}, IP: {ip_address}, Details: {details or 'None'})"
        )
    
    @staticmethod
    def log_malicious_input_attempt(user, field_name, input_value, ip_address):
        """Log malicious input attempts"""
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