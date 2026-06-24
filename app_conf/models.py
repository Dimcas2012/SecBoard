#  SecBoard\SecBoard\app_conf\models.py
from django.contrib.auth.models import Group
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.translation import gettext as _
from django.utils import timezone
from django.core.mail import send_mail, get_connection
import ssl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from encrypted_model_fields.fields import EncryptedCharField
from tinymce.models import HTMLField



class CustomGroup(Group):
    description_group = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Custom Group'
        verbose_name_plural = 'Custom Groups'



class MailServer(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    smtp_host = models.CharField(
        max_length=255, verbose_name=_("SMTP host"))
    smtp_port = models.IntegerField(verbose_name=_("SMTP port"))
    use_tls = models.BooleanField(
        default=True, verbose_name=_("Use TLS"))
    use_ssl = models.BooleanField(
        default=False, verbose_name=_("Use SSL"))

    # New fields for IMAP
    imap_host = models.CharField(
        max_length=255, blank=True, verbose_name=_("IMAP host"))
    imap_port = models.IntegerField(
        null=True, blank=True, verbose_name=_("IMAP port"))
    imap_use_ssl = models.BooleanField(
        default=True, verbose_name=_("IMAP use SSL"))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Mail Server")
        verbose_name_plural = _("Mail Servers")


def get_default_user():
    try:
        return User.objects.filter(is_superuser=True).first().id
    except:
        return None


class MailAccount(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='mail_accounts',
        default=get_default_user,
        null=True,
        verbose_name=_("User")
    )
    server = models.ForeignKey(
        MailServer, on_delete=models.CASCADE, related_name='accounts', verbose_name=_("Server"))
    username = models.CharField(
        max_length=255, verbose_name=_("Username"))
    password = EncryptedCharField(
        max_length=255, verbose_name=_("Password"))
    is_active = models.BooleanField(
        default=True, verbose_name=_("Active"))
    show_password = models.BooleanField(
        default=False, verbose_name=_("Show password"))

    def __str__(self):
        return f"{self.username} on {self.server.name}"

    def get_connection(self):
        connection_kwargs = {
            'host': self.server.smtp_host,
            'port': self.server.smtp_port,
            'username': self.username,
            'password': self.password,
        }
        
        # Correctly handle SSL/TLS settings - only set one to True, not both
        if self.server.use_ssl:
            connection_kwargs['use_ssl'] = True
        elif self.server.use_tls:
            connection_kwargs['use_tls'] = True
        
        return get_connection(**connection_kwargs)

    def get_masked_password(self):
        return self.password if self.show_password else '*' * 8

    def set_password(self, raw_password):
        self.password = raw_password  # In production, use proper encryption here

    def send_test_email(self, recipient):
        subject = _("Test email")
        body = _(f"This is a test email from {self.username}")
        from_email = self.username
        to_email = recipient
        
        try:
            # Create the email message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to the server directly using smtplib
            if self.server.use_ssl:
                # Create SSL context without keyfile issues
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                
                # Connect with SSL but avoid Django's connection wrapper
                smtp = smtplib.SMTP_SSL(
                    host=self.server.smtp_host,
                    port=self.server.smtp_port,
                    context=context
                )
            else:
                # Connect without SSL
                smtp = smtplib.SMTP(
                    host=self.server.smtp_host,
                    port=self.server.smtp_port
                )
                
                # Use TLS if needed
                if self.server.use_tls:
                    smtp.starttls()
            
            # Login and send
            smtp.login(self.username, self.password)
            smtp.send_message(msg)
            smtp.quit()
            
            return True, _("Test email sent successfully!")
        except smtplib.SMTPAuthenticationError as e:
            if "534" in str(e) and "5.7.9" in str(e):
                return False, _("Authentication error. Make sure you're using an app password if you have two-factor authentication enabled.")
            return False, f"{_('Authentication failed')}: {str(e)}"
        except Exception as e:
            return False, f"{_('Failed to send test email')}: {str(e)}"

    class Meta:
        verbose_name = _("Mail Account")
        verbose_name_plural = _("Mail Accounts")


class Email(models.Model):
    EMAIL_TYPE_CHOICES = [
        ('incoming', _('Incoming')),
        ('outgoing', _('Outgoing')),
    ]
    account = models.ForeignKey(
        MailAccount, on_delete=models.CASCADE, related_name='emails', verbose_name=_("Account"))
    message_id = models.CharField(
        max_length=255, unique=True, verbose_name=_("Message ID"))
    from_name = models.CharField(
        max_length=255, blank=True, verbose_name=_("From Name"))
    from_email = models.EmailField(
        default='unknown@example.com', verbose_name=_("From"))
    to_email = models.EmailField(
        blank=True, verbose_name=_("To"))  # New field for recipient address
    subject = models.CharField(
        max_length=255, verbose_name=_("Subject"))
    body = models.TextField(verbose_name=_("Body"))
    date = models.DateTimeField(null=True, blank=True, verbose_name=_("Date"))
    is_read = models.BooleanField(default=False, verbose_name=_("Read"))
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Created"))
    email_type = models.CharField(
        max_length=10, choices=EMAIL_TYPE_CHOICES, default='incoming', verbose_name=_("Type"))

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Email")
        verbose_name_plural = _("Emails")

    def __str__(self):
        return f"{self.subject} - {self.from_email}"


class Company(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    group = models.OneToOneField(
        Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='company', verbose_name=_("Group"))
    company_types = models.ManyToManyField(
        'CompanyType',
        blank=True,
        related_name='companies',
        verbose_name=_("Company Types"),
        help_text=_("Select one or more company types")
    )
    countries = models.ManyToManyField(
        'Country',
        blank=True,
        related_name='companies',
        verbose_name=_("Countries"),
        help_text=_("Countries where this company operates")
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Company")
        verbose_name_plural = _("Companies")

    def save(self, *args, **kwargs):
        # If no group is set, create a new group with the company name
        if not self.group:
            self.group, created = Group.objects.get_or_create(name=self.name)
        super().save(*args, **kwargs)


class Country(models.Model):
    """
    Country reference for use across the system
    """
    name = models.CharField(
        _("Country Name"),
        max_length=100,
        help_text=_("Full country name (e.g., Ukraine)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Country name in local language (e.g., Україна)")
    )
    code = models.CharField(
        _("Country Code"),
        max_length=2,
        unique=True,
        help_text=_("ISO 3166-1 alpha-2 country code (e.g., UA)")
    )
    flag_emoji = models.CharField(
        _("Flag Emoji"),
        max_length=10,
        blank=True,
        help_text=_("Flag emoji (e.g., 🇺🇦)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#007bff',
        help_text=_("Hex color code for display (e.g., #007bff)")
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        if self.flag_emoji:
            return f"{self.flag_emoji} {self.name} ({self.code})"
        return f"{self.name} ({self.code})"


class CompanyType(models.Model):
    """
    Company Type (Bank, Credit Bureau, Payment System, etc.)
    """
    name = models.CharField(
        _("Type Name"),
        max_length=100,
        help_text=_("Company type name (e.g., Bank, Payment System)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Type name in local language (e.g., Банк, Платіжна система)")
    )
    code = models.CharField(
        _("Type Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., bank, payment_system)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#007bff',
        help_text=_("Hex color code for display (e.g., #007bff)")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description of this company type")
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Company Type")
        verbose_name_plural = _("Company Types")
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name

    def get_local_name(self, country=None):
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except CompanyTypeTranslation.DoesNotExist:
                pass
        return self.name_local or self.name


class CompanyTypeTranslation(models.Model):
    """Localized names for company types per country."""

    company_type = models.ForeignKey(
        CompanyType,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Company Type")
    )

    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='company_type_translations',
        verbose_name=_("Country")
    )

    name_local = models.CharField(
        _("Country Local Name"),
        max_length=100,
        help_text=_("Company type name in the selected country's language")
    )

    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Optional description in the country's language")
    )

    class Meta:
        verbose_name = _("Company Type Translation")
        verbose_name_plural = _("Company Type Translations")
        unique_together = ['company_type', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.company_type.name} - {self.country.name}: {self.name_local}"


class LogEntry(models.Model):
    LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, verbose_name=_("Level"))
    logger_name = models.CharField(max_length=100, verbose_name=_("Logger"))
    message = models.TextField(verbose_name=_("Message"))
    trace = models.TextField(blank=True, null=True, verbose_name=_("Stack Trace"))
    request_path = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Request Path"))
    user = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("User"))

    class Meta:
        verbose_name = _("Log Entry")
        verbose_name_plural = _("Log Entries")
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.level}: {self.message[:100]}"

class ErrorLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))
    error_type = models.CharField(max_length=100, verbose_name=_("Error Type"))
    error_message = models.TextField(verbose_name=_("Error Message"))
    stack_trace = models.TextField(verbose_name=_("Stack Trace"))
    request_path = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Request Path"))
    request_method = models.CharField(max_length=10, blank=True, null=True, verbose_name=_("Request Method"))
    user = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("User"))
    resolved = models.BooleanField(default=False, verbose_name=_("Resolved"))

    class Meta:
        verbose_name = _("Error Log")
        verbose_name_plural = _("Error Logs")
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.error_type}: {self.error_message[:100]}"


