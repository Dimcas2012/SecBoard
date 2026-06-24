from django.db import migrations


def seed_record_hmac(apps, schema_editor):
    # Historical model has no instance methods — use live model for HMAC seeding.
    from app_conf.models import SecureLicense

    for lic in SecureLicense.objects.all().iterator(chunk_size=50):
        h = lic._compute_record_hmac(_v2_payload=True)
        SecureLicense.objects.filter(pk=lic.pk).update(record_hmac=h)


def reverse_seed(apps, schema_editor):
    SecureLicense = apps.get_model('app_conf', 'SecureLicense')
    SecureLicense.objects.all().update(record_hmac='')


class Migration(migrations.Migration):

    dependencies = [
        ('app_conf', '0002_add_securelicense_record_hmac'),
    ]

    operations = [
        migrations.RunPython(seed_record_hmac, reverse_seed),
    ]
