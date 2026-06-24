#  SecBoard\SecBoard\app_gdpr\tasks.py

import logging
from celery import shared_task
from django.utils import timezone
from django.utils.translation import gettext as _
from django.db.models import Q
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task
def check_consent_expiration():
    """
    Перевірка закінчення терміну згоди на обробку даних
    Запускається щоденно
    """
    from .models import ConsentRecord
    from .email_utils import send_consent_expiration_reminder
    
    try:
        today = timezone.now().date()
        
        # Знаходимо згоди, які закінчуються через 30 днів
        expiring_soon = ConsentRecord.objects.filter(
            is_active=True,
            expiration_date__lte=today + timedelta(days=30),
            expiration_date__gte=today
        )
        
        # Знаходимо згоди, які вже закінчилися
        expired = ConsentRecord.objects.filter(
            is_active=True,
            expiration_date__lt=today
        )
        
        # Автоматично деактивуємо закінчені згоди
        expired_count = 0
        for consent in expired:
            consent.is_active = False
            consent.save()
            expired_count += 1
            
            # Оновлюємо статус суб'єкта даних
            data_subject = consent.data_subject
            data_subject.consent_status = 'expired'
            data_subject.save()
            
            logger.info(f"Consent expired for {data_subject.email}: {consent.consent_type}")
        
        # Надсилаємо нагадування про згоди, що закінчуються
        reminder_count = 0
        for consent in expiring_soon:
            try:
                send_consent_expiration_reminder(consent)
                reminder_count += 1
            except Exception as e:
                logger.error(f"Error sending consent expiration reminder: {e}")
        
        logger.info(
            f"Consent expiration check completed: "
            f"{expired_count} expired, {reminder_count} reminders sent"
        )
        
        return {
            'success': True,
            'expired_count': expired_count,
            'reminder_count': reminder_count,
            'message': f"Checked consents: {expired_count} expired, {reminder_count} reminders sent"
        }
        
    except Exception as e:
        logger.error(f"Error in check_consent_expiration task: {e}")
        return {
            'success': False,
            'message': str(e)
        }


@shared_task
def check_data_retention_deadlines():
    """
    Перевірка дедлайнів утримання даних та автоматичне видалення/анонімізація
    Запускається щоденно
    """
    from .models import DataSubject, DataRetentionPolicy
    from .utils import anonymize_personal_data
    
    try:
        today = timezone.now().date()
        
        # Знаходимо суб'єктів, для яких настав час видалення
        subjects_for_deletion = DataSubject.objects.filter(
            deletion_scheduled_date__lte=today,
            is_anonymized=False
        )
        
        anonymized_count = 0
        for subject in subjects_for_deletion:
            try:
                # Перевіряємо, чи є активні згоди або відкриті DSR
                has_active_consent = subject.consents.filter(is_active=True).exists()
                has_pending_dsr = subject.dsr_requests.filter(
                    status__in=['pending', 'in_progress']
                ).exists()
                
                # Якщо є активні процеси, відкладаємо видалення
                if has_active_consent or has_pending_dsr:
                    logger.info(
                        f"Deletion postponed for {subject.email}: "
                        f"active processes exist"
                    )
                    # Відкладаємо на 30 днів
                    subject.deletion_scheduled_date = today + timedelta(days=30)
                    subject.save()
                    continue
                
                # Анонімізуємо дані
                if anonymize_personal_data(subject):
                    anonymized_count += 1
                    logger.info(f"Data anonymized for subject: {subject.email}")
                    
            except Exception as e:
                logger.error(f"Error anonymizing subject {subject.id}: {e}")
        
        # Застосовуємо автоматичні політики утримання
        auto_policies = DataRetentionPolicy.objects.filter(
            is_active=True,
            auto_apply=True
        )
        
        policies_applied = 0
        for policy in auto_policies:
            # Знаходимо суб'єктів без запланованої дати видалення
            applicable_subjects = DataSubject.objects.filter(
                company=policy.company,
                deletion_scheduled_date__isnull=True,
                is_anonymized=False
            )
            
            for subject in applicable_subjects:
                deletion_date = (
                    subject.last_activity_date + 
                    timedelta(days=policy.retention_period_days)
                ).date()
                
                subject.deletion_scheduled_date = deletion_date
                subject.save()
                policies_applied += 1
        
        logger.info(
            f"Data retention check completed: "
            f"{anonymized_count} anonymized, {policies_applied} policies applied"
        )
        
        return {
            'success': True,
            'anonymized_count': anonymized_count,
            'policies_applied': policies_applied,
            'message': f"{anonymized_count} subjects anonymized, {policies_applied} policies applied"
        }
        
    except Exception as e:
        logger.error(f"Error in check_data_retention_deadlines task: {e}")
        return {
            'success': False,
            'message': str(e)
        }


