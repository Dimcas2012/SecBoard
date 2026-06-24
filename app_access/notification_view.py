# SecBoard/app_access/notification_view.py

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.translation import gettext as _, get_language
from django.utils import timezone
import json
import logging
from datetime import datetime

from .models import EmailNotificationConfig, EmailNotificationHistory, AccessNotificationGuide, AccessNotificationGuideTranslation
from .email_utils import send_notification_email
from .matrix_view import (has_access_notification_settings_permission, can_add_notification_settings, 
                         can_edit_notification_settings, can_delete_notification_settings, 
                         get_user_companies_for_notification_settings)
from .email_template_presets import (
    get_email_template_presets,
    get_preset_by_notification_type,
    render_notification_email_content,
)
from .email_template_preview import render_email_preview

logger = logging.getLogger(__name__)


@login_required
def access_notification(request):
    """
    Головна сторінка налаштування сповіщень доступу з вкладками
    """
    # Check access permissions
    if not has_access_notification_settings_permission(request.user):
        return JsonResponse({
            'error': 'Access denied',
            'message': _('Access denied to Notification Settings page')
        }, status=403)

    # Get user's companies and permissions
    user_companies = get_user_companies_for_notification_settings(request.user)
    user_can_add = can_add_notification_settings(request.user)
    user_can_edit = can_edit_notification_settings(request.user)
    user_can_delete = can_delete_notification_settings(request.user)
    
    context = {
        'title': _('Access Notification Settings'),
        'current_page': 'access_notification',
        'can_add_notification_settings': user_can_add,
        'can_edit_notification_settings': user_can_edit,
        'can_delete_notification_settings': user_can_delete,
        'user_companies': user_companies,
        'email_template_presets': get_email_template_presets(),
    }
    return render(request, 'app_access/access_notification.html', context)


