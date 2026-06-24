# SecBoard/app_access/email_template_preview.py
"""Sample context and rendering for email template preview."""

from datetime import date, timedelta
from types import SimpleNamespace

from django.template import Context, Template
from django.utils.translation import gettext as _


def get_sample_email_context(preset_kind='grant'):
    """
    Build a context dict matching send_access_request_notification / status templates.
    preset_kind: 'grant' | 'revoke'
    """
    roles = [
        SimpleNamespace(name='SalesManager', color='#6c757d'),
        SimpleNamespace(name='SupportManager', color='#17a2b8'),
        SimpleNamespace(name='MerchantAccountant', color='#198754'),
    ]
    access_records_data = [
        SimpleNamespace(
            object_name='AvansCredit',
            object_color='#0d6efd',
            roles=roles,
            environment='test',
        ),
    ]
    access_request = SimpleNamespace(id=14, environment='test')

    if preset_kind == 'revoke':
        request_type = str(_('Revoke Access'))
        requested_for = str(_('Julia Solodovnikova'))
    else:
        request_type = str(_('Grant Access'))
        requested_for = str(_('Julia Solodovnikova'))

    start = date.today()
    return {
        'access_request': access_request,
        'recipient_name': str(_('Dmytro Senchenko')),
        'recipient_role': str(_('Requested By')),
        'company_name': 'Demo Company',
        'system_name': 'AvansCredit',
        'object_name': 'AvansCredit',
        'access_records_data': access_records_data,
        'has_multiple_objects': False,
        'environment': str(_('Test')),
        'requested_for': requested_for,
        'requested_by': str(_('Dmytro Senchenko')),
        'justification': str(_(
            'Temporary access is required for project execution and collaboration '
            'within the approved project scope.'
        )),
        'requirements': '',
        'notes': '',
        'start_date': start,
        'end_date': None,
        'roles': roles,
        'request_type': request_type,
        'site_domain': 'localhost',
        'site_protocol': 'http',
        'has_third_party': False,
        'third_party_name': '',
        'third_party_users': [],
        'third_party_count': 0,
        'third_party_first_name': '',
        'third_party_last_name': '',
        'third_party_email': '',
        'third_party_phone': '',
        'third_party_organization': '',
        'third_party_description': '',
        'include_third_party_info': True,
        'old_status': str(_('Pending')),
        'new_status': str(_('Approved')),
        'changed_by': str(_('System Administrator')),
        'comment': str(_('Approved for project timeline.')),
        'status_type': 'approver',
    }


def render_template_string(template_source, context):
    if not template_source or not str(template_source).strip():
        return ''
    return Template(template_source).render(Context(context))


def render_email_preview(subject='', html='', text='', preset_kind='grant'):
    context = get_sample_email_context(preset_kind)
    return {
        'subject': render_template_string(subject, context),
        'html': render_template_string(html, context),
        'text': render_template_string(text, context),
    }
