# app_gophish/context_processors.py

from .views import check_gophish_access


def gophish_permissions(request):
    """
    Context processor that adds Gophish permission flags to all templates
    """
    if not request.user.is_authenticated:
        return {
            'can_view_campaigns': False,
            'can_view_templates': False,
            'can_view_landing_pages': False,
            'can_view_sending_profiles': False,
            'can_view_groups': False,
            'can_manage_servers': False,
            'can_sync': False,
        }
    
    return {
        'can_view_campaigns': check_gophish_access(request.user, 'view_campaigns'),
        'can_view_templates': check_gophish_access(request.user, 'view_templates'),
        'can_view_landing_pages': check_gophish_access(request.user, 'view_landing_pages'),
        'can_view_sending_profiles': check_gophish_access(request.user, 'view_sending_profiles'),
        'can_view_groups': check_gophish_access(request.user, 'view_groups'),
        'can_manage_servers': check_gophish_access(request.user, 'manage_servers'),
        'can_sync': check_gophish_access(request.user, 'sync'),
    }

