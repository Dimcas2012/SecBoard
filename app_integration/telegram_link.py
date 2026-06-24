import re
import secrets
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from app_cabinet.models import CabinetUser

from .models import TelegramAuthLink, TelegramBot
from .telegram_client import send_message
from .utils import get_public_base_url

LINK_PAYLOAD_RE = re.compile(r'^link_(?P<token>.+)$', re.IGNORECASE)
TELEGRAM_AUTH_LINK_TTL = timedelta(hours=24)


def _extract_start_payload(text):
    if not text:
        return ''
    stripped = text.strip()
    match = re.match(r'^/start(?:@\w+)?(?:\s+(?P<payload>.+))?$', stripped, re.IGNORECASE)
    if not match:
        return ''
    return (match.group('payload') or '').strip()


def get_public_telegram_bot_link(company_id=None):
    """
    Public t.me link for footer / site chrome (no user-specific start payload).
    Prefers company bot when company_id is set, otherwise first active configured bot.
    """
    qs = TelegramBot.objects.filter(is_active=True).exclude(bot_username='')
    if company_id:
        bot = qs.filter(company_id=company_id).order_by(
            '-last_connection_ok', '-updated_at',
        ).first()
        if bot is None:
            bot = qs.order_by('-last_connection_ok', '-updated_at').first()
    else:
        bot = qs.order_by('-last_connection_ok', '-updated_at').first()

    if bot is None:
        return None

    username = (bot.bot_username or '').strip().lstrip('@')
    if not username:
        return None

    return {
        'url': f'https://t.me/{username}',
        'username': f'@{username}',
        'name': bot.name,
    }


def get_telegram_profile_link_context(cabinet_user):
    chat_id = (cabinet_user.telegram_chat_id or '').strip()
    context = {
        'is_linked': bool(chat_id),
        'telegram_chat_id': chat_id,
        'available': False,
        'bot_name': '',
        'bot_username': '',
        'deep_link': '',
        'reason': '',
    }

    if not cabinet_user.company_id:
        context['reason'] = _('Assign a company to your profile before linking Telegram.')
        return context

    bot = (
        TelegramBot.objects.filter(company_id=cabinet_user.company_id, is_active=True)
        .order_by('-last_connection_ok', '-updated_at')
        .first()
    )
    if not bot:
        context['reason'] = _('No active Telegram bot is configured for your company.')
        return context

    username = (bot.bot_username or '').strip().lstrip('@')
    if not username:
        context['reason'] = _(
            'Telegram bot is not configured yet. Ask your administrator to test the bot connection.',
        )
        return context

    payload = cabinet_user.get_telegram_start_payload()
    context.update({
        'available': True,
        'bot_name': bot.name,
        'bot_username': f'@{username}',
        'deep_link': f'https://t.me/{username}?start={payload}',
    })
    return context


