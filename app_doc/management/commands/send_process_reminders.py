# Management command to send automatic process reminders
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext as _
import logging

from app_compliance.models import MandatoryProcess
from app_doc.email_utils import send_mandatory_process_reminder

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Send automatic reminders for mandatory processes that are due in specified days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending emails',
        )
        parser.add_argument(
            '--days',
            type=int,
            help='Override the default reminder days for all processes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        override_days = options.get('days')
        
        self.stdout.write(
            self.style.SUCCESS('Starting automatic process reminders...')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No emails will be sent')
            )
        
        # Get all active processes
        processes = MandatoryProcess.objects.filter(is_active=True)
        
        if not processes.exists():
            self.stdout.write(
                self.style.WARNING('No active processes found')
            )
            return
        
        self.stdout.write(f'Found {processes.count()} active processes')
        
        reminders_sent = 0
        processes_checked = 0
        
        for process in processes:
            processes_checked += 1
            
            # Check if reminder should be sent
            if override_days:
                # Override the process's reminder_days setting
                days_until_due = process.days_until_due
                should_send = days_until_due == override_days
                reminder_days = override_days
            else:
                # Use the process's own reminder_days setting
                should_send = process.should_send_reminder()
                reminder_days = process.reminder_days
            
            if should_send:
                # Get recipients
                recipients = []
                
                # Add only responsible persons
                for user in process.responsible_person.all():
                    if user.email:
                        recipients.append({
                            'name': user.get_full_name() or user.username,
                            'email': user.email,
                            'role': _('Responsible Person')
                        })
                
                # Remove duplicates based on email
                unique_recipients = []
                seen_emails = set()
                for recipient in recipients:
                    if recipient['email'] not in seen_emails:
                        unique_recipients.append(recipient)
                        seen_emails.add(recipient['email'])
                
                if unique_recipients:
                    # Prepare email content
                    subject = _('Automatic Reminder: {process_name} - Due in {days} days').format(
                        process_name=process.process_name,
                        days=reminder_days
                    )
                    
                    message = _('This is an automatic reminder that the following mandatory process is due in {days} days:\n\nProcess: {process_name}\nDue Date: {due_date}\nCompany: {company}\nPriority: {priority}\n\nPlease ensure this process is completed on time.').format(
                        days=reminder_days,
                        process_name=process.process_name,
                        due_date=process.next_due_date,
                        company=process.company.name if process.company else _('N/A'),
                        priority=process.get_priority_display()
                    )
                    
                    if dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[DRY RUN] Would send reminder for process "{process.process_name}" '
                                f'(ID: {process.id}) to {len(unique_recipients)} recipients'
                            )
                        )
                        for recipient in unique_recipients:
                            self.stdout.write(f'  - {recipient["name"]} ({recipient["email"]})')
                    else:
                        # Send the reminder
                        success_count = send_mandatory_process_reminder(
                            process=process,
                            recipients=unique_recipients,
                            subject=subject,
                            message=message,
                            include_process_details=True,
                            sent_by=None  # System-generated reminder
                        )
                        
                        if success_count > 0:
                            reminders_sent += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Sent reminder for process "{process.process_name}" '
                                    f'(ID: {process.id}) to {success_count}/{len(unique_recipients)} recipients'
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'✗ Failed to send reminder for process "{process.process_name}" '
                                    f'(ID: {process.id})'
                                )
                            )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ No recipients found for process "{process.process_name}" (ID: {process.id})'
                        )
                    )
            else:
                # Show why reminder wasn't sent
                days_until_due = process.days_until_due
                if days_until_due is None:
                    reason = 'No due date set'
                elif days_until_due < 0:
                    reason = f'Overdue by {abs(days_until_due)} days'
                elif days_until_due > reminder_days:
                    reason = f'Due in {days_until_due} days (reminder set for {reminder_days} days)'
                else:
                    reason = f'Due in {days_until_due} days (not at reminder threshold of {reminder_days} days)'
                
                self.stdout.write(
                    f'  - Process "{process.process_name}" (ID: {process.id}): {reason}'
                )
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(f'Processed {processes_checked} processes')
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'[DRY RUN] Would have sent {reminders_sent} reminders')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Sent {reminders_sent} reminders')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Automatic process reminders completed!')
        )
