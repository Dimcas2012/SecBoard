#  SecBoard\SecBoard\app_cabinet\models.py


from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings as django_settings
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext
from app_study.models import Page
from app_conf.models import Company, MailAccount
from mptt.models import MPTTModel, TreeForeignKey
from encrypted_model_fields.fields import EncryptedCharField

import geoip2.database
from django.conf import settings
import os
import logging
import secrets
import uuid
from datetime import time as time_type

logger = logging.getLogger(__name__)


class CabinetGroup(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='cabinet_details')
    name = models.CharField(_("Name"), max_length=50)
    description = models.TextField(_("Description"), blank=True)
    company = models.ForeignKey(
        'app_conf.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Company")
    )
    color = models.CharField(_("Color"), max_length=7, default="#000000")

    class Meta:
        verbose_name = _('Cabinet Group Details')
        verbose_name_plural = _('Cabinet Group Details')

    def __str__(self):
        company_name = self.company.name if self.company else "Без компанії"
        return f"{self.name} ({company_name})"

    def get_name(self, lang=None):
        """Return group name (single language). Kept for API compatibility."""
        return self.name

    def get_description(self, lang=None):
        """Return group description. Kept for API compatibility."""
        return self.description


class PlatformRole(models.Model):
    """
    Platform role (profile) e.g. CISO, SOC analyst, internal auditor.
    Defines which access groups apply and which metrics/modules are available.
    Companies (from Access to Cabinet Management scope): if set, role applies only to these companies; if empty, role is global.
    """
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True)
    slug = models.SlugField(_("Slug"), max_length=100, blank=True, unique=True)
    is_active = models.BooleanField(_("Active"), default=True)
    color = models.CharField(_("Color"), max_length=7, default="#6c757d")
    # Companies this role applies to (from Access to Cabinet Management). Empty = all companies / global role.
    companies = models.ManyToManyField(
        'app_conf.Company',
        blank=True,
        related_name='platform_roles',
        verbose_name=_("Companies")
    )
    # Groups assigned to this role (users with this role can get these groups)
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name='platform_roles',
        verbose_name=_("Access Groups")
    )
    # Optional: list of metric/module codes to show (e.g. site_statistics, incidents, risk)
    allowed_metrics_modules = models.JSONField(
        _("Allowed metrics and modules"),
        default=list,
        blank=True,
        help_text=_("List of module/metric codes this role can see (e.g. site_statistics, incidents).")
    )
    order = models.PositiveIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Platform Role")
        verbose_name_plural = _("Platform Roles")
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class PlatformRoleDashboardConfig(models.Model):
    """
    Per-role dashboard (Executive View) configuration.
    Defines which sections and widgets are shown for this platform role.
    """
    platform_role = models.OneToOneField(
        PlatformRole,
        on_delete=models.CASCADE,
        related_name='dashboard_config',
        verbose_name=_("Platform Role")
    )
    config = models.JSONField(
        _("Dashboard config"),
        default=dict,
        blank=True,
        help_text=_(
            "JSON: sections list, each with id, enabled, widgets list. "
            "e.g. {\"sections\": [{\"id\": \"top_panel\", \"enabled\": true, \"widgets\": [\"security_index\", ...]}]}"
        )
    )
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Platform Role Dashboard Config")
        verbose_name_plural = _("Platform Role Dashboard Configs")

    def __str__(self):
        return _("Dashboard config for %(role)s") % {"role": self.platform_role.name}


class Department(MPTTModel):
    """Department with single Name and Description (no translations)."""
    name = models.CharField(_("Name"), max_length=255, blank=True, help_text=_("Department name."))
    description = models.TextField(_("Description"), blank=True, help_text=_("Department description."))
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Company")
    )
    color = models.CharField(_("Color"), max_length=7, default="#000000")
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_("Parent Department")
    )
    parent_position = models.ForeignKey(
        'Position',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departments',
        verbose_name=_("Parent Position")
    )

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")

    def get_name(self, lang=None):
        return self.name or ''

    def get_description(self, lang=None):
        return self.description or ''

    def __str__(self):
        return self.name or str(self.pk)


