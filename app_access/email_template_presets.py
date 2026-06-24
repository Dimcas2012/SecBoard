# SecBoard/app_access/email_template_presets.py
"""Typical email notification presets for Grant / Revoke access requests."""

from django.template import Context, Template
from django.template.loader import get_template, render_to_string
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

REQUEST_CREATED_TEMPLATE_PATHS = {
    'grant': {
        'html': 'app_access/emails/presets/grant_request_created.html',
        'text': 'app_access/emails/presets/grant_request_created.txt',
    },
    'revoke': {
        'html': 'app_access/emails/presets/revoke_request_created.html',
        'text': 'app_access/emails/presets/revoke_request_created.txt',
    },
}

STATUS_CHANGED_TEMPLATE_PATHS = {
    'html': 'app_access/emails/access_request_status_update.html',
    'text': 'app_access/emails/access_request_status_update.txt',
}


def _load_template_source(template_name: str) -> str:
    return get_template(template_name).template.source


def _status_changed_template_bundle():
    return {
        'subject': str(_lazy('Request Status Changed - {{ company_name }} / {{ system_name }}')),
        'html': _load_template_source(STATUS_CHANGED_TEMPLATE_PATHS['html']),
        'text': _load_template_source(STATUS_CHANGED_TEMPLATE_PATHS['text']),
    }


def get_email_template_presets():
    """
    Presets for Email Templates Management (request created notifications).
    Recipients flags align with EmailNotificationConfig recipient checkboxes.
    """
    status_changed = _status_changed_template_bundle()
    return [
        {
            'id': 'grant',
            'title': str(_lazy('Grant Access Request')),
            'description': str(_lazy(
                'Use when users submit requests to grant new access. '
                'Approvers are notified by level; administrators after full approver approval.'
            )),
            'config_name_suggestion': str(_lazy('Grant Access Request Notifications')),
            'recipients': {
                'send_to_owners': True,
                'send_to_administrators': True,
                'send_to_requested_by': True,
                'send_to_requested_for': False,
                'send_to_approving_persons': True,
                'send_to_third_party': False,
            },
            'triggers': {
                'trigger_on_request_created': True,
                'trigger_on_status_changed': True,
                'trigger_on_admin_status_changed': True,
            },
            'request_created': {
                'subject': str(_lazy('Grant Access Request - {{ company_name }} / {{ system_name }}')),
                'html': _load_template_source(REQUEST_CREATED_TEMPLATE_PATHS['grant']['html']),
                'text': _load_template_source(REQUEST_CREATED_TEMPLATE_PATHS['grant']['text']),
            },
            'status_changed': status_changed,
        },
        {
            'id': 'revoke',
            'title': str(_lazy('Revoke Access')),
            'description': str(_lazy(
                'Use when users submit requests to revoke existing access. '
                'Approvers by level; administrators after full approval. '
                'Also notify the user whose access is being revoked (Requested For).'
            )),
            'config_name_suggestion': str(_lazy('Revoke Access Request Notifications')),
            'recipients': {
                'send_to_owners': True,
                'send_to_administrators': True,
                'send_to_requested_by': True,
                'send_to_requested_for': True,
                'send_to_approving_persons': True,
                'send_to_third_party': False,
            },
            'triggers': {
                'trigger_on_request_created': True,
                'trigger_on_status_changed': True,
                'trigger_on_admin_status_changed': True,
            },
            'request_created': {
                'subject': str(_lazy('Revoke Access Request - {{ company_name }} / {{ system_name }}')),
                'html': _load_template_source(REQUEST_CREATED_TEMPLATE_PATHS['revoke']['html']),
                'text': _load_template_source(REQUEST_CREATED_TEMPLATE_PATHS['revoke']['text']),
            },
            'status_changed': status_changed,
        },
    ]


def get_preset_by_notification_type(notification_type):
    """Return preset dict for grant/revoke; defaults to grant."""
    for preset in get_email_template_presets():
        if preset['id'] == notification_type:
            return preset
    return get_email_template_presets()[0]


def _render_subject(subject_template: str, context: dict) -> str:
    if not subject_template:
        return ''
    return Template(subject_template).render(Context(context))


def _default_subject(config, template_kind: str, context: dict, status_type: str = 'approver') -> str:
    notification_type = getattr(config, 'notification_type', None) or 'grant'
    preset = get_preset_by_notification_type(notification_type)
    if template_kind == 'status_changed':
        if status_type == 'admin':
            return _('Admin Status Changed - {company_name} / {system_name}').format(**context)
        bundle = preset.get('status_changed') or _status_changed_template_bundle()
        return _render_subject(bundle['subject'], context) or _(
            'Request Status Changed - {company_name} / {system_name}'
        ).format(**context)
    bundle = preset['request_created']
    return _render_subject(bundle['subject'], context) or _(
        'New Access Request - {company_name} / {system_name}'
    ).format(**context)


def render_notification_email_content(config, template_kind: str, context: dict, status_type: str = 'approver'):
    """
    Render subject, HTML and plain text for an outgoing notification.

    Uses custom fields from config when use_custom_templates is True; otherwise
    uses Email Templates Management presets for the config notification_type (grant/revoke).
    """
    is_status = template_kind == 'status_changed'
    notification_type = getattr(config, 'notification_type', None) or 'grant'
    preset = get_preset_by_notification_type(notification_type)
    ctx = Context(context)

    if config.use_custom_templates:
        if is_status:
            subject_tpl = config.status_changed_subject_template or ''
            html_tpl = config.status_changed_html_template or ''
            text_tpl = config.status_changed_text_template or ''
        else:
            subject_tpl = config.request_created_subject_template or ''
            html_tpl = config.request_created_html_template or ''
            text_tpl = config.request_created_text_template or ''

        subject = Template(subject_tpl).render(ctx) if subject_tpl else ''
        html_content = Template(html_tpl).render(ctx) if html_tpl else ''
        text_content = Template(text_tpl).render(ctx) if text_tpl else ''

        if not html_content and not text_content:
            return render_notification_email_content(
                _config_with_custom_disabled(config),
                template_kind,
                context,
                status_type=status_type,
            )
        if not subject:
            subject = _default_subject(config, template_kind, context, status_type)
        return subject, html_content, text_content

    if is_status:
        html_content = render_to_string(STATUS_CHANGED_TEMPLATE_PATHS['html'], context)
        text_content = render_to_string(STATUS_CHANGED_TEMPLATE_PATHS['text'], context)
    else:
        paths = REQUEST_CREATED_TEMPLATE_PATHS.get(
            notification_type, REQUEST_CREATED_TEMPLATE_PATHS['grant']
        )
        html_content = render_to_string(paths['html'], context)
        text_content = render_to_string(paths['text'], context)

    subject = _default_subject(config, template_kind, context, status_type)
    return subject, html_content, text_content


def _config_with_custom_disabled(config):
    """Shallow stand-in to fall back to preset file templates when custom bodies are empty."""

    class _ConfigProxy:
        use_custom_templates = False
        notification_type = config.notification_type

    return _ConfigProxy()
