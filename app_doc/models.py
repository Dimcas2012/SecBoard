#  SecBoard\SecBoard\app_suib\models.py
import ssl
from datetime import datetime
from hashlib import sha256
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _, gettext
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils.translation import get_language
from django.core.files.storage import default_storage
import os
import re
import logging
from tinymce.models import HTMLField
from django.utils import timezone

from app_cabinet.models import CabinetUser

logger = logging.getLogger(__name__)

# Map language code to country codes for translations (same pattern as app_asset)
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

class DocType(models.Model):
    """Document type (same pattern as Asset Type / DocStatus: name/code/description + Translations per country)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Type Name"),
        max_length=100,
        blank=True,
        help_text=_("Type name, default: English (En). E.g. Policy, Procedure. For other languages use Translations inline.")
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
        help_text=_("Unique code (e.g., policy, procedure)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description of this type, default: English (En). For other languages use Translations inline.")
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
                DocType.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else DocType.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (DocType.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'doctype-{self.pk or next_id}'
        super().save(*args, **kwargs)

    def _country_for_lang(self, lang):
        """Return Country for language code (uk/ua->UA, en->GB, ru->RU) for use in translations."""
        from app_conf.models import Country
        code_map = {'uk': 'UA', 'ua': 'UA', 'en': 'GB', 'ru': 'RU'}
        code = code_map.get((lang or '')[:2].lower())
        if not code:
            return None
        try:
            return Country.objects.get(code=code)
        except Country.DoesNotExist:
            return None

    def get_name_by_language(self, language=None):
        if language is None:
            language = get_language()
        country = self._country_for_lang(language)
        if country:
            return self.get_local_name(country) or self.name or ''
        return self.name or self.name_local or ''

    def get_description_by_language(self, language=None):
        if language is None:
            language = get_language()
        country = self._country_for_lang(language)
        if country:
            return self.get_local_description(country) or self.description or ''
        return self.description or ''

    def get_name(self):
        """Get localized name: translation for current country, else get_name_by_language (same as Asset Type)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except DocTypeTranslation.DoesNotExist:
                pass
        return self.name or self.name_local or ''

    def get_description(self):
        """Get localized description: translation for current country, else default description."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.description:
                    return translation.description
            except DocTypeTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_local_name(self, country):
        """Get localized name for specific country (Document Type Translations only)."""
        if not country:
            return self.name or self.name_local or ''
        try:
            translation = self.translations.get(country=country)
            return translation.name_local or self.name or self.name_local or ''
        except DocTypeTranslation.DoesNotExist:
            return self.name or self.name_local or ''

    def get_local_description(self, country):
        """Get localized description for specific country (Document Type Translations only)."""
        if not country:
            return self.description or ''
        try:
            translation = self.translations.get(country=country)
            return translation.description or self.description or ''
        except DocTypeTranslation.DoesNotExist:
            return self.description or ''

    def __str__(self):
        return str(self.get_name() or _("Unnamed Document Type"))

    class Meta:
        verbose_name = _("Document Type")
        verbose_name_plural = _("Document Types")


class DocTypeTranslation(models.Model):
    """Translations of document type for different countries (same as Asset Type Translations)."""
    doc_type = models.ForeignKey(
        DocType,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Document Type")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='doc_type_translations',
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
        verbose_name = _("Document Type Translation")
        verbose_name_plural = _("Document Type Translations")
        unique_together = ['doc_type', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.doc_type.name or self.doc_type.name_local} - {self.country.name}: {self.name_local}"

class DocStatus(models.Model):
    """Document status (same pattern as Asset Type: name/code/description + Translations per country)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Status Name"),
        max_length=100,
        blank=True,
        help_text=_("Status name, default: English (En). E.g. Draft, Approved. For other languages use Translations inline.")
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
        help_text=_("Unique code (e.g., draft, approved)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description of this status, default: English (En). For other languages use Translations inline.")
    )

    color = models.CharField(_("Color"), max_length=7, default="#000000",
                             help_text=_("Color in HEX format, e.g. #FF0000"))
    sort_order = models.PositiveIntegerField(_("Sort Order"), default=0,
                                           help_text=_("Lower numbers appear first in sorting. 0 = highest priority"))
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
                DocStatus.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else DocStatus.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (DocStatus.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'docstatus-{self.pk or next_id}'
        super().save(*args, **kwargs)

    def _country_for_lang(self, lang):
        """Return Country for language code (uk/ua->UA, en->GB, ru->RU) for use in translations."""
        from app_conf.models import Country
        code_map = {'uk': 'UA', 'ua': 'UA', 'en': 'GB', 'ru': 'RU'}
        code = code_map.get((lang or '')[:2].lower())
        if not code:
            return None
        try:
            return Country.objects.get(code=code)
        except Country.DoesNotExist:
            return None

    def get_name_by_language(self, language=None):
        if language is None:
            language = get_language()
        country = self._country_for_lang(language)
        if country:
            return self.get_local_name(country) or self.name or ''
        return self.name or self.name_local or ''

    def get_description_by_language(self, language=None):
        if language is None:
            language = get_language()
        country = self._country_for_lang(language)
        if country:
            return self.get_local_description(country) or self.description or ''
        return self.description or ''

    def get_name(self):
        """Get localized name: Document Status Translations only (+ name/name_local fallback)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except DocStatusTranslation.DoesNotExist:
                pass
        return self.name or self.name_local or ''

    def get_description(self):
        """Get localized description: Document Status Translations only (+ description fallback)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.description:
                    return translation.description
            except DocStatusTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_local_name(self, country):
        """Get localized name for specific country (Document Status Translations only)."""
        if not country:
            return self.name or self.name_local or ''
        try:
            translation = self.translations.get(country=country)
            return translation.name_local or self.name or self.name_local or ''
        except DocStatusTranslation.DoesNotExist:
            return self.name or self.name_local or ''

    def get_local_description(self, country):
        """Get localized description for specific country (Document Status Translations only)."""
        if not country:
            return self.description or ''
        try:
            translation = self.translations.get(country=country)
            return translation.description or self.description or ''
        except DocStatusTranslation.DoesNotExist:
            return self.description or ''

    @classmethod
    def get_default_status(cls):
        """Get the status with highest priority (lowest sort_order)"""
        return cls.objects.filter(is_active=True).order_by('sort_order', 'id').first()

    @classmethod
    def get_statuses_by_priority(cls):
        """Get all statuses ordered by priority (sort_order)"""
        return cls.objects.filter(is_active=True).order_by('sort_order', 'id')

    def __str__(self):
        return str(self.get_name() or _("Unnamed Document Status"))

    class Meta:
        verbose_name = _("Document Status")
        verbose_name_plural = _("Document Status")
        ordering = ['sort_order', 'id']


class DocStatusTranslation(models.Model):
    """Translations of document status for different countries (same as Asset Type Translations)."""
    doc_status = models.ForeignKey(
        DocStatus,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Document Status")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='doc_status_translations',
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
        verbose_name = _("Document Status Translation")
        verbose_name_plural = _("Document Status Translations")
        unique_together = ['doc_status', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.doc_status.name or self.doc_status.name_local} - {self.country.name}: {self.name_local}"

class AccessClassification(models.Model):
    """Document access classification / security level (same pattern as DocStatus/DocType: name/code/description + Translations per country)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Classification Name"),
        max_length=100,
        blank=True,
        help_text=_("Name, default: English (En). E.g. Confidential, Public. For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Classification Code"),
        max_length=50,
        unique=True,
        blank=True,
        help_text=_("Unique code (e.g., confidential, public)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )

    color = models.CharField(_("Color"), max_length=7, default="#6c757d",
                             help_text=_("Color in HEX format, e.g. #FF0000"))
    icon = models.CharField(_("Icon"), max_length=50, default="fa-lock",
                           help_text=_("FontAwesome icon class, e.g. fa-lock, fa-shield-alt"))
    sort_order = models.PositiveIntegerField(_("Sort Order"), default=0,
                                           help_text=_("Lower numbers appear first in sorting. 0 = highest security level"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

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
                AccessClassification.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else AccessClassification.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (AccessClassification.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'accessclass-{self.pk or next_id}'
        super().save(*args, **kwargs)

    def _country_for_lang(self, lang):
        """Return first Country for language code, or None."""
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def get_name_by_language(self, language=None):
        """Get name from AccessClassificationTranslation for language's country, else name or first translation."""
        country = self._country_for_lang(language)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except AccessClassificationTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.name_local:
            return fallback.name_local
        return self.name or self.name_local or ''

    def get_description_by_language(self, language=None):
        """Get description from AccessClassificationTranslation for language's country, else description or first translation."""
        country = self._country_for_lang(language)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except AccessClassificationTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.description:
            return fallback.description
        return self.description or ''

    def get_name(self):
        """Get localized name from AccessClassificationTranslation (current country), else name or first translation."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except AccessClassificationTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.name_local:
            return fallback.name_local
        return self.name or self.name_local or ''

    def get_description(self):
        """Get localized description from AccessClassificationTranslation (current country), else description or first translation."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.description:
                    return translation.description
            except AccessClassificationTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.description:
            return fallback.description
        return self.description or ''

    def get_local_name(self, country):
        """Get localized name for specific country from AccessClassificationTranslation."""
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except AccessClassificationTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.name_local:
            return fallback.name_local
        return self.name or self.name_local or ''

    def get_local_description(self, country):
        """Get localized description for specific country from AccessClassificationTranslation."""
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.description:
                    return translation.description
            except AccessClassificationTranslation.DoesNotExist:
                pass
        fallback = self.translations.order_by('country__name').first()
        if fallback and fallback.description:
            return fallback.description
        return self.description or ''


    @classmethod
    def get_default_classification(cls):
        """Get the classification with highest priority (lowest sort_order)"""
        return cls.objects.filter(is_active=True).order_by('sort_order', 'id').first()

    @classmethod
    def get_classifications_by_priority(cls):
        """Get all active classifications ordered by priority (sort_order)"""
        return cls.objects.filter(is_active=True).order_by('sort_order', 'id')

    def __str__(self):
        return str(self.get_name() or _("Unnamed Access Classification"))

    class Meta:
        verbose_name = _("Access Classification")
        verbose_name_plural = _("Access Classifications")
        ordering = ['sort_order', 'id']


class AccessClassificationTranslation(models.Model):
    """Translations of access classification for different countries (same as DocStatus/DocType Translations)."""
    access_classification = models.ForeignKey(
        AccessClassification,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Access Classification")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='access_classification_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Classification name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )

    class Meta:
        verbose_name = _("Access Classification Translation")
        verbose_name_plural = _("Access Classification Translations")
        unique_together = ['access_classification', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.access_classification.name or self.name_local} - {self.country.name}: {self.name_local}"

class RelatedDocs(models.Model):

    name_rel_doc = models.CharField(max_length=255, verbose_name=_("Related Document Name"))
    company = models.ForeignKey('app_conf.Company', on_delete=models.SET_NULL,
                              null=True, blank=True, verbose_name=_("Company"))
    access_classification = models.ForeignKey('AccessClassification', on_delete=models.SET_NULL, null=True, blank=True,
                                             verbose_name=_("Access Classification"),
                                             help_text=_("Security level / access restriction"))
    date_rel_doc = models.DateField(verbose_name=_("Related Document Date"))
    vers_rel_doc = models.CharField(max_length=50, verbose_name=_("Related Document Version"))
    vers_rel_doc_html = models.TextField(blank=True, null=True,
                                       verbose_name=_("Related Document HTML Version"))
    description_rel_doc = models.TextField(verbose_name=_("Related Document Description"))
    file_rel_doc = models.FileField(upload_to='related_documents/', blank=True, null=True,
                                  verbose_name=_("Related Document File"))
    status_rel_doc = models.ForeignKey('DocStatus', on_delete=models.SET_NULL, null=True, blank=True,
                                     verbose_name=_("Related Document Status"))
    groups = models.ManyToManyField('auth.Group', blank=True, related_name='related_docs',
                                  verbose_name=_("Groups"))

    class Meta:
        verbose_name = _("Related Document")
        verbose_name_plural = _("Related Documents")
        ordering = ['status_rel_doc__sort_order', '-date_rel_doc', 'name_rel_doc']

    def __str__(self):
        return self.name_rel_doc


def validate_file_size(value):
    """Validate file size (max 10MB)"""
    filesize = value.size
    if filesize > 10 * 1024 * 1024:  # 10MB
        raise ValidationError(_("Maximum file size is 10MB"))


def document_file_path(instance, filename):
    """Generate file path for document files"""
    # Get file extension
    ext = filename.split('.')[-1]
    # Generate new filename with timestamp
    filename = f"{instance.name_doc}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    # Return the path
    return os.path.join('register_docs', filename)


class RegisterDocs(models.Model):
    name_doc = models.CharField(max_length=255, verbose_name=_("Document Name"), db_index=True,
                                help_text=_("Enter the name of the document"))
    company = models.ForeignKey('app_conf.Company', on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name=_("Company"))
    type_doc = models.ForeignKey('DocType', on_delete=models.SET_NULL, null=True, verbose_name=_("Document Type"))
    access_classification = models.ForeignKey('AccessClassification', on_delete=models.SET_NULL, null=True, blank=True,
                                             verbose_name=_("Access Classification"),
                                             help_text=_("Security level / access restriction"))
    vers_doc = models.CharField(max_length=50, verbose_name=_("Document Version"))
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='next_versions',
        verbose_name=_("Previous Document"),
        help_text=_("Previous Document Registry entry")
    )
    vers_doc_html = HTMLField(blank=True, null=True, verbose_name='Document HTML Version')
    date_doc = models.DateField(verbose_name=_("Document Date"), default=timezone.now)
    description = models.TextField(verbose_name=_("Description"))
    version_history = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Version history"),
        help_text=_("History of changes")
    )
    file_doc = models.FileField(
        upload_to=document_file_path,
        null=True,
        blank=True,
        verbose_name=_("Document File"),
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt']),
            validate_file_size
        ]
    )
    groups = models.ManyToManyField('auth.Group', blank=True, related_name='register_docs',
                                    verbose_name=_("Groups"))
    allowed_users = models.ManyToManyField(
        User, blank=True, related_name='register_docs_allowed',
        verbose_name=_("Cabinet users (access)"),
        help_text=_("Additional users with access to this document (Cabinet users)")
    )
    related_docs = models.ManyToManyField('RelatedDocs', blank=True, verbose_name=_("Related Documents"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_documents', verbose_name=_("Created By"))
    updated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='updated_documents', verbose_name=_("Updated By"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    document_hash = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Document Hash"))
    is_approved = models.BooleanField(default=False, verbose_name=_("Is Approved"))
    status_doc = models.ForeignKey('DocStatus', on_delete=models.SET_NULL, null=True, verbose_name=_("Document Status"))

    class Meta:
        verbose_name = _("Register Document")
        verbose_name_plural = _("Register Documents")
        ordering = ['status_doc__sort_order', '-date_doc', 'name_doc']
        indexes = [
            models.Index(fields=['name_doc']),
            models.Index(fields=['date_doc']),
            models.Index(fields=['is_active']),
            models.Index(fields=['document_hash']),
            models.Index(fields=['is_approved'])
        ]

    def __str__(self):
        return f"{self.name_doc} ({self.vers_doc})"

    def update_approval_status(self):
        """Update document approval status based on current approvals and hash"""
        try:
            # Get all approvers
            all_approvers = set(self.documentapproval_set.values_list('approver_id', flat=True))

            # Get current valid approved approvals (matching current hash)
            approved_approvers = set(
                self.documentapproval_set.filter(
                    status='approved',
                    document_hash=self.document_hash
                ).values_list('approver_id', flat=True)
            )

            # Document is approved only if all required approvers have approved with current hash
            was_approved = self.is_approved
            # Fix: Convert set() to boolean properly - if all_approvers is empty, return False
            # Otherwise, check if all approvers have approved
            if not all_approvers:
                self.is_approved = False
            else:
                self.is_approved = (all_approvers == approved_approvers)

            if was_approved != self.is_approved:
                logger.info(
                    f"Document {self.id} approval status changed from {was_approved} to {self.is_approved}. "
                    f"Approved: {len(approved_approvers)}/{len(all_approvers)}"
                )

            # Use update_fields to minimize database impact
            self.save(update_fields=['is_approved'])

        except Exception as e:
            logger.error(f"Error updating approval status for document {self.id}: {str(e)}", exc_info=True)
            raise

    def generate_hash(self):
        """Generate SHA-256 hash based ONLY on the file content"""
        try:
            if self.file_doc:
                # Calculate hash from file content
                file_hash = self.calculate_file_hash()
                if file_hash:
                    logger.debug(f"Generated file hash for document {self.id}: {file_hash}")
                    return file_hash

            # If no file or hash calculation failed, generate hash based on timestamp
            timestamp_hash = sha256(str(timezone.now().timestamp()).encode()).hexdigest()
            logger.debug(f"Generated timestamp hash for document {self.id}: {timestamp_hash}")
            return timestamp_hash

        except Exception as e:
            logger.error(f"Error generating hash for document {self.id}: {str(e)}", exc_info=True)
            return sha256(str(timezone.now().timestamp()).encode()).hexdigest()

    def calculate_file_hash(self):
        """Calculate hash of file content"""
        if not self.file_doc:
            return None

        try:
            hasher = sha256()
            if hasattr(self.file_doc, 'path'):
                with open(self.file_doc.path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        hasher.update(chunk)
                return hasher.hexdigest()
            else:
                # Handle files in memory (e.g., during upload)
                for chunk in self.file_doc.chunks():
                    hasher.update(chunk)
                return hasher.hexdigest()
        except FileNotFoundError:
            logger.error(f"File not found: {getattr(self.file_doc, 'path', 'unknown')}")
            return None
        except Exception as e:
            logger.error(f"Error calculating file hash for document {self.id}: {str(e)}")
            return None

    def clean(self):
        """Custom validation for the model"""
        if self.file_doc and not self.file_doc.name.lower().endswith(
                ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt')):
            raise ValidationError({'file_doc': _("Invalid file type. Allowed types: PDF, DOC, DOCX, XLS, XLSX, TXT")})

        if isinstance(self.date_doc, str):
            try:
                datetime.strptime(self.date_doc, '%Y-%m-%d')
            except ValueError:
                raise ValidationError({'date_doc': _("Invalid date format. Use YYYY-MM-DD format")})

    def save(self, *args, **kwargs):
        try:
            # Handle created_by and updated_by
            if not self.created_by_id and hasattr(self, '_current_user'):
                self.created_by = self._current_user
            if hasattr(self, '_current_user'):
                self.updated_by = self._current_user

            # Generate initial hash if not present
            if not self.document_hash:
                self.document_hash = self.generate_hash()
                logger.debug(f"Generated initial hash for document: {self.document_hash}")

            # Check if this is an update
            updating = self.pk is not None
            old_hash = self.document_hash if updating else None

            # Handle file hash update
            if 'update_fields' not in kwargs or 'document_hash' not in kwargs.get('update_fields', []):
                if self.file_doc and (not self.document_hash or updating):
                    new_hash = self.generate_hash()
                    logger.debug(f"Generated new hash for document {self.id}: {new_hash}")

                    # Handle hash change
                    if updating and old_hash and old_hash != new_hash:
                        logger.info(f"Hash changed for document {self.id}. Old: {old_hash}, New: {new_hash}")
                        self.document_hash = new_hash

            # Save the model
            super().save(*args, **kwargs)

            # Update approvals and clear familiarizations if hash changed (requires re-approval and re-acknowledgment)
            if updating and old_hash and old_hash != self.document_hash and 'update_fields' not in kwargs:
                DocumentApproval.objects.filter(document=self).update(
                    status='pending',
                    approved_at=None,
                    document_hash=self.document_hash
                )
                self.update_approval_status()
                # Require re-acknowledgment after full approval when document content (hash) changes
                DocumentFamiliarization.objects.filter(document=self).delete()
                logger.info(f"Familiarization records cleared for document {self.id} due to hash change")

        except Exception as e:
            logger.error(f"Error saving document {self.id}: {str(e)}", exc_info=True)
            raise

    def delete(self, *args, **kwargs):
        if self.file_doc:
            try:
                default_storage.delete(self.file_doc.path)
            except Exception as e:
                logger.error(f"Error deleting file for document {self.id}: {str(e)}")
        super().delete(*args, **kwargs)

    @property
    def file_url(self):
        return self.file_doc.url if self.file_doc else None

    @property
    def file_size(self):
        if self.file_doc:
            try:
                return self.file_doc.size
            except FileNotFoundError:
                return 0
        return 0

    @property
    def file_extension(self):
        if self.file_doc:
            return os.path.splitext(self.file_doc.name)[1].lower()
        return None

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('register_doc_detail', args=[str(self.id)])

    def has_access(self, user):
        if user.is_superuser:
            return True
        if self.allowed_users.filter(pk=user.pk).exists():
            return True
        if not self.groups.exists():
            return False
        return AccessDocs.objects.filter(
            group__in=user.groups.all(),
            has_access=True
        ).exists() and self.groups.filter(pk__in=user.groups.values_list('pk', flat=True)).exists()

    def can_edit(self, user):
        if user.is_superuser:
            return True
        if user == self.created_by:
            return True
        return AccessLegislativeDoc.objects.filter(
            group__in=user.groups.all(),
            has_access=True,
            can_edit=True
        ).exists()

    def can_delete(self, user):
        if user.is_superuser:
            return True
        if user == self.created_by:
            return True
        return user.groups.filter(name='Document Managers').exists()

    @property
    def approval_status(self):
        """Get approval status"""
        if self.is_approved:
            return 'Approved'
        return 'Pending'

    def check_approvals_validity(self):
        """Check if all approvals are still valid based on current document hash"""
        current_hash = self.generate_hash()
        invalid_approvals = self.documentapproval_set.filter(
            status='approved'
        ).exclude(document_hash=current_hash)

        if invalid_approvals.exists():
            invalid_approvals.update(
                status='pending',
                approved_at=None,
                document_hash=current_hash
            )
            self.is_approved = False
            self.save()
            return False
        return True

    def get_approval_history(self):
        return DocumentApproval.objects.filter(document=self).order_by('approved_at')

class DocumentApproval(models.Model):
    document = models.ForeignKey(RegisterDocs, on_delete=models.CASCADE)
    approver = models.ForeignKey(User, on_delete=models.PROTECT)
    approved_at = models.DateTimeField(null=True, blank=True)
    document_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default='pending',
                            choices=[('pending', 'Pending'),
                                   ('approved', 'Approved'),
                                   ('rejected', 'Rejected')])

    class Meta:
        unique_together = ['document', 'approver']


class DocumentFamiliarization(models.Model):
    """Records that a user has acknowledged/familiarized with a document version (by hash)."""
    document = models.ForeignKey(RegisterDocs, on_delete=models.CASCADE, related_name='familiarization_set')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doc_familiarizations')
    document_hash = models.CharField(max_length=64, verbose_name=_("Document Hash"))
    acknowledged_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Acknowledged At"))

    class Meta:
        unique_together = ['document', 'user']
        verbose_name = _("Document Familiarization")
        verbose_name_plural = _("Document Familiarizations")
        ordering = ['-acknowledged_at']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.document.name_doc} ({self.acknowledged_at})"


class AccessDocs(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to Docs"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit Docs"))
    description = models.TextField(blank=True)
    companies = models.ManyToManyField('app_conf.Company', blank=True, related_name='access_docs', verbose_name=_("Companies"))

    class Meta:
        verbose_name = _("Access to Docs")
        verbose_name_plural = _("Access to Docs")

    def __str__(self):
        return f"{self.group.name} - Access: {self.has_access}, Edit: {self.can_edit}"

class AccessLegislativeDoc(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to Legislative Docs"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit Legislative Docs"))
    show_link = models.BooleanField(default=False, verbose_name=_("Show Legislative Docs link"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Access to Legislative Docs")
        verbose_name_plural = _("Access to Legislative Docs")
        ordering = ['group__name']
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['has_access']),
            models.Index(fields=['can_edit']),
        ]

    def __str__(self):
        return f"{self.group.name} - Legislative Access: {self.has_access}, Edit: {self.can_edit}"

class AccessMandatory(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to Mandatory Processes Registry"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit Mandatory Processes Registry"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    companies = models.ManyToManyField('app_conf.Company', blank=True, related_name='access_mandatory', verbose_name=_("Companies"))

    class Meta:
        verbose_name = _("Access to Mandatory Processes")
        verbose_name_plural = _("Access to Mandatory Processes")
        ordering = ['group__name']
        indexes = [
            models.Index(fields=['group']),
            models.Index(fields=['has_access']),
            models.Index(fields=['can_edit']),
        ]

    def __str__(self):
        return f"{self.group.name} - Mandatory Access: {self.has_access}, Edit: {self.can_edit}"


class RegulatorName(models.Model):
    """Model for regulatory bodies"""
    name = models.CharField(max_length=255, verbose_name=_("Regulator Name"), unique=True)
    code = models.CharField(max_length=50, verbose_name=_("Regulator Code"), blank=True, null=True)
    description = models.TextField(verbose_name=_("Description"), blank=True, null=True)
    website = models.URLField(verbose_name=_("Website URL"), blank=True, null=True)
    color = models.CharField(max_length=7, verbose_name=_("Display Color"), 
                           default="#e0f7fa", help_text=_("Color in HEX format for text color, e.g. #FF0000"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    
    class Meta:
        verbose_name = _("Regulator")
        verbose_name_plural = _("Regulators")
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['code']),
        ]
    
    def __str__(self):
        return self.name

class LegislativeDoc(models.Model):
    """Model for legislative documents and regulatory requirements"""
    
    title = models.CharField(max_length=255, verbose_name=_("Title"))
    doc_number = models.CharField(max_length=100, verbose_name=_("Document Number"), blank=True, null=True)
    doc_type = models.ForeignKey('DocType', on_delete=models.SET_NULL, null=True, 
                               verbose_name=_("Document Type"), related_name='legislative_docs')
    issuing_authority = models.CharField(max_length=255, verbose_name=_("Issuing Authority"), blank=True, null=True)
    regulator = models.ForeignKey(RegulatorName, on_delete=models.SET_NULL, blank=True, null=True, 
                                related_name='legislative_docs', verbose_name=_("Regulator"))
    original_url = models.URLField(verbose_name=_("Original Document URL"), blank=True, null=True, 
                                max_length=1000, help_text=_("URL to the original document source"))
    issue_date = models.DateField(verbose_name=_("Issue Date"), null=True, blank=True)
    effective_date = models.DateField(verbose_name=_("Effective Date"), null=True, blank=True)
    expiration_date = models.DateField(verbose_name=_("Expiration Date"), null=True, blank=True)
    
    description = models.TextField(verbose_name=_("Description"))
    
    pdf_file = models.FileField(
        upload_to='legislative_docs/', 
        null=True, 
        blank=True,
        verbose_name=_("PDF Document"),
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf']),
            validate_file_size
        ]
    )
    
    html_content = HTMLField(blank=True, null=True, verbose_name='HTML Content')
    
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    company = models.ManyToManyField('app_conf.Company', blank=True, related_name='legislative_docs', verbose_name=_("Companies"))
    groups = models.ManyToManyField('auth.Group', blank=True, related_name='legislative_docs', verbose_name=_("Groups"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_legislative_docs', verbose_name=_("Created By"))
    updated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_legislative_docs', verbose_name=_("Updated By"))
    
    class Meta:
        verbose_name = _("Legislative Document")
        verbose_name_plural = _("Legislative Documents")
        ordering = ['-effective_date', 'title']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['doc_type']),
            models.Index(fields=['issue_date']),
            models.Index(fields=['effective_date']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        doc_type_name = self.doc_type.get_name() if self.doc_type else ""
        return f"{self.title} ({doc_type_name})"
    
    def has_access(self, user):
        if user.is_superuser:
            return True
        return AccessLegislativeDoc.objects.filter(
            group__in=user.groups.all(),
            has_access=True
        ).exists()
    
    def can_edit(self, user):
        if user.is_superuser:
            return True
        if user == self.created_by:
            return True
        return AccessLegislativeDoc.objects.filter(
            group__in=user.groups.all(),
            has_access=True,
            can_edit=True
        ).exists()


class RegDocsGuide(models.Model):
    """Base Guide for Document Registry (reg_docs). Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Reg Docs Guide")
        verbose_name_plural = _("Reg Docs Guides")

    def __str__(self):
        return str(gettext("Document Registry Guide"))


class RegDocsGuideTranslation(models.Model):
    """Per-country (language) translations of the Reg Docs Guide."""
    guide = models.ForeignKey(
        RegDocsGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="reg_docs_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Reg Docs Guide Translation")
        verbose_name_plural = _("Reg Docs Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class LegislativeDocsGuide(models.Model):
    """Base Guide for Legislative Documents. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Legislative Docs Guide")
        verbose_name_plural = _("Legislative Docs Guides")

    def __str__(self):
        return str(gettext("Legislative Documents Guide"))


class LegislativeDocsGuideTranslation(models.Model):
    """Per-country (language) translations of the Legislative Docs Guide."""
    guide = models.ForeignKey(
        LegislativeDocsGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="legislative_docs_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Legislative Docs Guide Translation")
        verbose_name_plural = _("Legislative Docs Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"