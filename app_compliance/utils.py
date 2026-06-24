"""
Utility functions and decorators for compliance module
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _, get_language
from functools import wraps
from app_conf.models import Company, Country
from datetime import datetime, date
from openpyxl.utils.datetime import from_excel
import json

from .models import (
    AccessCompliance, AccessLocalCompliance, AccessInternalCompliance,
    AccessControlMapping, ComplianceAuditLog
)


LANGUAGE_COUNTRY_MAP = {
    'uk': ['UA'],
    'ru': ['RU'],
    'pl': ['PL'],
    'de': ['DE'],
    'fr': ['FR'],
    'es': ['ES'],
    'it': ['IT'],
    'pt': ['PT'],
    'nl': ['NL'],
    'cs': ['CZ'],
    'sk': ['SK'],
    'ro': ['RO'],
    'bg': ['BG'],
    'hr': ['HR'],
    'sr': ['RS'],
    'tr': ['TR'],
    'ar': ['AE', 'SA'],
    'zh': ['CN'],
    'ja': ['JP'],
    'kk': ['KZ'],
    'be': ['BY'],
    'fi': ['FI'],
    'sv': ['SE'],
    'da': ['DK'],
    'no': ['NO'],
    'et': ['EE'],
    'lv': ['LV'],
    'lt': ['LT'],
}


def get_language_preferences(request):
    language_code = (getattr(request, 'LANGUAGE_CODE', None) or get_language() or '').lower()
    language_code = language_code[:2] if language_code else ''
    use_localized_labels = bool(language_code) and language_code != 'en'

    possible_country_codes = LANGUAGE_COUNTRY_MAP.get(language_code, [])
    country_for_language = None
    for country_code in possible_country_codes:
        try:
            country_for_language = Country.objects.get(code__iexact=country_code)
            break
        except Country.DoesNotExist:
            continue

    return language_code, country_for_language, use_localized_labels


def parse_local_requirement_date(value):
    """
    Parse Local Requirements dates, supporting DD.MM.YYYY and ISO formats.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            return from_excel(value).date()
        except Exception:
            pass
    value_str = str(value).strip()
    if not value_str:
        return None
    normalized = value_str.replace('/', '.').strip()
    try:
        numeric_value = float(normalized)
        if numeric_value.is_integer():
            return from_excel(int(numeric_value)).date()
        return from_excel(numeric_value).date()
    except (ValueError, TypeError):
        pass
    candidates = [normalized]
    if ' ' in normalized:
        candidates.append(normalized.split(' ')[0])
    if 'T' in normalized:
        candidates.append(normalized.split('T')[0])
    candidates = [c.strip() for c in candidates if c.strip()]
    formats = (
        '%d.%m.%Y',
        '%Y-%m-%d',
        '%d.%m.%Y %H:%M',
        '%d.%m.%Y %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%d-%m-%Y',
    )
    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    raise ValueError(_('Invalid date format. Use DD.MM.YYYY'))


def build_localized_options(model_qs, translation_qs, related_field, language_code, use_localized_labels):
    translation_map = {}
    if translation_qs is not None:
        translation_map = {
            getattr(translation, related_field).code: translation.name_local
            for translation in translation_qs
            if translation.name_local
        }

    options = []
    seen_codes = set()
    for obj in model_qs:
        label = obj.name
        if use_localized_labels:
            localized_label = translation_map.get(obj.code)
            if localized_label:
                label = localized_label
            elif language_code == 'uk' and getattr(obj, 'name_local', None):
                label = obj.name_local
        options.append({'code': obj.code, 'label': label})
        seen_codes.add(obj.code)
    return options, seen_codes


def get_dictionary_options(
    model_cls,
    translation_cls,
    related_field,
    language_code,
    country_for_language,
    use_localized_labels,
    codes=None,
    fallback_map=None
):
    filters = {'is_active': True}
    if codes is not None:
        filters['code__in'] = list(codes)

    model_qs = model_cls.objects.filter(**filters).order_by('display_order', 'name')
    model_codes = list(model_qs.values_list('code', flat=True))

    translation_qs = None
    if (
        country_for_language
        and use_localized_labels
        and model_codes
        and translation_cls is not None
    ):
        translation_filters = {
            'country': country_for_language,
            f'{related_field}__code__in': model_codes,
        }
        translation_qs = translation_cls.objects.filter(**translation_filters).select_related(related_field)

    options, seen_codes = build_localized_options(
        model_qs,
        translation_qs,
        related_field,
        language_code,
        use_localized_labels
    )

    if codes is not None:
        for code in codes:
            if code not in seen_codes:
                fallback_label = None
                if fallback_map:
                    fallback_label = fallback_map.get(code)
                options.append({'code': code, 'label': fallback_label or code})

    return options