class GoogleTagSettings(models.Model):
    """Model to store Google Analytics and Tag Manager settings"""
    
    # Google Analytics settings
    google_analytics_id = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        verbose_name=_("Google Analytics ID"),
        help_text=_("Example: G-XXXXXXXXXX or UA-XXXXXXXXX-X")
    )
    enable_google_analytics = models.BooleanField(
        default=False,
        verbose_name=_("Enable Google Analytics")
    )
    
    # Google Tag Manager settings
    google_tag_manager_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Google Tag Manager ID"),
        help_text=_("Example: GTM-XXXXXXX")
    )
    enable_google_tag_manager = models.BooleanField(
        default=False,
        verbose_name=_("Enable Google Tag Manager")
    )
    
    # Additional tracking settings
    facebook_pixel_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Facebook Pixel ID"),
        help_text=_("Example: 123456789012345")
    )
    enable_facebook_pixel = models.BooleanField(
        default=False,
        verbose_name=_("Enable Facebook Pixel")
    )
    
    # Custom tracking code
    custom_head_scripts = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Custom Head Scripts"),
        help_text=_("Custom tracking scripts to include in HTML head section")
    )
    custom_body_scripts = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Custom Body Scripts"),
        help_text=_("Custom tracking scripts to include at the end of body section")
    )
    
    # Settings metadata
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated")
    )
    
    class Meta:
        verbose_name = _("Google Tag Settings")
        verbose_name_plural = _("Google Tag Settings")
    
    def __str__(self):
        return f"Google Tag Settings (Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        if not self.pk and GoogleTagSettings.objects.exists():
            # Update existing instance instead of creating new one
            existing = GoogleTagSettings.objects.first()
            existing.google_analytics_id = self.google_analytics_id
            existing.enable_google_analytics = self.enable_google_analytics
            existing.google_tag_manager_id = self.google_tag_manager_id
            existing.enable_google_tag_manager = self.enable_google_tag_manager
            existing.facebook_pixel_id = self.facebook_pixel_id
            existing.enable_facebook_pixel = self.enable_facebook_pixel
            existing.custom_head_scripts = self.custom_head_scripts
            existing.custom_body_scripts = self.custom_body_scripts
            existing.is_active = self.is_active
            existing.save()
            return existing
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance"""
        settings, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'is_active': True
            }
        )
        return settings


class CelerySettings(models.Model):
    """Model to store Celery worker and beat configuration"""
    
    # Celery Worker settings
    enable_worker = models.BooleanField(
        default=True,
        verbose_name=_("Enable Celery Worker"),
        help_text=_("Start Celery worker automatically with runserver")
    )
    worker_concurrency = models.IntegerField(
        default=4,
        verbose_name=_("Worker Concurrency"),
        help_text=_("Number of concurrent worker processes")
    )
    worker_loglevel = models.CharField(
        max_length=20,
        choices=[
            ('DEBUG', 'DEBUG'),
            ('INFO', 'INFO'),
            ('WARNING', 'WARNING'),
            ('ERROR', 'ERROR'),
            ('CRITICAL', 'CRITICAL'),
        ],
        default='INFO',
        verbose_name=_("Worker Log Level")
    )
    
    # Celery Beat settings
    enable_beat = models.BooleanField(
        default=True,
        verbose_name=_("Enable Celery Beat"),
        help_text=_("Start Celery beat scheduler automatically with runserver")
    )
    beat_loglevel = models.CharField(
        max_length=20,
        choices=[
            ('DEBUG', 'DEBUG'),
            ('INFO', 'INFO'),
            ('WARNING', 'WARNING'),
            ('ERROR', 'ERROR'),
            ('CRITICAL', 'CRITICAL'),
        ],
        default='INFO',
        verbose_name=_("Beat Log Level")
    )
    
    # Redis settings
    redis_host = models.CharField(
        max_length=255,
        default='localhost',
        verbose_name=_("Redis Host"),
        help_text=_("Redis server hostname or IP address")
    )
    redis_port = models.IntegerField(
        default=6379,
        verbose_name=_("Redis Port"),
        help_text=_("Redis server port")
    )
    redis_db = models.IntegerField(
        default=0,
        verbose_name=_("Redis Database"),
        help_text=_("Redis database number")
    )
    redis_password = EncryptedCharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Redis Password"),
        help_text=_("Redis authentication password (if required)")
    )
    
    # Auto-start settings
    auto_start_with_runserver = models.BooleanField(
        default=True,
        verbose_name=_("Auto-start with runserver"),
        help_text=_("Automatically start Celery worker and beat when Django development server starts")
    )
    
    # Platform-specific settings
    use_windows_commands = models.BooleanField(
        default=False,
        verbose_name=_("Use Windows Commands"),
        help_text=_("Use Windows-specific commands for starting Celery processes")
    )
    
    # Custom commands
    custom_worker_command = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Custom Worker Command"),
        help_text=_("Custom command to start Celery worker (overrides default)")
    )
    custom_beat_command = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Custom Beat Command"),
        help_text=_("Custom command to start Celery beat (overrides default)")
    )
    
    # Process management
    kill_existing_processes = models.BooleanField(
        default=True,
        verbose_name=_("Kill Existing Processes"),
        help_text=_("Kill existing Celery processes before starting new ones")
    )
    
    # Settings metadata
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated")
    )
    
    class Meta:
        verbose_name = _("Celery Settings")
        verbose_name_plural = _("Celery Settings")
    
    def __str__(self):
        return f"Celery Settings (Worker: {'ON' if self.enable_worker else 'OFF'}, Beat: {'ON' if self.enable_beat else 'OFF'})"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        if not self.pk and CelerySettings.objects.exists():
            # Update existing instance instead of creating new one
            existing = CelerySettings.objects.first()
            for field in self._meta.fields:
                if field.name not in ['id', 'created_at']:
                    setattr(existing, field.name, getattr(self, field.name))
            existing.save()
            return existing
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance"""
        settings, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'enable_worker': True,
                'enable_beat': True,
                'auto_start_with_runserver': True,
                'is_active': True
            }
        )
        return settings
    
    def get_worker_command(self):
        """Get the command to start Celery worker"""
        if self.custom_worker_command:
            return self.custom_worker_command
        
        # Set environment variables for proper module discovery
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        secboard_dir = os.path.join(base_dir, 'SecBoard')
        
        if self.use_windows_commands:
            # Quoted set avoids trailing space before && being included in the value (cmd.exe quirk).
            env_vars = f'set "PYTHONPATH={secboard_dir}" && set "DJANGO_SETTINGS_MODULE=SecBoard.settings" && '
            return f"{env_vars}python -m celery -A SecBoard worker --loglevel={self.worker_loglevel.lower()} --concurrency={self.worker_concurrency} --pool=solo"
        else:
            env_vars = f'export PYTHONPATH={secboard_dir} && export DJANGO_SETTINGS_MODULE=SecBoard.settings && '
            return f"{env_vars}python -m celery -A SecBoard worker --loglevel={self.worker_loglevel.lower()} --concurrency={self.worker_concurrency}"
    
    def get_beat_command(self):
        """Get the command to start Celery beat"""
        if self.custom_beat_command:
            return self.custom_beat_command
        
        # Set environment variables for proper module discovery
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        secboard_dir = os.path.join(base_dir, 'SecBoard')
        
        if self.use_windows_commands:
            env_vars = f'set "PYTHONPATH={secboard_dir}" && set "DJANGO_SETTINGS_MODULE=SecBoard.settings" && '
            return f"{env_vars}python -m celery -A SecBoard beat --loglevel={self.beat_loglevel.lower()}"
        else:
            env_vars = f'export PYTHONPATH={secboard_dir} && export DJANGO_SETTINGS_MODULE=SecBoard.settings && '
            return f"{env_vars}python -m celery -A SecBoard beat --loglevel={self.beat_loglevel.lower()}"
    
    def get_redis_url(self):
        """Get Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


class SiteSettings(models.Model):
    """Model to store site-wide settings"""
    
    # Project type settings
    PROJECT_TYPE_CHOICES = [
        ('prod', _('Production')),
        ('test', _('Test')),
        ('demo', _('Demo')),
    ]
    
    project_type = models.CharField(
        max_length=10,
        choices=PROJECT_TYPE_CHOICES,
        default='prod',
        verbose_name=_("Project Type"),
        help_text=_("Type of project environment (affects navbar color and site name)")
    )
    demo_login = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("DEMO Login"),
        help_text=_("Login (email) to display on the login page for copying when Project Type is DEMO.")
    )
    demo_password = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("DEMO Password"),
        help_text=_("Password to display on the login page for copying when Project Type is DEMO.")
    )
    
    # Site domain and protocol settings
    site_domain = models.CharField(
        max_length=255,
        default='secboard.online',
        verbose_name=_("Site Domain"),
        help_text=_("Domain name for the site (e.g., secboard.online)")
    )
    site_protocol = models.CharField(
        max_length=10,
        choices=[
            ('http', 'HTTP'),
            ('https', 'HTTPS'),
        ],
        default='https',
        verbose_name=_("Site Protocol"),
        help_text=_("Protocol to use for site URLs")
    )
    
    # Email settings
    default_from_email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_("Default From Email"),
        help_text=_("Default email address for sending notifications")
    )
    
    # Site metadata
    site_name = models.CharField(
        max_length=100,
        default='SecBoard',
        verbose_name=_("Site Name"),
        help_text=_("Name of the site")
    )
    site_description = models.TextField(
        blank=True,
        verbose_name=_("Site Description"),
        help_text=_("Brief description of the site")
    )
    show_about_page = models.BooleanField(
        default=True,
        verbose_name=_("Show About Page"),
        help_text=_("Display the public about page at /about/")
    )
    show_knowledge_base = models.BooleanField(
        default=True,
        verbose_name=_("Show Knowledge Base"),
        help_text=_("Display the public knowledge base at /about/knowledge-base/")
    )
    show_faq_page = models.BooleanField(
        default=True,
        verbose_name=_("Show FAQ Page"),
        help_text=_("Display the public FAQ page at /about/faq/")
    )
    show_partnership_page = models.BooleanField(
        default=True,
        verbose_name=_("Show Partnership Page"),
        help_text=_("Display the public partnership page at /about/partnership/")
    )
    show_contact_page = models.BooleanField(
        default=True,
        verbose_name=_("Show Contact Page"),
        help_text=_("Display the public contact page at /about/contact/")
    )
    
    # Settings metadata
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated")
    )
    
    class Meta:
        verbose_name = _("Site Settings")
        verbose_name_plural = _("Site Settings")
    
    def __str__(self):
        return f"{self.site_name} Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton pattern)
        if not self.pk and SiteSettings.objects.exists():
            return
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get the active site settings, creating default if none exists"""
        settings, created = cls.objects.get_or_create(
            defaults={
                'site_domain': 'secboard.online',
                'site_protocol': 'https',
                'site_name': 'SecBoard',
            }
        )
        return settings
    
    def get_site_url(self):
        """Get the full site URL"""
        return f"{self.site_protocol}://{self.site_domain}"
    
    def get_project_display_name(self):
        """Get the display name with project type suffix"""
        if self.project_type == 'demo':
            return f"{self.site_name} DEMO"
        elif self.project_type == 'test':
            return f"{self.site_name} TEST"
        else:
            return self.site_name
    
    def get_navbar_color(self):
        """Get navbar background color based on project type"""
        if self.project_type == 'demo':
            return '#28a745'  # Green for Demo
        elif self.project_type == 'test':
            return '#dc3545'  # Red for Test
        else:
            return '#2c3e50'  # Default dark blue for Production




