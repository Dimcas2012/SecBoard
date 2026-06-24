from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_cabinet', '0009_cabinetuser_telegram_chat_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='cabinetuser',
            name='telegram_link_token',
            field=models.CharField(
                blank=True,
                help_text='Secret token for Telegram deep-link account linking.',
                max_length=64,
                null=True,
                unique=True,
                verbose_name='Telegram link token',
            ),
        ),
    ]
