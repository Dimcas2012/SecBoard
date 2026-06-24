import os

from django.conf import settings
from django.db import migrations, models

import app_cabinet.models


def fix_missing_avatar_paths(apps, schema_editor):
    CabinetUser = apps.get_model('app_cabinet', 'CabinetUser')
    avatars_dir = os.path.join(settings.MEDIA_ROOT, 'user_avatars')
    if not os.path.isdir(avatars_dir):
        return

    available_files = os.listdir(avatars_dir)
    for cabinet_user in CabinetUser.objects.exclude(avatar=''):
        stored_name = cabinet_user.avatar.name if hasattr(cabinet_user.avatar, 'name') else str(cabinet_user.avatar)
        if not stored_name:
            continue
        if os.path.exists(os.path.join(settings.MEDIA_ROOT, stored_name)):
            continue

        stored_base = os.path.basename(stored_name)
        hash_prefix = stored_base.split('_', 1)[0] if '_' in stored_base else stored_base
        candidates = sorted(
            [name for name in available_files if name.startswith(hash_prefix)],
            key=len,
            reverse=True,
        )
        if not candidates:
            continue

        cabinet_user.avatar = f'user_avatars/{candidates[0]}'
        cabinet_user.save(update_fields=['avatar'])


class Migration(migrations.Migration):

    dependencies = [
        ('app_cabinet', '0011_cabinetuser_preferred_language'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cabinetuser',
            name='avatar',
            field=models.ImageField(
                blank=True,
                max_length=255,
                null=True,
                upload_to=app_cabinet.models.cabinet_user_avatar_upload_to,
                verbose_name='Avatar',
            ),
        ),
        migrations.RunPython(fix_missing_avatar_paths, migrations.RunPython.noop),
    ]
