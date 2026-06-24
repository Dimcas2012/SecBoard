import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import Template, Context
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils import timezone
from app_conf.models import MailAccount, MailServer, GoogleTagSettings, SiteSettings
from django.contrib.auth.models import User
from typing import List, Dict, Any

from .email_template_presets import render_notification_email_content

logger = logging.getLogger(__name__)

def send_notification_email(config, notification_type, context, recipients, force_send=False):
    """
    Універсальна функція для відправки email повідомлень за конфігурацією
    
    Args:
        config: екземпляр EmailNotificationConfig
        notification_type: тип повідомлення ('request_created', 'status_changed', etc.)
        context: контекст для шаблону
        recipients: список email адрес для відправки
        force_send: примусова відправка (для тестування)
    
    Returns:
        bool: True якщо хоча б один email був відправлений успішно
    """
    if not config.is_active and not force_send:
        logger.info(f"Email configuration '{config.name}' is not active")
        return False
    
    try:
        # Визначаємо mail account та server
        mail_account = config.mail_account or get_default_mail_account()
        if not mail_account:
            logger.warning("No mail account configured for sending notifications")
            return False
        
        # Визначаємо mail server
        mail_server = config.mail_server or mail_account.server
        if not mail_server:
            logger.warning("No mail server configured for sending notifications")
            return False
        
        # Підготовка теми
        if notification_type == 'request_created':
            if config.use_custom_templates and config.request_created_subject_template:
                subject_template = Template(config.request_created_subject_template)
                subject = subject_template.render(Context(context))
            else:
                subject = _('📋 Test Email: New Access Request - {company_name} / {system_name}').format(**context)
        elif notification_type == 'status_changed':
            if config.use_custom_templates and config.status_changed_subject_template:
                subject_template = Template(config.status_changed_subject_template)
                subject = subject_template.render(Context(context))
            else:
                subject = _('🔄 Test Email: Status Changed - {company_name} / {system_name}').format(**context)
        else:
            subject = _('Test Email from {config_name}').format(**context)
        
        # Підготовка контенту
        if notification_type == 'request_created':
            if config.use_custom_templates and config.request_created_html_template:
                html_template = Template(config.request_created_html_template)
                html_content = html_template.render(Context(context))
            else:
                html_content = f"""
                <h2>🧪 Test Email - New Access Request</h2>
                <p><strong>Company:</strong> {context.get('company_name', 'N/A')}</p>
                <p><strong>System:</strong> {context.get('system_name', 'N/A')}</p>
                <p><strong>Environment:</strong> {context.get('environment', 'N/A')}</p>
                <p><strong>User:</strong> {context.get('user_full_name', 'N/A')}</p>
                <p><strong>Justification:</strong> {context.get('justification', 'N/A')}</p>
                <hr>
                <p><em>This is a test email sent from Email Configuration: {config.name}</em></p>
                """
            
            if config.use_custom_templates and config.request_created_text_template:
                text_template = Template(config.request_created_text_template)
                text_content = text_template.render(Context(context))
            else:
                text_content = f"""
Test Email - New Access Request

Company: {context.get('company_name', 'N/A')}
System: {context.get('system_name', 'N/A')}
Environment: {context.get('environment', 'N/A')}
User: {context.get('user_full_name', 'N/A')}
Justification: {context.get('justification', 'N/A')}

This is a test email sent from Email Configuration: {config.name}
                """
        else:
            # Status changed or other types
            html_content = f"""
            <h2>🧪 Test Email - Status Update</h2>
            <p><strong>Company:</strong> {context.get('company_name', 'N/A')}</p>
            <p><strong>System:</strong> {context.get('system_name', 'N/A')}</p>
            <p><strong>Status Change:</strong> {context.get('old_status', 'N/A')} → {context.get('new_status', 'N/A')}</p>
            <hr>
            <p><em>This is a test email sent from Email Configuration: {config.name}</em></p>
            """
            
            text_content = f"""
Test Email - Status Update

Company: {context.get('company_name', 'N/A')}
System: {context.get('system_name', 'N/A')}
Status Change: {context.get('old_status', 'N/A')} → {context.get('new_status', 'N/A')}

This is a test email sent from Email Configuration: {config.name}
            """
        
        # Відправка email
        success_count = 0
        for recipient_email in recipients:
            try:
                # Use smtplib directly instead of Django's email backend
                if send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, [recipient_email]):
                    success_count += 1
                    logger.info(f"Test email sent to {recipient_email} using config '{config.name}'")
                else:
                    logger.error(f"Failed to send test email to {recipient_email}")
                    
            except Exception as e:
                logger.error(f"Failed to send test email to {recipient_email}: {e}")
                continue
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        return False

