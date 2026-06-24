from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_POST
from .models import (AccessFunctionIS, AccessRight, AccessRoles, AccessObjectIS, 
                     ObjectRoles, ObjectAccessRights, AccessObjectFunction, ObjectRoleFunctions,
                     ObjectFunctionRightMapping, ObjectRoleFunctionRightMapping, RoleFunctionRightMapping,
                     AccessISAM, AccessMatrixGuide, AccessMatrixGuideTranslation)
import logging
import json
from django.utils.translation import gettext as _, get_language
from django.db.models import Q
from app_asset.models import InformationAsset
from app_conf.models import Company, Country
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


def has_any_isam_access(user):
    """Check if user has any ISAM access through AccessISAM model"""
    if not user.is_authenticated:
        return False
    
    return AccessISAM.objects.filter(
        group__in=user.groups.all()
    ).filter(
        Q(has_access_matrix=True) |
        Q(has_access_records=True) |
        Q(has_access_config_is=True) |
        Q(has_access_manage_ar=True) |
        Q(has_access_notification_settings=True) |
        Q(has_access_api=True)
    ).exists()


def has_access_matrix_permission_new(user):
    """Check if user has access to Access Matrix specifically"""
    if not user.is_authenticated:
        return False
    
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_matrix=True
    ).exists()


def has_access_matrix_permission(user):
    """Check if user has access to access matrix page"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_matrix=True
    ).exists()





def can_edit_access_matrix(user):
    """Check if user can edit access matrix"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_edit_matrix=True
    ).exists()


def get_user_companies_for_matrix(user):
    """Get companies that user can access through AccessISAM"""
    access_isam_records = AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_matrix=True
    ).prefetch_related('companies')
    
    # Collect all company IDs from AccessISAM records
    company_ids = set()
    for access_record in access_isam_records:
        company_ids.update(access_record.companies.values_list('id', flat=True))
    
    # Return companies filtered by collected IDs
    return Company.objects.filter(id__in=company_ids).order_by('name')


def has_access_records_permission(user):
    """Check if user has access to access records page"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_records=True
    ).exists()


def can_add_access_records(user):
    """Check if user can add access records"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_add_access_records=True
    ).exists()


def can_edit_access_records(user):
    """Check if user can edit access records"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_edit_access_records=True
    ).exists()


def can_delete_access_records(user):
    """Check if user can delete access records"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_delete_access_records=True
    ).exists()


def get_user_companies_for_records(user):
    """Get companies that user can access for records through AccessISAM"""
    access_isam_records = AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_records=True
    ).prefetch_related('companies')
    
    # Collect all company IDs from AccessISAM records
    company_ids = set()
    for access_record in access_isam_records:
        company_ids.update(access_record.companies.values_list('id', flat=True))
    
    # Return companies filtered by collected IDs
    return Company.objects.filter(id__in=company_ids).order_by('name')


def has_access_config_is_permission(user):
    """Check if user has permission to access Config IS"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_config_is=True
    ).exists()


def can_add_access_config_is(user):
    """Check if user can add Config IS records"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_add_access_config_is=True
    ).exists()


def can_edit_access_config_is(user):
    """Check if user can edit Config IS records"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_edit_access_config_is=True
    ).exists()


def can_delete_access_config_is(user):
    """Check if user can delete Config IS records"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_delete_access_config_is=True
    ).exists()


def get_user_companies_for_config_is(user):
    """Get companies that user can access for Config IS through AccessISAM"""
    access_isam_config = AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_config_is=True
    ).prefetch_related('companies')
    
    # Collect all company IDs from AccessISAM config
    company_ids = set()
    for access_record in access_isam_config:
        company_ids.update(access_record.companies.values_list('id', flat=True))
    
    # Return companies filtered by collected IDs
    return Company.objects.filter(id__in=company_ids).order_by('name')


def has_access_manage_ar_permission(user):
    """Check if user has permission to access Manage Access Requests"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_manage_ar=True
    ).exists()


def can_add_manage_ar(user):
    """Check if user can add Manage Access Requests records"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_add_manage_ar=True
    ).exists()


def can_edit_manage_ar(user):
    """Check if user can edit Manage Access Requests records"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_edit_manage_ar=True
    ).exists()


def can_delete_manage_ar(user):
    """Check if user can delete Manage Access Requests records"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        can_delete_manage_ar=True
    ).exists()


def get_user_companies_for_manage_ar(user):
    """Get companies that user can access for Manage AR through AccessISAM"""
    access_isam_manage_ar = AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_manage_ar=True
    ).prefetch_related('companies')
    
    # Collect all company IDs from AccessISAM manage AR
    company_ids = set()
    for access_record in access_isam_manage_ar:
        company_ids.update(access_record.companies.values_list('id', flat=True))
    
    # Return companies filtered by collected IDs
    return Company.objects.filter(id__in=company_ids).order_by('name')


def has_access_notification_settings_permission(user):
    """Check if user has access to Notification Settings"""
    if user.is_authenticated:
        return AccessISAM.objects.filter(
            group__in=user.groups.all(), 
            has_access_notification_settings=True
        ).exists()
    return False


def can_add_notification_settings(user):
    """Check if user can add Notification Settings"""
    if user.is_authenticated:
        return AccessISAM.objects.filter(
            group__in=user.groups.all(), 
            can_add_notification_settings=True
        ).exists()
    return False


def can_edit_notification_settings(user):
    """Check if user can edit Notification Settings"""
    if user.is_authenticated:
        return AccessISAM.objects.filter(
            group__in=user.groups.all(), 
            can_edit_notification_settings=True
        ).exists()
    return False


def can_delete_notification_settings(user):
    """Check if user can delete Notification Settings"""
    if user.is_authenticated:
        return AccessISAM.objects.filter(
            group__in=user.groups.all(), 
            can_delete_notification_settings=True
        ).exists()
    return False


def get_user_companies_for_notification_settings(user):
    """Get companies that user can access for Notification Settings through AccessISAM"""
    access_isam_notification = AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_notification_settings=True
    ).prefetch_related('companies')
    
    # Collect all company IDs from AccessISAM notification settings
    company_ids = set()
    for access_record in access_isam_notification:
        company_ids.update(access_record.companies.values_list('id', flat=True))
    
    # Return companies filtered by collected IDs
    return Company.objects.filter(id__in=company_ids).order_by('name')


