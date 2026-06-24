import logging
import re

from django.utils.translation import gettext as _

from .telegram_client import send_message
from .telegram_i18n import is_button_press, telegram_language
from .telegram_link import process_telegram_account_link
from .telegram_study import build_training_reply_text
from .telegram_tasks import (
    build_approvals_reply_text,
    build_my_tasks_reply_text,
    get_cabinet_user_for_telegram,
    get_login_inline_keyboard,
)

logger = logging.getLogger(__name__)

START_COMMAND_RE = re.compile(r'^/start(?:@\w+)?(?:\s|$)', re.IGNORECASE)
HELP_COMMAND_RE = re.compile(r'^/help(?:@\w+)?(?:\s|$)', re.IGNORECASE)
TASKS_COMMAND_RE = re.compile(r'^/tasks(?:@\w+)?(?:\s|$)', re.IGNORECASE)
APPROVALS_COMMAND_RE = re.compile(r'^/approvals(?:@\w+)?(?:\s|$)', re.IGNORECASE)
STUDY_COMMAND_RE = re.compile(r'^/study(?:@\w+)?(?:\s|$)', re.IGNORECASE)


def is_start_command(text):
    if not text:
        return False
    return bool(START_COMMAND_RE.match(text.strip()))


def parse_start_payload(text):
    match = re.match(r'^/start(?:@\w+)?\s+(\S+)', text.strip(), re.IGNORECASE)
    return match.group(1) if match else None


def is_help_request(text):
    if not text:
        return False
    normalized = text.strip()
    if HELP_COMMAND_RE.match(normalized):
        return True
    return is_button_press(text, 'Help')


def is_tasks_request(text):
    if not text:
        return False
    normalized = text.strip()
    if TASKS_COMMAND_RE.match(normalized):
        return True
    return is_button_press(text, 'My tasks')


def is_approvals_request(text):
    if not text:
        return False
    normalized = text.strip()
    if APPROVALS_COMMAND_RE.match(normalized):
        return True
    return is_button_press(text, 'For approval')


def is_training_request(text):
    if not text:
        return False
    normalized = text.strip()
    if STUDY_COMMAND_RE.match(normalized):
        return True
    return is_button_press(text, 'Training')


def is_refresh_request(text):
    if not text:
        return False
    if is_start_command(text):
        return False
    normalized = text.strip()
    if normalized == '/refresh':
        return True
    return is_button_press(text, 'Refresh')


def get_main_reply_keyboard():
    return {
        'keyboard': [
            [
                {'text': str(_('My tasks'))},
                {'text': str(_('For approval'))},
            ],
            [
                {'text': str(_('Training'))},
                {'text': str(_('Help'))},
            ],
            [
                {'text': str(_('Refresh'))},
            ],
        ],
        'resize_keyboard': True,
    }


def get_reply_markup_for_chat(bot, chat_id):
    if get_cabinet_user_for_telegram(bot, chat_id):
        return get_main_reply_keyboard()
    return get_login_inline_keyboard(bot, chat_id)


def get_start_reply_text(bot, chat_id=None):
    if bot.start_message.strip():
        return bot.start_message.strip()

    lines = [
        _('Hello! You are connected to the SecBoard bot "%(name)s".') % {'name': bot.name},
        _('Company: %(company)s') % {'company': bot.company.name},
    ]
    if chat_id is not None:
        lines.append(_('Your Chat ID: %(chat_id)s') % {'chat_id': chat_id})
    if chat_id is not None and not get_cabinet_user_for_telegram(bot, chat_id):
        lines.append(
            _('Tap the button below to sign in to SecBoard and link your Telegram account automatically.'),
        )
    else:
        lines.append(_('Use this Chat ID in SecBoard integration settings for notifications.'))
        lines.append(_('Use the menu below: My tasks, For approval, Training, Help, or Refresh.'))
    return '\n'.join(lines)