@shared_task
def send_dsr_deadline_reminder():
    """
    Надсилання нагадувань про дедлайни DSR (30 днів)
    Запускається щоденно
    """
    from .models import DataSubjectRequest
    from .email_utils import send_dsr_deadline_reminder_email
    
    try:
        today = timezone.now().date()
        
        # Знаходимо DSR, які наближаються до дедлайну (7 днів)
        upcoming_deadline = DataSubjectRequest.objects.filter(
            Q(status='pending') | Q(status='in_progress'),
            due_date__lte=today + timedelta(days=7),
            due_date__gte=today
        )
        
        # Знаходимо прострочені DSR
        overdue = DataSubjectRequest.objects.filter(
            Q(status='pending') | Q(status='in_progress'),
            due_date__lt=today
        )
        
        reminder_count = 0
        for dsr in upcoming_deadline:
            try:
                send_dsr_deadline_reminder_email(dsr, urgent=False)
                reminder_count += 1
            except Exception as e:
                logger.error(f"Error sending DSR reminder for {dsr.request_number}: {e}")
        
        overdue_count = 0
        for dsr in overdue:
            try:
                send_dsr_deadline_reminder_email(dsr, urgent=True)
                overdue_count += 1
            except Exception as e:
                logger.error(f"Error sending overdue DSR alert for {dsr.request_number}: {e}")
        
        logger.info(
            f"DSR deadline reminders sent: "
            f"{reminder_count} upcoming, {overdue_count} overdue"
        )
        
        return {
            'success': True,
            'reminder_count': reminder_count,
            'overdue_count': overdue_count,
            'message': f"{reminder_count} reminders sent, {overdue_count} overdue alerts sent"
        }
        
    except Exception as e:
        logger.error(f"Error in send_dsr_deadline_reminder task: {e}")
        return {
            'success': False,
            'message': str(e)
        }


@shared_task
def check_breach_notification_deadline():
    """
    Перевірка 72-годинного дедлайну повідомлення про витоки даних
    Запускається кожну годину
    """
    from .models import DataBreachIncident
    from .email_utils import send_breach_deadline_alert
    
    try:
        now = timezone.now()
        
        # Знаходимо витоки, про які не повідомлено
        unreported_breaches = DataBreachIncident.objects.filter(
            reported_to_authority=False,
            notification_deadline__isnull=False
        )
        
        overdue_count = 0
        warning_count = 0
        
        for breach in unreported_breaches:
            # Перевіряємо, чи пропущено дедлайн
            if breach.is_notification_overdue():
                try:
                    send_breach_deadline_alert(breach, overdue=True)
                    overdue_count += 1
                    logger.warning(
                        f"OVERDUE: Breach {breach.incident_number} notification deadline passed!"
                    )
                except Exception as e:
                    logger.error(f"Error sending overdue alert for breach {breach.incident_number}: {e}")
            
            # Попередження за 12 годин до дедлайну
            elif breach.notification_deadline - now <= timedelta(hours=12):
                try:
                    send_breach_deadline_alert(breach, overdue=False)
                    warning_count += 1
                    logger.warning(
                        f"WARNING: Breach {breach.incident_number} deadline approaching!"
                    )
                except Exception as e:
                    logger.error(f"Error sending warning for breach {breach.incident_number}: {e}")
        
        logger.info(
            f"Breach notification check completed: "
            f"{overdue_count} overdue, {warning_count} warnings sent"
        )
        
        return {
            'success': True,
            'overdue_count': overdue_count,
            'warning_count': warning_count,
            'message': f"{overdue_count} overdue, {warning_count} warnings sent"
        }
        
    except Exception as e:
        logger.error(f"Error in check_breach_notification_deadline task: {e}")
        return {
            'success': False,
            'message': str(e)
        }