def get_default_mail_account():
    """Отримати акаунт пошти за замовчуванням"""
    try:
        # Спочатку пробуємо знайти активний акаунт
        mail_account = MailAccount.objects.filter(is_active=True).first()
        if not mail_account:
            # Якщо немає активного, беремо будь-який
            mail_account = MailAccount.objects.first()
        return mail_account
    except Exception as e:
        logger.error(f"Error getting default mail account: {e}")
        return None

def send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, recipients):
    """
    Send email using smtplib directly
    
    Args:
        mail_server: MailServer instance
        mail_account: MailAccount instance
        subject: Email subject
        text_content: Plain text content
        html_content: HTML content
        recipients: List of recipient email addresses
    
    Returns:
        bool: True if email was sent successfully
    """
    try:
        # Create the email message
        msg = MIMEMultipart('alternative')
        msg['From'] = mail_account.username
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        # Add text part
        text_part = MIMEText(text_content, 'plain')
        msg.attach(text_part)
        
        # Add HTML part
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Connect to the server directly using smtplib
        if mail_server.use_ssl:
            # Create SSL context without keyfile issues
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Connect with SSL
            logger.info(f"Connecting with SSL to {mail_server.smtp_host}:{mail_server.smtp_port}")
            smtp = smtplib.SMTP_SSL(
                host=mail_server.smtp_host,
                port=mail_server.smtp_port,
                context=context
            )
            logger.info("Connected to mail server using SSL")
        else:
            # Connect without SSL
            logger.info(f"Connecting without SSL to {mail_server.smtp_host}:{mail_server.smtp_port}")
            smtp = smtplib.SMTP(
                host=mail_server.smtp_host,
                port=mail_server.smtp_port
            )
            
            # Use TLS if needed
            if mail_server.use_tls:
                logger.info("Starting TLS")
                smtp.starttls()
                logger.info("Connected to mail server using TLS")
        
        # Login and send
        logger.info(f"Logging in with username: {mail_account.username}")
        smtp.login(mail_account.username, mail_account.password)
        
        logger.info(f"Sending message to {recipients}")
        smtp.send_message(msg)
        smtp.quit()
        
        logger.info("Email sent successfully using direct SMTP method")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication error: {e}")
        if "534" in str(e) and "5.7.9" in str(e):
            logger.error("Authentication error. Make sure you're using an app password if you have two-factor authentication enabled.")
        return False
    except Exception as e:
        logger.error(f"Error sending email via SMTP: {e}")
        return False

