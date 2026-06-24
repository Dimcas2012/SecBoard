#  SecBoard\SecBoard\app_gdpr\management\commands\cleanup_expired_data.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from app_gdpr.models import DataSubject
from app_gdpr.utils import anonymize_personal_data
from datetime import timedelta


class Command(BaseCommand):
    help = 'Cleanup expired data according to retention policies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()
        
        # Знаходимо суб'єктів, для яких настав час видалення
        subjects_for_deletion = DataSubject.objects.filter(
            deletion_scheduled_date__lte=today,
            is_anonymized=False
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Found {subjects_for_deletion.count()} data subjects scheduled for deletion'
            )
        )
        
        anonymized_count = 0
        for subject in subjects_for_deletion:
            if dry_run:
                self.stdout.write(
                    f'[DRY RUN] Would anonymize: {subject.email}'
                )
            else:
                if anonymize_personal_data(subject):
                    anonymized_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Anonymized: {subject.email}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Failed to anonymize: {subject.email}'
                        )
                    )
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully anonymized {anonymized_count} data subjects'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    'Dry run completed - no changes made'
                )
            )