def compliance_access_required(view_func):
    """
    Decorator to check if user has access to compliance module
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Superusers and staff always have access
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Check AccessCompliance
        has_access = AccessCompliance.objects.filter(
            group__in=request.user.groups.all(),
            has_access=True
        ).exists()
        
        if has_access:
            return view_func(request, *args, **kwargs)
        
        messages.error(request, _('You do not have access to Compliance module'))
        return redirect('index')
    
    return wrapper


def get_user_company(user):
    """
    Helper function to get user's company from different possible sources
    """
    # Try cabinet (CabinetUser model)
    if hasattr(user, 'cabinet') and hasattr(user.cabinet, 'company'):
        return user.cabinet.company
    
    # Try profile
    if hasattr(user, 'profile') and hasattr(user.profile, 'company'):
        return user.profile.company
    
    # Fallback to first company
    company = Company.objects.first()
    return company


def get_user_accessible_companies(user):
    """
    Get companies accessible by user based on AccessCompliance settings
    
    Returns:
        QuerySet of Company objects the user can access
    """
    # Superusers and staff can access all companies
    if user.is_superuser or user.is_staff:
        return Company.objects.all()
    
    # Get user's groups
    user_groups = user.groups.all()
    
    # Get AccessCompliance for user's groups
    access_configs = AccessCompliance.objects.filter(
        group__in=user_groups,
        has_access=True
    ).prefetch_related('companies')
    
    if not access_configs.exists():
        # No access configuration, fallback to user's own company
        user_company = get_user_company(user)
        if user_company:
            return Company.objects.filter(id=user_company.id)
        return Company.objects.none()
    
    # Collect all accessible companies
    accessible_company_ids = set()
    has_all_companies_access = False
    
    for access_config in access_configs:
        config_companies = access_config.companies.all()
        if not config_companies.exists():
            # Empty companies means access to ALL companies
            has_all_companies_access = True
            break
        else:
            accessible_company_ids.update(config_companies.values_list('id', flat=True))
    
    if has_all_companies_access:
        return Company.objects.all()
    
    if accessible_company_ids:
        return Company.objects.filter(id__in=accessible_company_ids)
    
    # No companies specified, fallback to user's own company
    user_company = get_user_company(user)
    if user_company:
        return Company.objects.filter(id=user_company.id)
    
    return Company.objects.none()


def check_user_compliance_permission(user, permission_name):
    """
    Check if user has specific compliance permission
    
    Args:
        user: User object
        permission_name: str - permission field name (e.g., 'can_edit_frameworks')
    
    Returns:
        bool - True if user has permission
    """
    if user.is_superuser or user.is_staff:
        return True
    
    user_groups = user.groups.all()
    access_configs = AccessCompliance.objects.filter(
        group__in=user_groups,
        has_access=True
    )
    
    for access_config in access_configs:
        if getattr(access_config, permission_name, False):
            return True
    
    return False


def get_user_compliance_permissions(user):
    """
    Get all compliance permissions for user as a dictionary
    
    Args:
        user: User object
    
    Returns:
        dict - Dictionary of permissions
    """
    if user.is_superuser or user.is_staff:
        return {
            'can_view_frameworks': True,
            'can_edit_frameworks': True,
            'can_add_frameworks': True,
            'can_delete_frameworks': True,
            'can_view_controls': True,
            'can_edit_controls': True,
            'can_add_controls': True,
            'can_delete_controls': True,
            'can_view_instance_controls': True,
            'can_edit_instance_controls': True,
            'can_manage_evidence': True,
            'can_approve_evidence': True,
            'can_view_reports': True,
            'can_export': True,
        }
    
    permissions = {
        'can_view_frameworks': False,
        'can_edit_frameworks': False,
        'can_add_frameworks': False,
        'can_delete_frameworks': False,
        'can_view_controls': False,
        'can_edit_controls': False,
        'can_add_controls': False,
        'can_delete_controls': False,
        'can_view_instance_controls': False,
        'can_edit_instance_controls': False,
        'can_manage_evidence': False,
        'can_approve_evidence': False,
        'can_view_reports': False,
        'can_export': False,
    }
    
    user_groups = user.groups.all()
    access_configs = AccessCompliance.objects.filter(
        group__in=user_groups,
        has_access=True
    )
    
    for access_config in access_configs:
        for key in permissions.keys():
            if getattr(access_config, key, False):
                permissions[key] = True
    
    return permissions


def local_compliance_access_required(view_func):
    """
    Decorator to check if user has access to Local Compliance module
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Superusers and staff always have access
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Check AccessLocalCompliance
        has_access = AccessLocalCompliance.objects.filter(
            group__in=request.user.groups.all(),
            has_access=True
        ).exists()
        
        if has_access:
            return view_func(request, *args, **kwargs)
        
        messages.error(request, _('You do not have access to Local Compliance module'))
        return redirect('index')
    
    return wrapper