def send_access_request_notification(access_request, recipients_type='all'):
    """
    Відправка email повідомлення про новий запит доступу
    
    Args:
        access_request: екземпляр AccessRequest
        recipients_type: 'owners', 'approvers', або 'all' (deprecated, використовується конфігурація)
    """
    # Імпортуємо тут щоб уникнути циклічного імпорту
    from .models import EmailNotificationHistory, EmailNotificationConfig
    
    notification_history = None
    try:
        # Отримуємо активну конфігурацію для цього запиту
        config = EmailNotificationConfig.get_active_config_for_request(access_request)
        
        if not config:
            logger.info(f"No active email configuration found for access request {access_request.id}")
            return False
        
        if not config.send_on_request_created:
            logger.info(f"Email notifications for request creation are disabled in configuration '{config.name}'")
            return False
        
        # Визначаємо mail account та server
        mail_account = config.mail_account or get_default_mail_account()
        if not mail_account:
            logger.warning("No mail account configured for sending notifications")
            return False
        
        # Визначаємо mail server
        mail_server = config.mail_server or mail_account.server
        if not mail_server:
            logger.warning("No mail server configured for sending notifications")
            return False
        
        # Отримуємо список отримувачів згідно з конфігурацією
        recipients = config.get_recipients_for_request(access_request, 'request_created')
        
        if not recipients:
            logger.warning(f"No recipients found for access request {access_request.id} with configuration '{config.name}'")
            return False
        
        # Створюємо запис в історії email повідомлень
        recipients_emails = [r['email'] for r in recipients]
        
        # Перевіряємо, чи є дані третьої сторони
        has_third_party = bool(access_request.third_party_first_name or access_request.third_party_last_name)
        third_party_name = ""
        third_party_users = []
        
        if has_third_party:
            # Якщо є множинні третіх сторін, використовуємо їх
            if access_request.third_party_users_data and isinstance(access_request.third_party_users_data, list):
                third_party_users = access_request.third_party_users_data
                # Формуємо назву з усіх користувачів
                names = [f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() 
                        for user in third_party_users if user.get('first_name') or user.get('last_name')]
                if len(names) > 1:
                    third_party_name = f"{', '.join(names[:-1])} and {names[-1]}"
                elif len(names) == 1:
                    third_party_name = names[0]
                else:
                    third_party_name = "Third Party Users"
            else:
                # Використовуємо одну третю сторону з основних полів
                third_party_name = f"{access_request.third_party_first_name} {access_request.third_party_last_name}".strip()
                third_party_users = [{
                    'first_name': access_request.third_party_first_name,
                    'last_name': access_request.third_party_last_name,
                    'email': access_request.third_party_email,
                    'phone': access_request.third_party_phone,
                    'organization': access_request.third_party_organization,
                    'description': access_request.third_party_description,
                }]
        
        # Підготовка даних про access records з їх об'єктами та ролями
        access_records_data = []
        all_roles = []
        
        for access_record in access_request.access_records.all():
            record_roles = list(access_record.roles.all())
            all_roles.extend(record_roles)
            
            access_records_data.append({
                'object_name': access_record.access_object.get_name() if access_record.access_object else _('No Object'),
                'object_color': access_record.access_object.color if access_record.access_object and hasattr(access_record.access_object, 'color') else '#495057',
                'roles': record_roles,
                'environment': access_record.environment,
            })
        
        # Для зворотної сумісності - використовуємо перший об'єкт як основний
        first_record = access_request.access_records.first()
        main_object_name = first_record.access_object.get_name() if first_record and first_record.access_object else _('No Object')
        
        # Підготовка контексту для шаблону
        context = {
            'access_request': access_request,
            'company_name': access_request.company.name,
            'system_name': access_request.system.name,
            'object_name': main_object_name,  # Основний об'єкт для заголовка
            'access_records_data': access_records_data,  # Всі access records з об'єктами та ролями
            'has_multiple_objects': len(access_records_data) > 1,  # Флаг для множинних об'єктів
            'environment': access_request.get_environment_display(),
            'requested_for': access_request.requested_for.get_full_name() or access_request.requested_for.username,
            'requested_by': access_request.requested_by.get_full_name() or access_request.requested_by.username,
            'justification': access_request.justification,
            'requirements': access_request.requirements,
            'notes': access_request.notes,
            'start_date': access_request.start_date,
            'end_date': access_request.end_date,
            'roles': all_roles,  # Всі ролі з усіх access records
            'request_type': access_request.get_request_type_display(),
            'site_domain': SiteSettings.get_settings().site_domain,
            'site_protocol': SiteSettings.get_settings().site_protocol,
            # Дані третьої сторони (підтримка множинних користувачів)
            'has_third_party': has_third_party,
            'third_party_name': third_party_name,
            'third_party_users': third_party_users,
            'third_party_count': len(third_party_users) if third_party_users else 0,
            # Зберігаємо старі поля для зворотної сумісності
            'third_party_first_name': access_request.third_party_first_name,
            'third_party_last_name': access_request.third_party_last_name,
            'third_party_email': access_request.third_party_email,
            'third_party_phone': access_request.third_party_phone,
            'third_party_organization': access_request.third_party_organization,
            'third_party_description': access_request.third_party_description,
            'include_third_party_info': config.include_third_party_info_in_emails if config else True,
        }
        
        subject, _, _ = render_notification_email_content(config, 'request_created', context)

        notification_history = EmailNotificationHistory.create_notification(
            notification_type='access_request_created',
            subject=subject,
            recipients=recipients_emails,
            access_request=access_request,
            triggered_by=access_request.requested_by,
            mail_account=mail_account,
            template_data={
                'config_name': config.name,
                'recipients_count': len(recipients),
                'use_custom_templates': config.use_custom_templates
            }
        )
        
        # Відправка email кожному отримувачу
        success_count = 0
        for recipient in recipients:
            try:
                # Додаємо інформацію про отримувача до контексту
                context['recipient_name'] = recipient['name']
                context['recipient_role'] = recipient['role']
                
                subject, html_content, text_content = render_notification_email_content(
                    config, 'request_created', context
                )

                # Use smtplib directly instead of Django's email backend
                if send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, [recipient['email']]):
                    success_count += 1
                else:
                    logger.error(f"Failed to send notification to {recipient['email']}")
                    continue
                
                logger.info(f"Access request notification sent to {recipient['email']} for request {access_request.id} using config '{config.name}'")
                
            except Exception as e:
                logger.error(f"Failed to send notification to {recipient['email']}: {e}")
                continue
        
        logger.info(f"Successfully sent {success_count}/{len(recipients)} notifications for access request {access_request.id} using config '{config.name}'")
        
        # Оновлюємо статус в історії
        if notification_history:
            if success_count > 0:
                notification_history.mark_as_sent()
            else:
                notification_history.mark_as_failed(f"Failed to send to all {len(recipients)} recipients")
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error sending access request notifications: {e}")
        
        # Відмічаємо помилку в історії
        if notification_history:
            notification_history.mark_as_failed(str(e))
        
        return False

