from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_cabinet', '0008_cabinet_task_reminder_schedule'),
    ]

    operations = [
        migrations.AddField(
            model_name='cabinetuser',
            name='telegram_chat_id',
            field=models.CharField(
                blank=True,
                help_text='Your Telegram Chat ID from the SecBoard bot (tap Help in the bot to see it).',
                max_length=64,
                verbose_name='Telegram Chat ID',
            ),
        ),
    ]
