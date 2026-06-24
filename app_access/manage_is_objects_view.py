# SecBoard\app_access\manage_is_objects_view.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _, get_language
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf import settings

from .models import (
    SystemAccess, AccessRight, AccessRightTranslation, AccessFunctionIS, AccessFunctionISTranslation,
    AccessStatus, ApprovingPerson, AccessApprover, AccessRoles, AccessRolesTranslation,
    AccessObjectIS, AccessObjectISTranslation,
    ObjectRoles, ObjectAccessRights, AccessObjectFunction,
    ObjectRoleFunctions, ObjectFunctionRightMapping, AccessISAM, AccessRequestSequence
)
from .matrix_view import (
    has_access_config_is_permission,
    can_add_access_config_is,
    can_edit_access_config_is,
    can_delete_access_config_is,
    get_user_companies_for_config_is,
    get_user_companies_for_manage_ar,
)
import logging
from django.contrib.auth.models import Group, User
from django.db import transaction, OperationalError, IntegrityError
from django.db.models import F, Value, CharField, Case, When, Q, Prefetch
from django.db import models
from app_conf.models import Company
from app_asset.models import AccessAssets, InformationAsset
from app_access.models import AccessRequest, AccessRequestAdminStatusHistory
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json
import time
from app_cabinet.models import CabinetUser, CabinetGroup

logger = logging.getLogger(__name__)


def _get_object_form_languages():
    """Return list of (code, label) for site languages (used in Add/Edit Object modals)."""
    return list(getattr(settings, 'LANGUAGES', [('en', 'English')])) or [('en', 'English')]


def _get_country_for_lang(lang_code):
    """Return first Country for language code (for AccessObjectISTranslation), or None."""
    from app_cabinet.models import LANGUAGE_COUNTRY_MAP
    from app_conf.models import Country
    if not lang_code:
        return None
    lang_code = (lang_code or '')[:2].lower()
    for code in LANGUAGE_COUNTRY_MAP.get(lang_code, []):
        try:
            return Country.objects.filter(code__iexact=code).first()
        except Exception:
            continue
    return None


def _normalize_lang_to_legacy_role(lang_code):
    """Map form lang code to legacy attr (ua, ru, en) for roles."""
    lc = (lang_code or '')[:2].lower()
    if lc in ('uk', 'ua'):
        return 'ua'
    if lc == 'ru':
        return 'ru'
    if lc == 'en':
        return 'en'
    return None


def _build_function_names_descriptions(func, form_languages=None):
    """Build function_names and function_descriptions dicts keyed by lang. English from name/description, others from Translation."""
    form_langs = form_languages or _get_object_form_languages()
    function_names = {}
    function_descriptions = {}
    for lang_code, _label in form_langs:
        if hasattr(func, 'get_name'):
            function_names[lang_code] = func.get_name(lang_code) or ''
        else:
            function_names[lang_code] = ''
        if hasattr(func, 'get_description'):
            function_descriptions[lang_code] = func.get_description(lang_code) or ''
        else:
            function_descriptions[lang_code] = ''
    return function_names, function_descriptions


def _build_role_names_descriptions(role, form_languages=None):
    """Build role_names and role_descriptions dicts keyed by lang. English from name/description, others from AccessRolesTranslation."""
    form_langs = form_languages or _get_object_form_languages()
    role_names = {}
    role_descriptions = {}
    for lang_code, _label in form_langs:
        role_names[lang_code] = role.get_name(lang_code) or ''
        role_descriptions[lang_code] = role.get_description(lang_code) or ''
    return role_names, role_descriptions


# ================ OBJECTS MANAGEMENT FUNCTIONS ================