def send_access_request_status_notification(
    access_request,
    old_status,
    new_status,
    changed_by,
    comment='',
    status_type='approver',
    status_change_context=None,
):
    """
    Відправка email повідомлення про зміну статусу запиту доступу
    
    Args:
        access_request: екземпляр AccessRequest
        old_status: старий статус
        new_status: новий статус  
        changed_by: користувач, який змінив статус
        comment: коментар до зміни статусу
        status_type: тип статусу ('approver' або 'admin')
        status_change_context: додатковий контекст для фільтрації Approving Persons за рівнем
    """
    # Імпортуємо тут щоб уникнути циклічного імпорту
    from .models import EmailNotificationHistory, EmailNotificationConfig
    
    notification_history = None
    try:
        # Отримуємо активну конфігурацію для цього запиту
        config = EmailNotificationConfig.get_active_config_for_request(access_request)
        
        if not config:
            logger.info(f"No active email configuration found for access request {access_request.id}")
            return False
        
        # Перевіряємо, чи увімкнені сповіщення для цього типу статусу
        if status_type == 'admin' and not config.send_on_admin_status_changed:
            logger.info(f"Admin status change notifications are disabled in configuration '{config.name}'")
            return False
        elif status_type == 'approver' and not config.send_on_status_changed:
            logger.info(f"Status change notifications are disabled in configuration '{config.name}'")
            return False
        
        # Визначаємо mail account та server
        mail_account = config.mail_account or get_default_mail_account()
        if not mail_account:
            logger.warning("No mail account configured for sending notifications")
            return False
        
        # Визначаємо mail server
        mail_server = config.mail_server or mail_account.server
        if not mail_server:
            logger.warning("No mail server configured for sending notifications")
            return False
        
        # Отримуємо список отримувачів згідно з конфігурацією
        approver_ctx = dict(status_change_context or {})
        approver_ctx.setdefault('status_type', status_type)
        approver_ctx.setdefault('new_status', new_status)
        approver_ctx.setdefault('old_status', old_status)
        recipients = config.get_recipients_for_request(
            access_request,
            'status_changed',
            status_change_context=approver_ctx,
        )
        
        if not recipients:
            logger.warning(f"No recipients found for status change notification for access request {access_request.id}")
            return False
        
        # Визначаємо тип сповіщення
        notification_type = 'admin_status_changed' if status_type == 'admin' else 'access_request_status_changed'
        
        # Перевіряємо, чи є дані третьої сторони
        has_third_party = bool(access_request.third_party_first_name or access_request.third_party_last_name)
        third_party_name = ""
        third_party_users = []
        
        if has_third_party:
            # Якщо є множинні третіх сторін, використовуємо їх
            if access_request.third_party_users_data and isinstance(access_request.third_party_users_data, list):
                third_party_users = access_request.third_party_users_data
                # Формуємо назву з усіх користувачів
                names = [f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() 
                        for user in third_party_users if user.get('first_name') or user.get('last_name')]
                if len(names) > 1:
                    third_party_name = f"{', '.join(names[:-1])} and {names[-1]}"
                elif len(names) == 1:
                    third_party_name = names[0]
                else:
                    third_party_name = "Third Party Users"
            else:
                # Використовуємо одну третю сторону з основних полів
                third_party_name = f"{access_request.third_party_first_name} {access_request.third_party_last_name}".strip()
                third_party_users = [{
                    'first_name': access_request.third_party_first_name,
                    'last_name': access_request.third_party_last_name,
                    'email': access_request.third_party_email,
                    'phone': access_request.third_party_phone,
                    'organization': access_request.third_party_organization,
                    'description': access_request.third_party_description,
                }]
        
        # Підготовка контексту для шаблону
        context = {
            'access_request': access_request,
            'old_status': old_status,
            'new_status': new_status,
            'changed_by': changed_by.get_full_name() or changed_by.username,
            'comment': comment,
            'company_name': access_request.company.name,
            'system_name': access_request.system.name,
            'object_name': access_request.access_records.first().access_object.get_name() if access_request.access_records.exists() and access_request.access_records.first().access_object else _('No Object'),
            'environment': access_request.get_environment_display(),
            'requested_for': access_request.requested_for.get_full_name() or access_request.requested_for.username,
            'requested_by': access_request.requested_by.get_full_name() or access_request.requested_by.username,
            'justification': access_request.justification,
            'requirements': access_request.requirements,
            'notes': access_request.notes,
            'start_date': access_request.start_date,
            'end_date': access_request.end_date,
            'roles': access_request.access_records.first().roles.all() if access_request.access_records.exists() else [],
            'request_type': access_request.get_request_type_display(),
            'site_domain': SiteSettings.get_settings().site_domain,
            'site_protocol': SiteSettings.get_settings().site_protocol,
            'status_type': status_type,
            # Дані третьої сторони (підтримка множинних користувачів)
            'has_third_party': has_third_party,
            'third_party_name': third_party_name,
            'third_party_users': third_party_users,
            'third_party_count': len(third_party_users) if third_party_users else 0,
            # Зберігаємо старі поля для зворотної сумісності
            'third_party_first_name': access_request.third_party_first_name,
            'third_party_last_name': access_request.third_party_last_name,
            'third_party_email': access_request.third_party_email,
            'third_party_phone': access_request.third_party_phone,
            'third_party_organization': access_request.third_party_organization,
            'third_party_description': access_request.third_party_description,
            'include_third_party_info': config.include_third_party_info_in_emails if config else True,
        }
        
        subject, _, _ = render_notification_email_content(
            config, 'status_changed', context, status_type=status_type
        )

        # Створюємо запис в історії email повідомлень
        recipients_emails = [r['email'] for r in recipients]
        notification_history = EmailNotificationHistory.create_notification(
            notification_type=notification_type,
            subject=subject,
            recipients=recipients_emails,
            access_request=access_request,
            triggered_by=changed_by,
            mail_account=mail_account,
            template_data={
                'config_name': config.name,
                'old_status': old_status,
                'new_status': new_status,
                'status_type': status_type,
                'use_custom_templates': config.use_custom_templates
            }
        )
        
        # Відправка email кожному отримувачу
        success_count = 0
        for recipient in recipients:
            try:
                # Додаємо інформацію про отримувача до контексту
                context['recipient_name'] = recipient['name']
                context['recipient_role'] = recipient['role']
                
                subject, html_content, text_content = render_notification_email_content(
                    config, 'status_changed', context, status_type=status_type
                )

                # Use smtplib directly instead of Django's email backend
                if send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, [recipient['email']]):
                    success_count += 1
                else:
                    logger.error(f"Failed to send status change notification to {recipient['email']}")
                    continue
                
                logger.info(f"Status change notification sent to {recipient['email']} for request {access_request.id} using config '{config.name}'")
                
            except Exception as e:
                logger.error(f"Failed to send status change notification to {recipient['email']}: {e}")
                continue
        
        logger.info(f"Successfully sent {success_count}/{len(recipients)} status change notifications for access request {access_request.id} using config '{config.name}'")
        
        # Оновлюємо статус в історії
        if notification_history:
            if success_count > 0:
                notification_history.mark_as_sent()
            else:
                notification_history.mark_as_failed(f"Failed to send to all {len(recipients)} recipients")
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error sending status change notifications: {e}")
        
        # Відмічаємо помилку в історії
        if notification_history:
            notification_history.mark_as_failed(str(e))
        
        return False 

