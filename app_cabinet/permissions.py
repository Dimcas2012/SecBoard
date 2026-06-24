"""
Permission checking utilities for app_cabinet AccessOptions
"""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.db import models
from .models import AccessOptions


def get_user_access_options(user):
    """
    Get AccessOptions for a user based on their groups
    """
    if not user.is_authenticated:
        return None
    
    # Superusers have all permissions
    if user.is_superuser:
        return "superuser"
    
    # Get user's groups
    user_groups = user.groups.all()
    
    # Get all AccessOptions for user's groups
    access_options = AccessOptions.objects.filter(group__in=user_groups)
    
    # If user has cabinet profile, filter by company
    if hasattr(user, 'cabinet') and user.cabinet.company:
        access_options = access_options.filter(
            models.Q(companies__isnull=True) | 
            models.Q(companies=user.cabinet.company)
        )
    
    return access_options


def get_user_accessible_companies(user):
    """
    Get companies that the user has access to based on their AccessOptions
    This function is specifically for org_chart access and checks has_access_org_chart permission
    """
    from app_conf.models import Company
    
    if not user.is_authenticated:
        return Company.objects.none()
    
    # Superusers have access to all companies
    if user.is_superuser:
        return Company.objects.all()
    
    # Check if user is staff and has no specific access restrictions
    if user.is_staff:
        user_groups = user.groups.all()
        # Check if user has any access restrictions through AccessOptions
        access_records = AccessOptions.objects.filter(
            group__in=user_groups,
            has_access_org_chart=True
        )
        
        if not access_records.exists():
            # If staff user has no access restrictions, give access to all companies
            return Company.objects.all()
    
    # Get companies through access records
    user_groups = user.groups.all()
    access_records = AccessOptions.objects.filter(
        group__in=user_groups,
        has_access_org_chart=True
    )
    
    companies = Company.objects.none()
    for access in access_records:
        if access.companies.exists():
            companies = companies | access.companies.all()
        else:
            # If no specific companies are set, user has access to all companies
            companies = Company.objects.all()
            break
    
    # If no companies found through access records, try to get companies where user is a cabinet user
    if not companies.exists():
        try:
            from .models import CabinetUser
            cabinet_user = CabinetUser.objects.filter(user=user).first()
            if cabinet_user and cabinet_user.company:
                companies = Company.objects.filter(id=cabinet_user.company.id)
        except:
            pass
    
    # Last fallback: if still no companies and user is authenticated, give access to all companies
    if not companies.exists() and user.is_authenticated:
        companies = Company.objects.all()
    
    return companies.distinct()


def has_permission(user, permission_type, action=None):
    """
    Check if user has specific permission
    
    Args:
        user: Django User instance
        permission_type: str - 'users', 'groups', 'companies', 'org_structure', 'site_statistics'
        action: str - 'view', 'add', 'edit', 'delete', 'export', 'detailed'
    """
    if not user.is_authenticated:
        return False
    
    # Superusers have all permissions
    if user.is_superuser:
        return True
    
    access_options = get_user_access_options(user)
    if access_options == "superuser":
        return True
    
    if not access_options.exists():
        return False
    
    # Check permissions based on type and action
    permission_checks = {
        'users': {
            'view': 'has_access_users',
            'add': 'can_add_users',
            'edit': 'can_edit_users',
            'delete': 'can_delete_users',
            'export': 'can_export_users',
        },
        'roles': {
            'view': 'has_access_roles',
            'add': 'can_add_roles',
            'edit': 'can_edit_roles',
            'delete': 'can_delete_roles',
        },
        'groups': {
            'view': 'has_access_groups',
            'add': 'can_add_groups',
            'edit': 'can_edit_groups',
            'delete': 'can_delete_groups',
        },
        'org_structure': {
            'view': 'has_access_org_structure',
            'add_companies': 'can_add_companies',
            'edit_companies': 'can_edit_companies',
            'delete_companies': 'can_delete_companies',
            'add_departments': 'can_add_departments',
            'edit_departments': 'can_edit_departments',
            'delete_departments': 'can_delete_departments',
            'add_positions': 'can_add_positions',
            'edit_positions': 'can_edit_positions',
            'delete_positions': 'can_delete_positions',
        },
        'org_chart': {
            'view': 'has_access_org_chart',
        },
        'site_statistics': {
            'view': 'has_access_site_statistics',
            'export': 'can_export_statistics',
            'detailed': 'can_view_detailed_statistics',
        }
    }
    
    if permission_type not in permission_checks:
        return False
    
    if action and action not in permission_checks[permission_type]:
        return False
    
    # If no specific action, check for base access
    if not action:
        action = 'view'
    
    permission_field = permission_checks[permission_type][action]
    
    # Check if any of the user's access options grants this permission
    for access_option in access_options:
        if getattr(access_option, permission_field, False):
            return True
    
    return False


