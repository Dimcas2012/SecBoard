#  SecBoard\SecBoard\app_keycert\view.py

import json
import logging
import time
import pytz
from celery.app.control import Control
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import dsa, rsa, ec
from dateutil.parser import parser
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.translation import get_language
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.dateparse import parse_date, parse_datetime
from datetime import datetime, timedelta
from django_celery_beat.models import PeriodicTask
from redis import Redis
from .models import KeyCertificates, Typekeycert, Revocationstatus, AccessKeyCert, GenKeycertInfo, KeycertOwner, \
    Reminder, KeyCertHistory, KeyCertGuide, KeyCertGuideTranslation
from app_conf.models import Company, Country
from .tasks import schedule_reminder, cancel_reminder, send_reminder_email
from .pagination_utils import normalize_keycert_table_length

def get_active_cabinet_users():
    """Return active Cabinet users (user.is_active and is_active_employee) for Owner dropdown."""
    try:
        from app_cabinet.models import CabinetUser
        return list(
            CabinetUser.objects
            .filter(user__is_active=True)
            .select_related('user', 'department', 'position')
            .order_by('user__last_name', 'user__first_name', 'user__email')
        )
    except Exception:
        return []


def resolve_owner_from_value(owner_value):
    """
    Resolve owner from form value. Owner is Cabinet users only (KeycertOwner removed from API).
    Value must be 'c-{cabinet_user_id}'. Returns (KeycertOwner or None, error_message or None).
    KeycertOwner is still used internally for storage (created/synced from CabinetUser).
    """
    if not owner_value:
        return None, None
    raw = str(owner_value).strip()
    if not raw.startswith('c-'):
        return None, "Owner must be a Cabinet user"
    try:
        from app_cabinet.models import CabinetUser
        cabinet_id = int(raw[2:])
        cu = CabinetUser.objects.select_related('user', 'department', 'position').get(pk=cabinet_id)
        if not cu.user.is_active or not cu.is_active_employee():
            return None, "Selected Cabinet user is not active"
        name = cu.user.get_full_name() or cu.user.username or ''
        department = (cu.department.name if cu.department else '') or (cu.position.name if cu.position else '') or ''
        email = cu.user.email or ''
        owner, _ = KeycertOwner.objects.get_or_create(
            email=email,
            defaults={
                'name': name,
                'department': department,
                'phone': cu.phone or '',
                'notes': '',
            }
        )
        # Keep in sync if already existed
        if owner.name != name or owner.department != department or owner.phone != (cu.phone or ''):
            owner.name = name
            owner.department = department
            owner.phone = cu.phone or ''
            owner.save(update_fields=['name', 'department', 'phone'])
        return owner, None
    except CabinetUser.DoesNotExist:
        return None, "Invalid Cabinet user"
    except ValueError:
        return None, "Invalid owner value"


@login_required
def get_keycert_owner_options(request):
    """Return active cabinet users only for the Select Owner modal (Quick search + Department/Position). Owner can only be a Cabinet user."""
    try:
        from app_cabinet.models import CabinetUser
        company_id = request.GET.get('company_id')
        qs = CabinetUser.objects.filter(user__is_active=True).select_related('user', 'department', 'position')
        if company_id:
            qs = qs.filter(company_id=company_id)
        cabinet_users = []
        for cu in qs:
            if not cu.is_active_employee():
                continue
            dept_name = (cu.department.name if cu.department else '') or ''
            pos_name = (cu.position.name if cu.position else '') or ''
            cabinet_users.append({
                'type': 'c',
                'id': cu.id,
                'user_id': cu.user_id,
                'full_name': cu.user.get_full_name() or cu.user.username or '',
                'username': cu.user.username or '',
                'email': cu.user.email or '',
                'department_id': cu.department_id,
                'position_id': cu.position_id,
                'department_name': dept_name,
                'position_name': pos_name,
            })
        return JsonResponse({
            'success': True,
            'cabinet_users': cabinet_users,
        })
    except Exception as e:
        logger.exception("get_keycert_owner_options failed")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


import hashlib
# Try to import jks, but make it optional - will check in the functions that need it
JKS_AVAILABLE = False
# Only import the required modules that don't have dependencies
from OpenSSL import crypto
from cryptography.x509.oid import ExtensionOID
import tempfile
from django.conf import settings
try:
    from SecBoard.celery import app
except ImportError:
    try:
        from SecBoard.celery import app
    except ImportError:
        app = None
        print("Warning: Celery not available")
import os
from app_access.api_view import check_api_status, direct_service_status



logger = logging.getLogger(__name__)



logger.debug("This is a debug message")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")


def get_server_time(request):
    user_timezone = request.session.get('user_timezone', 'Europe/Kiev')
    server_time = timezone.now().astimezone(pytz.timezone(user_timezone))
    formatted_time = server_time.strftime('%Y-%m-%d %H:%M:%S %z')
    return JsonResponse({'server_time': formatted_time})

@login_required
def keys_cert(request):
    user_groups = request.user.groups.all()
    access_key_cert = AccessKeyCert.objects.filter(group__in=user_groups, has_access=True)
    allowed_companies = Company.objects.filter(access_keycert__in=access_key_cert).distinct()
    key_certs = KeyCertificates.objects.all()


    key_cert_types = list(Typekeycert.objects.filter(is_active=True).order_by('name', 'code'))
    for t in key_cert_types:
        t.name_uk = t.get_name_by_language('uk')
        t.name_en = t.get_name_by_language('en')
        t.name_ru = t.get_name_by_language('ru')
        t.description_uk = t.get_description_by_language('uk')
        t.description_en = t.get_description_by_language('en')
        t.description_ru = t.get_description_by_language('ru')
    revocation_statuses = list(Revocationstatus.objects.filter(is_active=True).order_by('name', 'code'))
    for s in revocation_statuses:
        s.name_uk = s.get_name_by_language('uk')
        s.name_en = s.get_name_by_language('en')
        s.name_ru = s.get_name_by_language('ru')
        s.description_uk = s.get_description_by_language('uk')
        s.description_en = s.get_description_by_language('en')
        s.description_ru = s.get_description_by_language('ru')
    cabinet_users = [cu for cu in get_active_cabinet_users() if cu.is_active_employee()]
    context = {
        'key_cert_types': key_cert_types,
        'revocation_statuses': revocation_statuses,
        'companies': allowed_companies,
        'cabinet_users': cabinet_users,
        'request': request,
        'LANGUAGE_CODE': get_language(),
        'show_link': AccessKeyCert.objects.filter(group__in=user_groups, show_link=True).exists(),
        'key_certs': key_certs,
        'can_edit': AccessKeyCert.objects.filter(group__in=user_groups, can_edit=True).exists(),
    }
    return render(request, 'app_keycert/keys_cert.html', context)


