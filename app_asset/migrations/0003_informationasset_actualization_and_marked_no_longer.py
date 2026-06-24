from django.conf import settings
from django.db import connection, migrations, models


def add_columns_if_missing(apps, schema_editor):
    table = 'app_asset_informationasset'
    user_model = apps.get_model(settings.AUTH_USER_MODEL)
    user_table = user_model._meta.db_table

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            """,
            [table],
        )
        existing = {row[0] for row in cursor.fetchall()}

    with connection.cursor() as cursor:
        if 'actualization_date' not in existing:
            cursor.execute(
                f'ALTER TABLE {table} ADD COLUMN actualization_date DATETIME(6) NULL'
            )
        if 'actualized_by_id' not in existing:
            cursor.execute(
                f"""
                ALTER TABLE {table}
                ADD COLUMN actualized_by_id BIGINT NULL,
                ADD CONSTRAINT app_asset_informationasset_actualized_by_id_fk
                FOREIGN KEY (actualized_by_id) REFERENCES {user_table}(id) ON DELETE SET NULL
                """
            )
        if 'marked_no_longer_actual_at' not in existing:
            cursor.execute(
                f'ALTER TABLE {table} ADD COLUMN marked_no_longer_actual_at DATETIME(6) NULL'
            )
        if 'marked_no_longer_comment' not in existing:
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN marked_no_longer_comment LONGTEXT NOT NULL DEFAULT ''"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('app_asset', '0002_initial'),
        ('auth', '__first__'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_columns_if_missing,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='informationasset',
                    name='actualization_date',
                    field=models.DateTimeField(
                        blank=True,
                        help_text='Date when the asset was last actualized by owner',
                        null=True,
                        verbose_name='Actualization Date',
                    ),
                ),
                migrations.AddField(
                    model_name='informationasset',
                    name='actualized_by',
                    field=models.ForeignKey(
                        blank=True,
                        help_text='User who actualized this asset',
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='actualized_assets',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Actualized by',
                    ),
                ),
                migrations.AddField(
                    model_name='informationasset',
                    name='marked_no_longer_actual_at',
                    field=models.DateTimeField(
                        blank=True,
                        help_text='Date when the asset was marked as no longer actual by owner',
                        null=True,
                        verbose_name='Marked no longer actual at',
                    ),
                ),
                migrations.AddField(
                    model_name='informationasset',
                    name='marked_no_longer_comment',
                    field=models.TextField(
                        blank=True,
                        help_text='Optional comment when the asset was marked as no longer actual',
                        verbose_name='Marked no longer actual comment',
                    ),
                ),
            ],
        ),
    ]