class AccessOption(models.Model):
    """Model to manage access options for groups"""
    
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE, 
        verbose_name=_("Group")
    )
    has_access = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Option")
    )
    description = models.TextField(
        blank=True, 
        verbose_name=_("Description")
    )
    
    class Meta:
        verbose_name = _("Access Option")
        verbose_name_plural = _("Access Options")
    
    def __str__(self):
        return f"{self.group.name} - {'Has Access' if self.has_access else 'No Access'}"
    
    @classmethod
    def user_has_options_access(cls, user):
        """Check if user has access to options through their groups"""
        if not user.is_authenticated:
            return False
        
        # Check if any of user's groups have options access
        return cls.objects.filter(
            group__in=user.groups.all(),
            has_access=True
        ).exists()


class ContactMessage(models.Model):
    """Model to store contact form submissions"""
    
    SUBJECT_CHOICES = [
        ('general', _('General Inquiry')),
        ('support', _('Technical Support')),
        ('sales', _('Sales & Demo Request')),
        ('partnership', _('Partnership Opportunities')),
        ('security', _('Security Issue Report')),
        ('feedback', _('Feedback & Suggestions')),
        ('other', _('Other')),
    ]
    
    STATUS_CHOICES = [
        ('new', _('New')),
        ('in_progress', _('In Progress')),
        ('responded', _('Responded')),
        ('closed', _('Closed')),
    ]
    
    # Contact information
    name = models.CharField(
        max_length=200,
        verbose_name=_("Name")
    )
    email = models.EmailField(
        verbose_name=_("Email")
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Phone")
    )
    company = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Company/Organization")
    )
    
    # Message details
    subject_type = models.CharField(
        max_length=50,
        choices=SUBJECT_CHOICES,
        default='general',
        verbose_name=_("Subject Type")
    )
    subject = models.CharField(
        max_length=300,
        verbose_name=_("Subject")
    )
    message = models.TextField(
        verbose_name=_("Message")
    )
    
    # Metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        verbose_name=_("Status")
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("IP Address")
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("User Agent")
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_("Read")
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_contact_messages',
        verbose_name=_("Assigned To")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Submitted At")
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Responded At")
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Closed At")
    )
    
    class Meta:
        verbose_name = _("Contact Message")
        verbose_name_plural = _("Contact Messages")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.subject} ({self.created_at.strftime('%Y-%m-%d')})"
    
    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
    
    def mark_as_responded(self):
        """Mark message as responded"""
        if self.status == 'new':
            self.status = 'responded'
            self.responded_at = timezone.now()
            self.save(update_fields=['status', 'responded_at'])
    
    def close(self):
        """Close the message"""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save(update_fields=['status', 'closed_at'])


