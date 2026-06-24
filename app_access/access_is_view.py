from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.translation import gettext as _, get_language
from .models import SystemAccess, AccessRight, AccessFunctionIS, AccessStatus, ApprovingPerson, AccessApprover, AccessRoles, AccessObjectIS, ObjectRoles, AccessRecordsGuide, AccessRecordsGuideTranslation
import logging
from collections import defaultdict
from django.contrib.auth.models import Group, User
from django.db import transaction, OperationalError
from django.db.models import F, Value, CharField, Case, When
from app_conf.models import Company, Country
from app_asset.models import AccessAssets, InformationAsset
import json
import time
from app_cabinet.models import CabinetUser, CabinetGroup, Department, Position
from .email_utils import send_access_status_change_notification
from .matrix_view import (has_access_records_permission, can_add_access_records, 
                         can_edit_access_records, can_delete_access_records, 
                         get_user_companies_for_records)


logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


def check_and_update_expired_records():
    """
    Автоматично перевіряє та встановлює статус Inactive для записів з минулими датами закінчення.
    Повертає кількість оновлених записів.
    """
    try:
        now = timezone.now()
        
        # Знаходимо всі активні записи з минулими датами закінчення
        expired_records = SystemAccess.objects.filter(
            is_active=True,
            end_date__lt=now
        ).select_related('asset', 'access_object', 'status')
        
        if not expired_records.exists():
            # Quiet: avoid info noise when nothing to update
            return 0
            
        updated_count = 0
        
        # Оновлюємо кожен запис окремо для відправки email повідомлень
        for record in expired_records:
            old_status = record.is_active
            
            with transaction.atomic():
                # Оновлюємо статус на неактивний
                record.is_active = False
                record.modified_at = now
                record.save(update_fields=['is_active', 'modified_at'])
                
                logger.info(f"Access record {record.id} ({record.asset.name}) set to inactive due to expiration")
                
                # Відправляємо email повідомлення про зміну статусу
                try:
                    send_access_status_change_notification(
                        access_record=record,
                        old_status=old_status,
                        new_status=record.is_active,
                        changed_by=None,  # Система автоматично
                        change_reason="Automatically set to inactive due to expiration"
                    )
                except Exception as email_error:
                    logger.warning(f"Failed to send email notification for expired record {record.id}: {email_error}")
                
                updated_count += 1
        
        # Quiet summary suppressed
        
        return updated_count
        
    except Exception as e:
        logger.error(f"Error checking and updating expired records: {str(e)}", exc_info=True)
        return 0


def _user_display_name(user):
    if getattr(user, 'cabinet', None):
        name = f"{user.first_name} {user.last_name}".strip()
        if name:
            return name
    return user.get_full_name() or user.username


def _group_display_name(group):
    cabinet_details = getattr(group, 'cabinet_details', None)
    if cabinet_details and cabinet_details.name:
        return cabinet_details.name
    return group.name


def _build_user_group_filter_options(access_records, user_relation, group_relation):
    """Build sorted filter options from users and groups on access records."""
    user_options = {}
    group_options = {}
    for access in access_records:
        for user in getattr(access, user_relation).all():
            user_options[user.id] = _user_display_name(user)
        for group in getattr(access, group_relation).all():
            group_options[group.id] = _group_display_name(group)

    options = [
        {'type': 'user', 'id': uid, 'label': label}
        for uid, label in user_options.items()
    ]
    options.extend(
        {'type': 'group', 'id': gid, 'label': label}
        for gid, label in group_options.items()
    )
    options.sort(key=lambda item: item['label'].lower())
    return options


from .pagination_utils import ACCESS_TABLE_PAGE_SIZE_OPTIONS, get_access_table_page_size

ACCESS_RECORDS_PAGE_SIZE_OPTIONS = ACCESS_TABLE_PAGE_SIZE_OPTIONS


def _get_access_records_page_size(request):
    return get_access_table_page_size(request)


def _access_records_list_queryset(access_records_qs):
    return access_records_qs.select_related(
        'asset',
        'asset__company',
        'access_object',
        'status',
        'created_by',
        'modified_by',
        'reviewed_by',
    ).prefetch_related(
        'asset__owners',
        'asset__administrators',
        'asset__approving_persons',
        'approvers',
        'approvers__cabinet_user',
        'approvers__cabinet_user__department',
        'approvers__cabinet_user__position',
        'request_users',
        'request_users__cabinet__user',
        'access_users',
        'access_users__cabinet__user',
        Prefetch('request_users__cabinet__department', queryset=Department.objects.only(
            'id', 'name'
        )),
        Prefetch('access_users__cabinet__department', queryset=Department.objects.only(
            'id', 'name'
        )),
        Prefetch('request_users__cabinet__position', queryset=Position.objects.only(
            'id', 'name'
        )),
        Prefetch('access_users__cabinet__position', queryset=Position.objects.only(
            'id', 'name'
        )),
        'request_groups',
        'request_groups__cabinet_details',
        'access_groups',
        'access_groups__cabinet_details',
        'roles',
        'access_requests',
    ).order_by('-created_at')


@login_required
def access_is(request):
    try:
        # Check access permissions
        if not has_access_records_permission(request.user):
            return JsonResponse({
                'error': 'Access denied',
                'message': _('Access denied to Access Records page')
            }, status=403)
        
        # Автоматично перевіряємо та оновлюємо записи з минулими датами
        expired_count = check_and_update_expired_records()
        # Quiet: don't emit info about auto-updates on page load
        
        # Get user's companies for records
        user_companies = get_user_companies_for_records(request.user)
        
        # Get user's permissions for template
        can_add = can_add_access_records(request.user)
        can_edit = can_edit_access_records(request.user)
        can_delete = can_delete_access_records(request.user)
        
        # Перевіряємо чи потрібно показувати неактивні записи
        show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
        
        # Базовий QuerySet
        access_records_qs = SystemAccess.objects.all()
        
        # Filter by user's companies if they have specific company access
        if user_companies.exists():
            access_records_qs = access_records_qs.filter(asset__company__in=user_companies)
        else:
            # If no companies specified, show no records for security
            access_records_qs = SystemAccess.objects.none()
        
        # Якщо не потрібно показувати неактивні, фільтруємо тільки активні
        if not show_inactive:
            access_records_qs = access_records_qs.filter(is_active=True)
        
        # Filter assets by user's companies
        if user_companies.exists():
            user_assets = InformationAsset.objects.filter(company__in=user_companies).order_by('name')
        else:
            user_assets = InformationAsset.objects.none()
        
        context = {
            'companies': user_companies,
            'groups': AccessAssets.objects.all(),
            'assets': user_assets,
            'show_inactive': show_inactive,
            'can_add_access_records': can_add,
            'can_edit_access_records': can_edit,
            'can_delete_access_records': can_delete,
        }

        records_qs = _access_records_list_queryset(access_records_qs)
        records_for_filters = list(
            access_records_qs.prefetch_related(
                'request_users',
                'request_groups',
                'access_users',
                'access_groups',
                'request_groups__cabinet_details',
                'access_groups__cabinet_details',
            ).only('id', 'third_parties')
        )
        context['request_who_filter_options'] = _build_user_group_filter_options(
            records_for_filters, 'request_users', 'request_groups'
        )
        request_for_filter_options = _build_user_group_filter_options(
            records_for_filters, 'access_users', 'access_groups'
        )
        if any(getattr(access, 'third_parties', False) for access in records_for_filters):
            request_for_filter_options.append({
                'type': 'third_parties',
                'id': '1',
                'label': str(_('Third parties')),
            })
            request_for_filter_options.sort(key=lambda item: item['label'].lower())
        context['request_for_filter_options'] = request_for_filter_options

        page_size = _get_access_records_page_size(request)
        paginator = Paginator(records_qs, page_size)
        page_number = request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages or 1)

        context['access_records'] = page_obj.object_list
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['is_paginated'] = paginator.count > 0
        context['current_page_size'] = page_size
        context['page_size_options'] = ACCESS_RECORDS_PAGE_SIZE_OPTIONS

        # Оптимізуємо завантаження груп
        for access in context['access_records']:
            for group in access.request_groups.all():
                group.user_set.all().select_related(
                    'cabinet__department',
                    'cabinet__position'
                )
            for group in access.access_groups.all():
                group.user_set.all().select_related(
                    'cabinet__department',
                    'cabinet__position'
                )

        logger.info(f"Found {paginator.count} access records (page {page_obj.number}/{paginator.num_pages})")
        return render(request, 'app_access/access_records.html', context)
    except Exception as e:
        logger.error(f"Error in access_is view: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': str(e),
            'message': _('Error loading access records')
        }, status=500)


