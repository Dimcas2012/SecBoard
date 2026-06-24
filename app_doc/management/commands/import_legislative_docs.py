"""
Django management command to import Legislative Documents from CSV file
Usage: python manage.py import_legislative_docs [--csv-file path/to/file.csv] [--update] [--user-id ID]
"""
import csv
import os
import sys
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from app_doc.models import LegislativeDoc, DocType, RegulatorName
from app_conf.models import Company

# Increase CSV field size limit to handle large HTML content
csv.field_size_limit(sys.maxsize)


class Command(BaseCommand):
    help = 'Import Legislative Documents from CSV file'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-file',
            type=str,
            default='app_doc/app_legdoc.csv',
            help='Path to the CSV file (default: app_doc/app_legdoc.csv)'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID for created_by/updated_by (default: first user)'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing documents if they exist (by id)'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip existing documents (by id)'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        update_mode = options['update']
        skip_existing = options['skip_existing']
        
        # Get user
        if options['user_id']:
            try:
                user = User.objects.get(id=options['user_id'])
            except User.DoesNotExist:
                raise CommandError(f'User with ID {options["user_id"]} not found')
        else:
            user = User.objects.first()
            if not user:
                raise CommandError('No user found! Create a user first.')
        
        # Check if file exists
        if not os.path.exists(csv_file):
            raise CommandError(f'CSV file not found: {csv_file}')
        
        self.stdout.write(self.style.SUCCESS(f'Starting import from: {csv_file}'))
        self.stdout.write(f'User: {user.username}')
        self.stdout.write(f'Update mode: {update_mode}')
        self.stdout.write(f'Skip existing: {skip_existing}')
        
        try:
            with transaction.atomic():
                imported_count = 0
                updated_count = 0
                skipped_count = 0
                errors = []
                
                with open(csv_file, 'r', encoding='utf-8-sig') as file:
                    # CSV uses semicolon as delimiter
                    csv_reader = csv.DictReader(file, delimiter=';')
                    
                    for row_num, row in enumerate(csv_reader, start=2):
                        try:
                            # Parse document ID
                            doc_id = self._parse_int(row.get('id'))
                            if not doc_id:
                                self.stdout.write(
                                    self.style.WARNING(f'Row {row_num}: Skipping row without ID')
                                )
                                skipped_count += 1
                                continue
                            
                            # Check if document already exists
                            doc = None
                            try:
                                doc = LegislativeDoc.objects.get(id=doc_id)
                                if skip_existing:
                                    self.stdout.write(
                                        self.style.WARNING(f'Row {row_num}: Skipping existing document ID {doc_id}')
                                    )
                                    skipped_count += 1
                                    continue
                                elif not update_mode:
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f'Row {row_num}: Document ID {doc_id} already exists. '
                                            f'Use --update to update or --skip-existing to skip.'
                                        )
                                    )
                                    skipped_count += 1
                                    continue
                            except LegislativeDoc.DoesNotExist:
                                doc = None
                            
                            # Parse basic fields
                            title = row.get('title', '').strip()
                            if not title:
                                self.stdout.write(
                                    self.style.WARNING(f'Row {row_num}: Skipping row without title')
                                )
                                skipped_count += 1
                                continue
                            
                            doc_number = self._parse_string(row.get('doc_number'))
                            issuing_authority = self._parse_string(row.get('issuing_authority'))
                            original_url = self._parse_string(row.get('original_url'))
                            description = self._parse_string(row.get('description')) or ''
                            
                            # Parse dates
                            issue_date = self._parse_date(row.get('issue_date'))
                            effective_date = self._parse_date(row.get('effective_date'))
                            expiration_date = self._parse_date(row.get('expiration_date'))
                            
                            # Parse boolean
                            is_active = self._parse_bool(row.get('is_active'), default=True)
                            
                            # Parse file path
                            pdf_file = self._parse_string(row.get('pdf_file'))
                            
                            # Parse HTML content
                            html_content = self._parse_string(row.get('html_content'))
                            
                            # Parse ForeignKey fields
                            doc_type_id = self._parse_int(row.get('doc_type_id'))
                            regulator_id = self._parse_int(row.get('regulator_id'))
                            created_by_id = self._parse_int(row.get('created_by_id'))
                            updated_by_id = self._parse_int(row.get('updated_by_id'))
                            
                            # Parse company_id (old ForeignKey - will be migrated to ManyToMany)
                            company_id = self._parse_int(row.get('company_id'))
                            
                            # Parse timestamps
                            created_at = self._parse_datetime(row.get('created_at'))
                            updated_at = self._parse_datetime(row.get('updated_at'))
                            
                            # Create or update document
                            if doc:
                                # Update existing document
                                doc.title = title
                                doc.doc_number = doc_number
                                doc.issuing_authority = issuing_authority
                                doc.original_url = original_url
                                doc.description = description
                                doc.issue_date = issue_date
                                doc.effective_date = effective_date
                                doc.expiration_date = expiration_date
                                doc.is_active = is_active
                                doc.html_content = html_content
                                
                                if doc_type_id:
                                    try:
                                        doc.doc_type = DocType.objects.get(id=doc_type_id)
                                    except DocType.DoesNotExist:
                                        self.stdout.write(
                                            self.style.WARNING(
                                                f'Row {row_num}: DocType ID {doc_type_id} not found'
                                            )
                                        )
                                
                                if regulator_id:
                                    try:
                                        doc.regulator = RegulatorName.objects.get(id=regulator_id)
                                    except RegulatorName.DoesNotExist:
                                        self.stdout.write(
                                            self.style.WARNING(
                                                f'Row {row_num}: Regulator ID {regulator_id} not found'
                                            )
                                        )
                                
                                if updated_by_id:
                                    try:
                                        doc.updated_by = User.objects.get(id=updated_by_id)
                                    except User.DoesNotExist:
                                        doc.updated_by = user
                                else:
                                    doc.updated_by = user
                                
                                # Handle PDF file (only if path exists)
                                if pdf_file and os.path.exists(pdf_file):
                                    with open(pdf_file, 'rb') as f:
                                        doc.pdf_file.save(
                                            os.path.basename(pdf_file),
                                            f,
                                            save=False
                                        )
                                
                                doc.save()
                                
                                # Handle company (ManyToMany)
                                if company_id:
                                    try:
                                        company = Company.objects.get(id=company_id)
                                        doc.company.clear()
                                        doc.company.add(company)
                                    except Company.DoesNotExist:
                                        self.stdout.write(
                                            self.style.WARNING(
                                                f'Row {row_num}: Company ID {company_id} not found'
                                            )
                                        )
                                
                                updated_count += 1
                                if updated_count % 10 == 0:
                                    self.stdout.write(f'  Updated {updated_count} documents...')
                                
                            else:
                                # Create new document
                                doc = LegislativeDoc(
                                    id=doc_id,
                                    title=title,
                                    doc_number=doc_number,
                                    issuing_authority=issuing_authority,
                                    original_url=original_url,
                                    description=description,
                                    issue_date=issue_date,
                                    effective_date=effective_date,
                                    expiration_date=expiration_date,
                                    is_active=is_active,
                                    html_content=html_content,
                                )
                                
                                if doc_type_id:
                                    try:
                                        doc.doc_type = DocType.objects.get(id=doc_type_id)
                                    except DocType.DoesNotExist:
                                        self.stdout.write(
                                            self.style.WARNING(
                                                f'Row {row_num}: DocType ID {doc_type_id} not found'
                                            )
                                        )
                                
                                if regulator_id:
                                    try:
                                        doc.regulator = RegulatorName.objects.get(id=regulator_id)
                                    except RegulatorName.DoesNotExist:
                                        self.stdout.write(
                                            self.style.WARNING(
                                                f'Row {row_num}: Regulator ID {regulator_id} not found'
                                            )
                                        )
                                
                                if created_by_id:
                                    try:
                                        doc.created_by = User.objects.get(id=created_by_id)
                                    except User.DoesNotExist:
                                        doc.created_by = user
                                else:
                                    doc.created_by = user
                                
                                if updated_by_id:
                                    try:
                                        doc.updated_by = User.objects.get(id=updated_by_id)
                                    except User.DoesNotExist:
                                        doc.updated_by = user
                                else:
                                    doc.updated_by = user
                                
                                # Handle PDF file (only if path exists)
                                if pdf_file and os.path.exists(pdf_file):
                                    with open(pdf_file, 'rb') as f:
                                        doc.pdf_file.save(
                                            os.path.basename(pdf_file),
                                            f,
                                            save=False
                                        )
                                
                                doc.save()
                                
                                # Handle company (ManyToMany)
                                if company_id:
                                    try:
                                        company = Company.objects.get(id=company_id)
                                        doc.company.add(company)
                                    except Company.DoesNotExist:
                                        self.stdout.write(
                                            self.style.WARNING(
                                                f'Row {row_num}: Company ID {company_id} not found'
                                            )
                                        )
                                
                                imported_count += 1
                                if imported_count % 10 == 0:
                                    self.stdout.write(f'  Imported {imported_count} documents...')
                        
                        except Exception as e:
                            error_msg = f'Row {row_num}: Error - {str(e)}'
                            errors.append(error_msg)
                            self.stdout.write(self.style.ERROR(error_msg))
                            continue
                
                # Summary
                self.stdout.write('\n' + '='*60)
                self.stdout.write(self.style.SUCCESS('Import completed!'))
                self.stdout.write(f'  Imported: {imported_count}')
                self.stdout.write(f'  Updated: {updated_count}')
                self.stdout.write(f'  Skipped: {skipped_count}')
                if errors:
                    self.stdout.write(self.style.ERROR(f'  Errors: {len(errors)}'))
                    self.stdout.write('\nFirst 10 errors:')
                    for error in errors[:10]:
                        self.stdout.write(self.style.ERROR(f'    {error}'))
        
        except Exception as e:
            raise CommandError(f'Import failed: {str(e)}')
    
    def _parse_int(self, value):
        """Parse integer value from CSV"""
        if not value or value == '\\N' or value.strip() == '':
            return None
        try:
            return int(value.strip().strip('"'))
        except (ValueError, AttributeError):
            return None
    
    def _parse_string(self, value):
        """Parse string value from CSV"""
        if not value or value == '\\N':
            return None
        value = str(value).strip().strip('"')
        return value if value else None
    
    def _parse_bool(self, value, default=False):
        """Parse boolean value from CSV"""
        if not value or value == '\\N':
            return default
        value = str(value).strip().strip('"').lower()
        return value in ('1', 'true', 'yes', 't')
    
    def _parse_date(self, value):
        """Parse date value from CSV"""
        if not value or value == '\\N' or value.strip() == '':
            return None
        value = str(value).strip().strip('"')
        if not value:
            return None
        try:
            # Try different date formats
            for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%Y/%m/%d']:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            return None
        except (ValueError, AttributeError):
            return None
    
    def _parse_datetime(self, value):
        """Parse datetime value from CSV"""
        if not value or value == '\\N' or value.strip() == '':
            return None
        value = str(value).strip().strip('"')
        if not value:
            return None
        try:
            # Try different datetime formats
            for fmt in [
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%d.%m.%Y %H:%M:%S',
                '%d/%m/%Y %H:%M:%S',
            ]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            return None
        except (ValueError, AttributeError):
            return None

