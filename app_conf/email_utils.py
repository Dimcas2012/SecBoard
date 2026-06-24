#  SecBoard\SecBoard\app_conf\email_utils.py
from django.core.mail import get_connection, EmailMessage
import logging


logger = logging.getLogger(__name__)



def send_test_email(account):
    subject = "Test email"
    message = "This is a test email sent"
    from_email = account.username
    recipient_list = [account.username]  # Sending to self for testing

    try:
        connection = get_connection(
            host=account.server.smtp_host,
            port=account.server.smtp_port,
            username=account.username,
            password=account.password,
            use_tls=account.server.use_tls,
            use_ssl=account.server.use_ssl
        )

        email = EmailMessage(
            subject,
            message,
            from_email,
            recipient_list,
            connection=connection,
        )

        email.send()
        return True, "Test email sent successfully!"
    except Exception as e:
        return False, str(e)


