#  SecBoard\SecBoard\app_incident\models.py

import re
from django.db import models
from django.utils.translation import get_language
from app_conf.models import Company
from django.utils.translation import gettext as _, gettext_lazy as _lazy
from django.contrib.auth.models import Group
import logging
from app_cabinet.models import CabinetUser


logger = logging.getLogger(__name__)

# Map language code to country codes for translations (same pattern as app_doc / app_asset)
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


class Classification(models.Model):
    """Incident classification (same pattern as DocStatus/DocType/AccessClassification: name/code/description + Translations per country)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Classification Name"),
        max_length=100,
        blank=True,
        help_text=_("Name, default: English (En). For other languages use Translations inline.")
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
        help_text=_("Unique code (e.g., security-breach, data-leak)")
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
                Classification.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else Classification.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (Classification.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'classification-{self.pk or next_id}'
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
            except ClassificationTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or ''

    def get_description_by_language(self, language=None):
        country = self._country_for_lang(language)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except ClassificationTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_name(self):
        """Get localized name: translation for current country, else get_name_by_language (same as DocStatus/DocType)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except ClassificationTranslation.DoesNotExist:
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
            except ClassificationTranslation.DoesNotExist:
                pass
        if self.description:
            return self.description
        return self.get_description_by_language()

    def get_local_name(self, country):
        """Get localized name for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except ClassificationTranslation.DoesNotExist:
            return self.name_local or self.name or self.get_name_by_language()

    def get_local_description(self, country):
        """Get localized description for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.description or self.description or ''
        except ClassificationTranslation.DoesNotExist:
            return self.description or self.get_description_by_language()

    def __str__(self):
        return self.get_name() or self.name or self.name_local or ''

    class Meta:
        verbose_name = _("Classification")
        verbose_name_plural = _("Classifications")


