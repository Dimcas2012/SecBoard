# SecBoard\app_access\manage_is_view.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _, get_language, activate
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf import settings

from .models import (
    SystemAccess, AccessRight, AccessFunctionIS, AccessFunctionISTranslation,
    AccessStatus, ApprovingPerson, AccessApprover, AccessRoles, AccessRolesTranslation,
    AccessObjectIS,
    ObjectRoles, ObjectAccessRights, AccessObjectFunction,
    ObjectRoleFunctions, ObjectFunctionRightMapping, AccessISAM, AccessRequestSequence,
    AccessConfigIsGuide, AccessConfigIsGuideTranslation,
    ManageAccessRequestsGuide, ManageAccessRequestsGuideTranslation,
)
from .matrix_view import (
    has_access_config_is_permission,
    has_access_manage_ar_permission,
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
from app_conf.models import Company, Country
from app_asset.models import AccessAssets, InformationAsset
from app_access.models import AccessRequest, AccessRequestAdminStatusHistory
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .pagination_utils import ACCESS_TABLE_PAGE_SIZE_OPTIONS, get_access_table_page_size
import json
import time
from app_cabinet.models import CabinetUser, CabinetGroup

logger = logging.getLogger(__name__)


def _get_department_display(department):
    """Department name for current site language; fallback to English if not defined for current language."""
    if not department:
        return ''
    lang = (get_language() or 'en')[:2].lower()
    name = (department.get_name(lang) or '').strip()
    if name:
        return name
    return (department.get_name('en') or '').strip()


def _get_position_display(position):
    """Position name for current site language; fallback to English if not defined for current language."""
    if not position:
        return ''
    lang = (get_language() or 'en')[:2].lower()
    name = (position.get_name(lang) or '').strip()
    if name:
        return name
    return (position.get_name('en') or '').strip()


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
                | Q(access_records__roles__translations__name_local__iexact=role_filter)
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
            name = r.get_name(lang_code) or r.name or ''
        except Exception:
            name = r.name or ''
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
        # Original grant request for revoke (for requested_role fallback)
        original_request = None
        if req.request_type == 'revoke':
            import re
            if req.notes and re.search(r'request #(\d+)', req.notes):
                match = re.search(r'request #(\d+)', req.notes)
                if match:
                    try:
                        original_request = AccessRequest.objects.filter(
                            id=int(match.group(1)), request_type='grant', status='approved', admin_status='granted'
                        ).first()
                    except (ValueError, TypeError):
                        pass
            if original_request is None and getattr(req, 'revoked_grant_access_record_ids', None):
                ids_list = req.revoked_grant_access_record_ids or []
                if ids_list:
                    try:
                        parts = str(ids_list[0]).split('.')
                        if len(parts) >= 2 and parts[1].isdigit():
                            orig = AccessRequest.objects.filter(
                                id=int(parts[1]), request_type='grant', status='approved', admin_status='granted'
                            ).first()
                            if orig:
                                original_request = orig
                    except (IndexError, ValueError, TypeError):
                        pass

        requested_role_by_record = {}
        if getattr(req, 'requested_access_record_roles', None) and isinstance(req.requested_access_record_roles, list):
            for item in req.requested_access_record_roles:
                if isinstance(item, dict) and 'access_record_id' in item and 'role_id' in item:
                    requested_role_by_record[item['access_record_id']] = item['role_id']
        if req.request_type == 'revoke' and original_request is not None and getattr(original_request, 'requested_access_record_roles', None) and isinstance(original_request.requested_access_record_roles, list):
            for item in original_request.requested_access_record_roles:
                if isinstance(item, dict) and 'access_record_id' in item and 'role_id' in item:
                    requested_role_by_record[item['access_record_id']] = item['role_id']

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
                role_name = role.get_name(current_language) or role.name or ''

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
                object_name = obj.get_name(current_language) if hasattr(obj, 'get_name') else (obj.name or '')
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

            requested_role_info = None
            rid = requested_role_by_record.get(access_record.id)
            if rid:
                try:
                    req_role = AccessRoles.objects.get(id=rid)
                    requested_role_info = {
                        'name': req_role.get_name(current_language) or req_role.name or '',
                        'color': req_role.color or '#6c757d',
                    }
                except AccessRoles.DoesNotExist:
                    pass

            access_records_data.append({
                'id': access_record.id,
                'object_id': obj.id if obj else None,
                'object_name': object_name,
                'object_color': object_color,
                'roles': roles_payload,
                'requested_role': requested_role_info,
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


@login_required
@require_http_methods(["GET"])
def manage_access_requests_guide(request):
    """Return JSON { content: html } for the Manage Access Requests guide (localized)."""
    if not has_access_manage_ar_permission(request.user):
        return JsonResponse({'content': ''})
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = ManageAccessRequestsGuide.objects.first()
    if guide:
        if country:
            trans = ManageAccessRequestsGuideTranslation.objects.filter(guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = ManageAccessRequestsGuideTranslation.objects.filter(guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def manage_access_requests_guide_translate(request):
    """API for AI translation of Manage Access Requests guide content (admin)."""
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
        
        from django.conf import settings as django_settings
        object_form_languages = list(getattr(django_settings, 'LANGUAGES', [('en', 'English')])) or [('en', 'English')]
        context = {
            'title': _('Access configuration Information Systems'),
            'active_tab': 'access_config_is',
            'companies': user_companies,
            'can_add_access_config_is': can_add,
            'can_edit_access_config_is': can_edit,
            'can_delete_access_config_is': can_delete,
            'object_form_languages': object_form_languages,
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
@require_http_methods(["GET"])
def access_config_is_guide(request):
    """Return JSON { content: html } for the Access Config IS guide (localized)."""
    if not has_access_config_is_permission(request.user):
        return JsonResponse({'content': ''})
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = AccessConfigIsGuide.objects.first()
    if guide:
        if country:
            trans = AccessConfigIsGuideTranslation.objects.filter(guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = AccessConfigIsGuideTranslation.objects.filter(guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def access_config_is_guide_translate(request):
    """API for AI translation of Access Config IS guide content (admin)."""
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
def access_right_list(request):
    if request.method == 'POST':
        # Handle creation
        try:
            from app_access.models import AccessRightTranslation
            from .manage_is_objects_view import _get_country_for_lang
            name_en = request.POST.get('accessright_name_en') or request.POST.get('accessright_name_ua') or ''
            right = AccessRight.objects.create(
                name=name_en,
                description=request.POST.get('description_en') or request.POST.get('description_ua') or '',
                color=request.POST.get('color', '#000000'),
                system_id=request.POST.get('system_id'),
                environment=request.POST.get('environment', 'test')
            )
            for lang_label in ('ua', 'ru'):
                country = _get_country_for_lang(lang_label)
                if country:
                    name_val = request.POST.get(f'accessright_name_{lang_label}', '')
                    desc_val = request.POST.get(f'description_{lang_label}', '')
                    AccessRightTranslation.objects.create(
                        access_right=right, country=country,
                        name_local=name_val, description=desc_val
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
                for field in ['name', 'description', 'color']:
                    logger.debug(f"{field}: {request.POST.get(field)}")

            with transaction.atomic():
                system_id = request.POST.get('system_id')
                environment = request.POST.get('environment', 'test')
                if not system_id:
                    return JsonResponse({'success': False, 'message': _('System ID is required')}, status=400)
                status_data = {
                    'system_id': system_id,
                    'environment': environment,
                    'name': (request.POST.get('name') or request.POST.get('accessstatus_name_ua', '')).strip(),
                    'description': request.POST.get('description', '') or request.POST.get('description_ua', ''),
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
        'name': status.name or '',
        'description': status.description or '',
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
                'name': status.name or '',
                'description': status.description or '',
                'color': status.color
            }
            return JsonResponse(data)

        elif request.method == 'POST':
            with transaction.atomic():
                status.name = (request.POST.get('name') or request.POST.get('accessstatus_name_ua', '')).strip()
                status.description = request.POST.get('description', '') or request.POST.get('description_ua', '')
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
        functions = AccessFunctionIS.objects.filter(is_active=True,
            asset_id=asset_id
        ).order_by('right', 'order').values(
            'id', 'name', 'description', 'color', 'parent_id', 'order', 'right'
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
            'accesfunct_name_ua': function.get_name('ua') or function.name or '',
            'accesfunct_name_ru': function.get_name('ru') or '',
            'accesfunct_name_en': function.get_name('en') or function.name or '',
            'description_ua': function.get_description('ua') or '',
            'description_ru': function.get_description('ru') or '',
            'description_en': function.get_description('en') or '',
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
                name=request.POST.get('accesfunct_name_en') or request.POST.get('accesfunct_name_ua') or '',
                description=request.POST.get('description_en') or request.POST.get('description_ua') or '',
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

            function.name = request.POST.get('accesfunct_name_en') or request.POST.get('accesfunct_name_ua', function.name)
            function.description = request.POST.get('description_en') or request.POST.get('description_ua', function.description)
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

            logger.info(f"Querying function with id {function_id}")
            function = AccessFunctionIS.objects.select_related(
                'parent', 'asset'
            ).prefetch_related('translations__country').get(id=function_id)

            logger.info(f"Found function: {function}")
            from .manage_is_objects_view import _build_function_names_descriptions
            from django.conf import settings as _django_settings
            _form_langs = list(getattr(_django_settings, 'LANGUAGES', [('en', 'English')])) or [('en', 'English')]
            _func_names, _func_descs = _build_function_names_descriptions(function, _form_langs)

            try:
                data = {
                    'id': function.id,
                    'name': function.get_name() or getattr(function, 'name', ''),
                    'description': function.get_description() or getattr(function, 'description', ''),
                    'function_names': _func_names,
                    'function_descriptions': _func_descs,
                    'color': function.color,
                    'parent_id': function.parent_id,
                    'asset_id': function.asset_id,
                    'order': getattr(function, 'order', 0)
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
            system_id=system_id, is_active=True
        ).prefetch_related(
            'functions',
            'functions__children'
        ).order_by('order', 'name', 'code')
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
                'name': func.get_name(lang_suffix) or func.get_name('en') or func.name or '',
                'color': func.color,
                'description': func.get_description(lang_suffix) or func.get_description('en') or func.description or '',
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
                    'name': role.get_name(lang_suffix) or role.name or '',
                    'color': role.color,
                    'description': role.get_description(lang_suffix) or role.description or ''
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
                functions = AccessFunctionIS.objects.filter(is_active=True, id__in=data['functions'])
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
            'department': _get_department_display(approver.cabinet_user.department),
            'position': _get_position_display(approver.cabinet_user.position),
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
            'department': _get_department_display(ap.cabinet_user.department),
            'position': _get_position_display(ap.cabinet_user.position),
            'order': ap.order,
            'color': ap.cabinet_user.color,
            'avatar': ap.cabinet_user.avatar.url if ap.cabinet_user.avatar else None,
            'department_name': _get_department_display(ap.cabinet_user.department),
            'position_name': _get_position_display(ap.cabinet_user.position)
        } for ap in access.approvers.all()]

        # Object approvers removed - only system approvers are used now
        object_approvers = []

        # Отримуємо системні approvers
        system_approvers = [{
            'id': ap.cabinet_user.id,
            'name': f"{ap.cabinet_user.user.first_name} {ap.cabinet_user.user.last_name}",
            'department': _get_department_display(ap.cabinet_user.department),
            'position': _get_position_display(ap.cabinet_user.position),
            'order': ap.order,
            'color': ap.cabinet_user.color,
            'avatar': ap.cabinet_user.avatar.url if ap.cabinet_user.avatar else None,
            'department_name': _get_department_display(ap.cabinet_user.department),
            'position_name': _get_position_display(ap.cabinet_user.position)
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
            'department': _get_department_display(cu.department),
            'position': _get_position_display(cu.position),
            'color': cu.color,
            'avatar': cu.avatar.url if cu.avatar else None,
            'department_name': _get_department_display(cu.department),
            'position_name': _get_position_display(cu.position)
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
            'department': _get_department_display(approver.cabinet_user.department),
            'position': _get_position_display(approver.cabinet_user.position),
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
def _role_form_languages():
    """Return list of (code, label) for role form languages (same as object form)."""
    from django.conf import settings as django_settings
    return list(getattr(django_settings, 'LANGUAGES', [('en', 'English')])) or [('en', 'English')]


@login_required
@require_http_methods(['GET'])
def get_system_roles(request):
    """Get roles for a specific system and environment (single name/description)."""
    try:
        system_id = request.GET.get('system_id')
        environment = request.GET.get('environment', 'test')
        if not system_id:
            return JsonResponse({'error': _('System ID is required')}, status=400)

        roles = AccessRoles.objects.filter(
            system_id=system_id,
            environment=environment,
            is_object_specific=False,
            is_active=True
        ).order_by('order', 'name', 'code')

        formatted_roles = [{
            'id': role.id,
            'name': role.get_name() or '',
            'description': role.get_description() or '',
            'color': role.color,
            'order': getattr(role, 'order', 0)
        } for role in roles]
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
    """Get specific role details (single name/description)."""
    try:
        role_id = request.GET.get('role_id')
        if not role_id:
            return JsonResponse({'error': _('Role ID is required')}, status=400)
        role = get_object_or_404(AccessRoles, id=role_id)
        return JsonResponse({
            'success': True,
            'role': {
                'id': role.id,
                'name': role.get_name() or '',
                'description': role.get_description() or '',
                'color': role.color
            }
        })
    except Exception as e:
        logger.error(f"Error getting role details: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def _normalize_lang_to_legacy(lang_code):
    """Map form lang code to legacy attr (ua, ru, en)."""
    lc = (lang_code or '')[:2].lower()
    if lc in ('uk', 'ua'):
        return 'ua'
    if lc == 'ru':
        return 'ru'
    if lc == 'en':
        return 'en'
    return None


@login_required
@require_POST
@ensure_csrf_cookie
def save_role(request):
    """Save or update a role. Single name/description (multilingual removed)."""
    try:
        is_json = (request.content_type or '').strip().lower().startswith('application/json')
        if is_json:
            try:
                data = json.loads(request.body)
            except (json.JSONDecodeError, TypeError, ValueError):
                data = None
        else:
            data = None

        def _get(key, default=''):
            if data is not None:
                return (str(data.get(key, default)).strip() if data.get(key) is not None else default) if default != '' else (data.get(key) or '')
            return (str(request.POST.get(key, default)).strip() if request.POST.get(key) is not None else default) if default != '' else (request.POST.get(key) or '')

        role_id = _get('role_id') or None
        asset_id = _get('asset_id')
        object_id = _get('object_id') or None
        environment = _get('environment', 'test')
        name = (_get('name') or _get('role_name_en') or _get('accessrole_name_en') or '').strip()
        description = (_get('description') or _get('role_description_en') or _get('description_en') or '').strip()

        if not asset_id:
            return JsonResponse({'error': _('System ID is required')}, status=400)

        def _str(val, default=''):
            if val is None:
                return default
            return (str(val).strip() if isinstance(val, str) else str(val)) or default

        role_data = {
            'name': name,
            'description': _str(description),
            'color': _str(_get('color'), '#6c757d'),
            'system_id': asset_id,
            'environment': _str(environment, 'test')
        }

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

        with transaction.atomic():
            if role_id:
                role = get_object_or_404(AccessRoles, id=role_id)
                if role.is_object_specific:
                    return JsonResponse({
                        'success': False,
                        'message': _('Cannot edit object-specific roles through system interface')
                    }, status=403)
                role.name = role_data['name']
                role.description = role_data['description']
                role.color = role_data['color']
                role.save()
                message = _('Role updated successfully')
            else:
                role = AccessRoles.objects.create(**role_data)
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
        import traceback
        logger.error(f"Error saving role: {str(e)}\n{traceback.format_exc()}")
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
            environment=environment,
            is_active=True
        ).prefetch_related(
            'functions',
            'functions__children'
        ).order_by('order', 'name', 'code')
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
                'name': func.get_name(lang_suffix) or func.get_name('en') or func.name or '',
                'color': func.color,
                'description': func.get_description(lang_suffix) or func.get_description('en') or func.description or '',
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
                    'name': role.get_name(lang_suffix) or role.name or '',
                    'color': role.color,
                    'description': role.get_description(lang_suffix) or role.description or ''
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

        rights = AccessRight.objects.filter(
            system_id=system_id,
            environment=environment,
            is_object_specific=False
        ).order_by('order')

        formatted_rights = [{
            'id': right.id,
            'name': right.get_name() or '',
            'description': right.get_description() or '',
            'color': right.color,
            'order': getattr(right, 'order', 0)
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
                'name': right.get_name() or '',
                'description': right.get_description() or '',
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
        name = (request.POST.get('name') or request.POST.get('accessright_name_en') or request.POST.get('accessright_name_ua') or '').strip()
        description = (request.POST.get('description') or request.POST.get('description_en') or request.POST.get('description_ua') or '').strip()

        if right_id:
            right = get_object_or_404(AccessRight, id=right_id)
            if right.is_object_specific:
                return JsonResponse({
                    'success': False,
                    'message': _('Cannot edit object-specific access rights through system interface')
                }, status=403)
            right.name = name
            right.description = description
            right.color = request.POST.get('color', right.color)
            right.system_id = system_id
            right.environment = environment or right.environment
            right.save()
            message = _('Access right updated successfully')
        else:
            right = AccessRight.objects.create(
                name=name,
                description=description,
                color=request.POST.get('color', '#000000'),
                system_id=system_id,
                environment=environment
            )
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
            'name': status.name or '',
            'description': status.description or '',
            'color': status.color,
            'order': status.order
        } for status in statuses]

        return JsonResponse({
            'status': 'success',
            'statuses': statuses_data
        })

    except Exception as e:
        import traceback
        logger.error(f"Error getting system statuses: {str(e)}\n{traceback.format_exc()}")
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
                'name': status.name or '',
                'description': status.description or '',
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
        name = (request.POST.get('name') or request.POST.get('accessstatus_name_ua', '')).strip()
        description = request.POST.get('description', '') or request.POST.get('description_ua', '')
        status_data = {
            'name': name,
            'description': description,
            'color': request.POST.get('color'),
            'system_id': system_id,
            'environment': environment
        }

        with transaction.atomic():
            if status_id:
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

        functions = AccessFunctionIS.objects.filter(
            is_active=True,
            asset_id=system_id,
            environment=environment,
            parent_id=None,
            is_object_specific=False
        ).order_by('order')

        def get_children(parent):
            children = AccessFunctionIS.objects.filter(
                parent_id=parent.id,
                asset_id=system_id,
                environment=environment,
                is_object_specific=False
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

        functions_data = [{
            'id': func.id,
            'name': func.get_name() or '',
            'description': func.get_description() or '',
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
    """Save or update function. Single name/description (multilingual removed)."""
    try:
        is_json = (request.content_type or '').strip().lower().startswith('application/json')
        if is_json:
            try:
                _post = json.loads(request.body)
            except (json.JSONDecodeError, TypeError, ValueError):
                _post = None
        else:
            _post = None

        def _get(key, default=''):
            if _post is not None:
                return (_post.get(key) or default) if default != '' else (_post.get(key) or '')
            return (request.POST.get(key) or default) if default != '' else (request.POST.get(key) or '')

        function_id = _get('function_id') or None
        system_id = _get('system_id')
        parent_id = _get('parent_id') or None
        if not system_id:
            return JsonResponse({'error': _('System ID is required')}, status=400)

        environment = _get('environment', 'test')
        name = (_get('name') or _get('function_name_en') or _get('accesfunct_name_en') or '').strip()
        description = (_get('description') or _get('function_description_en') or _get('description_en') or '').strip()
        color = _get('color', '#6c757d')

        order_val = _get('order')
        try:
            order_int = int(order_val) if order_val not in (None, '') else 0
        except (TypeError, ValueError):
            order_int = 0

        function_data = {
            'name': name,
            'description': description,
            'color': color or '#6c757d',
            'asset_id': system_id,
            'environment': environment or 'test',
            'order': order_int
        }

        with transaction.atomic():
            name_exists_query = AccessFunctionIS.objects.filter(
                asset_id=system_id,
                environment=environment,
                name=function_data['name']
            )
            if function_id:
                name_exists_query = name_exists_query.exclude(id=function_id)
            if name_exists_query.exists():
                return JsonResponse({
                    'success': False,
                    'message': _('Function with this name already exists in this system')
                }, status=400)

            if function_id:
                function = get_object_or_404(AccessFunctionIS, id=function_id)
                if parent_id and int(parent_id) != function.parent_id:
                    new_parent = get_object_or_404(AccessFunctionIS, id=parent_id)
                    function.move_to(new_parent)
                elif not parent_id and function.parent_id:
                    function.move_to(None)
                function.name = function_data['name']
                function.description = function_data['description']
                function.color = function_data['color']
                function.order = function_data['order']
                function.save()
                message = _('Function updated successfully')
            else:
                if parent_id:
                    parent = get_object_or_404(AccessFunctionIS, id=parent_id)
                    function = AccessFunctionIS.objects.create(parent=parent, **function_data)
                else:
                    function = AccessFunctionIS.objects.create(**function_data)
                message = _('Function created successfully')

            return JsonResponse({
                'success': True,
                'message': message,
                'function': {
                    'id': function.id,
                    'name': function.get_name() or '',
                    'description': function.get_description() or '',
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
        orders = data.get('orders', data.get('function_orders', []))
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
    """Get cabinet users for a specific company. Language from URL prefix so Select User respects site language."""
    try:
        # Activate language from request path (e.g. /de/app_access/...) so _() and get_name(lang) use it
        path_parts = (request.path or '').strip('/').split('/')
        if path_parts and len(path_parts[0]) == 2:
            try:
                activate(path_parts[0].lower())
            except Exception:
                pass
        now = timezone.now()
        active_employee_q = (
            (Q(start_date__isnull=True) | Q(start_date__lte=now))
            & (Q(end_date__isnull=True) | Q(end_date__gt=now))
        )
        users = CabinetUser.objects.filter(
            company_id=company_id,
            user__is_active=True,
        ).filter(active_employee_q).select_related(
            'user',
            'department',
            'position'
        ).order_by(
            'user__last_name',
            'user__first_name'
        )

        users_data = [{
            'id': user.id,
            'name': user.user.get_full_name(),
            'department': _get_department_display(user.department) or _('No Department'),
            'position': _get_position_display(user.position) or _('No Position'),
            'color': user.color,
            'avatar': user.avatar.url if user.avatar else None
        } for user in users]

        return JsonResponse({
            'status': 'success',
            'users': users_data
        })

    except Exception as e:
        logger.error(f"Error getting cabinet users: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