def send_access_status_change_notification(access, old_status, new_status, changed_by, comment=''):
    """
    Відправка email повідомлення про зміну статуса доступу (SystemAccess)
    
    Args:
        access: екземпляр SystemAccess
        old_status: старий статус ('active' або 'inactive')
        new_status: новий статус ('active' або 'inactive')
        changed_by: користувач, який змінив статус
        comment: коментар до зміни статусу
    """
    # Імпортуємо тут щоб уникнути циклічного імпорту
    from .models import EmailNotificationHistory, EmailNotificationConfig
    from django.template import Template, Context
    from django.template.loader import render_to_string
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings
    from django.utils.translation import gettext as _
    import logging
    
    logger = logging.getLogger(__name__)
    notification_history = None
    
    try:
        # Створюємо псевдо-запит для отримання конфігурації
        # Оскільки SystemAccess не пов'язаний безпосередньо з AccessRequest,
        # створюємо мок-об'єкт з необхідними полями
        class MockAccessRequest:
            def __init__(self, access):
                self.company = access.asset.company
                self.system = access.asset
                self.access_record = access
                
        mock_request = MockAccessRequest(access)
        
        # Отримуємо активну конфігурацію
        config = EmailNotificationConfig.get_active_config_for_request(mock_request)
        
        if not config:
            logger.info(f"No active email configuration found for access record {access.id}")
            return False
        
        # Перевіряємо, чи увімкнені сповіщення про зміну статуса
        if not config.send_on_status_changed:
            logger.info(f"Status change notifications are disabled in configuration '{config.name}'")
            return False
        
        # Визначаємо mail account та server
        mail_account = config.mail_account or get_default_mail_account()
        if not mail_account:
            logger.warning("No mail account configured for sending notifications")
            return False
        
        # Визначаємо mail server
        mail_server = config.mail_server or mail_account.server
        if not mail_server:
            logger.warning("No mail server configured for sending notifications")
            return False
        
        # Отримуємо список отримувачів
        recipients = []
        
        # Власники системи
        if config.notify_owners:
            for owner in access.asset.owners.all():
                if owner.cabinet_user.user.email:
                    recipients.append({
                        'email': owner.cabinet_user.user.email,
                        'name': owner.cabinet_user.user.get_full_name() or owner.cabinet_user.user.username,
                        'role': 'Owner'
                    })
        
        # Адміністратори системи
        if config.notify_administrators:
            for admin in access.asset.administrators.all():
                if admin.cabinet_user.user.email:
                    recipients.append({
                        'email': admin.cabinet_user.user.email,
                        'name': admin.cabinet_user.user.get_full_name() or admin.cabinet_user.user.username,
                        'role': 'Administrator'
                    })
        
        # Користувачі, що мають доступ
        for user in access.access_users.all():
            if user.email:
                recipients.append({
                    'email': user.email,
                    'name': user.get_full_name() or user.username,
                    'role': 'Access User'
                })
        
        # Додаткові отримувачі
        for email in config.get_additional_recipients_list():
            recipients.append({
                'email': email,
                'name': email,
                'role': 'Additional Recipient'
            })
        
        # Видаляємо дублікати
        unique_recipients = []
        seen_emails = set()
        for recipient in recipients:
            if recipient['email'] not in seen_emails:
                unique_recipients.append(recipient)
                seen_emails.add(recipient['email'])
        
        recipients = unique_recipients
        
        if not recipients:
            logger.warning(f"No recipients found for access status change notification for access record {access.id}")
            return False
        
        # Підготовка контексту для шаблону
        status_display = {
            'active': _('Active'),
            'inactive': _('Inactive')
        }
        
        context = {
            'access': access,
            'old_status': old_status,
            'new_status': new_status,
            'old_status_display': status_display.get(old_status, old_status),
            'new_status_display': status_display.get(new_status, new_status),
            'changed_by': changed_by.get_full_name() or changed_by.username,
            'comment': comment,
            'company_name': access.asset.company.name,
            'system_name': access.asset.name,
            'object_name': access.access_object.get_name() if access.access_object else _('No Object'),
            'environment': access.get_environment_display(),
            'access_users': [user.get_full_name() or user.username for user in access.access_users.all()],
            'roles': access.roles.all(),
            'site_domain': SiteSettings.get_settings().site_domain,
            'site_protocol': SiteSettings.get_settings().site_protocol,
        }
        
        # Формуємо тему листа
        if config.use_custom_templates and config.status_changed_subject_template:
            subject_template = Template(config.status_changed_subject_template)
            subject = subject_template.render(Context(context))
        else:
            subject = _('Access Status Changed - {company_name} / {system_name}').format(**context)
        
        # Створюємо запис в історії email повідомлень
        recipients_emails = [r['email'] for r in recipients]
        notification_history = EmailNotificationHistory.create_notification(
            notification_type='access_status_changed',
            subject=subject,
            recipients=recipients_emails,
            triggered_by=changed_by,
            mail_account=mail_account,
            template_data={
                'config_name': config.name,
                'old_status': old_status,
                'new_status': new_status,
                'access_id': access.id,
                'use_custom_templates': config.use_custom_templates
            }
        )
        
        # Відправка email кожному отримувачу
        success_count = 0
        for recipient in recipients:
            try:
                # Додаємо інформацію про отримувача до контексту
                context['recipient_name'] = recipient['name']
                context['recipient_role'] = recipient['role']
                
                # Формуємо контент
                if config.use_custom_templates and config.status_changed_html_template:
                    html_template = Template(config.status_changed_html_template)
                    html_content = html_template.render(Context(context))
                else:
                    # Використовуємо простий HTML шаблон
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <title>Access Status Changed</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; }}
                            .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
                            .content {{ padding: 20px; }}
                            .info {{ background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 10px 0; }}
                        </style>
                    </head>
                    <body>
                        <div class="header">
                            <h2>Access Status Changed</h2>
                        </div>
                        <div class="content">
                            <p>Dear {context['recipient_name']},</p>
                            <p>The access status has been changed for the following record:</p>
                            
                            <div class="info">
                                <strong>Company:</strong> {context['company_name']}<br>
                                <strong>System:</strong> {context['system_name']}<br>
                                <strong>Object:</strong> {context['object_name']}<br>
                                <strong>Environment:</strong> {context['environment']}<br>
                                <strong>Status Change:</strong> {context['old_status_display']} → {context['new_status_display']}<br>
                                <strong>Changed By:</strong> {context['changed_by']}
                                {f"<br><strong>Comment:</strong> {context['comment']}" if context['comment'] else ""}
                            </div>
                            
                            <p>Best regards,<br>SecBoard Access Management System</p>
                        </div>
                    </body>
                    </html>
                    """
                
                if config.use_custom_templates and config.status_changed_text_template:
                    text_template = Template(config.status_changed_text_template)
                    text_content = text_template.render(Context(context))
                else:
                    text_content = f"""
