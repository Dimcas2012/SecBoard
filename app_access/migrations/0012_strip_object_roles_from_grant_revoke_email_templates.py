# Generated manually on 2026-06-17

from django.db import migrations


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

OBJECT_ROLES_MARKERS = (
    'access_records_data',
    'Object Roles',
    'Access to revoke',
    'record.object_name',
    'object_name !=',
)


def _template_contains_object_roles(content):
    if not content:
        return False
    return any(marker in content for marker in OBJECT_ROLES_MARKERS)


def strip_object_roles_from_custom_templates(apps, schema_editor):
    from django.template.loader import get_template

    EmailNotificationConfig = apps.get_model('app_access', 'EmailNotificationConfig')

    for config in EmailNotificationConfig.objects.filter(
        notification_type__in=('grant', 'revoke'),
        use_custom_templates=True,
    ):
        html = config.request_created_html_template or ''
        text = config.request_created_text_template or ''
        if not (_template_contains_object_roles(html) or _template_contains_object_roles(text)):
            continue

        paths = REQUEST_CREATED_TEMPLATE_PATHS.get(config.notification_type)
        if not paths:
            continue

        config.request_created_html_template = get_template(paths['html']).template.source
        config.request_created_text_template = get_template(paths['text']).template.source
        config.save(update_fields=[
            'request_created_html_template',
            'request_created_text_template',
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('app_access', '0011_emailnotificationconfig_notification_type'),
    ]

    operations = [
        migrations.RunPython(
            strip_object_roles_from_custom_templates,
            migrations.RunPython.noop,
        ),
    ]
