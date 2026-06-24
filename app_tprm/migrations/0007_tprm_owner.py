import django.db.models.deletion
from django.db import connection, migrations, models

_VENDOR_OWNER_LINKS_BACKUP = []


def backup_vendor_owner_links(apps, schema_editor):
    AssetOwner = apps.get_model('app_asset', 'AssetOwner')
    TprmOwner = apps.get_model('app_tprm', 'TprmOwner')
    global _VENDOR_OWNER_LINKS_BACKUP
    _VENDOR_OWNER_LINKS_BACKUP = []
    with connection.cursor() as cursor:
        cursor.execute('SELECT vendor_id, assetowner_id FROM app_tprm_vendor_owners')
        rows = cursor.fetchall()
    for vendor_id, assetowner_id in rows:
        ao = AssetOwner.objects.get(pk=assetowner_id)
        to, _ = TprmOwner.objects.get_or_create(
            cabinet_user_id=ao.cabinet_user_id,
            company_id=ao.company_id,
        )
        _VENDOR_OWNER_LINKS_BACKUP.append((vendor_id, to.pk))


def restore_vendor_owner_links(apps, schema_editor):
    Vendor = apps.get_model('app_tprm', 'Vendor')
    TprmOwner = apps.get_model('app_tprm', 'TprmOwner')
    for vendor_id, tprmowner_id in _VENDOR_OWNER_LINKS_BACKUP:
        v = Vendor.objects.get(pk=vendor_id)
        to = TprmOwner.objects.get(pk=tprmowner_id)
        v.owners.add(to)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('app_asset', '0004_externalmediaguide_externalmediaguidetranslation'),
        ('app_cabinet', '0002_initial'),
        ('app_conf', '0003_seed_securelicense_record_hmac'),
        ('app_tprm', '0006_vendor_actualization'),
    ]

    operations = [
        migrations.CreateModel(
            name='TprmOwner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cabinet_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tprm_owner_entries', to='app_cabinet.cabinetuser', verbose_name='Cabinet User')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tprm_owners', to='app_conf.company', verbose_name='Company')),
            ],
            options={
                'verbose_name': 'TPRM Owner',
                'verbose_name_plural': 'TPRM Owners',
                'unique_together': {('cabinet_user', 'company')},
            },
        ),
        migrations.RunPython(backup_vendor_owner_links, noop_reverse),
        migrations.RemoveField(
            model_name='vendor',
            name='owners',
        ),
        migrations.AddField(
            model_name='vendor',
            name='owners',
            field=models.ManyToManyField(blank=True, related_name='owned_vendors', to='app_tprm.tprmowner', verbose_name='Owners'),
        ),
        migrations.RunPython(restore_vendor_owner_links, noop_reverse),
    ]
