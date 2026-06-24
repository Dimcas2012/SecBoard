# Data migration: populate Software Categories, Software Statuses, External Media Categories, External Media Statuses

from django.db import migrations


def populate_software_categories(apps, schema_editor):
    SoftwareCategory = apps.get_model('app_asset', 'SoftwareCategory')
    categories = [
        {'code': 'os', 'name': 'Operating System', 'color': '#007bff', 'display_order': 10, 'description': 'OS (Windows, Linux, macOS, etc.)'},
        {'code': 'office', 'name': 'Office Suite', 'color': '#28a745', 'display_order': 20, 'description': 'Office and productivity software'},
        {'code': 'antivirus', 'name': 'Antivirus / Security', 'color': '#dc3545', 'display_order': 30, 'description': 'Antivirus and security tools'},
        {'code': 'browser', 'name': 'Browser', 'color': '#17a2b8', 'display_order': 40, 'description': 'Web browsers'},
        {'code': 'dev', 'name': 'Development Tools', 'color': '#6f42c1', 'display_order': 50, 'description': 'IDEs, compilers, version control'},
        {'code': 'other', 'name': 'Other', 'color': '#6c757d', 'display_order': 999, 'description': 'Other software'},
    ]
    for item in categories:
        SoftwareCategory.objects.get_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'color': item['color'],
                'display_order': item['display_order'],
                'description': item.get('description', ''),
                'is_active': True,
            }
        )


def populate_software_statuses(apps, schema_editor):
    SoftwareStatus = apps.get_model('app_asset', 'SoftwareStatus')
    statuses = [
        {'code': 'allowed', 'name': 'Allowed', 'color': '#28a745', 'display_order': 10},
        {'code': 'forbidden', 'name': 'Forbidden', 'color': '#dc3545', 'display_order': 20},
        {'code': 'under_review', 'name': 'Under review', 'color': '#ffc107', 'display_order': 30},
    ]
    for item in statuses:
        SoftwareStatus.objects.get_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'color': item['color'],
                'display_order': item['display_order'],
                'is_active': True,
            }
        )


def populate_external_media_categories(apps, schema_editor):
    ExternalMediaCategory = apps.get_model('app_asset', 'ExternalMediaCategory')
    categories = [
        {'code': 'usb', 'name': 'USB drive', 'color': '#17a2b8', 'display_order': 10},
        {'code': 'hdd', 'name': 'External HDD', 'color': '#007bff', 'display_order': 20},
        {'code': 'ssd', 'name': 'External SSD', 'color': '#28a745', 'display_order': 30},
        {'code': 'cd_dvd', 'name': 'CD/DVD', 'color': '#6c757d', 'display_order': 40},
        {'code': 'memory_card', 'name': 'Memory card', 'color': '#fd7e14', 'display_order': 50},
        {'code': 'other', 'name': 'Other', 'color': '#6c757d', 'display_order': 999},
    ]
    for item in categories:
        ExternalMediaCategory.objects.get_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'color': item['color'],
                'display_order': item['display_order'],
                'is_active': True,
            }
        )


def populate_external_media_statuses(apps, schema_editor):
    ExternalMediaStatus = apps.get_model('app_asset', 'ExternalMediaStatus')
    statuses = [
        {'code': 'allowed', 'name': 'Allowed', 'color': '#28a745', 'display_order': 10},
        {'code': 'forbidden', 'name': 'Forbidden', 'color': '#dc3545', 'display_order': 20},
        {'code': 'under_review', 'name': 'Under review', 'color': '#ffc107', 'display_order': 30},
    ]
    for item in statuses:
        ExternalMediaStatus.objects.get_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'color': item['color'],
                'display_order': item['display_order'],
                'is_active': True,
            }
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('app_asset', '0009_external_media_register'),
    ]

    operations = [
        migrations.RunPython(populate_software_categories, noop),
        migrations.RunPython(populate_software_statuses, noop),
        migrations.RunPython(populate_external_media_categories, noop),
        migrations.RunPython(populate_external_media_statuses, noop),
    ]