Access Status Changed

Dear {context['recipient_name']},

The access status has been changed for the following record:

Company: {context['company_name']}
System: {context['system_name']}
Object: {context['object_name']}
Environment: {context['environment']}
Status Change: {context['old_status_display']} → {context['new_status_display']}
Changed By: {context['changed_by']}
{f"Comment: {context['comment']}" if context['comment'] else ""}

Best regards,
SecBoard Access Management System
                    """
                
                # Use smtplib directly instead of Django's email backend
                if send_email_via_smtplib(mail_server, mail_account, subject, text_content, html_content, [recipient['email']]):
                    success_count += 1
                else:
                    logger.error(f"Failed to send access status change notification to {recipient['email']}")
                    continue
                
                logger.info(f"Access status change notification sent to {recipient['email']} for access record {access.id}")
                
            except Exception as e:
                logger.error(f"Failed to send access status change notification to {recipient['email']}: {e}")
                continue
        
        logger.info(f"Successfully sent {success_count}/{len(recipients)} access status change notifications for access record {access.id}")
        
        # Оновлюємо статус в історії
        if notification_history:
            if success_count > 0:
                notification_history.mark_as_sent()
            else:
                notification_history.mark_as_failed(f"Failed to send to all {len(recipients)} recipients")
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error sending access status change notifications: {e}")
        
        # Відмічаємо помилку в історії
        if notification_history:
            notification_history.mark_as_failed(str(e))
        
        return False 