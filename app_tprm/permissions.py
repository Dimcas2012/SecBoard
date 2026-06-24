#  SecBoard\SecBoard\app_tprm\permissions.py

from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _
from .models import TPRMAccess
import logging

logger = logging.getLogger(__name__)


def get_user_accessible_companies_tprm(user):
    """
    Get list of companies accessible to user based on TPRMAccess
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
            access = TPRMAccess.objects.get(group=group, has_access_dashboard=True)
            # If no companies specified, user has access to all
            if not access.companies.exists():
                has_unrestricted_access = True
                break
            # Add companies from this access configuration
            accessible_companies.update(access.companies.all())
        except TPRMAccess.DoesNotExist:
            continue
    
    # If any group has unrestricted access, return None (all companies)
    if has_unrestricted_access:
        return None
    
    return list(accessible_companies) if accessible_companies else []


def has_company_access_tprm(user, company):
    """Return True if user can access given company according to TPRMAccess.companies.
    If user's access is unrestricted (None from getter), allow.
    If no companies configured for user (empty list), deny unless company is None.
    """
    if company is None:
        # Records without company are visible only when unrestricted access
        accessible = get_user_accessible_companies_tprm(user)
        return accessible is None
    accessible = get_user_accessible_companies_tprm(user)
    if accessible is None:
        return True
    return company in accessible


def check_tprm_access(user, required_permission=None):
    """
    Check if user has access to TPRM module based on TPRMAccess model
    
    Args:
        user: Django User object
        required_permission: Optional specific permission to check (e.g., 'has_access_vendors', 'can_edit_vendors')
    
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
    
    # Check if any of user's groups have TPRM access
    for group in user_groups:
        try:
            access = TPRMAccess.objects.get(group=group)
            if access.has_access_dashboard:
                # If specific permission is required, check it
                if required_permission:
                    # Vendor Management permissions
                    if required_permission == 'has_access_vendors' and not access.has_access_vendors:
                        continue
                    elif required_permission == 'can_edit_vendors' and not access.can_edit_vendors:
                        continue
                    elif required_permission == 'can_delete_vendors' and not access.can_delete_vendors:
                        continue
                    # Assessment permissions
                    elif required_permission == 'has_access_assessments' and not access.has_access_assessments:
                        continue
                    elif required_permission == 'can_conduct_assessments' and not access.can_conduct_assessments:
                        continue
                    elif required_permission == 'can_approve_assessments' and not access.can_approve_assessments:
                        continue
                    # Document permissions
                    elif required_permission == 'has_access_documents' and not access.has_access_documents:
                        continue
                    elif required_permission == 'can_upload_documents' and not access.can_upload_documents:
                        continue
                    elif required_permission == 'can_delete_documents' and not access.can_delete_documents:
                        continue
                    # Template permissions
                    elif required_permission == 'has_access_templates' and not access.has_access_templates:
                        continue
                    elif required_permission == 'can_edit_templates' and not access.can_edit_templates:
                        continue
                    elif required_permission == 'can_manage_questions' and not access.can_manage_questions:
                        continue
                    # Questionnaire permissions
                    elif required_permission == 'has_access_questionnaires' and not access.has_access_questionnaires:
                        continue
                    elif required_permission == 'can_complete_questionnaires' and not access.can_complete_questionnaires:
                        continue
                    elif required_permission == 'can_review_questionnaires' and not access.can_review_questionnaires:
                        continue
                    # Reporting permissions
                    elif required_permission == 'can_generate_reports' and not access.can_generate_reports:
                        continue
                    elif required_permission == 'can_export_data' and not access.can_export_data:
                        continue
                    # Risk management permissions
                    elif required_permission == 'can_change_risk_level' and not access.can_change_risk_level:
                        continue
                    elif required_permission == 'can_change_vendor_status' and not access.can_change_vendor_status:
                        continue
                
                return True
        except TPRMAccess.DoesNotExist:
            continue
    
    # No access if no group has has_access_dashboard=True
    return False


def tprm_access_required(permission=None):
    """
    Decorator to check TPRM access for function-based views
    
    Usage:
        @tprm_access_required()
        def some_view(request):
            ...
        
        @tprm_access_required('can_edit_vendors')
        def edit_vendor_view(request):
            ...
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not check_tprm_access(request.user, permission):
                logger.warning(
                    f"User {request.user.username} denied access to TPRM module "
                    f"(required permission: {permission})"
                )
                raise PermissionDenied(_("You don't have permission to access TPRM module"))
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class TPRMAccessMixin:
    """
    Mixin for class-based views to check TPRM access
    
    Usage:
        class SomeView(TPRMAccessMixin, ListView):
            required_tprm_permission = 'has_access_vendors'  # Optional
            ...
    """
    required_tprm_permission = None
    
    def dispatch(self, request, *args, **kwargs):
        if not check_tprm_access(request.user, self.required_tprm_permission):
            logger.warning(
                f"User {request.user.username} denied access to TPRM module "
                f"(required permission: {self.required_tprm_permission})"
            )
            raise PermissionDenied(_("You don't have permission to access TPRM module"))
        return super().dispatch(request, *args, **kwargs)

