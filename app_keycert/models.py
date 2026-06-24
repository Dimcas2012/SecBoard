# SecBoard/app_keycert/models.py
import re
from datetime import datetime

from django.db import models, transaction
from app_conf.models import Company
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy as _lazy
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.utils.translation import get_language
import logging

# Type checking import for EncryptedCharField (not used but may be referenced by type checkers)
try:
    from encrypted_model_fields.fields import EncryptedCharField  # noqa: F401  # pyright: ignore[reportMissingImports]
except ImportError:
    pass

logger = logging.getLogger(__name__)






class Typekeycert(models.Model):
    """Key/certificate type (same pattern as Revocationstatus: name/code/description + Translations per country)."""
    name = models.CharField(
        _("Type Name"),
        max_length=100,
        blank=True,
        help_text=_("Type name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Type name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Type Code"),
        max_length=50,
        unique=True,
        blank=True,
        help_text=_("Unique code (e.g., encryption-key, ssl-cert)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    color = models.CharField(_("Color"), max_length=7, default="#000000",
                             help_text=_("Color in HEX format, e.g. #FF0000"))
    is_active = models.BooleanField(_("Is Active"), default=True)

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:50]

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '').strip()
            self.code = self._slugify_code(base)
            existing = set(
                Typekeycert.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else Typekeycert.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (Typekeycert.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'typekeycert-{self.pk or next_id}'
        super().save(*args, **kwargs)

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def get_name_by_language(self, language=None):
        country = self._country_for_lang(language)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except TypekeycertTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or ''

    def get_description_by_language(self, language=None):
        country = self._country_for_lang(language)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except TypekeycertTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_name(self):
        """Get localized name: translation for current country, else get_name_by_language."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except TypekeycertTranslation.DoesNotExist:
                pass
        if self.name or self.name_local:
            lang = (get_language() or '')[:2].lower()
            if lang == 'en':
                return self.name or self.name_local
            return self.name_local or self.name
        return self.get_name_by_language()

    def get_description(self):
        """Get localized description: translation for current country, else get_description_by_language."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.description:
                    return translation.description
            except TypekeycertTranslation.DoesNotExist:
                pass
        if self.description:
            return self.description
        return self.get_description_by_language()

    def get_local_name(self, country):
        """Get localized name for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except TypekeycertTranslation.DoesNotExist:
            return self.name_local or self.name or self.get_name_by_language()

    def get_local_description(self, country):
        """Get localized description for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.description or self.description or ''
        except TypekeycertTranslation.DoesNotExist:
            return self.description or self.get_description_by_language()

    def __str__(self):
        return self.get_name() or self.name or self.name_local or ''

    class Meta:
        verbose_name = _("Key/Certificate Type")
        verbose_name_plural = _("Key/Certificate Types")


class TypekeycertTranslation(models.Model):
    """Translations of key/certificate type for different countries (same as RevocationstatusTranslation)."""
    typekeycert = models.ForeignKey(
        Typekeycert,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Key/Certificate Type")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='typekeycert_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Type name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )

    class Meta:
        verbose_name = _("Key/Certificate Type Translation")
        verbose_name_plural = _("Key/Certificate Type Translations")
        unique_together = ['typekeycert', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.typekeycert.name or self.name_local} - {self.country.name}: {self.name_local}"

# Map language code to country codes for translations (same pattern as app_doc / app_incident)
LANGUAGE_COUNTRY_MAP = {
    'uk': ['UA'],
    'ru': ['RU'],
    'en': ['GB', 'US'],
    'pl': ['PL'],
    'de': ['DE'],
    'fr': ['FR'],
    'es': ['ES'],
    'it': ['IT'],
    'pt': ['PT'],
    'nl': ['NL'],
    'cs': ['CZ'],
    'sk': ['SK'],
    'ro': ['RO'],
    'bg': ['BG'],
    'lt': ['LT'],
}


def get_country_for_current_language():
    """Return Country for current Django language, or None if not found."""
    from app_conf.models import Country
    language_code = (get_language() or '')[:2].lower()
    if not language_code:
        return None
    for country_code in LANGUAGE_COUNTRY_MAP.get(language_code, []):
        try:
            return Country.objects.get(code__iexact=country_code)
        except Country.DoesNotExist:
            continue
    return None


class Revocationstatus(models.Model):
    """Revocation status (same pattern as DocStatus/Classification: name/code/description + Translations per country)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Status Name"),
        max_length=100,
        blank=True,
        help_text=_("Status name, default: English (En). E.g. Active, Revoked. For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Status name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Status Code"),
        max_length=50,
        unique=True,
        blank=True,
        help_text=_("Unique code (e.g., active, revoked)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    color = models.CharField(_("Color"), max_length=7, default="#000000",
                             help_text=_("Color in HEX format, e.g. #FF0000"))
    is_active = models.BooleanField(_("Is Active"), default=True)

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:50]

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '').strip()
            self.code = self._slugify_code(base)
            existing = set(
                Revocationstatus.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else Revocationstatus.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (Revocationstatus.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'revstatus-{self.pk or next_id}'
        super().save(*args, **kwargs)

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def get_name_by_language(self, language=None):
        country = self._country_for_lang(language)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except RevocationstatusTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or ''

    def get_description_by_language(self, language=None):
        country = self._country_for_lang(language)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except RevocationstatusTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_name(self):
        """Get localized name: translation for current country, else get_name_by_language (same as DocStatus/Classification)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except RevocationstatusTranslation.DoesNotExist:
                pass
        if self.name or self.name_local:
            lang = (get_language() or '')[:2].lower()
            if lang == 'en':
                return self.name or self.name_local
            return self.name_local or self.name
        return self.get_name_by_language()

    def get_description(self):
        """Get localized description: translation for current country, else get_description_by_language."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.description:
                    return translation.description
            except RevocationstatusTranslation.DoesNotExist:
                pass
        if self.description:
            return self.description
        return self.get_description_by_language()

    def get_local_name(self, country):
        """Get localized name for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except RevocationstatusTranslation.DoesNotExist:
            return self.name_local or self.name or self.get_name_by_language()

    def get_local_description(self, country):
        """Get localized description for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.description or self.description or ''
        except RevocationstatusTranslation.DoesNotExist:
            return self.description or self.get_description_by_language()

    def __str__(self):
        return self.get_name() or self.name or self.name_local or ''

    class Meta:
        verbose_name = _("Revocation Status")
        verbose_name_plural = _("Revocation Status")


class RevocationstatusTranslation(models.Model):
    """Translations of revocation status for different countries (same as DocStatus/Classification Translations)."""
    revocationstatus = models.ForeignKey(
        Revocationstatus,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Revocation Status")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='revocationstatus_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Status name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )

    class Meta:
        verbose_name = _("Revocation Status Translation")
        verbose_name_plural = _("Revocation Status Translations")
        unique_together = ['revocationstatus', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.revocationstatus.name or self.name_local} - {self.country.name}: {self.name_local}"


class GenKeycertInfo(models.Model):
    key_certificate = models.OneToOneField('KeyCertificates', on_delete=models.CASCADE, related_name='general_info')
    organization_name = models.CharField(_("Organization Name"), max_length=255)
    date_created = models.DateTimeField(_("Date Created"))
    last_updated = models.DateTimeField(_("Last Updated"), null=True, blank=True)
    version = models.CharField(_("Version"), max_length=50)
    maintainer_name = models.CharField(_("Maintainer Name"), max_length=255)
    maintainer_contact = models.CharField(_("Maintainer Contact"), max_length=255)

    def __str__(self):
        return f"General Info for {self.key_certificate.key_cert_num}"

    class Meta:
        verbose_name = _("General Key/Certificate Info")
        verbose_name_plural = _("General Key/Certificate Info")


class KeycertOwner(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    department = models.CharField(_("Department/Position"), max_length=100)
    email = models.EmailField(_("Email"))
    phone = models.CharField(_("Phone"), max_length=20)
    notes = models.TextField(_("Notes"), blank=True)

    def __str__(self):
        return f"{self.name} - {self.department}"

    class Meta:
        verbose_name = _("Key/Certificate Owner")
        verbose_name_plural = _("Key/Certificate Owners")



class KeyCertificates(models.Model):
    """Model for storing information about keys and certificates."""
    id = models.AutoField(primary_key=True)
    company = models.ForeignKey('app_conf.Company', on_delete=models.CASCADE, verbose_name=_("Company"))
    key_cert_num = models.CharField(max_length=50, verbose_name=_("Key/Cert Number"))
    cert_hash = models.CharField(max_length=128, blank=True, verbose_name=_("Certificate/Key Hash"))
    type_key_sert = models.ForeignKey('Typekeycert', on_delete=models.SET_NULL, null=True, blank=True)
    purpose = models.TextField(verbose_name=_("Purpose"))
    location = models.CharField(max_length=255, verbose_name=_("Location"))
    owner = models.ForeignKey(KeycertOwner, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Owner"))
    owner_cabinet_user = models.ForeignKey(
        'app_cabinet.CabinetUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_key_certs',
        verbose_name=_("Owner (Cabinet user)")
    )
    access_control = models.TextField(verbose_name=_("Access Control"))
    expiry_date = models.DateField(verbose_name=_("Expiry Date"))
    revocation_status = models.ForeignKey('Revocationstatus', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    added_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='added_key_certs', verbose_name=_("Added By"))
    updated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='updated_key_certs', verbose_name=_("Updated By"))
    enable_reminder = models.BooleanField(default=False, verbose_name=_("Enable Reminder"))
    actualization_date = models.DateTimeField(_("Actualization Date"), null=True, blank=True)
    actualized_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actualized_key_certs',
        verbose_name=_("Actualized By")
    )

    def create_reminder(self, reminder_type, reminder_days=None, reminder_date=None):
        return Reminder.objects.create(
            key_certificate=self,
            reminder_type=reminder_type,
            reminder_days=reminder_days,
            reminder_date=reminder_date
        )

    def update_reminder(self, reminder_type, reminder_days=None, reminder_date=None):
        reminder, created = Reminder.objects.get_or_create(key_certificate=self)
        reminder.reminder_type = reminder_type
        reminder.reminder_days = reminder_days
        reminder.reminder_date = reminder_date
        reminder.save()
        return reminder

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_instance = None if is_new else KeyCertificates.objects.get(pk=self.pk)

        # Save the instance first
        super().save(*args, **kwargs)

        # Create history entry
        if is_new:
            KeyCertHistory.objects.create(
                key_certificate=self,
                action="created",
                action_by=self.added_by,
                details="Key/Certificate created"
            )
        else:
            changes = []
            # Compare old and new values
            fields_to_track = [
                'company', 'key_cert_num', 'type_key_sert', 'purpose',
                'location', 'owner', 'owner_cabinet_user', 'access_control', 'expiry_date',
                'revocation_status', 'notes', 'cert_hash'
            ]

            for field in fields_to_track:
                old_value = getattr(old_instance, field)
                new_value = getattr(self, field)
                if old_value != new_value:
                    changes.append(f"{field}: {old_value} → {new_value}")

            if changes:
                KeyCertHistory.objects.create(
                    key_certificate=self,
                    action="modified",
                    action_by=self.updated_by,
                    details="\n".join(changes)
                )

    class Meta:
        verbose_name = _("Key/Certificate")
        verbose_name_plural = _("Keys and Certificates")

    def __str__(self):
        return f"{self.key_cert_num} - {self.type_key_sert}"

class KeyCertHistory(models.Model):
    # Action types constants
    ACTION_CREATED = 'created'
    ACTION_MODIFIED = 'modified'
    ACTION_DELETED = 'deleted'
    ACTION_REMINDER_ATTEMPT = 'reminder_attempt'
    ACTION_REMINDER_SENT = 'reminder_sent'
    ACTION_REMINDER_FAILED = 'reminder_failed'
    ACTION_MANUAL_REMINDER_REQUESTED = 'manual_reminder_requested'
    ACTION_MANUAL_REMINDER_SENT = 'manual_reminder_sent'
    ACTION_MANUAL_REMINDER_FAILED = 'manual_reminder_failed'

    ACTION_CHOICES = [
        (ACTION_CREATED, _('Created')),
        (ACTION_MODIFIED, _('Modified')),
        (ACTION_DELETED, _('Deleted')),
        (ACTION_REMINDER_ATTEMPT, _('Reminder Attempt')),
        (ACTION_REMINDER_SENT, _('Reminder Sent')),
        (ACTION_REMINDER_FAILED, _('Reminder Failed')),
        (ACTION_MANUAL_REMINDER_REQUESTED, _('Manual Reminder Requested')),
        (ACTION_MANUAL_REMINDER_SENT, _('Manual Reminder Sent')),
        (ACTION_MANUAL_REMINDER_FAILED, _('Manual Reminder Failed')),
    ]

    key_certificate = models.ForeignKey(KeyCertificates, on_delete=models.CASCADE, related_name='history')
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    action_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    details = models.TextField()

    class Meta:
        verbose_name = _("Key/Certificate History")
        verbose_name_plural = _("Key/Certificate History")
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.key_certificate} - {self.get_action_display()} at {self.timestamp}"

    def get_formatted_timestamp(self):
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S')

    def get_action_by_name(self):
        if self.action_by:
            return self.action_by.get_full_name() or self.action_by.username
        return _('System')



class Reminder(models.Model):
    key_certificate = models.ForeignKey('KeyCertificates', on_delete=models.CASCADE, related_name='reminders',
                                      verbose_name=_("Key/Certificate"))
    reminder_type = models.CharField(
        max_length=10,
        choices=[('days', _('Days before expiry')), ('date', _('Specific date'))],
        verbose_name=_("Reminder Type")
    )
    reminder_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Days before expiry")
    )
    reminder_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Reminder Date")
    )
    is_sent = models.BooleanField(
        default=False,
        verbose_name=_("Is Sent")
    )
    is_cancelled = models.BooleanField(
        default=False,
        verbose_name=_("Is Cancelled")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Sent At")
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Cancelled At")
    )
    celery_task_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Celery Task ID")
    )

    class Meta:
        verbose_name = _("Reminder")
        verbose_name_plural = _("Reminders")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key_certificate', 'is_sent', 'is_cancelled']),
            models.Index(fields=['created_at']),
            models.Index(fields=['sent_at']),
        ]

    def __str__(self):
        return f"Reminder for {self.key_certificate.key_cert_num} ({self.get_status()})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if is_new:
            # Cancel existing active reminders for this certificate
            existing_active_reminders = Reminder.objects.filter(
                key_certificate=self.key_certificate,
                is_cancelled=False
            ).exists()

            if existing_active_reminders:
                with transaction.atomic():
                    Reminder.objects.filter(
                        key_certificate=self.key_certificate,
                        is_cancelled=False
                    ).update(
                        is_cancelled=True,
                        cancelled_at=timezone.now()
                    )

        # Save the current reminder
        super().save(*args, **kwargs)

        # Update the enable_reminder flag on the key_certificate
        self.key_certificate.enable_reminder = not self.is_cancelled
        self.key_certificate.save(update_fields=['enable_reminder'])

    def get_status(self):
        """Returns the basic status of the reminder."""
        if self.is_sent:
            return "Sent"
        elif self.is_cancelled:
            return "Cancelled"
        elif self.is_due():
            return "Overdue"
        else:
            return "Pending"

    def get_status_with_datetime(self):
        """Returns detailed status information including timestamp."""
        status = self.get_status()
        timestamp = None

        if status == "Sent" and self.sent_at:
            timestamp = self.sent_at.strftime('%Y-%m-%d %H:%M:%S')
        elif status == "Cancelled" and self.cancelled_at:
            timestamp = self.cancelled_at.strftime('%Y-%m-%d %H:%M:%S')
        elif status == "Overdue":
            next_date = self.get_next_reminder_date()
            if next_date:
                timestamp = next_date.strftime('%Y-%m-%d %H:%M:%S')

        return {
            'status': status,
            'timestamp': timestamp,
            'is_overdue': status == "Overdue",
            'days_remaining': self.get_days_remaining()
        }

    def get_formatted_reminder_info(self):
        """Returns formatted reminder information."""
        if self.reminder_type == 'days':
            days_text = _('days before expiry')
            return f"{self.reminder_days} {days_text}"
        elif self.reminder_type == 'date' and self.reminder_date:
            return self.reminder_date.strftime('%Y-%m-%d %H:%M:%S')
        return _("Not set")

    def get_next_reminder_date(self):
        """Calculate the next reminder date."""
        if self.is_sent or self.is_cancelled:
            return None

        if self.reminder_type == 'days':
            return self.key_certificate.expiry_date - timezone.timedelta(days=self.reminder_days)
        return self.reminder_date if self.reminder_type == 'date' else None

    def get_days_remaining(self):
        """Calculate days remaining until reminder or expiry."""
        if self.is_sent or self.is_cancelled:
            return None

        next_date = self.get_next_reminder_date()
        if not next_date:
            return None

        if isinstance(next_date, datetime):
            next_date = next_date.date()

        today = timezone.now().date()
        return (next_date - today).days

    def is_due(self):
        """Check if the reminder is due."""
        if self.is_sent or self.is_cancelled:
            return False

        next_date = self.get_next_reminder_date()
        if not next_date:
            return False

        if isinstance(next_date, datetime):
            return next_date <= timezone.now()
        return next_date <= timezone.now().date()

    def format_date(self, date_value):
        """Format a date/datetime value consistently."""
        if not date_value:
            return None
        if isinstance(date_value, datetime):
            return date_value.strftime('%Y-%m-%d %H:%M:%S')
        return date_value.strftime('%Y-%m-%d')

    def get_reminder_details(self):
        """Get comprehensive reminder details."""
        next_date = self.get_next_reminder_date()
        status_info = self.get_status_with_datetime()

        return {
            'id': self.pk,
            'type': self.reminder_type,
            'days': self.reminder_days,
            'date': self.format_date(self.reminder_date),
            'status': status_info['status'],
            'status_timestamp': status_info['timestamp'],
            'is_sent': self.is_sent,
            'is_cancelled': self.is_cancelled,
            'sent_at': self.format_date(self.sent_at),
            'cancelled_at': self.format_date(self.cancelled_at),
            'next_reminder': self.format_date(next_date),
            'days_remaining': self.get_days_remaining(),
            'created_at': self.format_date(self.created_at),
            'updated_at': self.format_date(self.updated_at),
            'celery_task_id': self.celery_task_id
        }



class AccessKeyCert(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to KeyCert"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit KeyCert"))
    show_link = models.BooleanField(default=False, verbose_name=_("Show link on index page"))
    companies = models.ManyToManyField(Company, blank=True, related_name='access_keycert', verbose_name=_("Companies"))
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Access to KeyCert")
        verbose_name_plural = _("Access to KeyCert")

    def __str__(self):
        return f"{self.group.name} - Has Access: {self.has_access}, Edit Access: {self.can_edit}, Show Link: {self.show_link}"


from tinymce.models import HTMLField


class KeyCertGuide(models.Model):
    """Base Guide for Keys/Certificates. Source content for translations."""
    base_content = HTMLField(
        _lazy("Base content"),
        blank=True,
        help_text=_lazy("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _lazy("Key/Cert Guide")
        verbose_name_plural = _lazy("Key/Cert Guides")

    def __str__(self):
        return _("Keys/Certificates Guide")


class KeyCertGuideTranslation(models.Model):
    """Per-country (language) translations of the Key/Cert Guide."""
    keycert_guide = models.ForeignKey(
        KeyCertGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_lazy("Key/Cert Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="keycert_guide_translations",
        verbose_name=_lazy("Country")
    )
    content = HTMLField(
        _lazy("Content"),
        blank=True,
        help_text=_lazy("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _lazy("Key/Cert Guide Translation")
        verbose_name_plural = _lazy("Key/Cert Guide Translations")
        unique_together = ["keycert_guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.keycert_guide} — {self.country.name}"