def require_permission(permission_type, action=None, ajax=False):
    """
    Decorator to require specific permission for a view
    
    Args:
        permission_type: str - 'users', 'groups', 'companies', 'org_structure', 'site_statistics'
        action: str - 'view', 'add', 'edit', 'delete', 'export', 'detailed'
        ajax: bool - whether this is an AJAX view
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not has_permission(request.user, permission_type, action):
                if ajax:
                    return JsonResponse({
                        'error': _('You do not have permission to perform this action.'),
                        'permission_required': f"{permission_type}:{action or 'view'}"
                    }, status=403)
                else:
                    messages.error(request, _('You do not have permission to access this page.'))
                    return redirect('unauthorized')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_permission_middleware(get_response):
    """
    Middleware to check permissions for cabinet views
    """
    def middleware(request):
        # Skip permission checks for certain paths
        skip_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/accounts/login/',
            '/login/',
            '/logout/',
            '/unauthorized/',
        ]
        
        if any(request.path.startswith(path) for path in skip_paths):
            return get_response(request)
        
        # Add permission info to request
        if request.user.is_authenticated:
            request.user_permissions = {
                'users': {
                    'view': has_permission(request.user, 'users', 'view'),
                    'add': has_permission(request.user, 'users', 'add'),
                    'edit': has_permission(request.user, 'users', 'edit'),
                    'delete': has_permission(request.user, 'users', 'delete'),
                    'export': has_permission(request.user, 'users', 'export'),
                },
                'roles': {
                    'view': has_permission(request.user, 'roles', 'view'),
                    'add': has_permission(request.user, 'roles', 'add'),
                    'edit': has_permission(request.user, 'roles', 'edit'),
                    'delete': has_permission(request.user, 'roles', 'delete'),
                },
                'groups': {
                    'view': has_permission(request.user, 'groups', 'view'),
                    'add': has_permission(request.user, 'groups', 'add'),
                    'edit': has_permission(request.user, 'groups', 'edit'),
                    'delete': has_permission(request.user, 'groups', 'delete'),
                },
                'org_structure': {
                    'view': has_permission(request.user, 'org_structure', 'view'),
                    'add_companies': has_permission(request.user, 'org_structure', 'add_companies'),
                    'edit_companies': has_permission(request.user, 'org_structure', 'edit_companies'),
                    'delete_companies': has_permission(request.user, 'org_structure', 'delete_companies'),
                    'add_departments': has_permission(request.user, 'org_structure', 'add_departments'),
                    'edit_departments': has_permission(request.user, 'org_structure', 'edit_departments'),
                    'delete_departments': has_permission(request.user, 'org_structure', 'delete_departments'),
                    'add_positions': has_permission(request.user, 'org_structure', 'add_positions'),
                    'edit_positions': has_permission(request.user, 'org_structure', 'edit_positions'),
                    'delete_positions': has_permission(request.user, 'org_structure', 'delete_positions'),
                },
                'org_chart': {
                    'view': has_permission(request.user, 'org_chart', 'view'),
                },
                'site_statistics': {
                    'view': has_permission(request.user, 'site_statistics', 'view'),
                    'export': has_permission(request.user, 'site_statistics', 'export'),
                    'detailed': has_permission(request.user, 'site_statistics', 'detailed'),
                }
            }
        
        response = get_response(request)
        return response
    
    return middleware 