@login_required
def keycert_guide(request):
    """Return JSON { content: html } for the Keys/Certificates guide (localized)."""
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = KeyCertGuide.objects.first()
    if guide:
        if country:
            trans = KeyCertGuideTranslation.objects.filter(keycert_guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = KeyCertGuideTranslation.objects.filter(keycert_guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def keycert_guide_translate(request):
    """API for AI translation of Key/Cert guide content (admin)."""
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


@login_required
def get_key_certs(request):
    try:
        # Safely get and convert parameters with proper error handling
        try:
            draw = int(request.GET.get('draw', 1))
            start = int(request.GET.get('start', 0))
            length = normalize_keycert_table_length(request.GET.get('length', 25))
            search_value = request.GET.get('search_value', '').strip()
        except (TypeError, ValueError) as e:
            logger.error(f"Parameter conversion error: {str(e)}")
            return JsonResponse({
                'error': 'Invalid parameters',
                'draw': 1,
                'recordsTotal': 0,
                'recordsFiltered': 0,
                'data': []
            }, status=400)

        # Get user permissions
        user_groups = request.user.groups.all()
        access_key_cert = AccessKeyCert.objects.filter(group__in=user_groups, has_access=True)
        allowed_companies = Company.objects.filter(access_keycert__in=access_key_cert).distinct()

        # Base queryset with select_related and prefetch_related for better performance
        key_certs = KeyCertificates.objects.filter(company__in=allowed_companies).select_related(
            'company',
            'type_key_sert',
            'revocation_status',
            'owner',
            'owner_cabinet_user',
            'added_by',
            'updated_by',
            'actualized_by',
            'general_info'
        ).prefetch_related(
            'reminders',
            'history'
        )

        # Apply filters with error handling
        try:
            # Company filter
            company_filter = request.GET.get('company')
            if company_filter and company_filter.isdigit():
                key_certs = key_certs.filter(company_id=company_filter)

            # Type filter
            type_filter = request.GET.get('type')
            if type_filter and type_filter.isdigit():
                key_certs = key_certs.filter(type_key_sert_id=type_filter)

            # Revocation status filter
            revocation_status_filter = request.GET.get('revocation_status')
            if revocation_status_filter and revocation_status_filter.isdigit():
                key_certs = key_certs.filter(revocation_status_id=revocation_status_filter)

            # Date range filter
            date_range = request.GET.get('date_range', '')
            if date_range:
                try:
                    start_date, end_date = date_range.split(' - ')
                    start_date = datetime.strptime(start_date.strip(), '%d/%m/%Y').date()
                    end_date = datetime.strptime(end_date.strip(), '%d/%m/%Y').date()
                    key_certs = key_certs.filter(expiry_date__range=[start_date, end_date])
                except (ValueError, IndexError) as e:
                    logger.warning(f"Date range parsing error: {str(e)}")

            # Search functionality
            if search_value:
                key_certs = key_certs.filter(
                    Q(key_cert_num__icontains=search_value) |
                    Q(cert_hash__icontains=search_value) |
                    Q(company__name__icontains=search_value) |
                    Q(type_key_sert__name__icontains=search_value) |
                    Q(type_key_sert__code__icontains=search_value) |
                    Q(purpose__icontains=search_value) |
                    Q(location__icontains=search_value) |
                    Q(owner__name__icontains=search_value) |
                    Q(access_control__icontains=search_value) |
                    Q(revocation_status__name__icontains=search_value) |
                    Q(revocation_status__code__icontains=search_value) |
                    Q(notes__icontains=search_value)
                )

        except Exception as filter_error:
            logger.error(f"Error applying filters: {str(filter_error)}", exc_info=True)
            return JsonResponse({
                'error': 'Error applying filters',
                'draw': draw,
                'recordsTotal': 0,
                'recordsFiltered': 0,
                'data': []
            }, status=400)

        # Get total counts
        total_records = key_certs.count()
        records_filtered = total_records

        # Apply sorting
        try:
            order_column = request.GET.get('order[0][column]')
            order_dir = request.GET.get('order[0][dir]')

            column_index_to_field = {
                '0': 'key_cert_num',
                '1': 'company__name',
                '3': 'type_key_sert__name',
                '4': 'purpose',
                '5': 'location',
                '6': 'access_control',
                '7': 'expiry_date',
                '10': 'revocation_status__name',
                '11': 'owner__name',
                '12': 'notes',
                '13': 'created_at',
                '14': 'updated_at'
            }

            if order_column and order_dir and order_column in column_index_to_field:
                order_field = column_index_to_field[order_column]
                if order_dir == 'desc':
                    order_field = f'-{order_field}'
                key_certs = key_certs.order_by(order_field)
            else:
                key_certs = key_certs.order_by('expiry_date')

        except Exception as sort_error:
            logger.error(f"Error applying sorting: {str(sort_error)}", exc_info=True)
            key_certs = key_certs.order_by('expiry_date')

        # Apply pagination
        try:
            key_certs = key_certs[start:start + length]
        except Exception as page_error:
            logger.error(f"Error applying pagination: {str(page_error)}", exc_info=True)
            key_certs = key_certs[:25]  # Default to first 25 records on error

        # Prepare response data
        data = []
        current_time = timezone.now()

        for key_cert in key_certs:
            try:
                # Process owner data
                owner_data = {
                    'name': '',
                    'department': '',
                    'email': '',
                    'phone': '',
                    'notes': ''
                }
                if key_cert.owner:
                    owner = key_cert.owner
                    owner_data.update({
                        'name': owner.name,
                        'department': owner.department,
                        'email': owner.email,
                        'phone': owner.phone,
                        'notes': owner.notes
                    })

                # Get general info
                general_info = key_cert.general_info if hasattr(key_cert, 'general_info') else None

                # Enhanced reminder processing
                reminder_info = {
                    'enable_reminder': key_cert.enable_reminder,
                    'reminder_type': None,
                    'reminder_days': None,
                    'reminder_date': None,
                    'reminder_sent': False,
                    'reminder_cancelled': False,
                    'sent_at': None,
                    'cancelled_at': None,
                    'celery_task_id': None,
                    'status': 'Not Set',
                    'next_reminder_date': None,
                    'previous_reminders': []
                }

                # Get active reminder
                active_reminder = Reminder.objects.filter(
                    key_certificate=key_cert,
                    is_cancelled=False
                ).order_by('-created_at').first()

                if active_reminder:
                    reminder_status = active_reminder.get_status_with_datetime()
                    reminder_info.update({
                        'reminder_type': active_reminder.reminder_type,
                        'reminder_days': active_reminder.reminder_days,
                        'reminder_date': (active_reminder.reminder_date.strftime('%Y-%m-%d %H:%M:%S')
                                        if active_reminder.reminder_date else None),
                        'reminder_sent': active_reminder.is_sent,
                        'reminder_cancelled': active_reminder.is_cancelled,
                        'sent_at': (active_reminder.sent_at.strftime('%Y-%m-%d %H:%M:%S')
                                  if active_reminder.sent_at else None),
                        'cancelled_at': (active_reminder.cancelled_at.strftime('%Y-%m-%d %H:%M:%S')
                                       if active_reminder.cancelled_at else None),
                        'celery_task_id': active_reminder.celery_task_id,
                        'status': reminder_status['status'],
                        'status_timestamp': reminder_status['timestamp']
                    })

                    # Calculate next reminder date
                    if not active_reminder.is_sent and not active_reminder.is_cancelled:
                        next_reminder_date = active_reminder.get_next_reminder_date()
                        if next_reminder_date:
                            reminder_info['next_reminder_date'] = next_reminder_date.strftime('%Y-%m-%d')

                # Get previous reminders
                previous_reminders = Reminder.objects.filter(
                    key_certificate=key_cert,
                    is_sent=True
                ).exclude(
                    id=active_reminder.id if active_reminder else None
                ).order_by('-sent_at')[:5]

                reminder_info['previous_reminders'] = [{
                    'sent_at': reminder.sent_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'reminder_type': reminder.reminder_type,
                    'reminder_days': reminder.reminder_days,
                    'status': reminder.get_status()
                } for reminder in previous_reminders]

                # Get history information
                history = key_cert.history.order_by('-timestamp').first()
                history_info = {
                    'last_action': history.action if history else None,
                    'last_action_by': history.action_by.get_full_name() if history and history.action_by else None,
                    'last_action_time': history.timestamp.isoformat() if history else None
                }

                # Compile the data
                data.append({
                    'id': key_cert.id,
                    'key_cert_num': key_cert.key_cert_num,
                    'cert_hash': key_cert.cert_hash,
                    'company': key_cert.company.name,
                    'general_info': {
                        'organization_name': general_info.organization_name if general_info else '',
                        'date_created': general_info.date_created.isoformat() if general_info and general_info.date_created else '',
                        'last_updated': general_info.last_updated.isoformat() if general_info and general_info.last_updated else '',
                        'version': general_info.version if general_info else '',
                        'maintainer_name': general_info.maintainer_name if general_info else '',
                        'maintainer_contact': general_info.maintainer_contact if general_info else '',
                        'cert_hash': key_cert.cert_hash,
                    },
                    'type_key_sert': {
                        'uk': key_cert.type_key_sert.get_name_by_language('uk') if key_cert.type_key_sert else '',
                        'en': key_cert.type_key_sert.get_name_by_language('en') if key_cert.type_key_sert else '',
                        'ru': key_cert.type_key_sert.get_name_by_language('ru') if key_cert.type_key_sert else '',
                    },
                    'type_key_sert_color': key_cert.type_key_sert.color if key_cert.type_key_sert else '#FFFFFF',
                    'purpose': key_cert.purpose,
                    'location': key_cert.location,
                    'owner': owner_data,
                    'access_control': key_cert.access_control,
                    'expiry_date': key_cert.expiry_date.isoformat() if key_cert.expiry_date else '',
                    'enable_reminder': reminder_info['enable_reminder'],
                    'reminder_type': reminder_info['reminder_type'],
                    'reminder_days': reminder_info['reminder_days'],
                    'reminder_date': reminder_info['reminder_date'],
                    'reminder_sent': reminder_info['reminder_sent'],
                    'reminder_cancelled': reminder_info['reminder_cancelled'],
                    'sent_at': reminder_info['sent_at'],
                    'cancelled_at': reminder_info['cancelled_at'],
                    'celery_task_id': reminder_info['celery_task_id'],
                    'reminder_status': reminder_info['status'],
                    'reminder_status_timestamp': reminder_info.get('status_timestamp'),
                    'next_reminder_date': reminder_info['next_reminder_date'],
                    'previous_reminders': reminder_info['previous_reminders'],
                    'revocation_status': {
                        'uk': key_cert.revocation_status.get_name_by_language('uk') if key_cert.revocation_status else '',
                        'en': key_cert.revocation_status.get_name_by_language('en') if key_cert.revocation_status else '',
                        'ru': key_cert.revocation_status.get_name_by_language('ru') if key_cert.revocation_status else '',
                    },
                    'revocation_status_color': key_cert.revocation_status.color if key_cert.revocation_status else '#FFFFFF',
                    'notes': key_cert.notes,
                    'created_at': key_cert.created_at.isoformat() if key_cert.created_at else '',
                    'updated_at': key_cert.updated_at.isoformat() if key_cert.updated_at else '',
                    'created_by': key_cert.added_by.get_full_name() if key_cert.added_by else '',
                    'updated_by': key_cert.updated_by.get_full_name() if key_cert.updated_by else '',
                    'history': history_info
                    ,
                    'actual': {
                        'has_actualization': bool(key_cert.actualization_date),
                        'date': (
                            timezone.localtime(key_cert.actualization_date).strftime('%Y-%m-%d %H:%M:%S')
                            if key_cert.actualization_date else None
                        ),
                        'user': (
                            key_cert.actualized_by.get_full_name() or key_cert.actualized_by.username
                            if key_cert.actualized_by else None
                        ),
                        'is_owner': bool(
                            key_cert.owner_cabinet_user and key_cert.owner_cabinet_user.user_id == request.user.id
                        )
                    }
                })

            except Exception as row_error:
                logger.error(f"Error processing row {key_cert.id}: {str(row_error)}", exc_info=True)
                continue

        response = {
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': records_filtered,
            'data': data,
        }
        return JsonResponse(response)

    except Exception as e:
        logger.error(f"Unexpected error in get_key_certs: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': str(e),
            'draw': draw if 'draw' in locals() else 1,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': []
        }, status=500)


@login_required
def get_key_cert(request, key_cert_id):
    key_cert = get_object_or_404(KeyCertificates, id=key_cert_id)
    general_info = key_cert.general_info if hasattr(key_cert, 'general_info') else None
    # Серіалізуємо об'єкт KeycertOwner вручну
    owner_data = None
    if key_cert.owner:
        owner_data = {
            'id': key_cert.owner.id,
            'name': key_cert.owner.name,
            'department': key_cert.owner.department,
            'email': key_cert.owner.email,
            'phone': key_cert.owner.phone,
            'notes': key_cert.owner.notes
        }
    data = {
        'id': key_cert.id,
        'key_cert_num': key_cert.key_cert_num,
        'company': key_cert.company.id,
        'type_key_sert': key_cert.type_key_sert.id if key_cert.type_key_sert else None,
        'purpose': key_cert.purpose,
        'location': key_cert.location,
        'owner': owner_data,
        'access_control': key_cert.access_control,
        'expiry_date': key_cert.expiry_date.isoformat() if key_cert.expiry_date else None,
        'revocation_status': key_cert.revocation_status.id if key_cert.revocation_status else None,
        'notes': key_cert.notes,
        'general_info': {
            'organization_name': general_info.organization_name if general_info else '',
            'date_created': general_info.date_created.isoformat() if general_info and general_info.date_created else '',
            'last_updated': general_info.last_updated.isoformat() if general_info and general_info.last_updated else '',
            'version': general_info.version if general_info else '',
            'maintainer_name': general_info.maintainer_name if general_info else '',
            'maintainer_contact': general_info.maintainer_contact if general_info else '',
        }
    }
    return JsonResponse(data)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def add_key_cert(request):
    try:
        # Authentication check
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=403)

        # Get form data
        data = request.POST
        key_cert_num = data.get('key_cert_num')
        logger.info(f'Adding new key/cert with num: {key_cert_num}')

        # Basic validation
        if not key_cert_num:
            return JsonResponse({
                'success': False,
                'error': "Key/Certificate ID is required"
            }, status=400)

        # Check for duplicate key_cert_num
        if KeyCertificates.objects.filter(key_cert_num__iexact=key_cert_num).exists():
            return JsonResponse({
                'success': False,
                'error': f"Key/Certificate ID '{key_cert_num}' already exists. Please use a different ID."
            }, status=400)

        # Permission check
        user_groups = request.user.groups.all()
        if not AccessKeyCert.objects.filter(group__in=user_groups, can_edit=True).exists():
            return JsonResponse({
                'success': False,
                'error': 'Permission denied'
            }, status=403)

        # Get current time
        current_time = timezone.now()

        # Validate required fields
        required_fields = ['company', 'key_cert_num', 'type_key_sert', 'expiry_date']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f"{field} is required"
                }, status=400)

        # Parse and validate expiry date
        expiry_date = parse_date(data['expiry_date'])
        if not expiry_date:
            return JsonResponse({
                'success': False,
                'error': "Invalid expiry date format"
            }, status=400)

        # Handle owner field (Owner is Cabinet users only: value is c-{cabinet_user_id})
        owner = None
        owner_cabinet_user_id = None
        if data.get('owner'):
            owner, err = resolve_owner_from_value(data['owner'])
            if err:
                return JsonResponse({
                    'success': False,
                    'error': err
                }, status=400)
            raw = str(data['owner']).strip()
            if raw.startswith('c-'):
                try:
                    owner_cabinet_user_id = int(raw[2:])
                except ValueError:
                    pass

        # Start transaction
        with transaction.atomic():
            # Create KeyCertificates instance
            key_cert = KeyCertificates(
                company=Company.objects.get(id=data['company']),
                key_cert_num=key_cert_num,
                cert_hash=data.get('cert_hash', ''),
                type_key_sert=Typekeycert.objects.get(id=data['type_key_sert']) if data.get('type_key_sert') else None,
                purpose=data.get('purpose', ''),
                location=data.get('location', ''),
                owner=owner,
                owner_cabinet_user_id=owner_cabinet_user_id,
                access_control=data.get('access_control', ''),
                expiry_date=expiry_date,
                revocation_status=Revocationstatus.objects.get(id=data['revocation_status']) if data.get(
                    'revocation_status') else None,
                notes=data.get('notes', ''),
                added_by=request.user,
                updated_by=request.user,
                enable_reminder=data.get('enable_reminder') == 'true'
            )

            # Save the key_cert instance
            key_cert.save()

            # Create GenKeycertInfo
            date_created = None
            if data.get('date_created'):
                date_created = parse_datetime(data['date_created'])
                if date_created:
                    date_created = timezone.make_aware(date_created)

            gen_keycert_info_data = {
                'key_certificate': key_cert,
                'organization_name': data.get('organization_name', ''),
                'date_created': date_created or current_time,
                'version': data.get('version', ''),
                'maintainer_name': data.get('maintainer_name', ''),
                'maintainer_contact': data.get('maintainer_contact', '')
            }

            # Handle last_updated field
            if data.get('last_updated'):
                last_updated = parse_datetime(data['last_updated'])
                if last_updated:
                    gen_keycert_info_data['last_updated'] = timezone.make_aware(last_updated)
            else:
                gen_keycert_info_data['last_updated'] = current_time

            # Create general info record
            GenKeycertInfo.objects.create(**gen_keycert_info_data)

            # Create history entry
            KeyCertHistory.objects.create(
                key_certificate=key_cert,
                action="created",
                action_by=request.user,
                details=f"Certificate {key_cert.key_cert_num} created"
            )

            # Handle reminder settings
            enable_reminder = data.get('enable_reminder') == 'true'
            if enable_reminder:
                reminder_type = data.get('reminder_type', 'days')
                reminder_days = None
                reminder_date = None

                if reminder_type == 'days':
                    try:
                        reminder_days = int(data.get('reminder_days', '30'))
                    except ValueError:
                        reminder_days = 30  # Default value

                    # Calculate reminder date based on days before expiry
                    reminder_date = expiry_date - timedelta(days=reminder_days)

                    if reminder_date <= timezone.now().date():
                        return JsonResponse({
                            'success': False,
                            'error': f"Cannot set reminder {reminder_days} days before expiry as it would be in the past."
                        }, status=400)

                elif reminder_type == 'date':
                    reminder_date = parse_datetime(data.get('reminder_date'))
                    if not reminder_date:
                        return JsonResponse({
                            'success': False,
                            'error': "Invalid reminder date format"
                        }, status=400)

                    reminder_date = timezone.make_aware(reminder_date)
                    if reminder_date.date() <= timezone.now().date():
                        return JsonResponse({
                            'success': False,
                            'error': "Cannot set reminder date in the past"
                        }, status=400)

                # Create reminder record
                reminder = Reminder.objects.create(
                    key_certificate=key_cert,
                    reminder_type=reminder_type,
                    reminder_days=reminder_days,
                    reminder_date=reminder_date if reminder_type == 'date' else None,
                    is_sent=False,
                    is_cancelled=False
                )

                # Schedule the reminder
                schedule_reminder(
                    key_cert=key_cert,
                    reminder_type=reminder_type,
                    reminder_days=reminder_days,
                    reminder_date=reminder_date
                )

        # Return success response
        return JsonResponse({
            'success': True,
            'message': 'Key/Certificate added successfully',
            'id': key_cert.id
        })

    except Exception as e:
        logger.error(f"Error adding key/certificate: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
@require_http_methods(["POST"])
def edit_key_cert(request, key_cert_id):
    start_time = time.time()
    logger.info(f"Starting edit_key_cert for id {key_cert_id}")

    try:
        with transaction.atomic():
            key_cert = get_object_or_404(KeyCertificates, id=key_cert_id)
            data = request.POST
            now = timezone.now().date()

            logger.info(f"Received data for editing key_cert_id {key_cert_id}")

            # Validate key_cert_num uniqueness
            new_key_cert_num = data['key_cert_num']
            if KeyCertificates.objects.filter(
                    key_cert_num__iexact=new_key_cert_num
            ).exclude(id=key_cert_id).exists():
                logger.warning(f"Duplicate key_cert_num attempted: {new_key_cert_num}")
                return JsonResponse({
                    'success': False,
                    'error': f"Key/Certificate ID '{new_key_cert_num}' already exists. Please use a different ID."
                }, status=400)

            # Process expiry date and reminder settings
            try:
                expiry_date = parse_date(data['expiry_date'])
                if not expiry_date:
                    logger.error("Invalid expiry date format provided")
                    return JsonResponse({
                        'success': False,
                        'error': "Invalid expiry date format"
                    }, status=400)

                # Validate reminder settings
                enable_reminder = data.get('enable_reminder') == 'true'
                if enable_reminder:
                    reminder_type = data.get('reminder_type')
                    reminder_validation = validate_reminder_settings(
                        reminder_type,
                        data.get('reminder_days'),
                        data.get('reminder_date'),
                        expiry_date,
                        now
                    )
                    if not reminder_validation['success']:
                        return JsonResponse({
                            'success': False,
                            'error': reminder_validation['error']
                        }, status=400)

                    reminder_days = reminder_validation.get('reminder_days')
                    reminder_date = reminder_validation.get('reminder_date')

            except Exception as e:
                logger.error(f"Error validating dates: {str(e)}", exc_info=True)
                return JsonResponse({
                    'success': False,
                    'error': f"Date validation error: {str(e)}"
                }, status=400)

            # Update main fields
            try:
                update_key_cert_fields(key_cert, data, request.user, expiry_date)
            except Exception as e:
                logger.error(f"Error updating main fields: {str(e)}", exc_info=True)
                return JsonResponse({
                    'success': False,
                    'error': f"Error updating certificate fields: {str(e)}"
                }, status=400)

            # Handle reminder settings
            try:
                key_cert.enable_reminder = enable_reminder
                if not enable_reminder:
                    logger.info(f"Disabling reminders for key_cert_id {key_cert_id}")
                    cancel_reminder(key_cert)
                    Reminder.objects.filter(key_certificate=key_cert).delete()
                else:
                    handle_reminder = handle_reminder_settings(
                        key_cert,
                        reminder_type,
                        reminder_days,
                        reminder_date
                    )
                    if not handle_reminder['success']:
                        return JsonResponse({
                            'success': False,
                            'error': handle_reminder['error']
                        }, status=400)

            except Exception as e:
                logger.error(f"Error handling reminders: {str(e)}", exc_info=True)
                return JsonResponse({
                    'success': False,
                    'error': f"Error handling reminder settings: {str(e)}"
                }, status=400)

            # Save certificate
            try:
                key_cert.save()
            except Exception as e:
                logger.error(f"Error saving certificate: {str(e)}", exc_info=True)
                return JsonResponse({
                    'success': False,
                    'error': f"Error saving certificate: {str(e)}"
                }, status=400)

            # Update general information
            try:
                update_general_info(key_cert, data)
            except Exception as e:
                logger.error(f"Error updating general info: {str(e)}", exc_info=True)
                return JsonResponse({
                    'success': False,
                    'error': f"Error updating general information: {str(e)}"
                }, status=400)

            # Record success
            execution_time = time.time() - start_time
            logger.info(f"Edit key_cert operation completed in {execution_time:.2f} seconds")

            # Create history entry
            KeyCertHistory.objects.create(
                key_certificate=key_cert,
                action="updated",
                action_by=request.user,
                details=f"Certificate {key_cert.key_cert_num} updated successfully"
            )

            return JsonResponse({
                'success': True,
                'message': 'Key/Certificate updated successfully'
            })

    except Exception as e:
        logger.error(f"Unexpected error in edit_key_cert: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }, status=400)

def validate_reminder_settings(reminder_type, reminder_days, reminder_date_str, expiry_date, now):
    """Validate reminder settings and return processed values"""
    try:
        if reminder_type == 'days':
            if not reminder_days or not str(reminder_days).isdigit():
                return {
                    'success': False,
                    'error': "Please enter a valid number of days for the reminder"
                }

            reminder_days = int(reminder_days)
            reminder_date = expiry_date - timezone.timedelta(days=reminder_days)

            if reminder_date <= now:
                return {
                    'success': False,
                    'error': f"Cannot set reminder {reminder_days} days before expiry as it would be in the past."
                }

            return {
                'success': True,
                'reminder_days': reminder_days,
                'reminder_date': None
            }

        elif reminder_type == 'date':
            if not reminder_date_str:
                return {
                    'success': False,
                    'error': "Please specify a reminder date"
                }

            reminder_date = parse_datetime(reminder_date_str)
            if not reminder_date:
                return {
                    'success': False,
                    'error': "Invalid reminder date format"
                }

            if reminder_date.date() <= now:
                return {
                    'success': False,
                    'error': "Cannot set reminder date in the past"
                }

            if reminder_date.date() >= expiry_date:
                return {
                    'success': False,
                    'error': "Reminder date must be before the expiry date"
                }

            return {
                'success': True,
                'reminder_days': None,
                'reminder_date': reminder_date
            }

        return {
            'success': False,
            'error': "Please select a valid reminder type (days or specific date)"
        }

    except Exception as e:
        logger.error(f"Error validating reminder settings: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f"Error validating reminder settings: {str(e)}"
        }

def update_key_cert_fields(key_cert, data, user, expiry_date):
    """Update main fields of the key certificate"""
    key_cert.key_cert_num = data['key_cert_num']
    key_cert.company = Company.objects.get(id=data['company'])
    key_cert.type_key_sert = Typekeycert.objects.get(id=data['type_key_sert']) if data.get('type_key_sert') else None
    key_cert.purpose = data.get('purpose', '')
    key_cert.location = data.get('location', '')
    key_cert.expiry_date = expiry_date

    # Handle owner (Owner is Cabinet users only: value is c-{cabinet_user_id})
    owner_value = data.get('owner')
    owner = None
    owner_cabinet_user_id = None
    if owner_value:
        owner, err = resolve_owner_from_value(owner_value)
        if err:
            raise ValueError(err)
        raw = str(owner_value).strip()
        if raw.startswith('c-'):
            try:
                owner_cabinet_user_id = int(raw[2:])
            except ValueError:
                pass
    key_cert.owner = owner
    key_cert.owner_cabinet_user_id = owner_cabinet_user_id

    key_cert.access_control = data.get('access_control', '')
    key_cert.revocation_status = (
        Revocationstatus.objects.get(id=data['revocation_status'])
        if data.get('revocation_status') else None
    )
    key_cert.notes = data.get('notes', '')
    key_cert.updated_by = user


def handle_reminder_settings(key_cert, reminder_type, reminder_days, reminder_date):
    """Handle reminder settings updates"""
    try:
        existing_reminder = Reminder.objects.filter(key_certificate=key_cert).first()

        if reminder_type == 'days':
            settings_changed = (
                    not existing_reminder or
                    existing_reminder.reminder_type != 'days' or
                    existing_reminder.reminder_days != reminder_days
            )
        else:  # date
            settings_changed = (
                    not existing_reminder or
                    existing_reminder.reminder_type != 'date' or
                    existing_reminder.reminder_date != reminder_date
            )

        if settings_changed:
            if existing_reminder:
                cancel_reminder(key_cert)
                existing_reminder.delete()

            reminder_result = schedule_reminder(
                key_cert,
                reminder_type,
                reminder_days=reminder_days,
                reminder_date=reminder_date
            )

            if not reminder_result['success']:
                logger.error(f"Failed to schedule reminder: {reminder_result.get('message')}")
                return {
                    'success': False,
                    'error': reminder_result.get('message', 'Failed to schedule reminder')
                }

        return {'success': True}

    except Exception as e:
        logger.error(f"Error handling reminder settings: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f"Error handling reminder settings: {str(e)}"
        }


def update_general_info(key_cert, data):
    """Update general information for the key certificate"""
    general_info, created = GenKeycertInfo.objects.get_or_create(
        key_certificate=key_cert
    )

    general_info.organization_name = data.get('organization_name', '')
    general_info.date_created = timezone.make_aware(parse_datetime(data.get('date_created')))
    general_info.last_updated = (
        timezone.make_aware(parse_datetime(data.get('last_updated')))
        if data.get('last_updated')
        else timezone.now()
    )
    general_info.version = data.get('version', '')
    general_info.maintainer_name = data.get('maintainer_name', '')
    general_info.maintainer_contact = data.get('maintainer_contact', '')
    general_info.save()

@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def delete_key_cert(request, id):
    try:
        # Перевірка доступу
        user_groups = request.user.groups.all()
        if not AccessKeyCert.objects.filter(group__in=user_groups, can_edit=True).exists():
            return JsonResponse({
                'success': False,
                'error': 'Permission denied'
            }, status=403)

        key_cert = get_object_or_404(KeyCertificates, id=id)

        # Збереження інформації про запис для логування
        key_cert_info = f"ID: {key_cert.id}, Key/Cert Number: {key_cert.key_cert_num}"

        # Створення запису в історії перед видаленням
        KeyCertHistory.objects.create(
            key_certificate=key_cert,
            action="deleted",
            action_by=request.user,
            details=f"Certificate {key_cert.key_cert_num} was deleted by {request.user.get_full_name()}"
        )

        # Скасування нагадування перед видаленням
        if key_cert.enable_reminder:
            try:
                cancel_reminder(key_cert)
            except Exception as e:
                logger.warning(f"Error cancelling reminder for {key_cert_info}: {str(e)}")

        # Видалення запису
        key_cert.delete()

        # Логування успішного видалення
        logger.info(f"Key/Certificate deleted successfully. {key_cert_info}")

        return JsonResponse({
            'success': True,
            'message': 'Key/Certificate deleted successfully'
        })

    except KeyCertificates.DoesNotExist:
        logger.warning(f"Attempt to delete non-existent Key/Certificate with ID: {id}")
        return JsonResponse({
            'success': False,
            'error': 'Key/Certificate not found'
        }, status=404)

    except Exception as e:
        logger.error(f"Error deleting Key/Certificate with ID {id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@require_POST
def add_keycert_owner(request):
    try:
        name = request.POST['name']
        department = request.POST['department']
        email = request.POST['email']
        phone = request.POST['phone']
        notes = request.POST.get('notes', '')

        owner = KeycertOwner.objects.create(
            name=name,
            department=department,
            email=email,
            phone=phone,
            notes=notes
        )

        return JsonResponse({
            'success': True,
            'owner_id': owner.id,
            'owner_name': owner.name,
            'owner_department': owner.department,
            'owner_email': owner.email
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
def delete_keycert_owner(request):
    try:
        owner_id = request.POST['owner_id']
        owner = KeycertOwner.objects.get(id=owner_id)
        owner.delete()
        return JsonResponse({'success': True})
    except KeycertOwner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Owner not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
def get_keycert_owner(request):
    try:
        owner_id = request.GET.get('owner_id')
        owner = KeycertOwner.objects.get(id=owner_id)
        return JsonResponse({
            'success': True,
            'owner': {
                'id': owner.id,
                'name': owner.name,
                'department': owner.department,
                'email': owner.email,
                'phone': owner.phone,
                'notes': owner.notes
            }
        })
    except KeycertOwner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Owner not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_http_methods(["POST"])
def edit_keycert_owner(request):
    try:
        owner_id = request.POST.get('id')
        owner = KeycertOwner.objects.get(id=owner_id)
        owner.name = request.POST.get('name')
        owner.department = request.POST.get('department')
        owner.email = request.POST.get('email')
        owner.phone = request.POST.get('phone')
        owner.notes = request.POST.get('notes')
        owner.save()
        return JsonResponse({
            'success': True,
            'owner': {
                'id': owner.id,
                'name': owner.name,
                'department': owner.department,
                'owner_email': owner.email
            }
        })
    except KeycertOwner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Owner not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@csrf_exempt
@login_required
def parse_certificate(request):
    try:
        file = request.FILES.get('file')
        password = request.POST.get('password', None)
        
        if not file:
            return JsonResponse({
                'success': False,
                'error': 'No file provided'
            }, status=400)

        file_content = file.read()
        file_extension = file.name.split('.')[-1].lower()

        # Check file type based on extension or content 
        if file_extension in ['pem', 'crt', 'cer', 'cert']:
            result = parse_pem(file_content)
        elif file_extension == 'der':
            result = parse_der(file_content)
        elif file_extension == 'jks':
            if not JKS_AVAILABLE:
                return JsonResponse({
                    'success': False,
                    'error': 'JKS files cannot be processed as the pyjks module is not installed. Please install it with "pip install pyjks".'
                }, status=400)
            result = parse_jks(file_content)
        elif file_extension in ['p12', 'pfx']:
            result = parse_pkcs12(file_content)
        elif file_extension in ['key', 'pub']:
            result = parse_key(file_content)
        else:
            # Try to auto-detect format if extension doesn't match
            try:
                result = parse_pem(file_content)
            except:
                try:
                    result = parse_der(file_content)
                except:
                    if JKS_AVAILABLE:
                        try:
                            result = parse_jks(file_content)
                        except:
                            try:
                                result = parse_pkcs12(file_content)
                            except:
                                try:
                                    result = parse_key(file_content)
                                except:
                                    return JsonResponse({
                                        'success': False,
                                        'error': 'Unable to determine file format'
                                    }, status=400)
                    else:
                        try:
                            result = parse_pkcs12(file_content)
                        except:
                            try:
                                result = parse_key(file_content)
                            except:
                                return JsonResponse({
                                    'success': False,
                                    'error': 'Unable to determine file format'
                                }, status=400)

        return result

    except Exception as e:
        logger.error(f"Error parsing certificate: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f"An unexpected error occurred: {str(e)}"
        }, status=500)

def parse_der(file_content):
    try:
        cert = x509.load_der_x509_certificate(file_content, default_backend())
        logger.info("Successfully parsed DER certificate")
        return process_x509_cert(cert)
    except Exception as e:
        logger.error(f"Error parsing DER certificate: {str(e)}")
        raise

def parse_jks(file_content):
    # Try to import jks only when needed
    global JKS_AVAILABLE
    try:
        import jks
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        JKS_AVAILABLE = True
    except ImportError:
        return JsonResponse({
            'success': False,
            'error': 'JKS files cannot be processed. The pyjks module is not available. Please install it with "pip install pyjks".'
        }, status=400)
        
    try:
        # Зберігаємо вміст у тимчасовий файл, бо jks потребує файл
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file_content)
            temp_file.flush()

            # Спробуємо відкрити без пароля
            try:
                ks = jks.KeyStore.load(temp_file.name, '')
            except:
                # Якщо не вдалося, повернемо помилку про необхідність пароля
                return JsonResponse({
                    'success': False,
                    'error': 'JKS file requires password'
                }, status=400)

            # Обробляємо перший сертифікат зі сховища
            for alias, cert in ks.certs.items():
                # Конвертуємо в x509
                x509_cert = x509.load_der_x509_certificate(cert.cert, default_backend())
                return process_x509_cert(x509_cert)

            # Якщо сертифікатів немає, спробуємо знайти ключі
            for alias, key_entry in ks.private_keys.items():
                # Конвертуємо в формат ключа
                return process_private_key(key_entry)

    except Exception as e:
        logger.error(f"Error parsing JKS: {str(e)}")
        return JsonResponse({'success': False, 'error': f'Error parsing JKS: {str(e)}'})


def parse_pkcs12(file_content):
    try:
        # Спробуємо відкрити без пароля
        try:
            p12 = crypto.load_pkcs12(file_content)
        except:
            return JsonResponse({
                'success': False,
                'error': 'PKCS12 file requires password'
            }, status=400)

        # Отримуємо сертифікат
        cert = p12.get_certificate()
        if cert:
            x509_cert = x509.load_der_x509_certificate(
                crypto.dump_certificate(crypto.FILETYPE_ASN1, cert),
                default_backend()
            )
            return process_x509_cert(x509_cert)

        # Якщо сертифіката немає, спробуємо отримати ключ
        pkey = p12.get_privatekey()
        if pkey:
            return process_private_key(pkey)

    except Exception as e:
        logger.error(f"Error parsing PKCS12: {str(e)}")
        return JsonResponse({'success': False, 'error': f'Error parsing PKCS12: {str(e)}'})


def process_x509_cert(cert):
    try:
        cert_hash = cert.fingerprint(hashes.SHA256()).hex()
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        serial_number = cert.serial_number
        not_valid_before = cert.not_valid_before_utc
        not_valid_after = cert.not_valid_after_utc

        # Додаткова інформація про сертифікат
        cert_info = {
            'type': 'Certificate',
            'subject': subject,
            'issuer': issuer,
            'serial_number': str(serial_number),
            'not_valid_before': not_valid_before.isoformat(),
            'not_valid_after': not_valid_after.isoformat(),
            'key_cert_num': str(serial_number),
            'cert_hash': cert_hash,
            'version': f'v{cert.version.value}',
            'organization_name': get_org_name(cert.subject) or get_org_name(cert.issuer),
            'maintainer_name': get_common_name(cert.subject),
            'maintainer_contact': get_email(cert.subject) or get_email(cert.issuer),
        }

        # Отримання додаткових полів з сертифіката, якщо вони є
        try:
            ext = cert.extensions
            for extension in ext:
                oid = extension.oid
                if oid == ExtensionOID.SUBJECT_KEY_IDENTIFIER:
                    cert_info['subject_key_id'] = extension.value.digest.hex()
                elif oid == ExtensionOID.AUTHORITY_KEY_IDENTIFIER:
                    if extension.value.key_identifier:
                        cert_info['authority_key_id'] = extension.value.key_identifier.hex()
        except Exception as ext_e:
            logger.warning(f"Error getting extensions: {str(ext_e)}")

        logger.info(f"Successfully processed certificate with SN: {serial_number}")
        return JsonResponse({'success': True, 'data': cert_info})

    except Exception as e:
        logger.error(f"Error processing certificate: {str(e)}")
        raise
def parse_pem(file_content):
    try:
        # Конвертуємо до текстового формату, якщо потрібно
        if isinstance(file_content, bytes):
            try:
                # Спочатку спробуємо декодувати як utf-8
                pem_text = file_content.decode('utf-8')
            except UnicodeDecodeError:
                # Якщо не вдалося, використовуємо latin1
                pem_text = file_content.decode('latin1')
        else:
            pem_text = file_content

        # Спочатку спробуємо знайти PEM заголовки
        is_cert = "-----BEGIN CERTIFICATE-----" in pem_text
        is_private_key = "-----BEGIN PRIVATE KEY-----" in pem_text or "-----BEGIN RSA PRIVATE KEY-----" in pem_text
        is_public_key = "-----BEGIN PUBLIC KEY-----" in pem_text

        logger.info(f"PEM content analysis: cert={is_cert}, private={is_private_key}, public={is_public_key}")

        if is_cert:
            try:
                cert = x509.load_pem_x509_certificate(
                    pem_text.encode('utf-8') if isinstance(pem_text, str) else pem_text,
                    default_backend()
                )
                logger.info("Successfully parsed as X.509 certificate")
                return process_x509_cert(cert)
            except Exception as e:
                logger.error(f"Failed to parse as certificate: {str(e)}")
                raise ValueError("Invalid certificate format")

        elif is_private_key:
            try:
                # Спробуємо різні формати приватного ключа
                try:
                    private_key = serialization.load_pem_private_key(
                        pem_text.encode('utf-8') if isinstance(pem_text, str) else pem_text,
                        password=None,
                        backend=default_backend()
                    )
                except ValueError:
                    # Якщо не вдалося, спробуємо як традиційний RSA ключ
                    private_key = serialization.load_pem_private_key(
                        pem_text.encode('utf-8') if isinstance(pem_text, str) else pem_text,
                        password=None,
                        backend=default_backend()
                    )
                logger.info("Successfully parsed as private key")
                return process_private_key(private_key)
            except Exception as e:
                logger.error(f"Failed to parse as private key: {str(e)}")
                raise ValueError("Invalid private key format")

        elif is_public_key:
            try:
                public_key = serialization.load_pem_public_key(
                    pem_text.encode('utf-8') if isinstance(pem_text, str) else pem_text,
                    backend=default_backend()
                )
                logger.info("Successfully parsed as public key")
                return process_public_key(public_key)
            except Exception as e:
                logger.error(f"Failed to parse as public key: {str(e)}")
                raise ValueError("Invalid public key format")

        # Якщо не знайдено відповідних заголовків
        logger.error("No valid PEM headers found")
        return JsonResponse({
            'success': False,
            'error': 'File does not contain valid PEM-encoded certificate or key'
        }, status=400)

    except Exception as e:
        logger.error(f"Error in parse_pem: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Could not parse the file as certificate or key: {str(e)}'
        }, status=400)

def process_private_key(private_key):
    try:
        # Отримуємо публічний ключ для обчислення хешу
        public_key = private_key.public_key()
        key_hash = hashlib.sha256(
            public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        ).hexdigest()

        # Визначаємо тип ключа
        if isinstance(private_key, rsa.RSAPrivateKey):
            key_algorithm = 'RSA'
            key_size = private_key.key_size
        elif isinstance(private_key, dsa.DSAPrivateKey):
            key_algorithm = 'DSA'
            key_size = private_key.key_size
        elif isinstance(private_key, ec.EllipticCurvePrivateKey):
            key_algorithm = 'EC'
            key_size = private_key.curve.key_size
        else:
            key_algorithm = 'Unknown'
            key_size = 0

        response_data = {
            'type': 'Private Key',
            'algorithm': key_algorithm,
            'key_size': key_size,
            'key_cert_num': f'PrivateKey-{key_algorithm}-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'organization_name': 'N/A for private key',
            'version': f'{key_algorithm} {key_size}-bit',
            'maintainer_name': 'Key Owner',
            'maintainer_contact': 'N/A',
            'cert_hash': key_hash,
            'not_valid_before': datetime.now().isoformat(),
            'not_valid_after': (datetime.now() + timedelta(days=365)).isoformat()
        }

        return JsonResponse({'success': True, 'data': response_data})
    except Exception as e:
        logger.error(f"Error processing private key: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error processing private key: {str(e)}'
        }, status=400)

def process_public_key(public_key):
    try:
        # Обчислюємо хеш публічного ключа
        key_hash = hashlib.sha256(
            public_key.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        ).hexdigest()

        # Визначаємо тип ключа
        if isinstance(public_key, rsa.RSAPublicKey):
            key_algorithm = 'RSA'
            key_size = public_key.key_size
        elif isinstance(public_key, dsa.DSAPublicKey):
            key_algorithm = 'DSA'
            key_size = public_key.key_size
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            key_algorithm = 'EC'
            key_size = public_key.curve.key_size
        else:
            key_algorithm = 'Unknown'
            key_size = 0

        response_data = {
            'type': 'Public Key',
            'algorithm': key_algorithm,
            'key_size': key_size,
            'key_cert_num': f'PublicKey-{key_algorithm}-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'organization_name': 'N/A for public key',
            'version': f'{key_algorithm} {key_size}-bit',
            'maintainer_name': 'Key Owner',
            'maintainer_contact': 'N/A',
            'cert_hash': key_hash,
            'not_valid_before': datetime.now().isoformat(),
            'not_valid_after': (datetime.now() + timedelta(days=365)).isoformat()
        }

        return JsonResponse({'success': True, 'data': response_data})
    except Exception as e:
        logger.error(f"Error processing public key: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error processing public key: {str(e)}'
        }, status=400)