@login_required
@require_http_methods(['GET'])
def get_system_objects(request):
    """Get objects for a specific system and environment"""
    try:
        system_id = request.GET.get('system_id')
        environment = request.GET.get('environment', 'test')
        
        if not system_id:
            return JsonResponse({
                'success': False,
                'message': _('System ID is required')
            }, status=400)

        # Filter objects by system and environment
        objects = AccessObjectIS.objects.filter(
            asset_id=system_id,
            environment=environment,
            is_active=True,
            parent_id=None  # Отримуємо тільки кореневі об'єкти
        ).order_by('order')

        def get_children(parent):
            children = AccessObjectIS.objects.filter(
                parent_id=parent.id,
                asset_id=system_id,
                environment=environment,
                is_active=True
            ).order_by('order')
            
            return [{
                'id': child.id,
                'name': child.get_name() or '',
                'description': child.get_description() or '',
                'color': child.color,
                'order': child.order,
                'parent_id': child.parent_id,
                'children': get_children(child)
            } for child in children]

        objects_data = []
        for obj in objects:
            objects_data.append({
                'id': obj.id,
                'name': obj.get_name() or '',
                'description': obj.get_description() or '',
                'color': obj.color,
                'order': obj.order,
                'parent_id': obj.parent_id,
                'children': get_children(obj)
            })

        return JsonResponse({
            'objects': objects_data
        })

    except Exception as e:
        logger.error(f"Error getting system objects: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_POST
def save_object(request):
    """Save or update object. Single name/description (multilingual removed)."""
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else None

        def _get(key, default=''):
            if data is not None:
                return (data.get(key) or default) if default != '' else (data.get(key) or '')
            return (request.POST.get(key) or default) if default != '' else (request.POST.get(key) or '')

        object_id = _get('object_id') or None
        parent_id = _get('parent_id') or None
        system_id = _get('system_id')
        environment = _get('environment', 'test')
        name = (_get('name') or _get('object_name_en') or _get('object_name') or '').strip()
        description = (_get('description') or _get('description_en') or '').strip()

        if not system_id:
            return JsonResponse({
                'success': False,
                'message': _('System ID is required')
            }, status=400)

        object_data = {
            'name': name,
            'description': description,
            'color': _get('color', '#6c757d'),
            'asset_id': system_id,
            'environment': environment
        }

        with transaction.atomic():
            name_exists_query = AccessObjectIS.objects.filter(
                asset_id=system_id,
                environment=environment,
                name=object_data['name']
            )
            if object_id:
                name_exists_query = name_exists_query.exclude(id=object_id)
            if name_exists_query.exists():
                return JsonResponse({
                    'success': False,
                    'message': _('Object with this name already exists in this system')
                }, status=400)

            if object_id:
                obj = get_object_or_404(AccessObjectIS, id=object_id)
                if parent_id and int(parent_id) != obj.parent_id:
                    new_parent = get_object_or_404(AccessObjectIS, id=parent_id)
                    obj.move_to(new_parent)
                elif not parent_id and obj.parent_id:
                    obj.move_to(None)
                obj.name = object_data['name']
                obj.description = object_data['description']
                obj.color = object_data['color']
                obj.save()
                message = _('Object updated successfully')
            else:
                if parent_id:
                    parent = get_object_or_404(AccessObjectIS, id=parent_id)
                    obj = AccessObjectIS.objects.create(parent=parent, **object_data)
                else:
                    obj = AccessObjectIS.objects.create(**object_data)
                message = _('Object created successfully')

            return JsonResponse({
                'success': True,
                'message': message,
                'object': {
                    'id': obj.id,
                    'name': obj.get_name() or '',
                    'description': obj.get_description() or '',
                    'color': obj.color,
                    'parent_id': obj.parent_id
                }
            })
    except Exception as e:
        logger.error(f"Error saving object: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)
def object_detail(request, object_id):
    """Get details for a specific object"""
    try:
        logger.info(f"Getting details for object_id: {object_id}")

        if not object_id:
            logger.error("Object ID is required")
            return JsonResponse({
                'error': _('Object ID is required')
            }, status=400)

        try:
            # Спочатку перевіримо, чи існує об'єкт
            if not AccessObjectIS.objects.filter(id=object_id).exists():
                logger.error(f"Object with id {object_id} not found in database")
                return JsonResponse({
                    'error': _('Object not found')
                }, status=404)

            # Логуємо запит до бази даних
            logger.info(f"Querying object with id {object_id}")
            obj = AccessObjectIS.objects.select_related(
                'parent',
                'asset'
            ).prefetch_related('translations__country').get(id=object_id)

            logger.info(f"Found object: {obj}")
            logger.info(f"Asset: {obj.asset}")

            data = {
                'id': obj.id,
                'name': obj.get_name() or '',
                'description': obj.get_description() or '',
                'color': obj.color,
                'parent_id': obj.parent_id,
                'asset_id': obj.asset_id,
                'order': obj.order
            }

            logger.info(f"Returning object data: {data}")
            return JsonResponse(data)

        except AccessObjectIS.DoesNotExist:
            logger.error(f"Object with id {object_id} does not exist")
            return JsonResponse({
                'error': _('Object not found')
            }, status=404)

    except Exception as e:
        logger.error(f"Error getting object details: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': _('Error loading object details'),
            'details': str(e)
        }, status=500)


@login_required
@require_POST
def delete_object(request, object_id):
    """Delete specific object"""
    try:
        logger.info(f"Attempting to delete object with ID: {object_id}")

        with transaction.atomic():
            # Отримуємо об'єкт
            obj = get_object_or_404(AccessObjectIS, id=object_id)
            logger.info(f"Found object: {obj}")

            # Перевіряємо, чи є дочірні об'єкти
            children_count = obj.get_descendant_count()
            logger.info(f"Object has {children_count} descendants")

            if children_count > 0:
                logger.warning(f"Object {object_id} has children, cannot delete")
                return JsonResponse({
                    'success': False,
                    'message': _('Cannot delete object with children. Please delete children first.')
                }, status=400)

            # Видаляємо об'єкт
            obj.delete()
            logger.info(f"Object {object_id} deleted successfully")

            return JsonResponse({
                'success': True,
                'message': _('Object deleted successfully')
            })

    except AccessObjectIS.DoesNotExist:
        logger.error(f"Object with id {object_id} not found")
        return JsonResponse({
            'success': False,
            'message': _('Object not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting object: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': _('Error deleting object')
        }, status=500)


@login_required
@require_POST
def update_objects_order(request):
    """Update objects order"""
    try:
        data = json.loads(request.body)
        orders = data.get('orders', [])
        parent_id = data.get('parent_id')
        moved_item_id = data.get('moved_item_id')
        system_id = data.get('system_id')
        environment = data.get('environment', 'test')
        
        if not system_id:
            return JsonResponse({
                'success': False,
                'message': _('System ID is required')
            }, status=400)

        with transaction.atomic():
            # Оновлюємо переміщений об'єкт
            if moved_item_id:
                moved_object = AccessObjectIS.objects.get(
                    id=moved_item_id,
                    asset_id=system_id,
                    environment=environment
                )
                old_parent_id = moved_object.parent_id
                moved_object.parent_id = parent_id
                moved_object.save()

            # Отримуємо всі об'єкти в поточному контейнері
            objects_in_container = AccessObjectIS.objects.filter(
                asset_id=system_id,
                environment=environment,
                parent_id=parent_id,
                is_active=True
            ).order_by('order')

            # Створюємо словник для швидкого пошуку нових порядків
            new_orders = {str(item['id']): item['order'] for item in orders}

            # Оновлюємо порядок для кожного об'єкта
            for index, obj in enumerate(objects_in_container):
                new_order = new_orders.get(str(obj.id))
                if new_order is not None and obj.order != new_order:
                    obj.order = new_order
                    obj.save()

            return JsonResponse({
                'success': True,
                'message': _('Order updated successfully')
            })

    except Exception as e:
        logger.error(f"Error updating objects order: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)



# ================ OBJECT ROLES MANAGEMENT FUNCTIONS ================

@login_required
@require_http_methods(['GET'])
def get_object_roles(request, object_id):
    """Get roles assigned to a specific object"""
    try:
        logger.info(f"Getting roles for object_id: {object_id}")
        
        object_roles = ObjectRoles.objects.filter(
            access_object_id=object_id,
            is_active=True
        ).select_related(
            'role'
        ).order_by('order')
        
        logger.info(f"Found {object_roles.count()} roles for object {object_id}")

        roles_data = [{
            'id': obj_role.id,
            'role_id': obj_role.role.id,
            'name': obj_role.role.get_name() or '',
            'description': obj_role.role.get_description() or '',
            'color': obj_role.role.color,
            'is_object_specific': obj_role.role.is_object_specific,
            'order': obj_role.order,
            'is_active': obj_role.is_active
        } for obj_role in object_roles]

        return JsonResponse({
            'status': 'success',
            'roles': roles_data,
            'total_count': len(roles_data)
        })

    except Exception as e:
        logger.error(f"Error getting object roles: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@require_POST
@ensure_csrf_cookie
def add_object_roles(request):
    """Add or update roles for a specific object"""
    try:
        data = json.loads(request.body)
        object_id = data.get('object_id')
        roles_data = data.get('roles', [])

        logger.info(f"Adding roles for object_id: {object_id}")
        logger.info(f"Roles data: {roles_data}")

        if not object_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Object ID is required')
            }, status=400)

        with transaction.atomic():
            try:
                access_object = AccessObjectIS.objects.get(id=object_id)
                logger.info(f"Found object: {access_object}")
            except AccessObjectIS.DoesNotExist:
                logger.error(f"Object with ID {object_id} not found")
                return JsonResponse({
                    'status': 'error',
                    'message': _('Selected object does not exist')
                }, status=400)

            # Перевіряємо існування всіх role_id перед видаленням
            for role_data in roles_data:
                logger.info(f"Checking role with ID: {role_data['role_id']}")
                if not AccessRoles.objects.filter(id=role_data['role_id']).exists():
                    logger.error(f"Role with ID {role_data['role_id']} not found")
                    return JsonResponse({
                        'status': 'error',
                        'message': _('One or more selected roles do not exist')
                    }, status=400)

            # Delete existing roles
            old_roles = ObjectRoles.objects.filter(access_object=access_object)
            logger.info(f"Deleting {old_roles.count()} existing roles")
            old_roles.delete()

            # Create new roles
            created_roles = []
            for role_data in roles_data:
                try:
                    role = AccessRoles.objects.get(id=role_data['role_id'])
                    logger.info(f"Creating role assignment for role: {role}")
                    obj_role = ObjectRoles.objects.create(
                        access_object=access_object,
                        role=role,
                        order=role_data.get('order', 0),
                        is_active=role_data.get('is_active', True)
                    )
                    created_roles.append(obj_role)
                except AccessRoles.DoesNotExist:
                    logger.error(f"Failed to find role with ID {role_data['role_id']}")
                    raise ValidationError(_(f"Role with id {role_data['role_id']} does not exist"))

            logger.info(f"Successfully created {len(created_roles)} role assignments")
            return JsonResponse({
                'status': 'success',
                'message': _('Object roles updated successfully')
            })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except ValidationError as e:
        logger.error(f"Validation error in add_object_roles: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Error in add_object_roles: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


@login_required
@require_POST
def update_object_roles(request, object_id):
    """Update roles for a specific object"""
    try:
        logger.info(f"Updating roles for object_id: {object_id}")
        
        # Перевіряємо, чи існує об'єкт
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        logger.info(f"Found object: {access_object}")
        
        # Парсимо дані запиту
        data = json.loads(request.body)
        roles = data.get('roles', [])
        logger.info(f"Received roles data: {roles}")
        
        # Валідація даних
        if not isinstance(roles, list):
            raise ValidationError(_('Roles must be a list'))
        
        for role_data in roles:
            if not isinstance(role_data, dict):
                raise ValidationError(_('Each role must be an object'))
            if 'role_id' not in role_data:
                raise ValidationError(_('Each role must have role_id'))
            
            # Перевіряємо, чи існує роль
            if not AccessRoles.objects.filter(id=role_data['role_id']).exists():
                raise ValidationError(_(f'Role with id {role_data["role_id"]} does not exist'))
        
        with transaction.atomic():
            # Видаляємо існуючі roles
            deleted_count = ObjectRoles.objects.filter(access_object_id=object_id).delete()
            logger.info(f"Deleted {deleted_count} existing roles")
            
            # Додаємо нові roles
            created_roles = []
            for role_data in roles:
                obj_role = ObjectRoles.objects.create(
                    access_object_id=object_id,
                    role_id=role_data['role_id'],
                    order=role_data.get('order', 0),
                    is_active=role_data.get('is_active', True)
                )
                created_roles.append(obj_role)
            
            logger.info(f"Created {len(created_roles)} new roles")
            
            return JsonResponse({
                'status': 'success',
                'message': _('Object roles updated successfully'),
                'updated_count': len(created_roles)
            })
            
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating object roles: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': _('An error occurred while updating roles')
        }, status=400)

@login_required
@require_http_methods(['GET'])
def get_object_available_roles(request, object_id):
    """Get available roles for a specific object (general system roles + object-specific roles)"""
    try:
        # Get the object and its system
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        system_id = access_object.asset_id
        environment = access_object.environment
        
        logger.info(f"Getting available roles for object_id: {object_id}, system_id: {system_id}, environment: {environment}")

        # Get general system roles (non-object-specific)
        general_roles = AccessRoles.objects.filter(
            system_id=system_id,
            environment=environment,
            is_object_specific=False,
            is_active=True
        )
        
        # Get object-specific roles created for this object
        object_specific_roles = AccessRoles.objects.filter(
            system_id=system_id,
            environment=environment,
            is_object_specific=True,
            created_for_object_id=object_id,
            is_active=True
        )
        
        # Combine both querysets
        all_roles = general_roles.union(object_specific_roles).order_by('order', 'name', 'code')
        
        current_lang = (get_language() or '')[:2].lower()
        roles_data = [{
            'id': role.id,
            'name': role.get_name() or '',
            'description': role.get_description() or '',
            'color': role.color,
            'is_object_specific': role.is_object_specific
        } for role in all_roles]

        logger.info(f"Found {len(roles_data)} available roles for object {object_id}")
        
        return JsonResponse({
            'status': 'success',
            'roles': roles_data
        })

    except Exception as e:
        logger.error(f"Error getting object available roles: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_POST
def update_object_roles_order(request, object_id):
    """Update the order of roles for a specific object"""
    try:
        logger.info(f"Updating role order for object {object_id}")
        
        # Get the object
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        
        # Parse the order data from request
        data = json.loads(request.body)
        roles = data.get('roles', [])
        
        if not roles:
            return JsonResponse({
                'status': 'error',
                'message': _('No role order data provided')
            }, status=400)
        
        with transaction.atomic():
            # Update each role order
            for item in roles:
                role_id = item.get('role_id')
                order = item.get('order', 0)
                
                try:
                    object_role = ObjectRoles.objects.get(
                        access_object=access_object,
                        role_id=role_id,
                        is_active=True
                    )
                    object_role.order = order
                    object_role.save()
                    
                except ObjectRoles.DoesNotExist:
                    logger.warning(f"ObjectRole not found for object {object_id} and role {role_id}")
                    continue
            
            logger.info(f"Successfully updated role order for object {object_id}")
            
            return JsonResponse({
                'status': 'success',
                'message': _('Role order updated successfully')
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating object role order: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

# ================ OBJECT ACCESS RIGHTS MANAGEMENT FUNCTIONS ================

@login_required
@require_http_methods(['GET'])
def get_object_access_rights(request, object_id):
    """Get access rights assigned to a specific object"""
    try:
        logger.info(f"Getting access rights for object_id: {object_id}")
        
        object_rights = ObjectAccessRights.objects.filter(
            access_object_id=object_id,
            is_active=True
        ).select_related(
            'access_right'
        ).order_by('order')
        
        logger.info(f"Found {object_rights.count()} access rights for object {object_id}")

        rights_data = [{
            'id': obj_right.id,
            'access_right_id': obj_right.access_right.id,
            'name': obj_right.access_right.get_name() or obj_right.access_right.name or '',
            'description': obj_right.access_right.get_description() or '',
            'color': obj_right.access_right.color,
            'is_object_specific': obj_right.access_right.is_object_specific,
            'order': obj_right.order,
            'is_active': obj_right.is_active
        } for obj_right in object_rights]

        return JsonResponse({
            'status': 'success',
            'access_rights': rights_data,
            'total_count': len(rights_data)
        })

    except Exception as e:
        logger.error(f"Error getting object access rights: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@require_POST
@ensure_csrf_cookie
def add_object_access_rights(request):
    """Add or update access rights for a specific object"""
    try:
        data = json.loads(request.body)
        object_id = data.get('object_id')
        rights_data = data.get('access_rights', [])

        logger.info(f"Adding access rights for object_id: {object_id}")
        logger.info(f"Access rights data: {rights_data}")

        if not object_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Object ID is required')
            }, status=400)

        with transaction.atomic():
            try:
                access_object = AccessObjectIS.objects.get(id=object_id)
                logger.info(f"Found object: {access_object}")
            except AccessObjectIS.DoesNotExist:
                logger.error(f"Object with ID {object_id} not found")
                return JsonResponse({
                    'status': 'error',
                    'message': _('Selected object does not exist')
                }, status=400)

            # Перевіряємо існування всіх access_right_id перед видаленням
            for right_data in rights_data:
                logger.info(f"Checking access right with ID: {right_data['access_right_id']}")
                if not AccessRight.objects.filter(id=right_data['access_right_id']).exists():
                    logger.error(f"Access right with ID {right_data['access_right_id']} not found")
                    return JsonResponse({
                        'status': 'error',
                        'message': _('One or more selected access rights do not exist')
                    }, status=400)

            # Delete existing access rights
            old_rights = ObjectAccessRights.objects.filter(access_object=access_object)
            logger.info(f"Deleting {old_rights.count()} existing access rights")
            old_rights.delete()

            # Create new access rights
            created_rights = []
            for right_data in rights_data:
                try:
                    access_right = AccessRight.objects.get(id=right_data['access_right_id'])
                    logger.info(f"Creating access right assignment for: {access_right}")
                    obj_right = ObjectAccessRights.objects.create(
                        access_object=access_object,
                        access_right=access_right,
                        order=right_data.get('order', 0),
                        is_active=right_data.get('is_active', True)
                    )
                    created_rights.append(obj_right)
                except AccessRight.DoesNotExist:
                    logger.error(f"Failed to find access right with ID {right_data['access_right_id']}")
                    raise ValidationError(_(f"Access right with id {right_data['access_right_id']} does not exist"))

            logger.info(f"Successfully created {len(created_rights)} access right assignments")
            return JsonResponse({
                'status': 'success',
                'message': _('Object access rights updated successfully')
            })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except ValidationError as e:
        logger.error(f"Validation error in add_object_access_rights: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Error in add_object_access_rights: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(['GET'])
def get_object_available_access_rights(request, object_id):
    """Get available access rights for a specific object"""
    try:
        # Get the object and its system
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        system_id = access_object.asset_id
        environment = access_object.environment
        
        logger.info(f"Getting available access rights for object_id: {object_id}, system_id: {system_id}, environment: {environment}")

        # Get all access rights for this system:
        # 1. Regular system access rights (not object-specific)
        # 2. Object-specific access rights created for this specific object
        access_rights = AccessRight.objects.filter(
            Q(system_id=system_id, environment=environment, is_object_specific=False) |
            Q(system_id=system_id, environment=environment, is_object_specific=True, created_for_object_id=object_id),
            is_active=True
        ).distinct().order_by('name', 'code')
        
        rights_data = [{
            'id': right.id,
            'name': right.get_name() or right.name or '',
            'description': right.get_description() or '',
            'color': right.color,
            'is_object_specific': right.is_object_specific,
            'created_for_object_id': right.created_for_object_id
        } for right in access_rights]

        logger.info(f"Found {len(rights_data)} available access rights for object {object_id}")
        
        return JsonResponse({
            'status': 'success',
            'access_rights': rights_data
        })

    except Exception as e:
        logger.error(f"Error getting object available access rights: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_POST
@ensure_csrf_cookie
def save_custom_object_access_right(request):
    """Create a custom access right for a specific object"""
    try:
        data = json.loads(request.body)
        object_id = data.get('object_id')
        name = (data.get('name') or data.get('name_en') or data.get('name_ua') or data.get('name_ru') or '').strip()
        description = (data.get('description') or data.get('description_en') or data.get('description_ua') or data.get('description_ru') or '').strip()
        name_ua = data.get('name_ua', '').strip()
        name_ru = data.get('name_ru', '').strip()
        name_en = data.get('name_en', '').strip()
        description_ua = data.get('description_ua', '').strip()
        description_ru = data.get('description_ru', '').strip()
        description_en = data.get('description_en', '').strip()
        color = data.get('color', '#000000')

        logger.info(f"Creating custom access right for object_id: {object_id}")

        if not object_id or not name:
            return JsonResponse({
                'status': 'error',
                'message': _('Object ID and name are required')
            }, status=400)

        # Get the object and its system
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        system = access_object.asset

        from app_access.models import AccessRightTranslation
        with transaction.atomic():
            existing_right = AccessRight.objects.select_for_update().filter(
                system=system,
                environment=access_object.environment,
                name=name
            ).first()

            if existing_right:
                return JsonResponse({
                    'status': 'error',
                    'message': _('Access right with this name already exists for this system. Please choose a different name.')
                }, status=400)

            max_order = AccessRight.objects.filter(
                system=system,
                environment=access_object.environment
            ).aggregate(max_order=models.Max('order'))['max_order'] or 0

            custom_access_right = AccessRight.objects.create(
                system=system,
                environment=access_object.environment,
                name=name,
                description=description,
                color=color,
                order=max_order + 1,
                is_object_specific=True,
                created_for_object=access_object
            )
            for lang_label, name_val, desc_val in [('ua', name_ua, description_ua), ('ru', name_ru, description_ru)]:
                country = _get_country_for_lang(lang_label)
                if country:
                    t, _ = AccessRightTranslation.objects.get_or_create(
                        access_right=custom_access_right, country=country,
                        defaults={'name_local': name_val or '', 'description': desc_val or ''}
                    )
                    t.name_local = name_val or ''
                    t.description = desc_val or ''
                    t.save()

            logger.info(f"Created custom access right {custom_access_right.id} for object {object_id}")

            return JsonResponse({
                'status': 'success',
                'message': 'Custom access right created successfully',
                'access_right': {
                    'id': custom_access_right.id,
                    'name': custom_access_right.get_name() or '',
                    'description': custom_access_right.get_description() or '',
                    'color': custom_access_right.color,
                    'is_object_specific': custom_access_right.is_object_specific,
                    'created_for_object_id': custom_access_right.created_for_object_id
                }
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except IntegrityError as e:
        # Handle database constraint violations
        if 'Duplicate entry' in str(e) and 'accessrole_nam' in str(e):
            return JsonResponse({
                'status': 'error',
                'message': f'Access right with this name already exists for this system. Please choose a different name.'
            }, status=400)
        else:
            logger.error(f"Database integrity error creating custom access right: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Database constraint violation. Please try again.'
            }, status=400)
    except Exception as e:
        logger.error(f"Error creating custom access right: {str(e)}")
        
        # Enhanced error handling for specific duplicate entry errors
        if 'Duplicate entry' in str(e):
            return JsonResponse({
                'status': 'error',
                'message': f'Access right with this name already exists for this system. Please choose a different name.'
            }, status=400)
        
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
def edit_custom_object_access_right(request):
    """Edit existing custom object access right. Accepts single name/description or legacy name_ua/name_en etc."""
    try:
        data = json.loads(request.body)
        access_right_id = data.get('access_right_id')
        object_id = data.get('object_id')
        name = (data.get('name') or data.get('name_en') or data.get('name_ua') or data.get('name_ru') or '').strip()
        description = (data.get('description') or data.get('description_en') or data.get('description_ua') or data.get('description_ru') or '').strip()
        name_ua = data.get('name_ua', '').strip()
        name_ru = data.get('name_ru', '').strip()
        name_en = data.get('name_en', '').strip()
        description_ua = data.get('description_ua', '').strip()
        description_ru = data.get('description_ru', '').strip()
        description_en = data.get('description_en', '').strip()
        color = (data.get('color') or '#007bff').strip()
        
        if not access_right_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Access right ID is required')
            }, status=400)
            
        if not object_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Object ID is required')
            }, status=400)
            
        if not name:
            return JsonResponse({
                'status': 'error',
                'message': _('Name is required')
            }, status=400)
        
        # Отримуємо право доступу
        try:
            access_right = AccessRight.objects.get(id=access_right_id)
        except AccessRight.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': _('Access right not found')
            }, status=404)
        
        # Перевіряємо що це object-specific право
        if not access_right.is_object_specific:
            return JsonResponse({
                'status': 'error',
                'message': _('Only custom access rights can be edited')
            }, status=400)
        
        # Отримуємо об'єкт
        try:
            access_object = AccessObjectIS.objects.get(id=object_id)
        except AccessObjectIS.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': _('Object not found')
            }, status=404)
        
        # Перевіряємо що право створене для цього об'єкта
        if access_right.created_for_object_id != int(object_id):
            return JsonResponse({
                'status': 'error',
                'message': _('Access right does not belong to this object')
            }, status=403)
        
        existing_right = AccessRight.objects.filter(
            system=access_object.asset,
            name=name
        ).exclude(id=access_right_id).first()
        
        if existing_right:
            return JsonResponse({
                'status': 'error',
                'message': _('Access right with this name already exists')
            }, status=400)
        
        logger.info(f"Updating custom access right {access_right_id} for object {object_id}")
        
        from app_access.models import AccessRightTranslation
        access_right.name = name
        access_right.description = description
        access_right.color = color
        access_right.save()
        for lang_label, name_val, desc_val in [('ua', name_ua, description_ua), ('ru', name_ru, description_ru)]:
            country = _get_country_for_lang(lang_label)
            if country:
                trans, _ = AccessRightTranslation.objects.get_or_create(
                    access_right=access_right, country=country,
                    defaults={'name_local': name_val or '', 'description': desc_val or ''}
                )
                trans.name_local = name_val or ''
                trans.description = desc_val or ''
                trans.save()
        
        logger.info(f"Updated custom access right {access_right_id} for object {object_id}")
        
        return JsonResponse({
            'status': 'success',
            'message': _('Custom access right updated successfully'),
            'access_right': {
                'id': access_right.id,
                'name': access_right.get_name() or '',
                'description': access_right.get_description() or '',
                'color': access_right.color,
                'is_object_specific': access_right.is_object_specific
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating custom access right: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_POST
@ensure_csrf_cookie
def delete_custom_object_access_right(request):
    """Delete custom object access right"""
    try:
        data = json.loads(request.body)
        access_right_id = data.get('access_right_id')
        object_id = data.get('object_id')
        
        # Валідація
        if not access_right_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Access right ID is required')
            }, status=400)
            
        if not object_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Object ID is required')
            }, status=400)
        
        # Отримуємо право доступу
        access_right = get_object_or_404(AccessRight, id=access_right_id)
        
        # Перевіряємо що це object-specific право
        if not access_right.is_object_specific:
            return JsonResponse({
                'status': 'error',
                'message': _('Only custom access rights can be deleted')
            }, status=400)
        
        # Перевіряємо що право створене для цього об'єкта
        if access_right.created_for_object_id != int(object_id):
            return JsonResponse({
                'status': 'error',
                'message': _('Access right does not belong to this object')
            }, status=403)
        
        # Check for dependencies and handle force delete
        force_delete = data.get('force_delete', False)
        assigned_objects = ObjectAccessRights.objects.filter(access_right=access_right, is_active=True)
        
        if assigned_objects.exists() and not force_delete:
            assigned_count = assigned_objects.count()
            return JsonResponse({
                'status': 'warning',
                'message': _('This access right is currently assigned to %(count)d object(s). Do you want to remove it from all objects and delete it?') % {'count': assigned_count},
                'assigned_count': assigned_count,
                'requires_confirmation': True
            }, status=400)
        
        # If force delete is requested, remove all assignments first
        if force_delete and assigned_objects.exists():
            assigned_objects.update(is_active=False)
            logger.info(f"Deactivated {assigned_objects.count()} object access right assignments for access right {access_right.id}")
        
        logger.info(f"Deleting custom access right {access_right_id} for object {object_id}")
        
        # Видаляємо право доступу (це також видалить всі пов'язані записи через CASCADE)
        access_right_name = access_right.get_name() or access_right.name or ''
        access_right.delete()
        
        logger.info(f"Deleted custom access right '{access_right_name}' for object {object_id}")
        
        return JsonResponse({
            'status': 'success',
            'message': _('Custom access right deleted successfully')
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except Exception as e:
        logger.error(f"Error deleting custom access right: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(['GET'])
def get_custom_object_access_rights(request, object_id):
    """Get custom access rights for a specific object"""
    try:
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        
        # Current language (default en); names/descriptions via model get_name/get_description
        current_lang = (get_language() or 'en')[:2].lower()
        
        # Get custom access rights for this object
        custom_access_rights = AccessRight.objects.filter(
            system=access_object.asset,
            is_object_specific=True,
            created_for_object_id=object_id
        ).order_by('name')
        
        access_rights_data = []
        for access_right in custom_access_rights:
            # Check if access right is currently assigned to this object
            is_assigned = ObjectAccessRights.objects.filter(
                access_object=access_object,
                access_right=access_right,
                is_active=True
            ).exists()
            
            access_right_data = {
                'id': access_right.id,
                'name': access_right.get_name() or access_right.name or '',
                'description': access_right.get_description() or '',
                'localized_description': access_right.get_description(current_lang) or access_right.get_description('en') or '',
                'color': access_right.color,
                'is_object_specific': access_right.is_object_specific,
                'created_for_object_id': access_right.created_for_object_id,
                'is_assigned': is_assigned,
                'can_edit': True,  # Custom access rights can always be edited by object owner
                'can_delete': True  # Custom access rights can be deleted if not assigned or with confirmation
            }
            access_rights_data.append(access_right_data)
        
        return JsonResponse({
            'status': 'success',
            'object': {
                'id': access_object.id,
                'name': access_object.get_name() or access_object.name or '',
                'object_name_ru': access_object.get_name('ru') or access_object.name or '',
                'object_name_en': access_object.get_name('en') or access_object.name or '',
                'localized_name': access_object.get_name(current_lang) or access_object.get_name('en')
            },
            'access_rights': access_rights_data,
            'total_count': len(access_rights_data),
            'current_language': current_lang
        })
        
    except Exception as e:
        logger.error(f"Error getting custom object access rights: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# ================ CUSTOM OBJECT ROLES MANAGEMENT ================

@login_required
@require_POST
@ensure_csrf_cookie
def save_custom_object_role(request):
    """Save a custom role for a specific object. Accepts role_names/role_descriptions or role_name_<lang>/role_description_<lang>."""
    try:
        data = json.loads(request.body)
        object_id = data.get('object_id')
        form_langs = _get_object_form_languages()
        name_single = (data.get('name') or '').strip()
        description_single = (data.get('description') or '').strip()

        name_ua = (data.get('name_ua') or data.get('accessrole_name_ua') or data.get('role_name_ua') or data.get('role_name_uk', '')).strip()
        name_ru = (data.get('name_ru') or data.get('accessrole_name_ru') or data.get('role_name_ru', '')).strip()
        name_en = (data.get('name_en') or data.get('accessrole_name_en') or data.get('role_name_en', '')).strip()
        description_ua = (data.get('description_ua') or data.get('role_description_ua') or data.get('role_description_uk', '')).strip()
        description_ru = (data.get('description_ru') or data.get('role_description_ru', '')).strip()
        description_en = (data.get('description_en') or data.get('role_description_en', '')).strip()
        if name_single:
            name_en = name_en or name_single
            name_ua = name_ua or name_single
            name_ru = name_ru or name_single
        if description_single:
            description_en = description_en or description_single
            description_ua = description_ua or description_single
            description_ru = description_ru or description_single
        for lang_code, _lang_label in form_langs:
            leg = _normalize_lang_to_legacy_role(lang_code)
            if leg == 'ua':
                name_ua = name_ua or (data.get(f'role_name_{lang_code}', '') or '').strip()
                description_ua = description_ua or (data.get(f'role_description_{lang_code}', '') or '').strip()
            elif leg == 'ru':
                name_ru = name_ru or (data.get(f'role_name_{lang_code}', '') or '').strip()
                description_ru = description_ru or (data.get(f'role_description_{lang_code}', '') or '').strip()
            elif leg == 'en':
                name_en = name_en or (data.get(f'role_name_{lang_code}', '') or '').strip()
                description_en = description_en or (data.get(f'role_description_{lang_code}', '') or '').strip()
        extra_translations = [
            (lc, (data.get(f'role_name_{lc}', '') or '').strip(), (data.get(f'role_description_{lc}', '') or '').strip())
            for lc, _label in form_langs if _normalize_lang_to_legacy_role(lc) is None
        ]
        color = data.get('color', '#007bff')

        if not object_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Object ID is required')
            }, status=400)

        name_default = name_single or name_en or name_ua or name_ru
        if not name_default:
            return JsonResponse({
                'status': 'error',
                'message': _('Role name is required')
            }, status=400)

        try:
            access_object = AccessObjectIS.objects.get(id=object_id)
        except AccessObjectIS.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': _('Object not found')
            }, status=404)

        # Block only if a default (system-level) role already has this name; allow custom roles to reuse names
        existing_default_role = AccessRoles.objects.filter(
            system_id=access_object.asset_id,
            environment=access_object.environment,
            name=name_default,
            is_object_specific=False,
            created_for_object__isnull=True,
        ).first()
        if existing_default_role:
            logger.warning(
                "Blocking custom role creation: default role with same name exists "
                "(role_id=%s, name=%r, system_id=%s, environment=%s)",
                existing_default_role.id, existing_default_role.name,
                access_object.asset_id, access_object.environment,
            )
            return JsonResponse({
                'status': 'error',
                'message': _('Role with this name already exists in the system. Please choose a different name.')
            }, status=400)

        max_order = AccessRoles.objects.filter(
            system_id=access_object.asset_id,
            environment=access_object.environment
        ).aggregate(
            max_order=models.Max('order')
        )['max_order'] or 0

        logger.info(
            "Creating custom role: object_id=%s, name=%r, system_id=%s, environment=%s",
            object_id, name_default, access_object.asset_id, access_object.environment,
        )
        with transaction.atomic():
            custom_role = AccessRoles.objects.create(
                system_id=access_object.asset_id,
                environment=access_object.environment,
                name=name_en or name_default,
                description=description_en or description_ua or description_ru,
                color=color,
                order=max_order + 1,
                is_object_specific=True,
                created_for_object=access_object
            )
            for lang_label, name_val, desc_val in [('ua', name_ua, description_ua), ('ru', name_ru, description_ru)]:
                country = _get_country_for_lang(lang_label)
                if country:
                    trans, _created = AccessRolesTranslation.objects.get_or_create(
                        access_role=custom_role, country=country,
                        defaults={'name_local': name_val or '', 'description': desc_val or ''}
                    )
                    trans.name_local = name_val or ''
                    trans.description = desc_val or ''
                    trans.save()
            for lang_code, name_val, desc_val in extra_translations:
                country = _get_country_for_lang(lang_code)
                if country:
                    trans, _created = AccessRolesTranslation.objects.get_or_create(
                        access_role=custom_role, country=country,
                        defaults={'name_local': name_val or '', 'description': desc_val or ''}
                    )
                    trans.name_local = name_val or ''
                    trans.description = desc_val or ''
                    trans.save()

            logger.info(f"Created custom role {custom_role.id} for object {object_id}")
            role_data = {
                'id': custom_role.id,
                'name': custom_role.get_name() or '',
                'description': custom_role.get_description() or '',
                'color': custom_role.color,
                'is_object_specific': custom_role.is_object_specific
            }
            return JsonResponse({
                'status': 'success',
                'message': _('Custom role created successfully'),
                'role': role_data
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except ValidationError as e:
        logger.error(f"Validation error creating custom object role: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    except IntegrityError as e:
        logger.warning("IntegrityError creating custom object role: %s", e)
        # Only show "name already exists" if the error suggests a name/code uniqueness issue
        if 'unique' in str(e).lower() and ('name' in str(e).lower() or 'code' in str(e).lower() or 'accessrole' in str(e).lower()):
            return JsonResponse({
                'status': 'error',
                'message': _('Role with this name already exists in the system. Please choose a different name.')
            }, status=400)
        return JsonResponse({
            'status': 'error',
            'message': _('A database constraint was violated. Please try again or choose a different name.')
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating custom object role: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _('Error creating custom role')
        }, status=500)


@login_required
@require_POST
@ensure_csrf_cookie
def edit_custom_object_role(request):
    """Edit a custom role for a specific object. Accepts single name/description or role_name_<lang>/role_description_<lang>."""
    try:
        data = json.loads(request.body)
        role_id = data.get('role_id')
        object_id = data.get('object_id')
        form_langs = _get_object_form_languages()
        name_single = (data.get('name') or '').strip()
        description_single = (data.get('description') or '').strip()

        name_ua = (data.get('name_ua') or data.get('accessrole_name_ua') or data.get('role_name_ua') or data.get('role_name_uk', '')).strip()
        name_ru = (data.get('name_ru') or data.get('accessrole_name_ru') or data.get('role_name_ru', '')).strip()
        name_en = (data.get('name_en') or data.get('accessrole_name_en') or data.get('role_name_en', '')).strip()
        description_ua = (data.get('description_ua') or data.get('role_description_ua') or data.get('role_description_uk', '')).strip()
        description_ru = (data.get('description_ru') or data.get('role_description_ru', '')).strip()
        description_en = (data.get('description_en') or data.get('role_description_en', '')).strip()
        if name_single:
            name_en = name_en or name_single
            name_ua = name_ua or name_single
            name_ru = name_ru or name_single
        if description_single:
            description_en = description_en or description_single
            description_ua = description_ua or description_single
            description_ru = description_ru or description_single
        for lang_code, _lang_label in form_langs:
            leg = _normalize_lang_to_legacy_role(lang_code)
            if leg == 'ua':
                name_ua = name_ua or (data.get(f'role_name_{lang_code}', '') or '').strip()
                description_ua = description_ua or (data.get(f'role_description_{lang_code}', '') or '').strip()
            elif leg == 'ru':
                name_ru = name_ru or (data.get(f'role_name_{lang_code}', '') or '').strip()
                description_ru = description_ru or (data.get(f'role_description_{lang_code}', '') or '').strip()
            elif leg == 'en':
                name_en = name_en or (data.get(f'role_name_{lang_code}', '') or '').strip()
                description_en = description_en or (data.get(f'role_description_{lang_code}', '') or '').strip()
        extra_translations = [
            (lc, (data.get(f'role_name_{lc}', '') or '').strip(), (data.get(f'role_description_{lc}', '') or '').strip())
            for lc, _label in form_langs if _normalize_lang_to_legacy_role(lc) is None
        ]
        color = data.get('color', '#007bff')

        if not role_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Role ID is required')
            }, status=400)

        if not object_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Object ID is required')
            }, status=400)

        name_default = name_single or name_en or name_ua or name_ru
        if not name_default:
            return JsonResponse({
                'status': 'error',
                'message': _('Role name is required')
            }, status=400)

        try:
            custom_role = AccessRoles.objects.get(id=role_id)
        except AccessRoles.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': _('Role not found')
            }, status=404)

        if not custom_role.is_object_specific:
            return JsonResponse({
                'status': 'error',
                'message': _('Cannot edit system roles through this interface')
            }, status=403)

        if custom_role.created_for_object_id != int(object_id):
            return JsonResponse({
                'status': 'error',
                'message': _('This role does not belong to the specified object')
            }, status=403)

        existing_role = AccessRoles.objects.filter(
            system_id=custom_role.system_id,
            name=name_default
        ).exclude(id=role_id).exists()
        if existing_role:
            return JsonResponse({
                'status': 'error',
                'message': _('Role with this name already exists in the system')
            }, status=400)

        with transaction.atomic():
            custom_role.name = name_en or name_default
            custom_role.description = description_en or description_ua or description_ru
            custom_role.color = color
            custom_role.save()

            for lang_label, name_val, desc_val in [('ua', name_ua, description_ua), ('ru', name_ru, description_ru)]:
                country = _get_country_for_lang(lang_label)
                if country:
                    trans, _created = AccessRolesTranslation.objects.get_or_create(
                        access_role=custom_role, country=country,
                        defaults={'name_local': name_val or '', 'description': desc_val or ''}
                    )
                    trans.name_local = name_val or ''
                    trans.description = desc_val or ''
                    trans.save()
            for lang_code, name_val, desc_val in extra_translations:
                country = _get_country_for_lang(lang_code)
                if country:
                    trans, _created = AccessRolesTranslation.objects.get_or_create(
                        access_role=custom_role, country=country,
                        defaults={'name_local': name_val or '', 'description': desc_val or ''}
                    )
                    trans.name_local = name_val or ''
                    trans.description = desc_val or ''
                    trans.save()

            logger.info(f"Updated custom role {custom_role.id} for object {object_id}")
            role_data = {
                'id': custom_role.id,
                'name': custom_role.get_name() or '',
                'description': custom_role.get_description() or '',
                'color': custom_role.color,
                'is_object_specific': custom_role.is_object_specific
            }
            return JsonResponse({
                'status': 'success',
                'message': _('Custom role updated successfully'),
                'role': role_data
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating custom object role: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _('Error updating custom role')
        }, status=500)


