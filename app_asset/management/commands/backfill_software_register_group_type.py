"""
Backfill SoftwareRegister.group_id and asset_type_id from legacy SoftwareCategory exports.

Maps each known software register row (by primary key) to an AssetType that exists in the
catalog; group is taken from asset_type.group_id.

Run after removing SoftwareCategory: use --dry-run first, then without it to apply.

Mapping rationale (IT Software / Security / Databases / Network / etc.):
  ELK Stack          -> Log Analysis Tools
  Wazuh              -> SIEM
  PostgreSQL         -> Database (Databases)
  Docker             -> Virtualization Systems
  Veeam Backup       -> Backup Systems
  Nginx              -> Proxy Servers (reverse proxy / web)
  GitLab             -> Version Control Systems
  pfSense            -> Application Firewalls
  OpenVPN            -> VPN Gateways
  Zabbix             -> Monitoring Systems
  Suricata           -> IPS/IDS
  RabbitMQ           -> Message broker (IT Services)
  AventusPay         -> Transaction System (Business Services)
  Ubuntu server      -> Servers (Personal Devices — server OS)
  GitLab Runner      -> Automation Systems
  BAS                -> Financial Accounting System
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from app_asset.models import AssetType, SoftwareRegister

# Legacy export row id -> asset_type.id (use when DB primary keys match the CSV)
DEFAULT_MAP_BY_ID = {
    1: 113,  # ELK Stack
    2: 16,  # Wazuh
    3: 24,  # postgresql
    4: 107,  # Docker
    5: 116,  # Veeam Backup for Google Cloud
    6: 174,  # Nginx
    7: 109,  # Gitlab
    8: 173,  # pFsense
    9: 32,  # OpenVPN (pfSense)
    10: 105,  # Zabbix
    11: 20,  # Suricata
    12: 186,  # RabbitMQ
    13: 17,  # AventusPay
    14: 8,  # Ubuntu server
    15: 111,  # Gitlab-runner
    16: 153,  # BAS
}

# software name (exact, case-insensitive) -> asset_type.id — used when ids do not match CSV
DEFAULT_MAP_BY_NAME = {
    'ELK Stack': 113,
    'Wazuh': 16,
    'postgresql': 24,  # name__iexact also matches PostgreSQL, POSTGRESQL, etc.
    'Docker': 107,
    'Veeam Backup for Google Cloud': 116,
    'Nginx': 174,
    'Gitlab': 109,
    'pFsense': 173,
    'OpenVPN (pfSense)': 32,
    'Zabbix': 105,
    'Suricata': 20,
    'RabbitMQ': 186,
    'AventusPay': 17,
    'Ubuntu server': 8,
    'Gitlab-runner': 111,
    'BAS': 153,
}


class Command(BaseCommand):
    help = 'Set SoftwareRegister group and asset_type from legacy category export (fixed id→type map).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned updates only; do not write.',
        )
        parser.add_argument(
            '--only-null',
            action='store_true',
            help='Only update rows where group_id and asset_type_id are both NULL.',
        )
        parser.add_argument(
            '--by-name',
            action='store_true',
            help='Match rows by software name (DEFAULT_MAP_BY_NAME) instead of by legacy id.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        only_null = options['only_null']
        by_name = options['by_name']

        type_ids = set(DEFAULT_MAP_BY_ID.values())
        if by_name:
            type_ids |= set(DEFAULT_MAP_BY_NAME.values())
        missing_types = [tid for tid in sorted(type_ids) if not AssetType.objects.filter(pk=tid).exists()]
        if missing_types:
            self.stderr.write('AssetType rows missing for id(s): ' + ', '.join(str(x) for x in missing_types))
            raise SystemExit(1)

        updates = []

        def consider(sw, at_id):
            if only_null and (sw.group_id is not None or sw.asset_type_id is not None):
                return
            at = AssetType.objects.select_related('group').get(pk=at_id)
            updates.append((sw, at))

        if by_name:
            for name, at_id in DEFAULT_MAP_BY_NAME.items():
                sw = SoftwareRegister.objects.filter(name__iexact=name).first()
                if not sw:
                    self.stderr.write(f'No SoftwareRegister with name={name!r} (skipped)')
                    continue
                consider(sw, at_id)
        else:
            seen_pks = set()
            for sw_id, at_id in sorted(DEFAULT_MAP_BY_ID.items()):
                try:
                    sw = SoftwareRegister.objects.get(pk=sw_id)
                except SoftwareRegister.DoesNotExist:
                    continue
                consider(sw, at_id)
                seen_pks.add(sw.pk)
            if not seen_pks:
                self.stdout.write(
                    'No rows matched legacy ids 1–16; matching by software name instead.'
                )
            # Fill gaps: same legacy export, different PKs in DB
            # NOTE: exclude(pk__in=[]) breaks the queryset in Django — only exclude when non-empty.
            for name, at_id in DEFAULT_MAP_BY_NAME.items():
                qs = SoftwareRegister.objects.filter(name__iexact=name)
                if seen_pks:
                    qs = qs.exclude(pk__in=seen_pks)
                sw = qs.first()
                if sw:
                    consider(sw, at_id)

        # Same row may appear twice (e.g. id + name paths); keep one update per pk
        dedup = {}
        for sw, at in updates:
            dedup[sw.pk] = (sw, at)
        updates = list(dedup.values())

        for sw, at in updates:
            self.stdout.write(
                f'id={sw.id} {sw.name!r} -> group={at.group_id} ({at.group.code}) '
                f'type={at.id} ({at.code})'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run: no changes written.'))
            return

        with transaction.atomic():
            for sw, at in updates:
                SoftwareRegister.objects.filter(pk=sw.pk).update(
                    group_id=at.group_id,
                    asset_type_id=at.id,
                )

        if not updates:
            self.stdout.write(
                self.style.WARNING(
                    'No SoftwareRegister rows were updated. If the table is empty, import the legacy CSV first, '
                    'then run this command again:\n'
                    '  python manage.py import_software_register_legacy_csv /path/to/export.csv'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f'Updated {len(updates)} software register row(s).'))
