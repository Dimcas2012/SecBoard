from celery import shared_task

@shared_task
def send_scheduled_reminders():
    """Send scheduled reminders that are due"""
    from django.utils import timezone
    from .models import ScheduledReminder, ReminderLog
    from app_conf.models import SiteSettings
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import ssl
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Get site settings for URL construction
    site_settings = SiteSettings.get_settings()
    base_url = site_settings.get_site_url()
    
    # Get all active reminders that should be sent now
    reminders = ScheduledReminder.objects.filter(
        is_active=True,
        next_send__lte=timezone.now()
    ).select_related('quiz', 'email_account')
    
    for reminder in reminders:
        try:
            # Get target users
            target_users = reminder.get_target_users()
            
            if not target_users:
                logger.warning(f"No target users found for reminder {reminder.id}")
                continue
            
            sent_count = 0
            failed_count = 0
            error_messages = []
            
            # Send emails to each user
            for user in target_users:
                try:
                    # Replace template variables
                    personalized_subject = reminder.subject_template.replace('{{ user_name }}', user.get_full_name() or user.username)
                    personalized_subject = personalized_subject.replace('{{ user_email }}', user.email)
                    personalized_subject = personalized_subject.replace('{{ quiz_title }}', reminder.quiz.title)
                    personalized_subject = personalized_subject.replace('{{ quiz_url }}', f"{base_url}/en/app_study/quiz/start/{reminder.quiz.id}/")
                    personalized_subject = personalized_subject.replace('{{ company_name }}', getattr(user.cabinet.company, 'name', 'Unknown Company') if hasattr(user, 'cabinet') else 'Unknown Company')
                    personalized_subject = personalized_subject.replace('{{ current_date }}', timezone.now().strftime('%d.%m.%Y'))
                    
                    personalized_body = reminder.body_template.replace('{{ user_name }}', user.get_full_name() or user.username)
                    personalized_body = personalized_body.replace('{{ user_email }}', user.email)
                    personalized_body = personalized_body.replace('{{ quiz_title }}', reminder.quiz.title)
                    personalized_body = personalized_body.replace('{{ quiz_url }}', f"{base_url}/en/app_study/quiz/start/{reminder.quiz.id}/")
                    personalized_body = personalized_body.replace('{{ company_name }}', getattr(user.cabinet.company, 'name', 'Unknown Company') if hasattr(user, 'cabinet') else 'Unknown Company')
                    personalized_body = personalized_body.replace('{{ current_date }}', timezone.now().strftime('%d.%m.%Y'))
                    
                    # Create the email message
                    msg = MIMEMultipart()
                    msg['From'] = reminder.email_account.username
                    msg['To'] = user.email
                    msg['Subject'] = personalized_subject
                    msg.attach(MIMEText(personalized_body, 'plain'))
                    
                    # Connect to the server
                    if reminder.email_account.server.use_ssl:
                        context = ssl.create_default_context()
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                        
                        smtp = smtplib.SMTP_SSL(
                            host=reminder.email_account.server.smtp_host,
                            port=reminder.email_account.server.smtp_port,
                            context=context
                        )
                    else:
                        smtp = smtplib.SMTP(
                            host=reminder.email_account.server.smtp_host,
                            port=reminder.email_account.server.smtp_port
                        )
                        
                        if reminder.email_account.server.use_tls:
                            smtp.starttls()
                    
                    # Login and send
                    smtp.login(reminder.email_account.username, reminder.email_account.password)
                    smtp.send_message(msg)
                    smtp.quit()
                    
                    sent_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    error_msg = f"Failed to send email to {user.email}: {str(e)}"
                    error_messages.append(error_msg)
                    logger.error(error_msg)
            
            # Create log entry
            reminder_log = ReminderLog.objects.create(
                scheduled_reminder=reminder,
                sent_count=sent_count,
                failed_count=failed_count,
                error_message='\n'.join(error_messages) if error_messages else ''
            )
            # Add recipients to the log
            reminder_log.recipients.set(target_users)
            
            # Mark reminder as sent and calculate next send date
            reminder.mark_sent()
            
            logger.info(f"Sent scheduled reminder {reminder.id}: {sent_count} sent, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error processing scheduled reminder {reminder.id}: {str(e)}")
            
            # Create log entry for the error
            error_target_users = reminder.get_target_users()
            error_log = ReminderLog.objects.create(
                scheduled_reminder=reminder,
                sent_count=0,
                failed_count=len(error_target_users),
                error_message=f"Error processing reminder: {str(e)}"
            )
            # Add recipients to the error log
            error_log.recipients.set(error_target_users)
