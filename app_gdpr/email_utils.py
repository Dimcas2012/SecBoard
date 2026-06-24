#  SecBoard\SecBoard\app_gdpr\email_utils.py

import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import Template, Context
from django.conf import settings
from django.utils.translation import gettext as _
from app_conf.models import MailAccount, SiteSettings
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def get_default_mail_account():
    """Отримати акаунт пошти за замовчуванням"""
    try:
        mail_account = MailAccount.objects.filter(is_active=True).first()
        if not mail_account:
            mail_account = MailAccount.objects.first()
        return mail_account
    except Exception as e:
        logger.error(f"Error getting default mail account: {e}")
        return None


def send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, recipients):
    """
    Відправка email через smtplib
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = mail_account.username
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        msg.attach(text_part)
        
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        if mail_server.use_ssl:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            smtp = smtplib.SMTP_SSL(
                host=mail_server.smtp_host,
                port=mail_server.smtp_port,
                context=context
            )
        else:
            smtp = smtplib.SMTP(
                host=mail_server.smtp_host,
                port=mail_server.smtp_port
            )
            
            if mail_server.use_tls:
                smtp.starttls()
        
        smtp.login(mail_account.username, mail_account.password)
        smtp.send_message(msg)
        smtp.quit()
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending email via SMTP: {e}")
        return False


def send_dsr_confirmation_email(dsr):
    """
    Підтвердження отримання запиту суб'єкта даних
    
    Args:
        dsr: екземпляр DataSubjectRequest
    """
    try:
        mail_account = get_default_mail_account()
        if not mail_account:
            logger.warning("No mail account configured")
            return False
        
        mail_server = mail_account.server
        if not mail_server:
            logger.warning("No mail server configured")
            return False
        
        # Контекст для шаблону
        context = {
            'dsr': dsr,
            'data_subject': dsr.data_subject,
            'request_number': dsr.request_number,
            'request_type': dsr.get_request_type_display(),
            'due_date': dsr.due_date,
            'site_domain': SiteSettings.get_settings().site_domain,
            'site_protocol': SiteSettings.get_settings().site_protocol,
        }
        
        subject = _(f'Data Subject Request Confirmation - {dsr.request_number}')
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>DSR Confirmation</title>
        </head>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #007bff;">Data Subject Request Received</h2>
                <p>Dear {context['data_subject'].first_name} {context['data_subject'].last_name},</p>
                <p>We have received your data subject request:</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
                    <strong>Request Number:</strong> {context['request_number']}<br>
                    <strong>Request Type:</strong> {context['request_type']}<br>
                    <strong>Due Date:</strong> {context['due_date']}<br>
                </div>
                
                <p>We will process your request within 30 days as required by GDPR Article 15.</p>
                <p>You will receive a response by email once your request has been processed.</p>
                
                <hr style="margin: 30px 0;">
                <p style="font-size: 12px; color: #6c757d;">
                    This is an automated message from SecBoard GDPR Management System.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
Data Subject Request Received

Dear {context['data_subject'].first_name} {context['data_subject'].last_name},

We have received your data subject request:

Request Number: {context['request_number']}
Request Type: {context['request_type']}
Due Date: {context['due_date']}

We will process your request within 30 days as required by GDPR Article 15.
You will receive a response by email once your request has been processed.

---
This is an automated message from SecBoard GDPR Management System.
        """
        
        recipients = [dsr.data_subject.email]
        
        if send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, recipients):
            logger.info(f"DSR confirmation email sent to {dsr.data_subject.email}")
            return True
        else:
            logger.error(f"Failed to send DSR confirmation email")
            return False
            
    except Exception as e:
        logger.error(f"Error sending DSR confirmation email: {e}")
        return False


def send_dsr_completion_email(dsr):
    """
    Повідомлення про виконання запиту суб'єкта даних
    
    Args:
        dsr: екземпляр DataSubjectRequest
    """
    try:
        mail_account = get_default_mail_account()
        if not mail_account:
            return False
        
        mail_server = mail_account.server
        if not mail_server:
            return False
        
        context = {
            'dsr': dsr,
            'data_subject': dsr.data_subject,
            'request_number': dsr.request_number,
            'request_type': dsr.get_request_type_display(),
            'response_text': dsr.response_text,
            'completion_date': dsr.completion_date,
        }
        
        subject = _(f'Data Subject Request Completed - {dsr.request_number}')
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>DSR Completed</title>
        </head>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #28a745;">Data Subject Request Completed</h2>
                <p>Dear {context['data_subject'].first_name} {context['data_subject'].last_name},</p>
                <p>Your data subject request has been completed:</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0;">
                    <strong>Request Number:</strong> {context['request_number']}<br>
                    <strong>Request Type:</strong> {context['request_type']}<br>
                    <strong>Completion Date:</strong> {context['completion_date']}<br>
                </div>
                
                <div style="background-color: #e9ecef; padding: 15px; margin: 20px 0;">
                    <h3>Response:</h3>
                    <p>{context['response_text']}</p>
                </div>
                
                <p>If you have any questions regarding this response, please contact us.</p>
                
                <hr style="margin: 30px 0;">
                <p style="font-size: 12px; color: #6c757d;">
                    This is an automated message from SecBoard GDPR Management System.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
