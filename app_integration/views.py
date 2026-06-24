import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from .forms import TelegramBotForm
from .models import TelegramBot
from .telegram_client import (
    TelegramAPIError,
    format_webhook_info,
    get_webhook_info,
    send_message,
    sync_bot_webhook,
    test_bot_connection,
    update_bot_connection_status,
)
from .telegram_handlers import process_telegram_update
from .utils import (
    filter_queryset_by_company_access,
    get_bot_webhook_url,
    get_user_integration_permissions,
    integration_access_required,
    register_bot_webhook,
)

logger = logging.getLogger(__name__)


def _register_bot_webhook(request, bot):
    return register_bot_webhook(bot, request)


def _get_bot_webhook_status(bot, request):
    expected_url = get_bot_webhook_url(bot, request)
    try:
        info = format_webhook_info(get_webhook_info(bot.bot_token))
    except TelegramAPIError as exc:
        return {
            'expected_url': expected_url,
            'registered_url': '',
            'is_configured': False,
            'pending_update_count': 0,
            'last_error_message': str(exc),
        }
    return {
        'expected_url': expected_url,
        'registered_url': info['url'],
        'is_configured': info['url'] == expected_url and bool(info['url']),
        'pending_update_count': info['pending_update_count'],
        'last_error_message': info['last_error_message'],
    }


def _integration_context(request, extra=None):
    permissions = getattr(request, 'integration_permissions', get_user_integration_permissions(request.user))
    context = {
        'integration_permissions': permissions,
        'can_manage_integrations': permissions.get('can_manage_integrations'),
        'can_test_connections': permissions.get('can_test_connections'),
    }
    if extra:
        context.update(extra)
    return context


@login_required
@integration_access_required('has_access')
def dashboard(request):
    bots = filter_queryset_by_company_access(
        TelegramBot.objects.select_related('company', 'created_by'),
        request.user,
    )
    context = _integration_context(request, {
        'title': _('Integrations'),
        'telegram_bots': bots,
        'active_bots_count': bots.filter(is_active=True).count(),
        'connected_bots_count': bots.filter(last_connection_ok=True).count(),
    })
    return render(request, 'app_integration/dashboard.html', context)


@login_required
@integration_access_required('can_view_integrations')
def telegram_bot_list(request):
    bots = filter_queryset_by_company_access(
        TelegramBot.objects.select_related('company', 'created_by'),
        request.user,
    )
    context = _integration_context(request, {
        'title': _('Telegram bots'),
        'bots': bots,
    })
    return render(request, 'app_integration/telegram_bot_list.html', context)


@login_required
@integration_access_required('can_manage_integrations')
def telegram_bot_create(request):
    if request.method == 'POST':
        form = TelegramBotForm(request.POST, user=request.user)
        if form.is_valid():
            bot = form.save(commit=False)
            bot.created_by = request.user
            bot.save()
            try:
                bot_info = test_bot_connection(bot.bot_token)
                update_bot_connection_status(bot, True, bot_info)
                messages.success(request, _('Telegram bot created and connection verified.'))
            except TelegramAPIError as exc:
                update_bot_connection_status(bot, False)
                messages.warning(
                    request,
                    _('Bot saved, but connection test failed: %(error)s') % {'error': exc},
                )
            webhook_error = _register_bot_webhook(request, bot)
            if webhook_error:
                messages.warning(
                    request,
                    _('Bot saved, but webhook setup failed: %(error)s') % {'error': webhook_error},
                )
            elif bot.respond_to_start:
                messages.info(request, _('Webhook registered for /start command handling.'))
            return redirect('app_integration:telegram_bot_list')
    else:
        form = TelegramBotForm(user=request.user)

    context = _integration_context(request, {
        'title': _('Add Telegram bot'),
        'form': form,
    })
    return render(request, 'app_integration/telegram_bot_form.html', context)


@login_required
@integration_access_required('can_manage_integrations')
def telegram_bot_edit(request, pk):
    bot = get_object_or_404(
        filter_queryset_by_company_access(TelegramBot.objects.all(), request.user),
        pk=pk,
    )
    if request.method == 'POST':
        form = TelegramBotForm(request.POST, instance=bot, user=request.user)
        if form.is_valid():
            bot = form.save()
            try:
                bot_info = test_bot_connection(bot.bot_token)
                update_bot_connection_status(bot, True, bot_info)
                messages.success(request, _('Telegram bot updated and connection verified.'))
            except TelegramAPIError as exc:
                update_bot_connection_status(bot, False)
                messages.warning(
                    request,
                    _('Bot updated, but connection test failed: %(error)s') % {'error': exc},
                )
            webhook_error = _register_bot_webhook(request, bot)
            if webhook_error:
                messages.warning(
                    request,
                    _('Bot updated, but webhook setup failed: %(error)s') % {'error': webhook_error},
                )
            elif bot.respond_to_start:
                messages.info(request, _('Webhook registered for /start command handling.'))
            return redirect('app_integration:telegram_bot_list')
    else:
        form = TelegramBotForm(instance=bot, user=request.user)

    context = _integration_context(request, {
        'title': _('Edit Telegram bot'),
        'form': form,
        'bot': bot,
        'webhook_status': _get_bot_webhook_status(bot, request),
    })
    return render(request, 'app_integration/telegram_bot_form.html', context)


