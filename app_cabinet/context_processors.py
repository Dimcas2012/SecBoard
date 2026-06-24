"""
Context processors for app_cabinet
"""
import logging

from .permissions import has_permission

logger = logging.getLogger(__name__)


def header_tasks_count(request):
    """
    Add total Tasks count for the header (same as Personal Cabinet Tasks tab).
    Uses get_tasks_count_for_cabinet_user so the number matches app_cabinet/personal-cabinet/ exactly.
    Returns 0 if user not authenticated or profile not ready.
    """
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'header_tasks_count': 0}
    try:
        from .models import CabinetUser
        from .views import get_tasks_count_for_cabinet_user

        cabinet_user, _ = CabinetUser.objects.get_or_create(user=request.user)
        if not cabinet_user.company_id:
            return {'header_tasks_count': 0}
        count = get_tasks_count_for_cabinet_user(cabinet_user)
    except Exception as e:
        logger.warning("header_tasks_count failed: %s", e, exc_info=True)
        count = 0
    return {'header_tasks_count': count}


def cabinet_permissions(request):
    """
    Add user permissions to template context
    """
    if not request.user.is_authenticated:
        return {'user_permissions': {}}
    
    permissions = {
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
    # Executive View: show link if user has cabinet profile with at least one platform role
    show_executive_view = False
    try:
        from .models import CabinetUser
        cu = CabinetUser.objects.filter(user=request.user).prefetch_related('roles').first()
        if cu and cu.roles.filter(is_active=True).exists():
            show_executive_view = True
    except Exception:
        pass
    return {'user_permissions': permissions, 'show_executive_view': show_executive_view} 