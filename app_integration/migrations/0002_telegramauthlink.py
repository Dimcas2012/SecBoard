from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app_cabinet', '0011_cabinetuser_preferred_language'),
        ('app_integration', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramAuthLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(db_index=True, max_length=64, unique=True, verbose_name='Token')),
                ('chat_id', models.CharField(max_length=64, verbose_name='Telegram chat ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(verbose_name='Expires at')),
                ('used_at', models.DateTimeField(blank=True, null=True, verbose_name='Used at')),
                ('bot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='auth_links', to='app_integration.telegrambot', verbose_name='Telegram bot')),
                ('cabinet_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='telegram_auth_links', to='app_cabinet.cabinetuser', verbose_name='Cabinet user')),
            ],
            options={
                'verbose_name': 'Telegram auth link',
                'verbose_name_plural': 'Telegram auth links',
                'ordering': ['-created_at'],
            },
        ),
    ]
