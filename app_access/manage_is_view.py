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
            | Q(access_records__roles__accessrole_name_ua__icontains=search_query)
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
                Q(access_records__roles__accessrole_name_ua__iexact=role_filter)
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

    roles = AccessRoles.objects.filter(system__in=systems_scope)
    if environment_filter and environment_filter.lower() != 'undefined':
        roles = roles.filter(environment=environment_filter)
    if object_filter and object_filter.lower() != 'undefined':
        roles = roles.filter(Q(is_object_specific=False) | Q(created_for_object_id=object_filter))
    else:
        roles = roles.filter(is_object_specific=False)
    roles = roles.distinct().order_by('order', 'accessrole_name_ua')

    # Build unique role names for dropdown to avoid duplicates
    lang_code = 'ua' if current_language == 'uk' else current_language
    role_names_seen = set()
    role_options = []
    for r in roles:
        try:
            name = r.get_name(lang_code)
        except Exception:
            name = getattr(r, 'accessrole_name_ua', '')
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
    ).distinct().order_by('object_name_ua')

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
                    role_name = role.accessrole_name_ua
                elif current_language == 'ru':
                    role_name = getattr(role, 'accessrole_name_ru', None) or role.accessrole_name_ua
                else:
                    role_name = getattr(role, 'accessrole_name_en', None) or role.accessrole_name_ua

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

def access_config_is(request):
    """
    View для відображення сторінки конфігурації доступу до інформаційних систем
    """
    try:
        if settings.DEBUG:
            logger.debug("Starting access_config_is view")
        
        # Check access permissions
        if not has_access_config_is_permission(request.user):
            return JsonResponse({
                'error': 'Access denied',
                'message': _('Access denied to Config IS page')
            }, status=403)

        # Get user's companies
        user_companies = get_user_companies_for_config_is(request.user)
        
        # Get user's permissions for template
        can_add = can_add_access_config_is(request.user)
        can_edit = can_edit_access_config_is(request.user)
        can_delete = can_delete_access_config_is(request.user)
        
        context = {
            'title': _('Access configuration Information Systems'),
            'active_tab': 'access_config_is',
            'companies': user_companies,
            'can_add_access_config_is': can_add,
            'can_edit_access_config_is': can_edit,
            'can_delete_access_config_is': can_delete,
        }
        
        if settings.DEBUG:
            logger.debug(f"Rendering template with context: {context}")
        return render(request, 'app_access/access_config_is.html', context)
        
    except Exception as e:
        logger.error(f"Error in access_config_is view: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': str(e),
            'message': _('Error loading access configuration page')
        }, status=500)


@login_required
def access_right_list(request):
    if request.method == 'POST':
        # Handle creation
        try:
            right = AccessRight.objects.create(
                accessright_name_ua=request.POST['accessright_name_ua'],
                accessright_name_ru=request.POST['accessright_name_ru'],
                accessright_name_en=request.POST['accessright_name_en'],
                description_ua=request.POST['description_ua'],
                description_ru=request.POST['description_ru'],
                description_en=request.POST['description_en'],
                color=request.POST['color']
            )
            return JsonResponse({'success': True, 'id': right.id})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)

    rights = AccessRight.objects.all()
    return JsonResponse({'rights': list(rights.values())})



@login_required
def access_status_list(request):
    """List all access statuses or create a new one."""
    if request.method == 'POST':
        try:
            # Log incoming request data (debug only)
            if settings.DEBUG:
                logger.debug("Received POST request to create access status")
                logger.debug(f"POST data: {request.POST}")

            # Log specific fields (debug only)
            if settings.DEBUG:
                logger.debug("Field values:")
                for field in ['accessstatus_name_ua', 'description_ua', 'color']:
                    logger.debug(f"{field}: {request.POST.get(field)}")

            with transaction.atomic():
                # Create new status
                status_data = {
                    'accessstatus_name_ua': request.POST['accessstatus_name_ua'],
                    'accessstatus_name_ru': request.POST.get('accessstatus_name_ru', ''),
                    'accessstatus_name_en': request.POST.get('accessstatus_name_en', ''),
                    'description_ua': request.POST.get('description_ua', ''),
                    'description_ru': request.POST.get('description_ru', ''),
                    'description_en': request.POST.get('description_en', ''),
                    'color': request.POST.get('color', '#000000')
                }

                logger.debug("Creating status with data:")
                logger.debug(status_data)

                status = AccessStatus.objects.create(**status_data)
                logger.debug(f"Status created with ID: {status.id}")

                return JsonResponse({
                    'success': True,
                    'id': status.id,
                    'message': _('Access status created successfully')
                })

        except Exception as e:
            logger.error(f"Error creating access status: {str(e)}")
            logger.exception("Full error traceback:")
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)

    # GET request
    statuses = AccessStatus.objects.all()
    data = [{
        'id': status.id,
        'accessstatus_name_ua': status.accessstatus_name_ua,
        'accessstatus_name_ru': status.accessstatus_name_ru,
        'accessstatus_name_en': status.accessstatus_name_en,
        'description_ua': status.description_ua,
        'description_ru': status.description_ru,
        'description_en': status.description_en,
        'color': status.color
    } for status in statuses]

    return JsonResponse({'success': True, 'statuses': data})


@ensure_csrf_cookie
@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def access_status_detail(request, status_id):
    """
    Retrieve, update or delete an access status.
    """
    try:
        status = get_object_or_404(AccessStatus, id=status_id)

        if request.method == 'GET':
            data = {
                'id': status.id,
                'accessstatus_name_ua': status.accessstatus_name_ua,
                'accessstatus_name_ru': status.accessstatus_name_ru,
                'accessstatus_name_en': status.accessstatus_name_en,
                'description_ua': status.description_ua,
                'description_ru': status.description_ru,
                'description_en': status.description_en,
                'color': status.color
            }
            return JsonResponse(data)

        elif request.method == 'POST':
            with transaction.atomic():
                # Update the status fields
                status.accessstatus_name_ua = request.POST.get('accessstatus_name_ua')
                status.accessstatus_name_ru = request.POST.get('accessstatus_name_ru', '')
                status.accessstatus_name_en = request.POST.get('accessstatus_name_en', '')
                status.description_ua = request.POST.get('description_ua', '')
                status.description_ru = request.POST.get('description_ru', '')
                status.description_en = request.POST.get('description_en', '')
                # Handle color value
                color = request.POST.get('color')
                logger.debug(f"Processing color value: {color}")

                if color:
                    # Ensure the color is a valid hex color
                    color = color.strip()
                    if not color.startswith('#'):
                        color = f'#{color}'
                    # Ensure it's a valid 6-digit hex color
                    if len(color) == 4:  # Convert 3-digit hex to 6-digit
                        color = f'#{color[1] * 2}{color[2] * 2}{color[3] * 2}'
                    elif len(color) != 7:
                        color = '#000000'
                else:
                    color = '#000000'

                logger.debug(f"Final color value: {color}")
                status.color = color

                # Validate and save
                try:
                    status.full_clean()
                    status.save()
                    return JsonResponse({
                        'success': True,
                        'message': _('Access status updated successfully')
                    })
                except ValidationError as e:
                    return JsonResponse({
                        'success': False,
                        'message': str(e)
                    }, status=400)


        elif request.method == 'DELETE':
            # Check total number of statuses
            total_statuses = AccessStatus.objects.count()

            # If this is the last status, prevent deletion
            if total_statuses <= 1:
                return JsonResponse({
                    'success': False,
                    'message': _(
                        'Cannot delete the last status. At least one status must exist.')
                }, status=400)

            # Check if status is in use
            if status.system_accesses.exists():
                # Log the number of system accesses using this status
                used_accesses = status.system_accesses.count()
                logger.warning(f"Attempted to delete status {status_id} used by {used_accesses} system access records")
                return JsonResponse({
                    'success': False,
                    'message': _(f'Cannot delete status used by {used_accesses} system access records')
                }, status=400)

            # Before deleting, log some information
            logger.info(f"Deleting access status {status_id}")

            status.delete()
            return JsonResponse({
                'success': True,
                'message': _('Access status deleted successfully')
            })

    except Exception as e:
        logger.error(f"Error in access_status_detail: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('An unexpected error occurred')
        }, status=500)






