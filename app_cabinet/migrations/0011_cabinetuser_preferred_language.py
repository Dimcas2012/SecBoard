from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_cabinet', '0010_cabinetuser_telegram_link_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='cabinetuser',
            name='preferred_language',
            field=models.CharField(
                blank=True,
                help_text='Preferred interface language for this user.',
                max_length=10,
                verbose_name='Default language',
            ),
        ),
    ]