def parse_key(key_content):
   try:
       # Спроба розпарсити як приватний ключ
       try:
           private_key = serialization.load_pem_private_key(
               key_content,
               password=None,
               backend=default_backend()
           )
           key_type = 'Private'
           # Обчислюємо хеш публічного ключа
           public_key = private_key.public_key()
           key_hash = hashlib.sha256(
               public_key.public_bytes(
                   encoding=serialization.Encoding.DER,
                   format=serialization.PublicFormat.SubjectPublicKeyInfo
               )
           ).hexdigest()
       except ValueError:
           try:
               # Якщо не вдалося, спробуємо як публічний ключ
               public_key = serialization.load_pem_public_key(
                   key_content,
                   backend=default_backend()
               )
               key_type = 'Public'
               key_hash = hashlib.sha256(
                   public_key.public_bytes(
                       encoding=serialization.Encoding.DER,
                       format=serialization.PublicFormat.SubjectPublicKeyInfo
                   )
               ).hexdigest()
           except ValueError:
               return JsonResponse({'success': False, 'error': 'Unsupported key format'})

       # Визначаємо тип та розмір ключа
       if isinstance(private_key, rsa.RSAPrivateKey) or isinstance(private_key, rsa.RSAPublicKey):
           key_algorithm = 'RSA'
           key_size = private_key.key_size
       elif isinstance(private_key, dsa.DSAPrivateKey) or isinstance(private_key, dsa.DSAPublicKey):
           key_algorithm = 'DSA'
           key_size = private_key.key_size
       elif isinstance(private_key, ec.EllipticCurvePrivateKey) or isinstance(private_key, ec.EllipticCurvePublicKey):
           key_algorithm = 'EC'
           key_size = private_key.curve.key_size
       else:
           return JsonResponse({'success': False, 'error': 'Unknown key type'})

       # Формуємо відповідь
       response_data = {
           'type': f'{key_type} Key',
           'algorithm': key_algorithm,
           'key_size': key_size,
           'key_cert_num': f'{key_type}{key_algorithm}Key-{datetime.now().strftime("%Y%m%d%H%M%S")}',
           'organization_name': 'N/A for keys',
           'version': 'N/A for keys',
           'maintainer_name': 'Key Owner',
           'maintainer_contact': 'N/A',
           'cert_hash': key_hash,  # Додаємо хеш
           'not_valid_before': datetime.now().isoformat(),  # Додаємо поточну дату
           'not_valid_after': (datetime.now() + timedelta(days=365)).isoformat()
       }

       return JsonResponse({'success': True, 'data': response_data})

   except Exception as e:
       logger.error(f"Error parsing key: {str(e)}", exc_info=True)
       return JsonResponse({
           'success': False,
           'error': f'Error parsing key: {str(e)}'
       }, status=400)


