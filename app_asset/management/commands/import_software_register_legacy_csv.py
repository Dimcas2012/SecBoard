"""
Import Software Register rows from a legacy semicolon CSV (e.g. mysqldump / phpMyAdmin export).

Expected header (example):
  id;name;description;version_pattern;is_active;display_order;created_date;updated_date;
  company_id;license_quantity;license_type;license_valid_until;manufacturer;notes;url;
  category_id;status_id;actualization_date;actualized_by_id;marked_no_longer_actual_at;marked_no_longer_comment

Uses NULL markers: \\N or empty for optional fields.
Ignores category_id. After import, run: backfill_software_register_group_type

Example:
  python manage.py import_software_register_legacy_csv /path/to/export.csv --dry-run
  python manage.py import_software_register_legacy_csv /path/to/export.csv
"""

import csv
import io
from datetime import datetime as dt

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

from app_conf.models import Company
from app_asset.models import SoftwareRegister, SoftwareStatus


def _null(s):
    if s is None:
        return None
    t = str(s).strip()
    if not t or t == r'\N':
        return None
    return t


def _int_or_none(s):
    t = _null(s)
    if t is None:
        return None
    try:
        return int(t)
    except ValueError:
        return None


def _bool(s):
    t = _null(s)
    if t is None:
        return True
    return str(t).strip() not in ('0', 'false', 'False', 'no', 'No')


def _parse_dt(val):
    """Parse MySQL datetime or ISO string."""
    s = _null(val)
    if not s:
        return None
    s = s.strip()
    p = parse_datetime(s)
    if p:
        return p
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
        try:
            return dt.strptime(s, fmt)
        except ValueError:
            continue
    return None


class Command(BaseCommand):
    help = 'Import SoftwareRegister rows from legacy semicolon CSV (SQL dump style).'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to UTF-8 CSV file')
        parser.add_argument('--dry-run', action='store_true', help='Parse only; do not write')

    def handle(self, *args, **options):
        path = options['csv_file']
        dry_run = options['dry_run']

        with open(path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        reader = csv.reader(io.StringIO(content), delimiter=';')
        rows = list(reader)
        if not rows:
            self.stderr.write('File is empty')
            raise SystemExit(1)
        headers = [h.strip() for h in rows[0]]

        def idx(name):
            try:
                return headers.index(name)
            except ValueError:
                return None

        # Allow optional columns
        h_id = idx('id')
        h_name = idx('name')
        if h_name is None:
            self.stderr.write('Column "name" is required')
            raise SystemExit(1)

        colmap = {
            'description': idx('description'),
            'version_pattern': idx('version_pattern'),
            'is_active': idx('is_active'),
            'display_order': idx('display_order'),
            'company_id': idx('company_id'),
            'license_quantity': idx('license_quantity'),
            'license_type': idx('license_type'),
            'license_valid_until': idx('license_valid_until'),
            'manufacturer': idx('manufacturer'),
            'notes': idx('notes'),
            'url': idx('url'),
            'status_id': idx('status_id'),
            'actualization_date': idx('actualization_date'),
            'actualized_by_id': idx('actualized_by_id'),
            'marked_no_longer_actual_at': idx('marked_no_longer_actual_at'),
            'marked_no_longer_comment': idx('marked_no_longer_comment'),
        }

        def cell(row, i):
            if i is None or i >= len(row):
                return ''
            return row[i]

        planned = []
        for row_num, row in enumerate(rows[1:], start=2):
            name = _null(cell(row, h_name))
            if not name:
                continue
            sid = _int_or_none(cell(row, colmap['status_id']))
            if not sid:
                self.stderr.write(f'Row {row_num}: missing status_id, skipped')
                continue
            if not SoftwareStatus.objects.filter(pk=sid).exists():
                self.stderr.write(f'Row {row_num}: status_id={sid} does not exist, skipped')
                continue
            status = SoftwareStatus.objects.get(pk=sid)
            company = None
            cid = _int_or_none(cell(row, colmap['company_id']))
            if cid:
                company = Company.objects.filter(pk=cid).first()
                if not company:
                    self.stderr.write(f'Row {row_num}: company_id={cid} not found, skipped')
                    continue

            lq = _int_or_none(cell(row, colmap['license_quantity']))
            ltu = _null(cell(row, colmap['license_valid_until']))
            license_valid_until = parse_date(ltu) if ltu else None

            ad = _null(cell(row, colmap['actualization_date']))
            actualization_date = _parse_dt(ad)

            mna = _null(cell(row, colmap['marked_no_longer_actual_at']))
            marked_no_longer = _parse_dt(mna)

            pk = _int_or_none(cell(row, h_id)) if h_id is not None else None

            data = {
                'name': name,
                'description': _null(cell(row, colmap['description'])) or '',
                'version_pattern': _null(cell(row, colmap['version_pattern'])) or '',
                'is_active': _bool(cell(row, colmap['is_active'])),
                'display_order': _int_or_none(cell(row, colmap['display_order'])) or 0,
                'company': company,
                'license_quantity': lq,
                'license_type': (_null(cell(row, colmap['license_type'])) or '')[:100],
                'license_valid_until': license_valid_until,
                'manufacturer': _null(cell(row, colmap['manufacturer'])) or '',
                'notes': _null(cell(row, colmap['notes'])) or '',
                'url': _null(cell(row, colmap['url'])) or '',
                'status': status,
                'actualization_date': actualization_date,
                'marked_no_longer_actual_at': marked_no_longer,
                'marked_no_longer_comment': _null(cell(row, colmap['marked_no_longer_comment'])) or '',
            }
            actualized_by_id = _int_or_none(cell(row, colmap['actualized_by_id']))
            planned.append((pk, data, actualized_by_id))

        self.stdout.write(f'Parsed {len(planned)} row(s) from {path}')
        if dry_run:
            for pk, data, aid in planned[:5]:
                self.stdout.write(f'  would save pk={pk} name={data["name"]!r} status={data["status"].id} actualized_by_id={aid}')
            if len(planned) > 5:
                self.stdout.write(f'  ... and {len(planned) - 5} more')
            self.stdout.write(self.style.WARNING('Dry run: no database writes.'))
            return

        created = 0
        updated = 0
        with transaction.atomic():
            for pk, data, actualized_by_id in planned:
                if pk:
                    _obj, was_created = SoftwareRegister.objects.update_or_create(
                        pk=pk,
                        defaults={**data, 'actualized_by_id': actualized_by_id},
                    )
                else:
                    SoftwareRegister.objects.create(**data, actualized_by_id=actualized_by_id)
                    was_created = True
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f'Done: created={created}, updated={updated}'))
        self.stdout.write('Next: python manage.py backfill_software_register_group_type')