def get_user_accessible_companies_local(user):
    """
    Get companies accessible by user based on AccessLocalCompliance settings
    
    Returns:
        QuerySet of Company objects the user can access for Local Compliance
    """
    # Superusers and staff can access all companies
    if user.is_superuser or user.is_staff:
        return Company.objects.all()
    
    # Get user's groups
    user_groups = user.groups.all()
    
    # Get AccessLocalCompliance for user's groups
    access_configs = AccessLocalCompliance.objects.filter(
        group__in=user_groups,
        has_access=True
    ).prefetch_related('companies')
    
    if not access_configs.exists():
        # No access configuration, fallback to user's own company
        user_company = get_user_company(user)
        if user_company:
            return Company.objects.filter(id=user_company.id)
        return Company.objects.none()
    
    # Collect all accessible companies
    accessible_company_ids = set()
    has_all_companies_access = False
    
    for access_config in access_configs:
        config_companies = access_config.companies.all()
        if not config_companies.exists():
            # Empty companies means access to ALL companies
            has_all_companies_access = True
            break
        else:
            accessible_company_ids.update(config_companies.values_list('id', flat=True))
    
    if has_all_companies_access:
        return Company.objects.all()
    
    if accessible_company_ids:
        return Company.objects.filter(id__in=accessible_company_ids)
    
    # No companies specified, fallback to user's own company
    user_company = get_user_company(user)
    if user_company:
        return Company.objects.filter(id=user_company.id)
    
    return Company.objects.none()


def check_user_local_compliance_permission(user, permission_name):
    """
    Check if user has specific local compliance permission
    
    Args:
        user: User object
        permission_name: str - permission field name (e.g., 'can_edit_regulators')
    
    Returns:
        bool - True if user has permission
    """
    if user.is_superuser or user.is_staff:
        return True
    
    user_groups = user.groups.all()
    access_configs = AccessLocalCompliance.objects.filter(
        group__in=user_groups,
        has_access=True
    )
    
    for access_config in access_configs:
        if getattr(access_config, permission_name, False):
            return True
    
    return False


def get_user_local_compliance_permissions(user):
    """
    Get all local compliance permissions for user as a dictionary
    
    Args:
        user: User object
    
    Returns:
        dict - Dictionary of permissions
    """
    if user.is_superuser or user.is_staff:
        return {
            'can_view_regulators': True,
            'can_edit_regulators': True,
            'can_add_regulators': True,
            'can_delete_regulators': True,
            'can_view_requirements': True,
            'can_edit_requirements': True,
            'can_add_requirements': True,
            'can_delete_requirements': True,
            'can_view_requirement_instances': True,
            'can_edit_requirement_instances': True,
            'can_view_controls': True,
            'can_edit_controls': True,
            'can_add_controls': True,
            'can_delete_controls': True,
            'can_manage_evidence': True,
            'can_approve_evidence': True,
            'can_view_reports': True,
            'can_export': True,
        }
    
    permissions = {
        'can_view_regulators': False,
        'can_edit_regulators': False,
        'can_add_regulators': False,
        'can_delete_regulators': False,
        'can_view_requirements': False,
        'can_edit_requirements': False,
        'can_add_requirements': False,
        'can_delete_requirements': False,
        'can_view_requirement_instances': False,
        'can_edit_requirement_instances': False,
        'can_view_controls': False,
        'can_edit_controls': False,
        'can_add_controls': False,
        'can_delete_controls': False,
        'can_manage_evidence': False,
        'can_approve_evidence': False,
        'can_view_reports': False,
        'can_export': False,
    }
    
    user_groups = user.groups.all()
    access_configs = AccessLocalCompliance.objects.filter(
        group__in=user_groups,
        has_access=True
    )
    
    for access_config in access_configs:
        for key in permissions.keys():
            if getattr(access_config, key, False):
                permissions[key] = True
    
    return permissions