def get_or_create_telegram_auth_link(bot, chat_id):
    chat_id_str = str(chat_id).strip()
    now = timezone.now()
    existing = (
        TelegramAuthLink.objects.filter(
            bot=bot,
            chat_id=chat_id_str,
            used_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by('-created_at')
        .first()
    )
    if existing:
        return existing

    return TelegramAuthLink.objects.create(
        token=secrets.token_urlsafe(32)[:48],
        bot=bot,
        chat_id=chat_id_str,
        expires_at=now + TELEGRAM_AUTH_LINK_TTL,
    )


def get_telegram_auth_login_url(bot, chat_id):
    auth_link = get_or_create_telegram_auth_link(bot, chat_id)
    base = get_public_base_url()
    login_path = f'{reverse("login")}?tg={auth_link.token}'
    if base:
        return f'{base.rstrip("/")}{login_path}'
    return login_path


def is_telegram_auth_token_valid(token):
    if not token:
        return False
    return TelegramAuthLink.objects.filter(
        token=token,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).exists()


def store_pending_telegram_auth_token(request, token):
    if not is_telegram_auth_token_valid(token):
        return False
    request.session['pending_telegram_auth_token'] = token
    request.session.modified = True
    return True


def _notify_telegram_link_success(auth_link, cabinet_user):
    from .telegram_handlers import get_main_reply_keyboard
    from .telegram_i18n import telegram_language

    with telegram_language(
        auth_link.bot,
        auth_link.chat_id,
        cabinet_user=cabinet_user,
    ):
        send_message(
            auth_link.bot.bot_token,
            auth_link.chat_id,
            str(_('Your SecBoard account has been linked to Telegram.')),
            reply_markup=get_main_reply_keyboard(),
        )


def complete_pending_telegram_link(request, user):
    token = request.session.pop('pending_telegram_auth_token', None)
    if not token:
        return False

    auth_link = (
        TelegramAuthLink.objects.select_related('bot', 'bot__company')
        .filter(token=token, used_at__isnull=True)
        .first()
    )
    if auth_link is None or not auth_link.is_valid:
        from django.contrib import messages
        messages.warning(
            request,
            _('This Telegram link has expired or is invalid. Open the bot and request a new sign-in link.'),
        )
        return False

    cabinet_user, _created = CabinetUser.objects.get_or_create(user=user)
    if not cabinet_user.company_id:
        from django.contrib import messages
        messages.warning(
            request,
            _('Assign a company to your profile before linking Telegram.'),
        )
        request.session['pending_telegram_auth_token'] = token
        request.session.modified = True
        return False

    if cabinet_user.company_id != auth_link.bot.company_id:
        from django.contrib import messages
        messages.warning(
            request,
            _('Your SecBoard company does not match this Telegram bot.'),
        )
        return False

    duplicate = (
        CabinetUser.objects.filter(
            telegram_chat_id=auth_link.chat_id,
            company_id=auth_link.bot.company_id,
        )
        .exclude(pk=cabinet_user.pk)
        .exists()
    )
    if duplicate:
        from django.contrib import messages
        messages.warning(
            request,
            _('This Telegram account is already linked to another SecBoard user.'),
        )
        return False

    cabinet_user.telegram_chat_id = auth_link.chat_id
    cabinet_user.save(update_fields=['telegram_chat_id'])
    auth_link.used_at = timezone.now()
    auth_link.cabinet_user = cabinet_user
    auth_link.save(update_fields=['used_at', 'cabinet_user'])

    try:
        _notify_telegram_link_success(auth_link, cabinet_user)
    except Exception:
        pass

    from django.contrib import messages
    messages.success(request, _('Your Telegram account has been linked successfully.'))
    return True


def process_telegram_account_link(bot, message):
    """Link a Cabinet user when they open a /start deep link from their profile."""
    payload = _extract_start_payload(message.get('text', ''))
    link_match = LINK_PAYLOAD_RE.match(payload)
    if not link_match:
        return False

    chat = message.get('chat') or {}
    chat_id = chat.get('id')
    if chat_id is None:
        return False

    token = link_match.group('token')
    cabinet_user = CabinetUser.objects.filter(
        telegram_link_token=token,
        company_id=bot.company_id,
    ).first()

    if cabinet_user is None:
        reply_text = _('This link is invalid or has expired. Generate a new link in your SecBoard profile.')
    else:
        cabinet_user.telegram_chat_id = str(chat_id)
        cabinet_user.save(update_fields=['telegram_chat_id'])
        reply_text = _('Your SecBoard account has been linked to Telegram.')

    from .telegram_i18n import telegram_language
    from .telegram_handlers import get_main_reply_keyboard

    with telegram_language(
        bot, chat_id, cabinet_user=cabinet_user, message=message,
    ):
        send_message(
            bot.bot_token,
            chat_id,
            str(reply_text),
            reply_markup=get_main_reply_keyboard(),
        )
    return True