class KnowledgeBaseCategory(models.Model):
    """Categories for Knowledge Base articles"""
    
    CATEGORY_TYPES = [
        ('threats', _('Security Threats')),
        ('protection', _('Protection Methods')),
        ('standards', _('Standards & Compliance')),
        ('best_practices', _('Best Practices')),
        ('tools', _('Security Tools')),
        ('incidents', _('Incident Response')),
        ('other', _('Other')),
    ]
    
    name = models.CharField(
        max_length=200,
        verbose_name=_("Category Name")
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        verbose_name=_("URL Slug")
    )
    category_type = models.CharField(
        max_length=50,
        choices=CATEGORY_TYPES,
        default='other',
        verbose_name=_("Category Type")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    icon = models.CharField(
        max_length=50,
        default='fa-book',
        verbose_name=_("Icon Class"),
        help_text=_("Font Awesome icon class (e.g., fa-shield-alt)")
    )
    color = models.CharField(
        max_length=20,
        default='primary',
        verbose_name=_("Color Theme"),
        help_text=_("Bootstrap color: primary, success, info, warning, danger, secondary")
    )
    order = models.IntegerField(
        default=0,
        verbose_name=_("Display Order")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated")
    )
    
    class Meta:
        verbose_name = _("Knowledge Base Category")
        verbose_name_plural = _("Knowledge Base Categories")
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_article_count(self):
        """Get number of published articles in this category"""
        return self.articles.filter(is_published=True).count()


class KnowledgeBaseArticle(models.Model):
    """Security Knowledge Base Articles"""
    
    ARTICLE_TYPES = [
        ('threat', _('Threat Description')),
        ('method', _('Protection Method')),
        ('standard', _('Standard Explanation')),
        ('guide', _('How-to Guide')),
        ('news', _('Security News')),
        ('case_study', _('Case Study')),
        ('other', _('Other')),
    ]
    
    PRIORITY_LEVELS = [
        ('critical', _('Critical')),
        ('high', _('High')),
        ('medium', _('Medium')),
        ('low', _('Low')),
        ('info', _('Informational')),
    ]
    
    # Basic information
    title = models.CharField(
        max_length=300,
        verbose_name=_("Title")
    )
    slug = models.SlugField(
        max_length=300,
        unique=True,
        verbose_name=_("URL Slug")
    )
    category = models.ForeignKey(
        KnowledgeBaseCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='articles',
        verbose_name=_("Category")
    )
    article_type = models.CharField(
        max_length=50,
        choices=ARTICLE_TYPES,
        default='other',
        verbose_name=_("Article Type")
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_LEVELS,
        default='info',
        verbose_name=_("Priority Level")
    )
    
    # Content
    summary = models.TextField(
        max_length=500,
        verbose_name=_("Summary"),
        help_text=_("Brief summary for list view (max 500 chars)")
    )
    content = HTMLField(
        verbose_name=_("Content"),
        help_text=_("Full article content with rich text formatting")
    )
    
    # Tags and keywords
    tags = models.CharField(
        max_length=300,
        blank=True,
        verbose_name=_("Tags"),
        help_text=_("Comma-separated tags for search and filtering")
    )
    
    # SEO
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name=_("Meta Description"),
        help_text=_("SEO meta description (max 160 chars)")
    )
    meta_keywords = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Meta Keywords"),
        help_text=_("SEO keywords, comma-separated")
    )
    
    # Author and publishing
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='kb_articles',
        verbose_name=_("Author")
    )
    is_published = models.BooleanField(
        default=False,
        verbose_name=_("Published"),
        help_text=_("Make article visible to users")
    )
    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("Featured"),
        help_text=_("Show on homepage/featured section")
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Published Date")
    )
    
    # Statistics
    views_count = models.IntegerField(
        default=0,
        verbose_name=_("Views Count")
    )
    
    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated")
    )
    
    class Meta:
        verbose_name = _("Knowledge Base Article")
        verbose_name_plural = _("Knowledge Base Articles")
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_published', '-published_at']),
            models.Index(fields=['category', 'is_published']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Auto-generate slug if not provided
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while KnowledgeBaseArticle.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        # Set published_at when first published
        if self.is_published and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def increment_views(self):
        """Increment article views count"""
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    def get_tags_list(self):
        """Get tags as list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []
    
    def get_related_articles(self, limit=5):
        """Get related articles based on category and tags"""
        related = KnowledgeBaseArticle.objects.filter(
            is_published=True
        ).exclude(
            id=self.id
        )
        
        # Prioritize same category
        if self.category:
            related = related.filter(category=self.category)
        
        return related.order_by('-views_count', '-published_at')[:limit]


class ContactSettings(models.Model):
    """Contact form settings and notification configuration"""
    
    # Email Settings
    support_email = models.EmailField(
        verbose_name=_("Support Email"),
        help_text=_("Email address for support inquiries"),
        blank=True,
        null=True
    )
    
    # Contact Notification Recipients (General)
    contact_notification_users = models.ManyToManyField(
        'app_cabinet.CabinetUser',
        verbose_name=_("General Contact Notification Recipients"),
        help_text=_("Cabinet users who will receive general contact form notifications"),
        blank=True,
        related_name='contact_notifications'
    )
    
    # Specific Contact Notification Recipients for Inquiry Types
    general_notification_users = models.ManyToManyField(
        'app_cabinet.CabinetUser',
        verbose_name=_("General Inquiry Recipients"),
        help_text=_("Users who will receive General inquiry messages"),
        blank=True,
        related_name='general_notifications'
    )
    
    support_notification_users = models.ManyToManyField(
        'app_cabinet.CabinetUser',
        verbose_name=_("Technical Support Recipients"),
        help_text=_("Users who will receive Technical Support inquiries"),
        blank=True,
        related_name='support_notifications'
    )
    
    sales_notification_users = models.ManyToManyField(
        'app_cabinet.CabinetUser',
        verbose_name=_("Sales & Demo Request Recipients"),
        help_text=_("Users who will receive Sales & Demo Request inquiries"),
        blank=True,
        related_name='sales_notifications'
    )
    
    partnership_notification_users = models.ManyToManyField(
        'app_cabinet.CabinetUser',
        verbose_name=_("Partnership Opportunities Recipients"),
        help_text=_("Users who will receive Partnership Opportunities inquiries"),
        blank=True,
        related_name='partnership_notifications'
    )
    
    security_notification_users = models.ManyToManyField(
        'app_cabinet.CabinetUser',
        verbose_name=_("Security Issue Report Recipients"),
        help_text=_("Users who will receive Security Issue Report inquiries"),
        blank=True,
        related_name='security_notifications'
    )
    
    feedback_notification_users = models.ManyToManyField(
        'app_cabinet.CabinetUser',
        verbose_name=_("Feedback & Suggestions Recipients"),
        help_text=_("Users who will receive Feedback & Suggestions inquiries"),
        blank=True,
        related_name='feedback_notifications'
    )
    
    other_notification_users = models.ManyToManyField(
        'app_cabinet.CabinetUser',
        verbose_name=_("Other Inquiry Recipients"),
        help_text=_("Users who will receive Other type inquiries"),
        blank=True,
        related_name='other_notifications'
    )
    
    # Auto-reply Settings
    enable_contact_auto_reply = models.BooleanField(
        default=False,
        verbose_name=_("Enable Contact Auto-Reply"),
        help_text=_("Send automatic reply to users who submit contact form")
    )
    
    contact_auto_reply_account = models.ForeignKey(
        'app_conf.MailAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Auto-Reply Email Account"),
        help_text=_("Email account to use for auto-replies")
    )
    
    auto_reply_subject = models.CharField(
        max_length=200,
        default="Thank you for contacting SecBoard",
        verbose_name=_("Auto-Reply Subject"),
        help_text=_("Subject line for auto-reply emails. Use {name} and {subject} placeholders")
    )
    
    auto_reply_body = models.TextField(
        default="Dear {name},\n\nThank you for your message regarding '{subject}'. We have received your inquiry and will get back to you as soon as possible.\n\nBest regards,\nSecBoard Team",
        verbose_name=_("Auto-Reply Body"),
        help_text=_("Body text for auto-reply emails. Use {name} and {subject} placeholders")
    )
    
    # Contact Information
    contact_address = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Contact Address"),
        help_text=_("Physical address for contact information")
    )
    
    contact_phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Contact Phone"),
        help_text=_("Phone number for contact information")
    )
    
    contact_email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_("Contact Email"),
        help_text=_("Email address for contact information")
    )
    
    working_hours = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Working Hours"),
        help_text=_("Business working hours")
    )
    
    # Social Media Links
    facebook_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Facebook URL"),
        help_text=_("Facebook page URL")
    )
    
    twitter_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Twitter URL"),
        help_text=_("Twitter profile URL")
    )
    
    linkedin_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("LinkedIn URL"),
        help_text=_("LinkedIn profile URL")
    )
    
    telegram_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Telegram URL"),
        help_text=_("Telegram channel or group URL")
    )
    
    github_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("GitHub URL"),
        help_text=_("GitHub repository or profile URL")
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Contact Settings")
        verbose_name_plural = _("Contact Settings")
    
    def __str__(self):
        return "Contact Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton ContactSettings instance"""
        settings, created = cls.objects.get_or_create(
            defaults={
                'support_email': 'support@secboard.online',
                'auto_reply_subject': 'Thank you for contacting SecBoard',
                'auto_reply_body': 'Dear {name},\n\nThank you for your message regarding \'{subject}\'. We have received your inquiry and will get back to you as soon as possible.\n\nBest regards,\nSecBoard Team'
            }
        )
        return settings
    
    def get_notification_recipients_for_inquiry_type(self, inquiry_type):
        """Get notification recipients based on inquiry type"""
        recipients = []
        
        # Get specific recipients for the inquiry type (using exact field names from ContactMessage)
        if inquiry_type == 'general':
            recipients = list(self.general_notification_users.all())
        elif inquiry_type == 'support':
            recipients = list(self.support_notification_users.all())
        elif inquiry_type == 'sales':
            recipients = list(self.sales_notification_users.all())
        elif inquiry_type == 'partnership':
            recipients = list(self.partnership_notification_users.all())
        elif inquiry_type == 'security':
            recipients = list(self.security_notification_users.all())
        elif inquiry_type == 'feedback':
            recipients = list(self.feedback_notification_users.all())
        elif inquiry_type == 'other':
            recipients = list(self.other_notification_users.all())
        
        # If no specific recipients, fall back to general recipients
        if not recipients:
            recipients = list(self.contact_notification_users.all())
        
        # Add support_email if configured
        if self.support_email:
            # Create a mock user object for the support email
            class MockUser:
                def __init__(self, email):
                    self.email = email
                    self.user = type('MockUser', (), {'email': email})()
            
            recipients.append(MockUser(self.support_email))
        
        return recipients
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and ContactSettings.objects.exists():
            # If this is a new instance but one already exists, update the existing one
            existing = ContactSettings.objects.first()
            for field in self._meta.fields:
                if field.name not in ['id', 'created_at', 'updated_at']:
                    setattr(existing, field.name, getattr(self, field.name))
            existing.save()
            return existing
        return super().save(*args, **kwargs)


# ============================================================================
# License Management Models
# Моделі для управління ліцензіями
# ============================================================================

_HMAC_SALT = b'SecBoard_License_Record_Integrity_v1_xK9mQ2'   # legacy — v1 compat only
_HMAC_SALT_V2 = b'SecBoard_License_Record_Integrity_v2'


def _get_record_hmac_key(v1_compat=False):
    """
    Derive the HMAC key used to sign/verify the integrity of SecureLicense records.

    v2 (default): SHA256(salt_v2 + server_id + ':' + SECRET_KEY)
      Requires BOTH the hardware identity (.secboard_server_id) AND Django's
      SECRET_KEY (stored in .env / settings).  An attacker who can read the
      filesystem cannot forge v2 HMACs without also obtaining SECRET_KEY.

    v1 (v1_compat=True): SHA256(salt_v1 + server_id)
      Used ONLY as a migration fallback inside verify_record_integrity() to
      detect records written before the v2 upgrade.  Never used for new writes.
    """
    import hashlib
    try:
        from app_conf.hardware_binding import HardwareFingerprint
        server_id = HardwareFingerprint.get_server_id()
    except Exception:
        server_id = 'fallback-no-hw'

    if v1_compat:
        return hashlib.sha256(_HMAC_SALT + server_id.encode('utf-8')).digest()

    try:
        from django.conf import settings as _s
        _secret = (_s.SECRET_KEY or '').encode('utf-8')
    except Exception:
        _secret = b'missing-django-secret'

    return hashlib.sha256(
        _HMAC_SALT_V2
        + server_id.encode('utf-8')
        + b':'
        + _secret
    ).digest()


class SecureLicense(models.Model):
    """
    Модель захищеної ліцензії
    
    Зберігає зашифровані дані ліцензії з цифровим підписом RSA.
    Прив'язується до апаратного забезпечення сервера.
    """
    
    # Ліцензійний ключ (публічна частина, формат: BASE64_DATA.BASE64_SIGNATURE)
    # RSA-4096 підпис може бути до ~1040 символів, тому використовуємо TextField
    # Для унікальності використовуємо license_key_hash
    license_key = models.TextField(
        verbose_name=_("License Key")
    )
    
    # SHA256 хеш license_key для унікальності та швидкого пошуку
    license_key_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name=_("License Key Hash"),
        default=''  # Temporary default for migration
    )
    
    # Підпис ліцензії (RSA signature, зберігається окремо для верифікації)
    # RSA-4096 підпис в Base64 може бути до ~800 символів
    signature = models.CharField(
        max_length=1024,
        blank=True,
        verbose_name=_("Signature")
    )
    
    # Hardware fingerprint (SHA256 хеш апаратних характеристик сервера)
    hardware_fingerprint = models.CharField(
        max_length=64,
        verbose_name=_("Hardware Fingerprint")
    )
    
    # Зашифровані дані ліцензії (JSON з інформацією про ліцензію)
    encrypted_data = models.JSONField(
        default=dict,
        verbose_name=_("License Data")
    )
    
    # Дата останньої успішної валідації
    last_validated = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Validated")
    )
    
    # Лічильник невдалих перевірок (для виявлення атак)
    failed_validations = models.IntegerField(
        default=0,
        verbose_name=_("Failed Validations")
    )
    
    # Статус активності (керується системою автоматично)
    is_active = models.BooleanField(
        default=False,
        verbose_name=_("Active")
    )
    
    # Віддалене блокування з сервера ліцензій
    is_blocked = models.BooleanField(
        default=False,
        verbose_name=_("Is Blocked")
    )
    
    # Причина блокування
    block_reason = models.TextField(
        blank=True,
        default='',
        verbose_name=_("Block Reason")
    )
    
    # Offline grace period - до якої дати можна працювати без зв'язку з сервером
    offline_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Offline Until")
    )
    
    # HMAC of critical fields — detects direct DB tampering
    record_hmac = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name=_("Record HMAC")
    )
    
    # Дати створення та оновлення
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    
    class Meta:
        verbose_name = _("Secure License")
        verbose_name_plural = _("Secure Licenses")
        ordering = ['-created_at']
    
    def _compute_record_hmac(self, _override_key=None, _v2_payload=False):
        """Compute HMAC-SHA256 over security-critical fields.

        Parameters:
          _override_key  — use this key instead of the default v2 key (e.g.,
                           pass the v1 compat key for migration checks).
          _v2_payload    — use the v2 payload layout (without offline_until);
                           required when verifying records written before the
                           v3 upgrade that added offline_until to the payload.

        Payload layout:
          v2 (legacy, _v2_payload=True):
            license_key_hash | hardware_fingerprint | is_active | is_blocked |
            block_reason | encrypted_data | failed_validations
          v3 (current, _v2_payload=False):
            … same fields … | offline_until          ← direct-DB tampering now
                                                         invalidates the HMAC
        """
        import hmac as _hmac
        import hashlib
        import json

        key = _override_key if _override_key is not None else _get_record_hmac_key()
        parts = [
            self.license_key_hash or '',
            self.hardware_fingerprint or '',
            '1' if self.is_active else '0',
            '1' if self.is_blocked else '0',
            self.block_reason or '',
            json.dumps(self.encrypted_data, sort_keys=True) if self.encrypted_data is not None else '',
            str(self.failed_validations),
        ]
        if not _v2_payload:
            # v3: include offline_until so direct DB modification is detectable.
            parts.append(self.offline_until.isoformat() if self.offline_until else '')
        payload = '|'.join(parts)
        return _hmac.new(key, payload.encode('utf-8'), hashlib.sha256).hexdigest()
    
    def verify_record_integrity(self):
        """
        Verify critical DB fields were not modified outside the application.

        Returns False if HMAC is missing — an empty record_hmac is not a valid
        state after migrations have been applied and is a strong indicator of
        deliberate DB tampering to bypass the integrity check.

        Migration chain (oldest → newest):
          v1 — SHA256(salt_v1 + server_id),              v2-payload (no offline_until)
          v2 — SHA256(salt_v2 + server_id + SECRET_KEY), v2-payload
          v3 — SHA256(salt_v2 + server_id + SECRET_KEY), v3-payload (+ offline_until)
               ↑ current default.  offline_until is now part of the signed payload
               so direct DB modification of the grace-period timestamp invalidates
               the HMAC and is caught on the next request.

        Each legacy level auto-upgrades to v3 on first successful check.
        """
        import hmac as _hmac
        import logging
        _logger = logging.getLogger(__name__)

        if not self.record_hmac:
            _logger.critical(
                f"SECURITY: License record HMAC is empty (id={self.pk})! "
                "Possible DB tampering — record_hmac was cleared to bypass integrity check."
            )
            return False

        # ── v3 check (current: v2 key + v3 payload with offline_until) ──────
        expected_v3 = self._compute_record_hmac()
        if _hmac.compare_digest(self.record_hmac, expected_v3):
            return True

        # ── v2 check (v2 key + v2 payload without offline_until) ─────────────
        try:
            _expected_v2 = self._compute_record_hmac(_v2_payload=True)
            if _hmac.compare_digest(self.record_hmac, _expected_v2):
                _logger.info(
                    f"record_hmac v2→v3 migration for license id={self.pk}; "
                    "re-saving with v3 payload (offline_until added)"
                )
                self.save(update_fields=['record_hmac'])
                return True
        except Exception as _ev2:
            _logger.debug(f"v2 HMAC compat check error: {_ev2}")

        # ── v1 check (v1 key + v2 payload — written before SECRET_KEY was added) ─
        try:
            _v1_key = _get_record_hmac_key(v1_compat=True)
            _expected_v1 = self._compute_record_hmac(_override_key=_v1_key, _v2_payload=True)
            if _hmac.compare_digest(self.record_hmac, _expected_v1):
                _logger.info(
                    f"record_hmac v1→v3 migration for license id={self.pk}; "
                    "re-saving with v3 key+payload (SECRET_KEY + offline_until)"
                )
                self.save(update_fields=['record_hmac'])
                return True
        except Exception as _ev1:
            _logger.debug(f"v1 HMAC compat check error: {_ev1}")

        return False
    
    def save(self, *args, **kwargs):
        """
        Автоматична генерація license_key_hash та record_hmac при збереженні.
        skip_record_hmac=True — лише оновити інші поля без перерахунку HMAC
        (наприклад після виявлення підміни запису).
        """
        import hashlib
        skip_record_hmac = kwargs.pop('skip_record_hmac', False)
        if self.license_key:
            self.license_key_hash = hashlib.sha256(self.license_key.encode('utf-8')).hexdigest()
        if not skip_record_hmac:
            try:
                self.record_hmac = self._compute_record_hmac()
            except Exception:
                pass
        super().save(*args, **kwargs)
    
    def __str__(self):
        try:
            data = self.get_license_data()
            if data:
                company = data.get('company', 'Unknown')
                expiration = data.get('expiration_date', 'Unknown')
                return f"{company} - Expires: {expiration}"
            return f"License (ID: {self.pk})"
        except:
            return f"License (ID: {self.pk})"
    
    def get_license_data(self):
        """
        Отримання та валідація даних ліцензії
        
        Returns:
            dict: Дані ліцензії або None у випадку помилки
        """
        try:
            from app_conf.license_crypto import LicenseCrypto
            from app_conf.hardware_binding import HardwareFingerprint
            
            if not self.verify_record_integrity():
                import logging
                logger = logging.getLogger(__name__)
                logger.critical(
                    f"SECURITY: License record HMAC mismatch (id={self.pk})! "
                    "Database tampering detected — critical fields modified outside application."
                )
                self.failed_validations += 1
                self.save(update_fields=['failed_validations'], skip_record_hmac=True)
                return None
            
            # Розпакування ключа
            license_data, signature = LicenseCrypto.extract_license_data(self.license_key)
            
            if not license_data or not signature:
                self.failed_validations += 1
                self.save(update_fields=['failed_validations', 'record_hmac'])
                return None
            
            # Перевірка підпису
            if not LicenseCrypto.verify_license_signature(license_data, signature):
                self.failed_validations += 1
                self.save(update_fields=['failed_validations', 'record_hmac'])
                return None
            
            # Перевірка Server ID (хеш від Hardware ID + HTTP_HOST)
            # ВАЖЛИВО: Тепер використовуємо Server ID замість Hardware ID
            license_server_id = license_data.get('hardware_id', '').strip()  # На сервері це зберігається як hardware_id, але тепер це Server ID
            current_server_id = HardwareFingerprint.get_server_id().strip()
            
            if license_server_id != current_server_id:
                import logging
                logger = logging.getLogger(__name__)
                logger.critical(
                    f"Server ID mismatch in get_license_data! "
                    f"License Server ID: {license_server_id[:16] if license_server_id else 'N/A'}..., "
                    f"Current Server ID: {current_server_id[:16]}..."
                )
                self.failed_validations += 1
                self.save(update_fields=['failed_validations', 'record_hmac'])
                return None
            
            # Успішна валідація
            self.last_validated = timezone.now()
            self.failed_validations = 0
            self.save(update_fields=['last_validated', 'failed_validations', 'record_hmac'])
            
            return license_data
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"License data validation error: {str(e)}")
            self.failed_validations += 1
            self.save(update_fields=['failed_validations', 'record_hmac'])
            return None
    
    def is_valid(self):
        """
        Перевірка чи ліцензія дійсна
        
        Returns:
            bool: True якщо ліцензія валідна
        """
        from datetime import datetime
        
        data = self.get_license_data()
        if not data:
            return False
        
        # Перевірка терміну дії
        try:
            expiration = datetime.fromisoformat(data.get('expiration_date'))
            if expiration.date() < timezone.now().date():
                self.is_active = False
                self.save(update_fields=['is_active'])
                return False
        except:
            return False
        
        # Перевірка блокування
        if self.failed_validations > 10:
            return False
        
        return True
    
    # Module access check disabled
    # def check_module_access(self, module_name):
    #     """
    #     Перевірка доступу до модуля
    #     
    #     Args:
    #         module_name (str): Назва модуля
    #         
    #     Returns:
    #         bool: True якщо доступ дозволений
    #     """
    #     data = self.get_license_data()
    #     if not data:
    #         return False
    #     
    #     modules = data.get('modules', {})
    #     return modules.get(module_name, False)
    
    def get_user_limit(self):
        """
        Отримання ліміту користувачів
        
        Returns:
            int: Максимальна кількість користувачів
        """
        data = self.get_license_data()
        return data.get('max_users', 0) if data else 0


