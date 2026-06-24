#  SecBoard\SecBoard\app_gdpr\models.py

from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext, get_language
from django.core.exceptions import ValidationError
from app_conf.models import Company, MailAccount
from datetime import timedelta
import json

# Map language code to country codes for translations (same pattern as app_doc/app_asset)
LANGUAGE_COUNTRY_MAP = {
    'uk': ['UA'], 'ua': ['UA'], 'ru': ['RU'], 'en': ['GB', 'US'],
    'pl': ['PL'], 'de': ['DE'], 'fr': ['FR'], 'es': ['ES'],
}


def get_country_for_current_language():
    """Return Country for current Django language, or None."""
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


class DataSubject(models.Model):
    """Суб'єкт даних (особа, дані якої обробляються)"""
    
    CONSENT_STATUS_CHOICES = [
        ('given', _('Given')),
        ('withdrawn', _('Withdrawn')),
        ('expired', _('Expired')),
        ('pending', _('Pending')),
    ]
    
    # Основна інформація
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("User"),
        help_text=_("Link to system user if exists")
    )
    first_name = models.CharField(_("First Name"), max_length=100)
    last_name = models.CharField(_("Last Name"), max_length=100)
    email = models.EmailField(_("Email"), unique=True)
    phone = models.CharField(_("Phone"), max_length=20, blank=True)
    
    # GDPR специфічні поля
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Company")
    )
    consent_status = models.CharField(
        _("Consent Status"),
        max_length=20,
        choices=CONSENT_STATUS_CHOICES,
        default='pending'
    )
    data_retention_period_days = models.IntegerField(
        _("Data Retention Period (days)"),
        default=365,
        help_text=_("Number of days to retain data after last activity")
    )
    last_activity_date = models.DateTimeField(
        _("Last Activity Date"),
        auto_now=True
    )
    deletion_scheduled_date = models.DateField(
        _("Deletion Scheduled Date"),
        null=True,
        blank=True,
        help_text=_("Date when data is scheduled for deletion")
    )
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    is_anonymized = models.BooleanField(_("Is Anonymized"), default=False)
    
    class Meta:
        verbose_name = _("Data Subject")
        verbose_name_plural = _("Data Subjects")
        ordering = ['-created_date']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    def calculate_deletion_date(self):
        """Розрахунок дати видалення на основі періоду утримання"""
        if self.last_activity_date and self.data_retention_period_days:
            return (self.last_activity_date + timedelta(days=self.data_retention_period_days)).date()
        return None