class Position(models.Model):
    """Position with single Name and Description (no translations)."""
    name = models.CharField(_("Name"), max_length=255, blank=True, help_text=_("Position name."))
    description = models.TextField(_("Description"), blank=True, help_text=_("Position description."))
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Company")
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Department")
    )
    parent_position = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_positions',
        verbose_name=_("Parent Position")
    )
    color = models.CharField(_("Color"), max_length=7, default="#000000")

    class Meta:
        verbose_name = _("Position")
        verbose_name_plural = _("Positions")
        ordering = ['name']

    def get_name(self, lang=None):
        return self.name or ''

    def get_description(self, lang=None):
        return self.description or ''

    def __str__(self):
        return self.name or str(self.pk)


def cabinet_user_avatar_upload_to(instance, filename):
    base_name = os.path.basename(filename)
    return f'user_avatars/{uuid.uuid4().hex}_{base_name}'


class CabinetUser(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name='cabinet'  # Added related_name
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Company")
    )
    is_profile_completed = models.BooleanField(
        default=False,
        verbose_name=_("Profile Completed")
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Department")
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Position")
    )
    phone = models.CharField(
        _('Phone'),
        max_length=20,
        blank=True,
        null=True
    )
    telegram_chat_id = models.CharField(
        _('Telegram Chat ID'),
        max_length=64,
        blank=True,
        help_text=_('Your Telegram Chat ID from the SecBoard bot (tap Help in the bot to see it).'),
    )
    telegram_link_token = models.CharField(
        _('Telegram link token'),
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        help_text=_('Secret token for Telegram deep-link account linking.'),
    )
    preferred_language = models.CharField(
        _('Default language'),
        max_length=10,
        blank=True,
        help_text=_('Preferred interface language for this user.'),
    )
    avatar = models.ImageField(
        upload_to=cabinet_user_avatar_upload_to,
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Avatar")
    )
    start_date = models.DateTimeField(
        _('Start Date'),
        null=True,
        blank=True,
        help_text=_('When the user started their position')
    )
    color = models.CharField(_("Color"), max_length=7, default="#000000")
    end_date = models.DateTimeField(
        _('End Date'),
        null=True,
        blank=True,
        help_text=_('When the user ended their position')
    )
    two_factor_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Two-Factor Authentication Enabled")
    )
    two_factor_secret = models.CharField(
        _("Two-Factor Secret"),
        max_length=64,
        blank=True
    )
    two_factor_temp_secret = models.CharField(
        _("Two-Factor Temporary Secret"),
        max_length=64,
        blank=True
    )
    two_factor_temp_created_at = models.DateTimeField(
        _("Two-Factor Temporary Secret Created At"),
        null=True,
        blank=True
    )
    two_factor_confirmed_at = models.DateTimeField(
        _("Two-Factor Confirmed At"),
        null=True,
        blank=True
    )
    two_factor_backup_codes = models.JSONField(
        _("Two-Factor Backup Codes"),
        default=list,
        blank=True
    )
    two_factor_last_used = models.DateTimeField(
        _("Two-Factor Last Used"),
        null=True,
        blank=True
    )
    force_two_factor = models.BooleanField(
        default=False,
        verbose_name=_("Require Two-Factor Authentication")
    )
    roles = models.ManyToManyField(
        'PlatformRole',
        blank=True,
        related_name='cabinet_users',
        verbose_name=_("Platform Roles")
    )
    is_ad_synced = models.BooleanField(
        _("Synced from AD"),
        default=False,
        help_text=_("User is provisioned from Active Directory; profile fields are updated on each AD login."),
    )
    ad_extra_attributes = models.JSONField(
        _("AD extra attributes"),
        default=dict,
        blank=True,
        help_text=_("Additional attributes from AD (General, Address, Telephones, etc.) stored at last login."),
    )

    def __str__(self):
        full_name = self.user.get_full_name()
        company_name = self.company.name if self.company else "Без компанії"
        
        if full_name:
            return f"{full_name} ({company_name}) - {self.user.email}"
        return f"{self.user.email} ({company_name})"

    class Meta:
        verbose_name = _("Cabinet User")

    @property
    def avatar_url(self):
        if not self.avatar:
            return None
        try:
            return self.avatar.url
        except Exception:
            return None

    @property
    def is_telegram_linked(self):
        return bool((self.telegram_chat_id or '').strip())

    def get_telegram_start_payload(self):
        if not self.telegram_link_token:
            self.telegram_link_token = secrets.token_urlsafe(32)[:64]
            self.save(update_fields=['telegram_link_token'])
        return f'link_{self.telegram_link_token}'

    def is_active_employee(self):
        if not self.start_date and not self.end_date:
            return True

        now = timezone.now()
        today = now.date()

        # Convert datetime to date for comparison
        start_date = self.start_date.date() if self.start_date else None
        end_date = self.end_date.date() if self.end_date else None

        if start_date and end_date:
            return start_date <= today <= end_date
        elif start_date:
            return start_date <= today
        elif end_date:
            return today <= end_date
        return True

    def clean(self):
        if self.start_date and self.end_date:
            # Convert to date for comparison
            start_date = self.start_date.date()
            end_date = self.end_date.date()

            if start_date > end_date:
                raise ValidationError({
                    'start_date': _('Start date must be before end date'),
                    'end_date': _('End date must be after start date')
                })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class CabinetSettings(models.Model):
    mail_account = models.ForeignKey(
        MailAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Mail Account")
    )

    class Meta:
        verbose_name = _("Cabinet Settings")
        verbose_name_plural = _("Cabinet Settings")

    def __str__(self):
        return str(_("Cabinet Settings"))


