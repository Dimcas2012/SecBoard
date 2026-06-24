import django.db.models.deletion
from django.db import connection, migrations, models


def add_periodic_task_column_if_missing(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'app_access_scheduledsync' AND COLUMN_NAME = 'periodic_task_id'
            """
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                """
                ALTER TABLE app_access_scheduledsync
                ADD COLUMN periodic_task_id BIGINT NULL UNIQUE,
                ADD CONSTRAINT app_access_scheduledsync_periodic_task_id_fk
                FOREIGN KEY (periodic_task_id) REFERENCES django_celery_beat_periodictask(id) ON DELETE SET NULL
                """
            )


class Migration(migrations.Migration):

    dependencies = [
        ('app_access', '0004_system_role_function_right_mapping'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_periodic_task_column_if_missing,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='scheduledsync',
                    name='periodic_task',
                    field=models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to='django_celery_beat.periodictask',
                        verbose_name='Periodic Task',
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='ObjectRoleFunctionRightMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('access_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_function_right_mappings', to='app_access.accessobjectis', verbose_name='Access Object')),
                ('access_right', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='object_role_function_mappings', to='app_access.accessright', verbose_name='Access Right')),
                ('function', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='object_role_right_mappings', to='app_access.accessfunctionis', verbose_name='Function')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='object_function_right_mappings', to='app_access.accessroles', verbose_name='Access Role')),
            ],
            options={
                'verbose_name': 'Object Role Function Right Mapping',
                'verbose_name_plural': 'Object Role Function Right Mappings',
                'ordering': ['access_object', 'role', 'function', 'access_right'],
            },
        ),
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
        migrations.DeleteModel(
            name='SystemRoleFunctionRightMapping',
        ),
        migrations.AddConstraint(
            model_name='objectrolefunctionrightmapping',
            constraint=models.UniqueConstraint(fields=('access_object', 'role', 'function', 'access_right'), name='unique_object_role_function_right'),
        ),
        migrations.AddConstraint(
            model_name='rolefunctionrightmapping',
            constraint=models.UniqueConstraint(fields=('role', 'function', 'access_right'), name='unique_role_function_right'),
        ),
    ]