def log_compliance_action(user, action, object_type, obj, changes=None, request=None, notes=None):
    """Utility function to log compliance actions"""
    log_data = {
        'user': user,
        'action': action,
        'object_type': object_type,
        'object_id': obj.id,
        'object_repr': str(obj),
    }
    
    if changes:
        log_data['changes'] = json.dumps(changes, ensure_ascii=False)
    
    if notes:
        log_data['notes'] = notes
    
    if request:
        log_data['ip_address'] = request.META.get('REMOTE_ADDR')
        log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
    
    ComplianceAuditLog.objects.create(**log_data)


def internal_compliance_access_required(view_func):
    """
    Decorator to check if user has access to Internal Compliance module
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Superusers and staff always have access
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Check AccessInternalCompliance
        has_access = AccessInternalCompliance.objects.filter(
            group__in=request.user.groups.all(),
            has_access=True
        ).exists()
        
        if has_access:
            return view_func(request, *args, **kwargs)
        
        messages.error(request, _('You do not have access to Internal Compliance module'))
        return redirect('index')
    
    return wrapper


def get_user_accessible_companies_internal(user):
    """
    Get companies accessible by user based on AccessInternalCompliance settings
    
    Returns:
        QuerySet of Company objects the user can access for Internal Compliance
    """
    # Superusers and staff can access all companies
    if user.is_superuser or user.is_staff:
        return Company.objects.all()
    
    # Get user's groups
    user_groups = user.groups.all()
    
    # Get AccessInternalCompliance for user's groups
    access_configs = AccessInternalCompliance.objects.filter(
        group__in=user_groups,
        has_access=True
    ).prefetch_related('companies')
    
    if not access_configs.exists():
        # No access configuration, fallback to user's own company
        user_company = get_user_company(user)
        if user_company:
            return Company.objects.filter(id=user_company.id)
        return Company.objects.none()
    
    # Collect all accessible companies
    accessible_company_ids = set()
    has_all_companies_access = False
    
    for access_config in access_configs:
        config_companies = access_config.companies.all()
        if not config_companies.exists():
            # Empty companies means access to ALL companies
            has_all_companies_access = True
            break
        else:
            accessible_company_ids.update(config_companies.values_list('id', flat=True))
    
    if has_all_companies_access:
        return Company.objects.all()
    
    if accessible_company_ids:
        return Company.objects.filter(id__in=accessible_company_ids)
    
    # No companies specified, fallback to user's own company
    user_company = get_user_company(user)
    if user_company:
        return Company.objects.filter(id=user_company.id)
    
    return Company.objects.none()


def get_user_accessible_companies_for_control_mapping(user):
    """
    Get companies accessible by user based on AccessControlMapping settings ONLY
    
    Returns:
        QuerySet of Company objects the user can access for Control Mapping
    """
    # Superusers and staff can access all companies
    if user.is_superuser or user.is_staff:
        return Company.objects.all()
    
    # Get user's groups
    user_groups = user.groups.all()
    
    # Get AccessControlMapping for user's groups
    access_configs = AccessControlMapping.objects.filter(
        group__in=user_groups,
        has_access=True
    ).prefetch_related('companies')
    
    if not access_configs.exists():
        # No AccessControlMapping configured - no access
        return Company.objects.none()
    
    # Collect all accessible companies
    # Тільки компанії, які явно вибрані в AccessControlMapping
    accessible_company_ids = set()
    
    for access_config in access_configs:
        config_companies = access_config.companies.all()
        # Пропускаємо конфігурації без вибраних компаній
        # Доступ тільки до явно вибраних компаній
        if config_companies.exists():
            accessible_company_ids.update(config_companies.values_list('id', flat=True))
    
    if accessible_company_ids:
        return Company.objects.filter(id__in=accessible_company_ids)
    
    # Немає вибраних компаній - немає доступу
    return Company.objects.none()


def check_user_control_mapping_access(user):
    """
    Check if user has access to Control Mapping based on AccessControlMapping ONLY
    
    Returns:
        bool: True if user has access, False otherwise
    """
    # Superusers and staff always have access
    if user.is_superuser or user.is_staff:
        return True
    
    # Get user's groups
    user_groups = user.groups.all()
    
    # Check if any of user's groups have access through AccessControlMapping
    # AccessControlMapping є ЄДИНИМ джерелом доступу до Control Mapping
    has_access = AccessControlMapping.objects.filter(
        group__in=user_groups,
        has_access=True
    ).exists()
    
    return has_access


def control_mapping_access_required(view_func):
    """
    Decorator to check if user has access to Control Mapping
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not check_user_control_mapping_access(request.user):
            from django.contrib import messages
            messages.error(request, _('You do not have permission to access Control Mapping.'))
            return redirect('compliance:dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def check_user_internal_compliance_permission(user, permission_name):
    """
    Check if user has specific internal compliance permission
    
    Args:
        user: User object
        permission_name: str - permission field name (e.g., 'can_edit_sources')
    
    Returns:
        bool - True if user has permission
    """
    if user.is_superuser or user.is_staff:
        return True
    
    user_groups = user.groups.all()
    access_configs = AccessInternalCompliance.objects.filter(
        group__in=user_groups,
        has_access=True
    )
    
    for access_config in access_configs:
        if getattr(access_config, permission_name, False):
            return True
    
    return False


def get_user_internal_compliance_permissions(user):
    """
    Get all internal compliance permissions for user as a dictionary
    
    Args:
        user: User object
    
    Returns:
        dict - Dictionary of permissions
    """
    if user.is_superuser or user.is_staff:
        return {
            'can_view_sources': True,
            'can_edit_sources': True,
            'can_add_sources': True,
            'can_delete_sources': True,
            'can_view_requirements': True,
            'can_edit_requirements': True,
            'can_add_requirements': True,
            'can_delete_requirements': True,
            'can_view_requirement_instances': True,
            'can_edit_requirement_instances': True,
            'can_view_controls': True,
            'can_edit_controls': True,
            'can_add_controls': True,
            'can_delete_controls': True,
            'can_manage_evidence': True,
            'can_approve_evidence': True,
            'can_view_reports': True,
            'can_export': True,
        }
    
    permissions = {
        'can_view_sources': False,
        'can_edit_sources': False,
        'can_add_sources': False,
        'can_delete_sources': False,
        'can_view_requirements': False,
        'can_edit_requirements': False,
        'can_add_requirements': False,
        'can_delete_requirements': False,
        'can_view_requirement_instances': False,
        'can_edit_requirement_instances': False,
        'can_view_controls': False,
        'can_edit_controls': False,
        'can_add_controls': False,
        'can_delete_controls': False,
        'can_manage_evidence': False,
        'can_approve_evidence': False,
        'can_view_reports': False,
        'can_export': False,
    }
    
    user_groups = user.groups.all()
    access_configs = AccessInternalCompliance.objects.filter(
        group__in=user_groups,
        has_access=True
    )
    
    for access_config in access_configs:
        for key in permissions.keys():
            if getattr(access_config, key, False):
                permissions[key] = True
    
    return permissions


# Helper functions for Excel import (shared by local and internal compliance)
def excel_get_required(field, requirement_data):
    """Helper for Excel import - get required field"""
    value = str(requirement_data.get(field, '') or '').strip()
    if not value:
        from django.utils.translation import gettext_lazy as _
        raise ValueError(_('Field "%(field)s" is required') % {'field': field})
    return value


def excel_normalize_choice(value, choices, label):
    """Helper for Excel import - normalize choice value"""
    from django.utils.translation import gettext_lazy as _
    if not value:
        raise ValueError(_('Field "%(field)s" is required') % {'field': label})
    value_str = str(value).strip().lower()
    for code, display in choices:
        if value_str == code.lower() or value_str == str(display).lower():
            return code
    raise ValueError(_('Invalid %(field)s value: %(value)s') % {'field': label, 'value': value})


def excel_is_empty_value(value):
    """Helper for Excel import - check if value is effectively empty"""
    if not value:
        return True
    value_str = str(value).strip()
    if not value_str:
        return True
    value_lower = value_str.lower()
    if value_lower in ('none', 'null', '', 'n/a', '-', '—'):
        return True
    return False


def excel_parse_date(value):
    """Helper for Excel import - safely parse date value"""
    if excel_is_empty_value(value):
        return None
    try:
        return parse_local_requirement_date(value)
    except (ValueError, TypeError):
        return None


def excel_parse_required_count(value):
    """Helper for Excel import - parse required count"""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 1


def excel_parse_periodicity(value):
    """Helper for Excel import - parse periodicity"""
    try:
        periodicity_val = int(value)
        return periodicity_val if periodicity_val > 0 else None
    except (TypeError, ValueError):
        return None

