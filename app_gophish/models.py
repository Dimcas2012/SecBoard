# app_gophish/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField
import json


class GophishServer(models.Model):
    """Model to store Gophish server configurations"""
    
    name = models.CharField(max_length=100, verbose_name="Server Name")
    base_url = models.URLField(verbose_name="Base URL")
    api_key = EncryptedCharField(max_length=500, verbose_name="API Key")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    company = models.ForeignKey('app_conf.Company', on_delete=models.CASCADE, verbose_name=_("Company"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gophish_servers')
    
    class Meta:
        verbose_name = "Gophish Server"
        verbose_name_plural = "Gophish Servers"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.base_url})"


class GophishGroup(models.Model):
    """Model to store Gophish groups"""
    
    server = models.ForeignKey(GophishServer, on_delete=models.CASCADE, related_name='groups')
    gophish_id = models.CharField(max_length=50, verbose_name="Gophish ID")
    name = models.CharField(max_length=200, verbose_name="Group Name")
    targets_data = models.JSONField(default=dict, verbose_name="Targets Data")
    last_sync = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Gophish Group"
        verbose_name_plural = "Gophish Groups"
        ordering = ['name']
        unique_together = ['server', 'gophish_id']
    
    def __str__(self):
        return f"{self.name} ({self.server.name})"
    
    @property
    def target_count(self):
        """Get the number of targets in this group"""
        return len(self.targets_data.get('targets', []))


class GophishTemplate(models.Model):
    """Model to store Gophish email templates"""
    
    server = models.ForeignKey(GophishServer, on_delete=models.CASCADE, related_name='templates')
    gophish_id = models.CharField(max_length=50, verbose_name="Gophish ID")
    name = models.CharField(max_length=200, verbose_name="Template Name")
    subject = models.CharField(max_length=500, verbose_name="Subject")
    html_content = models.TextField(verbose_name="HTML Content")
    text_content = models.TextField(blank=True, verbose_name="Text Content")
    last_sync = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Gophish Template"
        verbose_name_plural = "Gophish Templates"
        ordering = ['name']
        unique_together = ['server', 'gophish_id']
    
    def __str__(self):
        return f"{self.name} ({self.server.name})"


class GophishLandingPage(models.Model):
    """Model to store Gophish landing pages"""
    
    server = models.ForeignKey(GophishServer, on_delete=models.CASCADE, related_name='landing_pages')
    gophish_id = models.CharField(max_length=50, verbose_name="Gophish ID")
    name = models.CharField(max_length=200, verbose_name="Landing Page Name")
    html_content = models.TextField(verbose_name="HTML Content")
    capture_credentials = models.BooleanField(default=False, verbose_name="Capture Credentials")
    capture_passwords = models.BooleanField(default=False, verbose_name="Capture Passwords")
    redirect_url = models.URLField(blank=True, verbose_name="Redirect URL")
    last_sync = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Gophish Landing Page"
        verbose_name_plural = "Gophish Landing Pages"
        ordering = ['name']
        unique_together = ['server', 'gophish_id']
    
    def __str__(self):
        return f"{self.name} ({self.server.name})"


class GophishSendingProfile(models.Model):
    """Model to store Gophish sending profiles"""
    
    server = models.ForeignKey(GophishServer, on_delete=models.CASCADE, related_name='sending_profiles')
    gophish_id = models.CharField(max_length=50, verbose_name="Gophish ID")
    name = models.CharField(max_length=200, verbose_name="Profile Name")
    from_address = models.EmailField(verbose_name="From Address")
    from_name = models.CharField(max_length=200, verbose_name="From Name")
    smtp_host = models.CharField(max_length=200, verbose_name="SMTP Host")
    smtp_port = models.IntegerField(default=587, verbose_name="SMTP Port")
    smtp_username = models.CharField(max_length=200, verbose_name="SMTP Username")
    smtp_password = EncryptedCharField(max_length=500, verbose_name="SMTP Password")
    ignore_cert_errors = models.BooleanField(default=False, verbose_name="Ignore Certificate Errors")
    last_sync = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Gophish Sending Profile"
        verbose_name_plural = "Gophish Sending Profiles"
        ordering = ['name']
        unique_together = ['server', 'gophish_id']
    
    def __str__(self):
        return f"{self.name} ({self.server.name})"