@login_required
@require_POST
@ensure_csrf_cookie
def delete_custom_object_role(request):
    """Delete a custom object role"""
    try:
        data = json.loads(request.body)
        role_id = data.get('role_id')
        object_id = data.get('object_id')

        if not role_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Role ID is required')
            }, status=400)

        role = get_object_or_404(AccessRoles, id=role_id)

        # Check if role is object-specific and belongs to the object
        if not role.is_object_specific:
            return JsonResponse({
                'status': 'error',
                'message': _('Only object-specific roles can be deleted')
            }, status=400)

        if object_id and str(role.created_for_object_id) != str(object_id):
            return JsonResponse({
                'status': 'error',
                'message': _('Role does not belong to this object')
            }, status=400)

        # Check for dependencies and handle force delete
        force_delete = data.get('force_delete', False)
        assigned_objects = ObjectRoles.objects.filter(role=role, is_active=True)
        
        if assigned_objects.exists() and not force_delete:
            assigned_count = assigned_objects.count()
            return JsonResponse({
                'status': 'warning',
                'message': _('This role is currently assigned to %(count)d object(s). Do you want to remove it from all objects and delete it?') % {'count': assigned_count},
                'assigned_count': assigned_count,
                'requires_confirmation': True
            }, status=400)
        
        # If force delete is requested, remove all assignments first
        if force_delete and assigned_objects.exists():
            assigned_objects.update(is_active=False)
            logger.info(f"Deactivated {assigned_objects.count()} object role assignments for role {role.id}")

        if role.system_accesses.exists():
            return JsonResponse({
                'status': 'error',
                'message': _('Cannot delete role that is used in system accesses')
            }, status=400)

        role_name = role.get_name() or role.name or ''
        role.delete()

        logger.info(f"Deleted custom role '{role_name}' for object {object_id}")

        return JsonResponse({
            'status': 'success',
            'message': _('Role deleted successfully')
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except Exception as e:
        logger.error(f"Error deleting custom object role: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(['GET'])
def get_custom_object_roles(request, object_id):
    """Get custom roles for a specific object with role_names and role_descriptions by language."""
    try:
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        current_lang = (get_language() or 'en')[:2].lower()
        form_langs = _get_object_form_languages()

        custom_roles = AccessRoles.objects.filter(
            system=access_object.asset,
            is_object_specific=True,
            created_for_object_id=object_id,
            is_active=True
        ).prefetch_related('translations__country').order_by('order', 'name', 'code')

        roles_data = []
        for role in custom_roles:
            is_assigned = ObjectRoles.objects.filter(
                access_object=access_object,
                role=role,
                is_active=True
            ).exists()
            role_data = {
                'id': role.id,
                'name': role.get_name() or '',
                'description': role.get_description() or '',
                'color': role.color,
                'is_object_specific': role.is_object_specific,
                'created_for_object_id': role.created_for_object_id,
                'is_assigned': is_assigned,
                'can_edit': True,
                'can_delete': True
            }
            roles_data.append(role_data)
        
        return JsonResponse({
            'success': True,
            'object': {
                'id': access_object.id,
                'name': access_object.get_name() or ''
            },
            'roles': roles_data,
            'total_count': len(roles_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting custom object roles: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
# =================== Object Functions Management ===================
@login_required
@require_http_methods(['GET'])
def get_object_functions(request, object_id):
    """Get functions assigned to specific object"""
    try:
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        
        # Get current language
        current_lang = (get_language() or 'en')[:2].lower()
        
        # Get assigned functions with their actual function data
        object_functions = AccessObjectFunction.objects.filter(
            access_object=access_object,
            is_active=True
        ).select_related('function', 'function__parent').order_by('order')
        
        # Get the actual assigned functions for hierarchy building
        assigned_function_ids = set(obj_func.function.id for obj_func in object_functions)
        
        all_functions = AccessFunctionIS.objects.filter(
            Q(asset=access_object.asset, is_object_specific=False) |
            Q(asset=access_object.asset, is_object_specific=True, created_for_object=access_object),
            is_active=True
        ).select_related('parent').prefetch_related('translations__country').order_by('tree_id', 'lft')
        
        # Build hierarchical structure for assigned functions
        assigned_functions = []
        
        # Build hierarchy with depth-first approach (children after parent)
        def build_assigned_hierarchy():
            # Start with root functions that are assigned (no parent)
            root_functions = [func for func in all_functions if func.parent_id is None]
            root_functions = sorted(root_functions, key=lambda f: f.lft)  # Sort by MPTT left value
            
            # Function to add function and its assigned children safely
            def add_assigned_function_with_children(parent_func, level=0, max_depth=5):
                if level > max_depth:
                    return
                
                # Find the assignment record for this function
                assignment = None
                for obj_func in object_functions:
                    if obj_func.function.id == parent_func.id:
                        assignment = obj_func
                        break
                
                if assignment:
                    function_data = {
                        'id': parent_func.id,
                        'assignment_id': assignment.id,
                        'name': parent_func.get_name() or '',
                        'description': parent_func.get_description() or '',
                        'color': parent_func.color,
                        'order': assignment.order,
                        'level': level,
                        'parent_id': parent_func.parent_id,
                        'children_count': len([f for f in all_functions if f.parent_id == parent_func.id]),
                        'is_object_specific': parent_func.is_object_specific,
                        'function_type': 'custom' if parent_func.is_object_specific else 'system'
                    }
                    assigned_functions.append(function_data)
                
                # Find and add assigned children immediately after parent
                children = [f for f in all_functions if f.parent_id == parent_func.id]
                children = sorted(children, key=lambda f: f.lft)  # Sort by MPTT left value
                
                # Add each assigned child recursively
                for child in children:
                    add_assigned_function_with_children(child, level + 1, max_depth)
            
            # Add each assigned root function with its children
            for root_func in root_functions:
                add_assigned_function_with_children(root_func, 0)
        
        # Build the hierarchy
        build_assigned_hierarchy()
        
        return JsonResponse({
            'success': True,
            'object': {
                'id': access_object.id,
                'name': access_object.get_name() or ''
            },
            'functions': assigned_functions
        })
        
    except Exception as e:
        logger.error(f"Error getting object functions: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
@ensure_csrf_cookie
def add_object_functions(request):
    """Add functions to object"""
    try:
        object_id = request.POST.get('object_id')
        function_ids = request.POST.getlist('function_ids')
        
        if not object_id:
            return JsonResponse({'error': _('Object ID is required')}, status=400)
        
        if not function_ids:
            return JsonResponse({'error': _('At least one function must be selected')}, status=400)
        
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        
        added_functions = []
        skipped_functions = []
        
        with transaction.atomic():
            for function_id in function_ids:
                try:
                    function = AccessFunctionIS.objects.get(id=function_id)
                    
                    # Validate that function belongs to same system
                    if function.asset != access_object.asset:
                        logger.warning(f"Function {function_id} doesn't belong to same system as object {object_id}")
                        continue
                    
                    # Check if function is already assigned
                    if AccessObjectFunction.objects.filter(
                        access_object=access_object,
                        function=function
                    ).exists():
                        skipped_functions.append(function.get_name())
                        continue
                    
                    # Add function with children
                    assigned = AccessObjectFunction.assign_function_with_children(
                        access_object=access_object,
                        function=function,
                        user=request.user
                    )
                    
                    added_functions.extend([f.get_name() for f in assigned])
                    
                except AccessFunctionIS.DoesNotExist:
                    logger.warning(f"Function {function_id} not found")
                    continue
                except Exception as e:
                    logger.error(f"Error adding function {function_id}: {str(e)}")
                    continue
        
        message_parts = []
        if added_functions:
            message_parts.append(_('Added functions: {}').format(', '.join(added_functions)))
        if skipped_functions:
            message_parts.append(_('Skipped existing functions: {}').format(', '.join(skipped_functions)))
        
        return JsonResponse({
            'success': True,
            'message': '; '.join(message_parts) if message_parts else _('No functions were added'),
            'added_count': len(added_functions),
            'skipped_count': len(skipped_functions)
        })
        
    except Exception as e:
        logger.error(f"Error adding object functions: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def remove_object_function(request, object_id, function_id):
    """Remove function from object"""
    try:
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        function = get_object_or_404(AccessFunctionIS, id=function_id)
        
        # Remove function with children
        removed_functions = AccessObjectFunction.remove_function_with_children(
            access_object=access_object,
            function=function,
            user=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': _('Function removed successfully'),
            'removed_count': len(removed_functions)
        })
        
    except Exception as e:
        logger.error(f"Error removing object function: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(['GET'])
def get_object_available_functions(request, object_id):
    """Get available functions for assignment to object"""
    try:
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        environment = access_object.environment
        
        # Get current language
        current_lang = (get_language() or 'en')[:2].lower()
        
        # Get all functions for this system using tree ordering with custom order
        all_functions = AccessFunctionIS.objects.filter(
            Q(asset=access_object.asset, environment=environment, is_object_specific=False) |
            Q(asset=access_object.asset, environment=environment, is_object_specific=True, created_for_object=access_object),
            is_active=True
        ).select_related('parent').order_by('tree_id', 'order', 'lft')
        
        # Get already assigned function IDs
        assigned_function_ids = set(
            AccessObjectFunction.objects.filter(
                access_object=access_object,
                is_active=True
            ).values_list('function_id', flat=True)
        )
        
        # Build hierarchical structure safely
        available_functions = []
        
        # Create a mapping of functions by ID for quick lookup
        functions_by_id = {func.id: func for func in all_functions}
        
        # Build hierarchy with depth-first approach (children after parent)
        def build_hierarchy_safe():
            # Start with root functions (no parent)
            root_functions = [func for func in all_functions if func.parent_id is None]
            root_functions = sorted(root_functions, key=lambda f: (f.order, f.lft))  # Sort by order first, then MPTT left value
            
            # Iterative function to add function and its children safely
            def add_function_with_children_safe(parent_func, level=0, max_depth=5):
                if level > max_depth:
                    return
                
                # Add current function with localized names
                function_data = {
                    'id': parent_func.id,
                    'name': parent_func.get_name() or parent_func.name or '',
                    'description': parent_func.get_description() or '',
                    'localized_description': parent_func.get_description(current_lang) or parent_func.get_description('en') or '',
                    'color': parent_func.color,
                    'level': level,
                    'parent_id': parent_func.parent_id,
                    'order': parent_func.order,
                    'is_assigned': parent_func.id in assigned_function_ids,
                    'children_count': len([f for f in all_functions if f.parent_id == parent_func.id]),
                    'is_object_specific': parent_func.is_object_specific,
                    'function_type': 'custom' if parent_func.is_object_specific else 'system'
                }
                available_functions.append(function_data)
                
                # Find and add direct children immediately after parent
                children = [f for f in all_functions if f.parent_id == parent_func.id]
                children = sorted(children, key=lambda f: (f.order, f.lft))  # Sort by order first, then MPTT left value
                
                # Add each child recursively
                for child in children:
                    add_function_with_children_safe(child, level + 1, max_depth)
            
            # Add each root function with its children
            for root_func in root_functions:
                add_function_with_children_safe(root_func, 0)
        
        # Build the hierarchy
        build_hierarchy_safe()
        
        return JsonResponse({
            'success': True,
            'object': {
                'id': access_object.id,
                'name': access_object.get_name() or access_object.name or '',
                'object_name_ru': access_object.get_name('ru') or access_object.name or '',
                'object_name_en': access_object.get_name('en') or access_object.name or '',
                'localized_name': access_object.get_name(current_lang) or access_object.get_name('en'),
                'system_name': access_object.asset.name if access_object.asset else 'Unknown'
            },
            'functions': available_functions,
            'total_functions': len(available_functions),
            'assigned_count': len(assigned_function_ids),
            'current_language': current_lang
        })
        
    except Exception as e:
        logger.error(f"Error getting available functions: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
@ensure_csrf_cookie
def create_function(request):
    """Create new function"""
    try:
        asset_id = request.POST.get('asset_id')
        parent_id = request.POST.get('parent_id')
        
        if not asset_id:
            return JsonResponse({'error': _('Asset ID is required')}, status=400)
        
        asset = get_object_or_404(InformationAsset, id=asset_id)
        
        # Validate parent if provided
        parent = None
        if parent_id:
            parent = get_object_or_404(AccessFunctionIS, id=parent_id, asset=asset)
            
            # Check depth limit (max 3 levels)
            if parent.level >= 2:
                return JsonResponse({
                    'error': _('Maximum function hierarchy depth (3 levels) exceeded')
                }, status=400)
        
        function_data = {
            'asset': asset,
            'parent': parent,
            'accesfunct_name_ua': request.POST.get('accesfunct_name_ua'),
            'accesfunct_name_ru': request.POST.get('accesfunct_name_ru', ''),
            'accesfunct_name_en': request.POST.get('accesfunct_name_en', ''),
            'description_ua': request.POST.get('description_ua', ''),
            'description_ru': request.POST.get('description_ru', ''),
            'description_en': request.POST.get('description_en', ''),
            'color': request.POST.get('color', '#000000'),
            'order': int(request.POST.get('order', 0))
        }
        
        # Validate required fields
        if not function_data['accesfunct_name_ua']:
            return JsonResponse({'error': _('Function name (UA) is required')}, status=400)
        
        # Check for duplicate names in same asset
        if AccessFunctionIS.objects.filter(
            asset=asset,
            accesfunct_name_ua=function_data['accesfunct_name_ua']
        ).exists():
            return JsonResponse({
                'error': _('Function with this name already exists in this system')
            }, status=400)
        
        function = AccessFunctionIS.objects.create(**function_data)
        
        return JsonResponse({
            'success': True,
            'function': {
                'id': function.id,
                'name': function.get_name() or function.name or '',
                'level': function.level
            },
            'message': _('Function created successfully')
        })
        
    except Exception as e:
        logger.error(f"Error creating function: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(['GET', 'POST', 'DELETE'])
def function_management_detail(request, function_id):
    """Get, update or delete function"""
    try:
        function = get_object_or_404(AccessFunctionIS, id=function_id)
        
        if request.method == 'GET':
            return JsonResponse({
                'success': True,
                'function': {
                    'id': function.id,
                    'name': function.get_name() or function.name or '',
                    'description': function.get_description() or '',
                    'color': function.color,
                    'order': function.order,
                    'parent_id': function.parent_id,
                    'level': function.level,
                    'children_count': function.get_children().count(),
                    'usage_count': function.object_assignments.count()
                }
            })
        
        elif request.method == 'POST':
            function.name = request.POST.get('accesfunct_name_en') or request.POST.get('function_name_en') or request.POST.get('accesfunct_name_ua', function.name)
            function.description = request.POST.get('description_en') or request.POST.get('function_description_en', function.description)
            function.color = request.POST.get('color', function.color)
            function.order = int(request.POST.get('order', function.order))
            if not function.name:
                return JsonResponse({'error': _('Function name is required')}, status=400)
            if AccessFunctionIS.objects.filter(
                asset=function.asset,
                name=function.name,
                environment=function.environment
            ).exclude(id=function.id).exists():
                return JsonResponse({
                    'error': _('Function with this name already exists in this system')
                }, status=400)
            function.save()
            
            return JsonResponse({
                'success': True,
                'message': _('Function updated successfully')
            })
        
        elif request.method == 'DELETE':
            # Check if function can be deleted
            if function.object_assignments.exists():
                return JsonResponse({
                    'error': _('Cannot delete function that is assigned to objects')
                }, status=400)
            
            if function.get_children().exists():
                return JsonResponse({
                    'error': _('Cannot delete function that has child functions')
                }, status=400)
            
            function_name = function.get_name()
            function.delete()
            
            return JsonResponse({
                'success': True,
                'message': _('Function "{}" deleted successfully').format(function_name)
            })
        
    except Exception as e:
        logger.error(f"Error in function management detail: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_role_functions(request, role_id):
    """Get functions assigned to a role"""
    try:
        role = get_object_or_404(AccessRoles, id=role_id)
        functions = role.functions.filter(is_active=True).values('id', 'name')
        return JsonResponse({'functions': list(functions)})
    except Exception as e:
        logger.error(f"Error getting role functions: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_POST
def update_object_functions_order(request, object_id):
    """Update the order of functions assigned to object"""
    try:
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        function_orders = request.POST.get('function_orders')
        
        if not function_orders:
            return JsonResponse({'error': _('Function orders data is required')}, status=400)
        
        try:
            orders_data = json.loads(function_orders)
        except json.JSONDecodeError:
            return JsonResponse({'error': _('Invalid JSON data')}, status=400)
        
        with transaction.atomic():
            for item in orders_data:
                function_id = item.get('function_id')
                order = item.get('order', 0)
                
                AccessObjectFunction.objects.filter(
                    access_object=access_object,
                    function_id=function_id
                ).update(order=order)
        
        return JsonResponse({
            'success': True,
            'message': _('Function order updated successfully')
        })
        
    except Exception as e:
        logger.error(f"Error updating function order: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# =================== Functions Management (CRUD) ===================

@login_required
@require_http_methods(['GET'])
def get_functions_tree(request):
    """Get hierarchical tree of functions for specific system"""
    try:
        asset_id = request.GET.get('asset_id')
        if not asset_id:
            return JsonResponse({'error': _('Asset ID is required')}, status=400)
        
        asset = get_object_or_404(InformationAsset, id=asset_id)
        
        # Get all functions for this asset
        functions = AccessFunctionIS.objects.filter(asset=asset, is_active=True).order_by('tree_id', 'lft')
        
        def format_function_tree(func, level=0, max_depth=3):
            children = []
            if level < max_depth:
                # Get direct children only (not all descendants)
                direct_children = functions.filter(parent=func)
                for child in direct_children:
                    children.append(format_function_tree(child, level + 1, max_depth))
            
            return {
                'id': func.id,
                'name': func.get_name() or func.name or '',
                'description': func.get_description() or '',
                'color': func.color,
                'order': func.order,
                'level': level,
                'parent_id': func.parent_id,
                'children': children,
                'children_count': len(children),
                'usage_count': func.object_assignments.count()
            }
        
        # Build tree structure
        root_functions = functions.filter(parent=None)
        tree = [format_function_tree(func, 0) for func in root_functions]
        
        return JsonResponse({
            'success': True,
            'asset': {
                'id': asset.id,
                'name': asset.name
            },
            'functions_tree': tree,
            'total_functions': functions.count()
        })
        
    except Exception as e:
        logger.error(f"Error getting functions tree: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# ================ CUSTOM OBJECT FUNCTIONS MANAGEMENT ================

@login_required
@require_POST
@ensure_csrf_cookie
def save_custom_object_function(request):
    """Create a custom function for a specific object. Accepts single name/description or function_name_<lang>, function_description_<lang>."""
    try:
        data = json.loads(request.body)
        object_id = data.get('object_id')
        form_langs = _get_object_form_languages()
        name_single = (data.get('name') or '').strip()
        description_single = (data.get('description') or '').strip()
        name_ua = (data.get('name_ua') or data.get('accesfunct_name_ua') or data.get('function_name_ua') or data.get('function_name_uk', '')).strip()
        name_ru = (data.get('name_ru') or data.get('accesfunct_name_ru') or data.get('function_name_ru', '')).strip()
        name_en = (data.get('name_en') or data.get('accesfunct_name_en') or data.get('function_name_en', '')).strip()
        description_ua = (data.get('description_ua') or data.get('function_description_ua') or data.get('function_description_uk', '')).strip()
        description_ru = (data.get('description_ru') or data.get('function_description_ru', '')).strip()
        description_en = (data.get('description_en') or data.get('function_description_en', '')).strip()
        if name_single:
            name_en = name_en or name_single
            name_ua = name_ua or name_single
            name_ru = name_ru or name_single
        if description_single:
            description_en = description_en or description_single
            description_ua = description_ua or description_single
            description_ru = description_ru or description_single
        for lang_code, _label in form_langs:
            leg = _normalize_lang_to_legacy_role(lang_code)
            if leg == 'ua':
                name_ua = name_ua or (data.get(f'function_name_{lang_code}', '') or '').strip()
                description_ua = description_ua or (data.get(f'function_description_{lang_code}', '') or '').strip()
            elif leg == 'ru':
                name_ru = name_ru or (data.get(f'function_name_{lang_code}', '') or '').strip()
                description_ru = description_ru or (data.get(f'function_description_{lang_code}', '') or '').strip()
            elif leg == 'en':
                name_en = name_en or (data.get(f'function_name_{lang_code}', '') or '').strip()
                description_en = description_en or (data.get(f'function_description_{lang_code}', '') or '').strip()
        extra_translations = [
            (lc, (data.get(f'function_name_{lc}', '') or '').strip(), (data.get(f'function_description_{lc}', '') or '').strip())
            for lc, _label in form_langs if _normalize_lang_to_legacy_role(lc) is None
        ]
        color = data.get('color', '#007bff')
        parent_id = data.get('parent_id')

        logger.info(f"Creating custom function for object_id: {object_id}")

        name_default = name_single or name_en or name_ua or name_ru
        if not object_id or not name_default:
            return JsonResponse({
                'status': 'error',
                'message': _('Object ID and name are required')
            }, status=400)

        # Get the object and its system
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        system = access_object.asset

        # Validate parent function if provided
        parent_function = None
        if parent_id:
            try:
                parent_function = AccessFunctionIS.objects.filter(
                    Q(is_object_specific=False) | Q(created_for_object=access_object),
                    id=parent_id, 
                    asset=system
                ).first()
                
                if not parent_function:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Parent function not found or not accessible for this object'
                    }, status=400)
                    
                # Check depth limit (max 3 levels)
                if parent_function.level >= 2:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Maximum function hierarchy depth (3 levels) exceeded'
                    }, status=400)
            except AccessFunctionIS.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Parent function not found or not accessible for this object'
                }, status=400)

        # Block only if a default (system-level) function already has this name; allow custom functions to reuse names
        name_default = name_single or name_en or name_ua or name_ru
        existing_default_function = AccessFunctionIS.objects.filter(
            asset=system,
            environment=access_object.environment,
            name=name_default,
            is_object_specific=False,
            created_for_object__isnull=True,
        ).first()
        if existing_default_function:
            logger.warning(
                "Blocking custom function creation: default function with same name exists "
                "(function_id=%s, name=%r, asset_id=%s, environment=%s)",
                existing_default_function.id, existing_default_function.name,
                system.id, access_object.environment,
            )
            return JsonResponse({
                'status': 'error',
                'message': _('Function with this name already exists in the system. Please choose a different name.')
            }, status=400)

        # Create the custom function with enhanced validation
        with transaction.atomic():

            max_order = AccessFunctionIS.objects.filter(
                asset=system,
                environment=access_object.environment
            ).aggregate(max_order=models.Max('order'))['max_order'] or 0

            logger.info(
                "Creating custom function: object_id=%s, name=%r, asset_id=%s, environment=%s",
                object_id, name_default, system.id, access_object.environment,
            )
            custom_function = AccessFunctionIS.objects.create(
                asset=system,
                environment=access_object.environment,
                parent=parent_function,
                name=name_en or name_default,
                description=description_en or description_ua or description_ru,
                color=color,
                order=max_order + 1,
                is_object_specific=True,
                created_for_object=access_object
            )
            for lang_label, name_val, desc_val in [('ua', name_ua, description_ua), ('ru', name_ru, description_ru)]:
                country = _get_country_for_lang(lang_label)
                if country:
                    trans, _created = AccessFunctionISTranslation.objects.get_or_create(
                        access_function=custom_function, country=country,
                        defaults={'name_local': name_val or '', 'description': desc_val or ''}
                    )
                    trans.name_local = name_val or ''
                    trans.description = desc_val or ''
                    trans.save()
            for lang_code, name_val, desc_val in extra_translations:
                country = _get_country_for_lang(lang_code)
                if country:
                    trans, _created = AccessFunctionISTranslation.objects.get_or_create(
                        access_function=custom_function, country=country,
                        defaults={'name_local': name_val or '', 'description': desc_val or ''}
                    )
                    trans.name_local = name_val or ''
                    trans.description = desc_val or ''
                    trans.save()

            logger.info("Created custom function %s for object %s", custom_function.id, object_id)
            return JsonResponse({
                'status': 'success',
                'message': _('Custom function created successfully'),
                'function': {
                    'id': custom_function.id,
                    'name': custom_function.get_name() or '',
                    'description': custom_function.get_description() or '',
                    'color': custom_function.color,
                    'is_object_specific': custom_function.is_object_specific,
                    'created_for_object_id': custom_function.created_for_object_id,
                    'parent_id': custom_function.parent_id,
                    'level': custom_function.level
                }
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except IntegrityError as e:
        logger.warning("IntegrityError creating custom object function: %s", e)
        if 'unique' in str(e).lower() and ('name' in str(e).lower() or 'code' in str(e).lower() or 'accessfunction' in str(e).lower() or 'accesfunct' in str(e).lower()):
            return JsonResponse({
                'status': 'error',
                'message': _('Function with this name already exists in the system. Please choose a different name.')
            }, status=400)
        return JsonResponse({
            'status': 'error',
            'message': _('A database constraint was violated. Please try again or choose a different name.')
        }, status=400)
    except Exception as e:
        logger.error("Error creating custom function: %s", e)
        if 'Duplicate entry' in str(e) or 'unique' in str(e).lower():
            return JsonResponse({
                'status': 'error',
                'message': _('Function with this name already exists in the system. Please choose a different name.')
            }, status=400)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
def edit_custom_object_function(request):
    """Edit a custom function for a specific object. Accepts single name/description or function_name_<lang>, function_description_<lang>."""
    try:
        data = json.loads(request.body)
        function_id = data.get('function_id')
        object_id = data.get('object_id')
        form_langs = _get_object_form_languages()
        name_single = (data.get('name') or '').strip()
        description_single = (data.get('description') or '').strip()
        name_ua = (data.get('name_ua') or data.get('accesfunct_name_ua') or data.get('function_name_ua') or data.get('function_name_uk', '')).strip()
        name_ru = (data.get('name_ru') or data.get('accesfunct_name_ru') or data.get('function_name_ru', '')).strip()
        name_en = (data.get('name_en') or data.get('accesfunct_name_en') or data.get('function_name_en', '')).strip()
        description_ua = (data.get('description_ua') or data.get('function_description_ua') or data.get('function_description_uk', '')).strip()
        description_ru = (data.get('description_ru') or data.get('function_description_ru', '')).strip()
        description_en = (data.get('description_en') or data.get('function_description_en', '')).strip()
        if name_single:
            name_en = name_en or name_single
            name_ua = name_ua or name_single
            name_ru = name_ru or name_single
        if description_single:
            description_en = description_en or description_single
            description_ua = description_ua or description_single
            description_ru = description_ru or description_single
        for lang_code, _label in form_langs:
            leg = _normalize_lang_to_legacy_role(lang_code)
            if leg == 'ua':
                name_ua = name_ua or (data.get(f'function_name_{lang_code}', '') or '').strip()
                description_ua = description_ua or (data.get(f'function_description_{lang_code}', '') or '').strip()
            elif leg == 'ru':
                name_ru = name_ru or (data.get(f'function_name_{lang_code}', '') or '').strip()
                description_ru = description_ru or (data.get(f'function_description_{lang_code}', '') or '').strip()
            elif leg == 'en':
                name_en = name_en or (data.get(f'function_name_{lang_code}', '') or '').strip()
                description_en = description_en or (data.get(f'function_description_{lang_code}', '') or '').strip()
        extra_translations = [
            (lc, (data.get(f'function_name_{lc}', '') or '').strip(), (data.get(f'function_description_{lc}', '') or '').strip())
            for lc, _label in form_langs if _normalize_lang_to_legacy_role(lc) is None
        ]
        color = data.get('color', '#007bff')
        parent_id = data.get('parent_id')

        logger.info(f"Editing custom function {function_id} for object_id: {object_id}")

        name_default = name_single or name_en or name_ua or name_ru
        if not function_id or not object_id or not name_default:
            return JsonResponse({
                'status': 'error',
                'message': _('Function ID, Object ID and name are required')
            }, status=400)

        # Get the object and its system
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        system = access_object.asset

        # Get the custom function
        try:
            custom_function = AccessFunctionIS.objects.get(
                id=function_id,
                asset=system,
                is_object_specific=True,
                created_for_object=access_object
            )
        except AccessFunctionIS.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Custom function not found or you do not have permission to edit it'
            }, status=404)

        # Validate parent function if provided
        parent_function = None
        if parent_id:
            try:
                parent_function = AccessFunctionIS.objects.filter(
                    Q(is_object_specific=False) | Q(created_for_object=access_object),
                    id=parent_id, 
                    asset=system
                ).first()
                
                if not parent_function:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Parent function not found or not accessible for this object'
                    }, status=400)
                
                # Check that we're not creating a circular reference
                if parent_function.id == custom_function.id:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Function cannot be its own parent'
                    }, status=400)
                
                # Check depth limit (max 3 levels)
                if parent_function.level >= 2:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Maximum function hierarchy depth (3 levels) exceeded'
                    }, status=400)
                    
                # Check that the parent is not a descendant of this function
                if custom_function.get_descendants().filter(id=parent_function.id).exists():
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Cannot move function under its own descendant'
                    }, status=400)
                    
            except AccessFunctionIS.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Parent function not found or not accessible for this object'
                }, status=400)

        # Update the custom function
        with transaction.atomic():
            # Check for duplicate names (excluding current function)
            name_default = name_en or name_ua or name_ru
            existing_function = AccessFunctionIS.objects.filter(
                Q(is_object_specific=False) | Q(created_for_object=access_object),
                asset=system,
                name=name_default
            ).exclude(id=function_id).first()

            if existing_function:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Function with name "{name_default}" already exists for this system/object. Please choose a different name.'
                }, status=400)

            if parent_id and (not custom_function.parent or custom_function.parent.id != int(parent_id)):
                custom_function.move_to(parent_function)
            elif not parent_id and custom_function.parent:
                custom_function.move_to(None)

            custom_function.name = name_en or name_default
            custom_function.description = description_en or description_ua or description_ru
            custom_function.color = color
            custom_function.save()

            for lang_label, name_val, desc_val in [('ua', name_ua, description_ua), ('ru', name_ru, description_ru)]:
                country = _get_country_for_lang(lang_label)
                if country:
                    trans, _ = AccessFunctionISTranslation.objects.get_or_create(
                        access_function=custom_function, country=country,
                        defaults={'name_local': name_val or '', 'description': desc_val or ''}
                    )
                    trans.name_local = name_val or ''
                    trans.description = desc_val or ''
                    trans.save()
            for lang_code, name_val, desc_val in extra_translations:
                country = _get_country_for_lang(lang_code)
                if country:
                    trans, _ = AccessFunctionISTranslation.objects.get_or_create(
                        access_function=custom_function, country=country,
                        defaults={'name_local': name_val or '', 'description': desc_val or ''}
                    )
                    trans.name_local = name_val or ''
                    trans.description = desc_val or ''
                    trans.save()

            logger.info(f"Updated custom function {custom_function.id} for object {object_id}")
            return JsonResponse({
                'status': 'success',
                'message': _('Custom function updated successfully'),
                'function': {
                    'id': custom_function.id,
                    'name': custom_function.get_name() or '',
                    'description': custom_function.get_description() or '',
                    'color': custom_function.color,
                    'is_object_specific': custom_function.is_object_specific,
                    'created_for_object_id': custom_function.created_for_object_id,
                    'parent_id': custom_function.parent_id,
                    'level': custom_function.level
                }
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except IntegrityError as e:
        # Handle database constraint violations
        if 'Duplicate entry' in str(e) and 'accesfunct_name' in str(e):
            return JsonResponse({
                'status': 'error',
                'message': f'Function with this name already exists for this system. Please choose a different name.'
            }, status=400)
        else:
            logger.error(f"Database integrity error updating custom function: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Database constraint violation. Please try again.'
            }, status=400)
    except Exception as e:
        logger.error(f"Error updating custom function: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_POST
@ensure_csrf_cookie
def delete_custom_object_function(request):
    """Delete a custom function for a specific object"""
    try:
        logger.info(f"delete_custom_object_function called with method: {request.method}")
        logger.info(f"Request body: {request.body}")
        
        # Parse JSON data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data in request'
            }, status=400)
            
        function_id = data.get('function_id')
        object_id = data.get('object_id')

        logger.info(f"Deleting custom function {function_id} for object_id: {object_id}")

        # Validate required fields
        if not function_id or not object_id:
            logger.warning(f"Missing required fields: function_id={function_id}, object_id={object_id}")
            return JsonResponse({
                'status': 'error',
                'message': 'Function ID and Object ID are required'
            }, status=400)

        # Validate that the IDs are integers
        try:
            function_id = int(function_id)
            object_id = int(object_id)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid ID format: function_id={function_id}, object_id={object_id}, error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Function ID and Object ID must be valid integers'
            }, status=400)

        # Get the object and its system
        try:
            access_object = get_object_or_404(AccessObjectIS, id=object_id)
            system = access_object.asset
            logger.info(f"Found access object: {access_object} for system: {system}")
        except AccessObjectIS.DoesNotExist:
            logger.error(f"Access object not found: id={object_id}")
            return JsonResponse({
                'status': 'error',
                'message': 'Access object not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error getting access object: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error retrieving access object: {str(e)}'
            }, status=500)

        # Get the custom function with additional validation
        try:
            custom_function = AccessFunctionIS.objects.get(
                id=function_id,
                asset=system,
                is_object_specific=True,
                created_for_object=access_object
            )
            logger.info(f"Found custom function: {custom_function}")
        except AccessFunctionIS.DoesNotExist:
            logger.warning(f"Custom function not found: id={function_id}, asset={system}, object={access_object}")
            return JsonResponse({
                'status': 'error',
                'message': 'Custom function not found or you do not have permission to delete it'
            }, status=404)
        except Exception as e:
            logger.error(f"Error retrieving custom function: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error retrieving custom function: {str(e)}'
            }, status=500)

        # Additional validation to ensure this is truly a custom function
        if not custom_function.is_object_specific or custom_function.created_for_object != access_object:
            logger.error(f"Function {function_id} is not a custom function for object {object_id}")
            return JsonResponse({
                'status': 'error',
                'message': 'This function is not a custom function for the specified object'
            }, status=400)

        # Check if function has children
        try:
            # Use direct database query instead of MPTT get_children() to avoid recursion issues
            children_count = AccessFunctionIS.objects.filter(parent_id=custom_function.id).count()
            logger.info(f"Function has {children_count} children")
            if children_count > 0:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Cannot delete function with {children_count} child function(s). Please delete child functions first.'
                }, status=400)
        except Exception as e:
            logger.error(f"Error checking children: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error checking function children: {str(e)}'
            }, status=500)

        # Check if function is assigned to any objects
        try:
            assignments_count = AccessObjectFunction.objects.filter(function=custom_function).count()
            logger.info(f"Function has {assignments_count} assignments")
        except Exception as e:
            logger.error(f"Error checking assignments: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error checking function assignments: {str(e)}'
            }, status=500)
        
        # Delete the function and its assignments
        try:
            with transaction.atomic():
                # Remove all assignments first
                if assignments_count > 0:
                    deleted_assignments = AccessObjectFunction.objects.filter(function=custom_function).delete()
                    logger.info(f"Removed {assignments_count} function assignments before deletion: {deleted_assignments}")

                # Store function name before deletion
                function_name = custom_function.get_name() or custom_function.name or ''
                
                # Delete the custom function
                custom_function.delete()
                
                # Rebuild MPTT tree for the asset to prevent future corruption
                try:
                    AccessFunctionIS.objects.rebuild()
                    logger.info("MPTT tree rebuilt successfully after deletion")
                except Exception as rebuild_error:
                    logger.warning(f"Failed to rebuild MPTT tree: {str(rebuild_error)}")
                    # Don't fail the deletion if tree rebuild fails

                logger.info(f"Successfully deleted custom function {function_id} '{function_name}' for object {object_id}")

                return JsonResponse({
                    'status': 'success',
                    'message': f'Custom function "{function_name}" deleted successfully',
                    'removed_assignments': assignments_count
                })
                
        except Exception as e:
            logger.error(f"Error during deletion transaction: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Error deleting function: {str(e)}'
            }, status=500)

    except Exception as e:
        logger.error(f"Unexpected error in delete_custom_object_function: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Unexpected error: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(['GET'])
def get_custom_object_functions(request, object_id):
    """Get custom functions for a specific object"""
    try:
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        
        # Get current language
        current_lang = (get_language() or 'en')[:2].lower()
        
        # Get custom functions for this object - convert to list for easier processing
        custom_functions_qs = AccessFunctionIS.objects.filter(
            asset=access_object.asset,
            is_active=True,
            is_object_specific=True,
            created_for_object=access_object
        ).select_related('parent').order_by('tree_id', 'lft')
        
        custom_functions = list(custom_functions_qs)
        
        # Build hierarchical structure
        functions_data = []
        
        def build_hierarchy_for_custom():
            # Create a set of custom function IDs for quick lookup
            custom_function_ids = {func.id for func in custom_functions}
            
            # Start with root functions that are custom (no parent or parent is not a custom function for this object)
            root_functions = [func for func in custom_functions if func.parent_id is None or 
                            func.parent_id not in custom_function_ids]
            root_functions = sorted(root_functions, key=lambda f: f.lft)  # Sort by MPTT left value
            
            # Function to add function and its custom children safely
            def add_custom_function_with_children(parent_func, level=0, max_depth=5):
                if level > max_depth:
                    return
                
                # Check assignment status
                is_assigned = AccessObjectFunction.objects.filter(
                    access_object=access_object,
                    function=parent_func,
                    is_active=True
                ).exists()
                
                function_data = {
                    'id': parent_func.id,
                    'name': parent_func.get_name() or parent_func.name or '',
                    'description': parent_func.get_description() or '',
                    'localized_description': parent_func.get_description(current_lang) or parent_func.get_description('en') or '',
                    'color': parent_func.color,
                    'level': level,
                    'parent_id': parent_func.parent_id,
                    'children_count': len([f for f in custom_functions if f.parent_id == parent_func.id]),
                    'is_object_specific': parent_func.is_object_specific,
                    'is_assigned': is_assigned,
                    'can_edit': True,  # Custom functions can always be edited by object owner
                    'can_delete': len([f for f in custom_functions if f.parent_id == parent_func.id]) == 0  # Can delete if no children
                }
                functions_data.append(function_data)
                
                # Find and add custom children immediately after parent
                children = [f for f in custom_functions if f.parent_id == parent_func.id]
                children = sorted(children, key=lambda f: f.lft)  # Sort by MPTT left value
                
                # Add each custom child recursively
                for child in children:
                    add_custom_function_with_children(child, level + 1, max_depth)
            
            # Add each custom root function with its children
            for root_func in root_functions:
                add_custom_function_with_children(root_func, 0)
        
        # Build the hierarchy
        build_hierarchy_for_custom()
        
        return JsonResponse({
            'success': True,
            'object': {
                'id': access_object.id,
                'name': access_object.get_name() or access_object.name or '',
                'object_name_ru': access_object.get_name('ru') or access_object.name or '',
                'object_name_en': access_object.get_name('en') or access_object.name or '',
                'localized_name': access_object.get_name(current_lang) or access_object.get_name('en'),
                'system_name': access_object.asset.name if access_object.asset else 'Unknown'
            },
            'functions': functions_data,
            'total_functions': len(functions_data),
            'current_language': current_lang
        })
        
    except Exception as e:
        logger.error(f"Error getting custom object functions: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

def rebuild_mptt_trees():
    """
    Helper function to rebuild MPTT trees and fix corruption
    """
    try:
        logger.info("Starting MPTT tree rebuild for AccessFunctionIS")
        AccessFunctionIS.objects.rebuild()
        logger.info("MPTT tree rebuilt successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to rebuild MPTT tree: {str(e)}", exc_info=True)
        return False

@login_required
@require_POST
@ensure_csrf_cookie
def update_functions_order(request):
    """Update the order of functions via drag-and-drop"""
    try:
        data = json.loads(request.body)
        function_orders = data.get('function_orders', [])
        
        if not function_orders:
            return JsonResponse({
                'status': 'error',
                'message': 'No function orders provided'
            }, status=400)
        
        logger.info(f"Updating order for {len(function_orders)} functions")
        
        with transaction.atomic():
            for item in function_orders:
                function_id = item.get('id')
                new_order = item.get('order')
                
                if function_id is None or new_order is None:
                    continue
                    
                try:
                    function = AccessFunctionIS.objects.get(id=function_id)
                    function.order = new_order
                    function.save(update_fields=['order'])
                    logger.info(f"Updated function {function_id} order to {new_order}")
                except AccessFunctionIS.DoesNotExist:
                    logger.warning(f"Function {function_id} not found")
                    continue
                except Exception as e:
                    logger.error(f"Error updating function {function_id}: {str(e)}")
                    continue
            
            # Rebuild MPTT tree to ensure proper ordering
            try:
                AccessFunctionIS.objects.rebuild()
                logger.info("MPTT tree rebuilt after order update")
            except Exception as e:
                logger.warning(f"Failed to rebuild MPTT tree after order update: {str(e)}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Updated order for {len(function_orders)} functions'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating functions order: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error updating functions order: {str(e)}'
        }, status=500)

@login_required
@require_POST
@ensure_csrf_cookie
def update_assigned_functions_order(request):
    """Update the order of assigned functions via drag-and-drop"""
    try:
        data = json.loads(request.body)
        function_orders = data.get('function_orders', [])
        object_id = data.get('object_id')
        
        if not function_orders:
            return JsonResponse({
                'status': 'error',
                'message': 'No function orders provided'
            }, status=400)
            
        if not object_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Object ID is required'
            }, status=400)
        
        logger.info(f"Updating assigned order for {len(function_orders)} functions for object {object_id}")
        
        # Verify that the object exists
        try:
            access_object = AccessObjectIS.objects.get(id=object_id)
        except AccessObjectIS.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Object not found'
            }, status=404)
        
        with transaction.atomic():
            for item in function_orders:
                function_id = item.get('id')
                new_order = item.get('order')
                
                if function_id is None or new_order is None:
                    continue
                    
                try:
                    # Update the order in AccessObjectFunction table
                    assignment = AccessObjectFunction.objects.get(
                        access_object=access_object,
                        function_id=function_id,
                        is_active=True
                    )
                    assignment.order = new_order
                    assignment.save(update_fields=['order'])
                    logger.info(f"Updated assigned function {function_id} order to {new_order}")
                except AccessObjectFunction.DoesNotExist:
                    logger.warning(f"Assignment not found for function {function_id} and object {object_id}")
                    continue
                except Exception as e:
                    logger.error(f"Error updating assigned function {function_id}: {str(e)}")
                    continue
        
        return JsonResponse({
            'status': 'success',
            'message': f'Updated order for {len(function_orders)} assigned functions'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating assigned functions order: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error updating assigned functions order: {str(e)}'
        }, status=500)

