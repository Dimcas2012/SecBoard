#  SecBoard\SecBoard\app_cabinet\views.py


import traceback
import uuid
import hashlib
import base64
from datetime import datetime, timedelta
from functools import wraps
import requests
import json
import secrets
import pyotp
from urllib.parse import quote
import smtplib
import ssl
from email.mime.text import MIMEText

from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseBadRequest, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, get_object_or_404
from django.conf import settings
import logging

from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Q

from .forms import UpdateProfileForm, LoginForm, CabinetUserEditForm, PasswordResetRequestForm, SetPasswordForm
from django.core.mail import EmailMessage, send_mail
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext as _
from app_conf.models import Email, MailAccount, MailServer
from django.shortcuts import render
from app_asset.models import AccessAssets, InformationAsset, AssetOwner, SoftwareRegister, ExternalMediaRegister
# AccessISAM import removed - now using functions from matrix_view.py
from app_std.models import AccessPCIDSS, AccessISO27002
from app_incident.models import AccessIncidents
from app_keycert.models import AccessKeyCert, KeyCertificates, KeycertOwner
from app_access.models import AccessRequest
from app_doc.models import RegisterDocs
from app_compliance.models import Control, LocalComplianceControl, InternalComplianceControl
from app_doc.models import AccessDocs, RegisterDocs, RelatedDocs, AccessLegislativeDoc, DocumentFamiliarization
from app_study.models import QuizAttempt, Quiz, AccessQuiz
from django.contrib.auth import logout as auth_logout
from app_study.models import Page
from app_conf.models import Company
from django.db.models import Count, Sum, Case, When, Value, IntegerField, Max, Prefetch, Exists, OuterRef
from app_compliance.models import MandatoryProcess

# Lazy import for Risk Treatment tasks (app_risk) to avoid circular imports
def _get_risk_treatment_tasks(cabinet_user):
    """Return risk treatments where user is Responsible (or Monitoring Responsible) and status is not Completed."""
    try:
        from app_risk.models import RiskTreatment
        from app_risk.risk_assessment_utils import get_user_risk_assessment_permissions
    except ImportError:
        return []
    user = cabinet_user.user
    perms = get_user_risk_assessment_permissions(user)
    companies = list(perms.get('companies', []))
    if not companies:
        return []
    user_full_name = (f"{user.first_name} {user.last_name}".strip() or user.username or '').strip()
    responsible_match = Q(monitoring_responsible=user)
    if user_full_name:
        responsible_match = responsible_match | Q(responsible__icontains=user_full_name)
    if user.username and user.username != user_full_name:
        responsible_match = responsible_match | Q(responsible__icontains=user.username)
    return list(
        RiskTreatment.objects.filter(asset__company__in=companies)
        .exclude(status__code='Completed')
        .filter(responsible_match)
        .distinct()
        .select_related('asset', 'asset__company', 'vulnerability', 'status')
        .order_by('deadline', 'asset__name')[:50]
    )


def _get_risk_monitoring_review_tasks(cabinet_user):
    """Return risk treatments where user is Monitoring Responsible, next_review_date is set, and review is overdue or due within 30 days."""
    try:
        from app_risk.models import RiskTreatment
        from app_risk.risk_assessment_utils import get_user_risk_assessment_permissions
        from django.utils import timezone
    except ImportError:
        return {'overdue': [], 'due_7d': [], 'due_30d': []}
    user = cabinet_user.user
    perms = get_user_risk_assessment_permissions(user)
    companies = list(perms.get('companies', []))
    if not companies:
        return {'overdue': [], 'due_7d': [], 'due_30d': []}
    today = timezone.now().date()
    end_7d = today + timedelta(days=7)
    end_30d = today + timedelta(days=30)
    base = (
        RiskTreatment.objects.filter(asset__company__in=companies)
        .filter(monitoring_responsible=user, next_review_date__isnull=False)
        .exclude(status__code='Completed')
        .distinct()
        .select_related('asset', 'asset__company', 'vulnerability', 'status')
    )
    overdue = list(base.filter(next_review_date__lt=today).order_by('next_review_date', 'asset__name')[:30])
    due_7d = list(base.filter(next_review_date__gte=today, next_review_date__lte=end_7d).order_by('next_review_date', 'asset__name')[:30])
    due_30d = list(base.filter(next_review_date__gt=end_7d, next_review_date__lte=end_30d).order_by('next_review_date', 'asset__name')[:30])
    return {'overdue': overdue, 'due_7d': due_7d, 'due_30d': due_30d}


def verify_recaptcha(captcha_response, expected_action='login'):
    """
    Verify Google reCAPTCHA v3 response
    """
    if not captcha_response:
        return False
    
    recaptcha_secret = getattr(settings, 'RECAPTCHA_PRIVATE_KEY', '')
    if not recaptcha_secret:
        # If no reCAPTCHA is configured, skip verification
        logger.warning("reCAPTCHA verification requested but no secret key configured")
        return True
    
    data = {
        'secret': recaptcha_secret,
        'response': captcha_response
    }
    
    try:
        response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data, timeout=10)
        result = response.json()
        
        # Check if the verification was successful
        if not result.get('success', False):
            logger.warning(f"reCAPTCHA verification failed: {result.get('error-codes', [])}")
            return False
        
        # For reCAPTCHA v3, check the score and action
        score = result.get('score', 0.0)
        action = result.get('action', '')
        
        # Get the required score from settings
        required_score = getattr(settings, 'RECAPTCHA_REQUIRED_SCORE', 0.5)
        
        # Verify the action matches what we expected
        if action != expected_action:
            logger.warning(f"reCAPTCHA action mismatch. Expected: {expected_action}, Got: {action}")
            return False
        
        # Check if the score meets our threshold
        if score < required_score:
            logger.warning(f"reCAPTCHA score too low: {score} (required: {required_score})")
            return False
        
        logger.info(f"reCAPTCHA verification successful. Score: {score}, Action: {action}")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying reCAPTCHA: {e}")
        return False
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Case, When, Value, CharField
from django.db.models.functions import Concat
from .models import CabinetSettings, CabinetPasswordCompanyLink, UserActivity, UserSession, CabinetUser, CabinetGroup, PlatformRole, PlatformRoleDashboardConfig
from .dashboard_config import EXECUTIVE_SECTIONS, get_default_config, normalize_config, get_section_by_id
from .executive_metrics import get_executive_metrics
from  app_study.models import AccessQuiz
from .middleware import track_user_logout
from .options_view import *
from .permissions import require_permission, has_permission
from  app_risk.models import AccessRisk
from django.contrib.sites.shortcuts import get_current_site

logger = logging.getLogger(__name__)

logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")


TWO_FACTOR_TEMP_VALIDITY = timedelta(minutes=10)
BACKUP_CODE_COUNT = 8
FORCED_2FA_SESSION_KEYS = [
    'pending_force_2fa_user_id',
    'pending_force_2fa_ip',
    'pending_force_2fa_created',
    'pending_force_2fa_next'
]


def hash_backup_code(code: str) -> str:
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def generate_backup_codes(count: int = BACKUP_CODE_COUNT):
    plain_codes = []
    hashed_codes = []
    for _ in range(count):
        code = f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper()
        plain_codes.append(code)
        hashed_codes.append({
            'hash': hash_backup_code(code),
            'used': False
        })
    return plain_codes, hashed_codes


def verify_two_factor_code(cabinet_user, code, *, secret=None, allow_backup=False, mark_backup_used=False):
    """
    Returns tuple (is_valid, used_backup_code)
    """
    if not code:
        return False, False

    raw_code = code.strip()
    numeric_code = ''.join(ch for ch in raw_code if ch.isdigit())
    active_secret = secret or cabinet_user.two_factor_secret

    if active_secret and numeric_code:
        totp = pyotp.TOTP(active_secret)
        if totp.verify(numeric_code, valid_window=1):
            return True, False

    if allow_backup:
        normalized = raw_code.upper()
        candidate_hash = hash_backup_code(normalized)
        backup_codes = cabinet_user.two_factor_backup_codes or []
        for entry in backup_codes:
            if entry.get('hash') == candidate_hash and not entry.get('used'):
                if mark_backup_used:
                    entry['used'] = True
                    cabinet_user.two_factor_backup_codes = backup_codes
                    cabinet_user.save(update_fields=['two_factor_backup_codes'])
                return True, True

    return False, False


def clear_pending_two_factor_session(request):
    for key in [
        'pending_2fa_user_id',
        'pending_2fa_ip',
        'pending_2fa_user_agent',
        'pending_2fa_created',
        'pending_2fa_next'
    ]:
        if key in request.session:
            del request.session[key]


def clear_pending_force_two_factor_session(request):
    for key in FORCED_2FA_SESSION_KEYS:
        if key in request.session:
            del request.session[key]


def get_request_data(request):
    content_type = request.META.get('CONTENT_TYPE', '')
    if 'application/json' in content_type.lower():
        try:
            body = request.body.decode() if request.body else '{}'
            return json.loads(body or '{}')
        except (ValueError, TypeError):
            return {}
    return request.POST


def finalize_login(request, user, ip_address, *, next_url=None, two_factor_method=None):
    """
    Performs the shared steps required after successful credential + optional 2FA verification.
    Returns an HttpResponse redirect.
    """
    if getattr(settings, 'SESSION_REGENERATE_ON_LOGIN', True):
        old_session_key = request.session.session_key
        request.session.cycle_key()
        logger.info(f"Session regenerated for user {user.username}: {old_session_key} -> {request.session.session_key}")

    login(request, user)
    request._login_success = True

    request.session['session_ip'] = ip_address
    request.session['login_time'] = timezone.now().isoformat()
    request.session['last_activity'] = timezone.now().isoformat()
    request.session['user_agent_hash'] = hashlib.md5(
        request.META.get('HTTP_USER_AGENT', '').encode()
    ).hexdigest()

    session = UserSession.objects.create(
        user=user,
        session_key=request.session.session_key or request.session.create(),
        ip_address=ip_address,
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

    details = {
        'login_method': 'form',
        'browser': request.META.get('HTTP_USER_AGENT', ''),
        'ip_address': ip_address,
        'timestamp': timezone.now().isoformat()
    }

    if two_factor_method:
        details['two_factor_method'] = two_factor_method

    UserActivity.objects.create(
        user=user,
        session=session,
        action='login',
        url=request.path,
        details=details
    )

    force_change_records = UserActivity.objects.filter(
        user=user,
        action='password_reset',
        details__force_change=True,
        details__processed__isnull=True
    ).order_by('-timestamp')

    if force_change_records.exists():
        messages.warning(request, _("You need to change your password before continuing."))
        return redirect('password_change')

    from app_integration.telegram_link import complete_pending_telegram_link
    complete_pending_telegram_link(request, user)

    messages.success(request, _("You have been successfully logged in."))
    if next_url:
        return redirect(next_url)
    return redirect(reverse('personal_cabinet') + '#tasks')




from .permissions import require_permission

@require_permission('site_statistics', 'view')
def site_statistics(request):
    try:
        # Base querysets with error handling for missing GeoIP
        sessions = UserSession.objects.all().select_related('user')
        activities = UserActivity.objects.all().select_related('user', 'session')

        # Filter and annotate sessions with location info
        sessions = sessions.annotate(
            display_location=Case(
                When(ip_address__in=['127.0.0.1', 'localhost', '::1'],
                     then=Value('Local Development')),
                When(city='', then=Value('Unknown')),
                default=Concat('city', Value(', '), 'country'),
                output_field=CharField(),
            )
        )

        # Get general filter parameters (for charts and statistics)
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        user_filter = request.GET.get('user')
        action_filter = request.GET.get('action')
        country_filter = request.GET.get('country')

        # Apply general filters
        sessions_stats = sessions
        activities_stats = activities

        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                sessions_stats = sessions_stats.filter(login_time__gte=date_from_obj)
                activities_stats = activities_stats.filter(timestamp__gte=date_from_obj)
            except ValueError:
                messages.error(request, _('Invalid date format'))

        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                sessions_stats = sessions_stats.filter(login_time__lte=date_to_obj)
                activities_stats = activities_stats.filter(timestamp__lte=date_to_obj)
            except ValueError:
                messages.error(request, _('Invalid date format'))

        if user_filter:
            sessions_stats = sessions_stats.filter(
                Q(user__username__icontains=user_filter) |
                Q(user__first_name__icontains=user_filter) |
                Q(user__last_name__icontains=user_filter) |
                Q(user__email__icontains=user_filter)
            )
            activities_stats = activities_stats.filter(
                Q(user__username__icontains=user_filter) |
                Q(user__first_name__icontains=user_filter) |
                Q(user__last_name__icontains=user_filter) |
                Q(user__email__icontains=user_filter)
            )

        if action_filter:
            activities_stats = activities_stats.filter(action=action_filter)

        if country_filter:
            sessions_stats = sessions_stats.filter(
                Q(country__icontains=country_filter) |
                Q(city__icontains=country_filter)
            )

        # Get specific filters for Sessions table
        session_user = request.GET.get('session_user')
        session_date_from = request.GET.get('session_date_from')
        session_date_to = request.GET.get('session_date_to')
        session_ip = request.GET.get('session_ip')
        session_status = request.GET.get('session_status')

        # Apply session-specific filters
        sessions_table = sessions
        if session_user:
            sessions_table = sessions_table.filter(
                Q(user__username__icontains=session_user) |
                Q(user__first_name__icontains=session_user) |
                Q(user__last_name__icontains=session_user) |
                Q(user__email__icontains=session_user)
            )
        
        if session_date_from:
            try:
                session_date_from_obj = datetime.strptime(session_date_from, '%Y-%m-%d')
                sessions_table = sessions_table.filter(login_time__gte=session_date_from_obj)
            except ValueError:
                pass
        
        if session_date_to:
            try:
                session_date_to_obj = datetime.strptime(session_date_to, '%Y-%m-%d')
                sessions_table = sessions_table.filter(login_time__lte=session_date_to_obj)
            except ValueError:
                pass
        
        if session_ip:
            sessions_table = sessions_table.filter(ip_address__icontains=session_ip)
        
        if session_status:
            if session_status == 'active':
                sessions_table = sessions_table.filter(logout_time__isnull=True)
            elif session_status == 'ended':
                sessions_table = sessions_table.filter(logout_time__isnull=False)

        # Get specific filters for Activities table
        activity_user = request.GET.get('activity_user')
        activity_action = request.GET.get('activity_action')
        activity_date_from = request.GET.get('activity_date_from')
        activity_date_to = request.GET.get('activity_date_to')
        activity_ip = request.GET.get('activity_ip')

        # Apply activity-specific filters
        activities_table = activities
        if activity_user:
            activities_table = activities_table.filter(
                Q(user__username__icontains=activity_user) |
                Q(user__first_name__icontains=activity_user) |
                Q(user__last_name__icontains=activity_user) |
                Q(user__email__icontains=activity_user)
            )
        
        if activity_action:
            activities_table = activities_table.filter(action=activity_action)
        
        if activity_date_from:
            try:
                activity_date_from_obj = datetime.strptime(activity_date_from, '%Y-%m-%d')
                activities_table = activities_table.filter(timestamp__gte=activity_date_from_obj)
            except ValueError:
                pass
        
        if activity_date_to:
            try:
                activity_date_to_obj = datetime.strptime(activity_date_to, '%Y-%m-%d')
                activities_table = activities_table.filter(timestamp__lte=activity_date_to_obj)
            except ValueError:
                pass
        
        if activity_ip:
            activities_table = activities_table.filter(session__ip_address__icontains=activity_ip)

        # Paginate sessions (using table-specific filters)
        session_page = request.GET.get('page', 1)
        session_paginator = Paginator(sessions_table.order_by('-login_time'), 20)
        try:
            sessions_page = session_paginator.page(session_page)
        except (PageNotAnInteger, EmptyPage):
            sessions_page = session_paginator.page(1)

        # Paginate activities (using table-specific filters)
        activity_page = request.GET.get('activity_page', 1)
        activity_paginator = Paginator(activities_table.order_by('-timestamp'), 50)
        try:
            activities_page = activity_paginator.page(activity_page)
        except (PageNotAnInteger, EmptyPage):
            activities_page = activity_paginator.page(1)

        # Statistics calculations (using general filters for stats)
        total_users = User.objects.count()
        active_users_today = sessions_stats.filter(
            login_time__date=timezone.now().date()
        ).values('user').distinct().count()

        # Average session duration
        active_sessions = sessions_stats.exclude(logout_time=None)
        if active_sessions.exists():
            total_duration = sum(
                (session.logout_time - session.login_time).total_seconds()
                for session in active_sessions
            )
            avg_duration = total_duration / (active_sessions.count() * 60)  # Convert to minutes
        else:
            avg_duration = 0

        # Action statistics (using general filters)
        action_stats = activities_stats.values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:5]

        # Geographical statistics with local development handling (using general filters)
        country_stats = sessions_stats.exclude(
            ip_address__in=['127.0.0.1', 'localhost', '::1']
        ).exclude(
            country=''
        ).values('country').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        context = {
            'sessions': sessions_page,
            'activities': activities_page,
            'total_users': total_users,
            'active_users_today': active_users_today,
            'avg_duration': avg_duration,
            'action_stats': action_stats,
            'country_stats': country_stats,
            'action_choices': UserActivity.ACTION_CHOICES,
            'now': timezone.now(),
        }

        return render(request, 'app_conf/site_statistics.html', context)

    except Exception as e:
        logger.error(f"Error in site_statistics view: {str(e)}", exc_info=True)
        messages.error(request, _("An error occurred while loading statistics"))
        return redirect('index')