class GophishCampaign(models.Model):
    """Model to store Gophish campaigns"""
    
    CAMPAIGN_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('error', 'Error'),
    ]
    
    server = models.ForeignKey(GophishServer, on_delete=models.CASCADE, related_name='campaigns')
    gophish_id = models.CharField(max_length=50, verbose_name="Gophish ID")
    name = models.CharField(max_length=200, verbose_name="Campaign Name")
    status = models.CharField(max_length=20, choices=CAMPAIGN_STATUS_CHOICES, default='draft', verbose_name="Status")
    
    # Campaign components - allow NULL for deleted components
    template = models.ForeignKey(GophishTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    landing_page = models.ForeignKey(GophishLandingPage, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    sending_profile = models.ForeignKey(GophishSendingProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    groups = models.ManyToManyField(GophishGroup, related_name='campaigns', verbose_name="Target Groups")
    
    # Campaign settings
    launch_date = models.DateTimeField(null=True, blank=True, verbose_name="Launch Date")
    send_by_date = models.DateTimeField(null=True, blank=True, verbose_name="Send By Date")
    url = models.URLField(blank=True, verbose_name="Campaign URL")
    
    # Campaign results
    results_data = models.JSONField(default=dict, verbose_name="Results Data")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gophish_campaigns')
    last_sync = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Gophish Campaign"
        verbose_name_plural = "Gophish Campaigns"
        ordering = ['-created_at']
        unique_together = ['server', 'gophish_id']
    
    def __str__(self):
        return f"{self.name} ({self.server.name}) - {self.status}"
    
    @property
    def total_targets(self):
        """Get total number of targets across all groups"""
        return sum(group.target_count for group in self.groups.all())
    
    @property
    def emails_sent(self):
        """Get number of emails sent"""
        return self.results_data.get('emails_sent', 0)
    
    @property
    def emails_opened(self):
        """Get number of emails opened"""
        return self.results_data.get('emails_opened', 0)
    
    @property
    def links_clicked(self):
        """Get number of links clicked"""
        return self.results_data.get('links_clicked', 0)
    
    @property
    def credentials_submitted(self):
        """Get number of credentials submitted"""
        return self.results_data.get('credentials_submitted', 0)
    
    @property
    def data_submitted(self):
        """Get number of data submissions"""
        return self.results_data.get('data_submitted', 0)


class GophishEvent(models.Model):
    """Model to store Gophish campaign events"""
    
    EVENT_TYPE_CHOICES = [
        ('email_sent', 'Email Sent'),
        ('email_opened', 'Email Opened'),
        ('link_clicked', 'Link Clicked'),
        ('credentials_submitted', 'Credentials Submitted'),
        ('data_submitted', 'Data Submitted'),
        ('error', 'Error'),
    ]
    
    campaign = models.ForeignKey(GophishCampaign, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, verbose_name="Event Type")
    target_email = models.EmailField(verbose_name="Target Email")
    target_name = models.CharField(max_length=200, blank=True, verbose_name="Target Name")
    timestamp = models.DateTimeField(verbose_name="Timestamp")
    details = models.JSONField(default=dict, verbose_name="Event Details")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Address")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    
    class Meta:
        verbose_name = "Gophish Event"
        verbose_name_plural = "Gophish Events"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['campaign', 'event_type']),
            models.Index(fields=['target_email']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.campaign.name} - {self.event_type} - {self.target_email}"


class GophishSyncLog(models.Model):
    """Model to track synchronization logs"""
    
    SYNC_TYPE_CHOICES = [
        ('full', 'Full Sync'),
        ('campaigns', 'Campaigns Only'),
        ('groups', 'Groups Only'),
        ('templates', 'Templates Only'),
        ('landing_pages', 'Landing Pages Only'),
        ('sending_profiles', 'Sending Profiles Only'),
        ('results', 'Results Only'),
    ]
    
    STATUS_CHOICES = [
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    ]
    
    server = models.ForeignKey(GophishServer, on_delete=models.CASCADE, related_name='sync_logs')
    sync_type = models.CharField(max_length=20, choices=SYNC_TYPE_CHOICES, verbose_name="Sync Type")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name="Status")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Started At")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Completed At")
    records_processed = models.IntegerField(default=0, verbose_name="Records Processed")
    records_created = models.IntegerField(default=0, verbose_name="Records Created")
    records_updated = models.IntegerField(default=0, verbose_name="Records Updated")
    records_failed = models.IntegerField(default=0, verbose_name="Records Failed")
    error_message = models.TextField(blank=True, verbose_name="Error Message")
    details = models.JSONField(default=dict, verbose_name="Sync Details")
    
    class Meta:
        verbose_name = "Gophish Sync Log"
        verbose_name_plural = "Gophish Sync Logs"
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.server.name} - {self.sync_type} - {self.status} ({self.started_at})"
    
    @property
    def duration(self):
        """Get sync duration"""
        if self.completed_at:
            return self.completed_at - self.started_at
        return None


class AccessGophish(models.Model):
    """Model for controlling access to Gophish module"""
    group = models.ForeignKey('auth.Group', on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to Gophish"))
    can_view_campaigns = models.BooleanField(default=False, verbose_name=_("Can view campaigns"))
    can_view_templates = models.BooleanField(default=False, verbose_name=_("Can view templates"))
    can_view_landing_pages = models.BooleanField(default=False, verbose_name=_("Can view landing pages"))
    can_view_sending_profiles = models.BooleanField(default=False, verbose_name=_("Can view sending profiles"))
    can_view_groups = models.BooleanField(default=False, verbose_name=_("Can view target groups"))
    can_manage_servers = models.BooleanField(default=False, verbose_name=_("Can manage servers"))
    can_sync = models.BooleanField(default=False, verbose_name=_("Can synchronize data"))
    companies = models.ManyToManyField('app_conf.Company', blank=True, related_name='access_gophish', verbose_name=_("Companies"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Access to Gophish")
        verbose_name_plural = _("Access to Gophish")

    def __str__(self):
        return f"{self.group.name} - Has Access: {self.has_access}"


from tinymce.models import HTMLField


class GophishGuide(models.Model):
    """Base Guide for Gophish. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Gophish Guide")
        verbose_name_plural = _("Gophish Guides")

    def __str__(self):
        return gettext("Gophish Guide")


class GophishGuideTranslation(models.Model):
    """Per-country (language) translations of the Gophish Guide."""
    guide = models.ForeignKey(
        GophishGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="gophish_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Gophish Guide Translation")
        verbose_name_plural = _("Gophish Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"
