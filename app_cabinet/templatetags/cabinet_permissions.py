"""
Template tags for cabinet permissions
"""
from django import template
from ..permissions import has_permission

register = template.Library()


@register.filter
def has_cabinet_permission(user, permission_string):
    """
    Template filter to check cabinet permissions
    Usage: {% if user|has_cabinet_permission:"users:view" %}
    """
    try:
        permission_type, action = permission_string.split(':')
        return has_permission(user, permission_type, action)
    except (ValueError, AttributeError):
        return False


@register.simple_tag
def check_cabinet_permission(user, permission_type, action=None):
    """
    Template tag to check cabinet permissions
    Usage: {% check_cabinet_permission user "users" "view" as can_view_users %}
    """
    return has_permission(user, permission_type, action)


@register.inclusion_tag('app_cabinet/permission_check.html')
def show_if_permitted(user, permission_type, action=None):
    """
    Inclusion tag to conditionally show content based on permissions
    Usage: {% show_if_permitted user "users" "view" %}
    """
    return {
        'has_permission': has_permission(user, permission_type, action),
        'user': user,
        'permission_type': permission_type,
        'action': action
    } 