# ================ OBJECT ROLES & FUNCTIONS MANAGEMENT ================

@login_required
@require_http_methods(['GET'])
def get_object_roles_functions(request, object_id):
    """
    API endpoint для отримання ролей та їх функцій для конкретного об'єкта
    """
    try:
        # Перевіряємо, чи існує об'єкт
        obj = get_object_or_404(AccessObjectIS, id=object_id)
        
        # Отримуємо ролі об'єкта з функціями
        object_roles = ObjectRoles.objects.filter(access_object=obj).select_related('role')
        
        # Створюємо структуру даних для ролей та їх функцій
        roles_functions_data = []
        
        def build_function_hierarchy(functions, parent=None, level=0, max_depth=3):
            """Build function hierarchy with single name/description (multilingual removed)."""
            hierarchy = []
            parent_functions = [f for f in functions if f.parent_id == parent]
            for func in parent_functions:
                function_data = {
                    'id': func.id,
                    'name': func.get_name() or '',
                    'description': func.get_description() or '',
                    'color': func.color,
                    'function_type': 'custom' if func.is_object_specific else 'default',
                    'level': level,
                    'children': []
                }
                if level < max_depth:
                    function_data['children'] = build_function_hierarchy(
                        functions, func.id, level + 1, max_depth
                    )
                hierarchy.append(function_data)
            return hierarchy

        for object_role in object_roles:
            role = object_role.role

            object_role_functions = ObjectRoleFunctions.objects.filter(
                object_role=object_role,
                is_active=True
            ).select_related('function')

            if not object_role_functions.exists():
                global_functions = role.functions.all()
                object_functions = AccessObjectFunction.objects.filter(
                    access_object=obj,
                    function__in=global_functions,
                    is_active=True
                ).values_list('function', flat=True).distinct()
                for function_id in object_functions:
                    try:
                        ObjectRoleFunctions.objects.get_or_create(
                            object_role=object_role,
                            function_id=function_id,
                            defaults={'is_active': True}
                        )
                    except (IntegrityError, ValidationError):
                        # Race or duplicate: record already exists, refetch and use current state
                        break
                object_role_functions = ObjectRoleFunctions.objects.filter(
                    object_role=object_role,
                    is_active=True
                ).select_related('function')

            functions_list = [obj_role_func.function for obj_role_func in object_role_functions]
            functions_hierarchy = build_function_hierarchy(functions_list)
            is_custom = role.is_object_specific and role.created_for_object == obj

            roles_functions_data.append({
                'role': {
                    'id': role.id,
                    'name': role.get_name() or '',
                    'description': role.get_description() or '',
                    'color': role.color
                },
                'functions': functions_hierarchy,
                'total_functions': len(functions_list),
                'is_custom': is_custom
            })

        return JsonResponse({
            'success': True,
            'data': roles_functions_data
        })

    except AccessObjectIS.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Object not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error in get_object_roles_functions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