def get_help_reply_text(bot, chat_id):
    lines = [
        _('Help'),
        '',
        _('This bot is used to receive notifications from SecBoard.'),
        _('Bot: %(name)s') % {'name': bot.name},
        _('Company: %(company)s') % {'company': bot.company.name},
        '',
        _('My Chat ID: %(chat_id)s') % {'chat_id': chat_id},
    ]
    if get_cabinet_user_for_telegram(bot, chat_id):
        lines.extend([
            _('Copy this Chat ID into SecBoard integration settings to receive notifications.'),
            _('Or open Personal cabinet → Profile and tap Link Telegram to connect automatically.'),
        ])
    else:
        lines.append(
            _('Tap the button below to sign in to SecBoard and link your Telegram account automatically.'),
        )
    lines.append(_('Tap Refresh to show the welcome message again.'))
    return '\n'.join(lines)


def _maybe_save_default_chat_id(bot, chat_id):
    chat_id_str = str(chat_id)
    if not bot.default_chat_id:
        bot.default_chat_id = chat_id_str
        bot.save(update_fields=['default_chat_id'])


def _send_reply(bot, chat_id, reply_text, parse_mode=None, reply_markup=None):
    send_message(
        bot.bot_token,
        chat_id,
        reply_text,
        parse_mode=parse_mode,
        reply_markup=reply_markup or get_reply_markup_for_chat(bot, chat_id),
    )
    _maybe_save_default_chat_id(bot, chat_id)


def _send_localized_reply(bot, chat_id, reply_builder, message=None, *args, **kwargs):
    with telegram_language(bot, chat_id, message=message):
        result = reply_builder(*args, **kwargs)
        if isinstance(result, tuple):
            reply_text, parse_mode = result
        else:
            reply_text, parse_mode = result, None
        _send_reply(
            bot,
            chat_id,
            reply_text,
            parse_mode=parse_mode,
            reply_markup=get_reply_markup_for_chat(bot, chat_id),
        )


def process_telegram_update(bot, update):
    """Обробити вхідне оновлення від Telegram. Повертає True, якщо оновлення оброблено."""
    message = update.get('message') or update.get('edited_message')
    if not message or not bot.respond_to_start:
        return False

    text = message.get('text', '')
    chat = message.get('chat') or {}
    chat_id = chat.get('id')
    if chat_id is None:
        return False

    if is_start_command(text) or is_refresh_request(text):
        if is_start_command(text) and parse_start_payload(text):
            if process_telegram_account_link(bot, message):
                _maybe_save_default_chat_id(bot, chat_id)
                logger.info('Linked Telegram account for bot %s, chat_id=%s', bot.name, chat_id)
                return True
        _send_localized_reply(bot, chat_id, get_start_reply_text, message, bot, chat_id)
        action = 'refresh' if is_refresh_request(text) else 'start'
        logger.info('Replied to %s for bot %s, chat_id=%s', action, bot.name, chat_id)
        return True

    if is_help_request(text):
        _send_localized_reply(bot, chat_id, get_help_reply_text, message, bot, chat_id)
        logger.info('Replied to help for bot %s, chat_id=%s', bot.name, chat_id)
        return True

    if is_tasks_request(text):
        _send_localized_reply(bot, chat_id, build_my_tasks_reply_text, message, bot, chat_id)
        logger.info('Replied to tasks for bot %s, chat_id=%s', bot.name, chat_id)
        return True

    if is_approvals_request(text):
        _send_localized_reply(bot, chat_id, build_approvals_reply_text, message, bot, chat_id)
        logger.info('Replied to approvals for bot %s, chat_id=%s', bot.name, chat_id)
        return True

    if is_training_request(text):
        _send_localized_reply(bot, chat_id, build_training_reply_text, message, bot, chat_id)
        logger.info('Replied to training for bot %s, chat_id=%s', bot.name, chat_id)
        return True

    return False