Data Subject Request Completed

Dear {context['data_subject'].first_name} {context['data_subject'].last_name},

Your data subject request has been completed:

Request Number: {context['request_number']}
Request Type: {context['request_type']}
Completion Date: {context['completion_date']}

Response:
{context['response_text']}

If you have any questions regarding this response, please contact us.

---
This is an automated message from SecBoard GDPR Management System.
        """
        
        recipients = [dsr.data_subject.email]
        
        if send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, recipients):
            logger.info(f"DSR completion email sent to {dsr.data_subject.email}")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Error sending DSR completion email: {e}")
        return False


def send_consent_expiration_reminder(consent_record):
    """
    Нагадування про закінчення терміну згоди
    
    Args:
        consent_record: екземпляр ConsentRecord
    """
    try:
        mail_account = get_default_mail_account()
        if not mail_account:
            return False
        
        mail_server = mail_account.server
        if not mail_server:
            return False
        
        context = {
            'consent': consent_record,
            'data_subject': consent_record.data_subject,
            'consent_type': consent_record.get_consent_type_display(),
            'expiration_date': consent_record.expiration_date,
        }
        
        subject = _('Consent Expiration Reminder')
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Consent Expiration Reminder</title>
        </head>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ffc107;">Consent Expiration Reminder</h2>
                <p>Dear {context['data_subject'].first_name} {context['data_subject'].last_name},</p>
                <p>Your consent for data processing is expiring soon:</p>
                
                <div style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
                    <strong>Consent Type:</strong> {context['consent_type']}<br>
                    <strong>Expiration Date:</strong> {context['expiration_date']}<br>
                </div>
                
                <p>If you wish to renew your consent, please contact us or visit our website.</p>
                <p>If we do not hear from you, your data processing consent will expire and your data will be handled according to our retention policy.</p>
                
                <hr style="margin: 30px 0;">
                <p style="font-size: 12px; color: #6c757d;">
                    This is an automated message from SecBoard GDPR Management System.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
Consent Expiration Reminder

Dear {context['data_subject'].first_name} {context['data_subject'].last_name},

Your consent for data processing is expiring soon:

Consent Type: {context['consent_type']}
Expiration Date: {context['expiration_date']}

If you wish to renew your consent, please contact us or visit our website.
If we do not hear from you, your data processing consent will expire and your data will be handled according to our retention policy.

---
This is an automated message from SecBoard GDPR Management System.
        """
        
        recipients = [consent_record.data_subject.email]
        
        if send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, recipients):
            logger.info(f"Consent expiration reminder sent to {consent_record.data_subject.email}")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Error sending consent expiration reminder: {e}")
        return False


def send_breach_notification_email(incident, recipients):
    """
    Повідомлення про витік даних (для регулятора або постраждалих осіб)
    
    Args:
        incident: екземпляр DataBreachIncident
        recipients: список email адрес
    """
    try:
        mail_account = get_default_mail_account()
        if not mail_account:
            return False
        
        mail_server = mail_account.server
        if not mail_server:
            return False
        
        context = {
            'incident': incident,
            'incident_number': incident.incident_number,
            'title': incident.title,
            'incident_date': incident.incident_date,
            'discovery_date': incident.discovery_date,
            'affected_count': incident.affected_subjects_count,
            'data_types': incident.data_types_affected,
            'severity': incident.get_severity_display(),
            'mitigation': incident.mitigation_actions,
        }
        
        subject = _(f'Data Breach Notification - {incident.incident_number}')
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Data Breach Notification</title>
        </head>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #dc3545;">Data Breach Notification</h2>
                <p><strong>IMPORTANT: Security Incident Notification</strong></p>
                
                <div style="background-color: #f8d7da; padding: 15px; border-left: 4px solid #dc3545; margin: 20px 0;">
                    <strong>Incident Number:</strong> {context['incident_number']}<br>
                    <strong>Title:</strong> {context['title']}<br>
                    <strong>Incident Date:</strong> {context['incident_date']}<br>
                    <strong>Discovery Date:</strong> {context['discovery_date']}<br>
                    <strong>Severity:</strong> {context['severity']}<br>
                    <strong>Affected Subjects:</strong> {context['affected_count']}<br>
                </div>
                
                <h3>Data Types Affected:</h3>
                <p>{context['data_types']}</p>
                
                <h3>Mitigation Actions:</h3>
                <p>{context['mitigation']}</p>
                
                <p>We take this matter very seriously and are taking all necessary steps to address this incident and protect your data.</p>
                
                <hr style="margin: 30px 0;">
                <p style="font-size: 12px; color: #6c757d;">
                    This is an automated message from SecBoard GDPR Management System.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