class ConsentRecord(models.Model):
    """Запис згоди на обробку персональних даних"""
    
    CONSENT_TYPE_CHOICES = [
        ('registration', _('Registration')),
        ('marketing', _('Marketing')),
        ('profiling', _('Profiling')),
        ('third_party_sharing', _('Third Party Sharing')),
        ('analytics', _('Analytics')),
        ('cookies', _('Cookies')),
    ]
    
    data_subject = models.ForeignKey(
        DataSubject,
        on_delete=models.CASCADE,
        related_name='consents',
        verbose_name=_("Data Subject")
    )
    consent_type = models.CharField(
        _("Consent Type"),
        max_length=50,
        choices=CONSENT_TYPE_CHOICES
    )
    consent_text = models.TextField(
        _("Consent Text"),
        help_text=_("Full text of consent that was presented to the user")
    )
    
    # Дати та статус
    given_date = models.DateTimeField(_("Given Date"), auto_now_add=True)
    withdrawn_date = models.DateTimeField(_("Withdrawn Date"), null=True, blank=True)
    expiration_date = models.DateField(
        _("Expiration Date"),
        null=True,
        blank=True,
        help_text=_("Date when consent expires and needs renewal")
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    
    # Технічні деталі
    ip_address = models.GenericIPAddressField(_("IP Address"), null=True, blank=True)
    user_agent = models.TextField(_("User Agent"), blank=True)
    consent_method = models.CharField(
        _("Consent Method"),
        max_length=50,
        default='web_form',
        help_text=_("How consent was given (web_form, email, paper, etc.)")
    )
    
    # Версія згоди
    consent_version = models.CharField(
        _("Consent Version"),
        max_length=20,
        default='1.0',
        help_text=_("Version of the consent text")
    )
    
    class Meta:
        verbose_name = _("Consent Record")
        verbose_name_plural = _("Consent Records")
        ordering = ['-given_date']
    
    def __str__(self):
        status = _("Active") if self.is_active else _("Withdrawn")
        return f"{self.data_subject.email} - {self.get_consent_type_display()} ({status})"
    
    def withdraw(self):
        """Відкликання згоди"""
        self.is_active = False
        self.withdrawn_date = timezone.now()
        self.save()


class DataProcessingActivity(models.Model):
    """Діяльність з обробки персональних даних (Article 30 GDPR). Name/description/purpose: default + Translations per country."""

    LEGAL_BASIS_CHOICES = [
        ('consent', _('Consent')),
        ('contract', _('Contract')),
        ('legal_obligation', _('Legal Obligation')),
        ('vital_interests', _('Vital Interests')),
        ('public_task', _('Public Task')),
        ('legitimate_interests', _('Legitimate Interests')),
    ]

    # Default (English) – for other languages use DataProcessingActivityTranslation inline
    name = models.CharField(
        _("Activity Name"),
        max_length=200,
        blank=True,
        help_text=_("Default name (e.g. English). For other languages use Translations inline.")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Default description. For other languages use Translations inline.")
    )
    purpose = models.TextField(
        _("Purpose"),
        blank=True,
        help_text=_("Default purpose. For other languages use Translations inline.")
    )

    # Категорії даних
    data_categories = models.TextField(
        _("Data Categories"),
        help_text=_("Types of personal data processed (JSON format)")
    )
    data_subjects_categories = models.TextField(
        _("Data Subjects Categories"),
        help_text=_("Categories of data subjects (employees, customers, etc.)")
    )
    
    # Правова підстава
    legal_basis = models.CharField(
        _("Legal Basis"),
        max_length=50,
        choices=LEGAL_BASIS_CHOICES
    )
    legal_basis_description = models.TextField(
        _("Legal Basis Description"),
        blank=True
    )
    
    # Період зберігання
    retention_period_days = models.IntegerField(
        _("Retention Period (days)"),
        help_text=_("How long data is retained")
    )
    retention_criteria = models.TextField(
        _("Retention Criteria"),
        blank=True,
        help_text=_("Criteria for determining retention period")
    )
    
    # Обробники даних (треті сторони)
    processors = models.TextField(
        _("Data Processors"),
        blank=True,
        help_text=_("Third parties that process data (JSON format)")
    )
    
    # Передача даних
    international_transfers = models.BooleanField(
        _("International Data Transfers"),
        default=False
    )
    transfer_safeguards = models.TextField(
        _("Transfer Safeguards"),
        blank=True,
        help_text=_("Safeguards for international transfers")
    )
    
    # Технічні та організаційні заходи
    security_measures = models.TextField(
        _("Security Measures"),
        help_text=_("Technical and organizational security measures")
    )
    
    # Зв'язки
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_("Company")
    )
    responsible_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Responsible Person")
    )
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    
    class Meta:
        verbose_name = _("Data Processing Activity")
        verbose_name_plural = _("Data Processing Activities")
        ordering = ['name']

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def get_name(self, lang=None):
        """Localized name from DataProcessingActivityTranslation (current country or lang), else name or first translation."""
        country = self._country_for_lang(lang) if lang else get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except DataProcessingActivityTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.name_local:
            return fallback.name_local
        return self.name or ''

    def get_description(self, lang=None):
        """Localized description from DataProcessingActivityTranslation, else description or first translation."""
        country = self._country_for_lang(lang) if lang else get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except DataProcessingActivityTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.description:
            return fallback.description
        return self.description or ''

    def get_purpose(self, lang=None):
        """Localized purpose from DataProcessingActivityTranslation, else purpose or first translation."""
        country = self._country_for_lang(lang) if lang else get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.purpose:
                    return t.purpose
            except DataProcessingActivityTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.purpose:
            return fallback.purpose
        return self.purpose or ''

    def __str__(self):
        return self.get_name() or self.name or ''


