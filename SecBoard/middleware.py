#  SecBoard\SecBoard\middleware.py
from django.http import HttpResponseForbidden, JsonResponse
from django.core.cache import cache
from django.contrib.auth import logout
from django.utils.translation import gettext as _
import json
from django.http import HttpResponse
from django.conf import settings
from .views_i18n import raw_status_check
import time
import hashlib
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class LoginSecurityMiddleware:
    """
    Comprehensive login security middleware with rate limiting, progressive delays,
    and CAPTCHA requirements to prevent brute-force attacks and credential stuffing.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Check both user and admin login paths
        if request.path in ['/app_cabinet/login/', '/secboard_admin/login/']:
            ip = self.get_client_ip(request)
            
            # Create cache keys
            ip_attempts_key = f'login_attempts_{ip}'
            ip_lockout_key = f'login_lockout_{ip}'
            
            # Check if IP is currently locked out
            lockout_info = cache.get(ip_lockout_key)
            if lockout_info:
                lockout_until = lockout_info.get('until', 0)
                if time.time() < lockout_until:
                    remaining_time = int(lockout_until - time.time())
                    return HttpResponseForbidden(
                        _('IP address temporarily blocked due to too many failed login attempts. '
                          'Please try again in {} minutes.').format(remaining_time // 60 + 1)
                    )
                else:
                    # Lockout expired, clear it
                    cache.delete(ip_lockout_key)
                    cache.delete(ip_attempts_key)
            
            # Get current attempt count
            attempts_info = cache.get(ip_attempts_key, {'count': 0, 'first_attempt': time.time()})
            
            # If this is a POST request (actual login attempt)
            if request.method == 'POST':
                email = request.POST.get('email', '').lower()
                
                # Create user-specific cache key
                user_attempts_key = f'user_login_attempts_{hashlib.md5(email.encode()).hexdigest()}'
                user_attempts = cache.get(user_attempts_key, {'count': 0, 'first_attempt': time.time()})
                
                # Check user-specific rate limit
                if user_attempts['count'] >= getattr(settings, 'USER_LOGIN_ATTEMPT_LIMIT', 5):
                    user_lockout_until = user_attempts['first_attempt'] + getattr(settings, 'USER_LOGIN_LOCKOUT_DURATION', 1800)  # 30 minutes
                    if time.time() < user_lockout_until:
                        remaining_time = int(user_lockout_until - time.time())
                        return HttpResponseForbidden(
                            _('This account is temporarily locked due to too many failed login attempts. '
                              'Please try again in {} minutes or reset your password.').format(remaining_time // 60 + 1)
                        )
                
                # Process the request
                response = self.get_response(request)
                
                # Check if login failed (we'll detect this in the view)
                if hasattr(request, '_login_failed'):
                    # Increment IP attempts
                    attempts_info['count'] += 1
                    if attempts_info['count'] == 1:
                        attempts_info['first_attempt'] = time.time()
                    
                    # Increment user attempts
                    user_attempts['count'] += 1
                    if user_attempts['count'] == 1:
                        user_attempts['first_attempt'] = time.time()
                    
                    # Set progressive delays based on attempt count
                    delay = min(attempts_info['count'] * 2, 30)  # Max 30 seconds delay
                    time.sleep(delay)
                    
                    # Set lockout if too many attempts from IP
                    if attempts_info['count'] >= getattr(settings, 'IP_LOGIN_ATTEMPT_LIMIT', 10):
                        lockout_duration = getattr(settings, 'IP_LOGIN_LOCKOUT_DURATION', 3600)  # 1 hour
                        cache.set(ip_lockout_key, {'until': time.time() + lockout_duration}, lockout_duration)
                        cache.delete(ip_attempts_key)
                    else:
                        cache.set(ip_attempts_key, attempts_info, getattr(settings, 'LOGIN_ATTEMPT_WINDOW', 3600))
                    
                    # Update user attempts
                    cache.set(user_attempts_key, user_attempts, getattr(settings, 'USER_LOGIN_LOCKOUT_DURATION', 1800))
                    
                elif hasattr(request, '_login_success'):
                    # Clear attempts on successful login
                    cache.delete(ip_attempts_key)
                    cache.delete(user_attempts_key)
                
                return response
            else:
                # GET request - check if CAPTCHA is required
                if attempts_info['count'] >= getattr(settings, 'LOGIN_CAPTCHA_THRESHOLD', 3):
                    request.require_captcha = True
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        """Get the real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class AdminLoginRateLimitMiddleware:
    """Legacy admin login rate limiting - kept for backward compatibility"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/secboard_admin/login/'):
            ip = self.get_client_ip(request)
            login_attempts = cache.get(f'login_attempts_{ip}', 0)

            if login_attempts >= 5:  # Maximum 5 attempts
                return HttpResponseForbidden(_('Too many login attempts. Please try again later.'))

            response = self.get_response(request)

            # If login failed, increment the counter
            if request.method == 'POST' and response.status_code == 200:
                cache.set(f'login_attempts_{ip}', login_attempts + 1, 300)  # Reset after 5 minutes

            return response
        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

class StatusCheckMiddleware:
    """
    Middleware that completely bypasses Django's middleware stack for status check requests.
    This must be the first middleware in the MIDDLEWARE setting to work properly.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        """
        Check if this is a status check request and handle it directly.
        """
        # Check if this is a request to the status endpoint
        if request.path == '/service-status/':
            # Skip authentication check for simplicity or implement your own here
            # You might want to add IP-based restrictions or simple token auth
            
            # Get the status directly
            status_data = raw_status_check()
            
            # Return a direct response without going through the middleware stack
            return HttpResponse(
                json.dumps(status_data),
                content_type='application/json'
            )
            
        # Not a status check request, continue normal processing
        return self.get_response(request)

