#  SecBoard\SecBoard\app_gdpr\permissions.py

from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _
from .models import GDPRAccess
import logging

logger = logging.getLogger(__name__)


def get_user_accessible_companies_gdpr(user):
    """
    Get list of companies accessible to user based on GDPRAccess
    Returns None if user has access to all companies
    """
    if not user.is_authenticated:
        return []
    
    # Superusers have access to all companies
    if user.is_superuser:
        return None
    
    # Get user groups
    user_groups = user.groups.all()
    if not user_groups.exists():
        return []
    
    accessible_companies = set()
    has_unrestricted_access = False
    
    for group in user_groups:
        try:
            access = GDPRAccess.objects.get(group=group, has_access_compliance_dashboard=True)
            # If no companies specified, user has access to all
            if not access.companies.exists():
                has_unrestricted_access = True
                break
            # Add companies from this access configuration
            accessible_companies.update(access.companies.all())
        except GDPRAccess.DoesNotExist:
            continue
    
    # If any group has unrestricted access, return None (all companies)
    if has_unrestricted_access:
        return None
    
    return list(accessible_companies) if accessible_companies else []


def has_company_access_gdpr(user, company):
    """Return True if user can access given company according to GDPRAccess.companies.
    If user's access is unrestricted (None from getter), allow.
    If no companies configured for user (empty list), deny unless company is None.
    """
    if company is None:
        # Records without company are visible only when unrestricted access
        accessible = get_user_accessible_companies_gdpr(user)
        return accessible is None
    accessible = get_user_accessible_companies_gdpr(user)
    if accessible is None:
        return True
    return company in accessible


def check_gdpr_access(user, required_permission=None):
    """
    Check if user has access to GDPR module based on GDPRAccess model
    
    Args:
        user: Django User object
        required_permission: Optional specific permission to check (e.g., 'has_access_data_subjects', 'process_dsr')
    
    Returns:
        bool: True if user has access, False otherwise
    """
    if not user.is_authenticated:
        return False
    
    # Superusers have full access
    if user.is_superuser:
        return True
    
    # Get user groups
    user_groups = user.groups.all()
    if not user_groups.exists():
        return False
    
    # Check if any of user's groups have GDPR access
    for group in user_groups:
        try:
            access = GDPRAccess.objects.get(group=group)
            if access.has_access_compliance_dashboard:
                # If specific permission is required, check it
                if required_permission:
                    # "has_access_*" permissions - viewing access
                    if required_permission == 'has_access_data_subjects' and not access.has_access_data_subjects:
                        continue
                    elif required_permission == 'has_access_dsr' and not access.has_access_dsr:
                        continue
                    elif required_permission == 'has_access_consents' and not access.has_access_consents:
                        continue
                    elif required_permission == 'has_access_breach_management' and not access.has_access_breach_management:
                        continue
                    elif required_permission == 'has_access_dpia' and not access.has_access_dpia:
                        continue
                    # "can_*" permissions - specific actions
                    elif required_permission == 'can_export_data_subjects' and not access.can_export_data_subjects:
                        continue
                    elif required_permission == 'can_process_dsr' and not access.can_process_dsr:
                        continue
                    elif required_permission == 'can_approve_dsr' and not access.can_approve_dsr:
                        continue
                    elif required_permission == 'can_manage_consents' and not access.can_manage_consents:
                        continue
                    elif required_permission == 'can_report_breach' and not access.can_report_breach:
                        continue
                    elif required_permission == 'can_investigate_breach' and not access.can_investigate_breach:
                        continue
                    elif required_permission == 'can_conduct_dpia' and not access.can_conduct_dpia:
                        continue
                    elif required_permission == 'can_approve_dpia' and not access.can_approve_dpia:
                        continue
                    elif required_permission == 'can_generate_reports' and not access.can_generate_reports:
                        continue
                    elif required_permission == 'can_edit_data_subjects' and not access.can_edit_data_subjects:
                        continue
                    elif required_permission == 'can_edit_breaches' and not access.can_edit_breaches:
                        continue
                    elif required_permission == 'can_edit_activities' and not access.can_edit_activities:
                        continue
                    elif required_permission == 'can_edit_policies' and not access.can_edit_policies:
                        continue
                
                return True
        except GDPRAccess.DoesNotExist:
            continue
    
    # No access if no group has has_access_compliance_dashboard=True
    return False


def gdpr_access_required(permission=None):
    """
    Decorator to check GDPR access for function-based views
    
    Usage:
        @gdpr_access_required()
        def some_view(request):
            ...
        
        @gdpr_access_required('process_dsr')
        def process_dsr_view(request):
            ...
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not check_gdpr_access(request.user, permission):
                logger.warning(
                    f"User {request.user.username} denied access to GDPR module "
                    f"(required permission: {permission})"
                )
                raise PermissionDenied(_("You don't have permission to access GDPR Compliance module"))
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class GDPRAccessMixin:
    """
    Mixin for class-based views to check GDPR access
    
    Usage:
        class SomeView(GDPRAccessMixin, ListView):
            required_gdpr_permission = 'has_access_data_subjects'  # Optional
            ...
    """
    required_gdpr_permission = None
    
    def dispatch(self, request, *args, **kwargs):
        if not check_gdpr_access(request.user, self.required_gdpr_permission):
            logger.warning(
                f"User {request.user.username} denied access to GDPR module "
                f"(required permission: {self.required_gdpr_permission})"
            )
            raise PermissionDenied(_("You don't have permission to access GDPR Compliance module"))
        return super().dispatch(request, *args, **kwargs)
