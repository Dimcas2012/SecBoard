import logging

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = 'https://api.telegram.org/bot{token}/{method}'


class TelegramAPIError(Exception):
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


def _call_telegram_api(bot_token, method, payload=None, timeout=15):
    url = TELEGRAM_API_BASE.format(token=bot_token, method=method)
    try:
        response = requests.post(url, json=payload or {}, timeout=timeout)
    except requests.RequestException as exc:
        raise TelegramAPIError(str(exc)) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise TelegramAPIError(
            f'Invalid JSON response (HTTP {response.status_code})',
            status_code=response.status_code,
        ) from exc

    if not data.get('ok'):
        description = data.get('description', 'Unknown Telegram API error')
        raise TelegramAPIError(description, status_code=response.status_code, response_data=data)

    return data.get('result', {})


def test_bot_connection(bot_token):
    """Перевірити токен бота через getMe."""
    result = _call_telegram_api(bot_token, 'getMe')
    return {
        'bot_id': result.get('id'),
        'bot_username': result.get('username', ''),
        'first_name': result.get('first_name', ''),
        'can_join_groups': result.get('can_join_groups'),
        'can_read_all_group_messages': result.get('can_read_all_group_messages'),
    }


def send_message(bot_token, chat_id, text, parse_mode=None, reply_markup=None):
    payload = {'chat_id': str(chat_id), 'text': str(text)}
    if parse_mode:
        payload['parse_mode'] = parse_mode
    if reply_markup:
        payload['reply_markup'] = reply_markup
    return _call_telegram_api(bot_token, 'sendMessage', payload)


def get_webhook_info(bot_token):
    return _call_telegram_api(bot_token, 'getWebhookInfo')


def get_updates(bot_token, offset=None, timeout=0):
    payload = {
        'timeout': timeout,
        'allowed_updates': ['message', 'edited_message'],
    }
    if offset is not None:
        payload['offset'] = offset
    return _call_telegram_api(bot_token, 'getUpdates', payload)


def set_webhook(bot_token, webhook_url, secret_token=None, drop_pending_updates=False):
    payload = {
        'url': webhook_url,
        'drop_pending_updates': drop_pending_updates,
        'allowed_updates': ['message', 'edited_message'],
    }
    if secret_token:
        payload['secret_token'] = secret_token
    return _call_telegram_api(bot_token, 'setWebhook', payload)


def delete_webhook(bot_token):
    return _call_telegram_api(bot_token, 'deleteWebhook', {'drop_pending_updates': True})


def sync_bot_webhook(bot, webhook_url):
    """Увімкнути або вимкнути webhook залежно від налаштувань бота."""
    if bot.use_webhook or bot.respond_to_start:
        if not webhook_url.startswith('https://'):
            raise TelegramAPIError(
                'Telegram requires an HTTPS webhook URL. '
                f'Configure Site Settings with a public HTTPS domain (got: {webhook_url}).',
            )
        return set_webhook(
            bot.bot_token,
            webhook_url,
            bot.webhook_secret or None,
            drop_pending_updates=False,
        )
    return delete_webhook(bot.bot_token)


def format_webhook_info(info):
    last_error = info.get('last_error_message')
    last_error_date = info.get('last_error_date')
    return {
        'url': info.get('url') or '',
        'pending_update_count': info.get('pending_update_count', 0),
        'last_error_message': last_error or '',
        'last_error_date': last_error_date,
        'has_webhook': bool(info.get('url')),
    }


def update_bot_connection_status(bot, success, bot_info=None):
    bot.last_connection_check = timezone.now()
    bot.last_connection_ok = success
    update_fields = ['last_connection_check', 'last_connection_ok']
    if success and bot_info:
        bot.bot_username = bot_info.get('bot_username') or ''
        bot.bot_id = bot_info.get('bot_id')
        update_fields.extend(['bot_username', 'bot_id'])
    bot.save(update_fields=update_fields)