@login_required
@require_http_methods(["GET"])
def access_records_guide(request):
    """Return JSON { content: html } for the Access Records guide (localized)."""
    if not has_access_records_permission(request.user):
        return JsonResponse({'content': ''})
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = AccessRecordsGuide.objects.first()
    if guide:
        if country:
            trans = AccessRecordsGuideTranslation.objects.filter(guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = AccessRecordsGuideTranslation.objects.filter(guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def access_records_guide_translate(request):
    """API for AI translation of Access Records guide content (admin)."""
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
        err = str(e)
        if 'No support for the provided language' in err:
            return JsonResponse({
                'success': True,
                'translated_text': text,
                'target_language': target,
                'country_name': country.name,
                'warning': 'Language not supported, returned original',
            })
        return JsonResponse({'success': False, 'error': err}, status=500)


def _parse_json_id_list(raw_value, single_value=None):
    """Parse a JSON array or a single id into a list of non-empty string ids."""
    if raw_value:
        try:
            parsed = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
            items = parsed if isinstance(parsed, list) else [parsed]
            return [str(item) for item in items if item]
        except (json.JSONDecodeError, TypeError):
            pass
    if single_value:
        return [str(single_value)]
    return []


def _create_system_access_record(
    request,
    *,
    system_id,
    object_id,
    environment,
    role_ids,
    description,
    start_date,
    end_date,
    request_users,
    request_groups,
    access_users,
    access_groups,
    third_parties,
):
    """Create one SystemAccess row and attach M2M relations and approvers."""
    access = SystemAccess.objects.create(
        asset_id=system_id,
        access_object_id=object_id if object_id else None,
        environment=environment,
        description=description,
        start_date=start_date,
        end_date=end_date or None,
        third_parties=third_parties,
        created_by=request.user,
    )
    if request_users:
        access.request_users.add(*request_users)
    if request_groups:
        access.request_groups.add(*request_groups)
    if access_users:
        access.access_users.add(*access_users)
    if access_groups:
        access.access_groups.add(*access_groups)
    if role_ids:
        access.roles.set(role_ids)

    system_approvers = ApprovingPerson.objects.filter(
        asset_id=system_id,
        environment=environment,
    ).order_by('order')
    for approver in system_approvers:
        if not AccessApprover.objects.filter(
            access=access,
            cabinet_user=approver.cabinet_user,
        ).exists():
            AccessApprover.objects.create(
                access=access,
                cabinet_user=approver.cabinet_user,
                order=approver.order,
            )
    return access


@login_required
@require_POST
def add_access(request):
    try:
        logger.info(f"Add access request received from user: {request.user.username}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request POST data keys: {list(request.POST.keys())}")
        
        # Check if user can add access records
        if not can_add_access_records(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to add access records. Please contact your administrator to grant you add rights.')
            }, status=403)
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

        data = request.POST
        company_id = data.get('company')
        system_id = data.get('system')
        object_ids = _parse_json_id_list(data.get('objects'), data.get('object'))
        environment = data.get('environment')
        # Support both single 'role' and multiple 'roles' (JSON array)
        roles_raw = data.get('roles')
        if roles_raw:
            try:
                role_ids = json.loads(roles_raw) if isinstance(roles_raw, str) else roles_raw
                role_ids = [r for r in (role_ids if isinstance(role_ids, list) else [role_ids]) if r]
            except (json.JSONDecodeError, TypeError):
                role_ids = []
        else:
            role_id = data.get('role')
            role_ids = [role_id] if role_id else []

        description = data.get('description')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        logger.info(f"Parsed data - company_id: {company_id}, system_id: {system_id}, object_ids: {object_ids}")
        logger.info(f"Environment: {environment}, Role IDs: {role_ids}")
        logger.info(f"Start date: {start_date}, End date: {end_date}")
        
        # Check if user has access to the company
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
                user_companies = get_user_companies_for_records(request.user)
                
                if user_companies.exists() and company not in user_companies:
                    return JsonResponse({
                        'success': False,
                        'message': _('Access denied - you do not have permission to add access records for company "{}". Please contact your administrator.').format(company.name)
                    }, status=403)
            except Company.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': _('Company with ID {} not found').format(company_id)
                }, status=404)
        
        # Parsing JSON fields safely
        try:
            request_users = json.loads(data.get('request_users', '[]'))
            request_groups = json.loads(data.get('request_groups', '[]'))
            access_users = json.loads(data.get('access_users', '[]'))
            access_groups = json.loads(data.get('access_groups', '[]'))
            third_parties = data.get('third_parties', 'false').lower() == 'true'
            logger.info(f"Users/Groups - request_users: {request_users}, request_groups: {request_groups}")
            logger.info(f"Access - access_users: {access_users}, access_groups: {access_groups}")
            logger.info(f"Third parties: {third_parties}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return JsonResponse({
                'success': False,
                'message': _('Invalid JSON data in request')
            }, status=400)

        # Валідація обов'язкових полів
        if not company_id or not system_id or not role_ids:
            missing_fields = []
            if not company_id:
                missing_fields.append('company')
            if not system_id:
                missing_fields.append('system')
            if not role_ids:
                missing_fields.append('role')
            
            logger.warning(f"Missing required fields: {missing_fields}")
            return JsonResponse({
                'success': False,
                'message': _('Missing required fields: ') + ', '.join(missing_fields)
            }, status=400)

        # One record per selected object; empty list => single record without object
        target_object_ids = object_ids if object_ids else [None]

        created_accesses = []
        with transaction.atomic():
            for object_id in target_object_ids:
                logger.info("Creating SystemAccess object for object_id=%s", object_id)
                access = _create_system_access_record(
                    request,
                    system_id=system_id,
                    object_id=object_id,
                    environment=environment,
                    role_ids=role_ids,
                    description=description,
                    start_date=start_date,
                    end_date=end_date,
                    request_users=request_users,
                    request_groups=request_groups,
                    access_users=access_users,
                    access_groups=access_groups,
                    third_parties=third_parties,
                )
                logger.info("Created SystemAccess with ID: %s", access.id)
                created_accesses.append(access)

        count = len(created_accesses)
        if count == 1:
            message = _('Access record created successfully')
        else:
            message = _('%(count)s access records created successfully') % {'count': count}

        return JsonResponse({
            'success': True,
            'message': message,
            'access_id': created_accesses[0].id,
            'access_ids': [a.id for a in created_accesses],
        })

    except Exception as e:
        logger.error(f"Error creating access record: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


# In views.py


@login_required
def edit_access(request, access_id):
    try:
        # Check if user can edit access records
        if not can_edit_access_records(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit access records. Please contact your administrator to grant you edit rights.')
            }, status=403)
        
        access = get_object_or_404(SystemAccess, id=access_id)
        
        # Check if user has access to the record's company
        user_companies = get_user_companies_for_records(request.user)
        if user_companies.exists() and access.asset.company not in user_companies:
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit access records for company "{}". Please contact your administrator.').format(access.asset.company.name)
            }, status=403)

        # Update fields
        access.asset_id = request.POST.get('system')

        # Додаємо оновлення статусу
        status_id = request.POST.get('access_status')
        if status_id:
            access.status = get_object_or_404(AccessStatus, id=status_id)

        access.justification = request.POST.get('justification')
        access.requirements = request.POST.get('requirements')
        access.start_date = request.POST.get('start_date')
        access.end_date = request.POST.get('end_date')
        access.modified_by = request.user

        # Update users and groups
        users_groups = request.POST.getlist('users_groups[]')
        access.users.clear()
        access.groups.clear()

        for item in users_groups:
            if item.startswith('user_'):
                access.users.add(int(item.replace('user_', '')))
            elif item.startswith('group_'):
                access.groups.add(int(item.replace('group_', '')))

        access.save()

        return JsonResponse({
            'status': 'success',
            'message': _('Access record updated successfully')
        })

    except Exception as e:
        logger.error(f"Error in edit_access: {str(e)}")  # Додаємо логування помилок
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


