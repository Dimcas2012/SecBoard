"""Send bulk Telegram messages to cabinet users from Users Management."""

import logging

from django.utils.translation import gettext as _

from app_integration.models import TelegramBot
from app_integration.telegram_client import TelegramAPIError, send_message
from app_integration.telegram_i18n import telegram_language

logger = logging.getLogger(__name__)

MESSAGE_TYPE_CUSTOM = 'custom'
MESSAGE_TYPE_TASKS = 'tasks'


def get_active_telegram_bot_for_company(company_id):
    return (
        TelegramBot.objects.filter(company_id=company_id, is_active=True)
        .order_by('-last_connection_ok', '-updated_at')
        .first()
    )


def _build_broadcast_text(cabinet_user, message_type, custom_text=''):
    if message_type == MESSAGE_TYPE_TASKS:
        from app_cabinet.task_reminder_utils import build_task_reminder_plain_body

        return build_task_reminder_plain_body(cabinet_user)
    return (custom_text or '').strip()


def send_telegram_broadcast_for_user_ids(cabinet_user_ids, message_type=MESSAGE_TYPE_CUSTOM, custom_text=''):
    from app_cabinet.models import CabinetUser

    sent = 0
    skipped = 0
    errors = []

    if message_type == MESSAGE_TYPE_CUSTOM and not (custom_text or '').strip():
        return 0, 0, [_('Message text is required.')]

    cabinet_users = list(
        CabinetUser.objects.filter(pk__in=cabinet_user_ids)
        .select_related('user', 'company')
        .order_by('user__last_name', 'user__first_name')
    )

    bots_by_company = {}
    for cabinet_user in cabinet_users:
        display_name = cabinet_user.user.get_full_name() or cabinet_user.user.username
        chat_id = (cabinet_user.telegram_chat_id or '').strip()
        if not chat_id:
            skipped += 1
            errors.append(_('%(name)s: Telegram is not connected.') % {'name': display_name})
            continue

        company_id = cabinet_user.company_id
        if not company_id:
            skipped += 1
            errors.append(_('%(name)s: no company assigned.') % {'name': display_name})
            continue

        if company_id not in bots_by_company:
            bots_by_company[company_id] = get_active_telegram_bot_for_company(company_id)

        bot = bots_by_company[company_id]
        if not bot:
            skipped += 1
            errors.append(
                _('%(name)s: no active Telegram bot for company %(company)s.') % {
                    'name': display_name,
                    'company': cabinet_user.company.name,
                },
            )
            continue

        try:
            with telegram_language(bot, chat_id, cabinet_user=cabinet_user):
                text = _build_broadcast_text(cabinet_user, message_type, custom_text)
                if not text:
                    skipped += 1
                    errors.append(_('%(name)s: empty message.') % {'name': display_name})
                    continue
                send_message(bot.bot_token, chat_id, text)
            sent += 1
        except TelegramAPIError as exc:
            skipped += 1
            errors.append(f'{display_name}: {exc}')
            logger.warning('Telegram broadcast failed for cabinet user %s: %s', cabinet_user.pk, exc)

    return sent, skipped, errors