class CabinetPasswordCompanyLink(models.Model):
    cabinet_settings = models.ForeignKey(
        CabinetSettings,
        on_delete=models.CASCADE,
        related_name='password_links',
        verbose_name=_("Cabinet Settings")
    )
    cabinet_password = models.CharField(
        max_length=50,
        verbose_name=_("Control Word")
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_("Company")
    )

    class Meta:
        unique_together = ('cabinet_settings', 'cabinet_password')
        verbose_name = _("Control Word")
        verbose_name_plural = _("Control Words")

    def __str__(self):
        return f"{self.cabinet_password} - {self.company.name}"


class CabinetTaskReminderSchedule(models.Model):
    """
    Recurring email reminders about open cabinet tasks for selected Cabinet users.
    One-time sends are handled in the view without persisting a row.
    """
    FREQUENCY_DAILY = 'daily'
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_MONTHLY = 'monthly'
    FREQUENCY_CHOICES = [
        (FREQUENCY_DAILY, _('Daily')),
        (FREQUENCY_WEEKLY, _('Weekly')),
        (FREQUENCY_MONTHLY, _('Monthly')),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='cabinet_task_reminder_schedules',
        verbose_name=_('Company'),
    )
    recipients = models.ManyToManyField(
        'CabinetUser',
        related_name='task_reminder_schedules',
        blank=True,
        verbose_name=_('Recipients'),
    )
    frequency = models.CharField(_('Frequency'), max_length=16, choices=FREQUENCY_CHOICES)
    send_time = models.TimeField(_('Send time'), default=time_type(9, 0))
    weekday = models.PositiveSmallIntegerField(
        _('Weekday'),
        null=True,
        blank=True,
        help_text=_('For weekly schedule: 0 = Monday, 6 = Sunday'),
    )
    month_day = models.PositiveSmallIntegerField(
        _('Day of month'),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text=_('For monthly schedule: day of month (1–31)'),
    )
    is_active = models.BooleanField(_('Active'), default=True)
    periodic_task = models.OneToOneField(
        'django_celery_beat.PeriodicTask',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Periodic task'),
    )
    last_sent_at = models.DateTimeField(_('Last sent at'), null=True, blank=True)
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_cabinet_task_reminder_schedules',
        verbose_name=_('Created by'),
    )

    class Meta:
        verbose_name = _('Cabinet task reminder schedule')
        verbose_name_plural = _('Cabinet task reminder schedules')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.company} — {self.get_frequency_display()}'

    def clean(self):
        super().clean()
        if self.frequency == self.FREQUENCY_WEEKLY and self.weekday is None:
            raise ValidationError({'weekday': _('Select a weekday for weekly reminders.')})
        if self.frequency == self.FREQUENCY_MONTHLY and self.month_day is None:
            raise ValidationError({'month_day': _('Select a day of month for monthly reminders.')})

    def delete(self, *args, **kwargs):
        if self.periodic_task_id:
            try:
                self.periodic_task.delete()
            except Exception:
                pass
            self.periodic_task = None
        super().delete(*args, **kwargs)

    def sync_periodic_task(self):
        """Create or replace django-celery-beat PeriodicTask for this schedule."""
        import json
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        if self.periodic_task_id:
            try:
                self.periodic_task.delete()
            except Exception:
                pass
            self.periodic_task = None
            self.save(update_fields=['periodic_task'])

        if not self.is_active:
            return

        minute = self.send_time.minute
        hour = self.send_time.hour
        if self.frequency == self.FREQUENCY_DAILY:
            day_of_week = '*'
            day_of_month = '*'
        elif self.frequency == self.FREQUENCY_WEEKLY:
            py_wd = self.weekday if self.weekday is not None else 0
            day_of_week = str((int(py_wd) + 1) % 7)
            day_of_month = '*'
        else:
            day_of_week = '*'
            day_of_month = str(self.month_day or 1)

        schedule, _cr_created = CrontabSchedule.objects.get_or_create(
            minute=str(minute),
            hour=str(hour),
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year='*',
            timezone=str(django_settings.TIME_ZONE),
        )

        task = PeriodicTask.objects.create(
            name=f'Cabinet task reminders #{self.pk} ({self.company.name})',
            task='app_cabinet.tasks.run_cabinet_task_reminder_schedule',
            crontab=schedule,
            kwargs=json.dumps({'schedule_id': self.pk}),
            enabled=True,
            description=_('Email reminders about open cabinet tasks'),
        )
        self.periodic_task = task
        self.save(update_fields=['periodic_task'])