@login_required
@integration_access_required('can_manage_integrations')
@require_POST
def telegram_bot_delete(request, pk):
    bot = get_object_or_404(
        filter_queryset_by_company_access(TelegramBot.objects.all(), request.user),
        pk=pk,
    )
    bot_name = bot.name
    bot.delete()
    messages.success(request, _('Telegram bot "%(name)s" deleted.') % {'name': bot_name})
    return redirect('app_integration:telegram_bot_list')


@login_required
@integration_access_required('can_test_connections')
@require_POST
def telegram_bot_test_connection(request, pk):
    bot = get_object_or_404(
        filter_queryset_by_company_access(TelegramBot.objects.all(), request.user),
        pk=pk,
    )
    try:
        bot_info = test_bot_connection(bot.bot_token)
        update_bot_connection_status(bot, True, bot_info)
        webhook_error = None
        if bot.respond_to_start or bot.use_webhook:
            webhook_error = register_bot_webhook(bot, request)
        message = str(_('Connection successful.'))
        if webhook_error:
            message = str(_('Connection successful, but webhook setup failed: %(error)s') % {
                'error': webhook_error,
            })
        return JsonResponse({
            'success': True,
            'message': message,
            'bot_username': bot_info.get('bot_username', ''),
            'bot_id': bot_info.get('bot_id'),
        })
    except TelegramAPIError as exc:
        update_bot_connection_status(bot, False)
        return JsonResponse({
            'success': False,
            'message': str(exc),
        }, status=400)


@login_required
@integration_access_required('can_test_connections')
@require_POST
def telegram_bot_send_test_message(request, pk):
    bot = get_object_or_404(
        filter_queryset_by_company_access(TelegramBot.objects.all(), request.user),
        pk=pk,
    )
    chat_id = request.POST.get('chat_id') or bot.default_chat_id
    if not chat_id:
        return JsonResponse({
            'success': False,
            'message': str(_('Chat ID is required.')),
        }, status=400)

    try:
        send_message(
            bot.bot_token,
            chat_id,
            str(_('Test message from SecBoard integration module.')),
        )
        return JsonResponse({
            'success': True,
            'message': str(_('Test message sent.')),
        })
    except TelegramAPIError as exc:
        return JsonResponse({
            'success': False,
            'message': str(exc),
        }, status=400)
    except Exception as exc:
        logger.exception('Failed to send Telegram test message for bot %s', bot.pk)
        return JsonResponse({
            'success': False,
            'message': str(exc),
        }, status=500)


@login_required
@integration_access_required('can_manage_integrations')
@require_POST
def telegram_bot_configure_webhook(request, pk):
    bot = get_object_or_404(
        filter_queryset_by_company_access(TelegramBot.objects.all(), request.user),
        pk=pk,
    )
    webhook_url = get_bot_webhook_url(bot, request)
    try:
        sync_bot_webhook(bot, webhook_url)
        if bot.use_webhook or bot.respond_to_start:
            info = format_webhook_info(get_webhook_info(bot.bot_token))
            message = _('Webhook configured.')
            if info['pending_update_count']:
                message = _(
                    'Webhook configured. %(count)s pending update(s) will be delivered shortly.',
                ) % {'count': info['pending_update_count']}
        else:
            message = _('Webhook removed (long polling mode).')
        return JsonResponse({
            'success': True,
            'message': str(message),
            'webhook_url': webhook_url,
            'webhook_status': _get_bot_webhook_status(bot, request),
        })
    except TelegramAPIError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)


@login_required
@integration_access_required('can_manage_integrations')
@require_POST
def telegram_bot_webhook_status(request, pk):
    bot = get_object_or_404(
        filter_queryset_by_company_access(TelegramBot.objects.all(), request.user),
        pk=pk,
    )
    return JsonResponse({
        'success': True,
        'webhook_status': _get_bot_webhook_status(bot, request),
    })


@csrf_exempt
@require_http_methods(['POST'])
def telegram_webhook(request, pk):
    """Прийом оновлень від Telegram (webhook endpoint)."""
    bot = get_object_or_404(TelegramBot, pk=pk, is_active=True)
    if bot.webhook_secret:
        secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if secret != bot.webhook_secret:
            return JsonResponse({'ok': False}, status=403)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'ok': False}, status=400)

    logger.info('Telegram webhook received for bot %s (pk=%s)', bot.name, bot.pk)
    try:
        if process_telegram_update(bot, payload):
            logger.info('Processed /start for bot %s', bot.name)
        else:
            message = payload.get('message') or payload.get('edited_message') or {}
            logger.info(
                'Telegram update ignored for bot %s: text=%r',
                bot.name,
                message.get('text', ''),
            )
    except TelegramAPIError as exc:
        logger.error('Telegram webhook handler error for bot %s: %s', bot.name, exc)

    return JsonResponse({'ok': True})