class SessionSecurityMiddleware:
    """
    Enhanced session security middleware to prevent:
    - Session fixation attacks
    - Session hijacking  
    - Concurrent session abuse
    - IP address changes within sessions
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Check for IP address changes
            if getattr(settings, 'SESSION_TRACK_IP_CHANGES', True):
                self._check_ip_changes(request)
            
            # Enforce concurrent session limits
            self._enforce_session_limits(request)
            
            # Update last activity
            self._update_last_activity(request)
            
            # Check for session timeout
            if self._is_session_expired(request):
                logger.warning(f"Session expired for user {request.user.username}")
                logout(request)
                return redirect(reverse('login'))

        response = self.get_response(request)
        return response

    def _check_ip_changes(self, request):
        """Check if IP address has changed during the session"""
        current_ip = self._get_client_ip(request)
        session_ip = request.session.get('session_ip')
        
        if session_ip and session_ip != current_ip:
            logger.warning(
                f"IP address change detected for user {request.user.username}: "
                f"{session_ip} -> {current_ip}"
            )
            # Log security event but don't terminate session (could be legitimate)
            # In high-security environments, you might want to logout the user
            request.session['ip_change_detected'] = True
            request.session['ip_change_time'] = timezone.now().isoformat()
        
        # Always update the current IP
        request.session['session_ip'] = current_ip

    def _enforce_session_limits(self, request):
        """Enforce maximum concurrent sessions per user"""
        max_sessions = getattr(settings, 'SESSION_MAX_CONCURRENT_SESSIONS', 3)
        if max_sessions <= 0:
            return
            
        # Get all active sessions for this user
        user_sessions = Session.objects.filter(
            expire_date__gte=timezone.now()
        )
        
        current_session_key = request.session.session_key
        user_session_count = 0
        
        for session in user_sessions:
            try:
                session_data = session.get_decoded()
                if session_data.get('_auth_user_id') == str(request.user.id):
                    user_session_count += 1
                    
                    # If this is not the current session and we're over the limit
                    if (user_session_count > max_sessions and 
                        session.session_key != current_session_key):
                        session.delete()
                        logger.info(
                            f"Deleted excess session for user {request.user.username} "
                            f"(limit: {max_sessions})"
                        )
                        
            except Exception as e:
                logger.error(f"Error processing session data: {e}")

    def _update_last_activity(self, request):
        """Update last activity timestamp"""
        request.session['last_activity'] = timezone.now().isoformat()

    def _is_session_expired(self, request):
        """Check if session has expired due to inactivity"""
        last_activity_str = request.session.get('last_activity')
        if not last_activity_str:
            return False
            
        try:
            last_activity = timezone.datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
            session_timeout = timedelta(seconds=settings.SESSION_COOKIE_AGE)
            
            if timezone.now() - last_activity > session_timeout:
                return True
        except (ValueError, AttributeError):
            pass
            
        return False

    def _get_client_ip(self, request):
        """Get the real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class SecurityHeadersMiddleware:
    """
    Middleware to add security headers including permissions policy fixes
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add permissions policy header to allow necessary features
        # Allow clipboard operations for all pages (needed for copy functionality)
        response['Permissions-Policy'] = (
            'clipboard-read=*, '
            'clipboard-write=*, '
            'fullscreen=*, '
            'geolocation=(), '
            'camera=(), '
            'microphone=(), '
            'payment=(), '
            'usb=(), '
            'accelerometer=(), '
            'gyroscope=(), '
            'magnetometer=()'
        )
        
        # Add other security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Only set X-Frame-Options for non-admin pages (admin might need frames)
        if '/admin/' not in request.path and '/secboard_admin/' not in request.path:
            response['X-Frame-Options'] = 'DENY'
        
        return response