class ClassificationTranslation(models.Model):
    """Translations of incident classification for different countries (same as DocStatus/DocType Translations)."""
    classification = models.ForeignKey(
        Classification,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Classification")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='classification_translations',
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
        verbose_name = _("Classification Translation")
        verbose_name_plural = _("Classification Translations")
        unique_together = ['classification', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.classification.name or self.name_local} - {self.country.name}: {self.name_local}"


class Currentstate(models.Model):
    """Incident current state (same pattern as Classification: name/code/description + Translations per country)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("State Name"),
        max_length=100,
        blank=True,
        help_text=_("State name, default: English (En). E.g. Open, In Progress, Closed. For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("State name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("State Code"),
        max_length=50,
        unique=True,
        blank=True,
        help_text=_("Unique code (e.g., open, in-progress, closed)")
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
                Currentstate.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else Currentstate.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (Currentstate.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'currentstate-{self.pk or next_id}'
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
            except CurrentstateTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or ''

    def get_description_by_language(self, language=None):
        country = self._country_for_lang(language)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except CurrentstateTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_name(self):
        """Get localized name: translation for current country, else get_name_by_language (same as Classification)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except CurrentstateTranslation.DoesNotExist:
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
            except CurrentstateTranslation.DoesNotExist:
                pass
        if self.description:
            return self.description
        return self.get_description_by_language()

    def get_local_name(self, country):
        """Get localized name for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except CurrentstateTranslation.DoesNotExist:
            return self.name_local or self.name or self.get_name_by_language()

    def get_local_description(self, country):
        """Get localized description for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.description or self.description or ''
        except CurrentstateTranslation.DoesNotExist:
            return self.description or self.get_description_by_language()

    def __str__(self):
        return self.get_name() or self.name or self.name_local or ''

    class Meta:
        verbose_name = _("Current State")
        verbose_name_plural = _("Current States")


class CurrentstateTranslation(models.Model):
    """Translations of incident current state for different countries (same as Classification Translations)."""
    currentstate = models.ForeignKey(
        Currentstate,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Current State")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='currentstate_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("State name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )

    class Meta:
        verbose_name = _("Current State Translation")
        verbose_name_plural = _("Current State Translations")
        unique_together = ['currentstate', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.currentstate.name or self.name_local} - {self.country.name}: {self.name_local}"


class Incidenttype(models.Model):
    """Incident type (same pattern as Classification/Currentstate: name/code/description + Translations per country)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Type Name"),
        max_length=100,
        blank=True,
        help_text=_("Type name, default: English (En). E.g. Security breach, Data leak. For other languages use Translations inline.")
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
        help_text=_("Unique code (e.g., security-breach, data-leak)")
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
                Incidenttype.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else Incidenttype.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (Incidenttype.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'incidenttype-{self.pk or next_id}'
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
            except IncidenttypeTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or ''

    def get_description_by_language(self, language=None):
        country = self._country_for_lang(language)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except IncidenttypeTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_name(self):
        """Get localized name: translation for current country, else get_name_by_language (same as Classification)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except IncidenttypeTranslation.DoesNotExist:
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
            except IncidenttypeTranslation.DoesNotExist:
                pass
        if self.description:
            return self.description
        return self.get_description_by_language()

    def get_local_name(self, country):
        """Get localized name for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except IncidenttypeTranslation.DoesNotExist:
            return self.name_local or self.name or self.get_name_by_language()

    def get_local_description(self, country):
        """Get localized description for specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.description or self.description or ''
        except IncidenttypeTranslation.DoesNotExist:
            return self.description or self.get_description_by_language()

    def __str__(self):
        return self.get_name() or self.name or self.name_local or ''

    class Meta:
        verbose_name = _("Incident Type")
        verbose_name_plural = _("Incident Types")


class IncidenttypeTranslation(models.Model):
    """Translations of incident type for different countries (same as Classification Translations)."""
    incidenttype = models.ForeignKey(
        Incidenttype,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Incident Type")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='incidenttype_translations',
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
        verbose_name = _("Incident Type Translation")
        verbose_name_plural = _("Incident Type Translations")
        unique_together = ['incidenttype', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.incidenttype.name or self.name_local} - {self.country.name}: {self.name_local}"


class Incident(models.Model):
    company = models.ForeignKey('app_conf.Company', on_delete=models.CASCADE, verbose_name=_("Company"))
    cif_object = models.ForeignKey(
        'app_cif.CIFObject',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents',
        verbose_name=_("CIF object")
    )
    occurrence_datetime = models.DateTimeField(_("Date and Time of Occurrence"), null=True, blank=True)
    place = models.CharField(_("Place of Occurrence"), max_length=255)
    description = models.TextField(_("Description"))
    classification = models.ForeignKey('Classification', on_delete=models.SET_NULL, null=True, blank=True)
    incident_type = models.ForeignKey('Incidenttype', on_delete=models.SET_NULL, null=True, blank=True)
    features = models.TextField(_("Features and Signs"), blank=True)
    responsible = models.CharField(_("Responsible for Resolution"), max_length=255)
    reported_by = models.CharField(_("Reported by"), max_length=255)
    reported_datetime = models.DateTimeField(_("Date and Time"), null=True, blank=True)
    registered_by = models.CharField(_("Registered by"), max_length=255)
    registered_datetime = models.DateTimeField(_("Date and Time"), null=True, blank=True)
    reports_and_records = models.TextField(_("Reports and Records"), blank=True)
    impact = models.TextField(_("Impact"), blank=True)
    measures_taken = models.TextField(_("Measures Taken"), blank=True)
    additional_measures = models.TextField(_("Additional Measures to Prevent Recurrence"), blank=True)
    current_state = models.ForeignKey('Currentstate', on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.TextField(_("Comment"), blank=True)
    file_incident = models.FileField(upload_to='incident_reports/', 
                                   blank=True, null=True,
                                   verbose_name=_("Incident report files"),
                                   max_length=255)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = _("Incident")
        verbose_name_plural = _("Incidents")
        ordering = ['-occurrence_datetime']

    def __str__(self):
        return f"Incident {self.id} - {self.company.name} - {self.occurrence_datetime}"


class IncidentFile(models.Model):
    """Model for storing multiple files associated with incidents"""
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='incident_reports/', max_length=255)
    filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"File for Incident {self.incident.id} - {self.filename}"
    
    def save(self, *args, **kwargs):
        if not self.filename and self.file:
            self.filename = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)


class AccessIncidents(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to Information Incidents"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit Information Incidents"))
    can_add = models.BooleanField(default=False, verbose_name=_("Can add new Information Incidents"))
    can_delete = models.BooleanField(default=False, verbose_name=_("Can delete Information Incidents"))
    can_mail = models.BooleanField(default=False, verbose_name=_("Can send emails for Information Incidents"))
    show_link = models.BooleanField(default=False, verbose_name=_("Show link on index page"))
    companies = models.ManyToManyField(Company, blank=True, related_name='access_incidents', verbose_name=_("Companies"))
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Access to Incidents")
        verbose_name_plural = _("Access to Incidents")

    def __str__(self):
        return f"{self.group.name} - Has Access: {self.has_access}, Edit Access: {self.can_edit}, Show Link: {self.show_link}"


from tinymce.models import HTMLField


class IncidentRegisterGuide(models.Model):
    """Base Guide for Incident Register. Source content for translations."""
    base_content = HTMLField(
        _lazy("Base content"),
        blank=True,
        help_text=_lazy("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _lazy("Incident Register Guide")
        verbose_name_plural = _lazy("Incident Register Guides")

    def __str__(self):
        return _("Incident Register Guide")


class IncidentRegisterGuideTranslation(models.Model):
    """Per-country (language) translations of the Incident Register Guide."""
    guide = models.ForeignKey(
        IncidentRegisterGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_lazy("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="incident_register_guide_translations",
        verbose_name=_lazy("Country")
    )
    content = HTMLField(
        _lazy("Content"),
        blank=True,
        help_text=_lazy("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _lazy("Incident Register Guide Translation")
        verbose_name_plural = _lazy("Incident Register Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"