class CabinetADConnection(models.Model):
    """
    Active Directory / LDAP connection for one Company.
    Users with AD credentials can log in to the cabinet; first successful
    bind creates User + CabinetUser for that company (no manual sync).
    """
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='ad_connection',
        verbose_name=_("Company"),
        unique=True,
    )
    name = models.CharField(
        _("Name"),
        max_length=255,
        help_text=_("Display name for this AD connection"),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    server_url = models.CharField(
        _("Server URL"),
        max_length=255,
        help_text=_("LDAP server hostname or IP (e.g. dc.company.com)"),
    )
    port = models.PositiveIntegerField(
        _("Port"),
        default=389,
        help_text=_("389 for LDAP, 636 for LDAPS"),
    )
    use_ssl = models.BooleanField(
        _("Use SSL (LDAPS)"),
        default=False,
    )
    bind_dn = models.CharField(
        _("Bind DN"),
        max_length=512,
        help_text=_("DN of service account for directory search (e.g. CN=svc_ldap,OU=Service,DC=company,DC=com)"),
    )
    bind_password = EncryptedCharField(
        _("Bind password"),
        max_length=255,
    )
    base_dn = models.CharField(
        _("Base DN"),
        max_length=512,
        help_text=_("Base DN for user search (e.g. DC=company,DC=com)"),
    )
    user_search_ou = models.CharField(
        _("User search OU"),
        max_length=512,
        blank=True,
        help_text=_("Optional OU under base_dn to restrict user search (e.g. OU=Users)"),
    )
    user_filter = models.CharField(
        _("User object filter"),
        max_length=255,
        default="(objectClass=user)",
        help_text=_("LDAP filter for user objects (e.g. (objectClass=user))"),
    )
    # Attribute names for mapping (AD typical: sAMAccountName, mail, displayName)
    attr_username = models.CharField(
        _("Username attribute"),
        max_length=64,
        default="sAMAccountName",
        help_text=_("Attribute for login name (sAMAccountName or userPrincipalName)"),
    )
    attr_email = models.CharField(
        _("Email attribute"),
        max_length=64,
        default="mail",
    )
    attr_first_name = models.CharField(
        _("First name attribute"),
        max_length=64,
        default="givenName",
        blank=True,
    )
    attr_last_name = models.CharField(
        _("Last name attribute"),
        max_length=64,
        default="sn",
        blank=True,
    )
    attr_phone = models.CharField(
        _("Phone attribute"),
        max_length=64,
        blank=True,
        default="telephoneNumber",
        help_text=_("AD attribute for phone (e.g. telephoneNumber, mobile)"),
    )
    attr_start_date = models.CharField(
        _("Start date attribute"),
        max_length=64,
        blank=True,
        help_text=_("AD attribute for start date (e.g. whenCreated, or custom). LDAP generalized time (YYYYMMDDHHMMSS.0Z) or ISO date."),
    )
    attr_end_date = models.CharField(
        _("End date attribute"),
        max_length=64,
        blank=True,
        help_text=_("AD attribute for end date (e.g. accountExpires for expiry, or custom). Use blank to not sync."),
    )
    sync_ad_groups_to_cabinet = models.BooleanField(
        _("Sync AD groups to Cabinet groups"),
        default=False,
        help_text=_(
            "When enabled, on each AD login or refresh users are automatically added to Cabinet groups "
            "whose name matches one of their AD Member of groups (within the user's company or global groups)."
        ),
    )

    class Meta:
        verbose_name = _("Cabinet AD Connection")
        verbose_name_plural = _("Cabinet AD Connections")

    @staticmethod
    def _extract_domain_from_dn(dn):
        """Extract DC=... part from LDAP DN (e.g. DC=company,DC=com) for comparison."""
        if not dn or not isinstance(dn, str):
            return ""
        parts = [p.strip() for p in dn.split(",") if p.strip().upper().startswith("DC=")]
        return ",".join(p.lower() for p in parts)

    def clean(self):
        super().clean()
        bind_dn = (self.bind_dn or "").strip()
        base_dn = (self.base_dn or "").strip()
        if not bind_dn or not base_dn:
            return
        domain = self._extract_domain_from_dn(base_dn)
        if not domain:
            domain = self._extract_domain_from_dn(bind_dn)
        if not domain:
            return
        bind_dn_norm = bind_dn.lower()
        for other in CabinetADConnection.objects.exclude(pk=self.pk):
            if (other.bind_dn or "").strip().lower() != bind_dn_norm:
                continue
            other_domain = self._extract_domain_from_dn(other.base_dn or "")
            if other_domain and other_domain == domain:
                raise ValidationError(
                    _(
                        "Another Cabinet AD Connection for company \"%(company)s\" already uses the same domain (DC) and Bind DN. "
                        "Use a single connection per domain to avoid conflicts."
                    )
                    % {"company": other.company.name}
                )

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    user_agent = models.TextField()
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = _('User Session')
        verbose_name_plural = _('User Sessions')
        ordering = ['-login_time']

    def save(self, *args, **kwargs):
        # Handle local development IPs
        local_ips = ['127.0.0.1', 'localhost', '::1']
        if self.ip_address in local_ips:
            self.city = 'Local'
            self.country = 'Development'
        elif not self.country and self.ip_address:
            try:
                reader = geoip2.database.Reader(
                    os.path.join(settings.GEOIP_PATH, 'GeoLite2-City.mmdb')
                )
                response = reader.city(self.ip_address)
                self.country = response.country.name or ''
                self.city = response.city.name or ''
                reader.close()
            except Exception as e:
                logger.warning(f"GeoIP error: {str(e)}")
                self.city = 'Unknown'
                self.country = 'Unknown'
        super().save(*args, **kwargs)

    @property
    def duration(self):
        if self.logout_time:
            return self.logout_time - self.login_time
        return None


class UserActivity(models.Model):
    ACTION_CHOICES = [
        ('login', _('Login')),
        ('logout', _('Logout')),
        ('view_page', _('View Page')),
        ('update_profile', _('Update Profile')),
        ('password_change', _('Password Change')),
        ('password_reset', _('Password Reset')),
        ('failed_login', _('Failed Login Attempt')),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)
    url = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _('User Activity')
        verbose_name_plural = _('User Activities')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"


class AccessOptions(models.Model):
    """
    Model for managing comprehensive access rights to Cabinet Management module
    """
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE, 
        verbose_name=_("Group")
    )
    
    # Users management permissions
    has_access_users = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Users Management")
    )
    can_add_users = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Users")
    )
    can_edit_users = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Users")
    )
    can_delete_users = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Users")
    )
    can_export_users = models.BooleanField(
        default=False, 
        verbose_name=_("Can export Users")
    )

    # Roles management permissions
    has_access_roles = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Manage Roles")
    )
    can_add_roles = models.BooleanField(
        default=False,
        verbose_name=_("Can add Roles")
    )
    can_edit_roles = models.BooleanField(
        default=False,
        verbose_name=_("Can edit Roles")
    )
    can_delete_roles = models.BooleanField(
        default=False,
        verbose_name=_("Can delete Roles")
    )

    # Groups management permissions
    has_access_groups = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Groups Management")
    )
    can_add_groups = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Groups")
    )
    can_edit_groups = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Groups")
    )
    can_delete_groups = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Groups")
    )

    # Organization structure permissions
    has_access_org_structure = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Organization Structure")
    )
    has_access_org_chart = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to org_chart")
    )
    can_add_companies = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Companies")
    )
    can_edit_companies = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Companies")
    )
    can_delete_companies = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Companies")
    )
    can_add_departments = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Departments")
    )
    can_edit_departments = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Departments")
    )
    can_delete_departments = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Departments")
    )
    can_add_positions = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Positions")
    )
    can_edit_positions = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Positions")
    )
    can_delete_positions = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Positions")
    )

    # Site statistics permissions
    has_access_site_statistics = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Site Statistics")
    )
    can_export_statistics = models.BooleanField(
        default=False, 
        verbose_name=_("Can export Statistics")
    )
    can_view_detailed_statistics = models.BooleanField(
        default=False, 
        verbose_name=_("Can view detailed Statistics")
    )

    # Common fields
    companies = models.ManyToManyField(
        Company, 
        blank=True, 
        related_name='access_options', 
        verbose_name=_("Companies")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )

    class Meta:
        verbose_name = _("Access to Cabinet Management")
        verbose_name_plural = _("Access to Cabinet Management")
        unique_together = [('group',)]

    def __str__(self):
        return f"{self.group.name} - Users: {self.has_access_users}, Groups: {self.has_access_groups}, Org: {self.has_access_org_structure}, Stats: {self.has_access_site_statistics}"


