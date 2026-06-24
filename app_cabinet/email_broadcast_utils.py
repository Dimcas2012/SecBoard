"""Send bulk emails to cabinet users from Users Management."""

import logging

from django.utils.html import strip_tags
from django.utils import translation
from django.utils.translation import gettext as _

from app_integration.telegram_i18n import get_language_for_cabinet_user

logger = logging.getLogger(__name__)

MESSAGE_TYPE_CUSTOM = 'custom'
MESSAGE_TYPE_TASKS = 'tasks'
EMAIL_BROADCAST_MAX_HTML_LENGTH = 50000


def _custom_message_has_content(html_body):
    return bool(strip_tags(html_body or '').strip())

def _build_broadcast_body(cabinet_user, message_type, custom_text=''):
    if message_type == MESSAGE_TYPE_TASKS:
        from app_cabinet.task_reminder_utils import build_task_reminder_plain_body

        language = get_language_for_cabinet_user(cabinet_user)
        with translation.override(language):
            return build_task_reminder_plain_body(cabinet_user)
    return (custom_text or '').strip()


def _build_broadcast_subject(cabinet_user, message_type, custom_subject=''):
    if message_type == MESSAGE_TYPE_TASKS:
        language = get_language_for_cabinet_user(cabinet_user)
        with translation.override(language):
            return str(_('SecBoard: reminder about your tasks'))
    return (custom_subject or '').strip()


def send_email_broadcast_for_user_ids(
    cabinet_user_ids,
    message_type=MESSAGE_TYPE_CUSTOM,
    custom_subject='',
    custom_text='',
):
    from app_cabinet.models import CabinetSettings, CabinetUser
    from app_cabinet.views import send_email

    sent = 0
    skipped = 0
    errors = []

    if message_type == MESSAGE_TYPE_CUSTOM:
        if not (custom_subject or '').strip():
            return 0, 0, [_('Subject is required.')]
        if not _custom_message_has_content(custom_text):
            return 0, 0, [_('Message text is required.')]

    settings_row = CabinetSettings.objects.first()
    account = settings_row.mail_account if settings_row else None
    if not account:
        return 0, 0, [_('Cabinet mail account is not configured in Cabinet Settings.')]

    cabinet_users = list(
        CabinetUser.objects.filter(pk__in=cabinet_user_ids)
        .select_related('user', 'company')
        .order_by('user__last_name', 'user__first_name')
    )

    for cabinet_user in cabinet_users:
        display_name = cabinet_user.user.get_full_name() or cabinet_user.user.username
        email_addr = (cabinet_user.user.email or '').strip()
        if not email_addr:
            skipped += 1
            errors.append(_('%(name)s: no email address.') % {'name': display_name})
            continue

        try:
            body = _build_broadcast_body(cabinet_user, message_type, custom_text)
            if not body:
                skipped += 1
                errors.append(_('%(name)s: empty message.') % {'name': display_name})
                continue
            subject = _build_broadcast_subject(cabinet_user, message_type, custom_subject)
            send_as_html = message_type == MESSAGE_TYPE_CUSTOM
            ok, msg = send_email(account, email_addr, subject, body, html=send_as_html)
            if ok:
                sent += 1
            else:
                skipped += 1
                errors.append(f'{display_name}: {msg}')
        except Exception as exc:
            skipped += 1
            errors.append(f'{display_name}: {exc}')
            logger.warning('Email broadcast failed for cabinet user %s: %s', cabinet_user.pk, exc)

    return sent, skipped, errors