@require_permission('site_statistics', 'view')
def get_site_statistics(request):
    """API endpoint for real-time statistics updates"""
    try:
        from django.http import JsonResponse
        from django.utils import timezone
        
        # Get active users today
        sessions = UserSession.objects.filter(
            login_time__date=timezone.now().date()
        )
        active_users_today = sessions.values('user').distinct().count()
        
        # Get last update time
        last_activity = UserActivity.objects.order_by('-timestamp').first()
        last_update = last_activity.timestamp if last_activity else timezone.now()
        
        return JsonResponse({
            'active_users': active_users_today,
            'last_update': last_update.isoformat(),
        })
    except Exception as e:
        logger.error(f"Error in get_site_statistics: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Failed to fetch statistics'}, status=500)


@require_permission('site_statistics', 'view')
def export_statistics(request):
    """Export statistics data in various formats"""
    try:
        import json
        from django.http import HttpResponse
        from django.utils import timezone
        import csv
        import io
        
        if request.method != 'POST':
            return HttpResponse('Method not allowed', status=405)
        
        # Parse request data
        data = json.loads(request.body)
        export_format = data.get('format', 'json')
        data_type = data.get('data_type', 'both')
        date_from = data.get('export_date_from')
        date_to = data.get('export_date_to')
        
        # Prepare data
        sessions = UserSession.objects.all().select_related('user')
        activities = UserActivity.objects.all().select_related('user', 'session')
        
        # Apply date filters
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d')
                sessions = sessions.filter(login_time__gte=date_from)
                activities = activities.filter(timestamp__gte=date_from)
            except ValueError:
                pass
                
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d')
                sessions = sessions.filter(login_time__lte=date_to)
                activities = activities.filter(timestamp__lte=date_to)
            except ValueError:
                pass
        
        # Export data based on format
        if export_format == 'json':
            export_data = {}
            
            if data_type in ['sessions', 'both']:
                export_data['sessions'] = []
                for session in sessions:
                    export_data['sessions'].append({
                        'user': session.user.username,
                        'login_time': session.login_time.isoformat(),
                        'logout_time': session.logout_time.isoformat() if session.logout_time else None,
                        'ip_address': session.ip_address,
                        'user_agent': session.user_agent,
                        'city': session.city,
                        'country': session.country,
                    })
            
            if data_type in ['activities', 'both']:
                export_data['activities'] = []
                for activity in activities:
                    export_data['activities'].append({
                        'user': activity.user.username,
                        'timestamp': activity.timestamp.isoformat(),
                        'action': activity.action,
                        'object_type': activity.object_type,
                        'object_id': activity.object_id,
                        'ip_address': activity.ip_address,
                    })
            
            response = HttpResponse(
                json.dumps(export_data, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="statistics_{timezone.now().strftime("%Y%m%d")}.json"'
            return response
            
        elif export_format == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            
            if data_type in ['sessions', 'both']:
                writer.writerow(['Type', 'User', 'Login Time', 'Logout Time', 'IP Address', 'City', 'Country'])
                for session in sessions:
                    writer.writerow([
                        'Session',
                        session.user.username,
                        session.login_time.strftime('%Y-%m-%d %H:%M:%S'),
                        session.logout_time.strftime('%Y-%m-%d %H:%M:%S') if session.logout_time else '',
                        session.ip_address,
                        session.city,
                        session.country,
                    ])
            
            if data_type in ['activities', 'both']:
                if data_type == 'both':
                    writer.writerow([])  # Empty row separator
                writer.writerow(['Type', 'User', 'Timestamp', 'Action', 'Object Type', 'Object ID', 'IP Address'])
                for activity in activities:
                    writer.writerow([
                        'Activity',
                        activity.user.username,
                        activity.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        activity.action,
                        activity.object_type,
                        activity.object_id,
                        activity.ip_address,
                    ])
            
            response = HttpResponse(output.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="statistics_{timezone.now().strftime("%Y%m%d")}.csv"'
            return response
        
        else:
            return HttpResponse('Unsupported format', status=400)
            
    except Exception as e:
        logger.error(f"Error in export_statistics: {str(e)}", exc_info=True)
        return HttpResponse('Export failed', status=500)


def _executive_view_companies(request, role):
    """Companies available for Executive View: user-accessible intersected with role's companies (if any)."""
    from .options_view import get_user_companies
    accessible = get_user_companies(request.user)
    role_company_ids = set(role.companies.values_list('id', flat=True))
    if role_company_ids:
        companies = accessible.filter(id__in=role_company_ids).order_by('name')
    else:
        companies = accessible.order_by('name')
    return companies


def _get_executive_view_context(request, cabinet_user):
    """
    Build context for Executive View (sections, companies, widgets).
    Returns a dict to merge into template context, or None if user has no platform role.
    """
    role = cabinet_user.roles.filter(is_active=True).prefetch_related('companies').first() if cabinet_user else None
    if not role:
        return None
    companies = _executive_view_companies(request, role)
    available_ids = set(companies.values_list('id', flat=True))
    selected_company_ids = []
    company_id = request.GET.get('company_id')
    company_ids = request.GET.get('company_ids', '')
    if company_id and company_id.isdigit() and int(company_id) in available_ids:
        selected_company_ids = [int(company_id)]
    elif company_ids:
        for cid in company_ids.split(','):
            cid = cid.strip()
            if cid.isdigit() and int(cid) in available_ids:
                selected_company_ids.append(int(cid))
    try:
        config_obj = role.dashboard_config
        config = normalize_config(config_obj.config)
    except PlatformRoleDashboardConfig.DoesNotExist:
        config = get_default_config()
    sections_for_template = []
    all_widget_ids = []
    for sec in config.get('sections', []):
        if not sec.get('enabled', True):
            continue
        section_def = get_section_by_id(sec.get('id'))
        if not section_def:
            continue
        widgets = sec.get('widgets') or []
        widget_list = [w for w in section_def['widgets'] if w['id'] in widgets]
        for w in widget_list:
            all_widget_ids.append(w['id'])
        sections_for_template.append({
            'id': section_def['id'],
            'label': section_def['label'],
            'description': section_def.get('description', ''),
            'widgets': widget_list,
        })
    return {
        'executive_role': role,
        'executive_sections': sections_for_template,
        'executive_companies': companies,
        'executive_selected_company_ids': selected_company_ids,
        'executive_widget_ids_json': json.dumps(all_widget_ids),
    }


@login_required
def executive_view(request):
    """
    Redirect to Personal Cabinet with Executive View tab.
    Executive View is now shown as a tab inside /app_cabinet/personal-cabinet/.
    """
    return redirect(reverse('personal_cabinet') + '#executive-view')


@login_required
def executive_view_metrics_api(request):
    """
    GET: return metrics for requested widgets, filtered by company_id(s).
    Query params: company_id (single) or company_ids (comma), widgets (comma list of widget ids).
    """
    cabinet_user = CabinetUser.objects.filter(user=request.user).prefetch_related('roles').first()
    if not cabinet_user:
        return JsonResponse({'error': 'no_cabinet_profile'}, status=403)
    role = cabinet_user.roles.filter(is_active=True).prefetch_related('companies').first()
    if not role:
        return JsonResponse({'error': 'no_role'}, status=403)
    companies = _executive_view_companies(request, role)
    available_ids = set(companies.values_list('id', flat=True))
    company_ids = []
    company_id = request.GET.get('company_id')
    company_ids_param = request.GET.get('company_ids', '')
    if company_id and company_id.isdigit():
        if int(company_id) in available_ids:
            company_ids = [int(company_id)]
    elif company_ids_param:
        for cid in company_ids_param.split(','):
            cid = cid.strip()
            if cid.isdigit() and int(cid) in available_ids:
                company_ids.append(int(cid))
    widgets_param = request.GET.get('widgets', '')
    widget_ids = [w.strip() for w in widgets_param.split(',') if w.strip()]
    if not widget_ids:
        return JsonResponse({'metrics': {}})
    try:
        config_obj = role.dashboard_config
        config = normalize_config(config_obj.config)
    except PlatformRoleDashboardConfig.DoesNotExist:
        config = get_default_config()
    allowed_widgets = set()
    for sec in config.get('sections', []):
        if sec.get('enabled', True):
            allowed_widgets.update(sec.get('widgets') or [])
    widget_ids = [w for w in widget_ids if w in allowed_widgets]
    metrics = get_executive_metrics(company_ids, widget_ids)
    return JsonResponse({'metrics': metrics})


@require_permission('roles', 'view')
def role_dashboard_config(request, role_id):
    """
    Configure which sections and widgets are shown in Executive View for this platform role.
    POST: save config (requires roles edit permission).
    """
    from .options_view import get_user_companies
    accessible_companies = get_user_companies(request.user)
    ids_global = PlatformRole.objects.annotate(c=Count('companies')).filter(c=0).values_list('id', flat=True)
    ids_scoped = PlatformRole.objects.filter(companies__in=accessible_companies).values_list('id', flat=True).distinct()
    role_ids = set(ids_global) | set(ids_scoped)
    role = get_object_or_404(PlatformRole, pk=role_id)
    if role.id not in role_ids:
        return HttpResponseForbidden(_('You do not have access to this role.'))
    can_edit = has_permission(request.user, 'roles', 'edit')
    if request.method == 'POST' and can_edit:
        import json as json_module
        raw = request.POST.get('config')
        try:
            data = json_module.loads(raw) if raw else {}
        except (ValueError, TypeError):
            data = {}
        config = normalize_config(data)
        config_obj, created = PlatformRoleDashboardConfig.objects.get_or_create(platform_role=role)
        config_obj.config = config
        config_obj.save()
        messages.success(request, _('Dashboard configuration saved.'))
        return redirect('role_dashboard_config', role_id=role_id)
    try:
        config_obj = role.dashboard_config
        config = normalize_config(config_obj.config)
    except PlatformRoleDashboardConfig.DoesNotExist:
        config = get_default_config()
    # Build form structure: for each section, list widgets with checked if in config
    form_sections = []
    for sec_def in EXECUTIVE_SECTIONS:
        sec_config = next((s for s in config.get('sections', []) if isinstance(s, dict) and s.get('id') == sec_def['id']), None)
        enabled = sec_config.get('enabled', True) if sec_config else True
        selected_widget_ids = set(sec_config.get('widgets', [])) if sec_config else {w['id'] for w in sec_def['widgets']}
        form_sections.append({
            'id': sec_def['id'],
            'label': sec_def['label'],
            'description': sec_def.get('description', ''),
            'enabled': enabled,
            'widgets': [{'id': w['id'], 'label': w['label'], 'checked': w['id'] in selected_widget_ids} for w in sec_def['widgets']],
        })
    context = {
        'role': role,
        'form_sections': form_sections,
        'can_edit': can_edit,
        'page_title': _('Dashboard display settings'),
    }
    return render(request, 'app_cabinet/role_dashboard_config.html', context)


def show_assets_link(request):
    """Show Asset Inventory link if user has access to Information Assets (has_access)."""
    if request.user.is_authenticated:
        return AccessAssets.objects.filter(group__in=request.user.groups.all(), has_access=True).exists()
    return False


def show_software_register_link(request):
    """Show Software Register link if user has can_view_software_register in any group."""
    if request.user.is_authenticated:
        return AccessAssets.objects.filter(group__in=request.user.groups.all(), can_view_software_register=True).exists()
    return False


def show_external_media_register_link(request):
    """Show External Media Register link if user has can_view_external_media_register in any group."""
    if request.user.is_authenticated:
        return AccessAssets.objects.filter(group__in=request.user.groups.all(), can_view_external_media_register=True).exists()
    return False


def show_access_matrix_link(request):
    """Check if user should see Access Matrix link on index page"""
    from app_access.matrix_view import has_access_matrix_permission_new
    return has_access_matrix_permission_new(request.user)

def show_access_records_link(request):
    """Check if user should see Access Records link on index page"""
    from app_access.matrix_view import has_access_records_permission
    return has_access_records_permission(request.user)


def show_access_config_is_link(request):
    """Check if user should see Access Config IS link on index page"""
    from app_access.matrix_view import has_access_config_is_permission
    return has_access_config_is_permission(request.user)

def show_manage_ar_link(request):
    """Check if user should see Manage Access Requests link on index page"""
    from app_access.matrix_view import has_access_manage_ar_permission
    return has_access_manage_ar_permission(request.user)

def show_user_access_request_link(request):
    """Check if user should see User Access Request link based on request_users and request_groups"""
    if request.user.is_authenticated:
        from app_access.matrix_view import can_submit_access_requests
        return can_submit_access_requests(request.user)
    return False

def show_notification_settings_link(request):
    """Check if the user should see the notification settings link"""
    from app_access.matrix_view import has_access_notification_settings_permission
    return has_access_notification_settings_permission(request.user)

def show_api_link(request):
    """Check if the user should see the API link"""
    from app_access.matrix_view import has_access_api_permission
    return has_access_api_permission(request.user)

def show_incidents_link(request):
    if request.user.is_authenticated:
        return AccessIncidents.objects.filter(group__in=request.user.groups.all(), show_link=True).exists()
    return False
def show_keys_cert_link(request):
    if request.user.is_authenticated:
        return AccessKeyCert.objects.filter(group__in=request.user.groups.all(), show_link=True).exists()
    return False

def show_fim_dashboard_link(request):
    """Check if user has access to FIM Dashboard"""
    if request.user.is_authenticated:
        from app_soc.models import AccessFIM
        return AccessFIM.objects.filter(group__in=request.user.groups.all(), has_access=True).exists()
    return False

def show_gophish_link(request):
    """Check if user has access to Gophish"""
    if not request.user.is_authenticated:
        return False
    
    # Check AccessGophish model directly for has_access=True
    from app_gophish.models import AccessGophish
    return AccessGophish.objects.filter(
        group__in=request.user.groups.all(),
        has_access=True
    ).exists()

def show_risk_assessment_link(user):
    if user.is_authenticated:
        return AccessRisk.objects.filter(
            group__in=user.groups.all(),
            has_access_assessment=True
        ).exists()
    return False

def show_risk_assessment_config_link(request):
    if request.user.is_authenticated:
        return AccessRisk.objects.filter(
            group__in=request.user.groups.all(),
            has_access_config=True
        ).exists()
    return False

def show_risk_report_link(user):
    if user.is_authenticated:
        return AccessRisk.objects.filter(
            group__in=user.groups.all(),
            has_access_report=True
        ).exists()
    return False

def show_docs_link(request):
    if request.user.is_authenticated:
        return AccessDocs.objects.filter(
            group__in=request.user.groups.all(),
            has_access=True
        ).exists()
    return False

def show_mandatory_processes_link(request):
    """Check if user has access to mandatory processes"""
    if request.user.is_authenticated:
        from app_doc.models import AccessMandatory
        return AccessMandatory.objects.filter(
            group__in=request.user.groups.all(),
            has_access=True
        ).exists()
    return False

def show_pcidss_link(request):
    if request.user.is_authenticated:
        return AccessPCIDSS.objects.filter(group__in=request.user.groups.all(), show_link=True).exists()
    return False

def show_iso27002_link(request):
    if request.user.is_authenticated:
        return AccessISO27002.objects.filter(group__in=request.user.groups.all(), show_link=True).exists()
    return False

def quiz_result_link(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return True
        return AccessQuiz.objects.filter(
            group__in=request.user.groups.all(),
            has_access_to_results=True
        ).exists()
    return False

def show_legdocs_link(request):
    if request.user.is_authenticated:
        return AccessLegislativeDoc.objects.filter(
            group__in=request.user.groups.all(),
            has_access=True
        ).exists()
    return False

def show_quiz_manager_link(request):
    """Check if user should see Quiz Manager link on index page"""
    if request.user.is_authenticated:
        user_groups = request.user.groups.all()
        return AccessQuiz.objects.filter(
            group__in=user_groups, 
            has_access=True
        ).exists()
    return False


def show_page_manager_link(request):
    """Check if user should see Page Manager link on index page"""
    if request.user.is_authenticated:
        user_groups = request.user.groups.all()
        from app_study.models import AccessPage
        return AccessPage.objects.filter(
            group__in=user_groups, 
            has_access=True
        ).exists()
    return False

def show_org_chart_link(request):
    """
    Show organization chart link for users with permission
    """
    from .permissions import has_permission
    return has_permission(request.user, 'org_chart', 'view')

def show_gdpr_compliance_link(request):
    """Check if user has access to GDPR Compliance Dashboard"""
    if request.user.is_authenticated:
        from app_gdpr.models import GDPRAccess
        return GDPRAccess.objects.filter(
            group__in=request.user.groups.all(),
            has_access_compliance_dashboard=True
        ).exists()
    return False

def show_compliance_link(request):
    """Check if user has access to Framework Compliance (app_compliance)"""
    if request.user.is_authenticated:
        # Superusers and staff always have access
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Check AccessCompliance for user's groups
        from app_compliance.models import AccessCompliance
        return AccessCompliance.objects.filter(
            group__in=request.user.groups.all(),
            has_access=True
        ).exists()
    return False


def show_local_compliance_link(request):
    """Check if user has access to Local Compliance (app_compliance)"""
    if request.user.is_authenticated:
        # Superusers and staff always have access
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Check AccessLocalCompliance for user's groups
        from app_compliance.models import AccessLocalCompliance
        return AccessLocalCompliance.objects.filter(
            group__in=request.user.groups.all(),
            has_access=True
        ).exists()
    return False

def show_internal_compliance_link(request):
    """Check if user has access to Internal Compliance (app_compliance)"""
    if request.user.is_authenticated:
        # Superusers and staff always have access
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Check AccessInternalCompliance for user's groups
        from app_compliance.models import AccessInternalCompliance
        return AccessInternalCompliance.objects.filter(
            group__in=request.user.groups.all(),
            has_access=True
        ).exists()
    return False


def show_cif_link(request):
    """Check if user has access to CIF module (app_cif)."""
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return True
        from app_cif.utils import user_has_cif_module_access
        return user_has_cif_module_access(request.user)
    return False


def show_integration_link(request):
    """Check if user has access to Integrations module (app_integration)."""
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return True
        from app_integration.utils import user_has_integration_module_access
        return user_has_integration_module_access(request.user)
    return False


def index(request):
    from app_access.matrix_view import has_any_isam_access
    from app_conf.models import AccessOption

    build_marker = ''
    build_hash = ''
    marker_b64 = getattr(settings, '_SECBOARD_BUILD_MARKER_B64', '')
    if marker_b64:
        try:
            build_marker = base64.b64decode(marker_b64).decode('utf-8')
        except Exception:
            build_marker = ''
    build_hash = getattr(settings, '_SECBOARD_BUILD_HASH', '')
    
    # Check if user has options access through AccessOption model
    is_Options_member = AccessOption.user_has_options_access(request.user) if request.user.is_authenticated else False
    
    # Check if user has any ISAM access through AccessISAM model
    is_ISAM_member = has_any_isam_access(request.user)

    context = {
        'is_ISAM_member': is_ISAM_member,
        'is_Options_member': is_Options_member,
        'quiz_result_link': quiz_result_link(request),
        'show_quiz_manager_link': show_quiz_manager_link(request),
        'show_page_manager_link': show_page_manager_link(request),
        'show_assets_link': show_assets_link(request),
        'show_access_matrix_link': show_access_matrix_link(request),
        'show_access_records_link': show_access_records_link(request),
        'show_access_config_is_link': show_access_config_is_link(request),
        'show_incidents_link': show_incidents_link(request),
        'show_keys_cert_link': show_keys_cert_link(request),
        'show_fim_dashboard_link': show_fim_dashboard_link(request),
        'show_gophish_link': show_gophish_link(request),
        'access_risk_assessment_show_link': show_risk_assessment_link(request.user),
        'show_risk_report_link': show_risk_report_link(request.user),
        'show_docs_link': show_docs_link(request),
        'show_legdocs_link': show_legdocs_link(request),
        'show_mandatory_processes_link': show_mandatory_processes_link(request),
        'show_pcidss_link': show_pcidss_link(request),
        'show_iso27002_link': show_iso27002_link(request),
        'show_risk_assessment_config_link': show_risk_assessment_config_link(request),
        'show_manage_ar_link': show_manage_ar_link(request),
        'show_user_access_request_link': show_user_access_request_link(request),
        'show_notification_settings_link': show_notification_settings_link(request),
        'show_api_link': show_api_link(request),
        'show_org_chart_link': show_org_chart_link(request),
        'show_gdpr_compliance_link': show_gdpr_compliance_link(request),
        'compliance_has_access': show_compliance_link(request),
        'cif_has_access': show_cif_link(request),
        'show_integration_link': show_integration_link(request),
        'build_marker': build_marker,
        'build_hash': build_hash,
    }
    # Tasks for authenticated users with cabinet profile and company (same data as Personal Cabinet Tasks tab)
    if request.user.is_authenticated:
        try:
            from .models import CabinetUser
            cabinet_user, _ = CabinetUser.objects.get_or_create(user=request.user)
            if cabinet_user.company_id:
                tasks_ctx = get_tasks_context_for_cabinet_user(cabinet_user)
                context.update(tasks_ctx)
                context['tasks_total_count'] = get_tasks_count_for_cabinet_user(cabinet_user)
            else:
                empty_tasks = {
                    'mandatory_tasks_overdue': [], 'mandatory_tasks_due_3d': [], 'mandatory_tasks_due_30d': [],
                    'tasks_quizzes_not_passed': [], 'keycert_tasks_expired': [], 'keycert_tasks_expiring_30d': [],
                    'keycert_tasks_actualize': [],
                    'asset_tasks_actualize': [], 'software_tasks_actualize': [], 'external_media_tasks_actualize': [],
                    'vendor_tasks_actualize': [], 'vendor_tasks_contract_end': [],
                    'access_requests_tasks_approve': [], 'document_approve_tasks': [],
                    'familiarization_tasks': [], 'framework_compliance_tasks': [], 'local_compliance_tasks': [],
                    'internal_compliance_tasks': [], 'risk_treatment_tasks': [],
                    'risk_monitoring_review_tasks': {'overdue': [], 'due_7d': [], 'due_30d': []},
                }
                context.update(empty_tasks)
                context['tasks_total_count'] = 0
        except Exception:
            empty_tasks = {
                'mandatory_tasks_overdue': [], 'mandatory_tasks_due_3d': [], 'mandatory_tasks_due_30d': [],
                'tasks_quizzes_not_passed': [], 'keycert_tasks_expired': [], 'keycert_tasks_expiring_30d': [],
                'keycert_tasks_actualize': [],
                'asset_tasks_actualize': [], 'software_tasks_actualize': [], 'external_media_tasks_actualize': [],
                'vendor_tasks_actualize': [], 'vendor_tasks_contract_end': [],
                'access_requests_tasks_approve': [], 'document_approve_tasks': [],
                'familiarization_tasks': [], 'framework_compliance_tasks': [], 'local_compliance_tasks': [],
                'internal_compliance_tasks': [], 'risk_treatment_tasks': [],
                'risk_monitoring_review_tasks': {'overdue': [], 'due_7d': [], 'due_30d': []},
            }
            context.update(empty_tasks)
            context['tasks_total_count'] = 0
    return render(request, 'app_cabinet/index.html', context)

def send_email(account, to, subject, body, html=False):
    logger.info(f"Attempting to send email from {account.username} to {to}")
    try:
        email = EmailMessage(
            subject,
            body,
            account.username,
            [to],
            connection=account.get_connection()
        )
        if html:
            email.content_subtype = 'html'
        email.send(fail_silently=False)
        logger.info("Email sent successfully")

        sent_email = Email.objects.create(
            account=account,
            message_id=f"<{uuid.uuid4()}@{account.server.smtp_host}>",
            from_email=account.username,
            to_email=to,
            subject=subject,
            body=body,
            date=timezone.now(),
            email_type='outgoing'
        )
        logger.info(f"Email saved to database. ID: {sent_email.id}")

        return True, "Email sent successfully"
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        logger.error(traceback.format_exc())
        return False, str(e)

def cabinet_auth(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        login(request, user)
        cabinet_user, created = CabinetUser.objects.get_or_create(user=user)
        if created or not cabinet_user.is_profile_completed:
            return redirect(_personal_cabinet_user_info_url())
        return redirect('quiz_list')
    else:
        return render(request, 'app_cabinet/cabinet_invalid_token.html')
def first_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            cabinet_settings = CabinetSettings.objects.first()
            if not cabinet_settings:
                messages.error(request, _("Cabinet settings not found. Please contact the administrator."))
                return render(request, 'app_cabinet/first_login.html', {'form': form})

            password_link = CabinetPasswordCompanyLink.objects.filter(
                cabinet_settings=cabinet_settings,
                cabinet_password=password
            ).first()

            if not password_link:
                messages.error(request, _("Incorrect cabinet password. Please try again."))
                return render(request, 'app_cabinet/first_login.html', {'form': form})

            user, created = User.objects.get_or_create(username=email, email=email)
            cabinet_user, created = CabinetUser.objects.get_or_create(user=user)

            # Set the company based on the cabinet password
            cabinet_user.company = password_link.company
            cabinet_user.save()

            if password_link.company.group:
                user.groups.add(password_link.company.group)

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            login_url = request.build_absolute_uri(reverse('cabinet_auth', kwargs={'uidb64': uid, 'token': token}))

            if cabinet_settings.mail_account:
                mail_account = cabinet_settings.mail_account
                try:
                    subject = _('Login Link for SecBoard Group Cyber Security Portal')
                    message = _(f'Click here to access the SecBoard Group Cyber Security Portal: {login_url}')
                    from_email = mail_account.username
                    recipient_list = [email]

                    # Use direct SMTP connection for better reliability
                    smtp = None
                    try:
                        # Create the email message
                        msg = MIMEText(message, 'plain', 'utf-8')
                        msg['From'] = from_email
                        msg['To'] = email
                        msg['Subject'] = subject

                        # Connect to the server directly using smtplib
                        if mail_account.server.use_ssl:
                            # Create SSL context
                            context = ssl.create_default_context()
                            context.check_hostname = False
                            context.verify_mode = ssl.CERT_NONE
                            
                            # Connect with SSL
                            smtp = smtplib.SMTP_SSL(
                                host=mail_account.server.smtp_host,
                                port=mail_account.server.smtp_port,
                                context=context,
                                timeout=30
                            )
                        else:
                            # Connect without SSL
                            smtp = smtplib.SMTP(
                                host=mail_account.server.smtp_host,
                                port=mail_account.server.smtp_port,
                                timeout=30
                            )
                            
                            # Use TLS if needed
                            if mail_account.server.use_tls:
                                smtp.starttls()
                        
                        # Login and send
                        smtp.login(mail_account.username, mail_account.password)
                        smtp.send_message(msg)
                        
                        # Log the sent email
                        Email.objects.create(
                            account=mail_account,
                            message_id=f"<{uuid.uuid4()}@{mail_account.server.smtp_host}>",
                            from_email=from_email,
                            to_email=email,
                            subject=subject,
                            body=message,
                            date=timezone.now(),
                            email_type='outgoing'
                        )

                        messages.success(request, _("Login link sent to your email address."))
                        return render(request, 'app_cabinet/first_login_sent.html')
                    except smtplib.SMTPException as e:
                        logging.error(f"SMTP error sending email: {e}")
                        raise
                    except Exception as e:
                        logging.error(f"Error sending email: {e}")
                        raise
                    finally:
                        # Ensure connection is properly closed
                        if smtp:
                            try:
                                smtp.quit()
                            except:
                                try:
                                    smtp.close()
                                except:
                                    pass
                except Exception as e:
                    logging.error(f"Error sending email in first_login: {e}", exc_info=True)
                    messages.error(request, f"Error sending email: {str(e)}")
            else:
                messages.error(request, _("Email account not configured. Please contact the administrator."))
        else:
            messages.error(request, _("Invalid form submission. Please check your input."))

    else:
        form = LoginForm()

    return render(request, 'app_cabinet/first_login.html', {'form': form})


def _personal_cabinet_user_info_url(language=''):
    from .language_utils import build_language_prefixed_url
    path = reverse('personal_cabinet')
    if language:
        path = build_language_prefixed_url(path, language)
    return f'{path}#user-info'


def _build_profile_form(cabinet_user, request=None, data=None, files=None):
    initial_data = {
        'company': cabinet_user.company.name if cabinet_user.company else _("Not assigned")
    }
    kwargs = {'instance': cabinet_user, 'initial': initial_data, 'request': request}
    if data is not None:
        kwargs['data'] = data
    if files is not None:
        kwargs['files'] = files
    return UpdateProfileForm(**kwargs)


def _handle_profile_update_post(request, cabinet_user):
    """Process profile form POST. Returns redirect response, invalid form, or None."""
    from .input_security import PersonalCabinetSecurityValidator, PersonalCabinetAuditLogger, get_client_ip
    from .language_utils import apply_user_language

    if request.method != 'POST' or request.POST.get('profile_update') != '1':
        return None

    if cabinet_user.user != request.user:
        logger.warning(
            "User %s attempted to access profile for user %s",
            request.user.username,
            cabinet_user.user.username,
        )
        messages.error(request, _('Access denied. You can only update your own profile.'))
        return redirect('personal_cabinet')

    form = UpdateProfileForm(request.POST, request.FILES, instance=cabinet_user, request=request)
    if not form.is_valid():
        ip = get_client_ip(request)
        logger.warning(
            "Profile update form validation failed for user %s from IP %s. Errors in fields: %s",
            request.user.username,
            ip,
            list(form.errors.keys()),
        )
        return form

    try:
        validator = PersonalCabinetSecurityValidator()
        validator.validate_privilege_escalation_attempt(
            request.user,
            target_user_id=cabinet_user.user.id,
            company_change=None,
            department_change=None,
            position_change=None,
        )

        cabinet_user = form.save()
        cabinet_user.is_profile_completed = True
        cabinet_user.save()

        new_password = form.cleaned_data.get('new_password1')
        if new_password:
            password_reset_flags = UserActivity.objects.filter(
                user=request.user,
                action='password_reset',
                details__force_change=True,
                details__processed__isnull=True,
            )
            for flag in password_reset_flags:
                flag.details['processed'] = True
                flag.save()

            UserActivity.objects.create(
                user=request.user,
                action='password_change',
                details={
                    'source': 'profile_update',
                    'timestamp': timezone.now().isoformat(),
                },
            )

            user = authenticate(username=cabinet_user.user.username, password=new_password)
            if user:
                login(request, user)
                messages.success(request, _('Your profile has been updated and a new password has been set.'))
            else:
                messages.warning(
                    request,
                    _('Profile updated but there was an issue with password authentication. Please log in again.'),
                )
                return redirect('login')
        else:
            messages.success(request, _('Your profile has been updated successfully.'))

        language = (form.cleaned_data.get('preferred_language') or '').strip()
        if language:
            apply_user_language(request, language)
        return redirect(_personal_cabinet_user_info_url(language))

    except ValidationError as e:
        ip = get_client_ip(request)
        PersonalCabinetAuditLogger.log_privilege_escalation_attempt(
            request.user, 'profile_update_validation_failed', ip, str(e)
        )
        messages.error(request, _('Security validation failed. Please contact support if this continues.'))
        logger.warning(
            "Profile update security validation failed for user %s: %s",
            request.user.username,
            str(e),
        )
        return redirect(_personal_cabinet_user_info_url())

    return None


@login_required
def update_profile(request):
    cabinet_user, _created = CabinetUser.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        result = _handle_profile_update_post(request, cabinet_user)
        if result is not None:
            if hasattr(result, 'status_code'):
                return result
            return redirect(_personal_cabinet_user_info_url())
    return redirect(_personal_cabinet_user_info_url())

def unauthorized_access(request):
    return render(request, 'app_cabinet/unauthorized.html')


def logout_view(request):
    auth_logout(request)
    messages.success(request, _("You have been successfully logged out."))
    return redirect('index')


def get_tasks_context_for_cabinet_user(cabinet_user):
    """Build the same tasks context as personal_cabinet Tasks tab, for a given CabinetUser (e.g. for modal in users list)."""
    user = cabinet_user.user
    today = timezone.now().date()
    end_3d = today + timedelta(days=3)
    end_30d = today + timedelta(days=30)
    user_groups = list(user.groups.all())

    # Quiz data and not passed for this user (only ACTIVE quizzes)
    all_quizzes = Quiz.objects.filter(is_active=True).prefetch_related('page', 'companies', 'cabinet_groups', 'cabinet_users')
    accessible_quizzes = [q for q in all_quizzes if q.has_user_access(user)]
    quiz_data = []
    for quiz in accessible_quizzes:
        attempts = QuizAttempt.objects.filter(user=user, quiz=quiz)
        best_score = attempts.aggregate(Max('score'))['score__max']
        completed_attempts = attempts.filter(completed=True)
        passed_attempts = completed_attempts.filter(score__gte=quiz.passing_score)
        quiz_data.append({
            'id': quiz.id, 'title': quiz.title, 'description': quiz.description,
            'attempted': attempts.exists(), 'passing_score': quiz.passing_score,
            'is_passed': passed_attempts.exists(),
            'needs_retake': completed_attempts.exists() and not passed_attempts.exists(),
        })
    tasks_quizzes_not_passed = [q for q in quiz_data if not q['is_passed']]

    # Mandatory processes
    base_tasks = MandatoryProcess.objects.filter(
        is_active=True, next_due_date__isnull=False
    ).filter(
        Q(responsible_person=user) | Q(additional_person=user)
    ).distinct().select_related('company').order_by('next_due_date')
    mandatory_tasks_overdue = list(base_tasks.filter(next_due_date__lt=today))
    mandatory_tasks_due_3d = list(base_tasks.filter(next_due_date__gte=today, next_due_date__lte=end_3d))
    mandatory_tasks_due_30d = list(base_tasks.filter(next_due_date__gt=end_3d, next_due_date__lte=end_30d))

    # Keycert
    access_key_cert = AccessKeyCert.objects.filter(group__in=user_groups, has_access=True)
    allowed_companies_keycert = Company.objects.filter(access_keycert__in=access_key_cert).distinct()
    user_email = (user.email or '').strip() or ((user.username or '').strip() if '@' in (user.username or '') else '')
    keycert_owner_ids_fallback = list(KeycertOwner.objects.filter(email__iexact=user_email).values_list('id', flat=True)) if user_email else []
    if not keycert_owner_ids_fallback and user_email:
        keycert_owner_ids_fallback = [o.id for o in KeycertOwner.objects.only('id', 'email') if (o.email or '').strip().lower() == user_email.lower()]
    keycert_base = KeyCertificates.objects.filter(company__in=allowed_companies_keycert).filter(
        Q(owner_cabinet_user=cabinet_user)
        | Q(owner_cabinet_user__isnull=True, owner__isnull=True, company=cabinet_user.company)
        | Q(owner_cabinet_user__isnull=True, owner_id__in=keycert_owner_ids_fallback)
    )
    keycert_tasks_expired = list(keycert_base.filter(expiry_date__lt=today).select_related('company', 'owner').order_by('expiry_date'))
    keycert_tasks_expiring_30d = list(keycert_base.filter(expiry_date__gte=today, expiry_date__lte=end_30d).select_related('company', 'owner').order_by('expiry_date'))

    keycert_actualize_threshold = timezone.now() - timedelta(days=335)
    keycert_tasks_actualize = list(
        KeyCertificates.objects.filter(
            company__in=allowed_companies_keycert,
            owner_cabinet_user=cabinet_user,
        )
        .filter(Q(actualization_date__isnull=True) | Q(actualization_date__lt=keycert_actualize_threshold))
        .select_related('company', 'owner')
        .order_by('key_cert_num')
    )

    # Assets
    asset_actualize_threshold = timezone.now() - timedelta(days=335)
    asset_tasks_actualize = list(
        InformationAsset.objects.filter(owners__cabinet_user=cabinet_user)
        .filter(Q(actualization_date__isnull=True) | Q(actualization_date__lt=asset_actualize_threshold))
        .distinct().select_related('company').order_by('asset_id')
    )
    software_license_warn_threshold = today + timedelta(days=14)
    software_tasks_actualize = list(
        SoftwareRegister.objects.filter(owners__cabinet_user=cabinet_user, is_active=True)
        .filter(
            Q(actualization_date__isnull=True)
            | Q(actualization_date__lt=asset_actualize_threshold)
            | Q(license_valid_until__isnull=False, license_valid_until__lte=software_license_warn_threshold)
        )
        .distinct().select_related('company').order_by('name')
    )
    for sw in software_tasks_actualize:
        sw.license_warning_days = None
        if sw.license_valid_until:
            sw.license_warning_days = (sw.license_valid_until - today).days
    external_media_tasks_actualize = list(
        ExternalMediaRegister.objects.filter(owners__cabinet_user=cabinet_user, is_active=True)
        .filter(Q(actualization_date__isnull=True) | Q(actualization_date__lt=asset_actualize_threshold))
        .distinct().select_related('company').order_by('name')
    )

    # TPRM Vendors (app_tprm): as TprmOwner — yearly actualization (~11 months) and/or contract end within 30 days
    from app_tprm.models import Vendor as TprmVendor
    vendor_actualize_threshold = timezone.now() - timedelta(days=335)
    vendor_tasks_actualize = list(
        TprmVendor.objects.filter(owners__cabinet_user=cabinet_user, is_active=True)
        .filter(Q(actualization_date__isnull=True) | Q(actualization_date__lt=vendor_actualize_threshold))
        .distinct()
        .select_related('company')
        .order_by('name')
    )
    contract_end_warn_until = today + timedelta(days=30)
    vendor_tasks_contract_end = list(
        TprmVendor.objects.filter(owners__cabinet_user=cabinet_user, is_active=True)
        .filter(contract_end_date__isnull=False)
        .filter(contract_end_date__lte=contract_end_warn_until)
        .distinct()
        .select_related('company')
        .order_by('contract_end_date', 'name')
    )
    for vv in vendor_tasks_contract_end:
        vv.contract_end_days = (vv.contract_end_date - today).days

    # Access requests
    access_requests_tasks_approve = list(
        AccessRequest.objects.filter(
            Q(request_approvers__cabinet_user=cabinet_user, request_approvers__current_status='pending')
            | Q(system__administrators__cabinet_user=cabinet_user, request_approvers__current_status='pending')
        ).filter(status='pending').distinct()
        .select_related('company', 'system', 'requested_by', 'requested_for').order_by('-created_at')
    )

    # Document approve
    document_approve_tasks = list(
        RegisterDocs.objects.filter(
            documentapproval__approver=user, documentapproval__status='pending',
        ).distinct().select_related('company', 'type_doc', 'status_doc').order_by('-updated_at')
    )

    # Familiarization: documents approved, user has access, not yet acknowledged (current hash)
    familiarization_tasks = list(
        RegisterDocs.objects.filter(
            Q(groups__in=user_groups) | Q(allowed_users=user),
            is_approved=True,
        )
        .distinct()
        .exclude(
            Exists(
                DocumentFamiliarization.objects.filter(
                    document_id=OuterRef('pk'),
                    user=user,
                    document_hash=OuterRef('document_hash'),
                )
            )
        )
        .select_related('company', 'type_doc', 'status_doc')
        .order_by('-updated_at')
    )

    # Framework / Local / Internal compliance
    framework_compliance_incomplete_statuses = ['not_started', 'in_progress', 'ready_for_review', 'failed']
    _priority_order = Case(
        When(priority='critical', then=Value(0)), When(priority='high', then=Value(1)),
        When(priority='medium', then=Value(2)), When(priority='low', then=Value(3)),
        default=Value(2), output_field=IntegerField(),
    )
    _status_order = Case(
        When(status='failed', then=Value(0)), When(status='in_progress', then=Value(1)),
        When(status='ready_for_review', then=Value(2)), When(status='not_started', then=Value(3)),
        default=Value(4), output_field=IntegerField(),
    )
    framework_compliance_tasks = list(
        Control.objects.filter(
            Q(responsible=user) | Q(assignments__user=user, assignments__assignment_type='owner', assignments__is_active=True),
            status__in=framework_compliance_incomplete_statuses,
        ).distinct().annotate(priority_order=_priority_order, status_order=_status_order)
        .select_related('category', 'category__framework')
        .order_by('category__framework__name', 'priority_order', 'status_order', 'code')
    )
    local_compliance_tasks = list(
        LocalComplianceControl.objects.filter(
            Q(responsible=user) | Q(responsible__cabinet=cabinet_user)
            | Q(assignments__user=user, assignments__assignment_type='owner', assignments__is_active=True),
            status__in=framework_compliance_incomplete_statuses,
        ).distinct().annotate(priority_order=_priority_order, status_order=_status_order)
        .select_related('requirement', 'requirement__regulator', 'company')
        .order_by('requirement__name', 'priority_order', 'status_order', 'code')
    )
    internal_compliance_tasks = list(
        InternalComplianceControl.objects.filter(
            Q(responsible=user) | Q(responsible__cabinet=cabinet_user)
            | Q(assignments__user=user, assignments__assignment_type='owner', assignments__is_active=True),
            status__in=framework_compliance_incomplete_statuses,
        ).distinct().annotate(priority_order=_priority_order, status_order=_status_order)
        .select_related('requirement', 'company')
        .order_by('requirement__name', 'priority_order', 'status_order', 'code')
    )

    # Risk Treatment tasks: where user is Responsible or Monitoring Responsible, status not Completed
    risk_treatment_tasks = _get_risk_treatment_tasks(cabinet_user)
    # Risk Monitoring Review: where user is Monitoring Responsible, next_review_date set, review due soon
    risk_monitoring_review_tasks = _get_risk_monitoring_review_tasks(cabinet_user)

    return {
        'mandatory_tasks_overdue': mandatory_tasks_overdue,
        'mandatory_tasks_due_3d': mandatory_tasks_due_3d,
        'mandatory_tasks_due_30d': mandatory_tasks_due_30d,
        'tasks_quizzes_not_passed': tasks_quizzes_not_passed,
        'keycert_tasks_expired': keycert_tasks_expired,
        'keycert_tasks_expiring_30d': keycert_tasks_expiring_30d,
        'keycert_tasks_actualize': keycert_tasks_actualize,
        'asset_tasks_actualize': asset_tasks_actualize,
        'software_tasks_actualize': software_tasks_actualize,
        'external_media_tasks_actualize': external_media_tasks_actualize,
        'vendor_tasks_actualize': vendor_tasks_actualize,
        'vendor_tasks_contract_end': vendor_tasks_contract_end,
        'access_requests_tasks_approve': access_requests_tasks_approve,
        'document_approve_tasks': document_approve_tasks,
        'familiarization_tasks': familiarization_tasks,
        'framework_compliance_tasks': framework_compliance_tasks,
        'local_compliance_tasks': local_compliance_tasks,
        'internal_compliance_tasks': internal_compliance_tasks,
        'risk_treatment_tasks': risk_treatment_tasks,
        'risk_monitoring_review_tasks': risk_monitoring_review_tasks,
    }


def get_tasks_count_for_cabinet_user(cabinet_user):
    """Return total number of tasks for the given CabinetUser (for display in users list)."""
    ctx = get_tasks_context_for_cabinet_user(cabinet_user)
    return (
        len(ctx.get('mandatory_tasks_overdue', []))
        + len(ctx.get('mandatory_tasks_due_3d', []))
        + len(ctx.get('mandatory_tasks_due_30d', []))
        + len(ctx.get('tasks_quizzes_not_passed', []))
        + len(ctx.get('keycert_tasks_expired', []))
        + len(ctx.get('keycert_tasks_expiring_30d', []))
        + len(ctx.get('keycert_tasks_actualize', []))
        + len(ctx.get('asset_tasks_actualize', []))
        + len(ctx.get('software_tasks_actualize', []))
        + len(ctx.get('external_media_tasks_actualize', []))
        + len(ctx.get('vendor_tasks_actualize', []))
        + len(ctx.get('vendor_tasks_contract_end', []))
        + len(ctx.get('access_requests_tasks_approve', []))
        + len(ctx.get('document_approve_tasks', []))
        + len(ctx.get('familiarization_tasks', []))
        + len(ctx.get('framework_compliance_tasks', []))
        + len(ctx.get('local_compliance_tasks', []))
        + len(ctx.get('internal_compliance_tasks', []))
        + len(ctx.get('risk_treatment_tasks', []))
        + len(ctx.get('risk_monitoring_review_tasks', {}).get('overdue', []))
        + len(ctx.get('risk_monitoring_review_tasks', {}).get('due_7d', []))
        + len(ctx.get('risk_monitoring_review_tasks', {}).get('due_30d', []))
    )


@login_required
def personal_cabinet(request):
    cabinet_user, created = CabinetUser.objects.get_or_create(user=request.user)
    cabinet_user = CabinetUser.objects.filter(pk=cabinet_user.pk).prefetch_related('roles').first()

    profile_form = None
    active_tab = ''
    profile_update_result = _handle_profile_update_post(request, cabinet_user)
    if profile_update_result is not None:
        if hasattr(profile_update_result, 'status_code'):
            return profile_update_result
        profile_form = profile_update_result
        active_tab = 'user-info'

    profile_setup_required = not cabinet_user.is_profile_completed or not cabinet_user.company
    if profile_setup_required:
        if not cabinet_user.is_profile_completed:
            messages.warning(request, _("Please complete your profile to access all features."))
        elif not cabinet_user.company:
            messages.warning(request, _("You are not assigned to any company. Please contact the administrator."))
        active_tab = 'user-info'

    if profile_form is None:
        profile_form = _build_profile_form(cabinet_user, request=request)

    from app_integration.telegram_link import get_telegram_profile_link_context
    telegram_link = get_telegram_profile_link_context(cabinet_user)

    # Get all ACTIVE quizzes and filter by access
    all_quizzes = Quiz.objects.filter(is_active=True).prefetch_related('page', 'companies', 'cabinet_groups', 'cabinet_users')
    accessible_quizzes = [quiz for quiz in all_quizzes if quiz.has_user_access(request.user)]

    quiz_data = []
    for quiz in accessible_quizzes:
        attempts = QuizAttempt.objects.filter(user=request.user, quiz=quiz)
        best_score = attempts.aggregate(Max('score'))['score__max']
        completed_attempts = attempts.filter(completed=True)
        passed_attempts = completed_attempts.filter(score__gte=quiz.passing_score)
        
        quiz_info = {
            'id': quiz.id,
            'title': quiz.title,
            'description': quiz.description,
            'youtube_video_id': quiz.youtube_video_id,
            'attempted': attempts.exists(),
            'attempt_count': attempts.count(),
            'best_score': best_score,
            'page': quiz.page,
            'pdf_url': quiz.get_pdf_url(),  # Використовуємо метод з моделі
            'pdf_filename': quiz.pdf_filename if quiz.pdf_material else None,
            'pdf_material': quiz.pdf_material if quiz.pdf_material else None,
            'passing_score': quiz.passing_score,
            'is_passed': passed_attempts.exists(),
            'is_completed': completed_attempts.exists(),
            'needs_retake': completed_attempts.exists() and not passed_attempts.exists(),
        }
        quiz_data.append(quiz_info)

    accessible_pages = Page.objects.filter(companies=cabinet_user.company, is_active=True)

    all_attempts = QuizAttempt.objects.filter(user=request.user).order_by('-completed_at').select_related(
        'quiz').annotate(
        correct_answers_count=Sum(Case(When(answers__is_correct=True, then=1), default=0, output_field=IntegerField())),
        total_questions_count=Count('answers')
    )

    # Отримання документів відповідно до групи користувача
    user_groups = request.user.groups.all()
    register_docs = RegisterDocs.objects.filter(groups__in=user_groups).distinct()
    related_docs = RelatedDocs.objects.filter(groups__in=user_groups).distinct()

    # Mandatory processes where user is Responsible or Additional: overdue, due in 3 days, due in 30 days
    today = timezone.now().date()
    end_3d = today + timedelta(days=3)
    end_30d = today + timedelta(days=30)
    base_tasks = MandatoryProcess.objects.filter(
        is_active=True,
        next_due_date__isnull=False
    ).filter(
        Q(responsible_person=request.user) | Q(additional_person=request.user)
    ).distinct().select_related('company').order_by('next_due_date')
    mandatory_tasks_overdue = list(base_tasks.filter(next_due_date__lt=today))
    mandatory_tasks_due_3d = list(base_tasks.filter(next_due_date__gte=today, next_due_date__lte=end_3d))
    mandatory_tasks_due_30d = list(base_tasks.filter(next_due_date__gt=end_3d, next_due_date__lte=end_30d))

    # Quizzes (tests) not passed — to show in Tasks
    tasks_quizzes_not_passed = [q for q in quiz_data if not q['is_passed']]

    # Keys/Certificates (app_keycert): reminders for Owner (Cabinet user) or no-owner in user's company — expired and expiring within 30 days
    # Prefer owner_cabinet_user (set when Owner is chosen from Cabinet users). Fallback: owner_cabinet_user not set but owner (KeycertOwner) email matches current user.
    access_key_cert = AccessKeyCert.objects.filter(group__in=user_groups, has_access=True)
    allowed_companies_keycert = Company.objects.filter(access_keycert__in=access_key_cert).distinct()
    user_email = (request.user.email or '').strip() or ((request.user.username or '').strip() if '@' in (request.user.username or '') else '')
    keycert_owner_ids_fallback = list(KeycertOwner.objects.filter(email__iexact=user_email).values_list('id', flat=True)) if user_email else []
    if not keycert_owner_ids_fallback and user_email:
        keycert_owner_ids_fallback = [o.id for o in KeycertOwner.objects.only('id', 'email') if (o.email or '').strip().lower() == user_email.lower()]
    keycert_base = KeyCertificates.objects.filter(company__in=allowed_companies_keycert).filter(
        Q(owner_cabinet_user=cabinet_user)
        | Q(owner_cabinet_user__isnull=True, owner__isnull=True, company=cabinet_user.company)
        | Q(owner_cabinet_user__isnull=True, owner_id__in=keycert_owner_ids_fallback)
    )
    keycert_tasks_expired = list(keycert_base.filter(expiry_date__lt=today).select_related('company', 'owner').order_by('expiry_date'))
    keycert_tasks_expiring_30d = list(keycert_base.filter(expiry_date__gte=today, expiry_date__lte=end_30d).select_related('company', 'owner').order_by('expiry_date'))

    keycert_actualize_threshold = timezone.now() - timedelta(days=335)
    keycert_tasks_actualize = list(
        KeyCertificates.objects.filter(
            company__in=allowed_companies_keycert,
            owner_cabinet_user=cabinet_user,
        )
        .filter(Q(actualization_date__isnull=True) | Q(actualization_date__lt=keycert_actualize_threshold))
        .select_related('company', 'owner')
        .order_by('key_cert_num')
    )

    # Assets (app_asset): as Owner (via AssetOwner.cabinet_user), assets not actualized or actualized > 11 months ago
    asset_actualize_threshold = timezone.now() - timedelta(days=335)  # ~11 months
    # Match assets where current user is Owner (owners__cabinet_user); show all such assets so Tasks count is correct
    asset_tasks_actualize = list(
        InformationAsset.objects.filter(owners__cabinet_user=cabinet_user)
        .filter(Q(actualization_date__isnull=True) | Q(actualization_date__lt=asset_actualize_threshold))
        .distinct().select_related('company').order_by('asset_id')
    )
    software_license_warn_threshold = today + timedelta(days=14)
    software_tasks_actualize = list(
        SoftwareRegister.objects.filter(owners__cabinet_user=cabinet_user, is_active=True)
        .filter(
            Q(actualization_date__isnull=True)
            | Q(actualization_date__lt=asset_actualize_threshold)
            | Q(license_valid_until__isnull=False, license_valid_until__lte=software_license_warn_threshold)
        )
        .distinct().select_related('company').order_by('name')
    )
    for sw in software_tasks_actualize:
        sw.license_warning_days = None
        if sw.license_valid_until:
            sw.license_warning_days = (sw.license_valid_until - today).days
    external_media_tasks_actualize = list(
        ExternalMediaRegister.objects.filter(owners__cabinet_user=cabinet_user, is_active=True)
        .filter(Q(actualization_date__isnull=True) | Q(actualization_date__lt=asset_actualize_threshold))
        .distinct().select_related('company').order_by('name')
    )

    from app_tprm.models import Vendor as TprmVendor
    vendor_actualize_threshold = timezone.now() - timedelta(days=335)
    vendor_tasks_actualize = list(
        TprmVendor.objects.filter(owners__cabinet_user=cabinet_user, is_active=True)
        .filter(Q(actualization_date__isnull=True) | Q(actualization_date__lt=vendor_actualize_threshold))
        .distinct()
        .select_related('company')
        .order_by('name')
    )
    contract_end_warn_until = today + timedelta(days=30)
    vendor_tasks_contract_end = list(
        TprmVendor.objects.filter(owners__cabinet_user=cabinet_user, is_active=True)
        .filter(contract_end_date__isnull=False)
        .filter(contract_end_date__lte=contract_end_warn_until)
        .distinct()
        .select_related('company')
        .order_by('contract_end_date', 'name')
    )
    for vv in vendor_tasks_contract_end:
        vv.contract_end_days = (vv.contract_end_date - today).days

    # Access Requests: tasks requiring approval — Cabinet User is Approving Person (pending) or Administrator (system has pending approvers)
    access_requests_tasks_approve = list(
        AccessRequest.objects.filter(
            Q(request_approvers__cabinet_user=cabinet_user, request_approvers__current_status='pending')
            | Q(system__administrators__cabinet_user=cabinet_user, request_approvers__current_status='pending')
        )
        .filter(status='pending')
        .distinct()
        .select_related('company', 'system', 'requested_by', 'requested_for')
        .order_by('-created_at')
    )

    # Document Approve: register documents where this user is approver and approval status is pending
    document_approve_tasks = list(
        RegisterDocs.objects.filter(
            documentapproval__approver=request.user,
            documentapproval__status='pending',
        )
        .distinct()
        .select_related('company', 'type_doc', 'status_doc')
        .order_by('-updated_at')
    )

    # Familiarization: documents approved and with access, not yet acknowledged by user (with current hash)
    familiarization_tasks = list(
        RegisterDocs.objects.filter(
            Q(groups__in=request.user.groups.all()) | Q(allowed_users=request.user),
            is_approved=True,
        )
        .distinct()
        .exclude(
            Exists(
                DocumentFamiliarization.objects.filter(
                    document_id=OuterRef('pk'),
                    user=request.user,
                    document_hash=OuterRef('document_hash'),
                )
            )
        )
        .select_related('company', 'type_doc', 'status_doc')
        .order_by('-updated_at')
    )

    # Framework Compliance: controls where user is Responsible (Control.responsible) or Owner (ControlAssignment), status In Progress / Ready for Review / Not Started / Failed
    framework_compliance_incomplete_statuses = ['not_started', 'in_progress', 'ready_for_review', 'failed']
    _priority_order = Case(
        When(priority='critical', then=Value(0)),
        When(priority='high', then=Value(1)),
        When(priority='medium', then=Value(2)),
        When(priority='low', then=Value(3)),
        default=Value(2),
        output_field=IntegerField(),
    )
    _status_order = Case(
        When(status='failed', then=Value(0)),
        When(status='in_progress', then=Value(1)),
        When(status='ready_for_review', then=Value(2)),
        When(status='not_started', then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )
    framework_compliance_tasks = list(
        Control.objects.filter(
            Q(responsible=request.user)
            | Q(assignments__user=request.user, assignments__assignment_type='owner', assignments__is_active=True),
            status__in=framework_compliance_incomplete_statuses,
        )
        .distinct()
        .annotate(priority_order=_priority_order, status_order=_status_order)
        .select_related('category', 'category__framework')
        .order_by('category__framework__name', 'priority_order', 'status_order', 'code')
    )

    # Local Compliance: controls where user is Responsible or Owner (LocalControlAssignment), status Not Started / In Progress / Ready for Review / Failed
    # Include responsible__cabinet=cabinet_user so we match when Responsible is the User linked to this CabinetUser (handles UI/store mismatches)
    local_compliance_tasks = list(
        LocalComplianceControl.objects.filter(
            Q(responsible=request.user)
            | Q(responsible__cabinet=cabinet_user)
            | Q(assignments__user=request.user, assignments__assignment_type='owner', assignments__is_active=True),
            status__in=framework_compliance_incomplete_statuses,
        )
        .distinct()
        .annotate(priority_order=_priority_order, status_order=_status_order)
        .select_related('requirement', 'requirement__regulator', 'company')
        .order_by('requirement__name', 'priority_order', 'status_order', 'code')
    )

    # Internal Compliance: controls where user is Responsible or Owner (InternalControlAssignment), status Not Started / In Progress / Ready for Review / Failed
    internal_compliance_tasks = list(
        InternalComplianceControl.objects.filter(
            Q(responsible=request.user)
            | Q(responsible__cabinet=cabinet_user)
            | Q(assignments__user=request.user, assignments__assignment_type='owner', assignments__is_active=True),
            status__in=framework_compliance_incomplete_statuses,
        )
        .distinct()
        .annotate(priority_order=_priority_order, status_order=_status_order)
        .select_related('requirement', 'company')
        .order_by('requirement__name', 'priority_order', 'status_order', 'code')
    )

    # Risk Treatment tasks: where user is Responsible or Monitoring Responsible, status not Completed
    risk_treatment_tasks = _get_risk_treatment_tasks(cabinet_user)
    risk_monitoring_review_tasks = _get_risk_monitoring_review_tasks(cabinet_user)

    tasks_total_count = (
        len(mandatory_tasks_overdue) + len(mandatory_tasks_due_3d) + len(mandatory_tasks_due_30d)
        + len(tasks_quizzes_not_passed)
        + len(keycert_tasks_expired) + len(keycert_tasks_expiring_30d)
        + len(keycert_tasks_actualize)
        + len(asset_tasks_actualize)
        + len(software_tasks_actualize) + len(external_media_tasks_actualize)
        + len(vendor_tasks_actualize) + len(vendor_tasks_contract_end)
        + len(access_requests_tasks_approve) + len(document_approve_tasks) + len(familiarization_tasks)
        + len(framework_compliance_tasks) + len(local_compliance_tasks) + len(internal_compliance_tasks)
        + len(risk_treatment_tasks)
        + len(risk_monitoring_review_tasks.get('overdue', []))
        + len(risk_monitoring_review_tasks.get('due_7d', []))
        + len(risk_monitoring_review_tasks.get('due_30d', []))
    )
    context = {
        'cabinet_user': cabinet_user,
        'user': request.user,
        'quizzes': quiz_data,
        'accessible_pages': accessible_pages,
        'all_attempts': all_attempts,
        'register_docs': register_docs,
        'related_docs': related_docs,
        'mandatory_tasks_overdue': mandatory_tasks_overdue,
        'mandatory_tasks_due_3d': mandatory_tasks_due_3d,
        'mandatory_tasks_due_30d': mandatory_tasks_due_30d,
        'tasks_quizzes_not_passed': tasks_quizzes_not_passed,
        'keycert_tasks_expired': keycert_tasks_expired,
        'keycert_tasks_expiring_30d': keycert_tasks_expiring_30d,
        'keycert_tasks_actualize': keycert_tasks_actualize,
        'asset_tasks_actualize': asset_tasks_actualize,
        'software_tasks_actualize': software_tasks_actualize,
        'external_media_tasks_actualize': external_media_tasks_actualize,
        'vendor_tasks_actualize': vendor_tasks_actualize,
        'vendor_tasks_contract_end': vendor_tasks_contract_end,
        'access_requests_tasks_approve': access_requests_tasks_approve,
        'document_approve_tasks': document_approve_tasks,
        'familiarization_tasks': familiarization_tasks,
        'framework_compliance_tasks': framework_compliance_tasks,
        'local_compliance_tasks': local_compliance_tasks,
        'internal_compliance_tasks': internal_compliance_tasks,
        'risk_treatment_tasks': risk_treatment_tasks,
        'risk_monitoring_review_tasks': risk_monitoring_review_tasks,
        'tasks_total_count': tasks_total_count,
        'two_factor_backup_remaining': sum(1 for code in (cabinet_user.two_factor_backup_codes or []) if not code.get('used')),
        'force_two_factor_required': cabinet_user.force_two_factor,
        'profile_form': profile_form,
        'telegram_link': telegram_link,
        'profile_setup_required': profile_setup_required,
        'active_tab': active_tab,
    }
    executive_ctx = _get_executive_view_context(request, cabinet_user)
    if executive_ctx:
        context.update(executive_ctx)
    return render(request, 'app_cabinet/personal_cabinet.html', context)


@login_required
@require_permission('users', 'view')
def get_user_tasks_content(request, pk):
    """Return HTML fragment of Tasks for a given CabinetUser (for modal in users list)."""
    cabinet_user = get_object_or_404(CabinetUser, pk=pk)
    tasks_ctx = get_tasks_context_for_cabinet_user(cabinet_user)
    tasks_ctx['target_display_name'] = getattr(cabinet_user, 'display_name', None) or (
        cabinet_user.user.get_full_name() or cabinet_user.user.username
    )
    html = render_to_string('app_cabinet/includes/user_tasks_modal_content.html', tasks_ctx, request=request)
    return HttpResponse(html)


@login_required
@require_http_methods(["POST"])
def two_factor_setup(request):
    cabinet_user, _created = CabinetUser.objects.get_or_create(user=request.user)
    if cabinet_user.two_factor_enabled:
        return JsonResponse({'error': _("Two-factor authentication is already enabled.")}, status=400)

    secret = pyotp.random_base32()
    cabinet_user.two_factor_temp_secret = secret
    cabinet_user.two_factor_temp_created_at = timezone.now()
    cabinet_user.save(update_fields=['two_factor_temp_secret', 'two_factor_temp_created_at'])

    identifier = request.user.email or request.user.username
    issuer = getattr(settings, 'TWO_FACTOR_ISSUER', 'SecBoard')
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(name=identifier, issuer_name=issuer)

    return JsonResponse({
        'success': True,
        'secret': secret,
        'otpauth_uri': provisioning_uri,
    })


@login_required
@require_http_methods(["POST"])
def two_factor_verify(request):
    cabinet_user, _created = CabinetUser.objects.get_or_create(user=request.user)
    if cabinet_user.two_factor_enabled:
        return JsonResponse({'error': _("Two-factor authentication is already active.")}, status=400)

    if not cabinet_user.two_factor_temp_secret:
        return JsonResponse({'error': _("Start the setup process before verifying the code.")}, status=400)

    if cabinet_user.two_factor_temp_created_at and timezone.now() - cabinet_user.two_factor_temp_created_at > TWO_FACTOR_TEMP_VALIDITY:
        cabinet_user.two_factor_temp_secret = ''
        cabinet_user.two_factor_temp_created_at = None
        cabinet_user.save(update_fields=['two_factor_temp_secret', 'two_factor_temp_created_at'])
        return JsonResponse({'error': _("The QR code has expired. Please start again.")}, status=400)

    data = get_request_data(request)
    code = data.get('code')
    is_valid, _unused_backup = verify_two_factor_code(cabinet_user, code, secret=cabinet_user.two_factor_temp_secret)
    if not is_valid:
        return JsonResponse({'error': _("Invalid code. Please try again.")}, status=400)

    plain_codes, hashed_codes = generate_backup_codes()
    cabinet_user.two_factor_secret = cabinet_user.two_factor_temp_secret
    cabinet_user.two_factor_enabled = True
    cabinet_user.two_factor_confirmed_at = timezone.now()
    cabinet_user.two_factor_temp_secret = ''
    cabinet_user.two_factor_temp_created_at = None
    cabinet_user.two_factor_backup_codes = hashed_codes
    cabinet_user.save(update_fields=[
        'two_factor_secret',
        'two_factor_enabled',
        'two_factor_confirmed_at',
        'two_factor_temp_secret',
        'two_factor_temp_created_at',
        'two_factor_backup_codes'
    ])

    UserActivity.objects.create(
        user=request.user,
        action='update_profile',
        url=request.path,
        details={
            'action': 'two_factor_enabled',
            'timestamp': timezone.now().isoformat()
        }
    )

    return JsonResponse({'success': True, 'backup_codes': plain_codes})


@login_required
@require_http_methods(["POST"])
def two_factor_disable(request):
    cabinet_user, _created = CabinetUser.objects.get_or_create(user=request.user)
    if not cabinet_user.two_factor_enabled:
        return JsonResponse({'error': _("Two-factor authentication is not enabled.")}, status=400)

    if cabinet_user.force_two_factor:
        return JsonResponse({'error': _("Two-factor authentication is enforced for your account and cannot be disabled.")}, status=400)

    data = get_request_data(request)
    code = data.get('code')
    is_valid, _unused_backup = verify_two_factor_code(cabinet_user, code, allow_backup=True, mark_backup_used=True)
    if not is_valid:
        return JsonResponse({'error': _("Invalid authentication code.")}, status=400)

    cabinet_user.two_factor_enabled = False
    cabinet_user.two_factor_secret = ''
    cabinet_user.two_factor_backup_codes = []
    cabinet_user.two_factor_confirmed_at = None
    cabinet_user.two_factor_temp_secret = ''
    cabinet_user.two_factor_temp_created_at = None
    cabinet_user.two_factor_last_used = None
    cabinet_user.save(update_fields=[
        'two_factor_enabled',
        'two_factor_secret',
        'two_factor_backup_codes',
        'two_factor_confirmed_at',
        'two_factor_temp_secret',
        'two_factor_temp_created_at',
        'two_factor_last_used'
    ])

    UserActivity.objects.create(
        user=request.user,
        action='update_profile',
        url=request.path,
        details={
            'action': 'two_factor_disabled',
            'timestamp': timezone.now().isoformat()
        }
    )

    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def two_factor_regenerate_codes(request):
    cabinet_user, _created = CabinetUser.objects.get_or_create(user=request.user)
    if not cabinet_user.two_factor_enabled:
        return JsonResponse({'error': _("Enable two-factor authentication first.")}, status=400)

    data = get_request_data(request)
    code = data.get('code')
    is_valid, used_backup = verify_two_factor_code(
        cabinet_user,
        code,
        allow_backup=True,
        mark_backup_used=True
    )
    if not is_valid:
        return JsonResponse({'error': _("Invalid authentication code.")}, status=400)

    plain_codes, hashed_codes = generate_backup_codes()
    cabinet_user.two_factor_backup_codes = hashed_codes
    cabinet_user.save(update_fields=['two_factor_backup_codes'])

    UserActivity.objects.create(
        user=request.user,
        action='update_profile',
        url=request.path,
        details={
            'action': 'two_factor_backup_regenerated',
            'timestamp': timezone.now().isoformat(),
            'used_backup_to_auth': used_backup
        }
    )

    return JsonResponse({'success': True, 'backup_codes': plain_codes})


def update_user_active_status(email):
    """
    Updates user's active status based on start/end dates before login
    Returns tuple (updated, is_active, error_message)
    """
    try:
        user = User.objects.filter(email=email).first()
        if not user:
            return False, False, None

        # Get cabinet user info
        try:
            cabinet_user = CabinetUser.objects.get(user=user)
        except CabinetUser.DoesNotExist:
            return False, user.is_active, None

        now = timezone.now()
        original_status = user.is_active

        # Determine new active status based on dates
        if cabinet_user.start_date or cabinet_user.end_date:
            if cabinet_user.start_date and cabinet_user.end_date:
                user.is_active = cabinet_user.start_date <= now <= cabinet_user.end_date
            elif cabinet_user.start_date:
                user.is_active = cabinet_user.start_date <= now
            else:  # only end_date
                user.is_active = now <= cabinet_user.end_date

            # Save if status changed
            if user.is_active != original_status:
                user.save()
                logger.info(f"Updated user {user.email} active status to {user.is_active}")

        return True, user.is_active, None

    except Exception as e:
        logger.error(f"Error updating user status: {str(e)}")
        return False, False, str(e)
def login_view(request):
    if request.method != 'POST':
        tg_token = request.GET.get('tg')
        if tg_token:
            from app_integration.telegram_link import store_pending_telegram_auth_token
            if not store_pending_telegram_auth_token(request, tg_token):
                messages.error(
                    request,
                    _('This Telegram link has expired or is invalid. Open the bot and request a new sign-in link.'),
                )

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            # Verify CAPTCHA if required
            if hasattr(request, 'require_captcha') and request.require_captcha:
                captcha_response = request.POST.get('g-recaptcha-response')
                if not verify_recaptcha(captcha_response):
                    messages.error(request, _("Invalid CAPTCHA. Please try again."))
                    request._login_failed = True  # Signal to middleware
                    return render(request, 'app_cabinet/login.html', {
                        'form': form, 
                        'require_captcha': True,
                        'page_title': _("Login")
                    })

            # Update user active status before authentication
            updated, is_active, error = update_user_active_status(email)
            if error:
                messages.error(request, _("System error occurred. Please try again later."))
                return render(request, 'app_cabinet/login.html', {'form': form})

            # Get IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')

            # Authenticate user
            user = authenticate(request, username=email, password=password)

            if user is not None:
                # Check if user is active after status update
                if not user.is_active:
                    messages.error(request, _("Your account is currently inactive based on your employment period."))
                    logger.warning(f"Login attempt for inactive user {email} from IP: {ip_address}")
                    request._login_failed = True  # Signal to middleware
                    return render(request, 'app_cabinet/login.html', {'form': form})

                cabinet_user, _created = CabinetUser.objects.get_or_create(user=user)
                if cabinet_user.force_two_factor and not cabinet_user.two_factor_enabled:
                    if not cabinet_user.two_factor_temp_secret or (
                        cabinet_user.two_factor_temp_created_at and
                        timezone.now() - cabinet_user.two_factor_temp_created_at > TWO_FACTOR_TEMP_VALIDITY
                    ):
                        cabinet_user.two_factor_temp_secret = pyotp.random_base32()
                        cabinet_user.two_factor_temp_created_at = timezone.now()
                        cabinet_user.save(update_fields=['two_factor_temp_secret', 'two_factor_temp_created_at'])

                    request.session['pending_force_2fa_user_id'] = user.id
                    request.session['pending_force_2fa_ip'] = ip_address
                    request.session['pending_force_2fa_created'] = timezone.now().timestamp()
                    next_url = request.POST.get('next') or request.GET.get('next')
                    if next_url:
                        request.session['pending_force_2fa_next'] = next_url
                    request.session.modified = True
                    messages.info(request, _("Two-factor authentication is required for your account. Complete setup to continue."))
                    return redirect('force_two_factor_enroll')

                if cabinet_user.two_factor_enabled and cabinet_user.two_factor_secret:
                    request.session['pending_2fa_user_id'] = user.id
                    request.session['pending_2fa_ip'] = ip_address
                    request.session['pending_2fa_user_agent'] = request.META.get('HTTP_USER_AGENT', '')
                    request.session['pending_2fa_created'] = timezone.now().timestamp()
                    next_url = request.POST.get('next') or request.GET.get('next')
                    if next_url:
                        request.session['pending_2fa_next'] = next_url
                    request.session.modified = True
                    messages.info(request, _("Enter the 6-digit authentication code to finish signing in."))
                    return redirect('two_factor_challenge')

                next_url = request.POST.get('next') or request.GET.get('next')
                return finalize_login(request, user, ip_address, next_url=next_url)
            else:
                # Signal failed login to middleware
                request._login_failed = True
                
                # Track failed login attempt
                try:
                    attempted_user = User.objects.get(username=email)
                    session = UserSession.objects.filter(user=attempted_user).last()
                    
                    if attempted_user:
                        # Create a session if none exists
                        if not session:
                            session = UserSession.objects.create(
                                user=attempted_user,
                                session_key=request.session.session_key or request.session.create(),
                                ip_address=ip_address,
                                user_agent=request.META.get('HTTP_USER_AGENT', '')
                            )
                        
                        # Now create the activity record with the session
                        UserActivity.objects.create(
                            user=attempted_user,
                            session=session,
                            action='failed_login',
                            url=request.path,
                            details={
                                'reason': 'invalid_credentials',
                                'ip_address': ip_address,
                                'browser': request.META.get('HTTP_USER_AGENT', ''),
                                'timestamp': timezone.now().isoformat(),
                                'is_active': attempted_user.is_active
                            }
                        )
                except User.DoesNotExist:
                    # User doesn't exist, still log the attempt for security monitoring
                    pass

                messages.error(request, _("Invalid email or password."))
                logger.warning(f"Failed login attempt for email: {email} from IP: {ip_address}")

    else:
        form = LoginForm()

    # Add CSRF token to the session if not present
    if not request.session.get('csrf_token'):
        request.session['csrf_token'] = get_token(request)

    # Check if CAPTCHA is required (set by middleware)
    require_captcha = getattr(request, 'require_captcha', False)

    return render(request, 'app_cabinet/login.html', {
        'form': form,
        'require_captcha': require_captcha,
        'recaptcha_site_key': getattr(settings, 'RECAPTCHA_PUBLIC_KEY', ''),
        'page_title': _("Login")
    })


def two_factor_challenge(request):
    pending_user_id = request.session.get('pending_2fa_user_id')

    if request.user.is_authenticated and not pending_user_id:
        return redirect('personal_cabinet')

    if not pending_user_id:
        messages.error(request, _("Your 2FA session has expired. Please log in again."))
        return redirect('login')

    try:
        user = User.objects.get(pk=pending_user_id)
    except User.DoesNotExist:
        clear_pending_two_factor_session(request)
        messages.error(request, _("Unable to locate your account. Please try again."))
        return redirect('login')

    cabinet_user, _created = CabinetUser.objects.get_or_create(user=user)
    if not (cabinet_user.two_factor_enabled and cabinet_user.two_factor_secret):
        clear_pending_two_factor_session(request)
        return redirect('login')

    created_ts = request.session.get('pending_2fa_created')
    if created_ts and timezone.now().timestamp() - created_ts > 600:
        clear_pending_two_factor_session(request)
        messages.error(request, _("The verification code has expired. Please start again."))
        return redirect('login')

    if request.method == 'POST':
        code = request.POST.get('code')
        is_valid, used_backup = verify_two_factor_code(
            cabinet_user,
            code,
            allow_backup=True,
            mark_backup_used=True
        )
        if is_valid:
            next_url = request.session.get('pending_2fa_next')
            ip_address = request.session.get('pending_2fa_ip') or request.META.get('REMOTE_ADDR')
            clear_pending_two_factor_session(request)
            cabinet_user.two_factor_last_used = timezone.now()
            cabinet_user.save(update_fields=['two_factor_last_used'])
            method = 'backup_code' if used_backup else 'totp'
            return finalize_login(request, user, ip_address, next_url=next_url, two_factor_method=method)
        else:
            messages.error(request, _("Invalid authentication code. Please try again."))

    context = {
        'masked_identifier': user.email or user.username,
        'page_title': _("Two-Factor Verification")
    }
    return render(request, 'app_cabinet/two_factor_challenge.html', context)


def force_two_factor_enroll(request):
    pending_user_id = request.session.get('pending_force_2fa_user_id')
    if not pending_user_id:
        messages.error(request, _("Your session expired. Please log in again."))
        return redirect('login')

    try:
        user = User.objects.get(pk=pending_user_id)
    except User.DoesNotExist:
        clear_pending_force_two_factor_session(request)
        messages.error(request, _("Unable to locate your account. Please log in again."))
        return redirect('login')

    cabinet_user, _created = CabinetUser.objects.get_or_create(user=user)
    if not cabinet_user.force_two_factor:
        clear_pending_force_two_factor_session(request)
        return redirect('login')

    if cabinet_user.two_factor_enabled and cabinet_user.two_factor_secret:
        clear_pending_force_two_factor_session(request)
        request.session['pending_2fa_user_id'] = user.id
        request.session['pending_2fa_ip'] = request.session.get('pending_force_2fa_ip')
        request.session['pending_2fa_created'] = timezone.now().timestamp()
        messages.info(request, _("Two-factor authentication is already configured. Please enter your code."))
        return redirect('two_factor_challenge')

    if not cabinet_user.two_factor_temp_secret or (
        cabinet_user.two_factor_temp_created_at and
        timezone.now() - cabinet_user.two_factor_temp_created_at > TWO_FACTOR_TEMP_VALIDITY
    ):
        cabinet_user.two_factor_temp_secret = pyotp.random_base32()
        cabinet_user.two_factor_temp_created_at = timezone.now()
        cabinet_user.save(update_fields=['two_factor_temp_secret', 'two_factor_temp_created_at'])

    identifier = user.email or user.username
    issuer = getattr(settings, 'TWO_FACTOR_ISSUER', 'SecBoard')
    provisioning_uri = pyotp.TOTP(cabinet_user.two_factor_temp_secret).provisioning_uri(
        name=identifier,
        issuer_name=issuer
    )

    if request.method == 'POST':
        code = request.POST.get('code')
        is_valid, _unused = verify_two_factor_code(
            cabinet_user,
            code,
            secret=cabinet_user.two_factor_temp_secret
        )
        if is_valid:
            plain_codes, hashed_codes = generate_backup_codes()
            cabinet_user.two_factor_secret = cabinet_user.two_factor_temp_secret
            cabinet_user.two_factor_enabled = True
            cabinet_user.two_factor_confirmed_at = timezone.now()
            cabinet_user.two_factor_temp_secret = ''
            cabinet_user.two_factor_temp_created_at = None
            cabinet_user.two_factor_backup_codes = hashed_codes
            cabinet_user.save(update_fields=[
                'two_factor_secret',
                'two_factor_enabled',
                'two_factor_confirmed_at',
                'two_factor_temp_secret',
                'two_factor_temp_created_at',
                'two_factor_backup_codes'
            ])

            UserActivity.objects.create(
                user=user,
                action='update_profile',
                details={
                    'action': 'two_factor_forced_setup_completed',
                    'timestamp': timezone.now().isoformat()
                }
            )

            next_url = request.session.get('pending_force_2fa_next')
            ip_address = request.session.get('pending_force_2fa_ip') or request.META.get('REMOTE_ADDR')
            clear_pending_force_two_factor_session(request)
            messages.success(request, _("Two-factor authentication has been enabled."))
            return finalize_login(request, user, ip_address, next_url=next_url, two_factor_method='forced_setup')
        else:
            messages.error(request, _("Invalid authentication code. Please try again."))

    context = {
        'secret': cabinet_user.two_factor_temp_secret,
        'otpauth_uri': provisioning_uri,
        'masked_identifier': identifier,
        'page_title': _("Set up Two-Factor Authentication"),
    }
    return render(request, 'app_cabinet/force_two_factor_enroll.html', context)

def logout_view(request):
    if request.user.is_authenticated:
        track_user_logout(request.user)
    auth_logout(request)
    messages.success(request, _("You have been successfully logged out."))
    return redirect('index')


def logout(request):
    if 'cabinet_user_id' in request.session:
        del request.session['cabinet_user_id']
    return redirect('first_login')

def password_reset_request(request):
    """
    Handle password reset requests.
    Sends an email with a reset link if the email exists in the system.
    """
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            user_email = form.cleaned_data["email"]
            associated_user = User.objects.get(email=user_email)
            
            # Get the active mail account
            mail_account = MailAccount.objects.filter(is_active=True).first()
            if not mail_account:
                messages.error(request, _("Email server not configured. Please contact the administrator."))
                return redirect("login")
            
            # Create token for the one-time link
            token = default_token_generator.make_token(associated_user)
            uid = urlsafe_base64_encode(force_bytes(associated_user.pk))
            
            current_site = get_current_site(request)
            mail_subject = _("Password Reset for SecBoard")
            
            # Render email template
            email_template_name = "app_cabinet/password_reset_email.html"
            context = {
                "user": associated_user,
                "domain": current_site.domain,
                "uid": uid,
                "token": token,
                "protocol": "https" if request.is_secure() else "http",
            }
            
            # Get HTML and text versions from the template
            email_html = render_to_string(email_template_name, context)
            
            # Get the text part from the template
            text_content = ""
            capturing = False  # Initialize capturing flag
            for line in email_html.split('\n'):
                if line.strip().startswith('{% block text_body %}'):
                    capturing = True
                    continue
                elif capturing and line.strip().startswith('{% endblock %}'):
                    break
                elif capturing:
                    text_content += line + '\n'
            
            # If no text content was extracted from template, create a simple version
            if not text_content:
                text_content = f"""
Hello,

We received a request to reset your password. Please follow the link below to set a new password:
{context['protocol']}://{context['domain']}{reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})}

If you did not request a password reset, please ignore this email.

Regards,
SecBoard Team
"""
            
            try:
                # Create email with both HTML and text parts
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                from smtplib import SMTP, SMTP_SSL
                import ssl
                
                # Create the email
                msg = MIMEMultipart('alternative')
                msg['Subject'] = mail_subject
                msg['From'] = mail_account.username
                msg['To'] = user_email
                
                # Add plain text part
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
                
                # Add HTML part
                html_part = MIMEText(email_html, 'html')
                msg.attach(html_part)
                
                # Connect to the SMTP server
                if mail_account.server.use_ssl:
                    # Create SSL context
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    
                    # Connect with SSL
                    smtp = SMTP_SSL(
                        host=mail_account.server.smtp_host,
                        port=mail_account.server.smtp_port,
                        context=context
                    )
                else:
                    # Connect without SSL
                    smtp = SMTP(
                        host=mail_account.server.smtp_host,
                        port=mail_account.server.smtp_port
                    )
                    
                    # Use TLS if needed
                    if mail_account.server.use_tls:
                        smtp.starttls()
                
                # Login and send
                smtp.login(mail_account.username, mail_account.password)
                smtp.send_message(msg)
                smtp.quit()
                
                # Log the email
                Email.objects.create(
                    account=mail_account,
                    message_id=f"<{uuid.uuid4()}@{mail_account.server.smtp_host}>",
                    from_email=mail_account.username,
                    to_email=user_email,
                    subject=mail_subject,
                    body=email_html,
                    date=timezone.now(),
                    email_type='outgoing'
                )
                
                logger.info(f"Password reset email sent to {user_email}")
                return redirect("password_reset_done")
            except Exception as e:
                logger.error(f"Failed to send password reset email: {str(e)}")
                messages.error(request, _("Failed to send email. Please try again later or contact support."))
    else:
        form = PasswordResetRequestForm()
    
    return render(request, "app_cabinet/password_reset_form.html", {"form": form})


def password_reset_done(request):
    """
    Display a page informing the user that a password reset email has been sent.
    """
    return render(request, "app_cabinet/password_reset_done.html")


def password_reset_confirm(request, uidb64, token):
    """
    Verify the reset link and allow the user to set a new password.
    """
    try:
        uid = force_bytes(urlsafe_base64_decode(uidb64)).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        validlink = True

        if request.method == 'POST':
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key

            form = SetPasswordForm(request.POST)
            form.user = user  # Pass user to form for validation

            if form.is_valid():
                form.save(user)

                # Get IP and User-Agent
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                ip_address = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
                user_agent = request.META.get('HTTP_USER_AGENT', '')

                # Create session record
                session = UserSession.objects.create(
                    user=user,
                    session_key=session_key,
                    ip_address=ip_address,
                    user_agent=user_agent
                )

                # Clear password reset flags
                password_reset_flags = UserActivity.objects.filter(
                    user=user,
                    action='password_reset',
                    details__force_change=True,
                    details__processed__isnull=True
                )

                for flag in password_reset_flags:
                    flag.details['processed'] = True
                    flag.save()

                # Track password change activity
                UserActivity.objects.create(
                    user=user,
                    session=session,
                    action='password_change',
                    url=request.path,
                    details={
                        'source': 'reset',
                        'ip_address': ip_address,
                        'browser': user_agent,
                        'timestamp': timezone.now().isoformat()
                    }
                )

                messages.success(request, _("Your password has been set. You may now log in with your new password."))
                return redirect("password_reset_complete")
        else:
            form = SetPasswordForm()
            form.user = user
    else:
        validlink = False
        form = None

    return render(
        request,
        "app_cabinet/password_reset_confirm.html",
        {"form": form, "validlink": validlink}
    )



def password_reset_complete(request):
    """
    Display a page confirming the user's password has been successfully reset.
    """
    return render(request, "app_cabinet/password_reset_complete.html")


@login_required
def password_change(request):
    """
    Allow authenticated users to change their password.
    This view is used for both regular password changes and
    forced password changes after login.
    """
    if request.method == 'POST':
        form = SetPasswordForm(request.POST)
        form.user = request.user  # Pass user to form for validation
        
        if form.is_valid():
            form.save(request.user)
            
            # Clear any password reset flags
            password_reset_flags = UserActivity.objects.filter(
                user=request.user,
                action='password_reset',
                details__force_change=True,
                details__processed__isnull=True
            )
            
            for flag in password_reset_flags:
                flag.details['processed'] = True
                flag.save()
            
            # Track password change activity
            UserActivity.objects.create(
                user=request.user,
                action='password_change',
                details={
                    'source': 'self_change',
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            # Invalidate all other sessions if configured
            if getattr(settings, 'SESSION_INVALIDATE_ON_PASSWORD_CHANGE', True):
                # Get all sessions for this user and delete them except current one
                current_session_key = request.session.session_key
                from django.contrib.sessions.models import Session
                
                user_sessions = Session.objects.filter(expire_date__gte=timezone.now())
                invalidated_count = 0
                
                for session in user_sessions:
                    try:
                        session_data = session.get_decoded()
                        if (session_data.get('_auth_user_id') == str(request.user.id) and 
                            session.session_key != current_session_key):
                            session.delete()
                            invalidated_count += 1
                    except Exception as e:
                        logger.error(f"Error invalidating session: {e}")
                
                logger.info(f"Invalidated {invalidated_count} sessions for user {request.user.username} after password change")
            
            # Update session to avoid re-login issues
            update_session_auth_hash(request, request.user)
            
            messages.success(request, _("Your password was successfully changed."))
            return redirect('index')
    else:
        form = SetPasswordForm()
        form.user = request.user  # Pass user to form for validation
    
    # Check if this is a forced password change
    is_forced = UserActivity.objects.filter(
        user=request.user,
        action='password_reset',
        details__force_change=True,
        details__processed__isnull=True
    ).exists()
    
    return render(request, "app_cabinet/password_change.html", {
        "form": form,
        "is_forced": is_forced,
        "page_title": _("Change Password")
    })

@login_required
@require_permission('users', 'view')
def get_user_data(request, pk):
    """
    Get user data for the edit user form
    """
    try:
        cabinet_user = get_object_or_404(CabinetUser, pk=pk)
        
        # Check if company_id is provided in the request (for filtering groups)
        override_company_id = request.GET.get('company_id')
        
        # Format dates for the frontend
        start_date = None
        end_date = None
        start_time = None
        end_time = None
        
        if cabinet_user.start_date:
            start_date = cabinet_user.start_date.strftime('%Y-%m-%d')
            start_time = cabinet_user.start_date.strftime('%H:%M')
            
        if cabinet_user.end_date:
            end_date = cabinet_user.end_date.strftime('%Y-%m-%d')
            end_time = cabinet_user.end_date.strftime('%H:%M')
        
        # Prepare user data
        user_data = {
            'user_id': cabinet_user.user.id,  # Add the actual User ID
            'first_name': cabinet_user.user.first_name,
            'last_name': cabinet_user.user.last_name,
            'email': cabinet_user.user.email,
            'phone': cabinet_user.phone,
            'telegram_chat_id': cabinet_user.telegram_chat_id or '',
            'is_active': cabinet_user.user.is_active,
            'is_staff': cabinet_user.user.is_staff,
            'color': cabinet_user.color,
            'company_id': cabinet_user.company.id if cabinet_user.company else None,
            'department_id': cabinet_user.department.id if cabinet_user.department else None,
            'position_id': cabinet_user.position.id if cabinet_user.position else None,
            'position_parent_position_id': cabinet_user.position.parent_position_id if cabinet_user.position else None,
            'start_date': start_date,
            'end_date': end_date,
            'start_time': start_time,
            'end_time': end_time,
            'force_two_factor': cabinet_user.force_two_factor,
            'is_ad_synced': getattr(cabinet_user, 'is_ad_synced', False),
            'ad_extra_attributes': getattr(cabinet_user, 'ad_extra_attributes', None) or {},
            'ad_account_disabled': (getattr(cabinet_user, 'ad_extra_attributes', None) or {}).get('_ad_account_disabled', False),
        }
        if getattr(cabinet_user, 'is_ad_synced', False) and cabinet_user.company:
            try:
                from django.core.exceptions import ObjectDoesNotExist
                ad_conn = cabinet_user.company.ad_connection
                user_data['ad_connection_display'] = f"{ad_conn.name} ({ad_conn.server_url})"
            except ObjectDoesNotExist:
                user_data['ad_connection_display'] = ''
            except Exception:
                user_data['ad_connection_display'] = ''
        else:
            user_data['ad_connection_display'] = ''
        
        # Add avatar URL if exists
        if cabinet_user.avatar:
            user_data['avatar_url'] = cabinet_user.avatar.url
            
        # Get user's current group IDs
        user_group_ids = set(cabinet_user.user.groups.values_list('id', flat=True))
        
        # Determine current language
        current_lang = getattr(request, 'LANGUAGE_CODE', 'ua')
        if current_lang not in ['ua', 'ru', 'en']:
            current_lang = 'ua'
        
        # Prepare groups for the user
        cabinet_groups = []
        other_groups = []
        
        # Import needed models
        from django.db.models import Q
        from .models import CabinetGroup
        from app_conf.models import Company
        
        # Handle company-specific filtering
        cabinet_group_filter = Q(company__isnull=True)  # Always include global cabinet groups
        
        if override_company_id:
            # Use the company ID from the request for filtering
            try:
                selected_company = Company.objects.get(id=override_company_id)
                cabinet_group_filter |= Q(company=selected_company)
            except Company.DoesNotExist:
                pass
        elif cabinet_user.company:
            # Use the user's company for filtering
            cabinet_group_filter |= Q(company=cabinet_user.company)
            
        cabinet_group_objs = CabinetGroup.objects.filter(cabinet_group_filter)
        cabinet_group_ids = set(cabinet_group_objs.values_list('group_id', flat=True))
        
        # Process all groups
        for group in Group.objects.all():
            try:
                # Check if group has cabinet details and matches company filter
                has_cabinet_details = hasattr(group, 'cabinet_details') and group.cabinet_details is not None
                is_matching_cabinet_group = has_cabinet_details and group.id in cabinet_group_ids
                
                if is_matching_cabinet_group:
                    # This is a relevant cabinet group; name/description via model (default en, others via DB)
                    name = group.cabinet_details.get_name(current_lang) or ''
                    description = group.cabinet_details.get_description(current_lang) or ''
                    cabinet_groups.append({
                        'id': group.id,
                        'name': name,
                        'description': description,
                        'color': group.cabinet_details.color,
                        'selected': group.id in user_group_ids
                    })
                elif not has_cabinet_details:
                    # This is a regular group
                    other_groups.append({
                        'id': group.id,
                        'name': group.name,
                        'description': '',  # Regular groups don't have descriptions in the model
                        'selected': group.id in user_group_ids
                    })
            except Exception as e:
                logger.error(f"Error processing group {group.id}: {str(e)}")
                # Add to other groups as a fallback
                other_groups.append({
                    'id': group.id,
                    'name': group.name,
                    'description': '',
                    'selected': group.id in user_group_ids
                })
                
        user_data['cabinet_groups'] = cabinet_groups
        user_data['other_groups'] = other_groups
        user_data['role_ids'] = list(cabinet_user.roles.values_list('id', flat=True))
        # All cabinet group IDs the user has (for pre-checking Additional Cabinet Groups from role companies)
        user_data['user_cabinet_group_ids'] = list(
            cabinet_user.user.groups.filter(
                id__in=CabinetGroup.objects.values_list('group_id', flat=True)
            ).values_list('id', flat=True)
        )

        # Platform roles available for this user (global or scoped to user's company)
        from .models import PlatformRole
        ids_global = PlatformRole.objects.filter(is_active=True).annotate(c=Count('companies')).filter(c=0).values_list('id', flat=True)
        if cabinet_user.company:
            ids_scoped = PlatformRole.objects.filter(is_active=True, companies=cabinet_user.company).values_list('id', flat=True).distinct()
            role_ids_available = set(ids_global) | set(ids_scoped)
        else:
            role_ids_available = set(ids_global)
        roles_qs = PlatformRole.objects.filter(id__in=role_ids_available).prefetch_related(
            'companies',
            Prefetch('groups', queryset=Group.objects.select_related('cabinet_details', 'cabinet_details__company'))
        ).order_by('order', 'name')
        platform_roles_list = []
        for r in roles_qs:
            role_groups = []
            for g in r.groups.all():
                details = getattr(g, 'cabinet_details', None)
                if details:
                    role_groups.append({
                        'id': g.id,
                        'name': details.get_name() or g.name,
                        'description': (details.get_description() or '').strip(),
                        'company_name': details.company.name if details.company else '',
                        'color': details.color or '#000000',
                    })
                else:
                    role_groups.append({
                        'id': g.id,
                        'name': g.name,
                        'description': '',
                        'company_name': '',
                        'color': '#000000',
                    })
            platform_roles_list.append({
                'id': r.id,
                'name': r.name,
                'color': r.color or '#6c757d',
                'description': (r.description or '').strip(),
                'company_names': [c.name for c in r.companies.all()],
                'company_ids': list(r.companies.values_list('id', flat=True)),
                'groups': role_groups,
            })
        user_data['platform_roles'] = platform_roles_list

        return JsonResponse({
            'status': 'success',
            'data': user_data
        })
        
    except Exception as e:
        logger.error(f"Error in get_user_data: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@require_permission('users', 'edit')
@require_http_methods(["POST"])
def refresh_user_from_ad(request, pk):
    """Refresh AD-synced user data (groups, etc.) from Active Directory without user login."""
    cabinet_user = get_object_or_404(CabinetUser, pk=pk)
    from .backends import refresh_cabinet_user_from_ad
    ok, err = refresh_cabinet_user_from_ad(cabinet_user)
    if ok:
        return JsonResponse({"status": "success", "message": _("Data refreshed from AD.")})
    # Return 200 so the client can show the message in the success handler (avoids "Bad Request" in logs)
    return JsonResponse({"status": "error", "message": err or _("Refresh failed")})


@require_permission('users', 'edit')
def update_user(request, pk):
    """
    Update user information
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
        
    try:
        cabinet_user = get_object_or_404(CabinetUser, pk=pk)
        user = cabinet_user.user
        
        # Process form data
        form_data = {}
        for key, value in request.POST.items():
            if key not in ['csrfmiddlewaretoken', 'cabinet_groups[]', 'other_groups[]', 'parent_position', 'roles[]', 'apply_groups_from_roles', 'additional_cabinet_groups[]']:
                form_data[key] = value
                
        # Handle Cabinet Groups
        cabinet_group_ids = request.POST.getlist('cabinet_groups[]')
        
        # Handle Other Groups - Don't modify these, they're view-only
        # Get the user's current other groups (non-cabinet groups)
        from .models import CabinetGroup, PlatformRole
        cabinet_group_ids_in_db = list(CabinetGroup.objects.values_list('group_id', flat=True))
        
        other_group_ids = []
        for group in user.groups.all():
            if group.id not in cabinet_group_ids_in_db:
                other_group_ids.append(str(group.id))
        
        # Update user groups: start with cabinet + other
        all_group_ids = list(cabinet_group_ids) + other_group_ids
        
        # Create form with data
        form = CabinetUserEditForm(form_data, request.FILES, instance=cabinet_user)
        
        if form.is_valid():
            # Save cabinet user
            form.save()
            
            # Update platform roles
            role_ids = request.POST.getlist('roles[]')
            if role_ids is not None:
                cabinet_user.roles.set(PlatformRole.objects.filter(id__in=role_ids))
            
            # By default apply access groups from selected roles (when checkbox is on)
            if request.POST.get('apply_groups_from_roles') == 'on':
                for role in cabinet_user.roles.all():
                    for grp in role.groups.all():
                        all_group_ids.append(str(grp.id))
            # Additional cabinet groups (from companies of selected roles, or any cabinet group if roles are global)
            additional_group_ids = request.POST.getlist('additional_cabinet_groups[]')
            if additional_group_ids and cabinet_user.roles.exists():
                role_company_ids = set(
                    cabinet_user.roles.values_list('companies__id', flat=True).distinct()
                )
                role_company_ids.discard(None)
                for gid in additional_group_ids:
                    try:
                        if role_company_ids:
                            cg = CabinetGroup.objects.get(
                                group_id=gid, company_id__in=role_company_ids
                            )
                        else:
                            # Global roles (no companies): allow any cabinet group selected as additional
                            cg = CabinetGroup.objects.filter(group_id=gid).first()
                        if cg:
                            all_group_ids.append(str(cg.group_id))
                    except (CabinetGroup.DoesNotExist, ValueError):
                        pass
            all_group_ids = list(dict.fromkeys(all_group_ids))  # unique, preserve order
            
            # Update user groups
            user.groups.clear()
            for group_id in all_group_ids:
                try:
                    group = Group.objects.get(pk=group_id)
                    user.groups.add(group)
                except Group.DoesNotExist:
                    pass
            
            # Handle password change if needed
            if 'password1' in form_data and form_data.get('password1'):
                if form_data.get('password1') == form_data.get('password2'):
                    user.set_password(form_data.get('password1'))
                    
                    # Log password reset if needed
                    if form_data.get('force_password_change') == 'on':
                        UserActivity.objects.create(
                            user=user,
                            action='password_reset',
                            details={
                                'force_change': True,
                                'reset_by': request.user.username,
                                'timestamp': timezone.now().isoformat()
                            }
                        )
                else:
                    return JsonResponse({
                        'status': 'error',
                        'errors': {'password2': [_('Passwords do not match')]}
                    })
            
            # Handle quiz assignments
            assigned_quiz_ids = request.POST.getlist('assigned_quizzes[]')
            logger.info(f"Received quiz assignments for user {cabinet_user.id}: {assigned_quiz_ids}")
            if assigned_quiz_ids:
                try:
                    from app_study.models import Quiz
                    
                    # Clear existing individual quiz assignments for this user
                    existing_quizzes = Quiz.objects.filter(cabinet_users=cabinet_user)
                    logger.info(f"Clearing {existing_quizzes.count()} existing quiz assignments for user {cabinet_user.id}")
                    for quiz in existing_quizzes:
                        quiz.cabinet_users.remove(cabinet_user)
                    
                    # Add new quiz assignments
                    for quiz_id in assigned_quiz_ids:
                        try:
                            quiz = Quiz.objects.get(id=quiz_id)
                            quiz.cabinet_users.add(cabinet_user)
                            logger.info(f"Successfully assigned quiz {quiz_id} ({quiz.title}) to user {cabinet_user.id}")
                        except Quiz.DoesNotExist:
                            logger.warning(f"Quiz with ID {quiz_id} not found")
                            
                except Exception as e:
                    logger.error(f"Error handling quiz assignments: {str(e)}")
            else:
                # If no quizzes selected, clear all individual assignments
                logger.info(f"No quizzes selected for user {cabinet_user.id}, clearing all assignments")
                try:
                    from app_study.models import Quiz
                    existing_quizzes = Quiz.objects.filter(cabinet_users=cabinet_user)
                    logger.info(f"Clearing {existing_quizzes.count()} quiz assignments for user {cabinet_user.id}")
                    for quiz in existing_quizzes:
                        quiz.cabinet_users.remove(cabinet_user)
                        logger.info(f"Removed quiz {quiz.id} ({quiz.title}) from user {cabinet_user.id}")
                except Exception as e:
                    logger.error(f"Error clearing quiz assignments: {str(e)}")
            
            # Save the User model
            user.save()
            
            return JsonResponse({
                'status': 'success',
                'message': _('User updated successfully')
            })
        else:
            return JsonResponse({
                'status': 'error',
                'errors': form.errors
            })
            
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_permission('org_chart', 'view')
def org_chart_view(request):
    """
    View for displaying organization chart
    """
    from .permissions import get_user_accessible_companies
    
    # Get companies that the user has access to
    companies = get_user_accessible_companies(request.user)
    
    context = {
        'companies': companies,
        'page_title': _('Organization Chart'),
        'page_description': _('Interactive organization chart view')
    }
    
    return render(request, 'app_cabinet/org_chart.html', context)