Data Breach Notification

IMPORTANT: Security Incident Notification

Incident Number: {context['incident_number']}
Title: {context['title']}
Incident Date: {context['incident_date']}
Discovery Date: {context['discovery_date']}
Severity: {context['severity']}
Affected Subjects: {context['affected_count']}

Data Types Affected:
{context['data_types']}

Mitigation Actions:
{context['mitigation']}

We take this matter very seriously and are taking all necessary steps to address this incident and protect your data.

---
This is an automated message from SecBoard GDPR Management System.
        """
        
        success_count = 0
        for recipient in recipients:
            if send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, [recipient]):
                success_count += 1
                logger.info(f"Breach notification sent to {recipient}")
        
        return success_count > 0
            
    except Exception as e:
        logger.error(f"Error sending breach notification email: {e}")
        return False


def send_dsr_deadline_reminder_email(dsr, urgent=False):
    """Нагадування про дедлайн DSR"""
    try:
        mail_account = get_default_mail_account()
        if not mail_account or not mail_account.server:
            return False
        
        if not dsr.assigned_to or not dsr.assigned_to.email:
            return False
        
        urgency_label = "URGENT" if urgent else "Reminder"
        subject = f"[{urgency_label}] DSR Deadline - {dsr.request_number}"
        
        html_content = f"""
        <h2>{urgency_label}: DSR Deadline Approaching</h2>
        <p>Request Number: {dsr.request_number}</p>
        <p>Due Date: {dsr.due_date}</p>
        <p>Status: {dsr.get_status_display()}</p>
        <p>Data Subject: {dsr.data_subject.email}</p>
        """
        
        text_content = f"{urgency_label}: DSR Deadline\nRequest: {dsr.request_number}\nDue: {dsr.due_date}"
        
        return send_email_via_smtplib(
            mail_account.server, mail_account, subject, text_content, html_content, [dsr.assigned_to.email]
        )
    except Exception as e:
        logger.error(f"Error sending DSR deadline reminder: {e}")
        return False


def send_breach_deadline_alert(breach, overdue=False):
    """Попередження про дедлайн повідомлення про витік"""
    try:
        mail_account = get_default_mail_account()
        if not mail_account or not mail_account.server:
            return False
        
        if not breach.assigned_to or not breach.assigned_to.email:
            return False
        
        status_label = "OVERDUE" if overdue else "WARNING"
        subject = f"[{status_label}] Breach Notification Deadline - {breach.incident_number}"
        
        html_content = f"""
        <h2>{status_label}: 72-Hour Notification Deadline</h2>
        <p>Incident: {breach.incident_number}</p>
        <p>Deadline: {breach.notification_deadline}</p>
        <p>{'<strong style="color:red;">DEADLINE HAS PASSED!</strong>' if overdue else 'Deadline approaching!'}</p>
        """
        
        text_content = f"{status_label}: Breach {breach.incident_number}\nDeadline: {breach.notification_deadline}"
        
        return send_email_via_smtplib(
            mail_account.server, mail_account, subject, text_content, html_content, [breach.assigned_to.email]
        )
    except Exception as e:
        logger.error(f"Error sending breach deadline alert: {e}")
        return False


def send_compliance_report_email(report_data, company=None):
    """Надсилання звіту про відповідність GDPR"""
    # Базова реалізація - можна розширити
    logger.info(f"Compliance report generated for {company.name if company else 'all companies'}")
    return True


def send_dsr_extension_notification(dsr):
    """Повідомлення про продовження терміну DSR"""
    try:
        return send_dsr_confirmation_email(dsr)  # Використовуємо ту ж логіку
    except Exception as e:
        logger.error(f"Error sending DSR extension notification: {e}")
        return False


def send_activity_review_reminder(activity):
    """Нагадування про перегляд діяльності з обробки даних"""
    logger.info(f"Activity review reminder for {activity.get_name() or activity.name}")
    return True

