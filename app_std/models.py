# SecBoard/app_std/models.py
import re
from django.db import models
from django.utils.translation import gettext as _, get_language
from django.contrib.auth.models import Group
import os

import logging

logger = logging.getLogger(__name__)

# Map language code to country codes for translations (same as app_risk / app_access)
LANGUAGE_COUNTRY_MAP = {
    'uk': ['UA'], 'ua': ['UA'],
    'ru': ['RU'],
    'en': ['GB', 'US'],
    'pl': ['PL'], 'de': ['DE'], 'fr': ['FR'], 'es': ['ES'], 'it': ['IT'], 'pt': ['PT'],
    'nl': ['NL'], 'cs': ['CZ'], 'sk': ['SK'], 'ro': ['RO'], 'bg': ['BG'], 'lt': ['LT'],
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


class PCIDSSCategory(models.Model):
    """PCI DSS Standard (Category) with name/code/description + per-country Translations."""
    category_id = models.CharField(_("Category ID"), max_length=100, unique=True)
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Name"),
        max_length=255,
        blank=True,
        help_text=_("Category name, default: English. For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=255,
        blank=True,
        help_text=_("Category name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Code"),
        max_length=80,
        blank=True,
        help_text=_("Unique code (auto-generated from name if empty)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description. For other languages use Translations inline.")
    )
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("PCI DSS Standard")
        verbose_name_plural = _("PCI DSS Standard")
        ordering = ['category_id', 'name', 'code']

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:80]

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '')[:80].strip()
            self.code = self._slugify_code(base) or self.category_id or ''
        super().save(*args, **kwargs)

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        lang = 'uk' if lang == 'ua' else lang
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def get_name_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except PCIDSSCategoryTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or _("Unnamed")

    def set_name_for_language(self, lang, value):
        """Set or update the category name for a language (creates/updates Translation)."""
        country = self._country_for_lang(lang)
        if not country:
            return
        value = (value or '').strip()[:255]
        self.translations.update_or_create(
            country=country,
            defaults={'name_local': value or (self.name or self.name_local or '')}
        )

    def get_description_by_language(self, lang):
        return self.description or ""

    def get_name(self, language=None):
        if language is not None:
            return self.get_name_by_language(language)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except PCIDSSCategoryTranslation.DoesNotExist:
                pass
        if self.name or self.name_local:
            lang_code = (get_language() or '')[:2].lower()
            return self.name or self.name_local if lang_code == 'en' else self.name_local or self.name
        return self.get_name_by_language((get_language() or 'en')[:2].lower())

    def get_description(self, language=None):
        if language is not None:
            return self.get_description_by_language(language)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except PCIDSSCategoryTranslation.DoesNotExist:
                pass
        return self.description or ""

    def get_local_name(self, country):
        try:
            t = self.translations.get(country=country)
            if t.name_local:
                return t.name_local
        except PCIDSSCategoryTranslation.DoesNotExist:
            pass
        return self.name or self.get_name_by_language('en')

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except PCIDSSCategoryTranslation.DoesNotExist:
            return self.description or ''

    def get_category(self, lang='uk'):
        """Backward compatibility: return category name for language."""
        return self.get_name_by_language(lang)

    def __str__(self):
        return self.get_name() or self.name or self.name_local or f"{self.category_id}: —"