@login_required
def get_system_filters(request, system_id):
    """
    Get available filters for a specific system including environments, objects, and roles
    """
    try:
        logger.info(f"get_system_filters called for system_id: {system_id}")
        
        # Check if user has permission to view access records
        if not has_access_records_permission(request.user):
            logger.warning(f"User {request.user} doesn't have access records permission")
            return JsonResponse({
                'status': 'error',
                'message': _('Access denied')
            }, status=403)
        
        # Get the system
        try:
            system = InformationAsset.objects.get(id=system_id)
            logger.info(f"Found system: {system.name}")
        except InformationAsset.DoesNotExist:
            logger.error(f"System with id {system_id} not found")
            return JsonResponse({
                'status': 'error',
                'message': _('System not found')
            }, status=404)
        
        # Check if user has access to this system's company
        user_companies = get_user_companies_for_records(request.user)
        if user_companies.exists() and system.company not in user_companies:
            logger.warning(f"User {request.user} doesn't have access to company {system.company}")
            return JsonResponse({
                'status': 'error',
                'message': _('Access denied to this system')
            }, status=403)
        
        # Get unique environments for this system from existing access records
        environments = SystemAccess.objects.filter(
            asset=system
        ).values_list('environment', flat=True).distinct().order_by('environment')
        
        logger.info(f"Found environments for system {system.name}: {list(environments)}")
        
        # Get environment choices from the model
        environment_choices = SystemAccess._meta.get_field('environment').choices
        logger.info(f"Environment choices from model: {environment_choices}")
        
        environment_options = []
        
        # Add "All Environments" option
        environment_options.append({
            'value': '',
            'label': _('All Environments')
        })
        
        # Add available environments
        for env_value, env_label in environment_choices:
            if env_value in environments:
                # Get the appropriate label based on current language
                current_language = (get_language() or 'en')[:2].lower()
                if current_language == 'uk':
                    display_label = env_label
                elif current_language == 'en':
                    # Map Ukrainian labels to English
                    label_mapping = {
                        'Продакшн': 'Production',
                        'Тест': 'Test', 
                        'Розробка': 'Development'
                    }
                    display_label = label_mapping.get(env_label, env_label)
                else:
                    display_label = env_label
                    
                environment_options.append({
                    'value': env_value,
                    'label': display_label
                })
        
        logger.info(f"Environment options: {environment_options}")
        
        # Get objects for this system
        objects = AccessObjectIS.objects.filter(
            asset=system,
            is_active=True
        ).order_by('order', 'tree_id', 'lft')
        
        logger.info(f"Found {objects.count()} objects for system {system.name}")
        
        object_options = [{'value': '', 'label': _('All Objects')}]
        for obj in objects:
            current_language = (get_language() or 'en')[:2].lower()
            object_name = obj.get_name(current_language) or obj.get_name('en')
            object_options.append({
                'value': obj.id,
                'label': object_name
            })
        
        # Get roles for this system
        roles = AccessRoles.objects.filter(
            system=system, is_active=True
        ).order_by('order', 'name', 'code')
        
        logger.info(f"Found {roles.count()} roles for system {system.name}")
        
        role_options = [{'value': '', 'label': _('All Roles')}]
        current_language = (get_language() or '')[:2].lower()
        for role in roles:
            role_name = role.get_name(current_language)
            role_options.append({
                'value': role.id,
                'label': role_name,
                'color': role.color
            })
        
        response_data = {
            'status': 'success',
            'data': {
                'environments': environment_options,
                'objects': object_options,
                'roles': role_options
            }
        }
        
        logger.info(f"Returning response: {response_data}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error getting system filters: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


@login_required
def get_access(request, access_id):
    try:
        access = SystemAccess.objects.select_related(
            'asset',
            'asset__company',
            'access_object',
            'status'
        ).prefetch_related(
            'roles',
            'request_users',
            'request_users__cabinet',
            'request_users__cabinet__department',
            'request_users__cabinet__position',
            'request_groups',
            'access_users',
            'access_users__cabinet',
            'access_users__cabinet__department',
            'access_users__cabinet__position',
            'access_groups',
            'approvers',
            'approvers__cabinet_user',
            'approvers__cabinet_user__department',
            'approvers__cabinet_user__position'
        ).get(id=access_id)

        _status_lang = (get_language() or 'en')[:2].lower()
        _status_lang = 'ua' if _status_lang == 'uk' else (_status_lang if _status_lang in ('ru', 'en') else 'en')

        data = {
            'status': 'success',
            'access': {
                'id': access.id,
                'asset': {
                    'id': access.asset.id,
                    'name': access.asset.name,
                    'company': {
                        'id': access.asset.company.id,
                        'name': access.asset.company.name
                    }
                },
                'access_object': {
                    'id': access.access_object.id,
                    'name': access.access_object.get_name() if access.access_object else '',
                    'description': access.access_object.get_description() if access.access_object else ''
                } if access.access_object else None,
                'environment': access.environment,
                'start_date': access.start_date.isoformat() if access.start_date else None,
                'end_date': access.end_date.isoformat() if access.end_date else None,
                'is_active': access.is_active,
                'roles': [{
                    'id': role.id,
                    'name': role.get_name(get_language() or 'en') or role.get_name('en'),
                    'description': role.get_description(get_language() or 'en') or role.get_description('en') or '',
                    'color': role.color
                } for role in access.roles.all()],
                'request_users': [{
                    'id': user.id,
                    'name': user.get_full_name() or user.username,
                    'department': user.cabinet.department.get_name() if user.cabinet and user.cabinet.department else None,
                    'position': user.cabinet.position.get_name() if user.cabinet and user.cabinet.position else None
                } for user in access.request_users.all()],
                'request_groups': [{
                    'id': group.id,
                    'name': group.cabinet_details.get_name() if hasattr(group, 'cabinet_details') else group.name
                } for group in access.request_groups.all()],
                'access_users': [{
                    'id': user.id,
                    'name': user.get_full_name() or user.username,
                    'department': user.cabinet.department.get_name() if user.cabinet and user.cabinet.department else None,
                    'position': user.cabinet.position.get_name() if user.cabinet and user.cabinet.position else None
                } for user in access.access_users.all()],
                'access_groups': [{
                    'id': group.id,
                    'name': group.cabinet_details.get_name() if hasattr(group, 'cabinet_details') else group.name
                } for group in access.access_groups.all()],
                'status': {
                    'id': access.status.id,
                    'name': access.status.get_name() or access.status.name or '',
                    'color': access.status.color
                } if access.status else None,
                'approvers': [{
                    'id': approver.cabinet_user.id,
                    'name': approver.cabinet_user.user.get_full_name(),
                    'department': approver.cabinet_user.department.get_name() if approver.cabinet_user.department else None,
                    'position': approver.cabinet_user.position.get_name() if approver.cabinet_user.position else None,
                    'order': approver.order,
                    'color': approver.cabinet_user.color,
                    'avatar': approver.cabinet_user.avatar.url if approver.cabinet_user.avatar else None
                } for approver in access.approvers.all()],
                'default_approvers': [{
                    'id': approver.cabinet_user.id,
                    'name': approver.cabinet_user.user.get_full_name(),
                    'department': approver.cabinet_user.department.get_name() if approver.cabinet_user.department else None,
                    'position': approver.cabinet_user.position.get_name() if approver.cabinet_user.position else None,
                    'order': approver.order,
                    'color': approver.cabinet_user.color,
                    'avatar': approver.cabinet_user.avatar.url if approver.cabinet_user.avatar else None
                } for approver in access.asset.approving_persons.all()],
                'description': access.description,
                'third_parties': access.third_parties,
                'access_requests_count': access.access_requests.count()
            }
        }

        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error getting access: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


def _delete_access_record_if_allowed(request, access_id):
    """
    Delete one access record when allowed.
    Returns (True, success_message) or (False, error_message).
    """
    try:
        access = SystemAccess.objects.select_related('asset__company').get(id=access_id)
    except SystemAccess.DoesNotExist:
        return False, _('Access record not found')

    access_requests_count = access.access_requests.count()
    if access_requests_count > 0:
        return False, _(
            'Cannot delete access record #%(id)s: it has %(count)s active access request(s). '
            'Please complete or cancel all access requests first.'
        ) % {'id': access_id, 'count': access_requests_count}

    if not can_delete_access_records(request.user):
        return False, _(
            'Access denied - you do not have permission to delete access records.'
        )

    user_companies = get_user_companies_for_records(request.user)
    if user_companies.exists() and access.asset.company not in user_companies:
        return False, _(
            'Access denied - you do not have permission to delete access records for company "%(company)s".'
        ) % {'company': access.asset.company.name}

    access.delete()
    return True, _('Access record deleted successfully')


@require_POST
@login_required
def delete_access(request, access_id):
    """Delete access record."""
    try:
        logger.info(f"Attempting to delete access record with ID: {access_id}")
        ok, message = _delete_access_record_if_allowed(request, access_id)
        if not ok:
            if message == _('Access record not found'):
                status = 404
            elif 'Access denied' in message:
                status = 403
            else:
                status = 400
            logger.warning(f"Cannot delete access record {access_id}: {message}")
            return JsonResponse({'success': False, 'message': message}, status=status)

        logger.info(f"Successfully deleted access record with ID: {access_id}")
        return JsonResponse({'success': True, 'message': message})

    except Exception as e:
        logger.error(f"Error deleting access record {access_id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@require_POST
@login_required
def bulk_delete_access(request):
    """Delete multiple access records."""
    try:
        if not can_delete_access_records(request.user):
            return JsonResponse({
                'success': False,
                'message': _(
                    'Access denied - you do not have permission to delete access records. '
                    'Please contact your administrator to grant you delete rights.'
                ),
            }, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': _('Invalid JSON data in request'),
            }, status=400)

        raw_ids = data.get('access_ids') or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return JsonResponse({
                'success': False,
                'message': _('No access records selected'),
            }, status=400)

        access_ids = []
        for raw_id in raw_ids:
            try:
                access_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue
        access_ids = list(dict.fromkeys(access_ids))
        if not access_ids:
            return JsonResponse({
                'success': False,
                'message': _('No valid access record IDs provided'),
            }, status=400)

        deleted_ids = []
        failed = []
        for access_id in access_ids:
            ok, message = _delete_access_record_if_allowed(request, access_id)
            if ok:
                deleted_ids.append(access_id)
                logger.info("Bulk delete: removed access record %s", access_id)
            else:
                failed.append({'id': access_id, 'message': message})

        deleted_count = len(deleted_ids)
        failed_count = len(failed)

        if deleted_count and not failed_count:
            message = _('%(count)s access record(s) deleted successfully') % {'count': deleted_count}
        elif deleted_count and failed_count:
            message = _(
                '%(deleted)s access record(s) deleted; %(failed)s could not be deleted.'
            ) % {'deleted': deleted_count, 'failed': failed_count}
        else:
            message = _('No access records were deleted')

        return JsonResponse({
            'success': deleted_count > 0,
            'message': message,
            'deleted_count': deleted_count,
            'deleted_ids': deleted_ids,
            'failed': failed,
        })

    except Exception as e:
        logger.error(f"Error in bulk_delete_access: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e),
        }, status=500)

