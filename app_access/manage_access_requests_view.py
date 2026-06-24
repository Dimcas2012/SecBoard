# SecBoard\app_access\manage_is_view.py
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
    SystemAccess, AccessRight, AccessFunctionIS, AccessStatus, 
    ApprovingPerson, AccessApprover, AccessRoles, AccessObjectIS, 
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
from .pagination_utils import ACCESS_TABLE_PAGE_SIZE_OPTIONS, get_access_table_page_size
import json
import time
from app_cabinet.models import CabinetUser, CabinetGroup

logger = logging.getLogger(__name__)


@login_required
def admin_access_requests(request):
    """Render Manage Access Requests with access_records_data for Object Roles column."""
    user = request.user
    if not user.is_authenticated:
        return redirect('login')

    from app_access.models import EmailNotificationHistory
    requests_qs = (
        AccessRequest.objects.select_related('company', 'system', 'requested_by', 'requested_for')
        .prefetch_related(
            'access_records__roles',
            'attachments',
            'request_approvers__cabinet_user__user',
            'admin_status_history',
            Prefetch('email_notifications', queryset=EmailNotificationHistory.objects.select_related('triggered_by', 'mail_account').order_by('-created_at'))
        )
        .order_by('-created_at')
    )

    # Apply filters from query params
    search_query = (request.GET.get('search') or '').strip()
    if search_query and search_query.lower() != 'undefined':
        requests_qs = requests_qs.filter(
            Q(id__icontains=search_query)
            | Q(company__name__icontains=search_query)
            | Q(system__name__icontains=search_query)
            | Q(requested_by__first_name__icontains=search_query)
            | Q(requested_by__last_name__icontains=search_query)
            | Q(requested_for__first_name__icontains=search_query)
            | Q(requested_for__last_name__icontains=search_query)
            | Q(access_records__roles__name__icontains=search_query)
            | Q(access_records__roles__accessrole_name_en__icontains=search_query)
            | Q(access_records__roles__accessrole_name_ru__icontains=search_query)
        ).distinct()

    company_filter = request.GET.get('company')
    if company_filter and company_filter.lower() != 'undefined':
        requests_qs = requests_qs.filter(company_id=company_filter)

    system_filter = request.GET.get('system')
    if system_filter and system_filter.lower() != 'undefined':
        requests_qs = requests_qs.filter(system_id=system_filter)

    environment_filter = request.GET.get('environment')
    if environment_filter and environment_filter.lower() != 'undefined':
        requests_qs = requests_qs.filter(environment=environment_filter)

    # Object filter (by AccessObjectIS via access_records)
    object_filter = request.GET.get('object')
    if object_filter and object_filter.lower() != 'undefined':
        requests_qs = requests_qs.filter(access_records__access_object_id=object_filter).distinct()

    requested_by_filter = request.GET.get('requested_by')
    if requested_by_filter and requested_by_filter.lower() != 'undefined':
        requests_qs = requests_qs.filter(requested_by=requested_by_filter)

    requested_for_filter = request.GET.get('requested_for')
    if requested_for_filter and requested_for_filter.lower() != 'undefined':
        # Support internal users (numeric id) and third-party users (tp:<name>)
        if str(requested_for_filter).startswith('tp:'):
            tp_name = requested_for_filter[3:].strip()
            if tp_name:
                requests_qs = requests_qs.filter(
                    Q(third_party_first_name__icontains=tp_name)
                    | Q(third_party_last_name__icontains=tp_name)
                    | Q(third_party_email__icontains=tp_name)
                    | Q(third_party_organization__icontains=tp_name)
                    | Q(third_party_users_data__icontains=tp_name)
                )
        else:
            requests_qs = requests_qs.filter(requested_for=requested_for_filter)

    owner_filter = request.GET.get('owner')
    if owner_filter and owner_filter.lower() != 'undefined':
        requests_qs = requests_qs.filter(system__owners__cabinet_user__user=owner_filter)

    administrator_filter = request.GET.get('administrator')
    if administrator_filter and administrator_filter.lower() != 'undefined':
        requests_qs = requests_qs.filter(system__administrators__cabinet_user__user=administrator_filter)

    role_filter = request.GET.get('role')
    if role_filter and role_filter.lower() != 'undefined':
        # Support both role id and role name to allow UI to de-duplicate by name
        if str(role_filter).isdigit():
            requests_qs = requests_qs.filter(access_records__roles=int(role_filter)).distinct()
        else:
            requests_qs = requests_qs.filter(
                Q(access_records__roles__name__iexact=role_filter)
                | Q(access_records__roles__accessrole_name_en__iexact=role_filter)
                | Q(access_records__roles__accessrole_name_ru__iexact=role_filter)
            ).distinct()

    # Removed Access Records Period filter per request

    user_period = request.GET.get('user_period')
    if user_period and user_period.lower() != 'undefined':
        now = timezone.now()
        if user_period == 'active':
            requests_qs = requests_qs.filter(Q(end_date__gt=now) | Q(end_date__isnull=True), start_date__lte=now)
        elif user_period == 'expired':
            requests_qs = requests_qs.filter(end_date__lte=now)
        elif user_period == 'future':
            requests_qs = requests_qs.filter(start_date__gt=now)

    approving_status_filter = request.GET.get('approving_status')
    if approving_status_filter and approving_status_filter.lower() != 'undefined':
        requests_qs = requests_qs.filter(request_approvers__current_status=approving_status_filter).distinct()

    # Admin status filter
    admin_status_filter = request.GET.get('admin_status')
    if admin_status_filter and admin_status_filter.lower() != 'undefined':
        requests_qs = requests_qs.filter(admin_status=admin_status_filter)

    # Pagination (default 25 per page)
    page = request.GET.get('page', 1)
    page_size = get_access_table_page_size(request)
    paginator = Paginator(requests_qs, page_size)
    try:
        page_obj = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    current_language = get_language()[:2]
    # Companies allowed for this user by AccessISAM (Chosen Companies)
    user_companies = get_user_companies_for_manage_ar(user)
    # Build dropdown datasets based on the filtered set
    systems_in_requests = requests_qs.values_list('system', flat=True).distinct()
    owners = User.objects.filter(
        cabinet__assetowner__owned_assets__in=systems_in_requests
    ).distinct().order_by('first_name', 'last_name')
    administrators = User.objects.filter(
        cabinet__assetadministrator__administered_assets__in=systems_in_requests
    ).distinct().order_by('first_name', 'last_name')
    requested_by_users = User.objects.filter(
        access_requests_by__in=requests_qs
    ).distinct().order_by('first_name', 'last_name')
    requested_for_users = User.objects.filter(
        access_requests_for__in=requests_qs
    ).distinct().order_by('first_name', 'last_name')

    # Build third-party names options from current query set
    third_party_requested_for_options = []
    try:
        # Single third-party fields
        tp_rows = requests_qs.values('third_party_first_name', 'third_party_last_name', 'third_party_email')
        tp_names = set()
        for r in tp_rows:
            fn = (r.get('third_party_first_name') or '').strip()
            ln = (r.get('third_party_last_name') or '').strip()
            full = f"{fn} {ln}".strip()
            if full:
                tp_names.add(full)
            elif r.get('third_party_email'):
                tp_names.add(r['third_party_email'])
        # JSON third-party users
        for raw in requests_qs.values_list('third_party_users_data', flat=True):
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(data, list):
                    for u in data:
                        if isinstance(u, dict):
                            fn = (u.get('first_name') or u.get('firstName') or u.get('fname') or '').strip()
                            ln = (u.get('last_name') or u.get('lastName') or u.get('lname') or '').strip()
                            full = f"{fn} {ln}".strip() or u.get('user_display_name') or u.get('name') or u.get('email')
                            if full:
                                tp_names.add(full)
            except Exception:
                continue
        third_party_requested_for_options = sorted(tp_names)
    except Exception:
        third_party_requested_for_options = []

    # Build roles list to include all available roles in the selected scope,
    # not only those already used in the currently filtered requests
    from app_asset.models import InformationAsset as IA
    if system_filter and system_filter.lower() != 'undefined':
        systems_scope = IA.objects.filter(id=system_filter)
    elif company_filter and company_filter.lower() != 'undefined':
        systems_scope = IA.objects.filter(company_id=company_filter)
    else:
        # Fallback: all systems from user's allowed companies
        systems_scope = IA.objects.filter(company__in=user_companies)

    roles = AccessRoles.objects.filter(system__in=systems_scope, is_active=True)
    if environment_filter and environment_filter.lower() != 'undefined':
        roles = roles.filter(environment=environment_filter)
    if object_filter and object_filter.lower() != 'undefined':
        roles = roles.filter(Q(is_object_specific=False) | Q(created_for_object_id=object_filter))
    else:
        roles = roles.filter(is_object_specific=False)
    roles = roles.distinct().order_by('order', 'name', 'code')

    # Build unique role names for dropdown to avoid duplicates
    lang_code = 'ua' if current_language == 'uk' else current_language
    role_names_seen = set()
    role_options = []
    for r in roles:
        try:
            name = r.get_name(lang_code)
        except Exception:
            name = getattr(r, 'name', '') or (r.get_name() if hasattr(r, 'get_name') else '')
        if name and name not in role_names_seen:
            role_options.append({'value': name, 'label': name})
            role_names_seen.add(name)
    environments_in_requests = requests_qs.values_list('environment', flat=True).distinct()
    environment_choices = [choice for choice in AccessRequest.ENVIRONMENT_CHOICES if choice[0] in environments_in_requests]
    # Admin status choices: show all available values
    admin_status_choices = list(AccessRequest.ADMIN_STATUS_CHOICES)
    # Objects available within the filtered set
    from app_access.models import AccessObjectIS  # local import to avoid circulars if any
    objects = AccessObjectIS.objects.filter(
        id__in=requests_qs.values_list('access_records__access_object', flat=True)
    ).distinct().order_by('name')

    formatted_requests = []
    for req in page_obj:
        access_records_data = []
        for access_record in req.access_records.all():
            # Localized roles + revoked state per role (like My Access Requests)
            roles_payload = []
            # Determine target user email for chronology checks
            target_email = None
            is_third_party_user = False
            try:
                if getattr(req, 'third_party_email', None):
                    target_email = req.third_party_email
                    is_third_party_user = True
                elif req.requested_for:
                    target_email = req.requested_for.email
            except Exception:
                target_email = None

            any_role_revoked = False
            for role in access_record.roles.all():
                if current_language == 'uk':
                    role_name = role.name or (role.get_name() if hasattr(role, 'get_name') else '')
                elif current_language == 'ru':
                    role_name = role.name or (role.get_name() if hasattr(role, 'get_name') else '')
                else:
                    role_name = role.name or (role.get_name() if hasattr(role, 'get_name') else '')

                # Check if this specific role from this access record is revoked (using FULL sequence logic like My Access Requests)
                role_revoked = False
                try:
                    # Only grant requests can be revoked
                    if req.request_type == 'grant':
                        # Use the same comprehensive logic as in user_access_request
                        # Look for sequence records for this access record and grant request
                        sequence_record = AccessRequestSequence.objects.filter(
                            access_record=access_record,
                            grant_request=req
                        ).order_by('order_number').first()
                        
                        if sequence_record:
                            # Check if this sequence is revoked and matches user
                            if req.request_type == 'grant' and sequence_record.revoke_request and sequence_record.revoke_request.admin_status == 'granted':
                                revoke_request = sequence_record.revoke_request
                                
                                # Перевіряємо, чи revoke стосується того ж користувача, що і grant
                                grant_user_email = None
                                revoke_user_email = None
                                
                                if req.third_party_email:
                                    grant_user_email = req.third_party_email
                                elif req.requested_for:
                                    grant_user_email = req.requested_for.email
                                
                                if revoke_request.third_party_email:
                                    revoke_user_email = revoke_request.third_party_email
                                elif revoke_request.requested_for:
                                    revoke_user_email = revoke_request.requested_for.email
                                
                                # Only mark as revoked if it's for the same user
                                if grant_user_email and revoke_user_email and grant_user_email == revoke_user_email:
                                    role_revoked = True
                                    any_role_revoked = True
                        else:
                            # Auto-create missing sequence if needed (same as user_access_request)
                            if req.status == 'approved' and req.admin_status == 'granted':
                                try:
                                    from django.db import models
                                    max_order = AccessRequestSequence.objects.filter(
                                        grant_request=req
                                    ).aggregate(models.Max('order_number'))['order_number__max'] or 0
                                    order_number = max_order + 1
                                    
                                    sequence_record = AccessRequestSequence.objects.create(
                                        grant_request=req,
                                        access_record=access_record,
                                        order_number=order_number,
                                        sequence_status='active'
                                    )
                                    logger.info(f"[Manage-Role] Auto-created missing AccessRequestSequence {access_record.id}.{req.id}.{order_number}")
                                except Exception as e:
                                    logger.error(f"[Manage-Role] Failed to auto-create AccessRequestSequence: {str(e)}")
                            
                            # Fallback: check by sequence_id pattern with comprehensive user matching
                            grant_access_record_id = f"{access_record.id}.{req.id}"
                            seq_rev = AccessRequestSequence.objects.filter(
                                sequence_id__startswith=f"{grant_access_record_id}.",
                                sequence_status='revoked',
                                revoke_request__isnull=False,
                                revoke_request__admin_status='granted'
                            ).order_by('-revoked_at').first()
                            
                            if seq_rev:
                                revoke_request = seq_rev.revoke_request
                                
                                # Перевіряємо, чи revoke стосується того ж користувача, що і grant
                                grant_user_email = None
                                revoke_user_email = None
                                
                                if req.third_party_email:
                                    grant_user_email = req.third_party_email
                                elif req.requested_for:
                                    grant_user_email = req.requested_for.email
                                
                                if revoke_request.third_party_email:
                                    revoke_user_email = revoke_request.third_party_email
                                elif revoke_request.requested_for:
                                    revoke_user_email = revoke_request.requested_for.email
                                
                                # Only mark as revoked if it's for the same user
                                if grant_user_email and revoke_user_email and grant_user_email == revoke_user_email:
                                    role_revoked = True
                                    any_role_revoked = True
                            else:
                                # Additional fallback: search by Grant Access Record ID in revoked_grant_access_record_ids
                                existing_rr = AccessRequest.objects.filter(
                                    request_type='revoke',
                                    admin_status='granted',
                                    revoked_grant_access_record_ids__contains=[grant_access_record_id]
                                ).order_by('-created_at').first()
                                
                                if existing_rr:
                                    revoke_request = existing_rr
                                    
                                    # Перевіряємо, чи revoke стосується того ж користувача, що і grant
                                    grant_user_email = None
                                    revoke_user_email = None
                                    
                                    if req.third_party_email:
                                        grant_user_email = req.third_party_email
                                    elif req.requested_for:
                                        grant_user_email = req.requested_for.email
                                    
                                    if revoke_request.third_party_email:
                                        revoke_user_email = revoke_request.third_party_email
                                    elif revoke_request.requested_for:
                                        revoke_user_email = revoke_request.requested_for.email
                                    
                                    # Only mark as revoked if it's for the same user
                                    if grant_user_email and revoke_user_email and grant_user_email == revoke_user_email:
                                        role_revoked = True
                                        any_role_revoked = True
                except Exception as e:
                    logger.error(f"[Manage-Role] Error checking revoke status for role {role.id}: {str(e)}")

                roles_payload.append({
                    'id': role.id,
                    'name': role_name,
                    'color': role.color or '#6c757d',
                    'is_revoked': role_revoked,
                })

            obj = getattr(access_record, 'access_object', None)
            if obj:
                object_name = obj.get_name(current_language) if hasattr(obj, 'get_name') else getattr(obj, 'object_name_ua', '')
                object_color = getattr(obj, 'color', '#6c757d')
            else:
                object_name = _('No Object')
                object_color = '#6c757d'

            # Determine grant access record id (A.B.C) and full id (A.B.C.D)
            grant_access_record_id = None
            grant_access_record_id_full = None
            is_revoked = False
            revoke_info = None

            try:
                sequence_record = None
                # Resolve sequence record for grant requests
                if req.request_type == 'grant':
                    sequence_record = AccessRequestSequence.objects.filter(
                        access_record=access_record,
                        grant_request=req
                    ).order_by('order_number').first()

                    # Debug logging for sequence lookup
                    sequence_count = AccessRequestSequence.objects.filter(
                        access_record=access_record,
                        grant_request=req
                    ).count()
                    logger.info(
                        f"[Manage] Sequence lookup for Grant Request {req.id}, Access Record {access_record.id}: "
                        f"found {sequence_count} sequences, first sequence: "
                        f"{sequence_record.sequence_id if sequence_record else 'None'}"
                    )

                    # Fallback: prefix search A.B.*
                    if not sequence_record:
                        sequence_record = AccessRequestSequence.objects.filter(
                            sequence_id__startswith=f"{access_record.id}.{req.id}.",
                            grant_request=req
                        ).order_by('order_number').first()

                        if sequence_record:
                            logger.info(f"[Manage] Found sequence by prefix search: {sequence_record.sequence_id}")
                        else:
                            logger.warning(
                                f"[Manage] No AccessRequestSequence found for Grant Request {req.id}, Access Record {access_record.id}"
                            )
                            # Auto-create missing sequence for approved+granted grants
                            if req.status == 'approved' and req.admin_status == 'granted':
                                try:
                                    from django.db import models
                                    max_order = (
                                        AccessRequestSequence.objects.filter(grant_request=req)
                                        .aggregate(models.Max('order_number'))['order_number__max']
                                        or 0
                                    )
                                    order_number = max_order + 1
                                    sequence_record = AccessRequestSequence.objects.create(
                                        grant_request=req,
                                        access_record=access_record,
                                        order_number=order_number,
                                        sequence_status='active'
                                    )
                                    logger.info(
                                        f"[Manage] Auto-created missing AccessRequestSequence "
                                        f"{access_record.id}.{req.id}.{order_number} for Grant Request {req.id}, "
                                        f"Access Record {access_record.id}"
                                    )
                                except Exception as e2:
                                    logger.error(
                                        f"[Manage] Failed to auto-create AccessRequestSequence for Grant Request {req.id}, "
                                        f"Access Record {access_record.id}: {str(e2)}"
                                    )

                if sequence_record:
                    seq_id_str = str(sequence_record.sequence_id)
                    grant_access_record_id = '.'.join(seq_id_str.split('.')[:3])
                    # Full ID: add D-part (0 if active, or revoke request id)
                    if sequence_record.sequence_status == 'revoked' and sequence_record.revoke_request:
                        grant_access_record_id_full = f"{grant_access_record_id}.{sequence_record.revoke_request.id}"
                        if req.request_type == 'grant' and sequence_record.revoke_request.admin_status == 'granted':
                            is_revoked = True
                            revoke_request = sequence_record.revoke_request
                            revoked_for_correct = None
                            if revoke_request.third_party_email:
                                revoked_for_correct = (
                                    f"{revoke_request.third_party_first_name} {revoke_request.third_party_last_name}".strip()
                                )
                            elif revoke_request.requested_for:
                                revoked_for_correct = revoke_request.requested_for.get_full_name()
                            revoke_info = {
                                'revoked_at': getattr(sequence_record, 'revoked_at', None) or revoke_request.created_at,
                                'revoked_by': revoke_request.requested_by.get_full_name() if revoke_request.requested_by else 'System',
                                'revoked_for': revoked_for_correct,
                                'revoke_request_id': revoke_request.id,
                                'change_reason': 'Access revoked for this grant sequence',
                            }
                    else:
                        grant_access_record_id_full = f"{grant_access_record_id}.0"
            except Exception as e:
                logger.error(
                    f"[Manage] Failed to resolve Grant Access Record ID for request {req.id}, record {access_record.id}: {str(e)}"
                )

                # Перевірка по послідовності для рядків Grant: базуємось на повному Grant Access Record ID (A.B.C.D)
                if not is_revoked and req.request_type == 'grant' and grant_access_record_id:
                    try:
                        seq_rev = AccessRequestSequence.objects.filter(
                            sequence_id__startswith=f"{grant_access_record_id}.",
                            sequence_status='revoked',
                            revoke_request__isnull=False,
                            revoke_request__admin_status='granted'
                        ).order_by('-revoked_at').first()
                        if seq_rev:
                            revoke_request = seq_rev.revoke_request
                            
                            # Перевіряємо, чи revoke стосується того ж користувача, що і grant
                            grant_user_email = None
                            revoke_user_email = None
                            
                            if req.third_party_email:
                                grant_user_email = req.third_party_email
                            elif req.requested_for:
                                grant_user_email = req.requested_for.email
                            
                            if revoke_request.third_party_email:
                                revoke_user_email = revoke_request.third_party_email
                            elif revoke_request.requested_for:
                                revoke_user_email = revoke_request.requested_for.email
                            
                            # Тільки позначаємо як revoked, якщо це стосується того ж користувача
                            if grant_user_email and revoke_user_email and grant_user_email == revoke_user_email:
                                is_revoked = True
                                revoked_for_correct = None
                                if revoke_request.third_party_email:
                                    revoked_for_correct = f"{revoke_request.third_party_first_name} {revoke_request.third_party_last_name}".strip()
                                elif revoke_request.requested_for:
                                    revoked_for_correct = revoke_request.requested_for.get_full_name()
                                revoke_info = {
                                    'revoked_at': getattr(seq_rev, 'revoked_at', None) or revoke_request.created_at,
                                    'revoked_by': revoke_request.requested_by.get_full_name() if revoke_request.requested_by else 'System',
                                    'revoked_for': revoked_for_correct,
                                    'revoke_request_id': revoke_request.id,
                                    'change_reason': 'Access revoked for this grant sequence'
                                }
                        else:
                            # Фолбек: якщо немає revoke_request (дані старих записів), але послідовність має статус revoked
                            seq_rev2 = AccessRequestSequence.objects.filter(
                                sequence_id__startswith=f"{grant_access_record_id}.",
                                sequence_status='revoked'
                            ).order_by('-revoked_at').first()
                            if seq_rev2:
                                is_revoked = True
                                revoke_info = {
                                    'revoked_at': getattr(seq_rev2, 'revoked_at', None),
                                    'revoked_by': 'System',
                                    'revoked_for': None,
                                    'revoke_request_id': getattr(seq_rev2.revoke_request, 'id', None),
                                    'change_reason': 'Access revoked (no linked request)'
                                }
                            else:
                                # Додатковий фолбек: шукаємо Revoke запити, які містять цей Grant Access Record ID у списку
                                existing_rr = AccessRequest.objects.filter(
                                    request_type='revoke',
                                    admin_status='granted',
                                    revoked_grant_access_record_ids__contains=[grant_access_record_id]
                                ).order_by('-created_at').first()
                                if existing_rr:
                                    revoke_request = existing_rr
                                    
                                    # Перевіряємо, чи revoke стосується того ж користувача, що і grant
                                    grant_user_email = None
                                    revoke_user_email = None
                                    
                                    if req.third_party_email:
                                        grant_user_email = req.third_party_email
                                    elif req.requested_for:
                                        grant_user_email = req.requested_for.email
                                    
                                    if revoke_request.third_party_email:
                                        revoke_user_email = revoke_request.third_party_email
                                    elif revoke_request.requested_for:
                                        revoke_user_email = revoke_request.requested_for.email
                                    
                                    # Тільки позначаємо як revoked, якщо це стосується того ж користувача
                                    if grant_user_email and revoke_user_email and grant_user_email == revoke_user_email:
                                        is_revoked = True
                                        revoked_for_correct = None
                                        if revoke_request.third_party_email:
                                            revoked_for_correct = f"{revoke_request.third_party_first_name} {revoke_request.third_party_last_name}".strip()
                                        elif revoke_request.requested_for:
                                            revoked_for_correct = revoke_request.requested_for.get_full_name()
                                        revoke_info = {
                                            'revoked_at': revoke_request.created_at,
                                            'revoked_by': revoke_request.requested_by.get_full_name() if revoke_request.requested_by else 'System',
                                            'revoked_for': revoked_for_correct,
                                            'revoke_request_id': revoke_request.id,
                                            'change_reason': 'Access revoked for this grant sequence'
                                        }
                    except Exception as e:
                        logger.error(f"[Manage] Sequence revoke check by full ID failed for request {req.id}, record {access_record.id}: {str(e)}")
                    # Revocation state for this grant (if later revoked) - WITH USER MATCHING
                    if grant_access_record_id:
                        revoked_seq = (
                            AccessRequestSequence.objects.filter(
                                sequence_id__startswith=f"{grant_access_record_id}.",
                                sequence_status='revoked',
                                revoke_request__admin_status='granted',
                            )
                            .order_by('-revoked_at')
                            .first()
                        )
                        if revoked_seq:
                            revoke_req = revoked_seq.revoke_request
                            
                            # Перевіряємо, чи revoke стосується того ж користувача, що і grant
                            grant_user_email = None
                            revoke_user_email = None
                            
                            if req.third_party_email:
                                grant_user_email = req.third_party_email
                            elif req.requested_for:
                                grant_user_email = req.requested_for.email
                            
                            if revoke_req.third_party_email:
                                revoke_user_email = revoke_req.third_party_email
                            elif revoke_req.requested_for:
                                revoke_user_email = revoke_req.requested_for.email
                            
                            # Only mark as revoked if it's for the same user
                            if grant_user_email and revoke_user_email and grant_user_email == revoke_user_email:
                                is_revoked = True
                                revoke_for = None
                                if revoke_req.third_party_first_name or revoke_req.third_party_last_name:
                                    revoke_for = f"{revoke_req.third_party_first_name} {revoke_req.third_party_last_name}".strip()
                                elif revoke_req.requested_for:
                                    revoke_for = revoke_req.requested_for.get_full_name()
                                revoke_info = {
                                    'revoked_at': revoked_seq.revoked_at or revoke_req.created_at,
                                    'revoked_by': revoke_req.requested_by.get_full_name() if revoke_req.requested_by else 'System',
                                    'revoked_for': revoke_for,
                                    'revoke_request_id': revoke_req.id,
                                    'change_reason': 'Access revoked for this grant sequence',
                                }
                    # Fallback: if sequence not resolved, attempt direct lookup by synthetic id WITH USER MATCHING
                    if not is_revoked and not grant_access_record_id:
                        try:
                            synthetic_id = f"{access_record.id}.{req.id}.1"
                            revoked_seq = (
                                AccessRequestSequence.objects.filter(
                                    sequence_id__startswith=f"{synthetic_id}.",
                                    sequence_status='revoked',
                                    revoke_request__admin_status='granted',
                                )
                                .order_by('-revoked_at')
                                .first()
                            )
                            if revoked_seq:
                                revoke_req = revoked_seq.revoke_request
                                
                                # Перевіряємо, чи revoke стосується того ж користувача, що і grant
                                grant_user_email = None
                                revoke_user_email = None
                                
                                if req.third_party_email:
                                    grant_user_email = req.third_party_email
                                elif req.requested_for:
                                    grant_user_email = req.requested_for.email
                                
                                if revoke_req.third_party_email:
                                    revoke_user_email = revoke_req.third_party_email
                                elif revoke_req.requested_for:
                                    revoke_user_email = revoke_req.requested_for.email
                                
                                # Only mark as revoked if it's for the same user
                                if grant_user_email and revoke_user_email and grant_user_email == revoke_user_email:
                                    is_revoked = True
                                    revoke_for = None
                                    if revoke_req.third_party_first_name or revoke_req.third_party_last_name:
                                        revoke_for = f"{revoke_req.third_party_first_name} {revoke_req.third_party_last_name}".strip()
                                    elif revoke_req.requested_for:
                                        revoke_for = revoke_req.requested_for.get_full_name()
                                    revoke_info = {
                                        'revoked_at': revoked_seq.revoked_at or revoke_req.created_at,
                                        'revoked_by': revoke_req.requested_by.get_full_name() if revoke_req.requested_by else 'System',
                                        'revoked_for': revoke_for,
                                        'revoke_request_id': revoke_req.id,
                                        'change_reason': 'Access revoked for this grant sequence',
                                    }
                        except Exception:
                            pass
                else:
                    # Revoke request: find sequences revoked by this request for this access_record
                    revoked_seq = (
                        AccessRequestSequence.objects.filter(
                            access_record=access_record,
                            revoke_request=req,
                            sequence_status='revoked',
                        )
                        .order_by('-revoked_at')
                        .first()
                    )
                    if revoked_seq:
                        parts = str(revoked_seq.sequence_id).split('.')
                        if len(parts) >= 3:
                            grant_access_record_id = '.'.join(parts[:3])
                            grant_access_record_id_full = str(revoked_seq.sequence_id)
                        is_revoked = True
                        revoke_req = revoked_seq.revoke_request
                        revoke_for = None
                        if revoke_req:
                            if revoke_req.third_party_first_name or revoke_req.third_party_last_name:
                                revoke_for = f"{revoke_req.third_party_first_name} {revoke_req.third_party_last_name}".strip()
                            elif revoke_req.requested_for:
                                revoke_for = revoke_req.requested_for.get_full_name()
                        revoke_info = {
                            'revoked_at': revoked_seq.revoked_at or (revoke_req.created_at if revoke_req else None),
                            'revoked_by': revoke_req.requested_by.get_full_name() if revoke_req and revoke_req.requested_by else 'System',
                            'revoked_for': revoke_for,
                            'revoke_request_id': revoke_req.id if revoke_req else None,
                            'change_reason': 'Access revoked for this grant sequence',
                        }
                    else:
                        # Fallback by suffix .<revoke_id>
                        revoked_seq = (
                            AccessRequestSequence.objects.filter(
                                sequence_id__endswith=f".{req.id}",
                                access_record=access_record,
                            )
                            .order_by('-revoked_at')
                            .first()
                        )
                        if revoked_seq:
                            parts = str(revoked_seq.sequence_id).split('.')
                            if len(parts) >= 3:
                                grant_access_record_id = '.'.join(parts[:3])
                                grant_access_record_id_full = str(revoked_seq.sequence_id)
                            is_revoked = True
            except Exception:
                pass

            # Additional fallback for Grant requests when grant_access_record_id is still None
            if req.request_type == 'grant' and not is_revoked and not grant_access_record_id:
                try:
                    # Search for any revoke request targeting this grant request specifically
                    fallback_revoke = AccessRequest.objects.filter(
                        request_type='revoke',
                        admin_status='granted',
                        notes__icontains=f'request #{req.id}'
                    ).first()
                    
                    if fallback_revoke:
                        # Check if it's for the same user
                        grant_user_email = None
                        revoke_user_email = None
                        
                        if req.third_party_email:
                            grant_user_email = req.third_party_email
                        elif req.requested_for:
                            grant_user_email = req.requested_for.email
                        
                        if fallback_revoke.third_party_email:
                            revoke_user_email = fallback_revoke.third_party_email
                        elif fallback_revoke.requested_for:
                            revoke_user_email = fallback_revoke.requested_for.email
                        
                        if grant_user_email and revoke_user_email and grant_user_email == revoke_user_email:
                            # Check if this access record is mentioned in the revoke
                            if fallback_revoke.access_records.filter(id=access_record.id).exists():
                                is_revoked = True
                                revoke_info = {
                                    'revoked_at': fallback_revoke.created_at,
                                    'revoked_by': fallback_revoke.requested_by.get_full_name() if fallback_revoke.requested_by else 'System',
                                    'revoked_for': f"{fallback_revoke.third_party_first_name} {fallback_revoke.third_party_last_name}".strip() if fallback_revoke.third_party_first_name else (fallback_revoke.requested_for.get_full_name() if fallback_revoke.requested_for else None),
                                    'revoke_request_id': fallback_revoke.id,
                                    'change_reason': 'Access revoked (fallback detection)'
                                }
                                logger.info(f"[Manage] Fallback revoke detection found for Grant Request {req.id}, Access Record {access_record.id}")
                except Exception as e:
                    logger.error(f"[Manage] Fallback revoke detection error: {str(e)}")
            # Debug logging for Grant access records revoke status (Manage Access Requests)
            if req.request_type == 'grant':
                logger.info(f"[Manage] Grant Record Debug - Request {req.id}, Access Record {access_record.id}: is_revoked={is_revoked or any_role_revoked}, grant_access_record_id={grant_access_record_id}, user={req.third_party_email or (req.requested_for.email if req.requested_for else 'None')}")
                if revoke_info:
                    logger.info(f"[Manage]   Revoke info: {revoke_info}")

            access_records_data.append({
                'id': access_record.id,
                'object_id': obj.id if obj else None,
                'object_name': object_name,
                'object_color': object_color,
                'roles': roles_payload,
                # Mark record revoked if any role for this record is chronologically revoked
                'is_revoked': is_revoked or any_role_revoked,
                'revoke_info': revoke_info,
                'grant_access_record_id': grant_access_record_id,
                'grant_access_record_id_full': grant_access_record_id_full,
            })

        # Place revoked access records at the bottom for Grant requests
        if req.request_type == 'grant':
            try:
                access_records_data.sort(key=lambda item: item.get('is_revoked', False))
            except Exception:
                pass

        # Build third-party users list (helper)
        raw_tp = getattr(req, 'third_party_users_data', None)
        if isinstance(raw_tp, str):
            try:
                parsed_tp = json.loads(raw_tp)
            except Exception:
                parsed_tp = None
        else:
            parsed_tp = raw_tp

        def map_tp_entry(entry):
            if not isinstance(entry, dict):
                return ''
            first_name = (entry.get('first_name') or entry.get('firstName') or entry.get('fname') or '').strip()
            last_name = (entry.get('last_name') or entry.get('lastName') or entry.get('lname') or '').strip()
            full_name = f"{first_name} {last_name}".strip()
            return full_name or entry.get('user_display_name') or entry.get('name') or entry.get('email') or ''

        third_party_users_list = []
        if isinstance(parsed_tp, list):
            third_party_users_list = [map_tp_entry(u) for u in parsed_tp]
        elif hasattr(req, 'third_party_users'):
            third_party_users_list = [
                (f"{(getattr(u, 'first_name', '') or '').strip()} {(getattr(u, 'last_name', '') or '').strip()}".strip() or getattr(u, 'email', ''))
                for u in req.third_party_users.all()
            ]

        # Build approval history text for tooltip (same approach as My Access Requests)
        approval_history_text = None
        try:
            events = []
            # Current per-request approvers with their status history
            if hasattr(req, 'request_approvers') and req.request_approvers.exists():
                for ra in req.request_approvers.all().order_by('order'):
                    history_qs = getattr(ra, 'status_history', None)
                    if history_qs is not None:
                        for h in history_qs.all().order_by('changed_at'):
                            approver_name = ra.cabinet_user.user.get_full_name() if getattr(ra.cabinet_user, 'user', None) else ''
                            changer_name = h.changed_by.get_full_name() if h.changed_by else ''
                            from django.utils import timezone as _tz
                            ts = _tz.localtime(h.changed_at).strftime('%d.%m.%Y %H:%M')
                            events.append((h.changed_at, ra.order, f"Lvl {ra.order}: {approver_name} → {h.new_status.title()} ({ts} by {changer_name})"))
                    else:
                        approver_name = ra.cabinet_user.user.get_full_name() if getattr(ra.cabinet_user, 'user', None) else ''
                        events.append((None, ra.order, f"Lvl {ra.order}: {approver_name} - {ra.current_status.title()}"))

            # Snapshot history bound directly to the request (covers removed/replaced approvers)
            try:
                from .models import AccessRequestApproverStatusHistory as ARASH
                snapshot_qs = ARASH.objects.filter(access_request=req).order_by('changed_at')
                from django.utils import timezone as _tz
                for h in snapshot_qs:
                    approver_name = h.approver_name or (h.approver_cabinet_user.user.get_full_name() if h.approver_cabinet_user and getattr(h.approver_cabinet_user, 'user', None) else '')
                    changer_name = h.changed_by.get_full_name() if h.changed_by else ''
                    ts = _tz.localtime(h.changed_at).strftime('%d.%m.%Y %H:%M')
                    order_num = getattr(h, 'order_at_change', None) or 0
                    events.append((h.changed_at, order_num, f"Lvl {order_num}: {approver_name} → {h.new_status.title()} ({ts} by {changer_name})"))
            except Exception:
                pass

            if events:
                events.sort(key=lambda x: (x[0] is None, x[0] or 0, x[1] or 0))
                approval_history_text = " | ".join([e[2] for e in events])
            else:
                # Fallback: list current approvers and their current status
                if hasattr(req, 'request_approvers') and req.request_approvers.exists():
                    lines = []
                    for ra in req.request_approvers.all().order_by('order'):
                        name = ra.cabinet_user.user.get_full_name() if getattr(ra.cabinet_user, 'user', None) else ''
                        lines.append(f"Lvl {ra.order}: {name} - {ra.current_status.title()}")
                    if lines:
                        approval_history_text = " | ".join(lines)
        except Exception:
            approval_history_text = None

        formatted_requests.append({
            'id': req.id,
            'company': req.company,
            'system': req.system,
            'access_records': req.access_records,
            'access_records_data': access_records_data,
            'requested_by': req.requested_by,
            'requested_for': req.requested_for,
            # Third-party (single user)
            'third_party_first_name': getattr(req, 'third_party_first_name', ''),
            'third_party_last_name': getattr(req, 'third_party_last_name', ''),
            'third_party_email': getattr(req, 'third_party_email', ''),
            'third_party_phone': getattr(req, 'third_party_phone', ''),
            'third_party_organization': getattr(req, 'third_party_organization', ''),
            'third_party_description': getattr(req, 'third_party_description', ''),
            # Third-party (multiple users)
            'third_party_users_list': third_party_users_list,
            'request_type': req.request_type,
            'status': req.status,
            'admin_status': req.admin_status,
            'environment': req.environment,
            'start_date': req.start_date,
            'end_date': req.end_date,
            'justification': req.justification,
            'requirements': req.requirements,
            'notes': req.notes,
            'email_notifications': list(getattr(req, 'email_notifications').all().order_by('-created_at')[:5]) if hasattr(req, 'email_notifications') else [],
            'created_at': req.created_at,
            'attachments': req.attachments,
            'request_approvers': req.request_approvers,
            'admin_status_history': req.admin_status_history.all(),
            'approval_history_text': approval_history_text,
        })

    context = {
        'requests': formatted_requests,
        'companies': user_companies,
        'systems': InformationAsset.objects.filter(
            id__in=requests_qs.values_list('system_id', flat=True).distinct()
        ).order_by('name'),
        'objects': objects,
        'roles': roles,
        'role_options': role_options,
        'requested_by_users': requested_by_users,
        'requested_for_users': requested_for_users,
        'third_party_requested_for_options': third_party_requested_for_options,
        'owners': owners,
        'administrators': administrators,
        'environment_choices': environment_choices,
        'admin_status_choices': admin_status_choices,
        'current_language': current_language,
        'current_user': user,
        'can_add_manage_ar': True,
        'can_edit_manage_ar': True,
        'can_delete_manage_ar': True,
        # Pagination context expected by template
        'paginator': paginator,
        'page_obj': page_obj,
        'is_paginated': paginator.count > 0,
        'current_page_size': page_size,
        'page_size_options': ACCESS_TABLE_PAGE_SIZE_OPTIONS,
    }
    return render(request, 'app_access/manage_access_requests.html', context)

