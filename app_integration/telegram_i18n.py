from contextlib import contextmanager

from django.conf import settings
from django.utils import translation
from django.utils.translation import check_for_language, gettext

_BUTTON_LABEL_CACHE = {}


def get_language_for_cabinet_user(cabinet_user):
    if cabinet_user:
        language = (cabinet_user.preferred_language or '').strip()
        if language and check_for_language(language):
            return language
    return settings.LANGUAGE_CODE


def _language_from_telegram_user(message):
    from_user = (message or {}).get('from') or {}
    tg_lang = (from_user.get('language_code') or '').strip().lower()
    if not tg_lang:
        return None
    if check_for_language(tg_lang):
        return tg_lang
    short = tg_lang.split('-')[0]
    if check_for_language(short):
        return short
    return None


def get_language_for_telegram_chat(bot, chat_id, message=None, cabinet_user=None):
    if cabinet_user is None:
        from .telegram_tasks import get_cabinet_user_for_telegram

        cabinet_user = get_cabinet_user_for_telegram(bot, chat_id)
    if cabinet_user:
        language = (cabinet_user.preferred_language or '').strip()
        if language and check_for_language(language):
            return language
    tg_lang = _language_from_telegram_user(message)
    if tg_lang:
        return tg_lang
    return settings.LANGUAGE_CODE


def get_telegram_language_code(bot, chat_id, message=None):
    return get_language_for_telegram_chat(bot, chat_id, message=message)


def localized_button_labels(msgid):
    if msgid not in _BUTTON_LABEL_CACHE:
        labels = {msgid}
        for language_code, _language_name in settings.LANGUAGES:
            with translation.override(language_code):
                labels.add(str(gettext(msgid)))
        _BUTTON_LABEL_CACHE[msgid] = frozenset(labels)
    return _BUTTON_LABEL_CACHE[msgid]


def is_button_press(text, msgid):
    if not text:
        return False
    return text.strip() in localized_button_labels(msgid)


@contextmanager
def telegram_language(bot, chat_id, cabinet_user=None, message=None):
    if cabinet_user is None:
        from .telegram_tasks import get_cabinet_user_for_telegram

        cabinet_user = get_cabinet_user_for_telegram(bot, chat_id)
    language_code = get_language_for_telegram_chat(
        bot, chat_id, message=message, cabinet_user=cabinet_user,
    )
    with translation.override(language_code):
        yield language_code
