#  SecBoard\SecBoard\app_keycert\tasks.py
# SecBoard/SecBoard/app_keycert/tasks.py
from datetime import timedelta
import pytz
from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.db import transaction
import logging
from .models import Reminder, KeyCertificates, KeyCertHistory
from app_conf.models import MailAccount
from functools import wraps
import redis
from django.utils.dateparse import parse_datetime
import time
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# Initialize Redis client for distributed locking
try:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True
    )
    redis_client.ping()  # Test connection
    logger.info("Redis connection established successfully")
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {str(e)}")
    redis_client = None

class DistributedLock:
    def __init__(self, lock_id, timeout=60):
        self.lock_id = lock_id
        self.timeout = timeout
        self.redis_client = redis_client

    def acquire(self):
        if not self.redis_client:
            logger.warning("Redis client is not initialized, skipping lock acquisition")
            return True
        try:
            acquired = self.redis_client.set(
                self.lock_id,
                'lock',
                ex=self.timeout,
                nx=True
            )
            if not acquired:
                logger.warning(f"Could not acquire lock: {self.lock_id}")
            return bool(acquired)
        except Exception as e:
            logger.error(f"Error acquiring lock: {str(e)}")
            return False

    def release(self):
        if not self.redis_client:
            return
        try:
            self.redis_client.delete(self.lock_id)
        except Exception as e:
            logger.error(f"Error releasing lock: {str(e)}")

    def __enter__(self):
        acquired = self.acquire()
        if not acquired:
            raise Exception(f"Could not acquire lock: {self.lock_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

def ensure_unique_task(timeout=3600):
    def decorator(task_func):
        @wraps(task_func)
        def wrapper(*args, **kwargs):
            task_name = task_func.__name__
            lock_id = f"task_lock_{task_name}_{args}"

            try:
                with DistributedLock(lock_id, timeout):
                    logger.info(f"Acquired lock for task {task_name} with args {args}")
                    return task_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Lock acquisition failed for {task_name}: {str(e)}")
                return None
        return wrapper
    return decorator


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
@ensure_unique_task(timeout=3600)
def send_reminder_email(self, key_cert_id):

    """Send reminder email for key/certificate."""
    lock_id = f"reminder_email_lock_{key_cert_id}"

    try:
        with DistributedLock(lock_id, timeout=60), transaction.atomic():
            # Get active reminder
            reminder = Reminder.objects.select_for_update(nowait=True).filter(
                key_certificate_id=key_cert_id,
                is_sent=False,
                is_cancelled=False
            ).first()

            if not reminder:
                logger.info(f"No active reminder found for key_cert_id {key_cert_id}")
                return False, "No active reminder found or reminder already processed"

            logger.info(f"Processing reminder [{reminder.id}] for certificate {key_cert_id}")

            key_cert = KeyCertificates.objects.get(id=key_cert_id)

            # Create history entry for reminder attempt
            KeyCertHistory.objects.create(
                key_certificate=key_cert,
                action="reminder_attempt",
                action_by=None,  # System action
                details=f"Attempting to send reminder for key/certificate {key_cert.key_cert_num}"
            )
            expiry_date = key_cert.expiry_date.strftime("%d-%m-%Y")
            days_until_expiry = (key_cert.expiry_date - timezone.now().date()).days

            # Prepare email message
            message = f"""
Dear {key_cert.owner.name if key_cert.owner else 'Administrator'},

This is an important notification regarding the following key/certificate:

Key/Certificate Details:
-----------------------
ID: {key_cert.key_cert_num}
Type: {key_cert.type_key_sert.get_name_by_language('en') if key_cert.type_key_sert else 'N/A'}
Purpose: {key_cert.purpose}
Company: {key_cert.company.name}

Expiration Information:
----------------------
Expiry Date: {expiry_date}
Days Until Expiry: {days_until_expiry} days
Current Status: {key_cert.revocation_status.get_name_by_language('en') if key_cert.revocation_status else 'N/A'}

Location Information:
-------------------
Storage Location: {key_cert.location}
Access Control: {key_cert.access_control}

Additional Information:
---------------------
Organization: {key_cert.general_info.organization_name if hasattr(key_cert, 'general_info') else 'N/A'}
Maintainer: {key_cert.general_info.maintainer_name if hasattr(key_cert, 'general_info') else 'N/A'}
Contact: {key_cert.general_info.maintainer_contact if hasattr(key_cert, 'general_info') else 'N/A'}

Required Actions:
---------------
1. Review the expiration date and plan for renewal if necessary
2. Check if any updates or changes are needed
3. Verify all security requirements are still being met
4. Update documentation as needed

Notes: {key_cert.notes if key_cert.notes else 'No additional notes'}

Please take appropriate action to prevent any service disruption.
If you need assistance, please contact the system administrator.

Best regards,
Security Team
"""
            # Get active mail account
            mail_account = MailAccount.objects.filter(is_active=True).first()
            if not mail_account:
                raise ValueError("No active mail account found")

            subject = f"IMPORTANT: Key/Certificate {key_cert.key_cert_num} Expires in {days_until_expiry} Days"
            from_email = mail_account.username
            recipient_list = [key_cert.owner.email] if key_cert.owner and key_cert.owner.email else [settings.DEFAULT_FROM_EMAIL]

            # Create the email message directly to avoid Django's SSL issues
            try:
                logger.info(f"Preparing to send reminder email via SMTP directly, server: {mail_account.server.smtp_host}:{mail_account.server.smtp_port}")
                
                # Create the email message
                msg = MIMEMultipart()
                msg['From'] = from_email
                msg['To'] = ", ".join(recipient_list)
                msg['Subject'] = subject
                msg.attach(MIMEText(message, 'plain'))
                
                # Connect to the server directly using smtplib
                if mail_account.server.use_ssl:
                    # Create SSL context without keyfile issues
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    
                    # Connect with SSL but avoid Django's connection wrapper
                    smtp = smtplib.SMTP_SSL(
                        host=mail_account.server.smtp_host,
                        port=mail_account.server.smtp_port,
                        context=context
                    )
                    logger.info("Connected using SSL")
                else:
                    # Connect without SSL
                    smtp = smtplib.SMTP(
                        host=mail_account.server.smtp_host,
                        port=mail_account.server.smtp_port
                    )
                    
                    # Use TLS if needed
                    if mail_account.server.use_tls:
                        smtp.starttls()
                        logger.info("Connected using TLS")
                    else:
                        logger.info("Connected without encryption")
                
                # Login and send
                smtp.login(mail_account.username, mail_account.password)
                smtp.send_message(msg)
                smtp.quit()
                
                logger.info(f"Email sent successfully to {recipient_list}")
            except Exception as e:
                logger.error(f"Failed to send email: {str(e)}")
                if self.request.retries < self.max_retries:
                    raise self.retry(exc=e)
                raise

            # Update reminder status
            reminder.is_sent = True
            reminder.sent_at = timezone.now()
            reminder.save(update_fields=['is_sent', 'sent_at'])

            # Create history entry for successful sending
            KeyCertHistory.objects.create(
                key_certificate=key_cert,
                action="reminder_sent",
                action_by=None,  # System action
                details=(
                    f"Reminder sent successfully\n"
                    f"Type: {reminder.get_reminder_type_display()}\n"
                    f"Sent at: {reminder.sent_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Days until expiry: {(key_cert.expiry_date - timezone.now().date()).days}\n"
                    f"Recipients: {key_cert.owner.email if key_cert.owner else settings.DEFAULT_FROM_EMAIL}"
                )
            )

            logger.info(f"Successfully sent reminder [{reminder.id}] for certificate {key_cert_id}")
            return True, "Reminder sent successfully"

    except Exception as e:
        error_message = f"Error sending reminder: {str(e)}"
        logger.error(error_message)

        # Create history entry for failed attempt
        try:
            KeyCertHistory.objects.create(
                key_certificate=key_cert,
                action="reminder_failed",
                action_by=None,  # System action
                details=f"Failed to send reminder: {error_message}"
            )
        except Exception as hist_error:
            logger.error(f"Failed to create history entry: {str(hist_error)}")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return False, error_message

def schedule_reminder(key_cert, reminder_type, reminder_days=None, reminder_date=None):
    """Schedule a reminder for a key/certificate."""
    try:
        logger.info(f"Scheduling reminder for certificate {key_cert.id} "
                   f"(type: {reminder_type}, days: {reminder_days}, date: {reminder_date})")

        if reminder_type == 'days' and reminder_days is not None:
            reminder_date = timezone.now() + timedelta(days=reminder_days)
        elif reminder_type == 'date' and reminder_date is not None:
            reminder_date = timezone.make_aware(reminder_date) if timezone.is_naive(reminder_date) else reminder_date
        else:
            logger.error(f"Invalid reminder parameters for certificate {key_cert.id}")
            return {
                'success': False,
                'message': 'Invalid reminder parameters'
            }

        # Cancel existing reminders
        with transaction.atomic():
            cancelled = Reminder.objects.filter(
                key_certificate=key_cert,
                is_cancelled=False
            ).update(
                is_cancelled=True,
                cancelled_at=timezone.now()
            )

            if cancelled:
                logger.info(f"Cancelled {cancelled} existing reminders for certificate {key_cert.id}")

            # Create new reminder
            reminder = Reminder.objects.create(
                key_certificate=key_cert,
                reminder_type=reminder_type,
                reminder_days=reminder_days,
                reminder_date=reminder_date,
                is_sent=False,
                is_cancelled=False
            )

            logger.info(f"Created new reminder [{reminder.id}] for certificate {key_cert.id}")
            return {
                'success': True,
                'message': 'Reminder scheduled successfully',
                'reminder_id': reminder.id
            }

    except Exception as e:
        logger.error(f"Error scheduling reminder for certificate {key_cert.id}: {str(e)}",
                     exc_info=True)
        return {
            'success': False,
            'message': str(e)
        }

def cancel_reminder(key_cert):
    """Cancel active reminders for a key/certificate."""
    try:
        with transaction.atomic():
            reminders = Reminder.objects.select_for_update().filter(
                key_certificate=key_cert,
                is_sent=False,
                is_cancelled=False
            )

            cancelled_count = reminders.update(
                is_cancelled=True,
                cancelled_at=timezone.now()
            )

            message = (f"Cancelled {cancelled_count} reminders for key/certificate {key_cert.key_cert_num}"
                      if cancelled_count > 0 else
                      f"No active reminders found for key/certificate {key_cert.key_cert_num}")

            logger.info(message)
            return message

    except Exception as e:
        error_message = f"Error cancelling reminders: {str(e)}"
        logger.error(error_message)
        return error_message


@shared_task
@ensure_unique_task(timeout=3600)
def check_reminders():
    """Periodic task to check and send reminders."""
    logger.info("Starting periodic reminder check")

    try:
        with transaction.atomic():
            reminders = Reminder.objects.select_for_update(nowait=True).filter(
                is_sent=False,
                is_cancelled=False
            ).select_related(
                'key_certificate',
                'key_certificate__owner'
            )

            current_time = timezone.now()
            sent_count = 0

            for reminder in reminders:
                try:
                    logger.info(f"Checking reminder [{reminder.id}] for certificate {reminder.key_certificate.id}")

                    if reminder.is_due():
                        task = send_reminder_email.apply_async(args=[reminder.key_certificate.id])
                        reminder.celery_task_id = task.id
                        reminder.save(update_fields=['celery_task_id'])
                        sent_count += 1
                        logger.info(f"Queued reminder [{reminder.id}] for sending (task_id: {task.id})")

                except Exception as e:
                    logger.error(f"Error processing reminder [{reminder.id}]: {str(e)}",
                                 exc_info=True)
                    continue

            logger.info(
                f"Reminder check completed. Processed {len(reminders)} reminders, queued {sent_count} for sending")
            return {
                'success': True,
                'message': f'Processed {len(reminders)} reminders, sent {sent_count} notifications'
            }

    except Exception as e:
        error_message = f"Error in check_reminders task: {str(e)}"
        logger.error(error_message, exc_info=True)
        return {
            'success': False,
            'message': error_message
        }


@shared_task
def cleanup_old_reminders():
    """Clean up old reminders that have been sent and are no longer needed."""
    try:
        # Delete sent reminders older than 90 days
        cutoff_date = timezone.now() - timedelta(days=90)
        old_reminders = Reminder.objects.filter(
            is_sent=True,
            sent_at__lt=cutoff_date
        )
        count = old_reminders.count()
        old_reminders.delete()
        logger.info(f"Cleaned up {count} old reminders")
        return True, f"Cleaned up {count} old reminders"
    except Exception as e:
        logger.error(f"Error cleaning up old reminders: {str(e)}")
        return False, f"Error cleaning up old reminders: {str(e)}"


@shared_task
def beat_heartbeat():
    """Update Redis with the current timestamp to verify Beat is running."""
    try:
        current_time = time.time()
        redis_client.set('celery-beat-heartbeat', str(current_time), ex=120)  # expires in 2 minutes
        logger.info(f"Beat heartbeat updated at {current_time}")
        return True, "Beat heartbeat updated successfully"
    except Exception as e:
        logger.error(f"Error updating beat heartbeat: {str(e)}")
        return False, f"Error updating beat heartbeat: {str(e)}"


@shared_task(bind=True)
def test_celery(self):
    """Test Celery configuration with a simple task."""
    logger.info(f"Running test task with id: {self.request.id}")
    try:
        # Test Redis connection
        if redis_client and redis_client.ping():
            logger.info("Redis connection test successful")
            result = {"redis_test": "success"}
        else:
            logger.warning("Redis connection test failed")
            result = {"redis_test": "failed"}

        # Test database connection
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
                logger.info("Database connection test successful")
                result["db_test"] = "success"
        except Exception as e:
            logger.error(f"Database test failed: {str(e)}")
            result["db_test"] = "failed"

        logger.info(f"Test task completed: {result}")
        return {
            'status': 'success',
            'task_id': self.request.id,
            'tests': result,
            'timestamp': timezone.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Test task failed: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'task_id': self.request.id,
            'timestamp': timezone.now().isoformat()
        }


def test_redis_connection():
    try:
        # Create Redis client
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )

        # Test connection
        pong = redis_client.ping()
        print(f"Redis connection test: {'SUCCESS' if pong else 'FAILED'}")

        # Test basic operations
        redis_client.set('test_key', 'test_value')
        value = redis_client.get('test_key')
        print(f"Redis test value: {value}")

        return True

    except redis.ConnectionError as e:
        print(f"Redis connection error: {str(e)}")
        print("Please make sure Redis server is running")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False
