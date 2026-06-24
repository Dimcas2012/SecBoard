# Email utilities for Mandatory Process reminders
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.template.loader import render_to_string
from django.template import Template, Context
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils import timezone
from app_conf.models import MailAccount, MailServer, SiteSettings
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def get_default_mail_account():
    """Get default mail account for sending emails"""
    try:
        # First try to find an active account
        mail_account = MailAccount.objects.filter(is_active=True).first()
        if not mail_account:
            # If no active account, take any
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

def send_mandatory_process_reminder(process, recipients, subject, message, include_process_details=True, sent_by=None):
    """
    Send reminder email for mandatory process
    
    Args:
        process: MandatoryProcess instance
        recipients: List of recipient dictionaries with 'name', 'email', 'role'
        subject: Email subject
        message: Email message content
        include_process_details: Whether to include process details in email
        sent_by: User who sent the reminder
    
    Returns:
        int: Number of successfully sent emails
    """
    try:
        # Get mail account and server
        mail_account = get_default_mail_account()
        if not mail_account:
            logger.warning("No mail account configured for sending reminders")
            return 0
        
        mail_server = mail_account.server
        if not mail_server:
            logger.warning("No mail server configured for sending reminders")
            return 0
        
        # Prepare context for email templates
        context = {
            'process': process,
            'subject': subject,
            'message': message,
            'include_process_details': include_process_details,
            'sent_by': sent_by,
            'sent_by_name': sent_by.get_full_name() or sent_by.username if sent_by else _('System'),
            'site_domain': SiteSettings.get_settings().site_domain,
            'site_protocol': SiteSettings.get_settings().site_protocol,
            'current_date': timezone.now().date(),
        }
        
        # Generate HTML content
        if include_process_details:
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>""" + subject + """</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .header { background-color: #007bff; color: white; padding: 20px; text-align: center; }
                    .content { padding: 20px; }
                    .process-details { background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 15px 0; }
                    .footer { background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 0.9em; color: #666; }
                    .urgent { color: #dc3545; font-weight: bold; }
                    .warning { color: #ffc107; font-weight: bold; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>🔔 """ + _('Mandatory Process Reminder') + """</h2>
                </div>
                <div class="content">
                    <p>""" + _('Dear') + """ {recipient_name},</p>
                    
                    <p>""" + message + """</p>
                    
                    <div class="process-details">
                        <h3>📋 """ + _('Process Details') + """</h3>
                        <p><strong>""" + _('Process Name') + """:</strong> """ + process.process_name + """</p>
                        <p><strong>""" + _('Company') + """:</strong> """ + (process.company.name if process.company else _('N/A')) + """</p>
                        <p><strong>""" + _('Due Date') + """:</strong> """ + str(process.next_due_date) + """</p>
                        <p><strong>""" + _('Frequency') + """:</strong> """ + process.get_frequency_display() + """</p>
                        <p><strong>""" + _('Priority') + """:</strong> """ + process.get_priority_display() + """</p>
                        <p><strong>""" + _('Status') + """:</strong> """ + process.get_status_display() + """</p>
                        <p><strong>""" + _('Description') + """:</strong> """ + process.description + """</p>
                    </div>
                    
                    <p>""" + _('Please ensure this process is completed on time.') + """</p>
                    
                    <p>""" + _('Best regards') + """,<br>""" + context['sent_by_name'] + """</p>
                </div>
                <div class="footer">
                    <p>""" + _('This is an automated reminder from SecBoard Mandatory Processes Registry') + """</p>
                    <p>""" + _('Generated on') + """ """ + str(context['current_date']) + """</p>
                </div>
            </body>
            </html>
            """
        else:
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>""" + subject + """</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .header { background-color: #007bff; color: white; padding: 20px; text-align: center; }
                    .content { padding: 20px; }
                    .footer { background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 0.9em; color: #666; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>🔔 """ + _('Mandatory Process Reminder') + """</h2>
                </div>
                <div class="content">
                    <p>""" + _('Dear') + """ {recipient_name},</p>
                    
                    <p>""" + message + """</p>
                    
                    <p>""" + _('Best regards') + """,<br>""" + context['sent_by_name'] + """</p>
                </div>
                <div class="footer">
                    <p>""" + _('This is an automated reminder from SecBoard Mandatory Processes Registry') + """</p>
                    <p>""" + _('Generated on') + """ """ + str(context['current_date']) + """</p>
                </div>
            </body>
            </html>
            """
        
        # Generate text content
        if include_process_details:
            text_content = """
""" + _('Mandatory Process Reminder') + """

""" + _('Dear') + """ {recipient_name},

""" + message + """

""" + _('Process Details') + """:
""" + _('Process Name') + """: """ + process.process_name + """
""" + _('Company') + """: """ + (process.company.name if process.company else _('N/A')) + """
""" + _('Due Date') + """: """ + str(process.next_due_date) + """
""" + _('Frequency') + """: """ + process.get_frequency_display() + """
""" + _('Priority') + """: """ + process.get_priority_display() + """
""" + _('Status') + """: """ + process.get_status_display() + """
""" + _('Description') + """: """ + process.description + """

""" + _('Please ensure this process is completed on time.') + """

""" + _('Best regards') + """,
""" + context['sent_by_name'] + """

---
""" + _('This is an automated reminder from SecBoard Mandatory Processes Registry') + """
""" + _('Generated on') + """ """ + str(context['current_date']) + """
            """
        else:
            text_content = """
""" + _('Mandatory Process Reminder') + """

""" + _('Dear') + """ {recipient_name},

""" + message + """

""" + _('Best regards') + """,
""" + context['sent_by_name'] + """

---
""" + _('This is an automated reminder from SecBoard Mandatory Processes Registry') + """
""" + _('Generated on') + """ """ + str(context['current_date']) + """
            """
        
        # Send email to each recipient
        success_count = 0
        for recipient in recipients:
            try:
                # Replace {recipient_name} with actual recipient name
                recipient_html = html_content.replace('{recipient_name}', recipient['name'])
                recipient_text = text_content.replace('{recipient_name}', recipient['name'])
                
                # Send email
                if send_email_via_smtplib(mail_server, mail_account, subject, recipient_text, recipient_html, [recipient['email']]):
                    success_count += 1
                    logger.info(f"Process reminder sent to {recipient['email']} for process {process.id}")
                else:
                    logger.error(f"Failed to send process reminder to {recipient['email']}")
                    
            except Exception as e:
                logger.error(f"Failed to send process reminder to {recipient['email']}: {e}")
                continue
        
        logger.info(f"Successfully sent {success_count}/{len(recipients)} process reminders for process {process.id}")
        return success_count
        
    except Exception as e:
        logger.error(f"Error sending process reminders: {e}")
        return 0
