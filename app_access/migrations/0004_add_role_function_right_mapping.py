# Generated manually for per-role system matrix mappings

import django.db.models.deletion
from django.db import migrations, models


def populate_role_function_right_mapping(apps, schema_editor):
    """Copy existing function.access_rights into RoleFunctionRightMapping per role."""
    AccessRoles = apps.get_model('app_access', 'AccessRoles')
    AccessFunctionIS = apps.get_model('app_access', 'AccessFunctionIS')
    RoleFunctionRightMapping = apps.get_model('app_access', 'RoleFunctionRightMapping')
    for role in AccessRoles.objects.prefetch_related('functions').filter(is_object_specific=False):
        for func in role.functions.filter(is_object_specific=False):
            for right in func.access_rights.all():
                RoleFunctionRightMapping.objects.get_or_create(
                    role_id=role.id,
                    function_id=func.id,
                    access_right_id=right.id,
                    defaults={'is_active': True}
                )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('app_access', '0003_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoleFunctionRightMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('access_right', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_function_mappings', to='app_access.accessright', verbose_name='Access Right')),
                ('function', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_right_mappings', to='app_access.accessfunctionis', verbose_name='Function')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='function_right_mappings', to='app_access.accessroles', verbose_name='Access Role')),
            ],
            options={
                'verbose_name': 'Role Function Right Mapping',
                'verbose_name_plural': 'Role Function Right Mappings',
                'ordering': ['role', 'function', 'access_right'],
            },
        ),
        migrations.AddConstraint(
            model_name='rolefunctionrightmapping',
            constraint=models.UniqueConstraint(fields=('role', 'function', 'access_right'), name='unique_role_function_right'),
        ),
        migrations.RunPython(populate_role_function_right_mapping, noop_reverse),
    ]
