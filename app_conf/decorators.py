# SecBoard\app_conf\decorators.py
"""
License Decorators
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import HttpResponseForbidden
from django.template.response import TemplateResponse
import logging

logger = logging.getLogger(__name__)


def require_license_valid(view_func):
    """
    Decorator to verify license validity.

    Usage:
        @require_license_valid
        @login_required
        def my_view(request):
            ...
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        from app_conf.models import SecureLicense
        from app_conf.license_manager import LicenseValidator
        
        try:
            # Obtaining an active license
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            
            if not license_obj:
                logger.warning("License check failed: No active license")
                messages.error(request, _("No active license found. Please contact support."))
                return redirect('license_expired')
            
            # License validation
            is_valid, error_message = LicenseValidator.validate_license(license_obj)
            
            if not is_valid:
                logger.warning(f"License validation failed: {error_message}")
                messages.error(request, _("License validation failed: ") + str(error_message))
                return redirect('license_expired')
            
            # We add the license to the request for use in the view
            request.license = license_obj
            
            # Call the original view
            return view_func(request, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"License check error: {str(e)}")
            messages.error(request, _("License verification error. Please contact support."))
            return redirect('dashboard')
    
    return wrapped_view


def require_module_license(module_name):
    """
    Decorator to verify access to a specific module.

    Args:
        module_name (str): Module name ('risk', 'compliance', 'gdpr', etc.)

    Usage:
        @require_module_license('risk')
        @require_license_valid
        @login_required
        def risk_assessment_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Module access check disabled
            # from app_conf.models import SecureLicense
            # from app_conf.license_manager import LicenseValidator, ModuleAccessController
            # 
            # try:
            # # Checking the presence of a license in request
            #     if not hasattr(request, 'license'):
            # # If not, we try to get it
            #         license_obj = SecureLicense.objects.filter(is_active=True).first()
            #         if not license_obj:
            #             logger.warning(f"Module access denied for '{module_name}': No license")
            #             messages.error(request, _("No active license found."))
            #             return redirect('dashboard')
            #         request.license = license_obj
            #     
            # # Checking access to the module
            #     has_access = ModuleAccessController.check_access(request.license, module_name)
            #     
            #     if not has_access:
            #         module_info = ModuleAccessController.AVAILABLE_MODULES.get(module_name, {})
            #         module_display_name = module_info.get('name_uk', module_name)
            #         
            #         logger.warning(f"Module access denied: {module_name}")
            #         messages.warning(
            #             request,
            #             _("Your license does not include access to module: ") + module_display_name + ". " +
            #             _("Please contact support to upgrade your license.")
            #         )
            #         return redirect('dashboard')
            # 
            # # Access is allowed
            #     return view_func(request, *args, **kwargs)
            #     
            # except Exception as e:
            #     logger.error(f"Module access check error for '{module_name}': {str(e)}")
            #     messages.error(request, _("Error checking module access."))
            #     return redirect('dashboard')
            
            # Module access check disabled - allow all
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    return decorator


def check_user_limit(view_func):
    """
    Decorator to enforce user limit when creating a new user.

    Usage:
        @check_user_limit
        @login_required
        def create_user_view(request):
            ...
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        from app_conf.models import SecureLicense
        from django.contrib.auth.models import User
        
        try:
            # Verification only on creation (POST)
            if request.method == 'POST':
                license_obj = SecureLicense.objects.filter(is_active=True).first()
                
                if license_obj:
                    license_data = license_obj.get_license_data()
                    
                    if license_data:
                        max_users = license_data.get('max_users', 0)
                        current_users = User.objects.filter(is_active=True).count()
                        
                        if current_users >= max_users:
                            logger.warning(f"User limit reached: {current_users}/{max_users}")
                            messages.error(
                                request,
                                _("User limit reached ({current}/{max}). Cannot create new user. Please upgrade your license.").format(
                                    current=current_users,
                                    max=max_users
                                )
                            )
                            return redirect(request.path)
            
            return view_func(request, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"User limit check error: {str(e)}")
            return view_func(request, *args, **kwargs)
    
    return wrapped_view