# Helper functions
def get_available_assets(user):
    """Get assets available for the user with localized group and type names."""
    current_language = get_language()[:2]

    return InformationAsset.objects.filter(
        company__in=get_user_companies(user),
        access_manage=True,  # Only include assets marked for access management
        deletion_date__isnull=True  # Only include active assets
    ).select_related(
        'group',
        'asset_type',
        'company'
    ).annotate(
        group_name=Case(
            When(group__isnull=True, then=Value('')),
            When(**{f'group__name_{current_language}__exact': ''},
                 then=F('group__name_uk')),
            default=F(f'group__name_{current_language}'),
            output_field=CharField()
        ),
        type_name=Case(
            When(asset_type__isnull=True, then=Value('')),
            When(**{f'asset_type__name_{current_language}__exact': ''},
                 then=F('asset_type__name_uk')),
            default=F(f'asset_type__name_{current_language}'),
            output_field=CharField()
        )
    ).order_by('name')



def get_available_groups(user):
    """Get groups available for access assignment."""
    return Group.objects.all()




def get_user_companies(user):
    """Get companies the user has access to."""
    if user.is_superuser:
        return Company.objects.all()
    return Company.objects.filter(
        access_assets__group__in=user.groups.all()
    ).distinct()


@login_required
def get_role_matrix(request, role_id, system_id):
    """Get matrix data for specific role and system"""
    try:
        current_lang = (get_language() or 'en')[:2].lower()
        if current_lang == 'uk':
            current_lang = 'ua'

        # Отримуємо роль
        role = AccessRoles.objects.get(id=role_id, system_id=system_id)

        # Отримуємо всі функції системи з оптимізованими запитами
        functions = AccessFunctionIS.objects.filter(is_active=True,
            asset_id=system_id
        ).select_related(
            'asset',
            'parent'
        ).prefetch_related(
            'access_rights'
        )

        # Створюємо словник для швидкого доступу до дочірніх елементів
        children_map = {}
        for func in functions:
            parent_id = func.parent_id if func.parent_id else 'root'
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(func)

        # Отримуємо всі права доступу системи
        access_rights = AccessRight.objects.filter(
            system_id=system_id
        ).order_by('order')

        # Отримуємо призначені функції
        assigned_functions = set(role.functions.values_list('id', flat=True))

        def format_function(func):
            # Отримуємо права доступу для функції
            function_rights = []
            if func.id in assigned_functions:
                function_rights = func.access_rights.all()

            # Отримуємо дочірні функції з map
            children = children_map.get(func.id, [])

            return {
                'id': func.id,
                'name': func.get_name(current_lang) or func.get_name('en'),
                'description': func.get_description(current_lang) or func.get_description('en') or '',
                'color': func.color,
                'is_assigned': func.id in assigned_functions,
                'access_rights': [{
                    'id': right.id,
                    'name': right.get_name(current_lang) or right.get_name('en'),
                    'color': right.color,
                    'description': right.get_description(current_lang) or right.get_description('en') or ''
                } for right in function_rights],
                'children': [format_function(child) for child in children]
            }

        # Отримуємо тільки кореневі функції
        root_functions = [
            format_function(f)
            for f in functions.filter(parent__isnull=True).order_by('order')
        ]

        data = {
            'role': {
                'id': role.id,
                'name': role.get_name(current_lang) or role.get_name('en'),
                'description': role.get_description(current_lang) or role.get_description('en') or '',
                'color': role.color
            },
            'functions': root_functions,
            'access_rights': [{
                'id': right.id,
                'name': right.get_name(current_lang) or right.get_name('en'),
                'color': right.color
            } for right in access_rights]
        }

        return JsonResponse({
            'status': 'success',
            'data': data
        })

    except Exception as e:
        logger.error(f"Error in get_role_matrix: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(['GET'])
def get_cabinet_users_and_groups(request):
    company_id = request.GET.get('company_id')
    system_id = request.GET.get('system_id')
    environment = request.GET.get('environment')
    current_language = (get_language() or 'en')[:2].lower()

    # logger.debug(f"Getting request users and groups for company_id: {company_id}")
    try:
        # Only active Cabinet users for today:
        # - Django user must be active
        # - cabinet start_date <= today (or empty)
        # - cabinet end_date >= today (or empty)
        today = timezone.localdate()
        active_employee_q = (
            (Q(start_date__isnull=True) | Q(start_date__date__lte=today))
            & (Q(end_date__isnull=True) | Q(end_date__date__gte=today))
        )
        cabinet_users = CabinetUser.objects.filter(
            company_id=company_id,
            user__is_active=True,
        ).filter(active_employee_q).select_related(
            'user',
            'department',
            'position'
        ).order_by('user__last_name', 'user__first_name')

        # Pre-calculate available access-record counts per user for selected system/environment
        # so frontend can display count near each Available User.
        user_access_record_counts = defaultdict(int)
        if system_id and environment:
            requester_groups = request.user.groups.all()
            base_records = SystemAccess.objects.filter(
                asset_id=system_id,
                environment=environment,
                is_active=True
            ).filter(
                Q(end_date__gt=timezone.now()) | Q(end_date__isnull=True)
            ).filter(
                Q(request_users=request.user) | Q(request_groups__in=requester_groups)
            ).distinct().prefetch_related('access_users', 'access_groups')

            for record in base_records:
                target_user_ids = set(record.access_users.values_list('id', flat=True))
                target_user_ids.update(record.access_groups.values_list('user__id', flat=True))
                for user_id in target_user_ids:
                    user_access_record_counts[user_id] += 1

        formatted_users = [{
            'id': cu.user_id,
            'full_name': f"{cu.user.first_name} {cu.user.last_name}".strip() or cu.user.username,
            'email': cu.user.email or '',
            'available_access_records_count': user_access_record_counts.get(cu.user_id, 0),
            'department': (
                cu.department.get_name(current_language)
                if cu.department
                else None
            ),
            'position': (
                cu.position.get_name(current_language)
                if cu.position
                else None
            ),
            'avatar': cu.avatar.url if cu.avatar else None,
            'color': cu.color
        } for cu in cabinet_users]

        # Отримуємо басейни з урахуванням мови
        groups = Group.objects.filter(
            cabinet_details__company_id=company_id
        ).select_related('cabinet_details')

        formatted_groups = [{
            'id': group.id,
            'name': (
                group.cabinet_details.get_name(current_language)
                if hasattr(group, 'cabinet_details')
                else group.name
            )
        } for group in groups]

        # logger.debug(f"Formatted users: {formatted_users}")
        # logger.debug(f"Formatted groups: {formatted_groups}")

        return JsonResponse({
            'users': formatted_users,
            'groups': formatted_groups
        })
    except Exception as e:
        logger.error(f"Error getting users and groups: {str(e)}")
        return JsonResponse({
            'error': str(e)
        }, status=400)


@login_required
@require_POST
def update_access(request):
    try:
        # Check if user can edit access records
        if not can_edit_access_records(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit access records. Please contact your administrator to grant you edit rights.')
            }, status=403)
        
        data = json.loads(request.body)
        access_id = data.get('id')
        description = data.get('description')
        object_ids = data.get('object_ids')
        if object_ids is None:
            legacy_object = data.get('object_id')
            object_ids = [legacy_object] if legacy_object else []
        elif not isinstance(object_ids, list):
            object_ids = [object_ids] if object_ids else []
        object_ids = [oid for oid in object_ids if oid]
        environment = data.get('environment')
        request_users = data.get('request_users', [])
        request_groups = data.get('request_groups', [])
        access_users = data.get('access_users', [])
        access_groups = data.get('access_groups', [])
        roles = data.get('roles', [])

        start_date = data.get('start_date')
        end_date = data.get('end_date')
        third_parties = data.get('third_parties', False)
        is_active = data.get('is_active', True)  # Додаємо обробку поля is_active
        approvers_data = data.get('approvers', [])  # Додаємо дані про approvers

        with transaction.atomic():
            access = SystemAccess.objects.get(id=access_id)
            
            # Check if user has access to the record's company
            user_companies = get_user_companies_for_records(request.user)
            if user_companies.exists() and access.asset.company not in user_companies:
                return JsonResponse({
                    'success': False,
                    'message': _('Access denied - you do not have permission to edit access records for company "{}". Please contact your administrator.').format(access.asset.company.name)
                }, status=403)
            
            primary_object_id = object_ids[0] if object_ids else None
            extra_object_ids = object_ids[1:] if len(object_ids) > 1 else []

            # Перевіряємо, чи змінився об'єкт
            object_changed = access.access_object_id != (primary_object_id if primary_object_id else None)

            # Оновлюємо базові поля
            access.access_object_id = primary_object_id if primary_object_id else None
            access.environment = environment

            access.description = description
            access.start_date = start_date
            access.end_date = end_date
            access.third_parties = third_parties
            access.is_active = is_active  # Встановлюємо значення is_active
            access.modified_by = request.user
            access.save()

            # Оновлюємо зв'язки
            access.request_users.set(request_users)
            access.request_groups.set(request_groups)
            access.access_users.set(access_users)
            access.access_groups.set(access_groups)
            access.roles.set(roles)

            # Додаткові об'єкти — окремі Access Records з тими ж параметрами
            for extra_object_id in extra_object_ids:
                if SystemAccess.objects.filter(
                    asset_id=access.asset_id,
                    access_object_id=extra_object_id,
                    environment=environment,
                ).exists():
                    continue
                _create_system_access_record(
                    request,
                    system_id=access.asset_id,
                    object_id=extra_object_id,
                    environment=environment,
                    role_ids=roles,
                    description=description,
                    start_date=start_date,
                    end_date=end_date,
                    request_users=request_users,
                    request_groups=request_groups,
                    access_users=access_users,
                    access_groups=access_groups,
                    third_parties=third_parties,
                )
            
            # Оновлюємо затверджуючих осіб
            if approvers_data:
                # Якщо передані дані про approvers з frontend, використовуємо їх
                logger.info(f"Updating approvers from frontend data: {approvers_data}")
                
                # Видаляємо існуючих approvers
                access.approvers.all().delete()
                
                # Додаємо нових approvers з переданих даних
                for approver_data in approvers_data:
                    AccessApprover.objects.create(
                        access=access,
                        cabinet_user_id=approver_data['cabinet_user_id'],
                        order=approver_data['order']
                    )
                    
                logger.info(f"Updated {len(approvers_data)} approvers for access {access_id}")
                
            elif object_changed:
                # Якщо об'єкт змінився, використовуємо системні approvers
                logger.info(f"Object changed, updating to system approvers")
                
                # Видаляємо старих затверджуючих осіб
                access.approvers.all().delete()
                
                # Додаємо нових затверджуючих осіб (тільки системні)
                system_approvers = ApprovingPerson.objects.filter(
                    asset_id=access.asset_id,
                    environment=environment
                ).order_by('order')
                approvers_to_add = system_approvers
                logger.info(f"Updated to system approvers for system_id={access.asset_id}, environment={environment}")

                # Створюємо нові записи затверджуючих осіб
                for approver in approvers_to_add:
                    # Перевіряємо, чи не існує вже такий запис
                    existing_approver = AccessApprover.objects.filter(
                        access=access,
                        cabinet_user=approver.cabinet_user
                    ).first()
                    
                    if not existing_approver:
                        AccessApprover.objects.create(
                            access=access,
                            cabinet_user=approver.cabinet_user,
                            order=approver.order
                        )
                        logger.info(f"Created approver record for access_id={access.id}, cabinet_user_id={approver.cabinet_user.id}")
                    else:
                        logger.info(f"Approver record already exists for access_id={access.id}, cabinet_user_id={approver.cabinet_user.id}")

        message = _('Access record updated successfully')
        if len(object_ids) > 1:
            message = _('Access record updated; additional records created for extra objects')

        return JsonResponse({
            'success': True,
            'message': message,
        })

    except SystemAccess.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': _('Access record not found')
        }, status=404)
    except Exception as e:
        logger.error(f"Error updating access record: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
def get_systems_by_company(request):
    company_id = request.GET.get('company_id')

    if not company_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Company ID is required'
        }, status=400)

    try:
        # Використовуємо InformationAsset замість InformationSystem
        systems = InformationAsset.objects.filter(
            company_id=company_id,
            access_manage=True,  # Only include assets marked for access management
            deletion_date__isnull=True  # Only include active assets
        ).select_related('group', 'asset_type')  # змінюємо 'type' на 'asset_type'

        # Format response (AssetGroup/AssetType use name/get_name(), not name_uk)
        systems_data = [{
            'id': system.id,
            'name': system.name,
            'company_id': system.company_id,
            'group_name': system.group.get_name() if system.group else None,
            'type_name': system.asset_type.get_name() if system.asset_type else None,
        } for system in systems]

        return JsonResponse({
            'status': 'success',
            'systems': systems_data
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(['GET'])
def get_company_systems(request):
    company_id = request.GET.get('company_id')
    if not company_id:
        return JsonResponse({'error': _('Company ID is required')}, status=400)

    try:
        # Отримуємо басейни для компанії
        # Filter assets that are marked for access management
        systems = InformationAsset.objects.filter(
            company_id=company_id,
            access_manage=True,  # Only include assets marked for access management
            deletion_date__isnull=True  # Додаємо фільтр для активних систем
        ).values('id', 'name').order_by('name')

        # logger.debug(f"Found systems for company {company_id}: {list(systems)}")

        return JsonResponse({
            'systems': list(systems)
        })
    except Exception as e:
        logger.error(f"Error getting company systems: {str(e)}")
        return JsonResponse({
            'error': _('Error loading systems'),
            'details': str(e)
        }, status=400)

@login_required
def get_company_systems_for_filter(request, company_id):
    """Get information systems for specific company"""
    try:
        logger.info(f"Getting systems for company_id: {company_id}")
        company = get_object_or_404(Company, id=company_id)

        systems = InformationAsset.objects.filter(
            company_id=company_id,
            access_manage=True,  # Only include assets marked for access management
            deletion_date__isnull=True  # Only include active assets
        ).values(
            'id',
            'name',
            'description'
        ).order_by('name')

        # logger.info(f"Found {len(systems)} systems")
        # logger.debug(f"Systems data: {list(systems)}")

        return JsonResponse({
            'status': 'success',
            'data': {
                'systems': list(systems)
            }
        })
    except Exception as e:
        logger.error(f"Error getting company systems for company_id={company_id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)

# access_is Record Active
@login_required
@require_http_methods(['POST'])
def update_access_status(request, access_id):
    try:
        from .email_utils import send_access_status_change_notification
        
        data = json.loads(request.body)
        access = get_object_or_404(SystemAccess, id=access_id)

        # Зберігаємо старий статус для відправки повідомлення
        old_status = 'active' if access.is_active else 'inactive'
        new_status = 'active' if data.get('is_active', False) else 'inactive'

        access.is_active = data.get('is_active', False)
        access.modified_by = request.user
        access.modified_at = timezone.now()
        access.save(update_fields=['is_active', 'modified_by', 'modified_at'])

        logger.info(f"Access status updated for ID {access_id} by {request.user}: is_active={access.is_active}")

        # Відправляємо email повідомлення про зміну статуса тільки якщо статус змінився
        if old_status != new_status:
            try:
                send_access_status_change_notification(
                    access=access,
                    old_status=old_status,
                    new_status=new_status,
                    changed_by=request.user,
                    comment=data.get('comment', '')
                )
                logger.info(f"Status change notification sent for access record {access_id}")
            except Exception as e:
                logger.error(f"Failed to send status change notification for access record {access_id}: {e}")
                # Не зупиняємо процес через помилку email

        return JsonResponse({
            'status': 'success',
            'message': _('Record status updated successfully')
        })
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid request format')
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating access status: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)




@login_required
def get_system_objects(request, system_id):
    """Get objects for a specific system and environment"""
    try:
        current_lang = (get_language() or 'en')[:2].lower()
        if current_lang == 'uk':
            current_lang = 'ua'

        # Get environment from request parameters
        environment = request.GET.get('environment', 'test')
        
        objects = AccessObjectIS.objects.filter(
            asset_id=system_id,
            environment=environment
        ).order_by('tree_id', 'lft')

        objects_data = []
        for obj in objects:
            object_data = {
                'id': obj.id,
                'name': obj.get_name(current_lang) or obj.get_name('en'),
                'description': obj.get_description(current_lang) or obj.get_description('en') or '',
                'color': obj.color,
                'order': obj.order,
                'level': obj.level,
                'parent_id': obj.parent.id if obj.parent else None
            }
            objects_data.append(object_data)

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
def get_object_filters(request, object_id):
    """Get roles and statuses for specific object - only those assigned to the object in access_config_is"""
    try:
        # Отримуємо об'єкт для перевірки
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        
        # Отримуємо тільки ролі, які призначені цьому об'єкту через ObjectRoles
        object_roles = ObjectRoles.objects.filter(
            access_object=access_object,
            is_active=True
        ).select_related('role').order_by('order')
        
        roles = [obj_role.role for obj_role in object_roles]
        
        # Отримуємо всі статуси системи
        statuses = AccessStatus.objects.filter(
            system=access_object.asset
        ).order_by('order')

        return JsonResponse({
            'status': 'success',
            'data': {
                'roles': [{
                    'id': role.id,
                    'name': role.get_name() or role.name or '',
                    'color': role.color,
                    'order': next((obj_role.order for obj_role in object_roles if obj_role.role.id == role.id), 0),
                    'is_object_specific': role.created_for_object_id is not None
                } for role in roles],
                'statuses': [{
                    'id': status.id,
                    'name': status.name or '',
                    'description': status.description or '',
                    'color': status.color,
                    'order': status.order,
                    'is_object_specific': status.created_for_object_id is not None
                } for status in statuses]
            }
        })
    except Exception as e:
        logger.error(f"Error getting object filters: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def update_access_record_approvers(request, access_id):
    """Оновлення approvers для конкретного Access Record"""
    try:
        logger.info(f"Update access approvers request received from user: {request.user.username} for access_id: {access_id}")
        
        # Перевіряємо права доступу
        if not can_edit_access_records(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit access records.')
            }, status=403)
        
        # Отримуємо Access Record
        try:
            access = SystemAccess.objects.get(id=access_id)
        except SystemAccess.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': _('Access record not found')
            }, status=404)
        
        # Перевіряємо доступ до компанії
        user_companies = get_user_companies_for_records(request.user)
        if user_companies.exists() and access.asset.company not in user_companies:
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit access records for company "{}"').format(access.asset.company.name)
            }, status=403)
        
        # Отримуємо дані approvers з запиту
        try:
            raw_approvers_data = request.POST.get('approvers', '[]')
            logger.info(f"Raw approvers data received: {raw_approvers_data}")
            approvers_data = json.loads(raw_approvers_data)
            logger.info(f"Parsed approvers data: {approvers_data}")
            logger.info(f"Number of approvers to save: {len(approvers_data)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return JsonResponse({
                'success': False,
                'message': _('Invalid JSON data in request')
            }, status=400)
        
        with transaction.atomic():
            # Видаляємо всіх поточних approvers
            AccessApprover.objects.filter(access=access).delete()
            logger.info(f"Deleted existing approvers for access_id: {access_id}")
            
            # Додаємо нових approvers
            for approver_data in approvers_data:
                cabinet_user_id = approver_data.get('cabinet_user_id')
                order = approver_data.get('order', 1)
                
                if not cabinet_user_id:
                    continue
                
                try:
                    from app_cabinet.models import CabinetUser
                    cabinet_user = CabinetUser.objects.get(id=cabinet_user_id)
                    
                    # Перевіряємо, чи не існує вже такий approver
                    existing_approver = AccessApprover.objects.filter(
                        access=access,
                        cabinet_user=cabinet_user,
                        order=order
                    ).first()
                    
                    if not existing_approver:
                        AccessApprover.objects.create(
                            access=access,
                            cabinet_user=cabinet_user,
                            order=order
                        )
                        logger.info(f"Created approver: cabinet_user_id={cabinet_user_id}, order={order}")
                    
                except CabinetUser.DoesNotExist:
                    logger.warning(f"CabinetUser with id {cabinet_user_id} not found")
                    continue
                except Exception as e:
                    logger.error(f"Error creating approver: {str(e)}")
                    continue

            # Синхронізуємо схвалювачів у пов'язаних заявках зі статусом Pending,
            # не видаляючи історію погоджень. Замість видалення:
            #  - залишаємо існуючих погоджувачів та оновлюємо їх order,
            #  - для відсутніх у новому списку pending-погоджувачів ставимо статус 'cancelled', додаючи історію,
            #  - створюємо нових погоджувачів зі статусом 'pending'.
            try:
                from .models import AccessRequest, AccessRequestApprover, AccessRequestApproverStatusHistory
                from django.utils import timezone as _tz
                pending_requests = AccessRequest.objects.filter(
                    access_records=access,
                    status='pending'
                ).distinct()
                if pending_requests.exists():
                    logger.info(f"Syncing approvers to {pending_requests.count()} pending access request(s) for access_id={access_id}")

                # Поточний перелік системних погоджувачів
                new_approvers = list(AccessApprover.objects.filter(access=access).order_by('order'))

                for ar in pending_requests:
                    existing = list(AccessRequestApprover.objects.filter(access_request=ar))
                    # Map for fast lookup
                    by_cu_existing = {ra.cabinet_user_id: ra for ra in existing}
                    new_by_cu = {ap.cabinet_user_id: ap for ap in new_approvers}

                    # 1) Cancel pending approvers that were removed
                    for cu_id, ra in by_cu_existing.items():
                        if cu_id not in new_by_cu:
                            if ra.current_status == 'pending':
                                old_status = ra.current_status
                                ra.current_status = 'cancelled'
                                ra.status_comment = 'Cancelled automatically due to approver list change'
                                ra.status_changed_at = _tz.now()
                                ra.status_changed_by = request.user if request.user.is_authenticated else None
                                ra.save(update_fields=['current_status', 'status_comment', 'status_changed_at', 'status_changed_by'])
                                # Історія
                                try:
                                    AccessRequestApproverStatusHistory.objects.create(
                                        request_approver=ra,
                                        old_status=old_status,
                                        new_status='cancelled',
                                        comment=ra.status_comment,
                                        changed_by=ra.status_changed_by
                                    )
                                except Exception:
                                    pass

                    # 2) Update order for still-present approvers
                    for cu_id, ap in new_by_cu.items():
                        if cu_id in by_cu_existing:
                            ra = by_cu_existing[cu_id]
                            if ra.order != ap.order:
                                ra.order = ap.order
                                ra.save(update_fields=['order'])

                    # 3) Create missing request approvers (new ones)
                    for cu_id, ap in new_by_cu.items():
                        if cu_id not in by_cu_existing:
                            AccessRequestApprover.objects.create(
                                access_request=ar,
                                access_approver=ap,
                                cabinet_user=ap.cabinet_user,
                                order=ap.order,
                                current_status='pending'
                            )
                    logger.info(f"Request approvers synced (non-destructive) for access_request_id={ar.id}")
            except Exception as sync_error:
                logger.error(f"Failed to non-destructively sync approvers to pending requests for access_id={access_id}: {sync_error}")
        
        # Перевіряємо скільки approvers було збережено
        final_count = AccessApprover.objects.filter(access=access).count()
        logger.info(f"Final approvers count for access_id {access_id}: {final_count}")
        
        return JsonResponse({
            'success': True,
            'message': _('Approvers updated successfully')
        })
        
    except Exception as e:
        logger.error(f"Error updating access approvers: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
def get_access_approvers(request, access_id):
    """Отримання поточних approvers для Access Record"""
    try:
        # Перевіряємо права доступу
        if not can_edit_access_records(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied')
            }, status=403)
        
        # Отримуємо Access Record
        try:
            access = SystemAccess.objects.get(id=access_id)
        except SystemAccess.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': _('Access record not found')
            }, status=404)
        
        # Перевіряємо доступ до компанії
        user_companies = get_user_companies_for_records(request.user)
        if user_companies.exists() and access.asset.company not in user_companies:
            return JsonResponse({
                'success': False,
                'message': _('Access denied')
            }, status=403)
        
        # Отримуємо approvers
        approvers = AccessApprover.objects.filter(access=access).select_related(
            'cabinet_user__user',
            'cabinet_user__department',
            'cabinet_user__position'
        ).order_by('order')
        
        current_language = get_language()[:2]
        
        approvers_data = []
        for approver in approvers:
            cabinet_user = approver.cabinet_user
            approver_data = {
                'id': approver.id,
                'cabinet_user_id': cabinet_user.id,
                'order': approver.order,
                'current_status': approver.current_status,
                'user': {
                    'id': cabinet_user.user.id,
                    'full_name': cabinet_user.user.get_full_name(),
                    'email': cabinet_user.user.email,
                    'avatar': cabinet_user.avatar.url if cabinet_user.avatar else None,
                    'color': cabinet_user.color
                }
            }
            
            # Додаємо інформацію про департамент/посаду (мова сайту через get_name())
            if cabinet_user.department:
                approver_data['department'] = cabinet_user.department.get_name()
            if cabinet_user.position:
                approver_data['position'] = cabinet_user.position.get_name()
            
            approvers_data.append(approver_data)
        
        return JsonResponse({
            'success': True,
            'approvers': approvers_data
        })
        
    except Exception as e:
        logger.error(f"Error getting access approvers: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
def get_available_approvers(request, access_id):
    """Отримання доступних користувачів для призначення як approvers"""
    try:
        logger.info(f"get_available_approvers called for access_id: {access_id} by user: {request.user.username}")
        
        # Перевіряємо права доступу
        if not can_edit_access_records(request.user):
            logger.warning(f"Access denied for user {request.user.username} to get available approvers")
            return JsonResponse({
                'success': False,
                'message': _('Access denied')
            }, status=403)
        
        # Отримуємо Access Record
        try:
            access = SystemAccess.objects.get(id=access_id)
            logger.info(f"Found access record for company: {access.asset.company.name}")
        except SystemAccess.DoesNotExist:
            logger.error(f"Access record not found for id: {access_id}")
            return JsonResponse({
                'success': False,
                'message': _('Access record not found')
            }, status=404)
        
        # Отримуємо всіх користувачів компанії
        from app_cabinet.models import CabinetUser
        cabinet_users = CabinetUser.objects.filter(
            company=access.asset.company
        ).select_related(
            'user',
            'department',
            'position'
        ).order_by('user__first_name', 'user__last_name')
        
        logger.info(f"Found {cabinet_users.count()} cabinet users for company {access.asset.company.name}")
        
        users_data = []
        for cabinet_user in cabinet_users:
            user_data = {
                'id': cabinet_user.id,
                'full_name': cabinet_user.user.get_full_name(),
                'email': cabinet_user.user.email,
                'avatar': cabinet_user.avatar.url if cabinet_user.avatar else None,
                'color': cabinet_user.color
            }
            if cabinet_user.department:
                user_data['department'] = cabinet_user.department.get_name()
            if cabinet_user.position:
                user_data['position'] = cabinet_user.position.get_name()
            users_data.append(user_data)
        
        logger.info(f"Returning {len(users_data)} users for approvers selection")
        
        return JsonResponse({
            'success': True,
            'users': users_data
        })
        
    except Exception as e:
        logger.error(f"Error getting available approvers: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
def get_system_default_approvers(request, system_id, environment):
    """Отримання default approvers для системи та середовища"""
    try:
        # Перевіряємо права доступу
        if not can_edit_access_records(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied')
            }, status=403)
        
        # Отримуємо default approvers
        from app_cabinet.models import CabinetUser
        approvers = ApprovingPerson.objects.filter(
            asset_id=system_id,
            environment=environment
        ).select_related(
            'cabinet_user__user',
            'cabinet_user__department',
            'cabinet_user__position'
        ).order_by('order')
        
        approvers_data = []
        for approver in approvers:
            cabinet_user = approver.cabinet_user
            approver_data = {
                'id': approver.id,
                'cabinet_user_id': cabinet_user.id,
                'order': approver.order,
                'user': {
                    'id': cabinet_user.user.id,
                    'full_name': cabinet_user.user.get_full_name(),
                    'email': cabinet_user.user.email,
                    'avatar': cabinet_user.avatar.url if cabinet_user.avatar else None,
                    'color': cabinet_user.color
                }
            }
            if cabinet_user.department:
                approver_data['department'] = cabinet_user.department.get_name()
            if cabinet_user.position:
                approver_data['position'] = cabinet_user.position.get_name()
            approvers_data.append(approver_data)
        
        return JsonResponse({
            'success': True,
            'approvers': approvers_data
        })
        
    except Exception as e:
        logger.error(f"Error getting system default approvers: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)