def get_org_name(subject):
    for attr in subject:
        if attr.oid == x509.NameOID.ORGANIZATION_NAME:
            return attr.value
    return ''


def get_common_name(subject):
    for attr in subject:
        if attr.oid == x509.NameOID.COMMON_NAME:
            return attr.value
    return ''


def get_email(subject):
    for attr in subject:
        if attr.oid == x509.NameOID.EMAIL_ADDRESS:
            return attr.value
    return ''


@require_http_methods(["POST"])
def send_reminder_now(request):
    try:
        key_cert_id = request.POST.get('id')
        if not key_cert_id:
            return JsonResponse({'success': False, 'error': "Key certificate ID is required"})

        logger.info(f"Manual reminder request for key_cert_id: {key_cert_id}")

        key_cert = KeyCertificates.objects.get(id=key_cert_id)
        request_time = timezone.now()

        # Create history entry for manual reminder request
        KeyCertHistory.objects.create(
            key_certificate=key_cert,
            action=KeyCertHistory.ACTION_MANUAL_REMINDER_REQUESTED,
            action_by=request.user,
            details=(
                f"Manual reminder request\n"
                f"Requested by: {request.user.get_full_name()}\n"
                f"Request time: {request_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Certificate: {key_cert.key_cert_num}\n"
                f"Days until expiry: {(key_cert.expiry_date - timezone.now().date()).days}\n"
                f"Intended recipient: {key_cert.owner.email if key_cert.owner else settings.DEFAULT_FROM_EMAIL}"
            )
        )

        # Get or create an active reminder
        reminder = Reminder.objects.filter(
            key_certificate_id=key_cert_id,
            is_sent=False,
            is_cancelled=False
        ).first()

        if not reminder:
            reminder = Reminder.objects.create(
                key_certificate=key_cert,
                reminder_type='days',
                reminder_days=0,  # Immediate reminder
                is_sent=False,
                is_cancelled=False
            )
            logger.info(f"Created new immediate reminder for key_cert_id: {key_cert_id}")

        # Apply the task and store its ID
        task = send_reminder_email.apply(args=[key_cert_id])
        reminder.celery_task_id = task.id
        reminder.save(update_fields=['celery_task_id'])

        # Wait for the result
        try:
            result = task.get(timeout=30)  # Add timeout to avoid hanging indefinitely
            
            # If result is None or not unpackable, handle it
            if not result:
                logger.warning(f"Task returned None for key_cert_id: {key_cert_id}")
                success = False
                message = "Task failed to return a valid result. Check server logs for details."
            else:
                try:
                    success, message = result
                except (TypeError, ValueError) as e:
                    logger.error(f"Error unpacking task result: {e}, Result: {result}")
                    success = False
                    message = f"Invalid task result format: {result}"
        except Exception as e:
            logger.error(f"Error getting task result: {e}")
            success = False
            message = f"Error waiting for task: {str(e)}"
            
        send_time = timezone.now()

        if success:
            # Create history entry for successful manual sending
            KeyCertHistory.objects.create(
                key_certificate=key_cert,
                action=KeyCertHistory.ACTION_MANUAL_REMINDER_SENT,
                action_by=request.user,
                details=(
                    f"Manual reminder sent successfully\n"
                    f"Sent by: {request.user.get_full_name()}\n"
                    f"Send time: {send_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Processing time: {(send_time - request_time).total_seconds():.2f} seconds\n"
                    f"Recipients: {key_cert.owner.email if key_cert.owner else settings.DEFAULT_FROM_EMAIL}\n"
                    f"Certificate details:\n"
                    f"- ID: {key_cert.key_cert_num}\n"
                    f"- Type: {key_cert.type_key_sert.get_name_by_language('en') if key_cert.type_key_sert else 'N/A'}\n"
                    f"- Expiry date: {key_cert.expiry_date.strftime('%Y-%m-%d')}\n"
                    f"- Days until expiry: {(key_cert.expiry_date - timezone.now().date()).days}\n"
                    f"Task ID: {task.id}"
                )
            )
            logger.info(f"Manual reminder sent successfully for key_cert_id: {key_cert_id}")
            return JsonResponse({'success': True, 'message': message})
        else:
            # Create history entry for failed manual sending
            KeyCertHistory.objects.create(
                key_certificate=key_cert,
                action=KeyCertHistory.ACTION_MANUAL_REMINDER_FAILED,
                action_by=request.user,
                details=(
                    f"Failed to send manual reminder\n"
                    f"Attempted by: {request.user.get_full_name()}\n"
                    f"Attempt time: {send_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Processing time: {(send_time - request_time).total_seconds():.2f} seconds\n"
                    f"Error message: {message}\n"
                    f"Certificate details:\n"
                    f"- ID: {key_cert.key_cert_num}\n"
                    f"- Intended recipient: {key_cert.owner.email if key_cert.owner else settings.DEFAULT_FROM_EMAIL}\n"
                    f"Task ID: {task.id}"
                )
            )
            logger.warning(f"Failed to send manual reminder for key_cert_id: {key_cert_id}. Error: {message}")
            return JsonResponse({'success': False, 'error': message})

    except KeyCertificates.DoesNotExist:
        error_message = f"Key certificate with ID {key_cert_id} not found"
        logger.error(error_message)
        return JsonResponse({'success': False, 'error': error_message}, status=404)
    except Exception as e:
        error_message = f"Error in send_reminder_now: {str(e)}"
        logger.error(error_message, exc_info=True)
        return JsonResponse({'success': False, 'error': error_message}, status=500)