def license_feature(feature_key):
    """
    Decorator to verify access to a specific feature/function.

    Can be used to restrict individual functions within modules.

    Args:
        feature_key (str): Feature key

    Usage:
        @license_feature('advanced_analytics')
        @require_license_valid
        @login_required
        def advanced_analytics_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            try:
                if not hasattr(request, 'license'):
                    from app_conf.models import SecureLicense
                    license_obj = SecureLicense.objects.filter(is_active=True).first()
                    if not license_obj:
                        messages.error(request, _("License not found."))
                        return redirect('dashboard')
                    request.license = license_obj
                
                # Obtaining license data
                license_data = request.license.get_license_data()
                if not license_data:
                    messages.error(request, _("License validation failed."))
                    return redirect('dashboard')
                
                # Checking features (if they are in the license)
                features = license_data.get('features', {})
                if feature_key not in features or not features[feature_key]:
                    logger.warning(f"Feature access denied: {feature_key}")
                    messages.warning(
                        request,
                        _("This feature is not available in your license. Please contact support.")
                    )
                    return redirect('dashboard')
                
                return view_func(request, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Feature check error for '{feature_key}': {str(e)}")
                messages.error(request, _("Error checking feature access."))
                return redirect('dashboard')
        
        return wrapped_view
    return decorator


def add_license_context(view_func):
    """
    Decorator to add license information to the template context.

    Usage:
        @add_license_context
        @login_required
        def dashboard(request):
            # In the template: license_info is available
            ...
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        from app_conf.models import SecureLicense
        from app_conf.license_manager import LicenseStatusChecker
        
        try:
            # Obtaining license status
            license_status = LicenseStatusChecker.get_license_status()
            
            # Add to the request for use in the template
            request.license_info = license_status
            
            # Call the original view
            response = view_func(request, *args, **kwargs)
            
            # If the response is a TemplateResponse, add to the context
            if isinstance(response, TemplateResponse):
                response.context_data = response.context_data or {}
                response.context_data['license_info'] = license_status
            
            return response
            
        except Exception as e:
            logger.error(f"Error adding license context: {str(e)}")
            return view_func(request, *args, **kwargs)
    
    return wrapped_view


class LicenseRequired:
    """
    Class-based decorator for CBV (Class-Based Views).

    Usage:
        from django.views.generic import ListView
        from django.utils.decorators import method_decorator

        @method_decorator(require_license_valid, name='dispatch')
        @method_decorator(require_module_license('risk'), name='dispatch')
        class RiskListView(ListView):
            model = Risk
            ...
    """
    
    def __init__(self, module_name=None):
        self.module_name = module_name
    
    def __call__(self, view_class):
        """Apply decorator to CBV"""
        from django.utils.decorators import method_decorator
        
        # Basic license check
        decorated_class = method_decorator(
            require_license_valid,
            name='dispatch'
        )(view_class)
        
        # Module Check (if specified)
        if self.module_name:
            decorated_class = method_decorator(
                require_module_license(self.module_name),
                name='dispatch'
            )(decorated_class)
        
        return decorated_class


# API decorators
def api_require_license(view_func):
    """
    Decorator for API endpoints (DRF).
    Returns a JSON response instead of a redirect.

    Usage:
        from rest_framework.decorators import api_view

        @api_view(['GET'])
        @api_require_license
        def api_data(request):
            ...
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        from django.http import JsonResponse
        from app_conf.models import SecureLicense
        from app_conf.license_manager import LicenseValidator
        
        try:
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            
            if not license_obj:
                return JsonResponse({
                    'error': 'No active license',
                    'detail': 'License not found or expired'
                }, status=403)
            
            is_valid, error_message = LicenseValidator.validate_license(license_obj)
            
            if not is_valid:
                return JsonResponse({
                    'error': 'License invalid',
                    'detail': error_message
                }, status=403)
            
            request.license = license_obj
            return view_func(request, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"API license check error: {str(e)}")
            return JsonResponse({
                'error': 'License verification error',
                'detail': str(e)
            }, status=500)
    
    return wrapped_view


def api_require_module(module_name):
    """
    Decorator for API endpoints with module access check.

    Usage:
        @api_view(['GET'])
        @api_require_module('risk')
        def api_risk_data(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Module access check disabled
            # from django.http import JsonResponse
            # from app_conf.models import SecureLicense
            # from app_conf.license_manager import ModuleAccessController
            # 
            # try:
            #     if not hasattr(request, 'license'):
            #         license_obj = SecureLicense.objects.filter(is_active=True).first()
            #         if not license_obj:
            #             return JsonResponse({
            #                 'error': 'No active license'
            #             }, status=403)
            #         request.license = license_obj
            #     
            #     has_access = ModuleAccessController.check_access(request.license, module_name)
            #     
            #     if not has_access:
            #         return JsonResponse({
            #             'error': 'Module access denied',
            #             'detail': f'Your license does not include access to {module_name} module'
            #         }, status=403)
            # 
            #     return view_func(request, *args, **kwargs)
            #     
            # except Exception as e:
            #     logger.error(f"API module check error for '{module_name}': {str(e)}")
            #     return JsonResponse({
            #         'error': 'Module access verification error',
            #         'detail': str(e)
            #     }, status=500)
            
            # Module access check disabled - allow all
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    return decorator