from tinymce.models import HTMLField


class OrgStructureGuide(models.Model):
    """Base Guide for Organization Structure page. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Organization Structure Guide")
        verbose_name_plural = _("Organization Structure Guides")

    def __str__(self):
        return gettext("Organization Structure Guide")


class OrgStructureGuideTranslation(models.Model):
    """Per-country (language) translations of the Organization Structure Guide."""
    guide = models.ForeignKey(
        OrgStructureGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="org_structure_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Organization Structure Guide Translation")
        verbose_name_plural = _("Organization Structure Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class CabinetUsersGuide(models.Model):
    """Base Guide for Cabinet Users page. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Cabinet Users Guide")
        verbose_name_plural = _("Cabinet Users Guides")

    def __str__(self):
        return gettext("Cabinet Users Guide")


class CabinetUsersGuideTranslation(models.Model):
    """Per-country (language) translations of the Cabinet Users Guide."""
    guide = models.ForeignKey(
        CabinetUsersGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="cabinet_users_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Cabinet Users Guide Translation")
        verbose_name_plural = _("Cabinet Users Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class CabinetGroupsGuide(models.Model):
    """Base Guide for Cabinet Groups page. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Cabinet Groups Guide")
        verbose_name_plural = _("Cabinet Groups Guides")

    def __str__(self):
        return gettext("Cabinet Groups Guide")


class CabinetGroupsGuideTranslation(models.Model):
    """Per-country (language) translations of the Cabinet Groups Guide."""
    guide = models.ForeignKey(
        CabinetGroupsGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="cabinet_groups_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Cabinet Groups Guide Translation")
        verbose_name_plural = _("Cabinet Groups Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"