class PCIDSSCategoryTranslation(models.Model):
    """Translations of PCI DSS Standard (category) for different countries."""
    category = models.ForeignKey(
        PCIDSSCategory,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("PCI DSS Standard")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='pcidss_category_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=255, help_text=_("Category name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))

    class Meta:
        verbose_name = _("PCI DSS Standard Translation")
        verbose_name_plural = _("PCI DSS Standard Translations")
        unique_together = ['category', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.category.name or self.category.name_local} - {self.country.name}: {self.name_local}"


REQUIREMENT_TEXT_FIELDS = [
    'title', 'description', 'definitions', 'purpose', 'good_practice',
    'examples', 'testing_procedures', 'customized_approach_objective',
    'applicability_notes', 'further_information',
]


class PCIDSSRequirement(models.Model):
    """PCI DSS Requirement with default (e.g. English) fields + per-country Translations."""
    requirement_number = models.CharField(_("Requirement Number"), max_length=10)
    category = models.ForeignKey(PCIDSSCategory, on_delete=models.CASCADE, related_name='requirements', verbose_name=_("Category"))
    # Default (English) fields – for other languages use Translations inline
    title = models.TextField(_("Title"), blank=True, default="")
    description = models.TextField(_("Description"), blank=True, default="")
    definitions = models.TextField(_("Definitions"), blank=True, default="")
    purpose = models.TextField(_("Purpose"), blank=True, default="")
    good_practice = models.TextField(_("Good Practice"), blank=True, default="")
    examples = models.TextField(_("Examples"), blank=True, default="")
    testing_procedures = models.TextField(_("Testing Procedures"), blank=True, default="")
    customized_approach_objective = models.TextField(_("Customized Approach Objective"), blank=True, default="")
    applicability_notes = models.TextField(_("Applicability Notes"), blank=True, default="")
    further_information = models.TextField(_("Further Information"), blank=True, default="")

    class Meta:
        verbose_name = _("PCI DSS Requirement")
        verbose_name_plural = _("PCI DSS Requirements")
        ordering = ['requirement_number']

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        lang = 'uk' if lang == 'ua' else lang
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def _get_field_by_language(self, field_name, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                val = getattr(t, field_name, None)
                if val:
                    return val
            except PCIDSSRequirementTranslation.DoesNotExist:
                pass
        return getattr(self, field_name, '') or ''

    def _set_field_for_language(self, field_name, lang, value):
        if field_name not in REQUIREMENT_TEXT_FIELDS:
            return
        country = self._country_for_lang(lang)
        if not country:
            return
        value = value or ''
        try:
            trans = self.translations.get(country=country)
            setattr(trans, field_name, value)
            trans.save(update_fields=[field_name])
        except PCIDSSRequirementTranslation.DoesNotExist:
            defaults = {f: getattr(self, f, '') or '' for f in REQUIREMENT_TEXT_FIELDS}
            defaults[field_name] = value
            self.translations.create(country=country, **defaults)

    def get_title(self, lang='uk'):
        return self._get_field_by_language('title', lang)

    def get_description(self, lang='uk'):
        return self._get_field_by_language('description', lang)

    def get_definitions(self, lang='uk'):
        return self._get_field_by_language('definitions', lang)

    def get_purpose(self, lang='uk'):
        return self._get_field_by_language('purpose', lang)

    def get_good_practice(self, lang='uk'):
        return self._get_field_by_language('good_practice', lang)

    def get_examples(self, lang='uk'):
        return self._get_field_by_language('examples', lang)

    def get_testing_procedures(self, lang='uk'):
        return self._get_field_by_language('testing_procedures', lang)

    def get_customized_approach_objective(self, lang='uk'):
        return self._get_field_by_language('customized_approach_objective', lang)

    def get_applicability_notes(self, lang='uk'):
        return self._get_field_by_language('applicability_notes', lang)

    def get_further_information(self, lang='uk'):
        return self._get_field_by_language('further_information', lang)

    def set_field_for_language(self, field_name, lang, value):
        """Set one requirement text field for a language (creates/updates Translation)."""
        self._set_field_for_language(field_name, lang, value)

    def get_category(self, lang='uk'):
        return self.category.get_name(lang) if self.category else ''

    def __str__(self):
        return f"{self.requirement_number}: {self.get_title() or self.title or '—'}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('pcidss_requirement_detail', args=[str(self.id)])


class PCIDSSRequirementTranslation(models.Model):
    """Translations of PCI DSS Requirement text fields per country."""
    requirement = models.ForeignKey(
        PCIDSSRequirement,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Requirement")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='pcidss_requirement_translations',
        verbose_name=_("Country")
    )
    title = models.TextField(_("Title"), blank=True, default="")
    description = models.TextField(_("Description"), blank=True, default="")
    definitions = models.TextField(_("Definitions"), blank=True, default="")
    purpose = models.TextField(_("Purpose"), blank=True, default="")
    good_practice = models.TextField(_("Good Practice"), blank=True, default="")
    examples = models.TextField(_("Examples"), blank=True, default="")
    testing_procedures = models.TextField(_("Testing Procedures"), blank=True, default="")
    customized_approach_objective = models.TextField(_("Customized Approach Objective"), blank=True, default="")
    applicability_notes = models.TextField(_("Applicability Notes"), blank=True, default="")
    further_information = models.TextField(_("Further Information"), blank=True, default="")

    class Meta:
        verbose_name = _("PCI DSS Requirement Translation")
        verbose_name_plural = _("PCI DSS Requirement Translations")
        unique_together = ['requirement', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.requirement.requirement_number} - {self.country.name}: {self.title[:50] if self.title else '—'}"

class AccessPCIDSS(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to PCIDSS"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit Information PCIDSS"))
    show_link = models.BooleanField(default=False, verbose_name=_("Show link on index page to pcidss"))
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Access to PCIDSS")
        verbose_name_plural = _("Access to PCIDSS")

    def __str__(self):
        return f"{self.group.name} - Has Access: {self.has_access}, Edit Access: {self.can_edit}, Show Link: {self.show_link}"


class ISO27002Theme(models.Model):
    THEME_CHOICES = [
        ('people', _('People')),
        ('physical', _('Physical')),
        ('technological', _('Technological')),
        ('organizational', _('Organizational')),
    ]

    name = models.CharField(_("Theme Name"), max_length=50, choices=THEME_CHOICES)
    description = models.TextField(_("Description"), blank=True, default="", help_text=_("Default (e.g. English). Use Translations for other languages."))

    class Meta:
        verbose_name = _("ISO 27002 Theme")
        verbose_name_plural = _("ISO 27002 Themes")
        ordering = ['name']

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        lang = 'uk' if lang == 'ua' else lang
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def get_description(self, lang='uk'):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except ISO27002ThemeTranslation.DoesNotExist:
                pass
        return self.description or ''

    def set_description_for_language(self, lang, value):
        country = self._country_for_lang(lang)
        if not country:
            return
        value = value or ''
        try:
            trans = self.translations.get(country=country)
            trans.description = value
            trans.save(update_fields=['description'])
        except ISO27002ThemeTranslation.DoesNotExist:
            self.translations.create(country=country, description=value)

    def __str__(self):
        return self.get_name_display()


class ISO27002ThemeTranslation(models.Model):
    """Translations of ISO 27002 Theme description per country."""
    theme = models.ForeignKey(
        ISO27002Theme,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Theme")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='iso27002_theme_translations',
        verbose_name=_("Country")
    )
    description = models.TextField(_("Description"), blank=True, default="")

    class Meta:
        verbose_name = _("ISO 27002 Theme Translation")
        verbose_name_plural = _("ISO 27002 Theme Translations")
        unique_together = ['theme', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.theme.get_name_display()} - {self.country.name}"


class ISO27002Control(models.Model):
    CONTROL_TYPE_CHOICES = [
        ('preventive', _('Preventive')),
        ('detective', _('Detective')),
        ('corrective', _('Corrective')),
    ]

    INFO_SECURITY_PROPERTIES = [
        ('confidentiality', _('Confidentiality')),
        ('integrity', _('Integrity')),
        ('availability', _('Availability')),
    ]

    CYBERSECURITY_CONCEPTS = [
        ('identify', _('Identify')),
        ('protect', _('Protect')),
        ('detect', _('Detect')),
        ('respond', _('Respond')),
        ('recover', _('Recover')),
    ]

    SECURITY_DOMAINS = [
        ('governance_and_ecosystem', _('Governance and Ecosystem')),
        ('protection', _('Protection')),
        ('defence', _('Defence')),
        ('resilience', _('Resilience')),
    ]

    control_number = models.CharField(_("Control Number"), max_length=10)
    theme = models.ForeignKey(ISO27002Theme, on_delete=models.CASCADE, related_name='controls')

    # Default (e.g. English) text fields – use Translations for other languages
    title = models.CharField(_("Title"), max_length=255, blank=True, default="")
    control_description = models.TextField(_("Control Description"), blank=True, default="")
    purpose = models.TextField(_("Purpose"), blank=True, default="")
    guidance = models.TextField(_("Guidance"), blank=True, default="")
    other_information = models.TextField(_("Other Information"), blank=True, default="")

    # Attribute fields
    control_type = models.CharField(
        _("Control Type"),
        max_length=20,
        choices=CONTROL_TYPE_CHOICES
    )

    information_security_properties = models.JSONField(
        _("Information Security Properties"),
        help_text=_("List of applicable security properties (confidentiality, integrity, availability)")
    )

    cybersecurity_concepts = models.JSONField(
        _("Cybersecurity Concepts"),
        help_text=_("List of applicable cybersecurity concepts")
    )

    operational_capabilities = models.JSONField(
        _("Operational Capabilities"),
        help_text=_("List of applicable operational capabilities")
    )

    security_domain = models.CharField(
        _("Security Domain"),
        max_length=50,
        choices=SECURITY_DOMAINS
    )

    class Meta:
        verbose_name = _("ISO 27002 Control")
        verbose_name_plural = _("ISO 27002 Controls")
        ordering = ['control_number']

    ISO27002_CONTROL_TEXT_FIELDS = ['title', 'control_description', 'purpose', 'guidance', 'other_information']

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        lang = 'uk' if lang == 'ua' else lang
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def _get_field_by_language(self, field_name, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                val = getattr(t, field_name, None)
                if val:
                    return val
            except ISO27002ControlTranslation.DoesNotExist:
                pass
        return getattr(self, field_name, '') or ''

    def _set_field_for_language(self, field_name, lang, value):
        if field_name not in self.ISO27002_CONTROL_TEXT_FIELDS:
            return
        country = self._country_for_lang(lang)
        if not country:
            return
        value = (value or '')[:255] if field_name == 'title' else (value or '')
        try:
            trans = self.translations.get(country=country)
            setattr(trans, field_name, value)
            trans.save(update_fields=[field_name])
        except ISO27002ControlTranslation.DoesNotExist:
            defaults = {f: getattr(self, f, '') or '' for f in self.ISO27002_CONTROL_TEXT_FIELDS}
            defaults[field_name] = value
            self.translations.create(country=country, **defaults)

    def get_title(self, lang='uk'):
        return self._get_field_by_language('title', lang)

    def get_control_description(self, lang='uk'):
        return self._get_field_by_language('control_description', lang)

    def get_purpose(self, lang='uk'):
        return self._get_field_by_language('purpose', lang)

    def get_guidance(self, lang='uk'):
        return self._get_field_by_language('guidance', lang)

    def get_other_information(self, lang='uk'):
        return self._get_field_by_language('other_information', lang)

    def set_field_for_language(self, field_name, lang, value):
        self._set_field_for_language(field_name, lang, value)

    def __str__(self):
        return f"{self.control_number}: {self.get_title() or self.title or '—'}"


class ISO27002ControlTranslation(models.Model):
    """Translations of ISO 27002 Control text fields per country."""
    control = models.ForeignKey(
        ISO27002Control,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Control")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='iso27002_control_translations',
        verbose_name=_("Country")
    )
    title = models.CharField(_("Title"), max_length=255, blank=True, default="")
    control_description = models.TextField(_("Control Description"), blank=True, default="")
    purpose = models.TextField(_("Purpose"), blank=True, default="")
    guidance = models.TextField(_("Guidance"), blank=True, default="")
    other_information = models.TextField(_("Other Information"), blank=True, default="")

    class Meta:
        verbose_name = _("ISO 27002 Control Translation")
        verbose_name_plural = _("ISO 27002 Control Translations")
        unique_together = ['control', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.control.control_number} - {self.country.name}: {self.title[:50] if self.title else '—'}"


class AccessISO27002(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to ISO 27002"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit ISO 27002 information"))
    show_link = models.BooleanField(default=False, verbose_name=_("Show link on index page to ISO 27002"))
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Access to ISO 27002")
        verbose_name_plural = _("Access to ISO 27002")

    def __str__(self):
        return f"{self.group.name} - Has Access: {self.has_access}, Edit Access: {self.can_edit}, Show Link: {self.show_link}"

class PCIDSSDocument(models.Model):
    """Model for storing PCI DSS related documents (PDF files)"""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='pcidss_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
        
    def filename(self):
        return os.path.basename(self.file.name)