@login_required
def access_matrix_is(request):
    """View для відображення сторінки матриці доступу"""
    try:
        # logger.debug("Starting access_matrix_is view")

        # Check access permissions
        if not has_access_matrix_permission(request.user):
            return JsonResponse({
                'error': 'Access denied',
                'message': _('Access denied to Access Matrix page')
            }, status=403)

        # Get user's companies
        user_companies = get_user_companies_for_matrix(request.user)
        
        # Get user's edit permissions for template
        can_edit = can_edit_access_matrix(request.user)
        
        # Filter assets by user's companies
        if user_companies.exists():
            user_assets = InformationAsset.objects.filter(
                company__in=user_companies,
                access_manage=True,  # Only include assets marked for access management
                deletion_date__isnull=True  # Only include active assets
            ).order_by('name')
        else:
            # If no companies specified, show no assets for security
            user_assets = InformationAsset.objects.none()
        
        context = {
            'title': _('Access Matrix Information Systems'),
            'active_tab': 'access_matrix_is',
            'companies': user_companies,
            'groups': AccessISAM.objects.filter(group__in=request.user.groups.all()),
            'assets': user_assets,
            'can_edit_matrix': can_edit,
        }

        # logger.debug(f"Rendering template with context keys: {list(context.keys())}")
        return render(request, 'app_access/access_matrix_is.html', context)

    except Exception as e:
        logger.error(f"Error in access_matrix_is view: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': str(e),
            'message': _('Error loading access matrix page')
        }, status=500)