class LicenseActivation(models.Model):
    """
    Журнал активації ліцензій
    
    Відстежує всі спроби активації для виявлення зловживань
    та несанкціонованого використання.
    """
    
    license = models.ForeignKey(
        SecureLicense,
        on_delete=models.CASCADE,
        related_name='activations',
        null=True,
        blank=True,
        verbose_name=_("License")
    )
    
    activation_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Activation Date")
    )
    
    hardware_fingerprint = models.CharField(
        max_length=64,
        verbose_name=_("Hardware Fingerprint")
    )
    
    ip_address = models.GenericIPAddressField(
        verbose_name=_("IP Address")
    )
    
    success = models.BooleanField(
        verbose_name=_("Success")
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name=_("Error Message")
    )
    
    # Інформація про сервер (JSON з деталями системи)
    server_info = models.JSONField(
        default=dict,
        verbose_name=_("Server Info")
    )
    
    class Meta:
        verbose_name = _("License Activation")
        verbose_name_plural = _("License Activations")
        ordering = ['-activation_date']
    
    def __str__(self):
        status = "SUCCESS" if self.success else "FAILED"
        return f"Activation {status} at {self.activation_date}"


class LicenseHeartbeat(models.Model):
    """
    Журнал heartbeat перевірок з сервером ліцензій
    
    Зберігає історію зв'язку з центральним сервером ліцензій
    для моніторингу та виявлення проблем.
    """
    
    license = models.ForeignKey(
        SecureLicense,
        on_delete=models.CASCADE,
        related_name='heartbeats',
        verbose_name=_("License")
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Timestamp")
    )
    
    response_code = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Response Code")
    )
    
    response_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Response Data")
    )
    
    # Статистика використання (відправляється на сервер)
    usage_stats = models.JSONField(
        default=dict,
        verbose_name=_("Usage Statistics")
    )
    
    # Статус запиту
    success = models.BooleanField(
        default=False,
        verbose_name=_("Success")
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name=_("Error Message")
    )
    
    class Meta:
        verbose_name = _("License Heartbeat")
        verbose_name_plural = _("License Heartbeats")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['license', '-timestamp']),
        ]
    
    def __str__(self):
        status = "OK" if self.success else "FAILED"
        return f"Heartbeat {status} at {self.timestamp}"


class LicenseValidationLog(models.Model):
    """
    Детальний журнал всіх валідацій ліцензій
    
    Зберігає історію всіх перевірок ліцензії для аудиту та
    виявлення спроб несанкціонованого доступу.
    """
    
    license = models.ForeignKey(
        SecureLicense,
        on_delete=models.CASCADE,
        related_name='validation_logs',
        verbose_name=_("License")
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Timestamp")
    )
    
    validation_result = models.BooleanField(
        verbose_name=_("Validation Result")
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name=_("Error Message")
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("IP Address")
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name=_("User Agent")
    )
    
    # Додаткова інформація
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Extra Data")
    )
    
    class Meta:
        verbose_name = _("License Validation Log")
        verbose_name_plural = _("License Validation Logs")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['license', '-timestamp']),
            models.Index(fields=['validation_result', '-timestamp']),
        ]
    
    def __str__(self):
        result = "VALID" if self.validation_result else "INVALID"
        return f"Validation {result} at {self.timestamp}"