class DataProcessingActivityTranslation(models.Model):
    """Translations of activity name, description, purpose per country."""
    activity = models.ForeignKey(
        DataProcessingActivity,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Data Processing Activity")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='data_processing_activity_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Activity Name (local)"),
        max_length=200,
        blank=True,
        help_text=_("Activity name in country's language")
    )
    description = models.TextField(_("Description"), blank=True)
    purpose = models.TextField(_("Purpose"), blank=True)

    class Meta:
        verbose_name = _("Data Processing Activity Translation")
        verbose_name_plural = _("Data Processing Activity Translations")
        unique_together = [['activity', 'country']]
        ordering = ['country__name']

    def __str__(self):
        return f"{self.activity.name or self.name_local} - {self.country.name}: {self.name_local[:50] if self.name_local else ''}"


class DataBreachIncident(models.Model):
    """Інцидент витоку/порушення безпеки персональних даних"""
    
    SEVERITY_CHOICES = [
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('critical', _('Critical')),
    ]
    
    STATUS_CHOICES = [
        ('detected', _('Detected')),
        ('investigating', _('Investigating')),
        ('contained', _('Contained')),
        ('resolved', _('Resolved')),
        ('reported', _('Reported to Authority')),
    ]
    
    # Основна інформація
    incident_number = models.CharField(
        _("Incident Number"),
        max_length=50,
        unique=True,
        help_text=_("Unique incident identifier")
    )
    title = models.CharField(_("Incident Title"), max_length=200)
    description = models.TextField(_("Description"))
    
    # Дати
    incident_date = models.DateTimeField(
        _("Incident Date"),
        help_text=_("When the breach occurred")
    )
    discovery_date = models.DateTimeField(
        _("Discovery Date"),
        help_text=_("When the breach was discovered")
    )
    notification_deadline = models.DateTimeField(
        _("Notification Deadline"),
        null=True,
        blank=True,
        help_text=_("72 hours from discovery (GDPR requirement)")
    )
    
    # Постраждалі дані
    affected_subjects_count = models.IntegerField(
        _("Affected Subjects Count"),
        default=0
    )
    data_types_affected = models.TextField(
        _("Data Types Affected"),
        help_text=_("Types of personal data involved in the breach")
    )
    
    # Серйозність та статус
    severity = models.CharField(
        _("Severity"),
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='medium'
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='detected'
    )
    
    # Заходи реагування
    immediate_actions = models.TextField(
        _("Immediate Actions Taken"),
        blank=True
    )
    mitigation_actions = models.TextField(
        _("Mitigation Actions"),
        blank=True
    )
    preventive_measures = models.TextField(
        _("Preventive Measures"),
        blank=True,
        help_text=_("Measures to prevent future breaches")
    )
    
    # Повідомлення
    reported_to_authority = models.BooleanField(
        _("Reported to Authority"),
        default=False
    )
    authority_report_date = models.DateTimeField(
        _("Authority Report Date"),
        null=True,
        blank=True
    )
    subjects_notified = models.BooleanField(
        _("Subjects Notified"),
        default=False
    )
    subjects_notification_date = models.DateTimeField(
        _("Subjects Notification Date"),
        null=True,
        blank=True
    )
    
    # Зв'язки
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_("Company")
    )
    reported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reported_breaches',
        verbose_name=_("Reported By")
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_breaches',
        verbose_name=_("Assigned To")
    )
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Data Breach Incident")
        verbose_name_plural = _("Data Breach Incidents")
        ordering = ['-incident_date']
    
    def __str__(self):
        return f"{self.incident_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Автоматично генерувати incident_number якщо не встановлено
        if not self.incident_number:
            from datetime import datetime
            current_year = datetime.now().year
            # Формат: BREACH-YYYY-NNNN
            last_incident = DataBreachIncident.objects.filter(
                incident_number__startswith=f'BREACH-{current_year}-'
            ).order_by('-incident_number').first()
            
            if last_incident:
                # Витягуємо номер з останнього інциденту
                try:
                    last_number = int(last_incident.incident_number.split('-')[-1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1
            
            self.incident_number = f'BREACH-{current_year}-{next_number:04d}'
        
        # Автоматично розрахувати deadline для повідомлення (72 години)
        if not self.notification_deadline and self.discovery_date:
            self.notification_deadline = self.discovery_date + timedelta(hours=72)
        super().save(*args, **kwargs)
    
    def is_notification_overdue(self):
        """Перевірка, чи пропущено deadline для повідомлення"""
        if self.notification_deadline and not self.reported_to_authority:
            return timezone.now() > self.notification_deadline
        return False


class DataSubjectRequest(models.Model):
    """Запит суб'єкта даних (DSR - Data Subject Request)"""
    
    REQUEST_TYPE_CHOICES = [
        ('access', _('Right to Access')),
        ('rectification', _('Right to Rectification')),
        ('erasure', _('Right to Erasure (Right to be Forgotten)')),
        ('restriction', _('Right to Restriction of Processing')),
        ('portability', _('Right to Data Portability')),
        ('object', _('Right to Object')),
        ('automated_decision', _('Rights related to Automated Decision Making')),
    ]
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('rejected', _('Rejected')),
        ('extended', _('Extended (30+60 days)')),
    ]
    
    # Основна інформація
    request_number = models.CharField(
        _("Request Number"),
        max_length=50,
        unique=True
    )
    request_type = models.CharField(
        _("Request Type"),
        max_length=50,
        choices=REQUEST_TYPE_CHOICES
    )
    data_subject = models.ForeignKey(
        DataSubject,
        on_delete=models.CASCADE,
        related_name='dsr_requests',
        verbose_name=_("Data Subject")
    )
    
    # Опис запиту
    request_description = models.TextField(
        _("Request Description"),
        help_text=_("Detailed description of the request")
    )
    
    # Дати та терміни
    request_date = models.DateTimeField(_("Request Date"), auto_now_add=True)
    due_date = models.DateField(
        _("Due Date"),
        help_text=_("Must be completed within 30 days (GDPR)")
    )
    extended_due_date = models.DateField(
        _("Extended Due Date"),
        null=True,
        blank=True,
        help_text=_("Can be extended by 60 days in complex cases")
    )
    completion_date = models.DateTimeField(
        _("Completion Date"),
        null=True,
        blank=True
    )
    
    # Статус та обробка
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_dsr',
        verbose_name=_("Assigned To")
    )
    
    # Відповідь
    response_text = models.TextField(
        _("Response"),
        blank=True
    )
    response_sent_date = models.DateTimeField(
        _("Response Sent Date"),
        null=True,
        blank=True
    )
    
    # Причина відмови (якщо застосовно)
    rejection_reason = models.TextField(
        _("Rejection Reason"),
        blank=True
    )
    
    # Зв'язки
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_("Company")
    )
    
    # Технічні деталі
    request_source = models.CharField(
        _("Request Source"),
        max_length=50,
        default='email',
        help_text=_("How the request was received (email, portal, phone, etc.)")
    )
    verification_method = models.CharField(
        _("Verification Method"),
        max_length=100,
        blank=True,
        help_text=_("How identity was verified")
    )
    is_verified = models.BooleanField(_("Is Verified"), default=False)
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Data Subject Request")
        verbose_name_plural = _("Data Subject Requests")
        ordering = ['-request_date']
    
    def __str__(self):
        return f"{self.request_number} - {self.get_request_type_display()} ({self.data_subject.email})"
    
    def save(self, *args, **kwargs):
        # Автоматично генерувати request_number якщо не встановлено
        if not self.request_number:
            from datetime import datetime
            current_year = datetime.now().year
            # Формат: DSR-YYYY-NNNN
            last_request = DataSubjectRequest.objects.filter(
                request_number__startswith=f'DSR-{current_year}-'
            ).order_by('-request_number').first()

            if last_request:
                # Витягуємо номер з останнього запиту
                try:
                    last_number = int(last_request.request_number.split('-')[-1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1

            self.request_number = f'DSR-{current_year}-{next_number:04d}'
        
        # Автоматично встановити due_date (30 днів від запиту)
        if not self.due_date:
            self.due_date = (timezone.now() + timedelta(days=30)).date()
        super().save(*args, **kwargs)
    
    def is_overdue(self):
        """Перевірка, чи прострочено запит"""
        if self.status not in ['completed', 'rejected']:
            due = self.extended_due_date if self.extended_due_date else self.due_date
            return timezone.now().date() > due
        return False
    
    def extend_deadline(self, additional_days=60):
        """Продовжити термін виконання"""
        if not self.extended_due_date:
            self.extended_due_date = self.due_date + timedelta(days=additional_days)
            self.status = 'extended'
            self.save()


class DataRetentionPolicy(models.Model):
    """Політика утримання персональних даних. Name/description: default + DataRetentionPolicyTranslation per country."""

    DELETION_METHOD_CHOICES = [
        ('deletion', _('Permanent Deletion')),
        ('anonymization', _('Anonymization')),
        ('pseudonymization', _('Pseudonymization')),
        ('archival', _('Secure Archival')),
    ]

    name = models.CharField(
        _("Policy Name"),
        max_length=200,
        blank=True,
        help_text=_("Default name (e.g. English). For other languages use Translations inline.")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Default description. For other languages use Translations inline.")
    )

    # Категорія даних
    data_category = models.CharField(
        _("Data Category"),
        max_length=100,
        help_text=_("Category of data this policy applies to")
    )
    
    # Період утримання
    retention_period_days = models.IntegerField(
        _("Retention Period (days)"),
        help_text=_("Number of days to retain data")
    )
    
    # Метод видалення
    deletion_method = models.CharField(
        _("Deletion Method"),
        max_length=30,
        choices=DELETION_METHOD_CHOICES,
        default='deletion'
    )
    
    # Правова підстава для утримання
    legal_basis = models.TextField(
        _("Legal Basis for Retention"),
        help_text=_("Legal reason for retaining data for this period")
    )
    
    # Автоматизація
    auto_apply = models.BooleanField(
        _("Automatically Apply"),
        default=False,
        help_text=_("Automatically apply this policy")
    )
    
    # Зв'язки
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_("Company")
    )
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    
    class Meta:
        verbose_name = _("Data Retention Policy")
        verbose_name_plural = _("Data Retention Policies")
        ordering = ['name']

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def get_name(self, lang=None):
        """Localized name from DataRetentionPolicyTranslation (current country or lang), else name or first translation."""
        country = self._country_for_lang(lang) if lang else get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except DataRetentionPolicyTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.name_local:
            return fallback.name_local
        return self.name or ''

    def get_description(self, lang=None):
        """Localized description from DataRetentionPolicyTranslation, else description or first translation."""
        country = self._country_for_lang(lang) if lang else get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except DataRetentionPolicyTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.description:
            return fallback.description
        return self.description or ''

    def __str__(self):
        return f"{self.get_name() or self.name} ({self.retention_period_days} days)"


class DataRetentionPolicyTranslation(models.Model):
    """Translations of policy name and description per country."""
    policy = models.ForeignKey(
        DataRetentionPolicy,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Data Retention Policy")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='data_retention_policy_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Policy Name (local)"),
        max_length=200,
        blank=True,
        help_text=_("Policy name in country's language")
    )
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        verbose_name = _("Data Retention Policy Translation")
        verbose_name_plural = _("Data Retention Policy Translations")
        unique_together = [['policy', 'country']]
        ordering = ['country__name']

    def __str__(self):
        return f"{self.policy.name or self.name_local} - {self.country.name}: {self.name_local[:50] if self.name_local else ''}"