@login_required
@require_http_methods(["GET"])
def access_matrix_guide(request):
    """Return JSON { content: html } for the Access Matrix guide (localized)."""
    if not has_access_matrix_permission(request.user):
        return JsonResponse({'content': ''})
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = AccessMatrixGuide.objects.first()
    if guide:
        if country:
            trans = AccessMatrixGuideTranslation.objects.filter(guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = AccessMatrixGuideTranslation.objects.filter(guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def access_matrix_guide_translate(request):
    """API for AI translation of Access Matrix guide content (admin)."""
    try:
        data = json.loads(request.body)
        text = (data.get('text') or '').strip()
        country_id = data.get('country_id')
        if not text:
            return JsonResponse({'error': 'Text is required'}, status=400)
        if not country_id:
            return JsonResponse({'error': 'Country ID is required'}, status=400)
        country = Country.objects.get(id=country_id)
    except Country.DoesNotExist:
        return JsonResponse({'error': 'Country not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    lang_map = {
        'ua': 'uk', 'gb': 'en', 'us': 'en', 'uk': 'en', 'ru': 'ru',
        'kz': 'kk', 'by': 'be', 'md': 'ro', 'ge': 'ka', 'am': 'hy', 'az': 'az',
        'ch': 'de', 'at': 'de', 'be': 'nl', 'dk': 'da', 'no': 'no', 'se': 'sv',
        'fi': 'fi', 'ee': 'et', 'lv': 'lv', 'lt': 'lt', 'cz': 'cs', 'sk': 'sk',
        'hu': 'hu', 'ro': 'ro', 'bg': 'bg', 'pl': 'pl', 'fr': 'fr', 'es': 'es',
        'it': 'it', 'cn': 'zh-cn', 'jp': 'ja', 'kr': 'ko', 'tr': 'tr',
    }
    target = lang_map.get(country.code.lower(), country.code.lower())
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target=target)
        translated = translator.translate(text)
        return JsonResponse({
            'success': True,
            'translated_text': translated,
            'target_language': target,
            'country_name': country.name,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def update_matrix_mapping(request):
    try:
        # Check if user can edit matrix
        if not can_edit_access_matrix(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit the access matrix. Please contact your administrator to grant you edit rights.')
            }, status=403)
            
        data = json.loads(request.body)
        system_id = data.get('system_id')
        role_id = data.get('role_id')  # для системної матриці — обов'язково
        function_id = data.get('function_id')
        right_id = data.get('right_id')
        is_active = data.get('is_active')
        object_id = data.get('object_id')  # для об'єкт-специфічних маппінгів

        if not all([system_id, function_id, right_id, is_active is not None]):
            return JsonResponse({
                'success': False,
                'message': _('Missing required parameters: system_id, function_id, right_id, or is_active')
            }, status=400)

        # Check if user has access to the system's company
        try:
            system = InformationAsset.objects.get(id=system_id)
            user_companies = get_user_companies_for_matrix(request.user)
            
            if user_companies.exists() and system.company not in user_companies:
                return JsonResponse({
                    'success': False,
                    'message': _('Access denied - you do not have permission to edit matrix for company "{}". Please contact your administrator.').format(system.company.name)
                }, status=403)
        except InformationAsset.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': _('Information system with ID {} not found').format(system_id)
            }, status=404)

        # Отримуємо функцію та право доступу
        function = get_object_or_404(AccessFunctionIS, id=function_id, asset_id=system_id)
        right = get_object_or_404(AccessRight, id=right_id, system_id=system_id)

        # Об'єкт-специфічна матриця: потрібен role_id, зберігаємо в ObjectRoleFunctionRightMapping
        if object_id:
            if not role_id:
                return JsonResponse({
                    'success': False,
                    'message': _('Missing required parameter: role_id for object matrix')
                }, status=400)
            access_object = get_object_or_404(AccessObjectIS, id=object_id, asset_id=system_id)
            role = get_object_or_404(AccessRoles, id=role_id, system_id=system_id)
            if not ObjectRoles.objects.filter(access_object=access_object, role=role, is_active=True).exists():
                return JsonResponse({
                    'success': False,
                    'message': _('Role is not assigned to this object')
                }, status=400)
            object_function_exists = ObjectRoleFunctions.objects.filter(
                object_role__access_object=access_object,
                object_role__role=role,
                function=function,
                is_active=True
            ).exists()
            if not object_function_exists:
                return JsonResponse({
                    'success': False,
                    'message': _('Function is not assigned to this role on this object')
                }, status=400)
            if not ObjectAccessRights.objects.filter(
                access_object=access_object,
                access_right=right,
                is_active=True
            ).exists():
                return JsonResponse({
                    'success': False,
                    'message': _('Access right is not assigned to this object')
                }, status=400)
            if is_active:
                mapping, created = ObjectRoleFunctionRightMapping.objects.get_or_create(
                    access_object=access_object,
                    role=role,
                    function=function,
                    access_right=right,
                    defaults={'is_active': True}
                )
                if not created and not mapping.is_active:
                    mapping.is_active = True
                    mapping.save()
                logger.info(f"Added object mapping: role {role_id} / function {function_id} -> right {right_id} for object {object_id}")
            else:
                ObjectRoleFunctionRightMapping.objects.filter(
                    access_object=access_object,
                    role=role,
                    function=function,
                    access_right=right
                ).update(is_active=False)
                logger.info(f"Removed object mapping: role {role_id} / function {function_id} -> right {right_id} for object {object_id}")

        else:
            # Системний маппінг: потрібен role_id, зберігаємо (роль, функція, право) окремо
            if not role_id:
                return JsonResponse({
                    'success': False,
                    'message': _('Missing required parameter: role_id for system matrix')
                }, status=400)
            role = get_object_or_404(AccessRoles, id=role_id, system_id=system_id)
            if is_active:
                obj, created = RoleFunctionRightMapping.objects.get_or_create(
                    role_id=role.id,
                    function_id=function.id,
                    access_right_id=right.id,
                    defaults={'is_active': True}
                )
                if not created and not obj.is_active:
                    obj.is_active = True
                    obj.save()
                logger.info(f"Added system mapping: role {role_id} / function {function_id} -> right {right_id}")
            else:
                RoleFunctionRightMapping.objects.filter(
                    role_id=role.id,
                    function_id=function.id,
                    access_right_id=right.id
                ).update(is_active=False)
                logger.info(f"Removed system mapping: role {role_id} / function {function_id} -> right {right_id}")

        return JsonResponse({
            'success': True,
            'message': _('Mapping updated successfully')
        })

    except (AccessFunctionIS.DoesNotExist, AccessRight.DoesNotExist, AccessObjectIS.DoesNotExist) as e:
        return JsonResponse({
            'success': False,
            'message': _('Function, right, or object not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error updating matrix mapping: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(['POST'])
def clear_matrix(request):
    """Clear all access rights mappings for the current system (and optional object) with confirmation on frontend."""
    try:
        if not can_edit_access_matrix(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit the access matrix.')
            }, status=403)
        data = json.loads(request.body)
        system_id = data.get('system_id')
        object_id = data.get('object_id')
        environment = data.get('environment')
        if not system_id:
            return JsonResponse({
                'success': False,
                'message': _('Missing required parameter: system_id')
            }, status=400)
        system = get_object_or_404(InformationAsset, id=system_id)
        user_companies = get_user_companies_for_matrix(request.user)
        if user_companies.exists() and system.company not in user_companies:
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit matrix for this company.')
            }, status=403)
        if object_id:
            access_object = get_object_or_404(AccessObjectIS, id=object_id, asset_id=system_id)
            u1 = ObjectRoleFunctionRightMapping.objects.filter(access_object=access_object).update(is_active=False)
            u2 = ObjectFunctionRightMapping.objects.filter(access_object=access_object).update(is_active=False)
            updated = u1 + u2
            logger.info(f"Cleared object matrix: object_id={object_id}, deactivated {updated} mappings")
        else:
            qs = RoleFunctionRightMapping.objects.filter(role__system_id=system_id)
            if environment:
                qs = qs.filter(role__environment=environment)
            updated = qs.update(is_active=False)
            logger.info(f"Cleared system matrix: system_id={system_id}, environment={environment}, deactivated {updated} mappings")
        return JsonResponse({
            'success': True,
            'message': _('Matrix cleared successfully'),
            'cleared_count': updated
        })
    except Exception as e:
        logger.error(f"Error clearing matrix: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(['POST'])
def apply_default_matrix(request):
    """Copy Default Access Rights Matrix (per role/function/right) to the current object matrix."""
    try:
        if not can_edit_access_matrix(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit the access matrix.')
            }, status=403)
        data = json.loads(request.body)
        system_id = data.get('system_id')
        object_id = data.get('object_id')
        environment = data.get('environment')
        if not system_id or not object_id:
            return JsonResponse({
                'success': False,
                'message': _('Missing required parameters: system_id and object_id')
            }, status=400)
        system = get_object_or_404(InformationAsset, id=system_id)
        user_companies = get_user_companies_for_matrix(request.user)
        if user_companies.exists() and system.company not in user_companies:
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit matrix for this company.')
            }, status=403)
        access_object = get_object_or_404(AccessObjectIS, id=object_id, asset_id=system_id)

        role_ids_qs = system.access_roles.filter(is_object_specific=False)
        if environment:
            role_ids_qs = role_ids_qs.filter(environment=environment)
        role_ids = list(role_ids_qs.values_list('id', flat=True))
        default_mappings = list(
            RoleFunctionRightMapping.objects.filter(
                role_id__in=role_ids,
                is_active=True
            ).values_list('role_id', 'function_id', 'access_right_id')
        )
        object_roles_by_role = {
            obj_role.role_id: obj_role
            for obj_role in ObjectRoles.objects.filter(
                access_object=access_object,
                is_active=True
            ).select_related('role')
        }
        object_has_right = set(
            ObjectAccessRights.objects.filter(
                access_object=access_object,
                is_active=True
            ).values_list('access_right_id', flat=True)
        )
        applied = 0
        for role_id, function_id, right_id in default_mappings:
            obj_role = object_roles_by_role.get(role_id)
            if not obj_role:
                continue
            if not ObjectRoleFunctions.objects.filter(
                object_role=obj_role,
                function_id=function_id,
                is_active=True
            ).exists():
                continue
            if right_id not in object_has_right:
                continue
            mapping, created = ObjectRoleFunctionRightMapping.objects.get_or_create(
                access_object=access_object,
                role_id=role_id,
                function_id=function_id,
                access_right_id=right_id,
                defaults={'is_active': True}
            )
            if not created and not mapping.is_active:
                mapping.is_active = True
                mapping.save()
            applied += 1
        logger.info(f"Applied default matrix to object {object_id}: {applied} mappings (orange cells only)")
        return JsonResponse({
            'success': True,
            'message': _('Default matrix applied successfully'),
            'applied_count': applied
        })
    except Exception as e:
        logger.error(f"Error applying default matrix: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


def get_matrix_data_for_export(request, system_id, object_id=None, environment=None):
    """
    Returns (matrix_data, mappings) on success.
    On failure returns (None, error_dict, status_code) for use by get_access_matrix or export view.
    """
    try:
        current_lang = (get_language() or 'en')[:2].lower()
        if current_lang == 'uk':
            current_lang = 'ua'

        if not has_access_matrix_permission(request.user):
            return (None, {
                'status': 'error',
                'message': _('Access denied - you do not have permission to view the access matrix. Please contact your administrator to grant you access rights.')
            }, 403)

        user_companies = get_user_companies_for_matrix(request.user)

        try:
            system = get_object_or_404(
                InformationAsset.objects.prefetch_related(
                    'access_rights',
                    'access_roles',
                    'access_roles__functions',
                    'access_roles__functions__children',
                    'access_roles__functions__children__children',
                    'access_roles__functions__access_rights'
                ),
                id=system_id
            )
        except Http404:
            return (None, {'status': 'error', 'message': _('Information system not found')}, 404)

        if user_companies.exists() and system.company not in user_companies:
            return (None, {
                'status': 'error',
                'message': _('Access denied - you do not have permission to view matrix for company "{}". Please contact your administrator.').format(system.company.name)
            }, 403)

        mappings = []

        if object_id:
            try:
                access_object = get_object_or_404(AccessObjectIS, id=object_id, asset=system)
                
                # Отримуємо об'єкт-специфічні права доступу
                object_access_rights = ObjectAccessRights.objects.filter(
                    access_object=access_object, 
                    is_active=True
                ).select_related('access_right').order_by('order')
                
                access_rights_data = []
                for oar in object_access_rights:
                    right = oar.access_right
                    access_rights_data.append({
                        'id': right.id,
                        'name': right.get_name(current_lang) or right.get_name('en'),
                        'description': right.get_description(current_lang) or right.get_description('en') or '',
                        'color': right.color,
                        'order': oar.order
                    })
                
                # Отримуємо об'єкт-специфічні ролі
                object_roles = ObjectRoles.objects.filter(
                    access_object=access_object, 
                    is_active=True
                ).select_related('role').order_by('order')
                
                roles_data = []
                for obj_role in object_roles:
                    role = obj_role.role
                    role_data = {
                        'id': role.id,
                        'name': role.get_name(current_lang) or role.get_name('en'),
                        'description': role.get_description(current_lang) or role.get_description('en') or '',
                        'color': role.color,
                        'columns': {
                            'functions': [],
                            'subfunctions': [],
                            'subsubfunctions': []
                        }
                    }
                    
                    # Отримуємо функції для цієї ролі в контексті об'єкта
                    object_role_functions = ObjectRoleFunctions.objects.filter(
                        object_role=obj_role,
                        is_active=True
                    ).select_related('function').order_by('function__order')
                    
                    # Якщо немає об'єкт-специфічних функцій, ініціалізуємо їх з глобальних зв'язків
                    if not object_role_functions.exists():
                        logger.debug(f"No ObjectRoleFunctions found for role {role.id} in object {access_object.id}, initializing from global functions")
                        
                        # Отримуємо глобальні функції для цієї ролі
                        global_functions = role.functions.all()
                        # Reduce noisy debug logs in production
                        if settings.DEBUG:
                            logger.debug(f"Found {global_functions.count()} global functions for role {role.id}")
                        
                        # Створюємо об'єкт-специфічні записи для кожної глобальної функції,
                        # але тільки якщо функція призначена об'єкту
                        object_functions = AccessObjectFunction.objects.filter(
                            access_object=access_object,
                            function__in=global_functions,
                            is_active=True
                        ).values_list('function', flat=True)
                        if settings.DEBUG:
                            logger.debug(f"Found {len(object_functions)} functions assigned to object {access_object.id}")
                        
                        # Створюємо записи ObjectRoleFunctions для функцій, які є і в глобальній ролі, і в об'єкті
                        created_count = 0
                        for function_id in object_functions:
                            obj_role_func, created = ObjectRoleFunctions.objects.get_or_create(
                                object_role=obj_role,
                                function_id=function_id,
                                defaults={'is_active': True}
                            )
                            if created:
                                created_count += 1
                        
                        if settings.DEBUG:
                            logger.debug(f"Created {created_count} ObjectRoleFunctions records for role {role.id} in object {access_object.id}")
                        
                        # Оновлюємо запит після створення записів
                        object_role_functions = ObjectRoleFunctions.objects.filter(
                            object_role=obj_role,
                            is_active=True
                        ).select_related('function').order_by('function__order')
                    
                    # Збираємо всі функції для ролі
                    role_functions = [orf.function for orf in object_role_functions]
                    if settings.DEBUG:
                        logger.debug(f"Final result: role {role.id} has {len(role_functions)} functions for object {access_object.id}")
                    
                    # Групуємо функції по рівнях
                    root_functions = [f for f in role_functions if f.parent is None]
                    root_functions.sort(key=lambda x: x.order)
                    
                    for func in root_functions:
                        func_data = {
                            'id': func.id,
                            'name': func.get_name(current_lang) or func.get_name('en'),
                            'description': func.get_description(current_lang) or func.get_description('en') or '',
                            'color': func.color,
                            'order': func.order
                        }
                        role_data['columns']['functions'].append(func_data)

                        # Маппінги об'єкта: спочатку per-role (ObjectRoleFunctionRightMapping), потім legacy (ObjectFunctionRightMapping)
                        for right_data in access_rights_data:
                            object_mapping_exists = (
                                ObjectRoleFunctionRightMapping.objects.filter(
                                    access_object=access_object,
                                    role=role,
                                    function=func,
                                    access_right_id=right_data['id'],
                                    is_active=True
                                ).exists()
                                or ObjectFunctionRightMapping.objects.filter(
                                    access_object=access_object,
                                    function=func,
                                    access_right_id=right_data['id'],
                                    is_active=True
                                ).exists()
                            )
                            if object_mapping_exists:
                                mappings.append({
                                    'role_id': role.id,
                                    'function_id': func.id,
                                    'right_id': right_data['id']
                                })

                        # Отримуємо підфункції першого рівня
                        subfunctions = [f for f in role_functions if f.parent == func]
                        subfunctions.sort(key=lambda x: x.order)
                        
                        for subfunc in subfunctions:
                            subfunc_data = {
                                'id': subfunc.id,
                                'name': subfunc.get_name() or subfunc.name or '',
                                'description': getattr(subfunc, f'description_{current_lang}', '') or subfunc.description_ua,
                                'color': subfunc.color,
                                'parent_id': func.id,
                                'order': subfunc.order
                            }
                            role_data['columns']['subfunctions'].append(subfunc_data)

                            for right_data in access_rights_data:
                                object_mapping_exists = (
                                    ObjectRoleFunctionRightMapping.objects.filter(
                                        access_object=access_object,
                                        role=role,
                                        function=subfunc,
                                        access_right_id=right_data['id'],
                                        is_active=True
                                    ).exists()
                                    or ObjectFunctionRightMapping.objects.filter(
                                        access_object=access_object,
                                        function=subfunc,
                                        access_right_id=right_data['id'],
                                        is_active=True
                                    ).exists()
                                )
                                if object_mapping_exists:
                                    mappings.append({
                                        'role_id': role.id,
                                        'function_id': subfunc.id,
                                        'right_id': right_data['id']
                                    })

                            # Отримуємо підфункції другого рівня
                            subsubfunctions = [f for f in role_functions if f.parent == subfunc]
                            subsubfunctions.sort(key=lambda x: x.order)
                            
                            for subsubfunc in subsubfunctions:
                                subsubfunc_data = {
                                    'id': subsubfunc.id,
                                    'name': subsubfunc.get_name() or subsubfunc.name or '',
                                    'description': getattr(subsubfunc, f'description_{current_lang}', '') or subsubfunc.description_ua,
                                    'color': subsubfunc.color,
                                    'parent_id': subfunc.id,
                                    'order': subsubfunc.order
                                }
                                role_data['columns']['subsubfunctions'].append(subsubfunc_data)

                                for right_data in access_rights_data:
                                    object_mapping_exists = (
                                        ObjectRoleFunctionRightMapping.objects.filter(
                                            access_object=access_object,
                                            role=role,
                                            function=subsubfunc,
                                            access_right_id=right_data['id'],
                                            is_active=True
                                        ).exists()
                                        or ObjectFunctionRightMapping.objects.filter(
                                            access_object=access_object,
                                            function=subsubfunc,
                                            access_right_id=right_data['id'],
                                            is_active=True
                                        ).exists()
                                    )
                                    if object_mapping_exists:
                                        mappings.append({
                                            'role_id': role.id,
                                            'function_id': subsubfunc.id,
                                            'right_id': right_data['id']
                                        })

                    roles_data.append(role_data)

                matrix_data = {
                    'access_rights': access_rights_data,
                    'roles': roles_data,
                    'is_object_matrix': True,
                    'object_name': access_object.get_name(current_lang) or access_object.get_name('en')
                }

                # Системні маппінги (Default Matrix) — по (роль, функція, право) для порівняння з об'єктною матрицею
                role_ids_qs = system.access_roles.filter(is_object_specific=False)
                if environment:
                    role_ids_qs = role_ids_qs.filter(environment=environment)
                role_ids = list(role_ids_qs.values_list('id', flat=True))
                system_mappings_qs = RoleFunctionRightMapping.objects.filter(
                    role_id__in=role_ids,
                    is_active=True
                ).values_list('role_id', 'function_id', 'access_right_id')
                matrix_data['system_mappings'] = [
                    {'role_id': rid, 'function_id': fid, 'right_id': rtid}
                    for rid, fid, rtid in system_mappings_qs
                ]

            except Exception as e:
                logger.error(f"Error getting object matrix: {str(e)}", exc_info=True)
                # Fallback до системної матриці при помилці
                matrix_data, mappings = get_system_matrix(system, current_lang)
        
        else:
            # Якщо об'єкт не обрано, показуємо системну матрицю
            matrix_data, mappings = get_system_matrix(system, current_lang, environment)

        return (matrix_data, mappings)

    except Exception as e:
        logger.error(f"Error getting matrix data: {str(e)}", exc_info=True)
        return (None, {'status': 'error', 'message': str(e)}, 500)


@login_required
def get_access_matrix(request, system_id):
    """API view: returns JSON with matrix data and mappings."""
    result = get_matrix_data_for_export(
        request, system_id,
        object_id=request.GET.get('object_id'),
        environment=request.GET.get('environment')
    )
    if result[0] is None:
        return JsonResponse(result[1], status=result[2])
    matrix_data, mappings = result
    return JsonResponse({
        'status': 'success',
        'data': matrix_data,
        'mappings': mappings
    })


def get_system_matrix(system, current_lang, environment=None):
    """Отримання системної матриці доступу"""
    mappings = []
    
    # Показуємо тільки системні права та ролі (не специфічні для об'єктів), з урахуванням середовища якщо задано
    rights_qs = system.access_rights.filter(is_object_specific=False)
    roles_qs = system.access_roles.filter(is_object_specific=False)
    if environment:
        rights_qs = rights_qs.filter(environment=environment)
        roles_qs = roles_qs.filter(environment=environment)
    access_rights = rights_qs.order_by('order')
    roles = roles_qs.order_by('order')

    matrix_data = {
        'access_rights': [{
            'id': right.id,
            'name': right.get_name(current_lang) or right.get_name('en'),
            'description': right.get_description(current_lang) or right.get_description('en') or '',
            'color': right.color,
            'order': right.order
        } for right in access_rights],
        'roles': [],
        'is_object_matrix': False
    }

    for role in roles:
        role_data = {
            'id': role.id,
            'name': role.get_name(current_lang) or role.get_name('en'),
            'description': role.get_description(current_lang) or role.get_description('en') or '',
            'color': role.color,
            'columns': {
                'functions': [],
                'subfunctions': [],
                'subsubfunctions': []
            }
        }

        # Показуємо тільки системні функції (не специфічні для об'єктів), з урахуванням середовища якщо задано
        functions = role.functions.filter(is_object_specific=False)
        if environment:
            functions = functions.filter(environment=environment)

        # Отримуємо кореневі функції
        root_functions = functions.filter(parent__isnull=True).order_by('order')
        for func in root_functions:
            func_data = {
                'id': func.id,
                'name': func.get_name(current_lang) or func.get_name('en'),
                'description': func.get_description(current_lang) or func.get_description('en') or '',
                'color': func.color,
                'order': func.order
            }
            role_data['columns']['functions'].append(func_data)

            # Маппінги по (роль, функція, право) з RoleFunctionRightMapping
            for m in RoleFunctionRightMapping.objects.filter(role=role, function=func, is_active=True).select_related('access_right'):
                mappings.append({
                    'role_id': role.id,
                    'function_id': func.id,
                    'right_id': m.access_right_id
                })

            # Отримуємо підфункції першого рівня
            subfunctions = functions.filter(parent=func).order_by('order')
            for subfunc in subfunctions:
                subfunc_data = {
                    'id': subfunc.id,
                    'name': subfunc.get_name(current_lang) or subfunc.get_name('en'),
                    'description': subfunc.get_description(current_lang) or subfunc.get_description('en') or '',
                    'color': subfunc.color,
                    'parent_id': func.id,
                    'order': subfunc.order
                }
                role_data['columns']['subfunctions'].append(subfunc_data)

                for m in RoleFunctionRightMapping.objects.filter(role=role, function=subfunc, is_active=True).select_related('access_right'):
                    mappings.append({
                        'role_id': role.id,
                        'function_id': subfunc.id,
                        'right_id': m.access_right_id
                    })

                # Отримуємо підфункції другого рівня
                subsubfunctions = functions.filter(parent=subfunc).order_by('order')
                for subsubfunc in subsubfunctions:
                    subsubfunc_data = {
                        'id': subsubfunc.id,
                        'name': subsubfunc.get_name(current_lang) or subsubfunc.get_name('en'),
                        'description': subsubfunc.get_description(current_lang) or subsubfunc.get_description('en') or '',
                        'color': subsubfunc.color,
                        'parent_id': subfunc.id,
                        'order': subsubfunc.order
                    }
                    role_data['columns']['subsubfunctions'].append(subsubfunc_data)

                    for m in RoleFunctionRightMapping.objects.filter(role=role, function=subsubfunc, is_active=True).select_related('access_right'):
                        mappings.append({
                            'role_id': role.id,
                            'function_id': subsubfunc.id,
                            'right_id': m.access_right_id
                        })

        matrix_data['roles'].append(role_data)
    
    return matrix_data, mappings

@login_required
def get_role_matrix_for_tooltip(request, role_id, system_id):
    try:
        # Check if user has access to access matrix
        if not has_access_matrix_permission(request.user):
            return JsonResponse({
                'status': 'error',
                'message': _('Access denied - you do not have permission to view role details. Please contact your administrator to grant you access rights.')
            }, status=403)

        current_language = (get_language() or 'en')[:2].lower()
        if current_language == 'uk':
            current_language = 'ua'
        role = AccessRoles.objects.select_related('system').get(id=role_id, system_id=system_id)
        
        # Check if user has access to the system's company
        user_companies = get_user_companies_for_matrix(request.user)
        if user_companies.exists() and role.system.company not in user_companies:
            return JsonResponse({
                'status': 'error',
                'message': _('Access denied - you do not have permission to view role details for company "{}". Please contact your administrator.').format(role.system.company.name)
            }, status=403)

        # Отримуємо функції з правами доступу для ролі
        functions_data = []
        for function in role.functions.select_related('asset').filter(asset_id=system_id):
            # Використовуємо правильні назви полів з моделі - accesfunct_name замість functionis_name
            function_name = function.get_name(current_language) or function.get_name('en')
            rights = []
            for right in function.access_rights.all():
                right_name = right.get_name(current_language) or right.get_name('en')
                rights.append({
                    'name': right_name,
                    'color': right.color
                })

            functions_data.append({
                'name': function_name,
                'access_rights': rights
            })

        data = {
            'status': 'success',
            'data': {
                'role': {
                    'id': role.id,
                    'name': role.get_name(current_language) or role.get_name('en')
                },
                'functions': functions_data
            }
        }

        return JsonResponse(data)
    except AccessRoles.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': _('Role not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting role matrix: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def get_system_objects(request, system_id):
    """Get objects for a specific system in hierarchical structure"""
    try:
        current_lang = (get_language() or 'en')[:2].lower()
        if current_lang == 'uk':
            current_lang = 'ua'

        # Check if user has access to access matrix
        if not has_access_matrix_permission(request.user):
            return JsonResponse({
                'status': 'error',
                'message': _('Access denied - you do not have permission to view objects. Please contact your administrator to grant you access rights.')
            }, status=403)

        system = get_object_or_404(InformationAsset, id=system_id)
        
        # Check if user has access to the system's company
        user_companies = get_user_companies_for_matrix(request.user)
        if user_companies.exists() and system.company not in user_companies:
            return JsonResponse({
                'status': 'error',
                'message': _('Access denied - you do not have permission to view objects for company "{}". Please contact your administrator.').format(system.company.name)
            }, status=403)
        
        # Враховуємо середовище якщо задано
        environment = request.GET.get('environment')

        base_qs = AccessObjectIS.objects.filter(
            asset=system,
            parent__isnull=True
        )
        if environment:
            base_qs = base_qs.filter(environment=environment)
        root_objects = base_qs.order_by('order')

        def get_children(parent):
            """Рекурсивно отримуємо дочірні об'єкти"""
            children_qs = AccessObjectIS.objects.filter(
                parent=parent,
                asset=system
            )
            if environment:
                children_qs = children_qs.filter(environment=environment)
            children = children_qs.order_by('order')
            
            return [{
                'id': child.id,
                'name': child.get_name(current_lang) or child.get_name('en'),
                'description': child.get_description(current_lang) or child.get_description('en') or '',
                'color': child.color,
                'order': child.order,
                'level': child.level,
                'parent_id': child.parent.id if child.parent else None,
                'children': get_children(child)
            } for child in children]

        objects_data = []
        for obj in root_objects:
            objects_data.append({
                'id': obj.id,
                'name': obj.get_name(current_lang) or obj.get_name('en'),
                'description': obj.get_description(current_lang) or obj.get_description('en') or '',
                'color': obj.color,
                'order': obj.order,
                'level': obj.level,
                'parent_id': obj.parent.id if obj.parent else None,
                'children': get_children(obj)
            })

        return JsonResponse({
            'status': 'success',
            'data': objects_data
        })

    except Exception as e:
        logger.error(f"Error getting system objects: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@require_POST
def copy_matrix_between_environments(request):
    """
    Copy Access Rights Matrix from source environment to target environment.
    Default matrix: RoleFunctionRightMapping (roles/functions/rights matched by name; functions by tree order).
    Object matrices: ObjectRoleFunctionRightMapping with objects matched by name.
    """
    try:
        if not can_edit_access_matrix(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit the access matrix.')
            }, status=403)
        data = json.loads(request.body)
        system_id = data.get('system_id')
        source_environment = data.get('source_environment')
        target_environment = data.get('target_environment')
        copy_object_matrices = data.get('copy_object_matrices', True)
        if not all([system_id, source_environment, target_environment]):
            return JsonResponse({
                'success': False,
                'message': _('Missing required parameters: system_id, source_environment, target_environment')
            }, status=400)
        valid_envs = ('production', 'test', 'development')
        if source_environment not in valid_envs or target_environment not in valid_envs:
            return JsonResponse({'success': False, 'message': _('Invalid environment')}, status=400)
        if source_environment == target_environment:
            return JsonResponse({
                'success': False,
                'message': _('Source and target environments must be different')
            }, status=400)
        system = get_object_or_404(InformationAsset, id=system_id)
        user_companies = get_user_companies_for_matrix(request.user)
        if user_companies.exists() and system.company not in user_companies:
            return JsonResponse({
                'success': False,
                'message': _('Access denied to this system.')
            }, status=403)

        # Build function id mapping: source -> target by (name, parent name)
        source_funcs = list(
            AccessFunctionIS.objects.filter(
                asset=system,
                environment=source_environment,
                is_object_specific=False
            ).select_related('parent')
        )
        target_funcs = list(
            AccessFunctionIS.objects.filter(
                asset=system,
                environment=target_environment,
                is_object_specific=False
            ).select_related('parent')
        )
        def _func_key(f, attr='name'):
            p = f.parent
            parent_name = (getattr(p, 'name', None) or getattr(p, 'name_local', None) or getattr(p, 'code', None) or '') if p else ''
            n = getattr(f, attr, None) or ''
            return (n, parent_name)
        target_by_key = {}
        for f in target_funcs:
            for attr in ('name', 'name_local', 'code'):
                k = _func_key(f, attr=attr)
                if k[0]:
                    target_by_key[k] = f
        func_id_map = {}
        for sf in source_funcs:
            for attr in ('name', 'name_local', 'code'):
                key = _func_key(sf, attr=attr)
                if key[0] and key in target_by_key:
                    func_id_map[sf.id] = target_by_key[key].id
                    break
        # Fallback: if no matches by (name, parent), map by name, name_local, or code
        if not func_id_map and source_funcs and target_funcs:
            target_by_name = {}
            for f in target_funcs:
                for key in (f.name, f.name_local, f.code):
                    if key:
                        target_by_name[key] = f
            for sf in source_funcs:
                n = sf.name or sf.name_local or sf.code or ''
                if n and n in target_by_name:
                    func_id_map[sf.id] = target_by_name[n].id

        # Role by name, name_local, code (target findable by any)
        def get_role_map_multi(env):
            d = {}
            for r in AccessRoles.objects.filter(
                system=system, environment=env, is_object_specific=False
            ):
                for key in (r.name, r.name_local, r.code):
                    if key:
                        d[key] = r
            return d
        target_roles_by_name = get_role_map_multi(target_environment)

        # Right by name, name_local, code
        def get_right_map_multi(env):
            d = {}
            for r in AccessRight.objects.filter(
                system=system, environment=env, is_object_specific=False
            ):
                for key in (r.name, r.name_local, r.code):
                    if key:
                        d[key] = r
            return d
        target_rights_by_name = get_right_map_multi(target_environment)

        copied_default = 0
        skip_no_role = 0
        skip_no_func = 0
        skip_no_right = 0
        source_role_ids = list(AccessRoles.objects.filter(
            system=system, environment=source_environment, is_object_specific=False
        ).values_list('id', flat=True))
        for m in RoleFunctionRightMapping.objects.filter(
            role_id__in=source_role_ids, is_active=True
        ).select_related('role', 'function', 'access_right'):
            target_role = (
                target_roles_by_name.get(m.role.name) or
                target_roles_by_name.get(m.role.name_local or '') or
                target_roles_by_name.get(m.role.code or '')
            )
            if not target_role:
                skip_no_role += 1
                continue
            target_func_id = func_id_map.get(m.function_id)
            if not target_func_id:
                skip_no_func += 1
                continue
            r_right_name = m.access_right.name or ''
            r_right_name_local = m.access_right.name_local or ''
            r_right_code = m.access_right.code or ''
            target_right = (
                target_rights_by_name.get(r_right_name) or
                target_rights_by_name.get(r_right_name_local) or
                target_rights_by_name.get(r_right_code)
            )
            if not target_right:
                skip_no_right += 1
                continue
            obj, created = RoleFunctionRightMapping.objects.get_or_create(
                role=target_role,
                function_id=target_func_id,
                access_right=target_right,
                defaults={'is_active': True}
            )
            if created:
                copied_default += 1
            elif not obj.is_active:
                obj.is_active = True
                obj.save(update_fields=['is_active'])
                copied_default += 1

        copied_objects = 0
        if copy_object_matrices:
            source_objects = AccessObjectIS.objects.filter(
                asset=system, environment=source_environment
            )
            target_objects_by_name = {}
            for o in AccessObjectIS.objects.filter(
                asset=system, environment=target_environment
            ):
                for key in (o.get_name(), o.name, o.name_local):
                    if key:
                        target_objects_by_name[key] = o
            for src_obj in source_objects:
                obj_name = src_obj.get_name() or src_obj.name or src_obj.name_local or ''
                tgt_obj = target_objects_by_name.get(obj_name)
                if not tgt_obj:
                    continue
                for m in ObjectRoleFunctionRightMapping.objects.filter(
                    access_object=src_obj, is_active=True
                ).select_related('role', 'function', 'access_right'):
                    target_role = (
                        target_roles_by_name.get(m.role.name) or
                        target_roles_by_name.get(m.role.name_local or '') or
                        target_roles_by_name.get(m.role.code or '')
                    )
                    if not target_role:
                        continue
                    target_func_id = func_id_map.get(m.function_id)
                    if not target_func_id:
                        continue
                    r_right_name = m.access_right.name or ''
                    r_right_name_local = m.access_right.name_local or ''
                    r_right_code = m.access_right.code or ''
                    target_right = (
                        target_rights_by_name.get(r_right_name) or
                        target_rights_by_name.get(r_right_name_local) or
                        target_rights_by_name.get(r_right_code)
                    )
                    if not target_right:
                        continue
                    obj, created = ObjectRoleFunctionRightMapping.objects.get_or_create(
                        access_object=tgt_obj,
                        role=target_role,
                        function_id=target_func_id,
                        access_right=target_right,
                        defaults={'is_active': True}
                    )
                    if created:
                        copied_objects += 1
                    elif not obj.is_active:
                        obj.is_active = True
                        obj.save(update_fields=['is_active'])
                        copied_objects += 1

        resp = {
            'success': True,
            'message': _('Access Rights Matrix copied successfully'),
            'copied_default': copied_default,
            'copied_object_matrices': copied_objects
        }
        if copied_default == 0 and copied_objects == 0:
            source_count = RoleFunctionRightMapping.objects.filter(
                role_id__in=source_role_ids, is_active=True
            ).count()
            target_roles_count = AccessRoles.objects.filter(
                system=system, environment=target_environment, is_object_specific=False
            ).count()
            target_funcs_count = AccessFunctionIS.objects.filter(
                asset=system, environment=target_environment, is_object_specific=False
            ).count()
            target_rights_count = AccessRight.objects.filter(
                system=system, environment=target_environment, is_object_specific=False
            ).count()
            resp['diagnostic'] = {
                'source_default_mappings': source_count,
                'target_roles': target_roles_count,
                'target_functions': target_funcs_count,
                'target_rights': target_rights_count,
                'function_mapped_count': len(func_id_map),
                'skipped_no_target_role': skip_no_role,
                'skipped_no_target_function': skip_no_func,
                'skipped_no_target_right': skip_no_right,
            }
            if skip_no_role == 0 and skip_no_func == 0 and skip_no_right == 0 and source_count > 0:
                resp['hint'] = _(
                    'All %(count)s default mapping(s) already exist in target environment. No new records created.'
                ) % {'count': source_count}
            else:
                resp['hint'] = _(
                    'No mappings copied. Source has %(count)s default mapping(s). '
                    'Target: %(tr)s roles, %(tf)s functions (%(mapped)s matched), %(tright)s rights. '
                    'Skipped: %(sr)s (no role), %(sf)s (no function), %(sright)s (no right). '
                    'Create roles/functions/rights in target with same names (or name_local) as in source.'
                ) % {
                    'count': source_count,
                    'tr': target_roles_count,
                    'tf': target_funcs_count,
                    'mapped': len(func_id_map),
                    'tright': target_rights_count,
                    'sr': skip_no_role,
                    'sf': skip_no_func,
                    'sright': skip_no_right,
                }
        return JsonResponse(resp)
    except Exception as e:
        logger.error(f"Error copying matrix between environments: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


# API Access Permissions
def has_access_api_permission(user):
    """Check if user has permission to access API functionality"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_api=True
    ).exists()

def can_add_access_api(user):
    """Check if user can add API access configurations"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_api=True,
        can_add_access_api=True
    ).exists()

def can_edit_access_api(user):
    """Check if user can edit API access configurations"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_api=True,
        can_edit_access_api=True
    ).exists()

def can_delete_access_api(user):
    """Check if user can delete API access configurations"""
    return AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_api=True,
        can_delete_access_api=True
    ).exists()

def get_user_companies_for_api(user):
    """Get companies accessible to user for API functionality"""
    # First check if user has any API access permissions
    api_access = AccessISAM.objects.filter(
        group__in=user.groups.all(),
        has_access_api=True
    )
    
    if not api_access.exists():
        return Company.objects.none()
    
    # Get all companies from API access permissions
    companies = Company.objects.filter(
        access_isam__in=api_access
    ).distinct()
    
    return companies

def can_submit_access_requests(user):
    """Check if user can submit access requests based on active SystemAccess request_users, request_groups, or if they are owners, administrators, or approving persons"""
    from .models import SystemAccess
    import logging
    
    logger = logging.getLogger(__name__)
    # Reduce noise: only log warnings+ globally; keep function quiet
    
    # Check if user is in request_users of any active SystemAccess record
    active_user_records = SystemAccess.objects.filter(
        request_users=user,
        is_active=True
    ).filter(
        # Check if record hasn't expired
        Q(end_date__gt=timezone.now()) | Q(end_date__isnull=True)
    )
    
    # noisy log removed
    for record in active_user_records:
        record_name = f"{record.asset.name} - {record.access_right}" if record.access_right else record.asset.name
        # noisy log removed
    
    if active_user_records.exists():
        # noisy log removed
        return True
    
    # Check if user's groups are in request_groups of any active SystemAccess record
    user_groups = user.groups.all()
    # noisy log removed
    
    if user_groups.exists():
        active_group_records = SystemAccess.objects.filter(
            request_groups__in=user_groups,
            is_active=True
        ).filter(
            # Check if record hasn't expired
            Q(end_date__gt=timezone.now()) | Q(end_date__isnull=True)
        )
        
        # noisy log removed
        for record in active_group_records:
            record_name = f"{record.asset.name} - {record.access_right}" if record.access_right else record.asset.name
            groups_in_record = record.request_groups.filter(id__in=[g.id for g in user_groups])
            # noisy log removed
        
        if active_group_records.exists():
            # noisy log removed
            return True
    
    # Check if user is an owner of any active SystemAccess record's asset
    active_owner_records = SystemAccess.objects.filter(
        asset__owners__cabinet_user__user=user,
        is_active=True
    ).filter(
        # Check if record hasn't expired
        Q(end_date__gt=timezone.now()) | Q(end_date__isnull=True)
    )
    
    # noisy log removed
    for record in active_owner_records:
        record_name = f"{record.asset.name} - {record.access_right}" if record.access_right else record.asset.name
        # noisy log removed
    
    if active_owner_records.exists():
        # noisy log removed
        return True
    
    # Check if user is an administrator of any active SystemAccess record's asset
    active_admin_records = SystemAccess.objects.filter(
        asset__administrators__cabinet_user__user=user,
        is_active=True
    ).filter(
        # Check if record hasn't expired
        Q(end_date__gt=timezone.now()) | Q(end_date__isnull=True)
    )
    
    # noisy log removed
    for record in active_admin_records:
        record_name = f"{record.asset.name} - {record.access_right}" if record.access_right else record.asset.name
        # noisy log removed
    
    if active_admin_records.exists():
        # noisy log removed
        return True
    
    # Check if user is an approving person of any active SystemAccess record's asset
    active_approving_records = SystemAccess.objects.filter(
        asset__approving_persons__cabinet_user__user=user,
        is_active=True
    ).filter(
        # Check if record hasn't expired
        Q(end_date__gt=timezone.now()) | Q(end_date__isnull=True)
    )
    
    # noisy log removed
    for record in active_approving_records:
        record_name = f"{record.asset.name} - {record.access_right}" if record.access_right else record.asset.name
        # noisy log removed
    
    if active_approving_records.exists():
        # noisy log removed
        return True
    
    # Check if user's groups are owners of any active SystemAccess record's asset
    if user_groups.exists():
        active_group_owner_records = SystemAccess.objects.filter(
            asset__owners__cabinet_user__user__groups__in=user_groups,
            is_active=True
        ).filter(
            # Check if record hasn't expired
            Q(end_date__gt=timezone.now()) | Q(end_date__isnull=True)
        )
        
        # noisy log removed
        for record in active_group_owner_records:
            record_name = f"{record.asset.name} - {record.access_right}" if record.access_right else record.asset.name
            # noisy log removed
        
        if active_group_owner_records.exists():
            # noisy log removed
            return True
    
    # Check if user's groups are administrators of any active SystemAccess record's asset
    if user_groups.exists():
        active_group_admin_records = SystemAccess.objects.filter(
            asset__administrators__cabinet_user__user__groups__in=user_groups,
            is_active=True
        ).filter(
            # Check if record hasn't expired
            Q(end_date__gt=timezone.now()) | Q(end_date__isnull=True)
        )
        
        # noisy log removed
        for record in active_group_admin_records:
            record_name = f"{record.asset.name} - {record.access_right}" if record.access_right else record.asset.name
            # noisy log removed
        
        if active_group_admin_records.exists():
            # noisy log removed
            return True
    
    # Check if user's groups are approving persons of any active SystemAccess record's asset
    if user_groups.exists():
        active_group_approving_records = SystemAccess.objects.filter(
            asset__approving_persons__cabinet_user__user__groups__in=user_groups,
            is_active=True
        ).filter(
            # Check if record hasn't expired
            Q(end_date__gt=timezone.now()) | Q(end_date__isnull=True)
        )
        
        # noisy log removed
        for record in active_group_approving_records:
            record_name = f"{record.asset.name} - {record.access_right}" if record.access_right else record.asset.name
            # noisy log removed
        
        if active_group_approving_records.exists():
            # noisy log removed
            return True
    
    # noisy log removed
    return False