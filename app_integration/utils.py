from functools import wraps

from django.conf import settings as django_settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from app_conf.models import Company

from .models import AccessIntegration


def get_public_base_url():
    env_url = (
        getattr(django_settings, 'TELEGRAM_WEBHOOK_BASE_URL', None)
        or __import__('os').environ.get('TELEGRAM_WEBHOOK_BASE_URL', '')
    ).strip()
    if env_url:
        return env_url.rstrip('/')

    try:
        from app_conf.models import SiteSettings

        site_settings = SiteSettings.get_settings()
        if site_settings and site_settings.site_domain and site_settings.site_domain.strip():
            return site_settings.get_site_url().rstrip('/')
    except Exception:
        pass
    return (getattr(django_settings, 'PUBLIC_BASE_URL', None) or '').rstrip('/')


def get_bot_webhook_url(bot, request=None):
    path = reverse('telegram_webhook', kwargs={'pk': bot.pk})
    base_url = get_public_base_url()
    if base_url:
        return f'{base_url}{path}'
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def register_bot_webhook(bot, request=None):
    """Register or remove the Telegram webhook for a bot. Returns an error or None."""
    from .telegram_client import (
        TelegramAPIError,
        format_webhook_info,
        get_webhook_info,
        sync_bot_webhook,
    )

    webhook_url = get_bot_webhook_url(bot, request)

    if not bot.respond_to_start and not bot.use_webhook:
        try:
            sync_bot_webhook(bot, webhook_url)
        except TelegramAPIError:
            pass
        return None

    if bot.respond_to_start and not bot.use_webhook:
        bot.use_webhook = True
        bot.save(update_fields=['use_webhook'])

    try:
        sync_bot_webhook(bot, webhook_url)
        info = format_webhook_info(get_webhook_info(bot.bot_token))
        if info['url'] != webhook_url:
            raise TelegramAPIError(
                _('Webhook was not registered. Telegram reports URL: %(url)s') % {
                    'url': info['url'] or _('(empty)'),
                },
            )
        if info['last_error_message']:
            raise TelegramAPIError(info['last_error_message'])
        return None
    except TelegramAPIError as exc:
        return exc


def get_user_accessible_companies_integration(user):
    if not user.is_authenticated:
        return []

    if user.is_superuser or user.is_staff:
        return None

    user_groups = user.groups.all()
    if not user_groups.exists():
        return []

    accessible_companies = set()
    has_unrestricted_access = False

    for group in user_groups:
        try:
            access = AccessIntegration.objects.get(group=group, has_access=True)
            if not access.companies.exists():
                has_unrestricted_access = True
                break
            accessible_companies.update(access.companies.all())
        except AccessIntegration.DoesNotExist:
            continue

    if has_unrestricted_access:
        return None

    return list(accessible_companies) if accessible_companies else []


def get_user_integration_permissions(user):
    defaults = {
        'has_access': False,
        'can_view_integrations': False,
        'can_manage_integrations': False,
        'can_test_connections': False,
    }
    if not user.is_authenticated:
        return defaults

    if user.is_superuser or user.is_staff:
        return {
            'has_access': True,
            'can_view_integrations': True,
            'can_manage_integrations': True,
            'can_test_connections': True,
        }

    permissions = defaults.copy()
    for group in user.groups.all():
        try:
            access = AccessIntegration.objects.get(group=group)
        except AccessIntegration.DoesNotExist:
            continue
        if access.has_access:
            permissions['has_access'] = True
        if access.can_view_integrations:
            permissions['can_view_integrations'] = True
        if access.can_manage_integrations:
            permissions['can_manage_integrations'] = True
        if access.can_test_connections:
            permissions['can_test_connections'] = True

    return permissions


def user_has_integration_module_access(user):
    return get_user_integration_permissions(user)['has_access']


def filter_queryset_by_company_access(queryset, user, company_field='company'):
    accessible_companies = get_user_accessible_companies_integration(user)
    if accessible_companies is None:
        return queryset
    if not accessible_companies:
        return queryset.none()
    company_ids = [company.id for company in accessible_companies]
    return queryset.filter(**{f'{company_field}__in': company_ids})


def integration_access_required(permission_key='has_access'):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            permissions = get_user_integration_permissions(request.user)
            if not permissions.get(permission_key):
                message = str(_('You do not have permission to access integrations.'))
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'success': False, 'message': message}, status=403)
                messages.error(request, message)
                return redirect('index')
            request.integration_permissions = permissions
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def get_company_queryset_for_user(user):
    accessible_companies = get_user_accessible_companies_integration(user)
    if accessible_companies is None:
        return Company.objects.all().order_by('name')
    if not accessible_companies:
        return Company.objects.none()
    return Company.objects.filter(
        id__in=[company.id for company in accessible_companies],
    ).order_by('name')