@login_required
@require_http_methods(["GET"])
def access_notification_guide(request):
    """Return JSON { content: html } for the Access Notification guide (localized)."""
    if not has_access_notification_settings_permission(request.user):
        return JsonResponse({'content': ''})
    from app_conf.models import Country
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = AccessNotificationGuide.objects.first()
    if guide:
        if country:
            trans = AccessNotificationGuideTranslation.objects.filter(guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = AccessNotificationGuideTranslation.objects.filter(guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def access_notification_guide_translate(request):
    """API for AI translation of Access Notification guide content (admin)."""
    from app_conf.models import Country
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
def get_email_configurations(request):
    """
    Отримання списку конфігурацій email повідомлень
    """
    # Check access permissions
    if not has_access_notification_settings_permission(request.user):
        return JsonResponse({
            'success': False,
            'message': _('Access denied to Notification Settings')
        }, status=403)
        
    try:
        # Фільтри
        search_query = request.GET.get('search', '').strip()
        status_filter = request.GET.get('status', '')
        notification_type_filter = request.GET.get('notification_type', '')
        
        # Базовий queryset
        configurations = EmailNotificationConfig.objects.all()
        
        # Company-based filtering for users
        user_companies = get_user_companies_for_notification_settings(request.user)
        if user_companies.exists():
            configurations = configurations.filter(
                Q(companies__in=user_companies) | Q(companies__isnull=True)
            ).distinct()
        
        # Застосування фільтрів
        if search_query:
            configurations = configurations.filter(
                Q(name__icontains=search_query)
            )
        
        if status_filter:
            is_active = status_filter.lower() == 'active'
            configurations = configurations.filter(is_active=is_active)
        
        if notification_type_filter:
            configurations = configurations.filter(notification_type=notification_type_filter)
        
        # Сортування
        sort_by = request.GET.get('sort', 'priority')
        if sort_by in ['name', 'priority', 'created_at']:
            configurations = configurations.order_by(sort_by)
        else:
            configurations = configurations.order_by('priority', 'name')
        
        # Пагінація
        page = request.GET.get('page', 1)
        paginator = Paginator(configurations, 20)
        page_obj = paginator.get_page(page)
        
        # Формування даних для відповіді
        configurations_data = []
        for config in page_obj:
            configurations_data.append({
                'id': config.id,
                'name': config.name,
                'description': getattr(config, 'description', ''),  # description field might not exist
                'notification_type': config.notification_type,
                'notification_type_display': config.get_notification_type_display(),
                'is_active': config.is_active,
                'priority': config.priority,
                'recipients_config': {
                    'owners': config.notify_owners,
                    'administrators': config.notify_administrators,
                    'requested_by': config.notify_requested_by,
                    'requested_for': config.notify_requested_for,
                    'approving_persons': config.notify_approving_persons,
                    'third_party': config.notify_third_party,
                },
                'triggers': {
                    'request_created': config.send_on_request_created,
                    'status_changed': config.send_on_status_changed,
                    'admin_status_changed': config.send_on_admin_status_changed,
                },
                'custom_templates': config.use_custom_templates,
                'created_at': config.created_at.strftime('%d.%m.%Y %H:%M'),
                'updated_at': config.modified_at.strftime('%d.%m.%Y %H:%M'),
            })
        
        return JsonResponse({
            'success': True,
            'configurations': configurations_data,
            'pagination': {
                'has_previous': page_obj.has_previous(),
                'has_next': page_obj.has_next(),
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'count': paginator.count,
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting email configurations: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Error loading email configurations')
        }, status=500)


@login_required
def get_email_configuration_detail(request, config_id):
    """
    Отримання деталей конкретної конфігурації email повідомлень
    """
    # Check access permissions
    if not has_access_notification_settings_permission(request.user):
        return JsonResponse({
            'success': False,
            'message': _('Access denied to Notification Settings')
        }, status=403)
        
    try:
        config = get_object_or_404(EmailNotificationConfig, id=config_id)
        
        # Check company access
        user_companies = get_user_companies_for_notification_settings(request.user)
        if user_companies.exists():
            if config.companies.exists() and not config.companies.filter(id__in=user_companies.values_list('id', flat=True)).exists():
                return JsonResponse({
                    'success': False,
                    'message': _('Access denied to this configuration')
                }, status=403)
        
        data = {
            'id': config.id,
            'name': config.name,
            'description': getattr(config, 'description', ''),
            'notification_type': config.notification_type,
            'notification_type_display': config.get_notification_type_display(),
            'is_active': config.is_active,
            'priority': config.priority,
            
            # Налаштування отримувачів
            'send_to_owners': config.notify_owners,
            'send_to_administrators': config.notify_administrators,
            'send_to_requested_by': config.notify_requested_by,
            'send_to_requested_for': config.notify_requested_for,
            'send_to_approving_persons': config.notify_approving_persons,
            'send_to_third_party': config.notify_third_party,
            
            # Тригери
            'trigger_on_request_created': config.send_on_request_created,
            'trigger_on_status_changed': config.send_on_status_changed,
            'trigger_on_admin_status_changed': config.send_on_admin_status_changed,
            
            # Користувацькі шаблони
            'use_custom_templates': config.use_custom_templates,
            'custom_subject_request_created': config.request_created_subject_template,
            'custom_subject_status_changed': config.status_changed_subject_template,
            'custom_html_template_request_created': config.request_created_html_template,
            'custom_html_template_status_changed': config.status_changed_html_template,
            'custom_text_template_request_created': config.request_created_text_template,
            'custom_text_template_status_changed': config.status_changed_text_template,
            
            'created_at': config.created_at.strftime('%d.%m.%Y %H:%M'),
            'updated_at': config.modified_at.strftime('%d.%m.%Y %H:%M'),
        }
        
        return JsonResponse({
            'success': True,
            'configuration': data
        })
        
    except Exception as e:
        logger.error(f"Error getting email configuration detail: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Error loading configuration details')
        }, status=500)


@csrf_exempt
@login_required
def save_email_configuration(request):
    """
    Збереження конфігурації email повідомлень
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': _('Method not allowed')}, status=405)
    
    # Check permissions
    config_id = None
    try:
        data = json.loads(request.body)
        config_id = data.get('id')
    except:
        pass
        
    if config_id:
        # Editing existing configuration
        if not can_edit_notification_settings(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to edit notification settings')
            }, status=403)
    else:
        # Creating new configuration
        if not can_add_notification_settings(request.user):
            return JsonResponse({
                'success': False,
                'message': _('Access denied - you do not have permission to add notification settings')
            }, status=403)
    
    try:
        data = json.loads(request.body)
        config_id = data.get('id')
        
        # Валідація обов'язкових полів
        required_fields = ['name', 'notification_type']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'message': _(f'Field {field} is required')
                })

        notification_type = data.get('notification_type')
        valid_types = {choice[0] for choice in EmailNotificationConfig.NOTIFICATION_TYPE_CHOICES}
        if notification_type not in valid_types:
            return JsonResponse({
                'success': False,
                'message': _('Invalid notification type'),
            })
        
        # Створення або оновлення конфігурації
        if config_id:
            config = get_object_or_404(EmailNotificationConfig, id=config_id)
        else:
            config = EmailNotificationConfig()
        
        # Основні поля
        config.name = data['name']
        config.notification_type = notification_type
        config.is_active = data.get('is_active', True)
        config.priority = data.get('priority', 10)
        
        # Налаштування отримувачів
        config.notify_owners = data.get('send_to_owners', True)
        config.notify_administrators = data.get('send_to_administrators', True)
        config.notify_requested_by = data.get('send_to_requested_by', True)
        config.notify_requested_for = data.get('send_to_requested_for', False)
        config.notify_approving_persons = data.get('send_to_approving_persons', True)
        config.notify_third_party = data.get('send_to_third_party', True)
        
        # Тригери
        config.send_on_request_created = data.get('trigger_on_request_created', True)
        config.send_on_status_changed = data.get('trigger_on_status_changed', True)
        config.send_on_admin_status_changed = data.get('trigger_on_admin_status_changed', True)
        
        # Користувацькі шаблони
        config.use_custom_templates = data.get('use_custom_templates', False)
        if config.use_custom_templates:
            config.request_created_subject_template = data.get('custom_subject_request_created', '')
            config.status_changed_subject_template = data.get('custom_subject_status_changed', '')
            config.request_created_html_template = data.get('custom_html_template_request_created', '')
            config.status_changed_html_template = data.get('custom_html_template_status_changed', '')
            config.request_created_text_template = data.get('custom_text_template_request_created', '')
            config.status_changed_text_template = data.get('custom_text_template_status_changed', '')
        
        # Set created_by and modified_by if creating new config
        if not config_id:
            config.created_by = request.user
        config.modified_by = request.user
        
        config.save()
        
        logger.info(f"Email configuration saved: {config.name} (ID: {config.id})")
        
        return JsonResponse({
            'success': True,
            'message': _('Configuration saved successfully'),
            'configuration_id': config.id
        })
        
    except Exception as e:
        logger.error(f"Error saving email configuration: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Error saving configuration')
        }, status=500)


@csrf_exempt
@login_required
def delete_email_configuration(request, config_id):
    """
    Видалення конфігурації email повідомлень
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': _('Method not allowed')}, status=405)
    
    try:
        config = get_object_or_404(EmailNotificationConfig, id=config_id)
        config_name = config.name
        config.delete()
        
        logger.info(f"Email configuration deleted: {config_name} (ID: {config_id})")
        
        return JsonResponse({
            'success': True,
            'message': _('Configuration deleted successfully')
        })
        
    except Exception as e:
        logger.error(f"Error deleting email configuration: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Error deleting configuration')
        }, status=500)


@csrf_exempt
@login_required
def toggle_configuration_status(request, config_id):
    """
    Перемикання статусу конфігурації email повідомлень
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': _('Method not allowed')}, status=405)
    
    try:
        config = get_object_or_404(EmailNotificationConfig, id=config_id)
        config.is_active = not config.is_active
        config.modified_by = request.user
        config.save()
        
        status_text = _('activated') if config.is_active else _('deactivated')
        logger.info(f"Email configuration {status_text}: {config.name} (ID: {config_id})")
        
        return JsonResponse({
            'success': True,
            'message': _('Configuration status updated successfully'),
            'is_active': config.is_active
        })
        
    except Exception as e:
        logger.error(f"Error toggling configuration status: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Error updating configuration status')
        }, status=500)


def _resolve_email_templates_for_preview(config, template_kind, preset_kind):
    """Return (subject, html, text) for a saved EmailNotificationConfig."""
    from .email_template_preview import get_sample_email_context

    sample_ctx = get_sample_email_context(preset_kind or config.notification_type)
    return render_notification_email_content(config, template_kind, sample_ctx)


@login_required
@require_POST
def preview_email_template(request):
    """Render email template with sample data for UI preview."""
    if not has_access_notification_settings_permission(request.user):
        return JsonResponse({'success': False, 'message': _('Access denied')}, status=403)

    try:
        data = json.loads(request.body)
        preset_id = (data.get('preset_id') or 'grant').strip()
        template_kind = (data.get('template_kind') or 'request_created').strip()
        config_id = data.get('config_id')
        subject = data.get('subject', '')
        html = data.get('html', '')
        text = data.get('text', '')
        config_name = ''

        if config_id:
            config = get_object_or_404(EmailNotificationConfig, id=config_id)
            user_companies = get_user_companies_for_notification_settings(request.user)
            if user_companies.exists():
                if config.companies.exists() and not config.companies.filter(
                    id__in=user_companies.values_list('id', flat=True)
                ).exists():
                    return JsonResponse({
                        'success': False,
                        'message': _('Access denied to this configuration'),
                    }, status=403)
            config_name = config.name
            preset_id = config.notification_type
            subject, html, text = _resolve_email_templates_for_preview(config, template_kind, preset_id)
        elif not subject and not html and not text:
            preset = get_preset_by_notification_type(preset_id)
            bundle_key = 'status_changed' if template_kind == 'status_changed' else 'request_created'
            bundle = preset.get(bundle_key, preset['request_created'])
            subject = bundle.get('subject', '')
            html = bundle.get('html', '')
            text = bundle.get('text', '')
        elif not html and not text:
            from .email_template_preview import get_sample_email_context

            sample_ctx = get_sample_email_context(preset_id)

            class _PreviewConfig:
                use_custom_templates = False
                notification_type = preset_id

            subject, html, text = render_notification_email_content(
                _PreviewConfig(), template_kind, sample_ctx
            )

        preview = render_email_preview(subject=subject, html=html, text=text, preset_kind=preset_id)
        return JsonResponse({
            'success': True,
            'preview': preview,
            'config_name': config_name,
            'template_kind': template_kind,
        })
    except Exception as e:
        logger.error(f"Error previewing email template: {e}")
        return JsonResponse({
            'success': False,
            'message': _('Error rendering preview: %(error)s') % {'error': str(e)},
        }, status=400)


@csrf_exempt
@login_required
def test_email_send(request):
    """
    Тестова відправка email повідомлення
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': _('Method not allowed')}, status=405)
    
    try:
        data = json.loads(request.body)
        config_id = data.get('config_id')
        test_email = data.get('test_email')
        
        if not config_id or not test_email:
            return JsonResponse({
                'success': False,
                'message': _('Configuration ID and test email are required')
            })
        
        config = get_object_or_404(EmailNotificationConfig, id=config_id)
        
        # Create test context data
        test_context = {
            'config_name': config.name,
            'test_message': _('This is a test email notification'),
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'company_name': 'Test Company',
            'system_name': 'Test System',
            'environment': 'Test Environment',
            'user_full_name': request.user.get_full_name() or request.user.username,
            'justification': 'Test email functionality',
            'old_status': 'pending',
            'new_status': 'approved'
        }
        
        # Send test email using the correct function signature
        success = send_notification_email(
            config=config,
            notification_type='test_email',
            context=test_context,
            recipients=[test_email],
            force_send=True  # Force send for testing
        )
        
        if success:
            logger.info(f"Test email sent successfully to {test_email} using config {config.name}")
            return JsonResponse({
                'success': True,
                'message': _('Test email sent successfully')
            })
        else:
            raise Exception(_('Failed to send test email'))
        
    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Error sending test email')
        }, status=500)