class DPIAAssessment(models.Model):
    """DPIA - Data Protection Impact Assessment (Оцінка впливу на захист даних)"""
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('in_review', _('In Review')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('requires_revision', _('Requires Revision')),
    ]
    
    RISK_LEVEL_CHOICES = [
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('very_high', _('Very High')),
    ]
    
    # Основна інформація
    assessment_number = models.CharField(
        _("Assessment Number"),
        max_length=50,
        unique=True
    )
    project_name = models.CharField(_("Project/System Name"), max_length=200)
    project_description = models.TextField(_("Project Description"))
    
    # Обробка даних
    processing_description = models.TextField(
        _("Description of Processing"),
        help_text=_("Detailed description of data processing activities")
    )
    data_types = models.TextField(
        _("Types of Data"),
        help_text=_("Types of personal data to be processed")
    )
    data_subjects = models.TextField(
        _("Data Subjects"),
        help_text=_("Categories of data subjects")
    )
    
    # Необхідність та пропорційність
    necessity_assessment = models.TextField(
        _("Necessity Assessment"),
        help_text=_("Why processing is necessary")
    )
    proportionality_assessment = models.TextField(
        _("Proportionality Assessment"),
        help_text=_("Is the processing proportionate to the purpose?")
    )
    
    # Ризики
    risks_identified = models.TextField(
        _("Risks Identified"),
        help_text=_("Identified risks to data subjects")
    )
    overall_risk_level = models.CharField(
        _("Overall Risk Level"),
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default='medium'
    )
    
    # Заходи безпеки
    mitigation_measures = models.TextField(
        _("Mitigation Measures"),
        help_text=_("Measures to mitigate identified risks")
    )
    residual_risk_level = models.CharField(
        _("Residual Risk Level"),
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default='low'
    )
    
    # Консультації
    stakeholders_consulted = models.TextField(
        _("Stakeholders Consulted"),
        blank=True
    )
    dpo_consulted = models.BooleanField(
        _("DPO Consulted"),
        default=False,
        help_text=_("Data Protection Officer consulted")
    )
    
    # Статус та затвердження
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    approval_date = models.DateField(_("Approval Date"), null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_dpias',
        verbose_name=_("Approved By")
    )
    
    # Перегляд
    review_date = models.DateField(
        _("Review Date"),
        help_text=_("Date for next review")
    )
    
    # Зв'язки
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_("Company")
    )
    conducted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='conducted_dpias',
        verbose_name=_("Conducted By")
    )
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("DPIA Assessment")
        verbose_name_plural = _("DPIA Assessments")
        ordering = ['-created_date']
    
    def __str__(self):
        return f"{self.assessment_number} - {self.project_name}"
    
    def save(self, *args, **kwargs):
        # Автоматично генерувати assessment_number якщо не встановлено
        if not self.assessment_number:
            from datetime import datetime
            current_year = datetime.now().year
            # Формат: DPIA-YYYY-NNNN
            last_assessment = DPIAAssessment.objects.filter(
                assessment_number__startswith=f'DPIA-{current_year}-'
            ).order_by('-assessment_number').first()

            if last_assessment:
                # Витягуємо номер з останньої оцінки
                try:
                    last_number = int(last_assessment.assessment_number.split('-')[-1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1

            self.assessment_number = f'DPIA-{current_year}-{next_number:04d}'
        
        super().save(*args, **kwargs)


class GDPRAccess(models.Model):
    """Права доступу до модуля GDPR"""
    
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        verbose_name=_("Group")
    )
    
    # Data Subject Rights
    has_access_data_subjects = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Data Subjects")
    )
    can_edit_data_subjects = models.BooleanField(
        default=False,
        verbose_name=_("Can create/edit Data Subjects")
    )
    can_export_data_subjects = models.BooleanField(
        default=False,
        verbose_name=_("Can export Data Subjects data")
    )
    
    # DSR Management
    has_access_dsr = models.BooleanField(
        default=False,
        verbose_name=_("Has access to DSR Management")
    )
    can_process_dsr = models.BooleanField(
        default=False,
        verbose_name=_("Can process DSR")
    )
    can_approve_dsr = models.BooleanField(
        default=False,
        verbose_name=_("Can approve/reject DSR")
    )
    
    # Consent Management
    has_access_consents = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Consent Management")
    )
    can_manage_consents = models.BooleanField(
        default=False,
        verbose_name=_("Can manage Consents")
    )
    
    # Data Breach Management
    has_access_breach_management = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Data Breach Management")
    )
    can_edit_breaches = models.BooleanField(
        default=False,
        verbose_name=_("Can create/edit Data Breach records")
    )
    can_report_breach = models.BooleanField(
        default=False,
        verbose_name=_("Can report Data Breach")
    )
    can_investigate_breach = models.BooleanField(
        default=False,
        verbose_name=_("Can investigate Data Breach")
    )
    
    # DPIA Management
    has_access_dpia = models.BooleanField(
        default=False,
        verbose_name=_("Has access to DPIA")
    )
    can_conduct_dpia = models.BooleanField(
        default=False,
        verbose_name=_("Can conduct DPIA")
    )
    can_approve_dpia = models.BooleanField(
        default=False,
        verbose_name=_("Can approve DPIA")
    )
    
    # Compliance and Reporting
    has_access_compliance_dashboard = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Compliance Dashboard")
    )
    can_generate_reports = models.BooleanField(
        default=False,
        verbose_name=_("Can generate GDPR Reports")
    )
    
    # Activities & Policies edit permissions
    can_edit_activities = models.BooleanField(
        default=False,
        verbose_name=_("Can create/edit Data Processing Activities")
    )
    can_edit_policies = models.BooleanField(
        default=False,
        verbose_name=_("Can create/edit Data Retention Policies")
    )
    
    # Company filtering
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='gdpr_access',
        verbose_name=_("Companies")
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    
    class Meta:
        verbose_name = _("GDPR Access")
        verbose_name_plural = _("GDPR Access")
        unique_together = [('group',)]
    
    def __str__(self):
        return f"{self.group.name} - GDPR Access"