@shared_task
def generate_gdpr_compliance_report(company_id=None):
    """
    Генерація звіту про відповідність GDPR
    Запускається щотижня або за запитом
    """
    from .models import Company
    from .utils import generate_compliance_report_data
    from .email_utils import send_compliance_report_email
    
    try:
        company = None
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                logger.error(f"Company with id {company_id} not found")
                return {
                    'success': False,
                    'message': f"Company with id {company_id} not found"
                }
        
        # Генеруємо дані звіту за останній місяць
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        report_data = generate_compliance_report_data(
            company=company,
            start_date=start_date,
            end_date=end_date
        )
        
        # Надсилаємо звіт відповідальним особам
        try:
            send_compliance_report_email(report_data, company)
        except Exception as e:
            logger.error(f"Error sending compliance report email: {e}")
        
        logger.info(
            f"GDPR compliance report generated for "
            f"{'company ' + company.name if company else 'all companies'}"
        )
        
        return {
            'success': True,
            'report_data': report_data,
            'message': "Compliance report generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error in generate_gdpr_compliance_report task: {e}")
        return {
            'success': False,
            'message': str(e)
        }


@shared_task
def cleanup_old_anonymized_data(days_to_keep=365):
    """
    Очищення старих анонімізованих даних
    Запускається щомісяця
    """
    from .models import DataSubject
    
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Знаходимо анонімізовані записи старші за вказаний період
        old_anonymized = DataSubject.objects.filter(
            is_anonymized=True,
            updated_date__lt=cutoff_date
        )
        
        count = old_anonymized.count()
        old_anonymized.delete()
        
        logger.info(f"Cleaned up {count} old anonymized data subject records")
        
        return {
            'success': True,
            'deleted_count': count,
            'message': f"Deleted {count} old anonymized records"
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_anonymized_data task: {e}")
        return {
            'success': False,
            'message': str(e)
        }


@shared_task
def auto_extend_dsr_deadline(request_id, additional_days=60):
    """
    Автоматичне продовження терміну DSR у складних випадках
    Викликається вручну або автоматично при певних умовах
    """
    from .models import DataSubjectRequest
    from .email_utils import send_dsr_extension_notification
    
    try:
        dsr = DataSubjectRequest.objects.get(id=request_id)
        
        # Продовжуємо дедлайн
        dsr.extend_deadline(additional_days=additional_days)
        
        # Надсилаємо повідомлення суб'єкту даних
        try:
            send_dsr_extension_notification(dsr)
        except Exception as e:
            logger.error(f"Error sending DSR extension notification: {e}")
        
        logger.info(
            f"DSR {dsr.request_number} deadline extended by {additional_days} days"
        )
        
        return {
            'success': True,
            'message': f"DSR deadline extended to {dsr.extended_due_date}"
        }
        
    except DataSubjectRequest.DoesNotExist:
        logger.error(f"DSR with id {request_id} not found")
        return {
            'success': False,
            'message': f"DSR with id {request_id} not found"
        }
    except Exception as e:
        logger.error(f"Error in auto_extend_dsr_deadline task: {e}")
        return {
            'success': False,
            'message': str(e)
        }


@shared_task
def audit_data_processing_activities():
    """
    Аудит діяльності з обробки даних
    Перевіряє актуальність записів
    Запускається щомісяця
    """
    from .models import DataProcessingActivity
    from .email_utils import send_activity_review_reminder
    
    try:
        # Знаходимо активності, які не оновлювалися більше 6 місяців
        six_months_ago = timezone.now() - timedelta(days=180)
        outdated_activities = DataProcessingActivity.objects.filter(
            is_active=True,
            updated_date__lt=six_months_ago
        )
        
        reminder_count = 0
        for activity in outdated_activities:
            if activity.responsible_person:
                try:
                    send_activity_review_reminder(activity)
                    reminder_count += 1
                except Exception as e:
                    logger.error(
                        f"Error sending review reminder for activity {activity.id}: {e}"
                    )
        
        logger.info(
            f"Data processing activities audit completed: "
            f"{reminder_count} review reminders sent"
        )
        
        return {
            'success': True,
            'reminder_count': reminder_count,
            'outdated_count': outdated_activities.count(),
            'message': f"{reminder_count} review reminders sent for outdated activities"
        }
        
    except Exception as e:
        logger.error(f"Error in audit_data_processing_activities task: {e}")
        return {
            'success': False,
            'message': str(e)
        }