@login_required
def get_notification_history(request):
    """
    Отримання історії email повідомлень з пагінацією та фільтрацією
    """
    try:
        # Параметри пагінації
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 25))
        
        # Параметри фільтрації
        search = request.GET.get('search', '').strip()
        status_filter = request.GET.get('status', '').strip()
        notification_type_filter = request.GET.get('notification_type', '').strip()
        date_from = request.GET.get('date_from', '').strip()
        date_to = request.GET.get('date_to', '').strip()
        
        # Базовий запит
        queryset = EmailNotificationHistory.objects.select_related(
            'access_request',
            'access_request__company',
            'access_request__system',
            'triggered_by',
            'mail_account'
        ).order_by('-created_at')
        
        # Фільтрація за пошуком
        if search:
            queryset = queryset.filter(
                Q(subject__icontains=search) |
                Q(access_request__company__name__icontains=search) |
                Q(access_request__system__name__icontains=search) |
                Q(triggered_by__first_name__icontains=search) |
                Q(triggered_by__last_name__icontains=search) |
                Q(recipients__icontains=search)
            )
        
        # Фільтрація за статусом
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Фільтрація за типом повідомлення
        if notification_type_filter:
            queryset = queryset.filter(notification_type=notification_type_filter)
        
        # Фільтрація за датами
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                queryset = queryset.filter(created_at__gte=date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                queryset = queryset.filter(created_at__lte=date_to_obj)
            except ValueError:
                pass
        
        # Пагінація
        paginator = Paginator(queryset, per_page)
        total_pages = paginator.num_pages
        total_count = paginator.count
        
        if page > total_pages and total_pages > 0:
            page = total_pages
        
        notifications_page = paginator.get_page(page)
        
        # Підготовка даних
        notifications_data = []
        for notification in notifications_page:
            triggered_by_data = None
            if notification.triggered_by:
                triggered_username = notification.triggered_by.username
                triggered_name = notification.triggered_by.get_full_name()
                if (triggered_username or '').strip().lower() == 'customer':
                    triggered_name = ''

                triggered_by_data = {
                    'name': triggered_name,
                    'username': triggered_username,
                }

            notification_data = {
                'id': notification.id,
                'notification_type': notification.notification_type,
                'notification_type_display': notification.get_notification_type_display(),
                'subject': notification.subject,
                'recipients': notification.recipients,
                'recipients_count': notification.recipients_count,
                'recipients_display': notification.recipients_display,
                'status': notification.status,
                'status_display': notification.get_status_display(),
                'created_at': notification.created_at.isoformat(),
                'sent_at': notification.sent_at.isoformat() if notification.sent_at else None,
                'error_message': notification.error_message,
                'retry_count': notification.retry_count,
                'max_retries': notification.max_retries,
                'is_successful': notification.is_successful,
                'is_pending': notification.is_pending,
                'can_retry': notification.can_retry(),
                # Access request info
                'access_request': {
                    'id': notification.access_request.id if notification.access_request else None,
                    'company_name': notification.access_request.company.name if notification.access_request else None,
                    'system_name': notification.access_request.system.name if notification.access_request else None,
                    'requested_for': notification.access_request.requested_for.get_full_name() if notification.access_request else None,
                    'request_type': notification.access_request.request_type if notification.access_request else None,
                    'status': notification.access_request.status if notification.access_request else None,
                } if notification.access_request else None,
                # Triggered by info
                'triggered_by': triggered_by_data,
                # Mail account info
                'mail_account': {
                    'name': str(notification.mail_account) if notification.mail_account else None,
                    'username': notification.mail_account.username if notification.mail_account else None,
                } if notification.mail_account else None,
            }
            notifications_data.append(notification_data)
        
        # Статистика
        total_sent = EmailNotificationHistory.objects.filter(status='sent').count()
        total_failed = EmailNotificationHistory.objects.filter(status='failed').count()
        total_pending = EmailNotificationHistory.objects.filter(status='pending').count()
        total_retrying = EmailNotificationHistory.objects.filter(status='retrying').count()
        
        return JsonResponse({
            'status': 'success',
            'notifications': notifications_data,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_count': total_count,
                'has_previous': notifications_page.has_previous(),
                'has_next': notifications_page.has_next(),
                'per_page': per_page
            },
            'statistics': {
                'total_sent': total_sent,
                'total_failed': total_failed,
                'total_pending': total_pending,
                'total_retrying': total_retrying,
                'total_notifications': total_sent + total_failed + total_pending + total_retrying
            },
            'filters': {
                'search': search,
                'status': status_filter,
                'notification_type': notification_type_filter,
                'date_from': date_from,
                'date_to': date_to
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting notification history: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _('Error loading notification history')
        }, status=500)


@csrf_exempt
@login_required
def retry_failed_notification(request, notification_id):
    """
    Повторна спроба відправки невдалого email повідомлення
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': _('Method not allowed')}, status=405)
    
    try:
        notification = get_object_or_404(EmailNotificationHistory, id=notification_id)
        
        if not notification.can_retry():
            return JsonResponse({
                'success': False,
                'message': _('This notification cannot be retried')
            })
        
        # Mark for retry
        if notification.mark_for_retry():
            logger.info(f"Notification marked for retry: {notification.id}")
            
            # Here you could add the notification to a queue for retry
            # For now, we'll just mark it as retrying
            
            return JsonResponse({
                'success': True,
                'message': _('Notification marked for retry')
            })
        else:
            return JsonResponse({
                'success': False,
                'message': _('Failed to mark notification for retry')
            })
        
    except Exception as e:
        logger.error(f"Error retrying notification: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Error retrying notification')
        }, status=500) 