class GDPRGuide(models.Model):
    """
    Model for managing downloadable GDPR resources and templates.
    These resources are displayed in the GDPR Implementation Guide.
    """
    CATEGORY_CHOICES = [
        ('checklist', _('Checklist')),
        ('template', _('Template')),
        ('email', _('Email Template')),
        ('form', _('Form')),
        ('guide', _('Guide Document')),
        ('other', _('Other')),
    ]
    
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('docx', 'DOCX'),
        ('xlsx', 'XLSX'),
        ('txt', 'TXT'),
        ('zip', 'ZIP'),
        ('other', 'Other'),
    ]
    
    title = models.CharField(
        max_length=255,
        verbose_name=_("Title")
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Brief description of the resource")
    )
    
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='other',
        verbose_name=_("Category")
    )
    
    file = models.FileField(
        upload_to='gdpr_resources/%Y/%m/',
        verbose_name=_("File"),
        help_text=_("Upload the resource file")
    )
    
    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        default='pdf',
        verbose_name=_("File Type")
    )
    
    resource_id = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_("Resource ID"),
        help_text=_("Unique identifier for this resource (e.g., 'gdpr-implementation-checklist')")
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Show this resource in the downloads section")
    )
    
    order = models.IntegerField(
        default=0,
        verbose_name=_("Order"),
        help_text=_("Display order (lower numbers appear first)")
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gdpr_resources_created',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("GDPR Guide Resource")
        verbose_name_plural = _("GDPR Guide Resources")
        ordering = ['category', 'order', 'title']
    
    def __str__(self):
        return f"{self.get_category_display()} - {self.title}"
    
    def get_file_icon(self):
        """Return FontAwesome icon class based on file type"""
        icons = {
            'pdf': 'fas fa-file-pdf text-danger',
            'docx': 'fas fa-file-word text-primary',
            'xlsx': 'fas fa-file-excel text-success',
            'txt': 'fas fa-envelope text-info',
            'zip': 'fas fa-file-archive text-warning',
            'other': 'fas fa-file text-secondary',
        }
        return icons.get(self.file_type, icons['other'])
    
    def get_badge_class(self):
        """Return Bootstrap badge class based on category"""
        badges = {
            'checklist': 'bg-primary',
            'template': 'bg-success',
            'email': 'bg-info',
            'form': 'bg-warning',
            'guide': 'bg-secondary',
            'other': 'bg-light text-dark',
        }
        return badges.get(self.category, badges['other'])


from tinymce.models import HTMLField


class GdprGuideContent(models.Model):
    """Base rich-text Guide for GDPR (modal). Source for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("GDPR Guide Content")
        verbose_name_plural = _("GDPR Guide Contents")

    def __str__(self):
        return gettext("GDPR Guide")


class GdprGuideContentTranslation(models.Model):
    """Per-country (language) translations of the GDPR Guide content."""
    guide = models.ForeignKey(
        GdprGuideContent,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="gdpr_guide_content_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("GDPR Guide Content Translation")
        verbose_name_plural = _("GDPR Guide Content Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"
