from django.urls import reverse
from django.utils.translation import gettext as _

from .telegram_link import get_telegram_auth_login_url
from .utils import get_public_base_url


def get_cabinet_user_for_telegram(bot, chat_id):
    from app_cabinet.models import CabinetUser

    chat_id_str = str(chat_id).strip()
    if not chat_id_str:
        return None
    return (
        CabinetUser.objects.filter(
            telegram_chat_id=chat_id_str,
            company=bot.company,
        )
        .select_related('user')
        .first()
    )


def get_secboard_login_link(bot, chat_id):
    return get_telegram_auth_login_url(bot, chat_id)


def get_login_inline_keyboard(bot, chat_id):
    return {
        'inline_keyboard': [[
            {'text': str(_('Sign in to SecBoard')), 'url': get_secboard_login_link(bot, chat_id)},
        ]],
    }


def _build_not_linked_reply_text(title, chat_id):
    return '\n'.join([
        title,
        '',
        _('Your Telegram account is not linked to SecBoard yet.'),
        _('My Chat ID: %(chat_id)s') % {'chat_id': chat_id},
        _('Tap the button below to sign in to SecBoard and link your Telegram account automatically.'),
    ])


def _get_cabinet_link():
    base = get_public_base_url()
    path = reverse('personal_cabinet')
    return f'{base}{path}' if base else path


def build_my_tasks_reply_text(bot, chat_id):
    from app_cabinet.task_reminder_utils import build_task_reminder_plain_body

    cabinet_user = get_cabinet_user_for_telegram(bot, chat_id)
    if cabinet_user:
        return build_task_reminder_plain_body(cabinet_user)

    return _build_not_linked_reply_text(_('My tasks'), chat_id)


def build_approvals_reply_text(bot, chat_id):
    cabinet_user = get_cabinet_user_for_telegram(bot, chat_id)
    if not cabinet_user:
        return _build_not_linked_reply_text(_('For approval'), chat_id)

    from app_cabinet.views import get_tasks_context_for_cabinet_user

    ctx = get_tasks_context_for_cabinet_user(cabinet_user)
    access_requests = ctx.get('access_requests_tasks_approve', [])
    documents = ctx.get('document_approve_tasks', [])
    total = len(access_requests) + len(documents)

    lines = [
        _('For approval'),
        '',
    ]
    if total == 0:
        lines.append(_('There are no items waiting for your approval.'))
        return '\n'.join(lines)

    lines.append(_('You have %(n)s item(s) waiting for approval.') % {'n': total})
    lines.append('')

    if access_requests:
        lines.append(_('Access requests (%(n)s):') % {'n': len(access_requests)})
        for request in access_requests[:10]:
            system_name = request.system.name if request.system_id else '—'
            user_name = request.requested_for.get_full_name() or request.requested_for.username
            lines.append(
                f'  • #{request.pk} {request.get_request_type_display()} — {system_name} ({user_name})',
            )
        if len(access_requests) > 10:
            lines.append(_('  … and %(n)s more') % {'n': len(access_requests) - 10})
        lines.append('')

    if documents:
        lines.append(_('Documents (%(n)s):') % {'n': len(documents)})
        for document in documents[:10]:
            lines.append(f'  • {document.name_doc}')
        if len(documents) > 10:
            lines.append(_('  … and %(n)s more') % {'n': len(documents) - 10})
        lines.append('')

    lines.append(_('Open your personal cabinet: %(url)s') % {'url': _get_cabinet_link()})
    return '\n'.join(lines)