@require_http_methods(["GET"])
def get_key_cert_history(request, key_cert_id):
    try:
        history = KeyCertHistory.objects.filter(key_certificate_id=key_cert_id).order_by('-timestamp')
        data = []
        for entry in history:
            data.append({
                'timestamp': entry.timestamp.isoformat(),
                'action': entry.action,
                'action_by': entry.action_by.get_full_name() if entry.action_by else 'System',
                'details': entry.details,
            })
        return JsonResponse({'success': True, 'history': data})
    except Exception as e:
        logger.error(f"Error getting key/certificate history: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def actualize_key_cert(request, key_cert_id):
    try:
        key_cert = get_object_or_404(KeyCertificates, id=key_cert_id)

        user_groups = request.user.groups.all()
        access_key_cert = AccessKeyCert.objects.filter(group__in=user_groups, has_access=True)
        allowed_companies = Company.objects.filter(access_keycert__in=access_key_cert).distinct()
        if key_cert.company not in allowed_companies:
            return JsonResponse({'status': 'error', 'message': 'You do not have access to this record'}, status=403)

        if not key_cert.owner_cabinet_user or key_cert.owner_cabinet_user.user_id != request.user.id:
            return JsonResponse({
                'status': 'error',
                'message': 'Only the owner can actualize this record'
            }, status=403)

        key_cert.actualization_date = timezone.now()
        key_cert.actualized_by = request.user
        key_cert.save(update_fields=['actualization_date', 'actualized_by', 'updated_at'])

        KeyCertHistory.objects.create(
            key_certificate=key_cert,
            action=KeyCertHistory.ACTION_MODIFIED,
            action_by=request.user,
            details=(
                f"Record actualized by owner\n"
                f"Actualized at: {timezone.localtime(key_cert.actualization_date).strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"By: {request.user.get_full_name() or request.user.username}"
            )
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Record actualized successfully',
            'actualization_date': timezone.localtime(key_cert.actualization_date).strftime('%Y-%m-%d %H:%M:%S'),
            'actualized_by': request.user.get_full_name() or request.user.username
        })
    except Exception as e:
        logger.error(f"Error actualizing key/certificate: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def check_services_status(request):
    """
    Redirect to the central service status endpoint to avoid duplication.
    """
    # Use the non-i18n path to avoid translation issues
    return HttpResponseRedirect('/service-status/')