@login_required
def get_functions(request):
    """Get all functions for specific asset."""
    try:
        asset_id = request.GET.get('asset_id')
        if not asset_id:
            raise ValidationError(_('Asset ID is required'))

        # Get all functions for the asset, ordered by right and order
        functions = AccessFunctionIS.objects.filter(
            asset_id=asset_id
        ).order_by('right', 'order').values(
            'id', 'accesfunct_name_ua', 'accesfunct_name_ru',
            'accesfunct_name_en', 'description_ua', 'description_ru',
            'description_en', 'color', 'parent_id', 'order', 'right'
        )

        return JsonResponse({
            'success': True,
            'functions': list(functions)
        })
    except Exception as e:
        logger.error(f"Error in get_functions: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
def get_function(request, function_id):
    """Get single function details."""
    try:
        function = get_object_or_404(AccessFunctionIS, id=function_id)
        data = {
            'id': function.id,
            'accesfunct_name_ua': function.accesfunct_name_ua,
            'accesfunct_name_ru': function.accesfunct_name_ru,
            'accesfunct_name_en': function.accesfunct_name_en,
            'description_ua': function.description_ua,
            'description_ru': function.description_ru,
            'description_en': function.description_en,
            'color': function.color,
            'parent_id': function.parent_id,
            'order': function.order,
            'right': function.right,
            'asset_id': function.asset_id
        }
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error in get_function: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@require_POST
@login_required
def add_function(request):
    """Add new function."""
    try:
        with transaction.atomic():
            parent_id = request.POST.get('parent_id')

            # Create function
            function = AccessFunctionIS.objects.create(
                accesfunct_name_ua=request.POST.get('accesfunct_name_ua'),
                accesfunct_name_ru=request.POST.get('accesfunct_name_ru', ''),
                accesfunct_name_en=request.POST.get('accesfunct_name_en', ''),
                description_ua=request.POST.get('description_ua'),
                description_ru=request.POST.get('description_ru', ''),
                description_en=request.POST.get('description_en', ''),
                color=request.POST.get('color', '#000000'),
                parent_id=parent_id if parent_id else None,
                asset_id=request.POST.get('asset_id'),
                order=request.POST.get('order', 0)
            )

            # Update rights for the entire tree
            update_function_rights(function)

            return JsonResponse({
                'success': True,
                'id': function.id,
                'message': _('Function added successfully')
            })
    except Exception as e:
        logger.error(f"Error in add_function: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@require_POST
@login_required
def edit_function(request, function_id):
    """Edit existing function."""
    try:
        with transaction.atomic():
            function = get_object_or_404(AccessFunctionIS, id=function_id)
            old_parent_id = function.parent_id
            new_parent_id = request.POST.get('parent_id')

            # Update basic fields
            function.accesfunct_name_ua = request.POST.get('accesfunct_name_ua')
            function.accesfunct_name_ru = request.POST.get('accesfunct_name_ru', '')
            function.accesfunct_name_en = request.POST.get('accesfunct_name_en', '')
            function.description_ua = request.POST.get('description_ua')
            function.description_ru = request.POST.get('description_ru', '')
            function.description_en = request.POST.get('description_en', '')
            function.color = request.POST.get('color', '#000000')
            function.order = request.POST.get('order', function.order)

            # Update parent if changed
            if str(old_parent_id) != str(new_parent_id):
                function.parent_id = new_parent_id if new_parent_id else None
                # Update rights for entire subtree
                update_function_rights(function)

            function.save()

            return JsonResponse({
                'success': True,
                'message': _('Function updated successfully')
            })
    except Exception as e:
        logger.error(f"Error in edit_function: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(['POST'])
def delete_function(request, function_id):
    """Delete specific function"""
    try:
        logger.info(f"Attempting to delete function with ID: {function_id}")

        with transaction.atomic():
            # Отримуємо функцію
            function = get_object_or_404(AccessFunctionIS, id=function_id)
            logger.info(f"Found function: {function}")

            # Перевіряємо, чи є дочірні функції
            children_count = function.get_descendant_count()
            logger.info(f"Function has {children_count} descendants")

            if children_count > 0:
                logger.warning(f"Function {function_id} has children, cannot delete")
                return JsonResponse({
                    'success': False,
                    'message': _('Cannot delete function with children. Please delete children first.')
                }, status=400)

            try:
                # Зберігаємо ID системи для оновлення дерева
                asset_id = function.asset_id
                tree_id = function.tree_id
                logger.info(f"Asset ID: {asset_id}, Tree ID: {tree_id}")

                # Видаляємо функцію
                function.delete()
                logger.info(f"Function {function_id} deleted successfully")

                # Оновлюємо дерево для всіх функцій цієї системи
                AccessFunctionIS.objects.filter(
                    asset_id=asset_id,
                    tree_id__gt=tree_id
                ).update(tree_id=F('tree_id') - 1)

                logger.info("Tree updated successfully")

                return JsonResponse({
                    'success': True,
                    'message': _('Function deleted successfully')
                })

            except Exception as delete_error:
                logger.error(f"Error during function deletion: {str(delete_error)}", exc_info=True)
                raise

    except AccessFunctionIS.DoesNotExist:
        logger.error(f"Function with ID {function_id} not found")
        return JsonResponse({
            'success': False,
            'message': _('Function not found')
        }, status=404)

    except Exception as e:
        logger.error(f"Unexpected error in delete_function: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': _('Error deleting function')
        }, status=500)


@login_required
@require_http_methods(['GET'])
def function_detail(request, function_id):
    """Get details for a specific function"""
    try:
        logger.info(f"Getting details for function_id: {function_id}")

        if not function_id:
            logger.error("Function ID is required")
            return JsonResponse({
                'error': _('Function ID is required')
            }, status=400)

        try:
            # Спочатку перевіримо, чи існує функція
            if not AccessFunctionIS.objects.filter(id=function_id).exists():
                logger.error(f"Function with id {function_id} not found in database")
                return JsonResponse({
                    'error': _('Function not found')
                }, status=404)

            # Логуємо запит до бази даних
            logger.info(f"Querying function with id {function_id}")
            function = AccessFunctionIS.objects.select_related(
                'parent',
                'asset'
            ).get(id=function_id)

            logger.info(f"Found function: {function}")
            logger.info(f"Asset: {function.asset}")

            try:
                # Перевіряємо доступність всіх полів
                data = {
                    'id': function.id,
                    'accesfunct_name_ua': function.accesfunct_name_ua,
                    'accesfunct_name_ru': function.accesfunct_name_ru,
                    'accesfunct_name_en': function.accesfunct_name_en,
                    'description_ua': function.description_ua,
                    'description_ru': function.description_ru,
                    'description_en': function.description_en,
                    'color': function.color,
                    'parent_id': function.parent_id,
                    'asset_id': function.asset_id
                }

                # Додаємо додаткові поля з перевіркою
                try:
                    data['asset_name'] = function.asset.name if function.asset else ''
                except AttributeError:
                    data['asset_name'] = ''

                try:
                    data['children_count'] = function.get_children().count()
                except Exception as children_error:
                    logger.error(f"Error getting children count: {str(children_error)}")
                    data['children_count'] = 0

                logger.info(f"Prepared data for response: {data}")
                return JsonResponse(data)

            except Exception as data_error:
                logger.error(f"Error preparing response data: {str(data_error)}", exc_info=True)
                raise

        except AccessFunctionIS.DoesNotExist:
            logger.error(f"Function with id {function_id} not found")
            return JsonResponse({
                'error': _('Function not found')
            }, status=404)

    except Exception as e:
        logger.error(f"Error getting function details: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': _('Error loading function details'),
            'details': str(e)
        }, status=500)


def update_function_rights(function):
    """Update rights for a function and all its descendants."""
    if not function:
        return

    # Update current function's right
    if function.parent:
        function.right = function.parent.right + 1
    else:
        function.right = 0
    function.save()

    # Update all children recursively
    for child in function.children.all():
        update_function_rights(child)




@login_required
def get_roles_functions(request):
    try:
        system_id = request.GET.get('system_id')
        environment = request.GET.get('environment', 'test')
        if not system_id:
            return JsonResponse({
                'status': 'error',
                'message': _('System ID is required')
            }, status=400)
        # For now, environment is not used, but can be used for filtering in the future
        roles = AccessRoles.objects.filter(
            system_id=system_id
        ).prefetch_related(
            'functions',
            'functions__children'
        ).order_by('order')
        data = []
        current_lang = get_language()[:2]
        lang_mapping = {
            'uk': 'ua',
            'ru': 'ru',
            'en': 'en',
        }
        lang_suffix = lang_mapping.get(current_lang, 'ua')
        def format_function(func, max_depth=3, current_depth=0):
            if current_depth >= max_depth:
                return None
            function_data = {
                'id': func.id,
                'name': getattr(func, f'accesfunct_name_{lang_suffix}', None) or func.accesfunct_name_ua,
                'color': func.color,
                'description': getattr(func, f'description_{lang_suffix}', None) or func.description_ua,
            }
            if current_depth < max_depth:
                children = func.children.all()
                if children:
                    function_data['children'] = []
                    for child in children:
                        child_data = format_function(child, max_depth, current_depth + 1)
                        if child_data:
                            function_data['children'].append(child_data)
            return function_data
        for role in roles:
            root_functions = role.functions.filter(parent__isnull=True)
            functions_data = []
            for func in root_functions:
                func_data = format_function(func)
                if func_data:
                    functions_data.append(func_data)
            role_data = {
                'role': {
                    'id': role.id,
                    'name': getattr(role, f'accessrole_name_{lang_suffix}', None) or role.accessrole_name_ua,
                    'color': role.color,
                    'description': getattr(role, f'description_{lang_suffix}', None) or role.description_ua
                },
                'functions': functions_data
            }
            data.append(role_data)
        return JsonResponse({
            'status': 'success',
            'data': data
        })
    except Exception as e:
        logger.error(f"Error getting roles and functions: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_http_methods(['POST'])
def update_role_functions(request, role_id):
    """Update functions assigned to a role"""
    try:
        data = json.loads(request.body)
        role = get_object_or_404(AccessRoles, id=role_id)

        with transaction.atomic():
            role.functions.clear()
            if data.get('functions'):
                functions = AccessFunctionIS.objects.filter(id__in=data['functions'])
                role.functions.add(*functions)

        return JsonResponse({
            'success': True,
            'message': _('Functions updated successfully')
        })
    except Exception as e:
        logger.error(f"Error updating role functions: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)
@login_required
@require_POST
@ensure_csrf_cookie
def add_approving_persons(request):
    try:
        data = json.loads(request.body)
        asset_id = data.get('asset_id')
        environment = data.get('environment', 'test')
        approvers_data = data.get('approvers', [])

        logger.info(f"Adding approving persons for asset_id: {asset_id}")
        logger.info(f"Approvers data: {approvers_data}")

        if not asset_id:
            return JsonResponse({
                'status': 'error',
                'message': _('System ID is required')
            }, status=400)

        with transaction.atomic():
            try:
                asset = InformationAsset.objects.get(id=asset_id)
                logger.info(f"Found asset: {asset}")
            except InformationAsset.DoesNotExist:
                logger.error(f"Asset with ID {asset_id} not found")
                return JsonResponse({
                    'status': 'error',
                    'message': _('Selected system does not exist')
                }, status=400)

            # Перевіряємо існування всіх cabinet_user_id перед видаленням
            for approver in approvers_data:
                logger.info(f"Checking user with ID: {approver['user_id']}")
                if not CabinetUser.objects.filter(id=approver['user_id']).exists():
                    logger.error(f"User with ID {approver['user_id']} not found")
                    return JsonResponse({
                        'status': 'error',
                        'message': _('One or more selected users do not exist')
                    }, status=400)

            # Delete existing approvers for this environment only
            old_approvers = ApprovingPerson.objects.filter(asset=asset, environment=environment)
            logger.info(f"Deleting {old_approvers.count()} existing approvers for environment: {environment}")
            old_approvers.delete()

            # Create new approvers
            created_approvers = []
            for approver in approvers_data:
                try:
                    cabinet_user = CabinetUser.objects.get(id=approver['user_id'])
                    logger.info(f"Creating approver for user: {cabinet_user}")
                    approver_obj = ApprovingPerson.objects.create(
                        asset=asset,
                        cabinet_user=cabinet_user,
                        order=approver['order'],
                        environment=environment
                    )
                    created_approvers.append(approver_obj)
                except CabinetUser.DoesNotExist:
                    logger.error(f"Failed to find user with ID {approver['user_id']}")
                    raise ValidationError(_(f"User with id {approver['user_id']} does not exist"))

            logger.info(f"Successfully created {len(created_approvers)} approvers")
            return JsonResponse({
                'status': 'success',
                'message': _('Approving persons updated successfully')
            })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _('Invalid JSON data')
        }, status=400)
    except ValidationError as e:
        logger.error(f"Validation error in add_approving_persons: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Error in add_approving_persons: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_http_methods(['GET'])
def get_approving_persons(request, asset_id):
    """Get approving persons for a specific asset"""
    try:
        environment = request.GET.get('environment', 'test')
        # print(f"Getting approving persons for asset_id: {asset_id}")
        approvers = ApprovingPerson.objects.filter(
            asset_id=asset_id,
            environment=environment
        ).select_related(
            'cabinet_user',
            'cabinet_user__user',
            'cabinet_user__department',
            'cabinet_user__position'
        ).order_by('order')
        # print(f"Found approvers: {approvers}")

        approvers_data = [{
            'id': approver.cabinet_user.id,  # Додаємо id для фронтенду
            'user_id': approver.cabinet_user.id,
            'name': approver.cabinet_user.user.get_full_name(),
            'department': approver.cabinet_user.department.department_name_ua if approver.cabinet_user.department else '',
            'position': approver.cabinet_user.position.position_name_ua if approver.cabinet_user.position else '',
            'order': approver.order,
            'color': approver.cabinet_user.color,
            'avatar': approver.cabinet_user.avatar.url if approver.cabinet_user.avatar else None
        } for approver in approvers]
        # print(f"Formatted approvers data: {approvers_data}")

        return JsonResponse({
            'status': 'success',
            'approvers': approvers_data,
            'total_count': len(approvers_data)
        })

    except Exception as e:
        print(f"Error getting approving persons: {str(e)}")
        logger.error(f"Error getting approving persons: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)



@login_required
@require_POST
def edit_approving_persons(request, asset_id):
    try:
        with transaction.atomic():
            asset = get_object_or_404(InformationAsset, id=asset_id)
            approvers_data = json.loads(request.POST.get('approvers', '[]'))

            environment = request.POST.get('environment', 'test')
            # Update approvers
            ApprovingPerson.objects.filter(asset=asset, environment=environment).delete()
            for approver in approvers_data:
                ApprovingPerson.objects.create(
                    asset=asset,
                    cabinet_user_id=approver['user_id'],
                    order=approver['order'],
                    environment=environment
                )

            return JsonResponse({
                'status': 'success',
                'message': _('Approving persons updated successfully')
            })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def get_access_approvers(request, access_id):
    try:
        access = SystemAccess.objects.select_related(
            'asset',
            'access_object'
        ).prefetch_related(
            'approvers',
            'approvers__cabinet_user',
            'approvers__cabinet_user__user',
            'approvers__cabinet_user__department',
            'approvers__cabinet_user__position',
            'asset__approving_persons',
            'asset__approving_persons__cabinet_user',
            'asset__approving_persons__cabinet_user__user',
            'asset__approving_persons__cabinet_user__department',
            'asset__approving_persons__cabinet_user__position'
        ).get(id=access_id)

        # Додаємо логування для відстеження
        logger.debug(f"Getting approvers for access_id: {access_id}")
        logger.debug(f"Company ID: {access.asset.company.id}")

        # Отримуємо approvers запису
        access_approvers = [{
            'id': ap.cabinet_user.id,
            'name': f"{ap.cabinet_user.user.first_name} {ap.cabinet_user.user.last_name}",
            'department': ap.cabinet_user.department.department_name_ua if ap.cabinet_user.department else None,
            'position': ap.cabinet_user.position.position_name_ua if ap.cabinet_user.position else None,
            'order': ap.order,
            'color': ap.cabinet_user.color,
            'avatar': ap.cabinet_user.avatar.url if ap.cabinet_user.avatar else None,
            'department_name': ap.cabinet_user.department.department_name_ua if ap.cabinet_user.department else None,
            'position_name': ap.cabinet_user.position.position_name_ua if ap.cabinet_user.position else None
        } for ap in access.approvers.all()]

        # Object approvers removed - only system approvers are used now
        object_approvers = []

        # Отримуємо системні approvers
        system_approvers = [{
            'id': ap.cabinet_user.id,
            'name': f"{ap.cabinet_user.user.first_name} {ap.cabinet_user.user.last_name}",
            'department': ap.cabinet_user.department.department_name_ua if ap.cabinet_user.department else None,
            'position': ap.cabinet_user.position.position_name_ua if ap.cabinet_user.position else None,
            'order': ap.order,
            'color': ap.cabinet_user.color,
            'avatar': ap.cabinet_user.avatar.url if ap.cabinet_user.avatar else None,
            'department_name': ap.cabinet_user.department.department_name_ua if ap.cabinet_user.department else None,
            'position_name': ap.cabinet_user.position.position_name_ua if ap.cabinet_user.position else None
        } for ap in access.asset.approving_persons.all()]

        # Отримуємо всіх активних користувачів компанії
        cabinet_users = CabinetUser.objects.select_related(
            'user',
            'department',
            'position'
        ).filter(
            company=access.asset.company,
            user__is_active=True
        ).order_by('user__first_name', 'user__last_name')

        # Додаємо логування кількості користувачів
        logger.debug(f"Total active cabinet users found: {cabinet_users.count()}")

        available_approvers = [{
            'id': cu.id,
            'name': f"{cu.user.first_name} {cu.user.last_name}",
            'department': cu.department.department_name_ua if cu.department else None,
            'position': cu.position.position_name_ua if cu.position else None,
            'color': cu.color,
            'avatar': cu.avatar.url if cu.avatar else None,
            'department_name': cu.department.department_name_ua if cu.department else None,
            'position_name': cu.position.position_name_ua if cu.position else None
        } for cu in cabinet_users]

        # Додаємо логування результатів
        logger.debug(f"Access approvers: {len(access_approvers)}")
        logger.debug(f"Object approvers: {len(object_approvers)}")
        logger.debug(f"System approvers: {len(system_approvers)}")
        logger.debug(f"Available approvers: {len(available_approvers)}")

        response_data = {
            'access_approvers': access_approvers,
            'object_approvers': object_approvers,  # Empty - object approvers no longer used
            'system_approvers': system_approvers,
            'available_approvers': available_approvers,
            'max_approval_levels': AccessApprover.MAX_APPROVAL_LEVELS
        }

        return JsonResponse(response_data)
    except Exception as e:
        logger.error(f"Error in get_access_approvers: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_POST
def update_access_approvers(request):
    try:
        data = json.loads(request.body)
        access_id = data.get('access_id')
        approvers_data = data.get('approvers', [])

        if not access_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Access ID is required')
            }, status=400)

        with transaction.atomic():
            access = get_object_or_404(SystemAccess, id=access_id)

            # Видаляємо існуючих approvers
            AccessApprover.objects.filter(access=access).delete()

            # Додаємо нових approvers
            for approver_data in approvers_data:
                AccessApprover.objects.create(
                    access=access,
                    cabinet_user_id=approver_data['cabinet_user_id'],
                    order=approver_data['order']
                )

            return JsonResponse({
                'status': 'success',
                'message': _('Approvers updated successfully')
            })

    except Exception as e:
        logger.error(f"Error updating access approvers: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


@login_required
@require_POST
def save_access_approvers(request, access_id):
    try:
        data = json.loads(request.body)
        logger.info(f"Received data for access_id {access_id}: {data}")

        access = SystemAccess.objects.get(id=access_id)
        logger.info(f"Found access record: {access}")

        # Очищаємо поточних approvers
        current_approvers = list(access.approvers.all())
        logger.info(f"Current approvers before deletion: {current_approvers}")
        access.approvers.all().delete()

        # Додаємо нових approvers
        approvers_data = data.get('approvers', [])
        logger.info(f"New approvers data: {approvers_data}")

        created_approvers = []
        for approver_data in approvers_data:
            try:
                logger.info(f"Creating approver with data: {approver_data}")
                approver = AccessApprover.objects.create(
                    access=access,
                    cabinet_user_id=approver_data['approver_id'],
                    order=approver_data['order']
                )
                logger.info(f"Created approver: {approver}")
                created_approvers.append(approver)
            except Exception as e:
                logger.error(f"Error creating approver: {str(e)}")
                raise Exception(f"Error creating approver: {str(e)}")

        # Повертаємо оновлений список approvers
        approvers = [{
            'id': approver.cabinet_user.id,
            'name': f"{approver.cabinet_user.user.first_name} {approver.cabinet_user.user.last_name}",
            'department': approver.cabinet_user.department.department_name_ua if approver.cabinet_user.department else None,
            'position': approver.cabinet_user.position.position_name_ua if approver.cabinet_user.position else None,
            'order': approver.order,
            'color': approver.cabinet_user.color
        } for approver in created_approvers]

        logger.info(f"Returning approvers: {approvers}")

        return JsonResponse({
            'status': 'success',
            'message': _('Approvers updated successfully'),
            'approvers': approvers
        })
    except Exception as e:
        logger.error(f"Error saving approvers: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
@login_required
@require_http_methods(['GET'])
def get_system_roles(request):
    """Get roles for a specific system and environment"""
    try:
        system_id = request.GET.get('system_id')
        environment = request.GET.get('environment', 'test')
        
        if not system_id:
            return JsonResponse({'error': _('System ID is required')}, status=400)

        # Filter roles by system and environment
        roles = AccessRoles.objects.filter(
            system_id=system_id,
            environment=environment,
            is_object_specific=False  # Only show non-object-specific roles
        ).values(
            'id',
            'accessrole_name_ua',
            'accessrole_name_ru',
            'accessrole_name_en',
            'description_ua',
            'description_ru',
            'description_en',
            'color'
        ).order_by('order')

        # Повертаємо всі мовні версії
        formatted_roles = []
        for role in roles:
            formatted_roles.append({
                'id': role['id'],
                'accessrole_name_ua': role['accessrole_name_ua'],
                'accessrole_name_ru': role['accessrole_name_ru'],
                'accessrole_name_en': role['accessrole_name_en'],
                'description_ua': role['description_ua'],
                'description_ru': role['description_ru'],
                'description_en': role['description_en'],
                'color': role['color']
            })

        return JsonResponse({'roles': formatted_roles})
    except Exception as e:
        print(f"Error in get_system_roles: {str(e)}")
        logger.error(f"Error getting system roles: {str(e)}")
        return JsonResponse({
            'error': _('Error loading roles'),
            'details': str(e)
        }, status=500)


@login_required
@require_http_methods(['GET'])
def get_role(request):
    """Get specific role details"""
    try:
        role_id = request.GET.get('role_id')
        if not role_id:
            return JsonResponse({'error': _('Role ID is required')}, status=400)

        role = get_object_or_404(AccessRoles, id=role_id)
        return JsonResponse({
            'success': True,
            'role': {
                'id': role.id,
                'accessrole_name_ua': role.accessrole_name_ua,
                'accessrole_name_ru': role.accessrole_name_ru,
                'accessrole_name_en': role.accessrole_name_en,
                'description_ua': role.description_ua,
                'description_ru': role.description_ru,
                'description_en': role.description_en,
                'color': role.color
            }
        })
    except Exception as e:
        logger.error(f"Error getting role details: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
@ensure_csrf_cookie
def save_role(request):
    """Save or update a role"""
    try:
        role_id = request.POST.get('role_id')
        asset_id = request.POST.get('asset_id')
        object_id = request.POST.get('object_id')  # New field for object-specific roles

        if not asset_id:
            return JsonResponse({'error': _('System ID is required')}, status=400)

        # Environment must be provided by caller (UI passes from modal data attribute)
        environment = request.POST.get('environment', 'test')
        role_data = {
            'accessrole_name_ua': request.POST.get('accessrole_name_ua'),
            'accessrole_name_ru': request.POST.get('accessrole_name_ru'),
            'accessrole_name_en': request.POST.get('accessrole_name_en'),
            'description_ua': request.POST.get('description_ua'),
            'description_ru': request.POST.get('description_ru'),
            'description_en': request.POST.get('description_en'),
            'color': request.POST.get('color'),
            'system_id': asset_id,
            'environment': environment
        }

        # If object_id is provided, this is an object-specific role
        if object_id:
            try:
                access_object = AccessObjectIS.objects.get(id=object_id)
                role_data['is_object_specific'] = True
                role_data['created_for_object'] = access_object
            except AccessObjectIS.DoesNotExist:
                return JsonResponse({
                    'error': _('Selected object does not exist')
                }, status=400)
        else:
            role_data['is_object_specific'] = False
            role_data['created_for_object'] = None

        if role_id:
            # Update existing role
            role = get_object_or_404(AccessRoles, id=role_id)
            
            # Захист від редагування object-specific ролей через системний інтерфейс
            if role.is_object_specific:
                return JsonResponse({
                    'success': False,
                    'message': _('Cannot edit object-specific roles through system interface')
                }, status=403)
            
            for key, value in role_data.items():
                setattr(role, key, value)
            role.save()
            message = _('Role updated successfully')
        else:
            # Create new role - завжди створюємо як системну роль (не object-specific)
            AccessRoles.objects.create(**role_data)
            message = _('Role created successfully')

        return JsonResponse({'success': True, 'message': message})
    except IntegrityError as e:
        logger.error(f"Integrity error saving role: {str(e)}")
        if 'Duplicate entry' in str(e) or 'UNIQUE constraint failed' in str(e):
            return JsonResponse({
                'error': _('Role with this name already exists in the system. Please choose a different name.')
            }, status=400)
        else:
            return JsonResponse({
                'error': _('Database integrity error occurred while saving the role.')
            }, status=400)
    except Exception as e:
        logger.error(f"Error saving role: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def delete_role(request):
    """Delete a role"""
    try:
        data = json.loads(request.body)
        role_id = data.get('role_id')

        if not role_id:
            return JsonResponse({'error': _('Role ID is required')}, status=400)

        role = get_object_or_404(AccessRoles, id=role_id)
        role.delete()

        return JsonResponse({
            'success': True,
            'message': _('Role deleted successfully')
        })
    except Exception as e:
        logger.error(f"Error deleting role: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(['GET'])
def get_company_and_system(request):
    """Get list of companies and their systems filtered by AccessISAM permissions"""
    try:
        logger.info("Starting get_company_and_system view")
        logger.info(f"User: {request.user}")
        
        # Get companies that user has access to through AccessISAM
        access_isam_records = AccessISAM.objects.filter(
            group__in=request.user.groups.all(),
            has_access_matrix=True
        ).prefetch_related('companies')
        
        # Collect all company IDs from AccessISAM records
        company_ids = set()
        for access_record in access_isam_records:
            company_ids.update(access_record.companies.values_list('id', flat=True))
        
        # Get companies filtered by collected IDs
        user_companies = Company.objects.filter(id__in=company_ids).order_by('name')
        logger.info(f"Found {user_companies.count()} accessible companies for user")
        
        # If no companies are accessible, return empty result
        if not user_companies.exists():
            logger.info("No companies accessible for user - returning empty result")
            return JsonResponse({
                'status': 'success',
                'data': []
            })
        
        # Get systems for each accessible company
        result = []
        for company in user_companies:
            logger.info(f"Processing company: {company.id} - {company.name}")
            
            # Get active systems for the company
            systems = InformationAsset.objects.filter(
                company=company,
                access_manage=True,  # Only include assets marked for access management
                deletion_date__isnull=True
            ).values('id', 'name').order_by('name')
            
            logger.info(f"Found {systems.count()} systems for company {company.name}")
            
            # Add company and its systems to result
            result.append({
                'company': {
                    'id': company.id,
                    'name': company.name
                },
                'systems': list(systems)
            })

        logger.info(f"Prepared data for {len(result)} companies")
        
        response_data = {
            'status': 'success',
            'data': result
        }
        
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(f"Error getting companies and systems: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'message': _('Error loading companies and systems')
        }, status=400)

@login_required
@require_http_methods(['POST'])
def update_approving_persons(request, asset_id):
    """Update approving persons for a specific asset"""
    try:
        logger.info(f"Updating approving persons for asset_id: {asset_id}")
        
        # Перевіряємо, чи існує asset
        asset = get_object_or_404(InformationAsset, id=asset_id)
        logger.info(f"Found asset: {asset}")
        
        # Парсимо дані запиту
        data = json.loads(request.body)
        approvers = data.get('approvers', [])
        logger.info(f"Received approvers data: {approvers}")
        
        # Валідація даних
        if not isinstance(approvers, list):
            raise ValidationError(_('Approvers must be a list'))
        
        for approver in approvers:
            if not isinstance(approver, dict):
                raise ValidationError(_('Each approver must be an object'))
            if 'user_id' not in approver:
                raise ValidationError(_('Each approver must have user_id'))
            if 'order' not in approver:
                raise ValidationError(_('Each approver must have order'))
            
            # Перевіряємо, чи існує користувач
            if not CabinetUser.objects.filter(id=approver['user_id']).exists():
                raise ValidationError(_(f'User with id {approver["user_id"]} does not exist'))
        
        with transaction.atomic():
            # Get environment from request data, default to 'test'
            environment = data.get('environment', 'test')
            
            # Видаляємо існуючих approvers для цього environment
            deleted_count = ApprovingPerson.objects.filter(asset_id=asset_id, environment=environment).delete()
            logger.info(f"Deleted {deleted_count} existing approvers for environment: {environment}")
            
            # Додаємо нових approvers
            created_approvers = []
            for approver_data in approvers:
                approver = ApprovingPerson.objects.create(
                    asset_id=asset_id,
                    cabinet_user_id=approver_data['user_id'],
                    order=approver_data['order'],
                    environment=environment
                )
                created_approvers.append(approver)
            
            logger.info(f"Created {len(created_approvers)} new approvers")
            
            return JsonResponse({
                'status': 'success',
                'message': _('Approving persons updated successfully'),
                'updated_count': len(created_approvers)
            })
            
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating approving persons: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': _('An error occurred while updating approvers')
        }, status=400)

@login_required
def get_roles_functions(request):
    try:
        system_id = request.GET.get('system_id')
        environment = request.GET.get('environment', 'test')
        if not system_id:
            return JsonResponse({
                'status': 'error',
                'message': _('System ID is required')
            }, status=400)
        roles = AccessRoles.objects.filter(
            system_id=system_id,
            environment=environment
        ).prefetch_related(
            'functions',
            'functions__children'
        ).order_by('order')
        data = []
        current_lang = get_language()[:2]
        lang_mapping = {
            'uk': 'ua',
            'ru': 'ru',
            'en': 'en',
        }
        lang_suffix = lang_mapping.get(current_lang, 'ua')
        def format_function(func, max_depth=3, current_depth=0):
            if current_depth >= max_depth:
                return None
            function_data = {
                'id': func.id,
                'name': getattr(func, f'accesfunct_name_{lang_suffix}', None) or func.accesfunct_name_ua,
                'color': func.color,
                'description': getattr(func, f'description_{lang_suffix}', None) or func.description_ua,
            }
            if current_depth < max_depth:
                children = func.children.all()
                if children:
                    function_data['children'] = []
                    for child in children:
                        child_data = format_function(child, max_depth, current_depth + 1)
                        if child_data:
                            function_data['children'].append(child_data)
            return function_data
        for role in roles:
            root_functions = role.functions.filter(parent__isnull=True)
            functions_data = []
            for func in root_functions:
                func_data = format_function(func)
                if func_data:
                    functions_data.append(func_data)
            role_data = {
                'role': {
                    'id': role.id,
                    'name': getattr(role, f'accessrole_name_{lang_suffix}', None) or role.accessrole_name_ua,
                    'color': role.color,
                    'description': getattr(role, f'description_{lang_suffix}', None) or role.description_ua
                },
                'functions': functions_data
            }
            data.append(role_data)
        return JsonResponse({
            'status': 'success',
            'data': data
        })
    except Exception as e:
        logger.error(f"Error getting roles and functions: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_http_methods(['GET'])
def get_system_access_rights(request):
    """Get access rights for a specific system and environment"""
    try:
        system_id = request.GET.get('system_id')
        environment = request.GET.get('environment', 'test')
        
        if not system_id:
            return JsonResponse({'error': _('System ID is required')}, status=400)

        # Filter access rights by system and environment
        rights = AccessRight.objects.filter(
            system_id=system_id,
            environment=environment,
            is_object_specific=False
        ).values(
            'id',
            'accessright_name_ua',
            'accessright_name_ru',
            'accessright_name_en',
            'description_ua',
            'description_ru',
            'description_en',
            'color'
        ).order_by('order')

        formatted_rights = [{
            'id': right['id'],
            'accessright_name_ua': right['accessright_name_ua'],
            'accessright_name_ru': right['accessright_name_ru'],
            'accessright_name_en': right['accessright_name_en'],
            'description_ua': right['description_ua'],
            'description_ru': right['description_ru'],
            'description_en': right['description_en'],
            'color': right['color']
        } for right in rights]

        return JsonResponse({'rights': formatted_rights})
    except Exception as e:
        logger.error(f"Error getting system access rights: {str(e)}")
        return JsonResponse({
            'error': _('Error loading access rights'),
            'details': str(e)
        }, status=500)
def access_right_detail(request, right_id):
    try:
        right = get_object_or_404(AccessRight, id=right_id)
        
        # Захист від доступу до object-specific прав через системний інтерфейс
        if right.is_object_specific:
            return JsonResponse({
                'success': False,
                'message': _('Cannot access object-specific access rights through system interface')
            }, status=403)

        if request.method == 'GET':
            return JsonResponse({
                'id': right.id,
                'accessright_name_ua': right.accessright_name_ua,
                'accessright_name_ru': right.accessright_name_ru,
                'accessright_name_en': right.accessright_name_en,
                'description_ua': right.description_ua,
                'description_ru': right.description_ru,
                'description_en': right.description_en,
                'color': right.color
            })

        elif request.method == 'DELETE':
            # Перевіряємо чи право не використовується
            if right.system_accesses.exists():
                return JsonResponse({
                    'success': False,
                    'message': _('Cannot delete access right that is in use')
                }, status=400)

            right.delete()
            return JsonResponse({
                'success': True,
                'message': _('Access right deleted successfully')
            })

    except Exception as e:
        logger.error(f"Error in access_right_detail: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)
@login_required
@require_POST
def save_access_right(request):
    """Save or update an access right"""
    try:
        right_id = request.POST.get('right_id')
        system_id = request.POST.get('system_id')

        if not system_id:
            return JsonResponse({'error': _('System ID is required')}, status=400)

        environment = request.POST.get('environment', 'test')
        right_data = {
            'accessright_name_ua': request.POST.get('accessright_name_ua'),
            'accessright_name_ru': request.POST.get('accessright_name_ru'),
            'accessright_name_en': request.POST.get('accessright_name_en'),
            'description_ua': request.POST.get('description_ua'),
            'description_ru': request.POST.get('description_ru'),
            'description_en': request.POST.get('description_en'),
            'color': request.POST.get('color'),
            'system_id': system_id,
            'environment': environment
        }

        if right_id:
            # Update existing right
            right = get_object_or_404(AccessRight, id=right_id)
            
            # Захист від редагування object-specific прав через системний інтерфейс
            if right.is_object_specific:
                return JsonResponse({
                    'success': False,
                    'message': _('Cannot edit object-specific access rights through system interface')
                }, status=403)
            
            # Update only provided fields; preserve environment unless explicitly sent
            for key, value in right_data.items():
                if key == 'environment' and value is None:
                    continue
                setattr(right, key, value)
            right.save()
            message = _('Access right updated successfully')
        else:
            # Create new right
            AccessRight.objects.create(**right_data)
            message = _('Access right created successfully')

        return JsonResponse({'success': True, 'message': message})
    except IntegrityError as e:
        logger.error(f"Integrity error saving access right: {str(e)}")
        if 'Duplicate entry' in str(e) or 'UNIQUE constraint failed' in str(e):
            return JsonResponse({
                'error': _('Access right with this name already exists in the system. Please choose a different name.')
            }, status=400)
        else:
            return JsonResponse({
                'error': _('Database integrity error occurred while saving the access right.')
            }, status=400)
    except Exception as e:
        logger.error(f"Error saving access right: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_system_statuses(request):
    """Get statuses for a specific system and environment"""
    try:
        system_id = request.GET.get('system_id')
        environment = request.GET.get('environment', 'test')
        
        if not system_id:
            return JsonResponse({
                'status': 'error',
                'message': _('System ID is required')
            }, status=400)

        # Filter statuses by system and environment
        # For now, we'll return all system statuses regardless of environment
        # as statuses are typically shared across environments
        statuses = AccessStatus.objects.filter(
            system_id=system_id,
            environment=environment,
            is_object_specific=False  # Виключаємо кастомні статуси об'єктів
        )
        
        statuses_data = [{
            'id': status.id,
            'accessstatus_name_ua': status.accessstatus_name_ua,
            'accessstatus_name_ru': status.accessstatus_name_ru,
            'accessstatus_name_en': status.accessstatus_name_en,
            'description_ua': status.description_ua,
            'description_ru': status.description_ru,
            'description_en': status.description_en,
            'color': status.color,
            'order': status.order
        } for status in statuses]

        return JsonResponse({
            'status': 'success',
            'statuses': statuses_data
        })

    except Exception as e:
        logger.error(f"Error getting system statuses: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(['GET', 'DELETE'])
def status_detail(request, status_id):
    """Get or delete specific status"""
    try:
        status = get_object_or_404(AccessStatus, id=status_id)

        if request.method == 'GET':
            return JsonResponse({
                'id': status.id,
                'accessstatus_name_ua': status.accessstatus_name_ua,
                'accessstatus_name_ru': status.accessstatus_name_ru,
                'accessstatus_name_en': status.accessstatus_name_en,
                'description_ua': status.description_ua,
                'description_ru': status.description_ru,
                'description_en': status.description_en,
                'color': status.color
            })

        elif request.method == 'DELETE':

            # Перевіряємо, чи є інші статуси
            if AccessStatus.objects.filter(system=status.system).count() <= 1:
                return JsonResponse({
                    'success': False,
                    'message': _('Cannot delete the last status')
                }, status=400)

            status.delete()
            return JsonResponse({
                'success': True,
                'message': _('Status deleted successfully')
            })

    except Exception as e:
        logger.error(f"Error in status_detail: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
@require_POST
def save_status(request):
    """Save or update a status"""
    try:
        status_id = request.POST.get('status_id')
        system_id = request.POST.get('system_id')

        if not system_id:
            return JsonResponse({'error': _('System ID is required')}, status=400)

        environment = request.POST.get('environment', 'test')
        status_data = {
            'accessstatus_name_ua': request.POST.get('accessstatus_name_ua'),
            'accessstatus_name_ru': request.POST.get('accessstatus_name_ru'),
            'accessstatus_name_en': request.POST.get('accessstatus_name_en'),
            'description_ua': request.POST.get('description_ua'),
            'description_ru': request.POST.get('description_ru'),
            'description_en': request.POST.get('description_en'),
            'color': request.POST.get('color'),
            'system_id': system_id,
            'environment': environment
        }

        with transaction.atomic():

            if status_id:
                # Update existing status
                status = get_object_or_404(AccessStatus, id=status_id)
                for key, value in status_data.items():
                    setattr(status, key, value)
                status.save()
                message = _('Status updated successfully')
            else:
                # Create new status
                AccessStatus.objects.create(**status_data)
                message = _('Status created successfully')

            return JsonResponse({'success': True, 'message': message})
    except IntegrityError as e:
        logger.error(f"Integrity error saving status: {str(e)}")
        if 'Duplicate entry' in str(e) or 'UNIQUE constraint failed' in str(e):
            return JsonResponse({
                'error': _('Status with this name already exists in the system. Please choose a different name.')
            }, status=400)
        else:
            return JsonResponse({
                'error': _('Database integrity error occurred while saving the status.')
            }, status=400)
    except Exception as e:
        logger.error(f"Error saving status: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
@login_required
@require_POST
def update_status_order(request):
    try:
        data = json.loads(request.body)
        orders = data.get('orders', [])

        with transaction.atomic():
            for item in orders:
                AccessStatus.objects.filter(id=item['id']).update(order=item['order'])

        return JsonResponse({
            'success': True,
            'message': _('Status order updated successfully')
        })
    except Exception as e:
        logger.error(f"Error updating status order: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)
@login_required
@require_POST
def update_access_rights_order(request):
    """Update access rights order"""
    try:
        data = json.loads(request.body)
        orders = data.get('orders', [])
        
        with transaction.atomic():
            for item in orders:
                AccessRight.objects.filter(id=item['id']).update(order=item['order'])
        
        return JsonResponse({
            'success': True,
            'message': _('Order updated successfully')
        })
    except Exception as e:
        logger.error(f"Error updating access rights order: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)

@login_required
@require_POST
def update_roles_order(request):
    """Update roles order"""
    try:
        data = json.loads(request.body)
        orders = data.get('orders', [])
        
        with transaction.atomic():
            for item in orders:
                # Only update non-object-specific roles
                AccessRoles.objects.filter(
                    id=item['id'],
                    is_object_specific=False
                ).update(order=item['order'])
        
        return JsonResponse({
            'success': True,
            'message': _('Roles order updated successfully')
        })
    except Exception as e:
        logger.error(f"Error updating roles order: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)

@login_required
@require_http_methods(['GET'])
def get_system_functions(request):
    """Get functions for a specific system and environment"""
    try:
        system_id = request.GET.get('system_id')
        environment = request.GET.get('environment', 'test')
        
        if not system_id:
            return JsonResponse({
                'success': False,
                'message': _('System ID is required')
            }, status=400)

        # Filter functions by system and environment
        functions = AccessFunctionIS.objects.filter(
            asset_id=system_id,
            environment=environment,
            parent_id=None,  # Отримуємо тільки кореневі функції
            is_object_specific=False  # Виключаємо об'єкт-специфічні функції
        ).order_by('order')

        def get_children(parent):
            children = AccessFunctionIS.objects.filter(
                parent_id=parent.id,
                asset_id=system_id,
                environment=environment,
                is_object_specific=False  # Виключаємо об'єкт-специфічні дочірні функції
            ).order_by('order')
            
            return [{
                'id': child.id,
                'accesfunct_name_ua': child.accesfunct_name_ua,
                'accesfunct_name_ru': child.accesfunct_name_ru,
                'accesfunct_name_en': child.accesfunct_name_en,
                'description_ua': child.description_ua,
                'description_ru': child.description_ru,
                'description_en': child.description_en,
                'color': child.color,
                'order': child.order,
                'parent_id': child.parent_id,
                'children': get_children(child)
            } for child in children]

        functions_data = [{
            'id': func.id,
            'accesfunct_name_ua': func.accesfunct_name_ua,
            'accesfunct_name_ru': func.accesfunct_name_ru,
            'accesfunct_name_en': func.accesfunct_name_en,
            'description_ua': func.description_ua,
            'description_ru': func.description_ru,
            'description_en': func.description_en,
            'color': func.color,
            'order': func.order,
            'parent_id': func.parent_id,
            'children': get_children(func)
        } for func in functions]

        return JsonResponse({
            'success': True,
            'functions': functions_data
        })

    except Exception as e:
        logger.error(f"Error getting system functions: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
@require_POST
def save_function(request):
    """Save or update function"""
    try:
        function_id = request.POST.get('function_id')
        system_id = request.POST.get('system_id')
        parent_id = request.POST.get('parent_id')

        if not system_id:
            return JsonResponse({'error': _('System ID is required')}, status=400)

        environment = request.POST.get('environment', 'test')
        function_data = {
            'accesfunct_name_ua': request.POST.get('accesfunct_name_ua'),
            'accesfunct_name_ru': request.POST.get('accesfunct_name_ru'),
            'accesfunct_name_en': request.POST.get('accesfunct_name_en'),
            'description_ua': request.POST.get('description_ua'),
            'description_ru': request.POST.get('description_ru', ''),
            'description_en': request.POST.get('description_en', ''),
            'color': request.POST.get('color'),
            'asset_id': system_id,
            'environment': environment
        }

        with transaction.atomic():
            # Перевіряємо унікальність імені в межах системи та середовища
            name_exists_query = AccessFunctionIS.objects.filter(
                asset_id=system_id,
                environment=environment,
                accesfunct_name_ua=function_data['accesfunct_name_ua']
            )
            
            if function_id:
                name_exists_query = name_exists_query.exclude(id=function_id)
            
            if name_exists_query.exists():
                return JsonResponse({
                    'success': False,
                    'message': _('Function with this name already exists in this system')
                }, status=400)

            if function_id:
                # Оновлюємо існуючу функцію
                function = get_object_or_404(AccessFunctionIS, id=function_id)
                
                # Якщо змінюється parent_id, оновлюємо його
                if parent_id and int(parent_id) != function.parent_id:
                    new_parent = get_object_or_404(AccessFunctionIS, id=parent_id)
                    function.move_to(new_parent)
                elif not parent_id and function.parent_id:
                    function.move_to(None)  # Робимо кореневою функцією

                # Оновлюємо інші поля
                for key, value in function_data.items():
                    setattr(function, key, value)
                function.save()
                message = _('Function updated successfully')
            else:
                # Створюємо нову функцію
                if parent_id:
                    parent = get_object_or_404(AccessFunctionIS, id=parent_id)
                    function = AccessFunctionIS.objects.create(
                        parent=parent,
                        **function_data
                    )
                else:
                    function = AccessFunctionIS.objects.create(**function_data)
                message = _('Function created successfully')

            return JsonResponse({
                'success': True,
                'message': message,
                'function': {
                    'id': function.id,
                    'accesfunct_name_ua': function.accesfunct_name_ua,
                    'accesfunct_name_ru': function.accesfunct_name_ru,
                    'accesfunct_name_en': function.accesfunct_name_en,
                    'description_ua': function.description_ua,
                    'description_ru': function.description_ru,
                    'description_en': function.description_en,
                    'color': function.color,
                    'parent_id': function.parent_id
                }
            })
    except Exception as e:
        logger.error(f"Error saving function: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
@require_POST
def update_functions_order(request):
    """Update functions order"""
    try:
        data = json.loads(request.body)
        orders = data.get('orders', [])
        parent_id = data.get('parent_id')
        moved_item_id = data.get('moved_item_id')
        system_id = data.get('system_id')
        
        if not system_id:
            return JsonResponse({
                'success': False,
                'message': _('System ID is required')
            }, status=400)

        with transaction.atomic():
            # Оновлюємо переміщену функцію
            if moved_item_id:
                moved_function = AccessFunctionIS.objects.get(
                    id=moved_item_id,
                    asset_id=system_id
                )
                old_parent_id = moved_function.parent_id
                moved_function.parent_id = parent_id
                moved_function.save()

            # Отримуємо всі функції в поточному контейнері (виключаємо об'єкт-специфічні)
            functions_in_container = AccessFunctionIS.objects.filter(
                asset_id=system_id,
                parent_id=parent_id,
                is_object_specific=False  # Виключаємо об'єкт-специфічні функції
            ).order_by('order')

            # Створюємо словник для швидкого пошуку нових порядків
            new_orders = {str(item['id']): item['order'] for item in orders}

            # Оновлюємо порядок для кожної функції
            for index, function in enumerate(functions_in_container):
                new_order = new_orders.get(str(function.id))
                if new_order is not None and function.order != new_order:
                    function.order = new_order
                    function.save()

            return JsonResponse({
                'success': True,
                'message': _('Order updated successfully')
            })

    except Exception as e:
        logger.error(f"Error updating functions order: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(['GET'])
def get_cabinet_users(request, company_id):
    """Get cabinet users for a specific company"""
    try:
        print(f"Getting cabinet users for company_id: {company_id}")
        users = CabinetUser.objects.filter(
            company_id=company_id,
            user__is_active=True  # Тільки активні користувачі
        ).select_related(
            'user',
            'department',
            'position'
        ).order_by(
            'user__last_name',
            'user__first_name'
        )
        print(f"Found users: {users}")

        users_data = [{
            'id': user.id,
            'name': user.user.get_full_name(),
            'department': user.department.department_name_ua if user.department else '{% trans "No Department" %}',
            'position': user.position.position_name_ua if user.position else '{% trans "No Position" %}',
            'color': user.color,
            'avatar': user.avatar.url if user.avatar else None
        } for user in users]
        print(f"Formatted users data: {users_data}")

        return JsonResponse({
            'status': 'success',
            'users': users_data
        })

    except Exception as e:
        print(f"Error getting cabinet users: {str(e)}")
        logger.error(f"Error getting cabinet users: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

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
            parent_id=None  # Отримуємо тільки кореневі об'єкти
        ).order_by('order')

        def get_children(parent):
            children = AccessObjectIS.objects.filter(
                parent_id=parent.id,
                asset_id=system_id,
                environment=environment
            ).order_by('order')
            
            return [{
                'id': child.id,
                'object_name_ua': child.object_name_ua,
                'object_name_ru': child.object_name_ru,
                'object_name_en': child.object_name_en,
                'description_ua': child.description_ua,
                'description_ru': child.description_ru,
                'description_en': child.description_en,
                'color': child.color,
                'order': child.order,
                'parent_id': child.parent_id,
                'children': get_children(child)
            } for child in children]

        objects_data = []
        for obj in objects:
            objects_data.append({
                'id': obj.id,
                'object_name_ua': obj.object_name_ua,
                'object_name_ru': obj.object_name_ru,
                'object_name_en': obj.object_name_en,
                'description_ua': obj.description_ua,
                'description_ru': obj.description_ru,
                'description_en': obj.description_en,
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
    """Save or update object"""
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else None
        
        if data:
            object_id = data.get('object_id')
            parent_id = data.get('parent_id')
            system_id = data.get('system_id')
            environment = data.get('environment', 'test')
            object_data = {
                'object_name_ua': data.get('object_name_ua'),
                'object_name_ru': data.get('object_name_ru', ''),
                'object_name_en': data.get('object_name_en', ''),
                'description_ua': data.get('description_ua', ''),
                'description_ru': data.get('description_ru', ''),
                'description_en': data.get('description_en', ''),
                'color': data.get('color', '#6c757d'),
                'asset_id': system_id,
                'environment': environment
            }
        else:
            # Form data
            object_id = request.POST.get('object_id')
            parent_id = request.POST.get('parent_id')
            system_id = request.POST.get('system_id')
            environment = request.POST.get('environment', 'test')
            object_data = {
                'object_name_ua': request.POST.get('object_name_ua'),
                'object_name_ru': request.POST.get('object_name_ru', ''),
                'object_name_en': request.POST.get('object_name_en', ''),
                'description_ua': request.POST.get('description_ua', ''),
                'description_ru': request.POST.get('description_ru', ''),
                'description_en': request.POST.get('description_en', ''),
                'color': request.POST.get('color', '#6c757d'),
                'asset_id': system_id,
                'environment': environment
            }

        if not system_id:
            return JsonResponse({
                'success': False,
                'message': _('System ID is required')
            }, status=400)

        with transaction.atomic():
            # Перевіряємо унікальність імені в межах системи та environment
            name_exists_query = AccessObjectIS.objects.filter(
                asset_id=system_id,
                environment=environment,
                object_name_ua=object_data['object_name_ua']
            )
            
            if object_id:
                name_exists_query = name_exists_query.exclude(id=object_id)
            
            if name_exists_query.exists():
                return JsonResponse({
                    'success': False,
                    'message': _('Object with this name already exists in this system')
                }, status=400)

            if object_id:
                # Оновлюємо існуючий об'єкт
                obj = get_object_or_404(AccessObjectIS, id=object_id)
                
                # Якщо змінюється parent_id, оновлюємо його
                if parent_id and int(parent_id) != obj.parent_id:
                    new_parent = get_object_or_404(AccessObjectIS, id=parent_id)
                    obj.move_to(new_parent)
                elif not parent_id and obj.parent_id:
                    obj.move_to(None)  # Робимо кореневим об'єктом

                # Оновлюємо інші поля
                for key, value in object_data.items():
                    setattr(obj, key, value)
                obj.save()
                message = _('Object updated successfully')
            else:
                # Створюємо новий об'єкт
                if parent_id:
                    parent = get_object_or_404(AccessObjectIS, id=parent_id)
                    obj = AccessObjectIS.objects.create(
                        parent=parent,
                        **object_data
                    )
                else:
                    obj = AccessObjectIS.objects.create(**object_data)
                message = _('Object created successfully')

            return JsonResponse({
                'success': True,
                'message': message,
                'object': {
                    'id': obj.id,
                    'object_name_ua': obj.object_name_ua,
                    'object_name_ru': obj.object_name_ru,
                    'object_name_en': obj.object_name_en,
                    'description_ua': obj.description_ua,
                    'description_ru': obj.description_ru,
                    'description_en': obj.description_en,
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
            ).get(id=object_id)

            logger.info(f"Found object: {obj}")
            logger.info(f"Asset: {obj.asset}")
            
            # Збираємо дані про об'єкт
            data = {
                'id': obj.id,
                'object_name_ua': obj.object_name_ua,
                'object_name_ru': obj.object_name_ru,
                'object_name_en': obj.object_name_en,
                'description_ua': obj.description_ua,
                'description_ru': obj.description_ru,
                'description_en': obj.description_en,
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
                parent_id=parent_id
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
            'role_name_ua': obj_role.role.accessrole_name_ua,
            'role_name_ru': obj_role.role.accessrole_name_ru,
            'role_name_en': obj_role.role.accessrole_name_en,
            'description_ua': obj_role.role.description_ua,
            'description_ru': obj_role.role.description_ru,
            'description_en': obj_role.role.description_en,
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
            is_object_specific=False
        )
        
        # Get object-specific roles created for this object
        object_specific_roles = AccessRoles.objects.filter(
            system_id=system_id,
            environment=environment,
            is_object_specific=True,
            created_for_object_id=object_id
        )
        
        # Combine both querysets
        all_roles = general_roles.union(object_specific_roles).order_by('accessrole_name_ua')
        
        roles_data = [{
            'id': role.id,
            'accessrole_name_ua': role.accessrole_name_ua,
            'accessrole_name_ru': role.accessrole_name_ru,
            'accessrole_name_en': role.accessrole_name_en,
            'description_ua': role.description_ua,
            'description_ru': role.description_ru,
            'description_en': role.description_en,
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
            'accessright_name_ua': obj_right.access_right.accessright_name_ua,
            'accessright_name_ru': obj_right.access_right.accessright_name_ru,
            'accessright_name_en': obj_right.access_right.accessright_name_en,
            'description_ua': obj_right.access_right.description_ua,
            'description_ru': obj_right.access_right.description_ru,
            'description_en': obj_right.access_right.description_en,
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
            Q(system_id=system_id, environment=environment, is_object_specific=True, created_for_object_id=object_id)
        ).distinct().order_by('accessright_name_ua')
        
        rights_data = [{
            'id': right.id,
            'accessright_name_ua': right.accessright_name_ua,
            'accessright_name_ru': right.accessright_name_ru,
            'accessright_name_en': right.accessright_name_en,
            'description_ua': right.description_ua,
            'description_ru': right.description_ru,
            'description_en': right.description_en,
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
        name_ua = data.get('name_ua', '').strip()
        name_ru = data.get('name_ru', '').strip()
        name_en = data.get('name_en', '').strip()
        description_ua = data.get('description_ua', '').strip()
        description_ru = data.get('description_ru', '').strip()
        description_en = data.get('description_en', '').strip()
        color = data.get('color', '#000000')

        logger.info(f"Creating custom access right for object_id: {object_id}")

        # Validate required fields
        if not object_id or not name_ua:
            return JsonResponse({
                'status': 'error',
                'message': 'Object ID and Ukrainian name are required'
            }, status=400)

        # Get the object and its system
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        system = access_object.asset

        # Create the custom access right with enhanced validation
        with transaction.atomic():
            # Use select_for_update to prevent race conditions
            existing_right = AccessRight.objects.select_for_update().filter(
                system=system,
                environment=access_object.environment,
                accessright_name_ua=name_ua
            ).first()

            if existing_right:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Access right with name "{name_ua}" already exists for this system. Please choose a different name.'
                }, status=400)

            # Get the next order value
            max_order = AccessRight.objects.filter(
                system=system,
                environment=access_object.environment
            ).aggregate(max_order=models.Max('order'))['max_order'] or 0

            custom_access_right = AccessRight.objects.create(
                system=system,
                environment=access_object.environment,
                accessright_name_ua=name_ua,
                accessright_name_ru=name_ru,
                accessright_name_en=name_en,
                description_ua=description_ua,
                description_ru=description_ru,
                description_en=description_en,
                color=color,
                order=max_order + 1,
                is_object_specific=True,
                created_for_object=access_object
            )

            logger.info(f"Created custom access right {custom_access_right.id} for object {object_id}")

            return JsonResponse({
                'status': 'success',
                'message': 'Custom access right created successfully',
                'access_right': {
                    'id': custom_access_right.id,
                    'accessright_name_ua': custom_access_right.accessright_name_ua,
                    'accessright_name_ru': custom_access_right.accessright_name_ru,
                    'accessright_name_en': custom_access_right.accessright_name_en,
                    'description_ua': custom_access_right.description_ua,
                    'description_ru': custom_access_right.description_ru,
                    'description_en': custom_access_right.description_en,
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
    """Edit existing custom object access right"""
    try:
        data = json.loads(request.body)
        access_right_id = data.get('access_right_id')
        object_id = data.get('object_id')
        name_ua = data.get('name_ua', '').strip()
        name_ru = data.get('name_ru', '').strip()
        name_en = data.get('name_en', '').strip()
        description_ua = data.get('description_ua', '').strip()
        description_ru = data.get('description_ru', '').strip()
        description_en = data.get('description_en', '').strip()
        color = data.get('color', '#007bff').strip()
        
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
            
        if not name_ua:
            return JsonResponse({
                'status': 'error',
                'message': _('Ukrainian name is required')
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
        
        # Перевіряємо унікальність назви (виключаючи поточне право)
        existing_right = AccessRight.objects.filter(
            system=access_object.asset,
            accessright_name_ua=name_ua
        ).exclude(id=access_right_id).first()
        
        if existing_right:
            return JsonResponse({
                'status': 'error',
                'message': _('Access right with this name already exists')
            }, status=400)
        
        logger.info(f"Updating custom access right {access_right_id} for object {object_id}")
        
        # Оновлюємо право доступу
        access_right.accessright_name_ua = name_ua
        access_right.accessright_name_ru = name_ru
        access_right.accessright_name_en = name_en
        access_right.description_ua = description_ua
        access_right.description_ru = description_ru
        access_right.description_en = description_en
        access_right.color = color
        access_right.save()
        
        logger.info(f"Updated custom access right {access_right_id} for object {object_id}")
        
        return JsonResponse({
            'status': 'success',
            'message': _('Custom access right updated successfully'),
            'access_right': {
                'id': access_right.id,
                'accessright_name_ua': access_right.accessright_name_ua,
                'accessright_name_ru': access_right.accessright_name_ru,
                'accessright_name_en': access_right.accessright_name_en,
                'description_ua': access_right.description_ua,
                'description_ru': access_right.description_ru,
                'description_en': access_right.description_en,
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
        access_right_name = access_right.accessright_name_ua
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
        
        # Get current language
        current_lang = get_language()[:2]  # Get language code (uk, ru, en)
        
        # Get custom access rights for this object
        custom_access_rights = AccessRight.objects.filter(
            system=access_object.asset,
            is_object_specific=True,
            created_for_object_id=object_id
        ).order_by('accessright_name_ua')
        
        # Function to get localized access right name
        def get_localized_name(access_right):
            if current_lang == 'ru' and access_right.accessright_name_ru:
                return access_right.accessright_name_ru
            elif current_lang == 'en' and access_right.accessright_name_en:
                return access_right.accessright_name_en
            else:
                return access_right.accessright_name_ua  # Default fallback to Ukrainian
        
        # Function to get localized description
        def get_localized_description(access_right):
            if current_lang == 'ru' and access_right.description_ru:
                return access_right.description_ru
            elif current_lang == 'en' and access_right.description_en:
                return access_right.description_en
            else:
                return access_right.description_ua or ''  # Default fallback to Ukrainian
        
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
                'accessright_name_ua': access_right.accessright_name_ua,
                'accessright_name_ru': access_right.accessright_name_ru or '',
                'accessright_name_en': access_right.accessright_name_en or '',
                'localized_name': get_localized_name(access_right),  # Current language name
                'description_ua': access_right.description_ua or '',
                'description_ru': access_right.description_ru or '',
                'description_en': access_right.description_en or '',
                'localized_description': get_localized_description(access_right),  # Current language description
                'color': access_right.color,
                'is_object_specific': access_right.is_object_specific,
                'created_for_object_id': access_right.created_for_object_id,
                'is_assigned': is_assigned,
                'can_edit': True,  # Custom access rights can always be edited by object owner
                'can_delete': True  # Custom access rights can be deleted if not assigned or with confirmation
            }
            access_rights_data.append(access_right_data)
        
        # Get localized object name
        def get_localized_object_name(obj):
            if current_lang == 'ru' and obj.object_name_ru:
                return obj.object_name_ru
            elif current_lang == 'en' and obj.object_name_en:
                return obj.object_name_en
            else:
                return obj.object_name_ua
        
        return JsonResponse({
            'status': 'success',
            'object': {
                'id': access_object.id,
                'object_name_ua': access_object.object_name_ua,
                'object_name_ru': access_object.object_name_ru or '',
                'object_name_en': access_object.object_name_en or '',
                'localized_name': get_localized_object_name(access_object)
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
    """Save a custom role for a specific object"""
    try:
        data = json.loads(request.body)
        object_id = data.get('object_id')
        name_ua = data.get('name_ua', '').strip()
        name_ru = data.get('name_ru', '').strip()
        name_en = data.get('name_en', '').strip()
        description_ua = data.get('description_ua', '').strip()
        description_ru = data.get('description_ru', '').strip()
        description_en = data.get('description_en', '').strip()
        color = data.get('color', '#007bff')

        # Валідація
        if not object_id:
            return JsonResponse({
                'status': 'error',
                'message': _('Object ID is required')
            }, status=400)

        if not name_ua:
            return JsonResponse({
                'status': 'error',
                'message': _('Ukrainian name is required')
            }, status=400)

        try:
            access_object = AccessObjectIS.objects.get(id=object_id)
        except AccessObjectIS.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': _('Object not found')
            }, status=404)

        # Перевіряємо унікальність назви в межах системи та середовища
        existing_role = AccessRoles.objects.filter(
            system_id=access_object.asset_id,
            environment=access_object.environment,
            accessrole_name_ua=name_ua
        ).exists()

        if existing_role:
            return JsonResponse({
                'status': 'error',
                'message': _('Role with this name already exists in the system. Please choose a different name.')
            }, status=400)

        # Отримуємо максимальний order в межах системи та середовища
        max_order = AccessRoles.objects.filter(
            system_id=access_object.asset_id,
            environment=access_object.environment
        ).aggregate(
            max_order=models.Max('order')
        )['max_order'] or 0

        # Створюємо кастомну роль
        with transaction.atomic():
            custom_role = AccessRoles.objects.create(
                system_id=access_object.asset_id,
                environment=access_object.environment,
                accessrole_name_ua=name_ua,
                accessrole_name_ru=name_ru,
                accessrole_name_en=name_en,
                description_ua=description_ua,
                description_ru=description_ru,
                description_en=description_en,
                color=color,
                order=max_order + 1,
                is_object_specific=True,
                created_for_object=access_object
            )

            logger.info(f"Created custom role {custom_role.id} for object {object_id}")

            # Повертаємо дані створеної ролі
            role_data = {
                'id': custom_role.id,
                'accessrole_name_ua': custom_role.accessrole_name_ua,
                'accessrole_name_ru': custom_role.accessrole_name_ru,
                'accessrole_name_en': custom_role.accessrole_name_en,
                'description_ua': custom_role.description_ua,
                'description_ru': custom_role.description_ru,
                'description_en': custom_role.description_en,
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
    except Exception as e:
        logger.error(f"Error creating custom object role: {str(e)}")
        
        # Перевіряємо чи це помилка дублікату
        error_message = str(e)
        if 'Duplicate entry' in error_message and 'accessrole_nam' in error_message:
            return JsonResponse({
                'status': 'error',
                'message': _('Role with this name already exists in the system. Please choose a different name.')
            }, status=400)
        
        return JsonResponse({
            'status': 'error',
            'message': _('Error creating custom role')
        }, status=500)


@login_required
@require_POST
@ensure_csrf_cookie
def edit_custom_object_role(request):
    """Edit a custom role for a specific object"""
    try:
        data = json.loads(request.body)
        role_id = data.get('role_id')
        object_id = data.get('object_id')
        name_ua = data.get('name_ua', '').strip()
        name_ru = data.get('name_ru', '').strip()
        name_en = data.get('name_en', '').strip()
        description_ua = data.get('description_ua', '').strip()
        description_ru = data.get('description_ru', '').strip()
        description_en = data.get('description_en', '').strip()
        color = data.get('color', '#007bff')

        # Валідація
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

        if not name_ua:
            return JsonResponse({
                'status': 'error',
                'message': _('Ukrainian name is required')
            }, status=400)

        try:
            custom_role = AccessRoles.objects.get(id=role_id)
        except AccessRoles.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': _('Role not found')
            }, status=404)

        # Перевіряємо що це кастомна роль
        if not custom_role.is_object_specific:
            return JsonResponse({
                'status': 'error',
                'message': _('Cannot edit system roles through this interface')
            }, status=403)

        # Перевіряємо що роль належить цьому об'єкту
        if custom_role.created_for_object_id != int(object_id):
            return JsonResponse({
                'status': 'error',
                'message': _('This role does not belong to the specified object')
            }, status=403)

        # Перевіряємо унікальність назви (виключаючи поточну роль)
        existing_role = AccessRoles.objects.filter(
            system_id=custom_role.system_id,
            accessrole_name_ua=name_ua
        ).exclude(id=role_id).exists()

        if existing_role:
            return JsonResponse({
                'status': 'error',
                'message': _('Role with this name already exists in the system')
            }, status=400)

        # Оновлюємо роль
        with transaction.atomic():
            custom_role.accessrole_name_ua = name_ua
            custom_role.accessrole_name_ru = name_ru
            custom_role.accessrole_name_en = name_en
            custom_role.description_ua = description_ua
            custom_role.description_ru = description_ru
            custom_role.description_en = description_en
            custom_role.color = color
            custom_role.save()

            logger.info(f"Updated custom role {custom_role.id} for object {object_id}")

            # Повертаємо оновлені дані ролі
            role_data = {
                'id': custom_role.id,
                'accessrole_name_ua': custom_role.accessrole_name_ua,
                'accessrole_name_ru': custom_role.accessrole_name_ru,
                'accessrole_name_en': custom_role.accessrole_name_en,
                'description_ua': custom_role.description_ua,
                'description_ru': custom_role.description_ru,
                'description_en': custom_role.description_en,
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

        role_name = role.accessrole_name_ua
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
    """Get custom roles for a specific object"""
    try:
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        
        # Get current language
        current_lang = get_language()[:2]  # Get language code (uk, ru, en)
        
        # Get custom roles for this object
        custom_roles = AccessRoles.objects.filter(
            system=access_object.asset,
            is_object_specific=True,
            created_for_object_id=object_id
        ).order_by('accessrole_name_ua')
        
        # Function to get localized role name
        def get_localized_name(role):
            if current_lang == 'ru' and role.accessrole_name_ru:
                return role.accessrole_name_ru
            elif current_lang == 'en' and role.accessrole_name_en:
                return role.accessrole_name_en
            else:
                return role.accessrole_name_ua  # Default fallback to Ukrainian
        
        # Function to get localized description
        def get_localized_description(role):
            if current_lang == 'ru' and role.description_ru:
                return role.description_ru
            elif current_lang == 'en' and role.description_en:
                return role.description_en
            else:
                return role.description_ua or ''  # Default fallback to Ukrainian
        
        roles_data = []
        for role in custom_roles:
            # Check if role is currently assigned to this object
            is_assigned = ObjectRoles.objects.filter(
                access_object=access_object,
                role=role,
                is_active=True
            ).exists()
            
            role_data = {
                'id': role.id,
                'accessrole_name_ua': role.accessrole_name_ua,
                'accessrole_name_ru': role.accessrole_name_ru or '',
                'accessrole_name_en': role.accessrole_name_en or '',
                'localized_name': get_localized_name(role),  # Current language name
                'description_ua': role.description_ua or '',
                'description_ru': role.description_ru or '',
                'description_en': role.description_en or '',
                'localized_description': get_localized_description(role),  # Current language description
                'color': role.color,
                'is_object_specific': role.is_object_specific,
                'created_for_object_id': role.created_for_object_id,
                'is_assigned': is_assigned,
                'can_edit': True,  # Custom roles can always be edited by object owner
                'can_delete': True  # Custom roles can be deleted if not assigned or with confirmation
            }
            roles_data.append(role_data)
        
        # Get localized object name
        def get_localized_object_name(obj):
            if current_lang == 'ru' and obj.object_name_ru:
                return obj.object_name_ru
            elif current_lang == 'en' and obj.object_name_en:
                return obj.object_name_en
            else:
                return obj.object_name_ua
        
        return JsonResponse({
            'success': True,
            'object': {
                'id': access_object.id,
                'object_name_ua': access_object.object_name_ua,
                'object_name_ru': access_object.object_name_ru or '',
                'object_name_en': access_object.object_name_en or '',
                'localized_name': get_localized_object_name(access_object)
            },
            'roles': roles_data,
            'total_count': len(roles_data),
            'current_language': current_lang
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
        current_lang = get_language()[:2]  # Get language code (uk, ru, en)
        
        # Get assigned functions with their actual function data
        object_functions = AccessObjectFunction.objects.filter(
            access_object=access_object,
            is_active=True
        ).select_related('function', 'function__parent').order_by('order')
        
        # Get the actual assigned functions for hierarchy building
        assigned_function_ids = set(obj_func.function.id for obj_func in object_functions)
        
        # Get all functions for this system to build proper hierarchy
        all_functions = AccessFunctionIS.objects.filter(
            Q(asset=access_object.asset, is_object_specific=False) |
            Q(asset=access_object.asset, is_object_specific=True, created_for_object=access_object)
        ).select_related('parent').order_by('tree_id', 'lft')
        
        # Build hierarchical structure for assigned functions
        assigned_functions = []
        
        # Function to get localized function name
        def get_localized_name(func):
            if current_lang == 'ru' and func.accesfunct_name_ru:
                return func.accesfunct_name_ru
            elif current_lang == 'en' and func.accesfunct_name_en:
                return func.accesfunct_name_en
            else:
                return func.accesfunct_name_ua  # Default fallback to Ukrainian
        
        # Function to get localized description
        def get_localized_description(func):
            if current_lang == 'ru' and func.description_ru:
                return func.description_ru
            elif current_lang == 'en' and func.description_en:
                return func.description_en
            else:
                return func.description_ua or ''  # Default fallback to Ukrainian
        
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
                
                if assignment:  # Only add if function is actually assigned
                    function_data = {
                        'id': parent_func.id,
                        'assignment_id': assignment.id,
                        'accesfunct_name_ua': parent_func.accesfunct_name_ua,
                        'accesfunct_name_ru': parent_func.accesfunct_name_ru or '',
                        'accesfunct_name_en': parent_func.accesfunct_name_en or '',
                        'localized_name': get_localized_name(parent_func),  # Current language name
                        'description_ua': parent_func.description_ua or '',
                        'description_ru': parent_func.description_ru or '',
                        'description_en': parent_func.description_en or '',
                        'localized_description': get_localized_description(parent_func),  # Current language description
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
        
        # Get localized object name
        def get_localized_object_name(obj):
            if current_lang == 'ru' and obj.object_name_ru:
                return obj.object_name_ru
            elif current_lang == 'en' and obj.object_name_en:
                return obj.object_name_en
            else:
                return obj.object_name_ua
        
        return JsonResponse({
            'success': True,
            'object': {
                'id': access_object.id,
                'object_name_ua': access_object.object_name_ua,
                'object_name_ru': access_object.object_name_ru or '',
                'object_name_en': access_object.object_name_en or '',
                'localized_name': get_localized_object_name(access_object)
            },
            'functions': assigned_functions,
            'current_language': current_lang
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
                        skipped_functions.append(function.accesfunct_name_ua)
                        continue
                    
                    # Add function with children
                    assigned = AccessObjectFunction.assign_function_with_children(
                        access_object=access_object,
                        function=function,
                        user=request.user
                    )
                    
                    added_functions.extend([f.accesfunct_name_ua for f in assigned])
                    
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
        current_lang = get_language()[:2]  # Get language code (uk, ru, en)
        
        # Get all functions for this system using tree ordering with custom order
        all_functions = AccessFunctionIS.objects.filter(
            Q(asset=access_object.asset, environment=environment, is_object_specific=False) |
            Q(asset=access_object.asset, environment=environment, is_object_specific=True, created_for_object=access_object)
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
        
        # Function to get localized function name
        def get_localized_name(func):
            if current_lang == 'ru' and func.accesfunct_name_ru:
                return func.accesfunct_name_ru
            elif current_lang == 'en' and func.accesfunct_name_en:
                return func.accesfunct_name_en
            else:
                return func.accesfunct_name_ua  # Default fallback to Ukrainian
        
        # Function to get localized description
        def get_localized_description(func):
            if current_lang == 'ru' and func.description_ru:
                return func.description_ru
            elif current_lang == 'en' and func.description_en:
                return func.description_en
            else:
                return func.description_ua or ''  # Default fallback to Ukrainian
        
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
                    'accesfunct_name_ua': parent_func.accesfunct_name_ua,
                    'accesfunct_name_ru': parent_func.accesfunct_name_ru or '',
                    'accesfunct_name_en': parent_func.accesfunct_name_en or '',
                    'localized_name': get_localized_name(parent_func),  # Current language name
                    'description_ua': parent_func.description_ua or '',
                    'description_ru': parent_func.description_ru or '',
                    'description_en': parent_func.description_en or '',
                    'localized_description': get_localized_description(parent_func),  # Current language description
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
        
        # Get localized object name
        def get_localized_object_name(obj):
            if current_lang == 'ru' and obj.object_name_ru:
                return obj.object_name_ru
            elif current_lang == 'en' and obj.object_name_en:
                return obj.object_name_en
            else:
                return obj.object_name_ua
        
        return JsonResponse({
            'success': True,
            'object': {
                'id': access_object.id,
                'object_name_ua': access_object.object_name_ua,
                'object_name_ru': access_object.object_name_ru or '',
                'object_name_en': access_object.object_name_en or '',
                'localized_name': get_localized_object_name(access_object),
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
                'accesfunct_name_ua': function.accesfunct_name_ua,
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
                    'accesfunct_name_ua': function.accesfunct_name_ua,
                    'accesfunct_name_ru': function.accesfunct_name_ru,
                    'accesfunct_name_en': function.accesfunct_name_en,
                    'description_ua': function.description_ua,
                    'description_ru': function.description_ru,
                    'description_en': function.description_en,
                    'color': function.color,
                    'order': function.order,
                    'parent_id': function.parent_id,
                    'level': function.level,
                    'children_count': function.get_children().count(),
                    'usage_count': function.object_assignments.count()
                }
            })
        
        elif request.method == 'POST':
            # Update function
            function.accesfunct_name_ua = request.POST.get('accesfunct_name_ua', function.accesfunct_name_ua)
            function.accesfunct_name_ru = request.POST.get('accesfunct_name_ru', function.accesfunct_name_ru)
            function.accesfunct_name_en = request.POST.get('accesfunct_name_en', function.accesfunct_name_en)
            function.description_ua = request.POST.get('description_ua', function.description_ua)
            function.description_ru = request.POST.get('description_ru', function.description_ru)
            function.description_en = request.POST.get('description_en', function.description_en)
            function.color = request.POST.get('color', function.color)
            function.order = int(request.POST.get('order', function.order))
            
            # Validate required fields
            if not function.accesfunct_name_ua:
                return JsonResponse({'error': _('Function name (UA) is required')}, status=400)
            
            # Check for duplicate names in same asset (excluding current function)
            if AccessFunctionIS.objects.filter(
                asset=function.asset,
                accesfunct_name_ua=function.accesfunct_name_ua
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
            
            function_name = function.accesfunct_name_ua
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
        functions = role.functions.all().values('id', 'accesfunct_name_ua')
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
        functions = AccessFunctionIS.objects.filter(asset=asset).order_by('tree_id', 'lft')
        
        def format_function_tree(func, level=0, max_depth=3):
            children = []
            if level < max_depth:
                # Get direct children only (not all descendants)
                direct_children = functions.filter(parent=func)
                for child in direct_children:
                    children.append(format_function_tree(child, level + 1, max_depth))
            
            return {
                'id': func.id,
                'accesfunct_name_ua': func.accesfunct_name_ua,
                'accesfunct_name_ru': func.accesfunct_name_ru,
                'accesfunct_name_en': func.accesfunct_name_en,
                'description_ua': func.description_ua,
                'description_ru': func.description_ru,
                'description_en': func.description_en,
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
    """Create a custom function for a specific object"""
    try:
        data = json.loads(request.body)
        object_id = data.get('object_id')
        name_ua = data.get('name_ua', '').strip()
        name_ru = data.get('name_ru', '').strip()
        name_en = data.get('name_en', '').strip()
        description_ua = data.get('description_ua', '').strip()
        description_ru = data.get('description_ru', '').strip()
        description_en = data.get('description_en', '').strip()
        color = data.get('color', '#007bff')
        parent_id = data.get('parent_id')

        logger.info(f"Creating custom function for object_id: {object_id}")

        # Validate required fields
        if not object_id or not name_ua:
            return JsonResponse({
                'status': 'error',
                'message': 'Object ID and Ukrainian name are required'
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

        # Create the custom function with enhanced validation
        with transaction.atomic():
            # Check for duplicate names in system for this object
            existing_function = AccessFunctionIS.objects.filter(
                Q(is_object_specific=False) | Q(created_for_object=access_object),
                asset=system,
                environment=access_object.environment,
                accesfunct_name_ua=name_ua
            ).first()

            if existing_function:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Function with name "{name_ua}" already exists for this system/object. Please choose a different name.'
                }, status=400)

            # Get the next order value
            max_order = AccessFunctionIS.objects.filter(
                asset=system,
                environment=access_object.environment
            ).aggregate(max_order=models.Max('order'))['max_order'] or 0

            custom_function = AccessFunctionIS.objects.create(
                asset=system,
                environment=access_object.environment,
                parent=parent_function,
                accesfunct_name_ua=name_ua,
                accesfunct_name_ru=name_ru,
                accesfunct_name_en=name_en,
                description_ua=description_ua,
                description_ru=description_ru,
                description_en=description_en,
                color=color,
                order=max_order + 1,
                is_object_specific=True,
                created_for_object=access_object
            )

            logger.info(f"Created custom function {custom_function.id} for object {object_id}")

            return JsonResponse({
                'status': 'success',
                'message': 'Custom function created successfully',
                'function': {
                    'id': custom_function.id,
                    'accesfunct_name_ua': custom_function.accesfunct_name_ua,
                    'accesfunct_name_ru': custom_function.accesfunct_name_ru,
                    'accesfunct_name_en': custom_function.accesfunct_name_en,
                    'description_ua': custom_function.description_ua,
                    'description_ru': custom_function.description_ru,
                    'description_en': custom_function.description_en,
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
        # Handle database constraint violations
        if 'Duplicate entry' in str(e) and 'accesfunct_name' in str(e):
            return JsonResponse({
                'status': 'error',
                'message': f'Function with this name already exists for this system. Please choose a different name.'
            }, status=400)
        else:
            logger.error(f"Database integrity error creating custom function: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Database constraint violation. Please try again.'
            }, status=400)
    except Exception as e:
        logger.error(f"Error creating custom function: {str(e)}")
        
        # Enhanced error handling for specific duplicate entry errors
        if 'Duplicate entry' in str(e):
            return JsonResponse({
                'status': 'error',
                'message': f'Function with this name already exists for this system. Please choose a different name.'
            }, status=400)
        
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
def edit_custom_object_function(request):
    """Edit a custom function for a specific object"""
    try:
        data = json.loads(request.body)
        function_id = data.get('function_id')
        object_id = data.get('object_id')
        name_ua = data.get('name_ua', '').strip()
        name_ru = data.get('name_ru', '').strip()
        name_en = data.get('name_en', '').strip()
        description_ua = data.get('description_ua', '').strip()
        description_ru = data.get('description_ru', '').strip()
        description_en = data.get('description_en', '').strip()
        color = data.get('color', '#007bff')
        parent_id = data.get('parent_id')

        logger.info(f"Editing custom function {function_id} for object_id: {object_id}")

        # Validate required fields
        if not function_id or not object_id or not name_ua:
            return JsonResponse({
                'status': 'error',
                'message': 'Function ID, Object ID and Ukrainian name are required'
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
            existing_function = AccessFunctionIS.objects.filter(
                Q(is_object_specific=False) | Q(created_for_object=access_object),
                asset=system,
                accesfunct_name_ua=name_ua
            ).exclude(id=function_id).first()

            if existing_function:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Function with name "{name_ua}" already exists for this system/object. Please choose a different name.'
                }, status=400)

            # Update parent if changed
            if parent_id and (not custom_function.parent or custom_function.parent.id != int(parent_id)):
                custom_function.move_to(parent_function)
            elif not parent_id and custom_function.parent:
                custom_function.move_to(None)  # Make it a root function

            # Update other fields
            custom_function.accesfunct_name_ua = name_ua
            custom_function.accesfunct_name_ru = name_ru
            custom_function.accesfunct_name_en = name_en
            custom_function.description_ua = description_ua
            custom_function.description_ru = description_ru
            custom_function.description_en = description_en
            custom_function.color = color
            custom_function.save()

            logger.info(f"Updated custom function {custom_function.id} for object {object_id}")

            return JsonResponse({
                'status': 'success',
                'message': 'Custom function updated successfully',
                'function': {
                    'id': custom_function.id,
                    'accesfunct_name_ua': custom_function.accesfunct_name_ua,
                    'accesfunct_name_ru': custom_function.accesfunct_name_ru,
                    'accesfunct_name_en': custom_function.accesfunct_name_en,
                    'description_ua': custom_function.description_ua,
                    'description_ru': custom_function.description_ru,
                    'description_en': custom_function.description_en,
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
                function_name = custom_function.accesfunct_name_ua
                
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
        current_lang = get_language()[:2]  # Get language code (uk, ru, en)
        
        # Get custom functions for this object - convert to list for easier processing
        custom_functions_qs = AccessFunctionIS.objects.filter(
            asset=access_object.asset,
            is_object_specific=True,
            created_for_object=access_object
        ).select_related('parent').order_by('tree_id', 'lft')
        
        custom_functions = list(custom_functions_qs)
        
        # Function to get localized function name
        def get_localized_name(func):
            if current_lang == 'ru' and func.accesfunct_name_ru:
                return func.accesfunct_name_ru
            elif current_lang == 'en' and func.accesfunct_name_en:
                return func.accesfunct_name_en
            else:
                return func.accesfunct_name_ua  # Default fallback to Ukrainian
        
        # Function to get localized description
        def get_localized_description(func):
            if current_lang == 'ru' and func.description_ru:
                return func.description_ru
            elif current_lang == 'en' and func.description_en:
                return func.description_en
            else:
                return func.description_ua or ''  # Default fallback to Ukrainian
        
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
                    'accesfunct_name_ua': parent_func.accesfunct_name_ua,
                    'accesfunct_name_ru': parent_func.accesfunct_name_ru or '',
                    'accesfunct_name_en': parent_func.accesfunct_name_en or '',
                    'localized_name': get_localized_name(parent_func),  # Current language name
                    'description_ua': parent_func.description_ua or '',
                    'description_ru': parent_func.description_ru or '',
                    'description_en': parent_func.description_en or '',
                    'localized_description': get_localized_description(parent_func),  # Current language description
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
        
        # Get localized object name
        def get_localized_object_name(obj):
            if current_lang == 'ru' and obj.object_name_ru:
                return obj.object_name_ru
            elif current_lang == 'en' and obj.object_name_en:
                return obj.object_name_en
            else:
                return obj.object_name_ua
        
        return JsonResponse({
            'success': True,
            'object': {
                'id': access_object.id,
                'object_name_ua': access_object.object_name_ua,
                'object_name_ru': access_object.object_name_ru or '',
                'object_name_en': access_object.object_name_en or '',
                'localized_name': get_localized_object_name(access_object),
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
            """
            Рекурсивно будує ієрархію функцій з дочірніми елементами
            """
            hierarchy = []
            
            # Фільтруємо функції по батьківському елементу
            parent_functions = [f for f in functions if f.parent_id == parent]
            
            for func in parent_functions:
                function_data = {
                    'id': func.id,
                    'accesfunct_name_ua': func.accesfunct_name_ua,
                    'accesfunct_name_en': getattr(func, 'accesfunct_name_en', func.accesfunct_name_ua),
                    'description_ua': func.description_ua,
                    'description_en': getattr(func, 'description_en', func.description_ua),
                    'color': func.color,
                    'function_type': 'custom' if func.is_object_specific else 'default',
                    'level': level,
                    'children': []
                }
                
                # Додаємо дочірні функції, якщо не досягли максимальної глибини
                if level < max_depth:
                    function_data['children'] = build_function_hierarchy(
                        functions, func.id, level + 1, max_depth
                    )
                
                hierarchy.append(function_data)
            
            return hierarchy
        
        for object_role in object_roles:
            role = object_role.role
            
            # Спочатку перевіряємо, чи є об'єкт-специфічні функції для цієї ролі
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
                
                # Створюємо записи ObjectRoleFunctions для функцій, які є і в глобальній ролі, і в об'єкті
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
            
            # Отримуємо всі функції для побудови ієрархії
            functions_list = [obj_role_func.function for obj_role_func in object_role_functions]
            
            # Будуємо ієрархію функцій
            functions_hierarchy = build_function_hierarchy(functions_list)

            # Визначаємо, чи є роль кастомною (створеною для об'єкта)
            is_custom = role.is_object_specific and role.created_for_object == obj

            roles_functions_data.append({
                'role': {
                    'id': role.id,
                    'accessrole_name_ua': role.accessrole_name_ua,
                    'accessrole_name_en': getattr(role, 'accessrole_name_en', role.accessrole_name_ua),
                    'description_ua': role.description_ua,
                    'description_en': getattr(role, 'description_en', role.description_ua),
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
                'accesfunct_name_ua': func.accesfunct_name_ua,
                'accesfunct_name_en': getattr(func, 'accesfunct_name_en', func.accesfunct_name_ua),
                'description_ua': func.description_ua,
                'description_en': getattr(func, 'description_en', func.description_ua),
                'color': func.color,
                'function_type': 'custom' if func.is_object_specific else 'default'
            })

        return JsonResponse({
            'success': True,
            'functions': functions_data,
            'role': {
                'id': role.id,
                'accessrole_name_ua': role.accessrole_name_ua,
                'accessrole_name_en': getattr(role, 'accessrole_name_en', role.accessrole_name_ua),
                'description_ua': role.description_ua,
                'description_en': getattr(role, 'description_en', role.description_ua),
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
        
        # DEBUG: Log existing ObjectStatus records for this object
        existing_statuses = ObjectStatus.objects.filter(
            access_object=access_object,
            is_active=True
        ).values('id', 'status_id', 'status__accessstatus_name_ua', 'is_active')
        
        logger.info(f"DEBUG: Existing ObjectStatus records for object {object_id}: {list(existing_statuses)}")
        logger.info(f"DEBUG: Looking to remove status_ids: {status_ids}")
        
        with transaction.atomic():
            # DEBUG: Check what the query would find before deleting
            query_result = ObjectStatus.objects.filter(
                access_object=access_object,
                status_id__in=status_ids,
                is_active=True
            )
            
            logger.info(f"DEBUG: Query found {query_result.count()} records to delete")
            for record in query_result.values('id', 'status_id', 'status__accessstatus_name_ua'):
                logger.info(f"DEBUG: Record to delete: {record}")
            
            # Remove the specified statuses
            removed_count = query_result.delete()[0]
            
            logger.info(f"Successfully removed {removed_count} statuses from object {object_id}")
            
            return JsonResponse({
                'success': True,
                'message': _('Statuses removed successfully'),
                'removed_count': removed_count
            })
            
    except Exception as e:
        logger.error(f"Error removing object statuses: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(['GET'])
def get_custom_object_statuses(request, object_id):
    """Get custom statuses for a specific object"""
    try:
        access_object = get_object_or_404(AccessObjectIS, id=object_id)
        
        # Get current language
        current_lang = get_language()[:2]  # Get language code (uk, ru, en)
        
        # Get custom statuses for this object
        custom_statuses = AccessStatus.objects.filter(
            system=access_object.asset,
            is_object_specific=True,
            created_for_object=access_object
        ).order_by('accessstatus_name_ua')
        
        # Function to get localized status name
        def get_localized_name(status):
            if current_lang == 'ru' and status.accessstatus_name_ru:
                return status.accessstatus_name_ru
            elif current_lang == 'en' and status.accessstatus_name_en:
                return status.accessstatus_name_en
            else:
                return status.accessstatus_name_ua  # Default fallback to Ukrainian
        
        # Function to get localized description
        def get_localized_description(status):
            if current_lang == 'ru' and status.description_ru:
                return status.description_ru
            elif current_lang == 'en' and status.description_en:
                return status.description_en
            else:
                return status.description_ua or ''  # Default fallback to Ukrainian
        
        # Build status data
        statuses_data = []
        for status in custom_statuses:
            # Check if status is currently assigned to this object
            is_assigned = ObjectStatus.objects.filter(
                access_object=access_object,
                status=status,
                is_active=True
            ).exists()
            
            status_data = {
                'id': status.id,
                'accessstatus_name_ua': status.accessstatus_name_ua,
                'accessstatus_name_ru': status.accessstatus_name_ru or '',
                'accessstatus_name_en': status.accessstatus_name_en or '',
                'localized_name': get_localized_name(status),  # Current language name
                'description_ua': status.description_ua or '',
                'description_ru': status.description_ru or '',
                'description_en': status.description_en or '',
                'localized_description': get_localized_description(status),  # Current language description
                'color': status.color,
    
                'is_object_specific': status.is_object_specific,
                'created_for_object_id': status.created_for_object_id,
                'is_assigned': is_assigned,
                'can_edit': True,  # Custom statuses can always be edited by object owner
                'can_delete': True  # Custom statuses can be deleted if not assigned or with confirmation
            }
            statuses_data.append(status_data)
        
        # Get localized object name
        def get_localized_object_name(obj):
            if current_lang == 'ru' and obj.object_name_ru:
                return obj.object_name_ru
            elif current_lang == 'en' and obj.object_name_en:
                return obj.object_name_en
            else:
                return obj.object_name_ua
        
        return JsonResponse({
            'success': True,
            'object': {
                'id': access_object.id,
                'object_name_ua': access_object.object_name_ua,
                'object_name_ru': access_object.object_name_ru or '',
                'object_name_en': access_object.object_name_en or '',
                'localized_name': get_localized_object_name(access_object),
                'system_name': access_object.asset.name if access_object.asset else 'Unknown'
            },
            'statuses': statuses_data,
            'total_statuses': len(statuses_data),
            'current_language': current_lang
        })
        
    except Exception as e:
        logger.error(f"Error getting custom object statuses: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

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
                object_name_ua=original_object.object_name_ua + ' (Копія)',
                object_name_ru=(original_object.object_name_ru + ' (Копия)') if original_object.object_name_ru else '',
                object_name_en=(original_object.object_name_en + ' (Copy)') if original_object.object_name_en else '',
                description_ua=original_object.description_ua,
                description_ru=original_object.description_ru,
                description_en=original_object.description_en,
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
                    'object_name_ua': new_object.object_name_ua,
                    'object_name_ru': new_object.object_name_ru,
                    'object_name_en': new_object.object_name_en,
                    'description_ua': new_object.description_ua,
                    'description_ru': new_object.description_ru,
                    'description_en': new_object.description_en,
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
            
            # Copy Statuses
            if 'statuses' in data_types:
                copied_statuses = copy_statuses_between_environments(system, source_environment, target_environment)
                copied_items['statuses'] = copied_statuses
            
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
            object_name_ua=source_obj.object_name_ua,
            environment=target_env
        ).first()
        
        if not existing_obj:
            # Create new object with target environment
            new_obj = AccessObjectIS.objects.create(
                asset=system,
                parent=None,  # Will be set after all objects are created
                object_name_ua=source_obj.object_name_ua,
                object_name_ru=source_obj.object_name_ru,
                object_name_en=source_obj.object_name_en,
                description_ua=source_obj.description_ua,
                description_ru=source_obj.description_ru,
                description_en=source_obj.description_en,
                color=source_obj.color,
                order=source_obj.order,
                environment=target_env
            )
            
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
            accessrole_name_ua=source_role.accessrole_name_ua,
            environment=target_env,
            is_object_specific=False
        ).first()
        
        if not existing_role:
            # Create new role only if it doesn't exist
            new_role = AccessRoles.objects.create(
                system=system,
                accessrole_name_ua=source_role.accessrole_name_ua,
                accessrole_name_ru=source_role.accessrole_name_ru,
                accessrole_name_en=source_role.accessrole_name_en,
                description_ua=source_role.description_ua,
                description_ru=source_role.description_ru,
                description_en=source_role.description_en,
                color=source_role.color,
                order=source_role.order,
                environment=target_env,
                is_object_specific=False
            )
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
            accessright_name_ua=source_right.accessright_name_ua,
            environment=target_env,
            is_object_specific=False
        ).first()
        
        if not existing_right:
            # Create new access right only if it doesn't exist
            new_right = AccessRight.objects.create(
                accessright_name_ua=source_right.accessright_name_ua,
                accessright_name_ru=source_right.accessright_name_ru,
                accessright_name_en=source_right.accessright_name_en,
                description_ua=source_right.description_ua,
                description_ru=source_right.description_ru,
                description_en=source_right.description_en,
                color=source_right.color,
                order=source_right.order,
                environment=target_env,
                system=system,
                is_object_specific=False
            )
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
            accesfunct_name_ua=source_func.accesfunct_name_ua,
            environment=target_env,
            is_object_specific=False
        ).first()
        
        if not existing_func:
            # Create new function with target environment
            new_func = AccessFunctionIS.objects.create(
                asset=system,
                parent=None,  # Will be set after all functions are created
                accesfunct_name_ua=source_func.accesfunct_name_ua,
                accesfunct_name_ru=source_func.accesfunct_name_ru,
                accesfunct_name_en=source_func.accesfunct_name_en,
                description_ua=source_func.description_ua,
                description_ru=source_func.description_ru,
                description_en=source_func.description_en,
                color=source_func.color,
                order=source_func.order,
                environment=target_env,
                is_object_specific=False
            )
            
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
            accessstatus_name_ua=source_status.accessstatus_name_ua,
            environment=target_env,
            is_object_specific=False
        ).first()
        
        if not existing_status:
            # Create new status only if it doesn't exist
            new_status = AccessStatus.objects.create(
                system=system,
                accessstatus_name_ua=source_status.accessstatus_name_ua,
                accessstatus_name_ru=source_status.accessstatus_name_ru,
                accessstatus_name_en=source_status.accessstatus_name_en,
                description_ua=source_status.description_ua,
                description_ru=source_status.description_ru,
                description_en=source_status.description_en,
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
    source_obj_map = {obj.object_name_ua: obj for obj in source_objects}
    target_obj_map = {obj.object_name_ua: obj for obj in target_objects}
    
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
                    accessrole_name_ua=source_role.role.accessrole_name_ua
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
                    accessright_name_ua=source_right.access_right.accessright_name_ua
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
                    accesfunct_name_ua=source_func.function.accesfunct_name_ua
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
            
            # Copy object statuses
            source_statuses = ObjectStatus.objects.filter(access_object=source_obj)
            for source_status in source_statuses:
                # Find corresponding status in target environment
                target_status = AccessStatus.objects.filter(
                    system=system,
                    environment=target_env,
                    accessstatus_name_ua=source_status.status.accessstatus_name_ua
                ).first()
                
                if target_status:
                    ObjectStatus.objects.get_or_create(
                        access_object=target_obj,
                        status=target_status,
                        defaults={
                            'order': source_status.order,
                            'is_active': source_status.is_active
                        }
                    )
                    copied_data['object_statuses'] += 1
    
    return copied_data