def get_object_role_functions(request, object_id, role_id):
    """
    API endpoint для отримання функцій конкретної ролі для конкретного об'єкта
    """
    try:
        # Перевіряємо, чи існують об'єкт та роль
        obj = get_object_or_404(AccessObjectIS, id=object_id)
        role = get_object_or_404(AccessRoles, id=role_id)
        
        # Перевіряємо, чи призначена роль цьому об'єкту
        object_role = ObjectRoles.objects.filter(access_object=obj, role=role).first()
        if not object_role:
            return JsonResponse({
                'success': False,
                'error': _('Role is not assigned to this object')
            }, status=400)

        # Отримуємо об'єкт-специфічні функції для цієї ролі
        object_role_functions = ObjectRoleFunctions.objects.filter(
            object_role=object_role,
            is_active=True
        ).select_related('function')
        
        # Якщо немає об'єкт-специфічних функцій, ініціалізуємо їх з глобальних зв'язків
        if not object_role_functions.exists():
            # Отримуємо глобальні функції для цієї ролі
            global_functions = role.functions.all()
            
            # Створюємо об'єкт-специфічні записи для кожної глобальної функції,
            # але тільки якщо функція призначена об'єкту
            object_functions = AccessObjectFunction.objects.filter(
                access_object=obj,
                function__in=global_functions,
                is_active=True
            ).values_list('function', flat=True)
            
            # Створюємо записи ObjectRoleFunctions
            for function_id in object_functions:
                ObjectRoleFunctions.objects.get_or_create(
                    object_role=object_role,
                    function_id=function_id,
                    defaults={'is_active': True}
                )
            
            # Оновлюємо запит після створення записів
            object_role_functions = ObjectRoleFunctions.objects.filter(
                object_role=object_role,
                is_active=True
            ).select_related('function')

        functions_data = []
        for obj_role_func in object_role_functions:
            func = obj_role_func.function
            functions_data.append({
                'id': func.id,
                'name': func.get_name() or func.name or '',
                'description': func.get_description() or '',
                'color': func.color,
                'function_type': 'custom' if func.is_object_specific else 'default'
            })

        return JsonResponse({
            'success': True,
            'functions': functions_data,
            'role': {
                'id': role.id,
                'name': role.get_name() or '',
                'description': role.get_description() or '',
                'color': role.color
            }
        })

    except (AccessObjectIS.DoesNotExist, AccessRoles.DoesNotExist):
        return JsonResponse({
            'success': False,
            'error': _('Object or role not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error in get_object_role_functions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def update_object_role_functions(request, object_id, role_id):
    """
    API endpoint для оновлення функцій ролі для конкретного об'єкта
    """
    try:
        # Перевіряємо, чи існують об'єкт та роль
        obj = get_object_or_404(AccessObjectIS, id=object_id)
        role = get_object_or_404(AccessRoles, id=role_id)
        
        # Перевіряємо, чи призначена роль цьому об'єкту
        object_role = ObjectRoles.objects.filter(access_object=obj, role=role).first()
        if not object_role:
            return JsonResponse({
                'success': False,
                'error': _('Role is not assigned to this object')
            }, status=400)

        # Отримуємо список ID функцій з POST запиту
        function_ids = request.POST.getlist('function_ids[]')
        function_ids = [int(fid) for fid in function_ids if fid.isdigit()]

        with transaction.atomic():
            # Видаляємо всі існуючі об'єкт-специфічні зв'язки для цієї ролі
            ObjectRoleFunctions.objects.filter(object_role=object_role).delete()
            
            # Додаємо нові зв'язки, але тільки для функцій, які призначені об'єкту
            if function_ids:
                # Перевіряємо, які з переданих функцій дійсно призначені об'єкту
                valid_functions = AccessObjectFunction.objects.filter(
                    access_object=obj,
                    function_id__in=function_ids,
                    is_active=True
                ).values_list('function_id', flat=True)
                
                # Створюємо записи тільки для валідних функцій
                for function_id in valid_functions:
                    ObjectRoleFunctions.objects.create(
                        object_role=object_role,
                        function_id=function_id,
                        is_active=True
                    )

        return JsonResponse({
            'success': True,
            'message': _('Role functions updated successfully'),
            'updated_functions_count': len(function_ids) if function_ids else 0
        })

    except (AccessObjectIS.DoesNotExist, AccessRoles.DoesNotExist):
        return JsonResponse({
            'success': False,
            'error': _('Object or role not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error in update_object_role_functions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(['GET'])
def test_object_roles_functions(request, object_id):
    """
    Test endpoint to verify URL routing works
    """
    return JsonResponse({
        'success': True,
        'message': f'Test endpoint reached for object {object_id}',
        'object_id': object_id
    })

























@login_required
@require_POST
@ensure_csrf_cookie  
def remove_object_statuses(request):
    """Remove multiple statuses from an object (bulk removal)"""
    try:
        # Handle form data instead of JSON
        object_id = request.POST.get('object_id')
        status_ids = request.POST.getlist('status_ids')  # getlist to handle array
        
        logger.info(f"Removing statuses {status_ids} from object {object_id}")
        
        if not object_id:
            return JsonResponse({
                'success': False,
                'error': _('Object ID is required')
            }, status=400)
            
        if not status_ids:
            return JsonResponse({
                'success': False,
                'error': _('No status IDs provided')
            }, status=400)
        
        # Get the object
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        
        # ObjectStatus model no longer exists - functionality removed
        return JsonResponse({
            'success': False,
            'error': _('Object statuses functionality is not available')
        }, status=400)
            
    except Exception as e:
        logger.error(f"Error removing object statuses: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# Function get_custom_object_statuses removed - functionality no longer needed

@login_required
@require_POST
def copy_object(request, object_id):
    """Copy object with all related data"""
    try:
        logger.info(f"Copying object with ID: {object_id}")
        
        with transaction.atomic():
            # Отримуємо оригінальний об'єкт
            original_object = get_object_or_404(AccessObjectIS, id=object_id)
            logger.info(f"Original object: {original_object}")
            
            # Створюємо копію об'єкта
            new_object = AccessObjectIS.objects.create(
                name=(original_object.name or '') + ' (Копія)',
                description=original_object.description or '',
                color=original_object.color,
                asset_id=original_object.asset_id,
                environment=original_object.environment,
                parent_id=original_object.parent_id,
                order=original_object.order
            )
            logger.info(f"Created new object: {new_object}")
            

            
            # Копіюємо Object Roles
            original_roles = ObjectRoles.objects.filter(access_object=original_object)
            for role in original_roles:
                ObjectRoles.objects.create(
                    access_object=new_object,
                    role=role.role,
                    order=role.order,
                    is_active=role.is_active
                )
            logger.info(f"Copied {original_roles.count()} object roles")
            
            # Копіюємо Object Access Rights
            original_access_rights = ObjectAccessRights.objects.filter(access_object=original_object)
            for right in original_access_rights:
                ObjectAccessRights.objects.create(
                    access_object=new_object,
                    access_right=right.access_right,
                    order=right.order,
                    is_active=right.is_active
                )
            logger.info(f"Copied {original_access_rights.count()} access rights")
            

            
            # Копіюємо Object Functions
            original_functions = AccessObjectFunction.objects.filter(access_object=original_object)
            for func in original_functions:
                AccessObjectFunction.objects.create(
                    access_object=new_object,
                    function=func.function,
                    order=func.order,
                    is_active=func.is_active
                )
            logger.info(f"Copied {original_functions.count()} functions")
            
            # Копіюємо Object Role Functions
            original_role_functions = ObjectRoleFunctions.objects.filter(object_role__access_object=original_object)
            for role_func in original_role_functions:
                # Знаходимо відповідну нову роль об'єкта
                try:
                    new_object_role = ObjectRoles.objects.get(
                        access_object=new_object,
                        role=role_func.object_role.role
                    )
                    ObjectRoleFunctions.objects.create(
                        object_role=new_object_role,
                        function=role_func.function,
                        is_active=role_func.is_active
                    )
                except ObjectRoles.DoesNotExist:
                    logger.warning(f"Could not find matching role for role function: {role_func}")
            logger.info(f"Copied {original_role_functions.count()} role functions")
            
            # Копіюємо Object Function Right Mappings
            original_function_mappings = ObjectFunctionRightMapping.objects.filter(access_object=original_object)
            for mapping in original_function_mappings:
                ObjectFunctionRightMapping.objects.create(
                    access_object=new_object,
                    function=mapping.function,
                    access_right=mapping.access_right,
                    is_active=mapping.is_active,
                    created_by=request.user
                )
            logger.info(f"Copied {original_function_mappings.count()} function right mappings")
            
            return JsonResponse({
                'success': True,
                'message': _('Object copied successfully with all related data'),
                'object': {
                    'id': new_object.id,
                    'name': new_object.get_name() or '',
                    'description': new_object.get_description() or '',
                    'color': new_object.color,
                    'parent_id': new_object.parent_id
                }
            })
            
    except Exception as e:
        logger.error(f"Error copying object: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
@require_POST
@ensure_csrf_cookie
def copy_environment_data(request):
    """
    Copy data from one environment to another for a specific information system
    """
    try:
        logger.debug("Starting copy_environment_data view")
        
        # Check access permissions
        if not can_edit_access_config_is(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied to copy environment data')
            }, status=403)
        
        # Get request data
        system_id = request.POST.get('system_id')
        source_environment = request.POST.get('source_environment')
        target_environment = request.POST.get('target_environment')
        data_types = request.POST.getlist('data_types[]')  # List of data types to copy
        
        if not all([system_id, source_environment, target_environment, data_types]):
            return JsonResponse({
                'success': False,
                'message': _('Missing required parameters')
            }, status=400)
        
        # Validate environments
        valid_environments = ['production', 'test', 'development']
        if source_environment not in valid_environments or target_environment not in valid_environments:
            return JsonResponse({
                'success': False,
                'message': _('Invalid environment specified')
            }, status=400)
        
        if source_environment == target_environment:
            return JsonResponse({
                'success': False,
                'message': _('Source and target environments must be different')
            }, status=400)
        
        # Get the information system
        try:
            system = InformationAsset.objects.get(id=system_id)
        except InformationAsset.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': _('Information system not found')
            }, status=404)
        
        # Check if user has access to this system
        user_companies = get_user_companies_for_config_is(request.user)
        if not user_companies.filter(id=system.company.id).exists():
            return JsonResponse({
                'success': False,
                'message': _('Access denied to this information system')
            }, status=403)
        
        # Start transaction
        with transaction.atomic():
            copied_items = {}
            
            # Copy Objects
            if 'objects' in data_types:
                copied_objects = copy_objects_between_environments(system, source_environment, target_environment)
                copied_items['objects'] = copied_objects
            
            # Copy Roles
            if 'roles' in data_types:
                copied_roles = copy_roles_between_environments(system, source_environment, target_environment)
                copied_items['roles'] = copied_roles
            
            # Copy Access Rights
            if 'access_rights' in data_types:
                copied_rights = copy_access_rights_between_environments(system, source_environment, target_environment)
                copied_items['access_rights'] = copied_rights
            
            # Copy Functions
            if 'functions' in data_types:
                copied_functions = copy_functions_between_environments(system, source_environment, target_environment)
                copied_items['functions'] = copied_functions
            
            # Copy Roles & Functions (role-function assignments)
            if 'roles_functions' in data_types:
                copied_rf = copy_roles_functions_between_environments(system, source_environment, target_environment)
                copied_items['roles_functions'] = copied_rf
            
            # Copy Approving Persons
            if 'approving_persons' in data_types:
                copied_approvers = copy_approving_persons_between_environments(system, source_environment, target_environment)
                copied_items['approving_persons'] = copied_approvers
            
            # Copy Object-specific data
            if 'object_data' in data_types:
                copied_object_data = copy_object_data_between_environments(system, source_environment, target_environment)
                copied_items['object_data'] = copied_object_data
        
        # Prepare response
        total_copied = sum(items if isinstance(items, int) else sum(items.values()) if isinstance(items, dict) else 0 for items in copied_items.values())
        
        return JsonResponse({
            'success': True,
            'message': _('Data copied successfully'),
            'copied_items': copied_items,
            'total_copied': total_copied,
            'source_environment': source_environment,
            'target_environment': target_environment
        })
        
    except Exception as e:
        logger.error(f"Error in copy_environment_data: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


def copy_objects_between_environments(system, source_env, target_env):
    """Copy objects from source environment to target environment"""
    copied_count = 0
    
    # Get all objects from source environment
    source_objects = AccessObjectIS.objects.filter(
        asset=system,
        environment=source_env
    ).order_by('tree_id', 'lft')
    
    # Create a mapping of old IDs to new IDs for parent relationships
    id_mapping = {}
    
    for source_obj in source_objects:
        # Check if object already exists in target environment
        existing_obj = AccessObjectIS.objects.filter(
            asset=system,
            name=source_obj.name,
            environment=target_env
        ).first()
        
        if not existing_obj:
            new_obj = AccessObjectIS.objects.create(
                asset=system,
                parent=None,
                name=source_obj.name or '',
                description=source_obj.description or '',
                color=source_obj.color,
                order=source_obj.order,
                environment=target_env
            )
            for t in source_obj.translations.all():
                trans, _ = AccessObjectISTranslation.objects.get_or_create(
                    access_object=new_obj, country=t.country,
                    defaults={'name_local': t.name_local, 'description': t.description or ''}
                )
                trans.name_local = t.name_local
                trans.description = t.description or ''
                trans.save()
            
            # Store mapping for parent relationship
            id_mapping[source_obj.id] = new_obj.id
            copied_count += 1
        else:
            # Use existing object for parent relationship mapping
            id_mapping[source_obj.id] = existing_obj.id
    
    # Update parent relationships for newly created objects
    for source_obj in source_objects:
        if source_obj.parent_id and source_obj.parent_id in id_mapping:
            new_obj = AccessObjectIS.objects.get(id=id_mapping[source_obj.id])
            new_parent = AccessObjectIS.objects.get(id=id_mapping[source_obj.parent_id])
            new_obj.parent = new_parent
            new_obj.save()
    
    return copied_count


def copy_roles_between_environments(system, source_env, target_env):
    """Copy roles from source environment to target environment"""
    copied_count = 0
    
    source_roles = AccessRoles.objects.filter(
        system=system,
        environment=source_env,
        is_object_specific=False  # Only copy system-level roles
    )
    
    for source_role in source_roles:
        # Check if role already exists in target environment
        existing_role = AccessRoles.objects.filter(
            system=system,
            name=source_role.name,
            environment=target_env,
            is_object_specific=False
        ).first()
        
        if not existing_role:
            new_role = AccessRoles.objects.create(
                system=system,
                name=source_role.name or '',
                description=source_role.description or '',
                color=source_role.color,
                order=source_role.order,
                environment=target_env,
                is_object_specific=False
            )
            for t in source_role.translations.all():
                trans, _created = AccessRolesTranslation.objects.get_or_create(
                    access_role=new_role, country=t.country,
                    defaults={'name_local': t.name_local, 'description': t.description or ''}
                )
                trans.name_local = t.name_local
                trans.description = t.description or ''
                trans.save()
            copied_count += 1
    
    return copied_count


def copy_access_rights_between_environments(system, source_env, target_env):
    """Copy access rights from source environment to target environment"""
    copied_count = 0
    
    source_rights = AccessRight.objects.filter(
        system=system,
        environment=source_env,
        is_object_specific=False  # Only copy system-level rights
    )
    
    for source_right in source_rights:
        # Check if access right already exists in target environment
        existing_right = AccessRight.objects.filter(
            system=system,
            name=source_right.name,
            environment=target_env,
            is_object_specific=False
        ).first()
        
        if not existing_right:
            new_right = AccessRight.objects.create(
                name=source_right.name or '',
                description=source_right.description or '',
                color=source_right.color,
                order=source_right.order,
                environment=target_env,
                system=system,
                is_object_specific=False
            )
            for t in source_right.translations.all():
                trans, _ = AccessRightTranslation.objects.get_or_create(
                    access_right=new_right, country=t.country,
                    defaults={'name_local': t.name_local, 'description': t.description or ''}
                )
                trans.name_local = t.name_local
                trans.description = t.description or ''
                trans.save()
            copied_count += 1
    
    return copied_count


def copy_functions_between_environments(system, source_env, target_env):
    """Copy functions from source environment to target environment"""
    copied_count = 0
    
    # Get all functions from source environment
    source_functions = AccessFunctionIS.objects.filter(
        asset=system,
        environment=source_env
    ).order_by('tree_id', 'lft')
    
    # Create a mapping of old IDs to new IDs for parent relationships
    id_mapping = {}
    
    for source_func in source_functions:
        # Check if function already exists in target environment
        existing_func = AccessFunctionIS.objects.filter(
            asset=system,
            name=source_func.name,
            environment=target_env,
            is_object_specific=False
        ).first()
        
        if not existing_func:
            new_func = AccessFunctionIS.objects.create(
                asset=system,
                parent=None,
                name=source_func.name or '',
                description=source_func.description or '',
                color=source_func.color,
                order=source_func.order,
                environment=target_env,
                is_object_specific=False
            )
            for t in source_func.translations.all():
                trans, _ = AccessFunctionISTranslation.objects.get_or_create(
                    access_function=new_func, country=t.country,
                    defaults={'name_local': t.name_local, 'description': t.description or ''}
                )
                trans.name_local = t.name_local
                trans.description = t.description or ''
                trans.save()
            
            # Store mapping for parent relationship
            id_mapping[source_func.id] = new_func.id
            copied_count += 1
        else:
            # Use existing function for parent relationship mapping
            id_mapping[source_func.id] = existing_func.id
    
    # Update parent relationships for newly created functions
    for source_func in source_functions:
        if source_func.parent_id and source_func.parent_id in id_mapping:
            new_func = AccessFunctionIS.objects.get(id=id_mapping[source_func.id])
            new_parent = AccessFunctionIS.objects.get(id=id_mapping[source_func.parent_id])
            new_func.parent = new_parent
            new_func.save()
    
    return copied_count


def _function_path_tuple(func, id_to_func=None):
    """Return tuple of (name, ...) from root to this function for hierarchy matching.
    If id_to_func is provided (dict id -> function), walk parents via it to avoid extra queries.
    """
    path = []
    node = func
    while node:
        path.append((node.name or '').strip())
        if id_to_func is not None and node.parent_id:
            node = id_to_func.get(node.parent_id)
        else:
            node = getattr(node, 'parent', None) if node else None
    return tuple(reversed(path))


def copy_roles_functions_between_environments(system, source_env, target_env):
    """Copy role-function assignments (Roles & Functions) from source to target environment.
    Matches roles by name and functions by hierarchy path (root-to-node names).
    """
    source_funcs = list(
        AccessFunctionIS.objects.filter(
            asset=system,
            environment=source_env,
            is_object_specific=False
        )
    )
    target_funcs = list(
        AccessFunctionIS.objects.filter(
            asset=system,
            environment=target_env,
            is_object_specific=False
        )
    )
    source_id_to_func = {f.id: f for f in source_funcs}
    target_id_to_func = {f.id: f for f in target_funcs}

    # Map by path so we match same logical function across environments (not by tree index)
    target_path_to_id = {}
    for f in target_funcs:
        path = _function_path_tuple(f, target_id_to_func)
        if path not in target_path_to_id:
            target_path_to_id[path] = f.id

    source_id_to_target_id = {}
    for f in source_funcs:
        path = _function_path_tuple(f, source_id_to_func)
        if path in target_path_to_id:
            source_id_to_target_id[f.id] = target_path_to_id[path]

    copied_count = 0
    source_roles = AccessRoles.objects.filter(
        system=system,
        environment=source_env,
        is_object_specific=False
    ).prefetch_related('functions')

    for source_role in source_roles:
        target_role = AccessRoles.objects.filter(
            system=system,
            environment=target_env,
            name=source_role.name,
            is_object_specific=False
        ).first()
        if not target_role:
            continue
        source_func_ids = list(source_role.functions.filter(is_object_specific=False).values_list('id', flat=True))
        target_func_ids = [source_id_to_target_id[fid] for fid in source_func_ids if fid in source_id_to_target_id]
        target_func_ids = list(dict.fromkeys(target_func_ids))
        target_role.functions.set(target_func_ids)
        copied_count += len(target_func_ids)

    return copied_count


def copy_statuses_between_environments(system, source_env, target_env):
    """Copy statuses from source environment to target environment"""
    copied_count = 0
    
    source_statuses = AccessStatus.objects.filter(
        system=system,
        environment=source_env,
        is_object_specific=False  # Only copy system-level statuses
    )
    
    for source_status in source_statuses:
        # Check if status already exists in target environment
        existing_status = AccessStatus.objects.filter(
            system=system,
            name=source_status.name,
            environment=target_env,
            is_object_specific=False
        ).first()
        
        if not existing_status:
            new_status = AccessStatus.objects.create(
                system=system,
                name=source_status.name or '',
                description=source_status.description or '',
                color=source_status.color,
                order=source_status.order,
                environment=target_env,
                is_object_specific=False
            )
            copied_count += 1
    
    return copied_count


def copy_approving_persons_between_environments(system, source_env, target_env):
    """Copy approving persons from source environment to target environment"""
    copied_count = 0
    
    source_approvers = ApprovingPerson.objects.filter(
        asset=system,
        environment=source_env
    )
    
    for source_approver in source_approvers:
        # Check if approving person already exists in target environment
        existing_approver = ApprovingPerson.objects.filter(
            asset=system,
            cabinet_user=source_approver.cabinet_user,
            order=source_approver.order,
            environment=target_env
        ).first()
        
        if not existing_approver:
            # Create new approving person only if it doesn't exist
            new_approver = ApprovingPerson.objects.create(
                asset=system,
                cabinet_user=source_approver.cabinet_user,
                order=source_approver.order,
                color=source_approver.color,
                environment=target_env
            )
            copied_count += 1
    
    return copied_count


def copy_object_data_between_environments(system, source_env, target_env):
    """Copy object-specific data between environments"""
    copied_data = {
        'object_roles': 0,
        'object_access_rights': 0,
        'object_functions': 0,
        'object_statuses': 0
    }
    
    # Get source and target objects
    source_objects = AccessObjectIS.objects.filter(
        asset=system,
        environment=source_env
    )
    target_objects = AccessObjectIS.objects.filter(
        asset=system,
        environment=target_env
    )
    
    # Create mapping by name (assuming objects with same name should be linked)
    source_obj_map = {obj.name or '': obj for obj in source_objects}
    target_obj_map = {obj.name or '': obj for obj in target_objects}
    
    for obj_name, source_obj in source_obj_map.items():
        if obj_name in target_obj_map:
            target_obj = target_obj_map[obj_name]
            
            # Copy object roles
            source_roles = ObjectRoles.objects.filter(access_object=source_obj)
            for source_role in source_roles:
                # Find corresponding role in target environment
                target_role = AccessRoles.objects.filter(
                    system=system,
                    environment=target_env,
                    name=source_role.role.name
                ).first()
                
                if target_role:
                    ObjectRoles.objects.get_or_create(
                        access_object=target_obj,
                        role=target_role,
                        defaults={
                            'order': source_role.order,
                            'is_active': source_role.is_active
                        }
                    )
                    copied_data['object_roles'] += 1
            
            # Copy object access rights
            source_rights = ObjectAccessRights.objects.filter(access_object=source_obj)
            for source_right in source_rights:
                # Find corresponding access right in target environment
                target_right = AccessRight.objects.filter(
                    system=system,
                    environment=target_env,
                    name=source_right.access_right.name
                ).first()
                
                if target_right:
                    ObjectAccessRights.objects.get_or_create(
                        access_object=target_obj,
                        access_right=target_right,
                        defaults={
                            'order': source_right.order,
                            'is_active': source_right.is_active
                        }
                    )
                    copied_data['object_access_rights'] += 1
            
            # Copy object functions
            source_functions = AccessObjectFunction.objects.filter(access_object=source_obj)
            for source_func in source_functions:
                # Find corresponding function in target environment
                target_func = AccessFunctionIS.objects.filter(
                    asset=system,
                    environment=target_env,
                    name=source_func.function.name
                ).first()
                
                if target_func:
                    AccessObjectFunction.objects.get_or_create(
                        access_object=target_obj,
                        function=target_func,
                        defaults={
                            'order': source_func.order,
                            'is_active': source_func.is_active
                        }
                    )
                    copied_data['object_functions'] += 1
            
            # Copy object statuses - ObjectStatus model no longer exists, skipping
            # source_statuses = ObjectStatus.objects.filter(access_object=source_obj)
            # for source_status in source_statuses:
            #     # Find corresponding status in target environment
            #     target_status = AccessStatus.objects.filter(
            #         system=system,
            #         environment=target_env,
            #         accessstatus_name_ua=source_status.status.accessstatus_name_ua
            #     ).first()
            #     
            #     if target_status:
            #         ObjectStatus.objects.get_or_create(
            #             access_object=target_obj,
            #             status=target_status,
            #             defaults={
            #                 'order': source_status.order,
            #                 'is_active': source_status.is_active
            #             }
            #         )
            #         copied_data['object_statuses'] += 1
    
    return copied_data