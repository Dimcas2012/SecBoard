"""
Utility functions and decorators for CIF module access control.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from app_conf.models import Company

from .models import AccessCIF


def get_user_company(user):
    if hasattr(user, 'cabinet') and hasattr(user.cabinet, 'company'):
        return user.cabinet.company
    if hasattr(user, 'profile') and hasattr(user.profile, 'company'):
        return user.profile.company
    return Company.objects.first()


def get_user_accessible_companies(user):
    if user.is_superuser or user.is_staff:
        return Company.objects.all()

    user_groups = user.groups.all()
    access_configs = AccessCIF.objects.filter(
        group__in=user_groups,
    ).filter(
        models_q_has_any_cif_access(),
    ).prefetch_related('companies')

    if not access_configs.exists():
        user_company = get_user_company(user)
        if user_company:
            return Company.objects.filter(id=user_company.id)
        return Company.objects.none()

    accessible_company_ids = set()
    has_all_companies_access = False

    for access_config in access_configs:
        config_companies = access_config.companies.all()
        if not config_companies.exists():
            has_all_companies_access = True
            break
        accessible_company_ids.update(config_companies.values_list('id', flat=True))

    if has_all_companies_access:
        return Company.objects.all()

    if accessible_company_ids:
        return Company.objects.filter(id__in=accessible_company_ids)

    user_company = get_user_company(user)
    if user_company:
        return Company.objects.filter(id=user_company.id)

    return Company.objects.none()


def models_q_has_any_cif_access():
    from django.db.models import Q
    return (
        Q(has_access=True)
        | Q(can_view_objects=True)
        | Q(can_edit_objects=True)
        | Q(can_add_objects=True)
        | Q(can_delete_objects=True)
        | Q(can_view_passports=True)
        | Q(can_edit_passports=True)
        | Q(can_approve_passports=True)
        | Q(can_view_plans=True)
        | Q(can_edit_plans=True)
        | Q(can_export=True)
    )


def user_has_cif_module_access(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return AccessCIF.objects.filter(
        group__in=user.groups.all(),
    ).filter(models_q_has_any_cif_access()).exists()


def check_user_cif_permission(user, permission_name):
    if user.is_superuser or user.is_staff:
        return True

    access_configs = AccessCIF.objects.filter(
        group__in=user.groups.all(),
    ).filter(models_q_has_any_cif_access())

    for access_config in access_configs:
        if getattr(access_config, permission_name, False):
            return True

    return False


def get_user_cif_permissions(user):
    if user.is_superuser or user.is_staff:
        return {
            'has_access': True,
            'can_view_objects': True,
            'can_edit_objects': True,
            'can_add_objects': True,
            'can_delete_objects': True,
            'can_view_passports': True,
            'can_edit_passports': True,
            'can_approve_passports': True,
            'can_view_plans': True,
            'can_edit_plans': True,
            'can_export': True,
        }

    permissions = {
        'has_access': False,
        'can_view_objects': False,
        'can_edit_objects': False,
        'can_add_objects': False,
        'can_delete_objects': False,
        'can_view_passports': False,
        'can_edit_passports': False,
        'can_approve_passports': False,
        'can_view_plans': False,
        'can_edit_plans': False,
        'can_export': False,
    }

    access_configs = AccessCIF.objects.filter(
        group__in=user.groups.all(),
    ).filter(models_q_has_any_cif_access())

    for access_config in access_configs:
        for key in permissions:
            if getattr(access_config, key, False):
                permissions[key] = True

    return permissions


def user_can_access_cif_company(user, company):
    if user.is_superuser or user.is_staff:
        return True
    if company is None:
        return False
    return get_user_accessible_companies(user).filter(pk=company.pk).exists()


def filter_cif_objects_for_user(user, queryset):
    if user.is_superuser or user.is_staff:
        return queryset
    company_ids = get_user_accessible_companies(user).values_list('id', flat=True)
    return queryset.filter(company_id__in=company_ids)


def cif_access_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not user_has_cif_module_access(request.user):
            messages.error(request, _('You do not have access to CIF module'))
            return redirect('index')
        return view_func(request, *args, **kwargs)
    return wrapper


def cif_permission_required(permission_name):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if not user_has_cif_module_access(request.user):
                messages.error(request, _('You do not have access to CIF module'))
                return redirect('index')
            if not check_user_cif_permission(request.user, permission_name):
                messages.error(request, _('You do not have permission for this action'))
                return redirect('index')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
