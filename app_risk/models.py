# SecBoard/app_risk/models.py

import re
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from app_conf.models import Company
from django.utils.translation import gettext as _, gettext_lazy as _lazy, get_language
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from decimal import Decimal
import logging
from app_asset.models import InformationAsset, AssetGroup, AssetType
from datetime import datetime, timedelta
from django.utils import timezone
from app_cabinet.models import CabinetUser
import uuid

logger = logging.getLogger(__name__)

# Map language code to country codes for translations (same pattern as app_keycert / app_doc)
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





class Threat(models.Model):
    """Threat (same pattern as FinancialImpact: name/code/description/risks + Translations per country)."""
    PROBABILITY_CHOICES = [
        ('manual', _('Manual input')),
        ('daily', _('Daily')),
        ('m_in_n_days', 'M times in N days'),
        ('once_in_n_years', 'Once in N years'),
        ('m_in_n_years', 'M times in N years'),
    ]

    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Threat Name"),
        max_length=200,
        blank=True,
        help_text=_("Threat name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=200,
        blank=True,
        help_text=_("Threat name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Threat Code"),
        max_length=80,
        unique=True,
        blank=True,
        help_text=_("Unique code (auto-generated from name if empty)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    risks = models.TextField(
        _("Risks"),
        blank=True,
        help_text=_("Risks description, default: English (En). For other languages use Translations inline.")
    )
    extra_translations = models.JSONField(default=dict, blank=True, help_text=_("Translations for additional languages: {name: {de: '...'}, description: {...}, risks: {...}}"))

    TRANSLATABLE_FIELDS = ('name', 'description', 'risks')

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def get_translated_value(self, field, lang):
        """Get value for field+lang from extra_translations (and country translation for name/description/risks)."""
        country = self._country_for_lang(lang)
        if country and field in ('name', 'description', 'risks'):
            try:
                t = self.translations.get(country=country)
                val = getattr(t, 'name_local' if field == 'name' else field, None)
                if val is not None and str(val).strip():
                    return val
            except ThreatTranslation.DoesNotExist:
                pass
        ext = (self.extra_translations or {}).get(field) or {}
        return ext.get(lang, '') or ''

    def set_translated_value(self, field, lang, value):
        """Set value for field+lang in extra_translations."""
        ext = dict(self.extra_translations or {})
        if field not in ext:
            ext[field] = {}
        ext[field][lang] = value or ''
        self.extra_translations = ext

    probability = models.DecimalField(
        verbose_name=_("Probability value (L)"),
        max_digits=5,  # Загальна кількість цифр
        decimal_places=4,  # 4 десяткові знаки
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('1'))
        ]
    )
    impact = models.DecimalField(
        verbose_name=_("Threat realization impact (E)"),
        max_digits=5,  # Загальна кількість цифр
        decimal_places=2,  # 2 десяткові знаки
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100'))
        ]
    )
    
    # New impact fields according to methodology
    financial_impact = models.ForeignKey(
        'FinancialImpact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Financial Impact"),
        help_text=_("Financial impact level according to methodology")
    )
    operational_impact = models.ForeignKey(
        'OperationalImpact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Operational Impact"),
        help_text=_("Operational impact level according to methodology")
    )
    reputational_impact = models.ForeignKey(
        'ReputationalImpact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Reputational Impact"),
        help_text=_("Reputational impact level according to methodology")
    )
    
    probability_scenario = models.CharField(max_length=20, choices=PROBABILITY_CHOICES, default='manual', verbose_name=_("Probability scenario"))
    scenario_m = models.IntegerField(null=True, blank=True, verbose_name=_("Scenario M"))
    scenario_n = models.IntegerField(null=True, blank=True, verbose_name=_("Scenario N"))
    is_active = models.BooleanField(_("Is Active"), default=True)

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:80]

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '')[:80].strip()
            self.code = self._slugify_code(base)
            existing = set(
                Threat.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else Threat.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (Threat.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'threat-{self.pk or next_id}'
        super().save(*args, **kwargs)

    def get_name_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except ThreatTranslation.DoesNotExist:
                pass
        val = (self.extra_translations or {}).get('name') or {}
        return val.get(lang, '') or self.name_local or self.name or ''

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except ThreatTranslation.DoesNotExist:
                pass
        val = (self.extra_translations or {}).get('description') or {}
        return val.get(lang, '') or self.description or ''

    def get_risks_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.risks:
                    return t.risks
            except ThreatTranslation.DoesNotExist:
                pass
        val = (self.extra_translations or {}).get('risks') or {}
        return val.get(lang, '') or self.risks or ''

    @classmethod
    def get_by_display_name(cls, name):
        """Return first Threat whose name, name_local, or any translation name_local equals name."""
        from django.db.models import Q
        if not name:
            return None
        qs = cls.objects.filter(
            Q(name=name) | Q(name_local=name) | Q(translations__name_local=name)
        ).distinct()
        return qs.first()

    def get_name(self, lang=None):
        if lang is not None:
            return self.get_name_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except ThreatTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, lang=None):
        if lang is not None:
            return self.get_description_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except ThreatTranslation.DoesNotExist:
                pass
        return self.description or self.get_description_by_language((get_language() or 'en')[:2]) or ''

    def get_risks(self, lang=None):
        if lang is not None:
            return self.get_risks_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.risks:
                    return t.risks
            except ThreatTranslation.DoesNotExist:
                pass
        return self.risks or self.get_risks_by_language((get_language() or 'en')[:2])

    def get_impact_level_name(self, impact_type, lang='uk'):
        """Get localized name for impact level"""
        impact_field = getattr(self, f'{impact_type}_impact')
        if impact_field:
            return impact_field.get_name(lang)
        return _('Not specified')

    def get_financial_impact_display_name(self):
        """Get localized financial impact name. Uses Country-based translations (e.g. Germany DE)."""
        if not self.financial_impact:
            return ''
        return self.financial_impact.get_name()

    def get_operational_impact_display_name(self):
        """Get localized operational impact name. Uses Country-based translations (e.g. Germany DE)."""
        if not self.operational_impact:
            return ''
        return self.operational_impact.get_name()

    def get_reputational_impact_display_name(self):
        """Get localized reputational impact name. Uses Country-based translations (e.g. Germany DE)."""
        if not self.reputational_impact:
            return ''
        return self.reputational_impact.get_name()

    def get_calculated_impact_display(self):
        """Get calculated impact value for display"""
        if self.financial_impact or self.operational_impact or self.reputational_impact:
            return self.calculate_threat_impact()
        return self.impact

    def get_overall_impact_display(self):
        """Get overall impact value for display"""
        if self.financial_impact or self.operational_impact or self.reputational_impact:
            return self.calculate_overall_impact()
        return self.impact / 100

    def get_probability_scenario_display(self):
        return dict(self.PROBABILITY_CHOICES)[self.probability_scenario]

    def get_localized_probability_scenario(self, lang):
        val = getattr(self, f'probability_scenario_{lang}', None)
        return val or self.get_probability_scenario_display()

    def get_formatted_probability_scenario(self):
        scenario = self.get_probability_scenario_display()
        if self.probability_scenario == 'm_in_n_days':
            return f"{self.scenario_m} {_('times in')} {self.scenario_n} {_('days')}"
        elif self.probability_scenario == 'once_in_n_years':
            return f"{_('Once in')} {self.scenario_n} {_('years')}"
        elif self.probability_scenario == 'm_in_n_years':
            return f"{self.scenario_m} {_('times in')} {self.scenario_n} {_('years')}"
        return scenario

    def calculate_probability(self):
        if self.probability_scenario == 'manual':
            return self.probability
        elif self.probability_scenario == 'daily':
            return Decimal('1')
        elif self.probability_scenario == 'm_in_n_days':
            return min(Decimal('1'), Decimal(str(self.scenario_m)) / Decimal(str(self.scenario_n)))
        elif self.probability_scenario == 'once_in_n_years':
            return min(Decimal('1'), Decimal('1') / (Decimal(str(self.scenario_n)) * Decimal('365')))
        elif self.probability_scenario == 'm_in_n_years':
            return min(Decimal('1'), Decimal(str(self.scenario_m)) / (Decimal(str(self.scenario_n)) * Decimal('365')))
        return Decimal('0')

    def calculate_overall_impact(self):
        """Calculate overall impact based on financial, operational, and reputational impacts"""
        impacts = []
        
        if self.financial_impact:
            impacts.append(self.financial_impact.impact_value)
        if self.operational_impact:
            impacts.append(self.operational_impact.impact_value)
        if self.reputational_impact:
            impacts.append(self.reputational_impact.impact_value)
        
        if impacts:
            return sum(impacts) / len(impacts)
        else:
            # Fallback to the original impact field if no specific impacts are set
            return self.impact / 100  # Convert from percentage to decimal
    
    def calculate_threat_impact(self):
        """Calculate threat impact: Threat Impact = Probability × Overall Impact × 100"""
        overall_impact = self.calculate_overall_impact()
        return self.probability * overall_impact * 100
    
    def get_impact_details(self, lang='uk'):
        """Get detailed impact information for all three categories"""
        return {
            'financial': {
                'name': self.financial_impact.get_name(lang) if self.financial_impact else _('Not specified'),
                'value': float(self.financial_impact.impact_value) if self.financial_impact else 0,
                'color': self.financial_impact.color if self.financial_impact else '#808080',
                'description': self.financial_impact.get_description(lang) if self.financial_impact else '',
                'criteria': self.financial_impact.get_criteria(lang) if self.financial_impact else '',
                'examples': self.financial_impact.get_examples(lang) if self.financial_impact else ''
            },
            'operational': {
                'name': self.operational_impact.get_name(lang) if self.operational_impact else _('Not specified'),
                'value': float(self.operational_impact.impact_value) if self.operational_impact else 0,
                'color': self.operational_impact.color if self.operational_impact else '#808080',
                'description': self.operational_impact.get_description(lang) if self.operational_impact else '',
                'criteria': self.operational_impact.get_criteria(lang) if self.operational_impact else '',
                'examples': self.operational_impact.get_examples(lang) if self.operational_impact else ''
            },
            'reputational': {
                'name': self.reputational_impact.get_name(lang) if self.reputational_impact else _('Not specified'),
                'value': float(self.reputational_impact.impact_value) if self.reputational_impact else 0,
                'color': self.reputational_impact.color if self.reputational_impact else '#808080',
                'description': self.reputational_impact.get_description(lang) if self.reputational_impact else '',
                'criteria': self.reputational_impact.get_criteria(lang) if self.reputational_impact else '',
                'examples': self.reputational_impact.get_examples(lang) if self.reputational_impact else ''
            }
        }

    def save(self, *args, **kwargs):
        if self.probability_scenario != 'manual':
            self.probability = self.calculate_probability()
        
        # Автоматично розраховуємо вплив загрози якщо встановлені нові impact поля
        if self.financial_impact or self.operational_impact or self.reputational_impact:
            self.impact = self.calculate_threat_impact()
        
        super().save(*args, **kwargs)

    def get_local_name(self, country):
        try:
            return self.translations.get(country=country).name_local
        except ThreatTranslation.DoesNotExist:
            return self.name_local or self.name or self.get_name_by_language('en')

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except ThreatTranslation.DoesNotExist:
            return self.description or self.get_description_by_language('en')

    def get_local_risks(self, country):
        try:
            t = self.translations.get(country=country)
            return t.risks or self.risks or ''
        except ThreatTranslation.DoesNotExist:
            return self.risks or self.get_risks_by_language('en')

    def __str__(self):
        return self.get_name() or self.name or self.name_local or _("Unnamed")

    class Meta:
        verbose_name = _("Threat")
        verbose_name_plural = _("Threats")


class ThreatTranslation(models.Model):
    """Translations of threat for different countries (same as FinancialImpactTranslation)."""
    threat = models.ForeignKey(
        Threat,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Threat")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='threat_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=200, help_text=_("Threat name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))
    risks = models.TextField(_("Risks"), blank=True, help_text=_("Risks description in country's language"))

    class Meta:
        verbose_name = _("Threat Translation")
        verbose_name_plural = _("Threat Translations")
        unique_together = ['threat', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.threat.name or self.threat.name_local} - {self.country.name}: {self.name_local}"


class FinancialImpact(models.Model):
    """Model for Financial Impact levels (same pattern as Revocationstatus: name/code/description + Translations per country)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Level Name"),
        max_length=100,
        blank=True,
        help_text=_("Level name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Level name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Level Code"),
        max_length=50,
        unique=True,
        blank=True,
        help_text=_("Unique code (e.g., low, medium, high)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    criteria = models.TextField(
        _("Criteria"),
        blank=True,
        help_text=_("Criteria, default: English (En). For other languages use Translations inline.")
    )
    examples = models.TextField(
        _("Examples"),
        blank=True,
        help_text=_("Examples, default: English (En). For other languages use Translations inline.")
    )
    min_value = models.DecimalField(
        _("Minimum Value (UAH)"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Minimum financial impact in UAH")
    )
    max_value = models.DecimalField(
        _("Maximum Value (UAH)"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Maximum financial impact in UAH")
    )

    impact_value = models.DecimalField(
        _("Impact Value (E)"),
        max_digits=3,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('1'))
        ],
        help_text=_("Impact value from 0 to 1 for calculations")
    )

    color = models.CharField(
        _("Color"),
        max_length=7,
        default="#000000",
        help_text=_("Color for visualization (hex format)")
    )
    is_active = models.BooleanField(_("Is Active"), default=True)

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:50]

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '').strip()
            self.code = self._slugify_code(base)
            existing = set(
                FinancialImpact.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else FinancialImpact.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (FinancialImpact.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'financial-impact-{self.pk or next_id}'
        super().save(*args, **kwargs)

    def get_name_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except FinancialImpactTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or ''

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except FinancialImpactTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_criteria_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.criteria:
                    return t.criteria
            except FinancialImpactTranslation.DoesNotExist:
                pass
        return self.criteria or ''

    def get_examples_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.examples:
                    return t.examples
            except FinancialImpactTranslation.DoesNotExist:
                pass
        return self.examples or ''

    @classmethod
    def get_by_display_name(cls, name):
        from django.db.models import Q
        if not name:
            return None
        return cls.objects.filter(Q(name=name) | Q(name_local=name) | Q(translations__name_local=name)).distinct().first()

    def get_name(self, lang=None):
        if lang is not None:
            return self.get_name_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except FinancialImpactTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, lang=None):
        if lang is not None:
            return self.get_description_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except FinancialImpactTranslation.DoesNotExist:
                pass
        return self.description or self.get_description_by_language((get_language() or 'en')[:2]) or ''

    def get_local_name(self, country):
        try:
            return self.translations.get(country=country).name_local
        except FinancialImpactTranslation.DoesNotExist:
            return self.name_local or self.name or ''

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except FinancialImpactTranslation.DoesNotExist:
            return self.description or ''

    def get_criteria(self, lang=None):
        if lang is not None:
            return self.get_criteria_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.criteria:
                    return t.criteria
            except FinancialImpactTranslation.DoesNotExist:
                pass
        return self.criteria or self.get_criteria_by_language((get_language() or 'en')[:2]) or ''

    def get_examples(self, lang=None):
        if lang is not None:
            return self.get_examples_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.examples:
                    return t.examples
            except FinancialImpactTranslation.DoesNotExist:
                pass
        return self.examples or self.get_examples_by_language((get_language() or 'en')[:2]) or ''

    def __str__(self):
        return self.get_name() or self.name or self.name_local or _("Unnamed")

    class Meta:
        verbose_name = _("Financial Impact Level")
        verbose_name_plural = _("Financial Impact Levels")
        ordering = ['min_value']


class FinancialImpactTranslation(models.Model):
    """Translations of financial impact level for different countries (same as RevocationstatusTranslation)."""
    financialimpact = models.ForeignKey(
        FinancialImpact,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Financial Impact Level")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='financialimpact_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Level name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )
    criteria = models.TextField(
        _("Criteria"),
        blank=True,
        help_text=_("Criteria in country's language")
    )
    examples = models.TextField(
        _("Examples"),
        blank=True,
        help_text=_("Examples in country's language")
    )

    class Meta:
        verbose_name = _("Financial Impact Level Translation")
        verbose_name_plural = _("Financial Impact Level Translations")
        unique_together = ['financialimpact', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.financialimpact.name or self.financialimpact.name_local} - {self.country.name}: {self.name_local}"


class OperationalImpact(models.Model):
    """Model for Operational Impact levels (same pattern as FinancialImpact: name/code/description/criteria/examples + Translations)."""
    name = models.CharField(
        _("Level Name"),
        max_length=100,
        blank=True,
        help_text=_("Level name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Level name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Level Code"),
        max_length=50,
        unique=True,
        blank=True,
        help_text=_("Unique code (e.g., low, medium, high)")
    )
    description = models.TextField(_("Description"), blank=True, help_text=_("Description, default: English (En). For other languages use Translations inline."))
    criteria = models.TextField(_("Criteria"), blank=True, help_text=_("Criteria, default: English (En). For other languages use Translations inline."))
    examples = models.TextField(_("Examples"), blank=True, help_text=_("Examples, default: English (En). For other languages use Translations inline."))
    min_downtime_hours = models.DecimalField(
        _("Minimum Downtime (hours)"),
        max_digits=5,
        decimal_places=2,
        help_text=_("Minimum system downtime in hours")
    )
    max_downtime_hours = models.DecimalField(
        _("Maximum Downtime (hours)"),
        max_digits=5,
        decimal_places=2,
        help_text=_("Maximum system downtime in hours")
    )
    impact_value = models.DecimalField(
        _("Impact Value (E)"),
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        help_text=_("Impact value from 0 to 1 for calculations")
    )
    color = models.CharField(_("Color"), max_length=7, default="#000000", help_text=_("Color for visualization (hex format)"))
    is_active = models.BooleanField(_("Is Active"), default=True)

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:50]

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '').strip()
            self.code = self._slugify_code(base)
            existing = set(
                OperationalImpact.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else OperationalImpact.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (OperationalImpact.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'operational-impact-{self.pk or next_id}'
        super().save(*args, **kwargs)

    def get_name_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except OperationalImpactTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or ''

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except OperationalImpactTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_criteria_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.criteria:
                    return t.criteria
            except OperationalImpactTranslation.DoesNotExist:
                pass
        return self.criteria or ''

    def get_examples_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.examples:
                    return t.examples
            except OperationalImpactTranslation.DoesNotExist:
                pass
        return self.examples or ''

    @classmethod
    def get_by_display_name(cls, name):
        from django.db.models import Q
        if not name:
            return None
        return cls.objects.filter(Q(name=name) | Q(name_local=name) | Q(translations__name_local=name)).distinct().first()

    def get_name(self, lang=None):
        if lang is not None:
            return self.get_name_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except OperationalImpactTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, lang=None):
        if lang is not None:
            return self.get_description_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except OperationalImpactTranslation.DoesNotExist:
                pass
        return self.description or self.get_description_by_language((get_language() or 'en')[:2]) or ''

    def get_criteria(self, lang=None):
        if lang is not None:
            return self.get_criteria_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.criteria:
                    return t.criteria
            except OperationalImpactTranslation.DoesNotExist:
                pass
        return self.criteria or self.get_criteria_by_language((get_language() or 'en')[:2]) or ''

    def get_examples(self, lang=None):
        if lang is not None:
            return self.get_examples_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.examples:
                    return t.examples
            except OperationalImpactTranslation.DoesNotExist:
                pass
        return self.examples or self.get_examples_by_language((get_language() or 'en')[:2]) or ''

    def get_local_name(self, country):
        try:
            return self.translations.get(country=country).name_local
        except OperationalImpactTranslation.DoesNotExist:
            return self.name_local or self.name or ''

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except OperationalImpactTranslation.DoesNotExist:
            return self.description or ''

    def __str__(self):
        return self.get_name() or self.name or self.name_local or _("Unnamed")

    class Meta:
        verbose_name = _("Operational Impact Level")
        verbose_name_plural = _("Operational Impact Levels")
        ordering = ['min_downtime_hours']


class OperationalImpactTranslation(models.Model):
    """Translations of operational impact level for different countries (same as FinancialImpactTranslation)."""
    operationalimpact = models.ForeignKey(
        OperationalImpact,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Operational Impact Level")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='operationalimpact_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=100, help_text=_("Level name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))
    criteria = models.TextField(_("Criteria"), blank=True, help_text=_("Criteria in country's language"))
    examples = models.TextField(_("Examples"), blank=True, help_text=_("Examples in country's language"))

    class Meta:
        verbose_name = _("Operational Impact Level Translation")
        verbose_name_plural = _("Operational Impact Level Translations")
        unique_together = ['operationalimpact', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.operationalimpact.name or self.operationalimpact.name_local} - {self.country.name}: {self.name_local}"


class ReputationalImpact(models.Model):
    """Model for Reputational Impact levels (same pattern as FinancialImpact: name/code/description/criteria/examples + Translations)."""
    name = models.CharField(
        _("Level Name"),
        max_length=100,
        blank=True,
        help_text=_("Level name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Level name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Level Code"),
        max_length=50,
        unique=True,
        blank=True,
        help_text=_("Unique code (e.g., low, medium, high)")
    )
    description = models.TextField(_("Description"), blank=True, help_text=_("Description, default: English (En). For other languages use Translations inline."))
    criteria = models.TextField(_("Criteria"), blank=True, help_text=_("Criteria, default: English (En). For other languages use Translations inline."))
    examples = models.TextField(_("Examples"), blank=True, help_text=_("Examples, default: English (En). For other languages use Translations inline."))
    impact_value = models.DecimalField(
        _("Impact Value (E)"),
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('1'))],
        help_text=_("Impact value from 0 to 1 for calculations")
    )
    color = models.CharField(_("Color"), max_length=7, default="#000000", help_text=_("Color for visualization (hex format)"))
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
                ReputationalImpact.objects.exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else ReputationalImpact.objects.values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (ReputationalImpact.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'reputational-impact-{self.pk or next_id}'
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

    def get_name_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except ReputationalImpactTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or ''

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except ReputationalImpactTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_criteria_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.criteria:
                    return t.criteria
            except ReputationalImpactTranslation.DoesNotExist:
                pass
        return self.criteria or ''

    def get_examples_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.examples:
                    return t.examples
            except ReputationalImpactTranslation.DoesNotExist:
                pass
        return self.examples or ''

    def get_name(self, lang=None):
        if lang is not None:
            return self.get_name_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except ReputationalImpactTranslation.DoesNotExist:
                pass
        if self.name or self.name_local:
            lang_code = (get_language() or '')[:2].lower()
            return self.name or self.name_local if lang_code == 'en' else self.name_local or self.name
        return self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, lang=None):
        if lang is not None:
            return self.get_description_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except ReputationalImpactTranslation.DoesNotExist:
                pass
        return self.description or self.get_description_by_language((get_language() or 'en')[:2])

    def get_criteria(self, lang=None):
        if lang is not None:
            return self.get_criteria_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.criteria:
                    return t.criteria
            except ReputationalImpactTranslation.DoesNotExist:
                pass
        return self.criteria or self.get_criteria_by_language((get_language() or 'en')[:2])

    def get_examples(self, lang=None):
        if lang is not None:
            return self.get_examples_by_language(lang)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.examples:
                    return t.examples
            except ReputationalImpactTranslation.DoesNotExist:
                pass
        return self.examples or self.get_examples_by_language((get_language() or 'en')[:2])

    def get_local_name(self, country):
        try:
            return self.translations.get(country=country).name_local
        except ReputationalImpactTranslation.DoesNotExist:
            return self.name_local or self.name or self.get_name_by_language('en')

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except ReputationalImpactTranslation.DoesNotExist:
            return self.description or self.get_description_by_language('en')

    def __str__(self):
        return self.get_name() or self.name or self.name_local or ''

    class Meta:
        verbose_name = _("Reputational Impact Level")
        verbose_name_plural = _("Reputational Impact Levels")
        ordering = ['impact_value']


class ReputationalImpactTranslation(models.Model):
    """Translations of reputational impact level for different countries (same as FinancialImpactTranslation)."""
    reputationalimpact = models.ForeignKey(
        ReputationalImpact,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Reputational Impact Level")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='reputationalimpact_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=100, help_text=_("Level name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))
    criteria = models.TextField(_("Criteria"), blank=True, help_text=_("Criteria in country's language"))
    examples = models.TextField(_("Examples"), blank=True, help_text=_("Examples in country's language"))

    class Meta:
        verbose_name = _("Reputational Impact Level Translation")
        verbose_name_plural = _("Reputational Impact Level Translations")
        unique_together = ['reputationalimpact', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.reputationalimpact.name or self.name_local} - {self.country.name}: {self.name_local}"


class Vulnerability(models.Model):
    """Vulnerability with name/code/description + per-country Translations (same pattern as Treatment_status)."""
    asset_group = models.ForeignKey(AssetGroup, on_delete=models.CASCADE)
    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE)
    # Default (English) fields – for other languages use Translations inline
    name = models.TextField(
        _("Vulnerability Name"),
        blank=True,
        help_text=_("Vulnerability name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.TextField(
        _("Local Name"),
        blank=True,
        help_text=_("Vulnerability name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Code"),
        max_length=80,
        unique=True,
        blank=True,
        help_text=_("Unique code (auto-generated from name if empty)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    scope = models.CharField(_("Scope"), max_length=255, blank=True, default="", help_text=_("Scope, default. For other languages use Translations inline."))
    risk_mitigation_controls = models.TextField(_("Risk Mitigation Controls"), blank=True, default="", help_text=_("Default. For other languages use Translations inline."))
    pci_dss_requirement = models.TextField(_("PCI DSS Requirement"), blank=True, null=True, help_text=_("Default. For other languages use Translations inline."))
    iso27001_requirement = models.TextField(_("ISO 27001 Requirement"), blank=True, null=True, help_text=_("Default. For other languages use Translations inline."))
    note = models.TextField(_("Note"), blank=True, null=True, help_text=_("Default. For other languages use Translations inline."))
    is_active = models.BooleanField(_("Is Active"), default=True)
    threats = models.ManyToManyField('Threat', blank=True)
    extra_translations = models.JSONField(default=dict, blank=True, help_text=_("Translations for additional languages: {scope: {de: '...'}, vulnerability: {...}, ...}"))

    TRANSLATABLE_FIELDS = ('scope', 'vulnerability', 'description', 'risk_mitigation_controls', 'pci_dss_requirement', 'iso27001_requirement', 'note')

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
        for country_code in LANGUAGE_COUNTRY_MAP.get(lang, []):
            try:
                return Country.objects.get(code__iexact=country_code)
            except Country.DoesNotExist:
                continue
        return None

    def get_translated_value(self, field, lang):
        """Get value for field+lang: Translation for country from lang, else default on model, else extra_translations."""
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if field == 'vulnerability':
                    if t.name_local:
                        return t.name_local
                else:
                    val = getattr(t, field, None)
                    if val is not None and str(val).strip():
                        return val
            except VulnerabilityTranslation.DoesNotExist:
                pass
        if field == 'vulnerability':
            return self.name or ''
        default_val = getattr(self, field, None)
        if default_val is not None and str(default_val).strip():
            return default_val
        ext = (self.extra_translations or {}).get(field) or {}
        return ext.get(lang, '') or ''

    def set_translated_value(self, field, lang, value):
        """Set value for field+lang: stored in extra_translations (for languages without Translation row)."""
        ext = dict(self.extra_translations or {})
        if field not in ext:
            ext[field] = {}
        ext[field][lang] = value or ''
        self.extra_translations = ext

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))[:80]
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:80]

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '')[:80].strip()
            self.code = self._slugify_code(base)
            if self.code:
                existing = set(
                    Vulnerability.objects.exclude(pk=self.pk).values_list('code', flat=True)
                    if self.pk else Vulnerability.objects.values_list('code', flat=True)
                )
                if self.code in existing:
                    from django.db.models import Max
                    next_id = (Vulnerability.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                    self.code = f'vuln-{self.pk or next_id}'
            # Ensure we never persist empty code (unique constraint would reject duplicate '')
            if not self.code or not self.code.strip():
                from django.db.models import Max
                import uuid
                next_id = (Vulnerability.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                existing = set(
                    Vulnerability.objects.exclude(pk=self.pk).values_list('code', flat=True)
                    if self.pk else Vulnerability.objects.values_list('code', flat=True)
                )
                self.code = f'vuln-{self.pk or next_id}'
                while self.code in existing:
                    self.code = f'vuln-{uuid.uuid4().hex[:12]}'
                    existing.add(self.code)
        super().save(*args, **kwargs)

    def get_name_by_language(self, lang):
        val = self.get_translated_value('vulnerability', lang)
        return val or self.name or _("Unnamed")

    def get_description_by_language(self, lang):
        val = self.get_translated_value('description', lang)
        return val or self.description or ""

    def get_name(self, language=None):
        if language is not None:
            return self.get_name_by_language(language)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except VulnerabilityTranslation.DoesNotExist:
                pass
        if self.name or self.name_local:
            lang_code = (get_language() or '')[:2].lower()
            return (self.name or self.name_local) if lang_code == 'en' else (self.name_local or self.name)
        return self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, language=None):
        if language is not None:
            return self.get_description_by_language(language)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except VulnerabilityTranslation.DoesNotExist:
                pass
        return self.description or self.get_description_by_language((get_language() or 'en')[:2])

    def get_local_name(self, country):
        try:
            t = self.translations.get(country=country)
            if t.name_local:
                return t.name_local
        except VulnerabilityTranslation.DoesNotExist:
            pass
        return self.name or self.get_name_by_language('en')

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except VulnerabilityTranslation.DoesNotExist:
            return self.description or self.get_description_by_language('en')

    def __str__(self):
        asset_type_name = self.asset_type.name_local or self.asset_type.name or "Unnamed Asset Type" if self.asset_type_id else "—"
        name_display = (self.get_name() or self.name or "")[:50]
        return f"{self.asset_group.abbreviation if self.asset_group_id else '—'}/{asset_type_name} - {name_display}"

    def get_localized_field(self, field_name, lang):
        val = self.get_translated_value(field_name, lang)
        return val or self.get_translated_value(field_name, 'uk') or self.get_translated_value(field_name, 'en') or ''


class VulnerabilityTranslation(models.Model):
    """Translations of vulnerability for different countries."""
    vulnerability = models.ForeignKey(
        Vulnerability,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Vulnerability")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='vulnerability_translations',
        verbose_name=_("Country")
    )
    name_local = models.TextField(_("Local Name"), blank=True, help_text=_("Vulnerability name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))
    scope = models.TextField(_("Scope"), blank=True, help_text=_("Scope in country's language"))
    risk_mitigation_controls = models.TextField(_("Risk Mitigation Controls"), blank=True, help_text=_("Risk mitigation controls in country's language"))
    pci_dss_requirement = models.TextField(_("PCI DSS Requirement"), blank=True, null=True)
    iso27001_requirement = models.TextField(_("ISO 27001 Requirement"), blank=True, null=True)
    note = models.TextField(_("Note"), blank=True, null=True)

    class Meta:
        verbose_name = _("Vulnerability Translation")
        verbose_name_plural = _("Vulnerability Translations")
        unique_together = ['vulnerability', 'country']
        ordering = ['country__name']

    def __str__(self):
        name = (self.vulnerability.name or self.name_local or "")[:50]
        return f"{name} - {self.country.name}: {self.name_local[:50] if self.name_local else ''}"


class RiskLevel(models.Model):
    """Risk level (same pattern as Revocationstatus: name/code + Translations per country)."""
    name = models.CharField(
        _("Level Name"),
        max_length=100,
        blank=True,
        help_text=_("Level name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Level name in local language (use Translations inline for per-country names)")
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='risk_levels',
        verbose_name=_("Company"),
        help_text=_("Leave empty for organization-wide level")
    )
    code = models.CharField(
        _("Level Code"),
        max_length=50,
        blank=True,
        help_text=_("Code unique per company (e.g., low, medium, high, critical)")
    )
    min_value = models.IntegerField(
        _("Minimum Value"),
        validators=[MinValueValidator(0), MaxValueValidator(200)],
        help_text=_("Minimum value for this risk level (0 to 200)")
    )
    max_value = models.IntegerField(
        _("Maximum Value"),
        validators=[MinValueValidator(0), MaxValueValidator(200)],
        help_text=_("Maximum value for this risk level (0 to 200)")
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
                RiskLevel.objects.filter(company_id=self.company_id).exclude(pk=self.pk).values_list('code', flat=True)
                if self.pk else RiskLevel.objects.filter(company_id=self.company_id).values_list('code', flat=True)
            )
            if not self.code or self.code in existing:
                from django.db.models import Max
                next_id = (RiskLevel.objects.aggregate(m=Max('id'))['m'] or 0) + 1
                self.code = f'risk-level-{self.pk or next_id}'
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

    def get_name_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except RiskLevelTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or _("Unnamed")

    @classmethod
    def get_by_display_name(cls, name, company_id=None):
        """Return first RiskLevel whose name or any translation name_local equals name."""
        from django.db.models import Q
        qs = cls.objects.filter(Q(name=name) | Q(translations__name_local=name))
        if company_id:
            qs = qs.filter(Q(company__isnull=True) | Q(company_id=company_id))
        else:
            qs = qs.filter(company__isnull=True)
        qs = qs.distinct()
        return qs.first()

    def get_name(self, language=None):
        if language is not None:
            return self.get_name_by_language(language)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except RiskLevelTranslation.DoesNotExist:
                pass
        if self.name or self.name_local:
            lang_code = (get_language() or '')[:2].lower()
            return self.name or self.name_local if lang_code == 'en' else self.name_local or self.name
        return self.get_name_by_language((get_language() or 'en')[:2])

    def get_local_name(self, country):
        try:
            return self.translations.get(country=country).name_local
        except RiskLevelTranslation.DoesNotExist:
            return self.name_local or self.name or self.get_name_by_language('en')

    def __str__(self):
        return f"{self.get_name()} ({self.min_value} - {self.max_value})"

    class Meta:
        verbose_name = _("Risk Level")
        verbose_name_plural = _("Risk Levels")
        ordering = ['min_value']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='app_risk_risklevel_company_code_uniq',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.min_value > self.max_value:
            raise ValidationError(_("Minimum value cannot be greater than maximum value."))


class RiskLevelTranslation(models.Model):
    """Translations of risk level for different countries (same as RevocationstatusTranslation)."""
    risklevel = models.ForeignKey(
        RiskLevel,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Risk Level")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='risklevel_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Level name in country's language")
    )

    class Meta:
        verbose_name = _("Risk Level Translation")
        verbose_name_plural = _("Risk Level Translations")
        unique_together = ['risklevel', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.risklevel.name or self.name_local} - {self.country.name}: {self.name_local}"


class Treatment_type(models.Model):
    """Treatment Type with name/code/description + per-country Translations (same pattern as Treatment_status)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Treatment Type Name"),
        max_length=200,
        blank=True,
        help_text=_("Type name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=200,
        blank=True,
        help_text=_("Type name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(_("Code"), max_length=20, unique=True)
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    color = models.CharField(_("Color"), max_length=7, default="#000000",
                            help_text=_("Color in HEX format, e.g. #FF0000"))

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
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
            except TreatmentTypeTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or _("Unnamed")

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except TreatmentTypeTranslation.DoesNotExist:
                pass
        return self.description or ""

    @classmethod
    def get_by_display_name(cls, name):
        """Return first Treatment_type whose code, name, or any translation name_local equals name."""
        from django.db.models import Q
        if not name:
            return None
        qs = cls.objects.filter(
            Q(code=name) | Q(name=name) | Q(name_local=name) | Q(translations__name_local=name)
        ).distinct()
        return qs.first()

    def get_name(self, language=None):
        if language is not None:
            return self.get_name_by_language(language)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except TreatmentTypeTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, language=None):
        if language is not None:
            return self.get_description_by_language(language)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except TreatmentTypeTranslation.DoesNotExist:
                pass
        return self.description or self.get_description_by_language((get_language() or 'en')[:2]) or ""

    def get_local_name(self, country):
        try:
            t = self.translations.get(country=country)
            if t.name_local:
                return t.name_local
        except TreatmentTypeTranslation.DoesNotExist:
            pass
        return self.name or self.name_local or _("Unnamed")

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except TreatmentTypeTranslation.DoesNotExist:
            return self.description or ''

    def __str__(self):
        return self.get_name() or self.name or self.name_local or _("Unnamed")

    class Meta:
        verbose_name = _("Treatment Type")
        verbose_name_plural = _("Treatment Types")


class TreatmentTypeTranslation(models.Model):
    """Translations of treatment type for different countries."""
    treatment_type = models.ForeignKey(
        Treatment_type,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Treatment Type")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='treatment_type_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=200, help_text=_("Type name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))

    class Meta:
        verbose_name = _("Treatment Type Translation")
        verbose_name_plural = _("Treatment Type Translations")
        unique_together = ['treatment_type', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.treatment_type.name or self.treatment_type.name_local} - {self.country.name}: {self.name_local}"


class Treatment_status(models.Model):
    """Treatment Status with name/code/description + per-country Translations (same pattern as Threat/RiskLevel)."""
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Treatment Status Name"),
        max_length=200,
        blank=True,
        help_text=_("Status name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=200,
        blank=True,
        help_text=_("Status name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(_("Code"), max_length=20, unique=True)
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    color = models.CharField(_("Color"), max_length=7, default="#000000",
                             help_text=_("Color in HEX format, e.g. #FF0000"))

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
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
            except TreatmentStatusTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or _("Unnamed")

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except TreatmentStatusTranslation.DoesNotExist:
                pass
        return self.description or ""

    @classmethod
    def get_by_display_name(cls, name):
        """Return first Treatment_status whose code, name, or any translation name_local equals name."""
        from django.db.models import Q
        if not name:
            return None
        qs = cls.objects.filter(
            Q(code=name) | Q(name=name) | Q(name_local=name) | Q(translations__name_local=name)
        ).distinct()
        return qs.first()

    def get_name(self, language=None):
        if language is not None:
            return self.get_name_by_language(language)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except TreatmentStatusTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, language=None):
        if language is not None:
            return self.get_description_by_language(language)
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except TreatmentStatusTranslation.DoesNotExist:
                pass
        return self.description or self.get_description_by_language((get_language() or 'en')[:2]) or ""

    def get_local_name(self, country):
        try:
            t = self.translations.get(country=country)
            if t.name_local:
                return t.name_local
        except TreatmentStatusTranslation.DoesNotExist:
            pass
        return self.name or self.name_local or _("Unnamed")

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except TreatmentStatusTranslation.DoesNotExist:
            return self.description or ''

    def __str__(self):
        return self.get_name() or self.name or self.name_local or _("Unnamed")

    class Meta:
        verbose_name = _("Treatment Status")
        verbose_name_plural = _("Treatment Statuses")


class TreatmentStatusTranslation(models.Model):
    """Translations of treatment status for different countries."""
    treatment_status = models.ForeignKey(
        Treatment_status,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Treatment Status")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='treatment_status_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=200, help_text=_("Status name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))

    class Meta:
        verbose_name = _("Treatment Status Translation")
        verbose_name_plural = _("Treatment Status Translations")
        unique_together = ['treatment_status', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.treatment_status.name or self.treatment_status.name_local} - {self.country.name}: {self.name_local}"


class ResidualRiskLevel(models.Model):
    """Residual risk level with name/description + per-country Translations (same pattern as TreatmentEffectiveness)."""
    name = models.CharField(_("Name"), max_length=100, blank=True, help_text=_("Default name (e.g. English). Use Translations for other languages."))
    name_local = models.CharField(_("Local Name"), max_length=100, blank=True)
    description = models.TextField(_("Description"), blank=True, default="")
    value = models.IntegerField(_("Value"), validators=[MinValueValidator(0), MaxValueValidator(100)])
    color = models.CharField(_("Color"), max_length=7, default="#000000")

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
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
            except ResidualRiskLevelTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or _("Unnamed")

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except ResidualRiskLevelTranslation.DoesNotExist:
                pass
        return self.description or ""

    def get_name(self, language=None):
        if language is not None:
            return self.get_name_by_language(language)
        return self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, language=None):
        if language is not None:
            return self.get_description_by_language(language)
        return self.get_description_by_language((get_language() or 'en')[:2]) or ""

    @classmethod
    def get_by_display_name(cls, name):
        """Return first ResidualRiskLevel whose name or any translation name_local equals name."""
        from django.db.models import Q
        qs = cls.objects.filter(Q(name=name) | Q(name_local=name) | Q(translations__name_local=name)).distinct()
        return qs.first()

    def __str__(self):
        return self.get_name() or self.name or self.name_local or _("Unnamed")

    class Meta:
        verbose_name = _("Residual Risk Level")
        verbose_name_plural = _("Residual Risk Levels")


class ResidualRiskLevelTranslation(models.Model):
    """Translations of residual risk level for different countries."""
    residual_risk_level = models.ForeignKey(
        ResidualRiskLevel,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Residual Risk Level")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='residualrisklevel_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=200, help_text=_("Name in country's language"))
    description = models.TextField(_("Description"), blank=True, default="")

    class Meta:
        verbose_name = _("Residual Risk Level Translation")
        verbose_name_plural = _("Residual Risk Level Translations")
        unique_together = ['residual_risk_level', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.residual_risk_level.name or self.residual_risk_level.name_local} - {self.country.name}: {self.name_local}"

class TreatmentEffectiveness(models.Model):
    """Treatment effectiveness level with name/description + per-country Translations."""
    name = models.CharField(_("Name"), max_length=100, blank=True, help_text=_("Default name (e.g. English). Use Translations for other languages."))
    name_local = models.CharField(_("Local Name"), max_length=100, blank=True)
    description = models.TextField(_("Description"), blank=True, default="")
    value = models.IntegerField(_("Value"), validators=[MinValueValidator(0), MaxValueValidator(100)])
    color = models.CharField(_("Color"), max_length=7, default="#000000")

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
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
            except TreatmentEffectivenessTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or _("Unnamed")

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except TreatmentEffectivenessTranslation.DoesNotExist:
                pass
        return self.description or ""

    def get_name(self, language=None):
        if language is not None:
            return self.get_name_by_language(language)
        return self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, language=None):
        if language is not None:
            return self.get_description_by_language(language)
        return self.get_description_by_language((get_language() or 'en')[:2]) or ""

    class Meta:
        verbose_name = _("Treatment Effectiveness")
        verbose_name_plural = _("Treatment Effectiveness Levels")


class TreatmentEffectivenessTranslation(models.Model):
    """Translations of treatment effectiveness for different countries."""
    treatment_effectiveness = models.ForeignKey(
        TreatmentEffectiveness,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Treatment Effectiveness")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='treatmenteffectiveness_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=100, help_text=_("Name in country's language"))
    description = models.TextField(_("Description"), blank=True, default="")

    class Meta:
        verbose_name = _("Treatment Effectiveness Translation")
        verbose_name_plural = _("Treatment Effectiveness Translations")
        unique_together = ['treatment_effectiveness', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.treatment_effectiveness.name or self.treatment_effectiveness.name_local} - {self.country.name}: {self.name_local}"


class TreatmentPriority(models.Model):
    """Treatment priority level with name/description + per-country Translations."""
    name = models.CharField(_("Name"), max_length=100, blank=True, help_text=_("Default name (e.g. English). Use Translations for other languages."))
    name_local = models.CharField(_("Local Name"), max_length=100, blank=True)
    description = models.TextField(_("Description"), blank=True, default="")
    value = models.IntegerField(_("Value"), validators=[MinValueValidator(1), MaxValueValidator(5)])
    color = models.CharField(_("Color"), max_length=7, default="#000000")

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
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
            except TreatmentPriorityTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or _("Unnamed")

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except TreatmentPriorityTranslation.DoesNotExist:
                pass
        return self.description or ""

    def get_name(self, language=None):
        if language is not None:
            return self.get_name_by_language(language)
        return self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, language=None):
        if language is not None:
            return self.get_description_by_language(language)
        return self.get_description_by_language((get_language() or 'en')[:2]) or ""

    class Meta:
        verbose_name = _("Treatment Priority")
        verbose_name_plural = _("Treatment Priorities")


class TreatmentPriorityTranslation(models.Model):
    """Translations of treatment priority for different countries."""
    treatment_priority = models.ForeignKey(
        TreatmentPriority,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Treatment Priority")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='treatmentpriority_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=100, help_text=_("Name in country's language"))
    description = models.TextField(_("Description"), blank=True, default="")

    class Meta:
        verbose_name = _("Treatment Priority Translation")
        verbose_name_plural = _("Treatment Priority Translations")
        unique_together = ['treatment_priority', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.treatment_priority.name or self.treatment_priority.name_local} - {self.country.name}: {self.name_local}"


class MonitoringFrequency(models.Model):
    """Monitoring frequency with name/description + per-country Translations."""
    name = models.CharField(_("Name"), max_length=100, blank=True, help_text=_("Default name (e.g. English). Use Translations for other languages."))
    name_local = models.CharField(_("Local Name"), max_length=100, blank=True)
    description = models.TextField(_("Description"), blank=True, default="")
    days = models.IntegerField(_("Days between reviews"))
    color = models.CharField(_("Color"), max_length=7, default="#000000")

    def _country_for_lang(self, lang):
        from app_conf.models import Country
        lang = (lang or get_language() or '')[:2].lower()
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
            except MonitoringFrequencyTranslation.DoesNotExist:
                pass
        return self.name_local or self.name or _("Unnamed")

    def get_description_by_language(self, lang):
        country = self._country_for_lang(lang)
        if country:
            try:
                t = self.translations.get(country=country)
                if t.description:
                    return t.description
            except MonitoringFrequencyTranslation.DoesNotExist:
                pass
        return self.description or ""

    def get_name(self, language=None):
        if language is not None:
            return self.get_name_by_language(language)
        return self.get_name_by_language((get_language() or 'en')[:2])

    def get_description(self, language=None):
        if language is not None:
            return self.get_description_by_language(language)
        return self.get_description_by_language((get_language() or 'en')[:2]) or ""

    class Meta:
        verbose_name = _("Monitoring Frequency")
        verbose_name_plural = _("Monitoring Frequencies")


class MonitoringFrequencyTranslation(models.Model):
    """Translations of monitoring frequency for different countries."""
    monitoring_frequency = models.ForeignKey(
        MonitoringFrequency,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Monitoring Frequency")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='monitoringfrequency_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=100, help_text=_("Name in country's language"))
    description = models.TextField(_("Description"), blank=True, default="")

    class Meta:
        verbose_name = _("Monitoring Frequency Translation")
        verbose_name_plural = _("Monitoring Frequency Translations")
        unique_together = ['monitoring_frequency', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.monitoring_frequency.name or self.monitoring_frequency.name_local} - {self.country.name}: {self.name_local}"


class AssetVulnerability(models.Model):
    asset = models.ForeignKey(InformationAsset, on_delete=models.CASCADE)
    vulnerability = models.ForeignKey(Vulnerability, on_delete=models.CASCADE)
    modified_at = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=10, choices=[('No', 'No'), ('Undefined', 'Undefined'), ('Yes', 'Yes')])
    comment = models.TextField(blank=True)

    @staticmethod
    def get_user_full_name(user):
        if user:
            return f"{user.first_name} {user.last_name}".strip() or user.username
        return ''

    class Meta:
        unique_together = ('asset', 'vulnerability')


class ManualRiskLevelOverride(models.Model):
    """
    Model to store manual risk level overrides for specific asset-vulnerability-threat combinations
    """
    asset = models.ForeignKey(InformationAsset, on_delete=models.CASCADE, verbose_name=_("Asset"))
    vulnerability = models.ForeignKey(Vulnerability, on_delete=models.CASCADE, verbose_name=_("Vulnerability"))
    threat = models.ForeignKey(Threat, on_delete=models.CASCADE, verbose_name=_("Threat"), null=True, blank=True)
    manual_risk_level = models.ForeignKey(RiskLevel, on_delete=models.CASCADE, verbose_name=_("Manual Risk Level"))
    justification = models.TextField(_("Justification"), blank=True, help_text=_("Reason for manual override"))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Created By"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Updated By"), related_name='updated_risk_overrides')
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    
    def __str__(self):
        threat_name = self.threat.get_name() if self.threat else "No Threat"
        return f"{self.asset.name} - {self.vulnerability.get_name()} - {threat_name} -> {self.manual_risk_level.get_name()}"
    
    class Meta:
        verbose_name = _("Manual Risk Level Override")
        verbose_name_plural = _("Manual Risk Level Overrides")
        unique_together = ('asset', 'vulnerability', 'threat')
        ordering = ['-created_at']



class AccessRisk(models.Model):
    """
    Model for managing comprehensive access rights to Risk Management module
    """
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE, 
        verbose_name=_("Group")
    )
    
    # Risk Assessment permissions
    has_access_assessment = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Risk Assessment")
    )
    can_edit_assessment = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Risk Assessment")
    )
    can_config_assessment = models.BooleanField(
        default=False, 
        verbose_name=_("Can configure Risk Assessment")
    )

    
    # Risk Report permissions
    has_access_report = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Risk Report")
    )
    can_add_report = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Risk Report")
    )
    can_edit_report = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Risk Report")
    )
    can_delete_report = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Risk Report")
    )

    # Risk Configuration permissions
    has_access_config = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Risk Configuration")
    )
    can_add_config = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Risk Configuration")
    )
    can_edit_config = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Risk Configuration")
    )
    can_delete_config = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Risk Configuration")
    )

    
    # Common fields
    companies = models.ManyToManyField(
        Company, 
        blank=True, 
        related_name='access_risk', 
        verbose_name=_("Companies")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )

    class Meta:
        verbose_name = _("Access to Risk Management")
        verbose_name_plural = _("Access to Risk Management")
        unique_together = [('group',)]

    def __str__(self):
        return f"{self.group.name} - Assessment: {self.has_access_assessment}, Report: {self.has_access_report}, Config: {self.has_access_config}"


class RiskTreatment(models.Model):
    asset = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.CASCADE,
        related_name='risk_treatments',
        null=True,
        blank=True
    )
    software_register = models.ForeignKey(
        'app_asset.SoftwareRegister',
        on_delete=models.CASCADE,
        related_name='risk_treatments',
        null=True,
        blank=True
    )
    external_media_register = models.ForeignKey(
        'app_asset.ExternalMediaRegister',
        on_delete=models.CASCADE,
        related_name='risk_treatments',
        null=True,
        blank=True
    )
    vulnerability = models.ForeignKey('Vulnerability', on_delete=models.CASCADE)
    threats = models.TextField(blank=True, verbose_name=_("Threats with Risk Levels"))
    highest_risk_level = models.ForeignKey('RiskLevel', on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='highest_risk_treatments', verbose_name=_("Risk Level"))
    risk_mitigation_controls = models.ForeignKey(
        'Vulnerability',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='risk_treatments',
        verbose_name=_("Risk Mitigation Controls")
    )
    treatment_type = models.ForeignKey(
        'Treatment_type',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='risk_treatments',
        verbose_name=_("Treatment Type")
    )
    description = models.TextField(blank=True)
    responsible = models.CharField(max_length=255, blank=True)
    deadline = models.DateField(null=True, blank=True)
    status = models.ForeignKey(
        'Treatment_status',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='risk_treatments',
        verbose_name=_("Status")
    )
    last_modified = models.DateTimeField(auto_now=True, verbose_name=_("Last Modified"))
    last_modified_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='modified_risk_treatments', verbose_name=_("Last Modified By"))

    # 1. Residual Risk Assessment
    residual_risk_level = models.ForeignKey(
        'RiskLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='residual_risk_treatments',
        verbose_name=_("Residual Risk Level")
    )
    residual_risk_justification = models.TextField(blank=True, verbose_name=_("Residual Risk Justification"))

    # 2. Treatment Effectiveness
    effectiveness = models.ForeignKey(
        'TreatmentEffectiveness',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='risk_treatments',
        verbose_name=_("Treatment Effectiveness")
    )
    effectiveness_metrics = models.TextField(blank=True, verbose_name=_("Effectiveness Metrics"))
    effectiveness_evaluation_date = models.DateField(null=True, blank=True, verbose_name=_("Effectiveness Evaluation Date"))

    # 3. Cost and Resources
    implementation_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Implementation Cost")
    )
    annual_maintenance_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Annual Maintenance Cost")
    )
    required_resources = models.TextField(blank=True, verbose_name=_("Required Resources"))
    roi_assessment = models.TextField(blank=True, verbose_name=_("ROI Assessment"))

    # 4. Priority
    priority = models.ForeignKey(
        'TreatmentPriority',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='risk_treatments',
        verbose_name=_("Priority")
    )
    priority_justification = models.TextField(blank=True, verbose_name=_("Priority Justification"))

    # 5. Monitoring and Review
    monitoring_frequency = models.ForeignKey(
        'MonitoringFrequency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='risk_treatments',
        verbose_name=_("Monitoring Frequency")
    )
    next_review_date = models.DateField(null=True, blank=True, verbose_name=_("Next Review Date"))
    monitoring_responsible = models.ManyToManyField(
        get_user_model(),
        blank=True,
        related_name='monitoring_risk_treatments',
        verbose_name=_("Monitoring Responsible")
    )
    last_review_date = models.DateField(null=True, blank=True, verbose_name=_("Last Review Date"))
    review_notes = models.TextField(blank=True, verbose_name=_("Review Notes"))

    # 6. Dependencies
    dependencies = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='dependent_treatments',
        verbose_name=_("Dependencies")
    )
    affected_assets = models.ManyToManyField(
        'app_asset.InformationAsset',
        blank=True,
        related_name='affected_by_treatments',
        verbose_name=_("Affected Assets")
    )
    prerequisites = models.TextField(blank=True, verbose_name=_("Prerequisites"))

    # 7. Approval
    approved_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_risk_treatments',
        verbose_name=_("Approved By")
    )
    approval_date = models.DateField(null=True, blank=True, verbose_name=_("Approval Date"))
    approval_notes = models.TextField(blank=True, verbose_name=_("Approval Notes"))

    def __str__(self):
        if self.asset_id:
            entity_name = self.asset.name
        elif self.software_register_id:
            entity_name = self.software_register.name
        elif self.external_media_register_id:
            entity_name = self.external_media_register.name
        else:
            entity_name = str(_('Unknown'))
        return f"Risk Treatment for {entity_name} - {self.vulnerability.get_name()}"

    def get_risk_level_display(self):
        return self.risk_level.get_name() if self.risk_level else _('Undefined')

    def calculate_next_review_date(self):
        if self.monitoring_frequency and self.last_review_date:
            return self.last_review_date + timedelta(days=self.monitoring_frequency.days)
        return None

    def save(self, *args, **kwargs):
        # Get user from kwargs if provided
        user = kwargs.pop('user', None)
        if user:
            self._current_user = user
        
        # Track changes for history
        is_new = self.pk is None
        if not is_new:
            try:
                old_instance = RiskTreatment.objects.get(pk=self.pk)
                self._track_field_changes(old_instance)
            except RiskTreatment.DoesNotExist:
                pass
        
        if self.last_review_date and self.monitoring_frequency:
            self.next_review_date = self.calculate_next_review_date()
        super().save(*args, **kwargs)
    
    def _track_field_changes(self, old_instance):
        """Track changes to specific fields and create history records"""
        fields_to_track = {
            'status': 'status',
            'highest_risk_level': 'highest_risk_level',
            'treatment_type': 'treatment_type',
            'residual_risk_level': 'residual_risk_level',
        }
        
        for field_name, field_obj in fields_to_track.items():
            old_value = getattr(old_instance, field_obj)
            new_value = getattr(self, field_obj)
            
            if old_value != new_value:
                # Get display names for the values
                old_display = self._get_field_display_name(field_name, old_value)
                new_display = self._get_field_display_name(field_name, new_value)
                
                # Create history record
                RiskTreatmentHistory.objects.create(
                    treatment=self,
                    field_name=field_name,
                    old_value=old_display,
                    new_value=new_display,
                    old_value_id=old_value.id if old_value else None,
                    new_value_id=new_value.id if new_value else None,
                    changed_by=getattr(self, '_current_user', None),
                    change_reason=getattr(self, '_change_comment', '')
                )
    
    def _get_field_display_name(self, field_name, value):
        """Get display name for a field value"""
        if value is None:
            return _('Not Set')
        
        # Try to get localized name first
        if hasattr(value, 'get_name'):
            return value.get_name()
        elif hasattr(value, 'name'):
            return value.name
        elif hasattr(value, '__str__'):
            return str(value)
        else:
            return str(value)

    class Meta:
        verbose_name = _("Risk Treatment")
        verbose_name_plural = _("Risk Treatments")
        ordering = ['-priority__value', 'next_review_date']


class RiskTreatmentAttachment(models.Model):
    """Модель для файлів, прикріплених до Risk Treatment"""
    treatment = models.ForeignKey(
        RiskTreatment,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Risk Treatment")
    )
    file = models.FileField(
        upload_to='risk_treatments/attachments/%Y/%m/%d/',
        verbose_name=_("File")
    )
    filename = models.CharField(
        max_length=255,
        verbose_name=_("Filename")
    )
    file_size = models.IntegerField(
        verbose_name=_("File Size (bytes)")
    )
    file_type = models.CharField(
        max_length=100,
        verbose_name=_("File Type")
    )
    uploaded_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Uploaded By")
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Uploaded At")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )

    def __str__(self):
        return f"{self.filename} - {self.treatment}"

    def get_file_size_display(self):
        """Повертає розмір файлу в читабельному форматі"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.1f} GB"

    @property
    def file_url(self):
        """Return the URL for the file"""
        if self.file:
            return self.file.url
        return None

    class Meta:
        verbose_name = _("Risk Treatment Attachment")
        verbose_name_plural = _("Risk Treatment Attachments")
        ordering = ['-uploaded_at']

    @property
    def get_treatment_type_display_with_color(self):
        if self.treatment_type:
            return {
                'name': self.treatment_type.get_name(),
                'color': self.treatment_type.color
            }
        return {
            'name': _('Undefined'),
            'color': '#808080'
        }

    @property
    def get_status_display_with_color(self):
        if self.status:
            return {
                'name': self.status.get_name(),
                'color': self.status.color
            }
        return {
            'name': _('Undefined'),
            'color': '#808080'
        }

    @property
    def get_residual_risk_display_with_color(self):
        if self.residual_risk_level:
            return {
                'name': self.residual_risk_level.get_name(),
                'color': self.residual_risk_level.color,
                'value': self.residual_risk_level.max_value
            }
        return {
            'name': _('Undefined'),
            'color': '#808080',
            'value': None
        }

    @property
    def get_effectiveness_display_with_color(self):
        if self.effectiveness:
            return {
                'name': self.effectiveness.get_name(),
                'color': self.effectiveness.color,
                'value': self.effectiveness.value
            }
        return {
            'name': _('Undefined'),
            'color': '#808080',
            'value': None
        }

    @property
    def get_priority_display_with_color(self):
        if self.priority:
            return {
                'name': self.priority.get_name(),
                'color': self.priority.color,
                'value': self.priority.value
            }
        return {
            'name': _('Undefined'),
            'color': '#808080',
            'value': None
        }


class RiskTreatmentHistory(models.Model):
    """
    Model to track changes to RiskTreatment fields: Status, Risk Level, Treatment Type, and Treatment Status
    """
    FIELD_CHOICES = [
        ('status', _('Status')),
        ('highest_risk_level', _('Risk Level')),
        ('treatment_type', _('Treatment Type')),
        ('residual_risk_level', _('Residual Risk Level')),
    ]
    
    treatment = models.ForeignKey(
        RiskTreatment,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name=_("Risk Treatment")
    )
    field_name = models.CharField(
        max_length=50,
        choices=FIELD_CHOICES,
        verbose_name=_("Field Name")
    )
    old_value = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Old Value")
    )
    new_value = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("New Value")
    )
    old_value_display = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Old Value Display")
    )
    new_value_display = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("New Value Display")
    )
    old_value_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Old Value ID")
    )
    new_value_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("New Value ID")
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Changed At")
    )
    changed_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Changed By")
    )
    change_reason = models.TextField(
        blank=True,
        verbose_name=_("Change Reason")
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("IP Address")
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("User Agent")
    )
    
    class Meta:
        verbose_name = _("Risk Treatment History")
        verbose_name_plural = _("Risk Treatment History")
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['treatment', 'field_name']),
            models.Index(fields=['changed_at']),
            models.Index(fields=['changed_by']),
        ]
    
    def __str__(self):
        return f"{self.treatment} - {self.get_field_name_display()}: {self.old_value} → {self.new_value}"
    
    def get_formatted_timestamp(self):
        return self.changed_at.strftime('%Y-%m-%d %H:%M:%S')
    
    def get_changed_by_name(self):
        if self.changed_by:
            return self.changed_by.get_full_name() or self.changed_by.username
        return _('System')


class RiskAssessmentAuditLog(models.Model):
    """
    Модель для детального аудиту всіх дій в Risk Assessment модулі
    """
    ACTION_TYPES = [
        ('VIEW', 'View'),
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('EXPORT', 'Export'),
        ('ACCESS', 'Access'),
        ('ERROR', 'Error'),
        ('SECURITY', 'Security'),
    ]
    
    SEVERITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))
    user = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name=_("User")
    )
    action_type = models.CharField(
        max_length=20, 
        choices=ACTION_TYPES,
        verbose_name=_("Action Type")
    )
    action_name = models.CharField(
        max_length=100,
        verbose_name=_("Action Name")
    )
    asset = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Asset")
    )
    object_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Object Type")
    )
    object_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Object ID")
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_("IP Address")
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("User Agent")
    )
    request_path = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_("Request Path")
    )
    request_method = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name=_("Request Method")
    )
    data_before = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Data Before")
    )
    data_after = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Data After")
    )
    additional_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Additional Data")
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_LEVELS,
        default='LOW',
        verbose_name=_("Severity")
    )
    success = models.BooleanField(
        default=True,
        verbose_name=_("Success")
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Error Message")
    )
    duration_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Duration (ms)")
    )
    
    class Meta:
        verbose_name = _("Risk Assessment Audit Log")
        verbose_name_plural = _("Risk Assessment Audit Logs")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user']),
            models.Index(fields=['action_type']),
            models.Index(fields=['asset']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['success']),
        ]
    
    def __str__(self):
        return f"[{self.timestamp}] {self.user} - {self.action_name}"
    
    @property
    def duration_seconds(self):
        """Повертає тривалість в секундах"""
        return self.duration_ms / 1000 if self.duration_ms else None


class RiskAssessmentSession(models.Model):
    """
    Модель для відстеження сесій користувачів в Risk Assessment модулі
    """
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        verbose_name=_("User")
    )
    session_key = models.CharField(
        max_length=40,
        verbose_name=_("Session Key")
    )
    start_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Start Time")
    )
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("End Time")
    )
    ip_address = models.GenericIPAddressField(
        verbose_name=_("IP Address")
    )
    user_agent = models.TextField(
        verbose_name=_("User Agent")
    )
    actions_count = models.IntegerField(
        default=0,
        verbose_name=_("Actions Count")
    )
    assets_accessed = models.ManyToManyField(
        'app_asset.InformationAsset',
        blank=True,
        verbose_name=_("Assets Accessed")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    
    class Meta:
        verbose_name = _("Risk Assessment Session")
        verbose_name_plural = _("Risk Assessment Sessions")
        ordering = ['-start_time']
        unique_together = ['user', 'session_key']
    
    def __str__(self):
        return f"{self.user} - {self.start_time}"
    
    @property
    def duration(self):
        """Повертає тривалість сесії"""
        if self.end_time:
            return self.end_time - self.start_time
        return timezone.now() - self.start_time


class ScheduledReport(models.Model):
    """Model for scheduled risk reports"""
    
    REPORT_TYPE_CHOICES = [
        ('full', _('Full Report')),
        ('summary', _('Summary Report')),
        ('compliance', _('Compliance Report')),
    ]
    
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('word', 'Word'),
    ]
    
    FREQUENCY_CHOICES = [
        ('once', _('Once')),
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('monthly', _('Monthly')),
        ('quarterly', _('Quarterly')),
        ('yearly', _('Yearly')),
    ]
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('paused', _('Paused')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    ]
    
    # Basic fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name=_('Schedule Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    
    # Report configuration
    report_profile = models.ForeignKey(
        'ReportProfile',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Report Profile'),
        help_text=_('Report profile to use for this scheduled report')
    )
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='full', verbose_name=_('Report Type'))
    report_format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='pdf', verbose_name=_('Format'))
    report_language = models.CharField(max_length=5, default='uk', verbose_name=_('Language'))
    
    # Company filter
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Company'))
    
    # Scheduling
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, verbose_name=_('Frequency'))
    start_date = models.DateField(verbose_name=_('Start Date'))
    end_date = models.DateField(null=True, blank=True, verbose_name=_('End Date'))
    execution_time = models.TimeField(verbose_name=_('Execution Time'))
    
    # Weekly scheduling (if frequency is weekly)
    monday = models.BooleanField(default=False, verbose_name=_('Monday'))
    tuesday = models.BooleanField(default=False, verbose_name=_('Tuesday'))
    wednesday = models.BooleanField(default=False, verbose_name=_('Wednesday'))
    thursday = models.BooleanField(default=False, verbose_name=_('Thursday'))
    friday = models.BooleanField(default=False, verbose_name=_('Friday'))
    saturday = models.BooleanField(default=False, verbose_name=_('Saturday'))
    sunday = models.BooleanField(default=False, verbose_name=_('Sunday'))
    
    # Monthly scheduling (if frequency is monthly)
    day_of_month = models.IntegerField(null=True, blank=True, verbose_name=_('Day of Month'), help_text=_('1-31'))
    
    # Email settings
    email_recipients = models.ManyToManyField(CabinetUser, blank=True, verbose_name=_('Email Recipients'))
    email_subject = models.CharField(max_length=200, blank=True, verbose_name=_('Email Subject'))
    email_body = models.TextField(blank=True, verbose_name=_('Email Body'))
    send_email = models.BooleanField(default=True, verbose_name=_('Send Email'))
    
    # Email server configuration
    mail_server = models.ForeignKey(
        'app_conf.MailServer', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name=_('Mail Server'),
        help_text=_('Select mail server for sending scheduled reports')
    )
    mail_account = models.ForeignKey(
        'app_conf.MailAccount', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name=_('Mail Account'),
        help_text=_('Select mail account for sending scheduled reports')
    )
    use_default_email_settings = models.BooleanField(
        default=True, 
        verbose_name=_('Use Default Email Settings'),
        help_text=_('Use system default email settings if no specific server/account selected')
    )
    
    # Attachments field removed - using separate model for multiple files
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name=_('Status'))
    last_run = models.DateTimeField(null=True, blank=True, verbose_name=_('Last Run'))
    next_run = models.DateTimeField(null=True, blank=True, verbose_name=_('Next Run'))
    run_count = models.IntegerField(default=0, verbose_name=_('Run Count'))
    
    # Audit fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_schedules', verbose_name=_('Created By'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))
    
    class Meta:
        verbose_name = _('Scheduled Report')
        verbose_name_plural = _('Scheduled Reports')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
    
    def save(self, *args, **kwargs):
        """Override save to update next_run when schedule changes"""
        # Check if this is a new object (pk is None) or if schedule parameters changed
        # Only recalculate next_run if:
        # 1. It's a new object (pk is None)
        # 2. next_run is not set
        # 3. next_run is in the past (needs recalculation)
        # BUT: Don't recalculate if status is 'completed' and frequency is 'once' (next_run should be None)
        from django.utils import timezone
        recalculate = False
        
        # Don't recalculate if report is completed and frequency is 'once'
        if self.status == 'completed' and self.frequency == 'once':
            # For completed 'once' reports, next_run should be None
            if self.next_run is not None:
                self.next_run = None
        elif self.pk is None:
            # New object - always calculate
            recalculate = True
        elif not self.next_run:
            # next_run not set - calculate it (unless it's a completed 'once' report)
            if not (self.status == 'completed' and self.frequency == 'once'):
                recalculate = True
        elif self.next_run <= timezone.now():
            # next_run is in the past - recalculate for next occurrence
            # But don't recalculate if it's a completed 'once' report
            if not (self.status == 'completed' and self.frequency == 'once'):
                recalculate = True
        
        if recalculate:
            self.next_run = self.calculate_next_run()
        
        super().save(*args, **kwargs)
    
    def get_weekdays(self):
        """Get list of selected weekdays"""
        days = []
        if self.monday: days.append(_('Monday'))
        if self.tuesday: days.append(_('Tuesday'))
        if self.wednesday: days.append(_('Wednesday'))
        if self.thursday: days.append(_('Thursday'))
        if self.friday: days.append(_('Friday'))
        if self.saturday: days.append(_('Saturday'))
        if self.sunday: days.append(_('Sunday'))
        return days
    
    def calculate_next_run(self):
        """Calculate the next run time based on frequency and current settings"""
        from datetime import datetime, timedelta
        import calendar
        from django.utils import timezone
        
        # Use timezone-aware datetime
        now = timezone.now()
        
        if self.frequency == 'once':
            # For "once" frequency, schedule for the start date at execution time
            if self.start_date > now.date():
                # Start date is in the future - schedule for start date
                next_run = timezone.make_aware(datetime.combine(self.start_date, self.execution_time))
            elif self.start_date == now.date():
                # Start date is today - check if execution time has passed
                scheduled_time = timezone.make_aware(datetime.combine(now.date(), self.execution_time))
                if scheduled_time > now:
                    # Execution time hasn't passed yet - schedule for today
                    next_run = scheduled_time
                else:
                    # Execution time has already passed today - schedule for immediate execution
                    # Set to a time slightly in the past so check_scheduled_reports can find it
                    next_run = scheduled_time
            else:
                # Start date is in the past - check if report has already been executed
                # If run_count is 0, schedule for immediate execution (use start_date + execution_time)
                # If run_count > 0, don't schedule (set to None)
                if self.run_count == 0:
                    # Report hasn't been executed yet - schedule for immediate execution
                    scheduled_time = timezone.make_aware(datetime.combine(self.start_date, self.execution_time))
                    next_run = scheduled_time
                else:
                    # Report has already been executed - don't schedule again
                    next_run = None
        
        elif self.frequency == 'daily':
            # For daily frequency, respect start_date
            if self.start_date > now.date():
                # Start date is in the future - schedule for start date
                next_run = timezone.make_aware(datetime.combine(self.start_date, self.execution_time))
            elif self.start_date == now.date():
                # Start date is today - check if execution time has passed
                scheduled_time = timezone.make_aware(datetime.combine(now.date(), self.execution_time))
                if scheduled_time > now:
                    # Execution time hasn't passed yet - schedule for today
                    next_run = scheduled_time
                else:
                    # Execution time has passed - schedule for tomorrow
                    next_date = now.date() + timedelta(days=1)
                    next_run = timezone.make_aware(datetime.combine(next_date, self.execution_time))
            else:
                # Start date is in the past - schedule for tomorrow
                next_date = now.date() + timedelta(days=1)
                next_run = timezone.make_aware(datetime.combine(next_date, self.execution_time))
        
        elif self.frequency == 'weekly':
            # Find next occurrence of selected weekday(s)
            weekdays = []
            if self.monday: weekdays.append(0)
            if self.tuesday: weekdays.append(1)
            if self.wednesday: weekdays.append(2)
            if self.thursday: weekdays.append(3)
            if self.friday: weekdays.append(4)
            if self.saturday: weekdays.append(5)
            if self.sunday: weekdays.append(6)
            
            if weekdays:
                days_ahead = []
                for weekday in weekdays:
                    days_ahead.append((weekday - now.weekday()) % 7)
                
                next_day_offset = min([d for d in days_ahead if d > 0] or [min(days_ahead) + 7])
                next_date = now.date() + timedelta(days=next_day_offset)
                next_run = timezone.make_aware(datetime.combine(next_date, self.execution_time))
            else:
                next_run = None
        
        elif self.frequency == 'monthly':
            # Next month on specified day
            if self.day_of_month:
                try:
                    if now.day >= self.day_of_month:
                        # Next month
                        if now.month == 12:
                            next_month = datetime(now.year + 1, 1, self.day_of_month)
                        else:
                            next_month = datetime(now.year, now.month + 1, self.day_of_month)
                    else:
                        # This month
                        next_month = datetime(now.year, now.month, self.day_of_month)
                    
                    next_run = timezone.make_aware(datetime.combine(next_month.date(), self.execution_time))
                except ValueError:
                    # Invalid day for month, use last day of month
                    if now.month == 12:
                        last_day = calendar.monthrange(now.year + 1, 1)[1]
                        next_month = datetime(now.year + 1, 1, min(self.day_of_month, last_day))
                    else:
                        last_day = calendar.monthrange(now.year, now.month + 1)[1]
                        next_month = datetime(now.year, now.month + 1, min(self.day_of_month, last_day))
                    
                    next_run = timezone.make_aware(datetime.combine(next_month.date(), self.execution_time))
            else:
                next_run = None
        
        elif self.frequency == 'quarterly':
            start_day = self.start_date.day
            
            # First check if start_date is today and execution time hasn't passed yet
            if self.start_date == now.date():
                scheduled_time = timezone.make_aware(datetime.combine(now.date(), self.execution_time))
                if scheduled_time > now:
                    # Execution time hasn't passed yet today - schedule for today
                    next_run = scheduled_time
                else:
                    # Execution time has passed today - find next quarter
                    # Calculate next run based on start_date's quarter and day
                    next_run_candidate = None
                    
                    # Consider current year's remaining quarters and next year's quarters
                    for year_offset in range(2): # Check current and next year
                        current_year = now.year + year_offset
                        
                        for q_month_start in [1, 4, 7, 10]: # Start months of quarters
                            # Calculate the target date for this quarter
                            try:
                                candidate_date = datetime(current_year, q_month_start, start_day).date()
                            except ValueError:
                                # Handle cases where start_day is invalid for the month (e.g., Feb 30)
                                last_day = calendar.monthrange(current_year, q_month_start)[1]
                                candidate_date = datetime(current_year, q_month_start, min(start_day, last_day)).date()
                            
                            candidate_datetime = timezone.make_aware(datetime.combine(candidate_date, self.execution_time))
                            
                            # If this candidate is in the future, it's a potential next run
                            if candidate_datetime > now:
                                if next_run_candidate is None or candidate_datetime < next_run_candidate:
                                    next_run_candidate = candidate_datetime
                    
                    next_run = next_run_candidate
            elif self.start_date > now.date():
                # Start date is in the future - schedule for start date
                next_run = timezone.make_aware(datetime.combine(self.start_date, self.execution_time))
            else:
                # Start date is in the past - find next quarter
                # Calculate next run based on start_date's quarter and day
                next_run_candidate = None
                
                # Consider current year's remaining quarters and next year's quarters
                for year_offset in range(2): # Check current and next year
                    current_year = now.year + year_offset
                    
                    for q_month_start in [1, 4, 7, 10]: # Start months of quarters
                        # Calculate the target date for this quarter
                        try:
                            candidate_date = datetime(current_year, q_month_start, start_day).date()
                        except ValueError:
                            # Handle cases where start_day is invalid for the month (e.g., Feb 30)
                            last_day = calendar.monthrange(current_year, q_month_start)[1]
                            candidate_date = datetime(current_year, q_month_start, min(start_day, last_day)).date()
                        
                        candidate_datetime = timezone.make_aware(datetime.combine(candidate_date, self.execution_time))
                        
                        # If this candidate is in the future, it's a potential next run
                        if candidate_datetime > now:
                            if next_run_candidate is None or candidate_datetime < next_run_candidate:
                                next_run_candidate = candidate_datetime
                
                next_run = next_run_candidate
        
        elif self.frequency == 'yearly':
            # Next year on same date
            next_run = timezone.make_aware(datetime.combine(datetime(now.year + 1, now.month, now.day).date(), self.execution_time))
        
        else:
            next_run = None
        
        return next_run
    
    def process_email_tags(self, text, execution, recipient=None):
        """Process tags in email subject and body"""
        from django.conf import settings
        from datetime import datetime
        
        if not text:
            return text
        
        # Helper function to build absolute URL using Site Domain from SiteSettings
        def _build_absolute_url(path: str) -> str:
            # Try to get Site Domain from SiteSettings (primary source)
            import logging
            logger = logging.getLogger(__name__)
            try:
                from app_conf.models import SiteSettings
                site_settings = SiteSettings.get_settings()
                logger.info(f"[process_email_tags] SiteSettings loaded: site_domain='{site_settings.site_domain if site_settings else 'None'}', site_protocol='{site_settings.site_protocol if site_settings else 'None'}'")
                
                if site_settings and site_settings.site_domain and site_settings.site_domain.strip():
                    # Use get_site_url() method which combines protocol + domain
                    base = site_settings.get_site_url().rstrip('/')
                    logger.info(f"[process_email_tags] Using Site Domain from SiteSettings: {base} for path: {path}")
                    full_url = f"{base}{path}"
                    logger.info(f"[process_email_tags] Generated full URL: {full_url}")
                    return full_url
                else:
                    logger.warning(f"[process_email_tags] SiteSettings.site_domain is empty or None: site_settings={site_settings}, site_domain='{site_settings.site_domain if site_settings else 'No SiteSettings'}'")
            except Exception as e:
                logger.error(f"[process_email_tags] Could not load SiteSettings: {e}", exc_info=True)
            
            # Fallback to PUBLIC_BASE_URL from settings
            base = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')
            if base:
                logger.warning(f"[process_email_tags] Using PUBLIC_BASE_URL fallback: {base} for path: {path}")
                return f"{base}{path}"
            
            # Fallback to ALLOWED_HOSTS - but prefer test.secboard.online if available
            scheme = 'https' if getattr(settings, 'PRODUCTION', False) else 'http'
            host = 'localhost:8000'
            try:
                if settings.ALLOWED_HOSTS:
                    # Prefer test.secboard.online if available, otherwise use first non-testserver host
                    preferred_hosts = ['test.secboard.online', 'demo.secboard.online', 'prod.secboard.online', 'secboard.online']
                    host = None
                    for preferred in preferred_hosts:
                        if preferred in settings.ALLOWED_HOSTS:
                            host = preferred
                            break
                    if not host:
                        host = next((h for h in settings.ALLOWED_HOSTS if h not in ('testserver',)), settings.ALLOWED_HOSTS[0])
                    if ':' not in host and host in ('localhost', '127.0.0.1'):
                        host = f"{host}:8000"
            except Exception:
                pass
            fallback_url = f"{scheme}://{host}"
            logger.warning(f"[process_email_tags] Using ALLOWED_HOSTS fallback: {fallback_url} for path: {path}")
            return f"{fallback_url}{path}"
            
        # Get company name
        company_name = self.company.name if self.company else _('All Companies')
        
        # Get report name
        report_name = self.name
        
        # Get report date
        report_date = execution.started_at.strftime('%Y-%m-%d')
        
        # Get generated by
        generated_by = self.created_by.get_full_name() if self.created_by else _('System')
        
        # Get report link
        report_link = execution.get_snapshot_url()
        if report_link:
            report_link = _build_absolute_url(report_link)
        
        # Get system name
        system_name = getattr(settings, 'SYSTEM_NAME', 'SecBoard')
        
        # Get current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get recipient info
        recipient_name = recipient.get_full_name() if recipient else ''
        recipient_email = recipient.email if recipient else ''
        
        # Get attachments list
        attachments_list = ''
        if self.attachments.exists():
            attachments_links = []
            for attachment in self.attachments.all():
                file_url = attachment.get_file_url()
                if file_url:
                    # Build absolute URL using Site Domain from SiteSettings
                    if file_url.startswith('/'):
                        file_url = _build_absolute_url(file_url)
                    
                    attachments_links.append(f"- {attachment.original_filename} ({attachment.get_file_size_display()}) - {file_url}")
            
            if attachments_links:
                attachments_list = '\n'.join(attachments_links)
        
        # Replace tags
        replacements = {
            '{company_name}': company_name,
            '{report_name}': report_name,
            '{date}': report_date,
            '{generated_by}': generated_by,
            '{report_link}': report_link,
            '{system_name}': system_name,
            '{current_date}': current_date,
            '{recipient_name}': recipient_name,
            '{recipient_email}': recipient_email,
            '{attachments_list}': attachments_list,
        }
        
        # Replace tags - handle both plain tags and tags wrapped in HTML (e.g., <code>{tag}</code>)
        import re
        for tag, value in replacements.items():
            # Replace plain tags
            text = text.replace(tag, str(value))
            # Replace tags wrapped in <code> tags
            text = text.replace(f'<code>{tag}</code>', str(value))
            text = text.replace(f'<code>{tag}</code>', str(value))  # Handle with &nbsp;
            # Replace tags wrapped in other HTML tags (common cases)
            # Match tags inside various HTML tags
            pattern = f'<[^>]*>{re.escape(tag)}</[^>]*>'
            text = re.sub(pattern, str(value), text)
        
        # Remove empty <p> tags and unwrap content from <p> tags if they only contain plain text
        # This handles cases where TinyMCE wraps each line in <p> tags
        # First, replace <p></p> and <p>&nbsp;</p> with empty string or newline
        text = re.sub(r'<p>\s*</p>', '\n', text)
        text = re.sub(r'<p>&nbsp;</p>', '\n', text)
        text = re.sub(r'<p>\s*&nbsp;\s*</p>', '\n', text)
        # Replace <p>content</p> with just content + newline (if content doesn't contain other HTML tags)
        # But preserve <p> tags that contain other HTML elements (like <strong>, <em>, etc.)
        # Only unwrap <p> tags that contain only plain text (no nested HTML tags)
        text = re.sub(r'<p>([^<]+)</p>', r'\1\n', text)
        # Replace multiple consecutive newlines with double newline (paragraph break)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        # Trim leading/trailing whitespace but preserve internal formatting
        text = text.strip()
        
        return text
    
    def send_email_report(self, file_path, execution):
        """Send email with report attachment using configured email settings"""
        from django.core.mail import EmailMessage
        from django.conf import settings
        import os
        import logging
        import smtplib
        import ssl
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        
        logger = logging.getLogger(__name__)
        
        try:
            # Get email recipients
            recipients = []
            recipient_users = []
            for cabinet_user in self.email_recipients.all():
                if cabinet_user.user and cabinet_user.user.email:
                    recipients.append(cabinet_user.user.email)
                    recipient_users.append(cabinet_user.user)
            
            if not recipients:
                error_msg = _('No valid email recipients found')
                logger.error(f"Email sending failed for report {self.name}: {error_msg}")
                execution.email_error = error_msg
                execution.save()
                return False
            
            # Prepare email content with tag processing
            base_subject = self.email_subject or _('Risk Assessment Report')
            base_body = self.email_body or _('Please find the attached risk assessment report.')
            
            # Process tags with first recipient (for general tags)
            subject = self.process_email_tags(base_subject, execution, recipient_users[0] if recipient_users else None)
            body = self.process_email_tags(base_body, execution, recipient_users[0] if recipient_users else None)
            
            logger.info(f"Preparing to send email for report {self.name} to {len(recipients)} recipients")
            
            # Use custom email settings if configured
            if not self.use_default_email_settings and self.mail_account:
                logger.info(f"Using custom mail account: {self.mail_account.username}")
                
                # Use direct SMTP method (like in keys-cert)
                try:
                    # Create message
                    msg = MIMEMultipart()
                    msg['From'] = self.mail_account.username
                    msg['To'] = ', '.join(recipients)
                    msg['Subject'] = subject
                    
                    # Add body
                    msg.attach(MIMEText(body, 'plain'))
                    
                    # Add attachment
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {os.path.basename(file_path)}'
                            )
                            msg.attach(part)
                        logger.info(f"Attached report file: {os.path.basename(file_path)}")
                    
                    # Connect and send
                    if self.mail_account.server.use_ssl:
                        context = ssl.create_default_context()
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                        
                        smtp = smtplib.SMTP_SSL(
                            host=self.mail_account.server.smtp_host,
                            port=self.mail_account.server.smtp_port,
                            context=context
                        )
                        logger.info("Connected using SSL")
                    else:
                        smtp = smtplib.SMTP(
                            host=self.mail_account.server.smtp_host,
                            port=self.mail_account.server.smtp_port
                        )
                        
                        if self.mail_account.server.use_tls:
                            smtp.starttls()
                            logger.info("Connected using TLS")
                        else:
                            logger.info("Connected without encryption")
                    
                    # Login and send
                    smtp.login(self.mail_account.username, self.mail_account.password)
                    smtp.send_message(msg)
                    smtp.quit()
                    
                    logger.info(f"Email sent successfully using direct SMTP method")
                    
                except Exception as e:
                    logger.error(f"Direct SMTP method failed: {str(e)}")
                    raise e
                        
            else:
                # Use default Django email settings
                logger.info("Using default Django email settings")
                
                email = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=None,  # Will use default from settings
                    to=recipients
                )
                
                # Attach report file
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        file_name = os.path.basename(file_path)
                        email.attach(file_name, f.read())
                    logger.info(f"Attached report file: {file_name}")
                
                # Send email
                email.send()
                logger.info(f"Email sent successfully using default settings")
            
            # Update execution status
            execution.email_sent = True
            execution.email_recipients_count = len(recipients)
            execution.save()
            
            logger.info(f"Email sending completed successfully for report {self.name}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Email sending failed for report {self.name}: {error_msg}")
            execution.email_error = error_msg
            execution.save()
            return False


class ScheduledReportExecution(models.Model):
    """Model to track scheduled report executions"""
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('running', _('Running')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheduled_report = models.ForeignKey(ScheduledReport, on_delete=models.CASCADE, related_name='executions', verbose_name=_('Scheduled Report'))
    
    # Execution details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_('Status'))
    started_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Started At'))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Completed At'))
    
    # Results
    file_path = models.CharField(max_length=500, blank=True, verbose_name=_('File Path'))
    file_size = models.BigIntegerField(null=True, blank=True, verbose_name=_('File Size'))
    error_message = models.TextField(blank=True, verbose_name=_('Error Message'))
    # Snapshot of HTML preview at generation time
    snapshot_html = models.TextField(blank=True, verbose_name=_('Snapshot HTML'))
    snapshot_language = models.CharField(max_length=5, blank=True, verbose_name=_('Snapshot Language'))
    snapshot_created_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Snapshot Created At'))
    snapshot_token = models.CharField(max_length=64, blank=True, verbose_name=_('Snapshot Token'))
    
    # Email status
    email_sent = models.BooleanField(default=False, verbose_name=_('Email Sent'))
    email_recipients_count = models.IntegerField(default=0, verbose_name=_('Email Recipients Count'))
    email_error = models.TextField(blank=True, verbose_name=_('Email Error'))
    
    class Meta:
        verbose_name = _('Scheduled Report Execution')
        verbose_name_plural = _('Scheduled Report Executions')
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.scheduled_report.name} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def get_snapshot_url(self):
        try:
            from django.urls import reverse
            return reverse('view_scheduled_report_snapshot', args=[str(self.id)])
        except Exception:
            return ''


class ScheduledReportAttachment(models.Model):
    """Model for storing attachments for scheduled reports"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheduled_report = models.ForeignKey(
        ScheduledReport, 
        on_delete=models.CASCADE, 
        related_name='attachments',
        verbose_name=_('Scheduled Report')
    )
    file = models.FileField(
        upload_to='scheduled_reports/attachments/',
        verbose_name=_('File'),
        help_text=_('File to be attached to the email')
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name=_('Original Filename'),
        help_text=_('Original filename of the uploaded file')
    )
    file_size = models.BigIntegerField(
        verbose_name=_('File Size (bytes)'),
        help_text=_('Size of the file in bytes')
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Uploaded At')
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Uploaded By')
    )
    
    class Meta:
        verbose_name = _('Scheduled Report Attachment')
        verbose_name_plural = _('Scheduled Report Attachments')
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.original_filename} ({self.scheduled_report.name})"
    
    def get_file_url(self):
        """Get download URL for the file"""
        try:
            from django.urls import reverse
            return reverse('download_scheduled_report_attachment', args=[str(self.id)])
        except Exception:
            return ''
    
    def get_file_size_display(self):
        """Get human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class RiskReportEmailConfig(models.Model):
    """Global email settings for Risk Report scheduled emails"""
    send_email = models.BooleanField(default=True, verbose_name=_('Send Email'))
    use_default_email_settings = models.BooleanField(
        default=True,
        verbose_name=_('Use Default Email Settings'),
        help_text=_('If disabled, the selected mail account below will be used for all Risk Report emails')
    )
    mail_server = models.ForeignKey(
        'app_conf.MailServer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Mail Server')
    )
    mail_account = models.ForeignKey(
        'app_conf.MailAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Mail Account')
    )
    default_subject = models.CharField(max_length=200, blank=True, default='Risk Assessment Report', verbose_name=_('Default Subject'))
    default_body = models.TextField(blank=True, default='Please view your report at the link below.', verbose_name=_('Default Body'))

    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))

    class Meta:
        verbose_name = _('Risk Report Email Settings')
        verbose_name_plural = _('Risk Report Email Settings')

    def __str__(self):
        return _('Risk Report Email Settings')

class ReportProfile(models.Model):
    """Model for custom report type profiles"""
    
    PROFILE_TYPE_CHOICES = [
        ('system', _('System Profile')),
        ('user', _('User Profile')),
        ('shared', _('Shared Profile')),
    ]
    
    # Basic information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name=_('Profile Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    
    # Profile type and ownership
    profile_type = models.CharField(
        max_length=20, 
        choices=PROFILE_TYPE_CHOICES, 
        default='user', 
        verbose_name=_('Profile Type')
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_report_profiles', 
        verbose_name=_('Created By')
    )
    # company = models.ForeignKey(
    #     Company, 
    #     on_delete=models.CASCADE, 
    #     null=True, 
    #     blank=True, 
    #     verbose_name=_('Company'),
    #     help_text=_('Company this profile belongs to (for shared profiles)')
    # )
    
    # Report sections configuration (JSON field)
    sections_config = models.JSONField(
        default=dict,
        verbose_name=_('Sections Configuration'),
        help_text=_('JSON configuration of enabled/disabled report sections')
    )
    
    # Default settings for reports using this profile
    default_format = models.CharField(
        max_length=10, 
        choices=[('pdf', 'PDF'), ('word', 'Word')], 
        default='pdf', 
        verbose_name=_('Default Format')
    )
    default_language = models.CharField(
        max_length=5, 
        default='uk', 
        verbose_name=_('Default Language')
    )
    
    # Sharing and permissions
    is_active = models.BooleanField(default=True, verbose_name=_('Active'))
    is_public = models.BooleanField(
        default=False, 
        verbose_name=_('Public'),
        help_text=_('Allow other users in the same company to use this profile')
    )
    allowed_users = models.ManyToManyField(
        User, 
        blank=True, 
        related_name='allowed_report_profiles',
        verbose_name=_('Allowed Users'),
        help_text=_('Specific users who can use this profile')
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Last Used At'))
    usage_count = models.IntegerField(default=0, verbose_name=_('Usage Count'))
    
    class Meta:
        verbose_name = _('Report Profile')
        verbose_name_plural = _('Report Profiles')
        ordering = ['-updated_at']
        unique_together = [['name', 'created_by']]  # Unique name per user
    
    def __str__(self):
        return f"{self.name} ({self.get_profile_type_display()})"
    
    def get_sections_config(self):
        """Get sections configuration with defaults"""
        default_sections = {
            # Original sections (18)
            'statistics': True,
            'risk_distribution': True,
            'compliance_overview': True,
            'top_risks': True,
            'asset_details': True,
            'vulnerability_details': True,
            'risk_calculations': True,
            'treatment_details': True,
            'pci_dss': True,
            'iso27001': True,
            'compliance_gaps': True,
            'recommendations': True,
            # Compliance & Standards sections
            'framework_company_requirements': True,
            'company_requirements': True,
            'internal_requirements': True,
            'asset_tables': True,
            'vulnerability_tables': True,
            'treatment_tables': True,
            'charts': True,
            'graphs': True,
            'metrics': True,
            # New sections (16) - Financial Analysis
            'financial_analysis': True,
            'cost_benefit_analysis': True,
            'roi_assessment': True,
            'budget_allocation': True,
            # New sections - Monitoring & Performance
            'monitoring_dashboard': True,
            'effectiveness_metrics': True,
            'performance_indicators': True,
            'treatment_effectiveness': True,
            # Timeline & Trends sections
            'timeline_analysis': True,
            'trend_analysis': True,
            'historical_data': True,
            'deadline_tracking': True,
            # Risk Dependencies sections
            'dependency_analysis': True,
            'impact_assessment': True,
            'cascading_risks': True,
            'interdependency_matrix': True,
            # Extended Asset Details sections
            'asset_criticality': True,
            'asset_location': True,
            'asset_owners': True,
            'asset_lifecycle': True,
            # Threat Analysis sections
            'threat_analysis': True,
            'threat_scenarios': True,
            'probability_analysis': True,
            'threat_landscape': True,
            # Residual Risk & Priority sections
            'residual_risk_analysis': True,
            'acceptable_risk_analysis': True,
            'risk_appetite': True,
            # Conclusions section
            'conclusions': True,
            '_ai_conclusion_model': None,
            'priority_matrix': True,
            'resource_allocation': True,
            # Other sections
            'quiz_results': True,
            'third_party_risk': True,
            'gdpr_compliance': True,
            'access_risk_summary': True,
            # Security Operations sections
            'incident': True,
            'mandatory_processes': True,
            'certificate_key_management': True,
            'siem': True,
        }
        
        # If we have saved configuration, use it directly (preserving False values)
        if self.sections_config:
            # Start with saved configuration
            config = {}
            
            # First, copy all saved sections (including False values)
            # This preserves the user's explicit choices
            for key, value in self.sections_config.items():
                if key.startswith('_'):
                    # Include special fields (like _company_id)
                    config[key] = value
                else:
                    # Include all saved sections (both True and False)
                    config[key] = value
            
            # Then, for any default sections that weren't explicitly saved,
            # default to False (not included) to ensure only explicitly selected sections are shown
            # This prevents sections from being included when they weren't explicitly selected
            for section_name in default_sections.keys():
                if section_name not in config:
                    # Default to False if section wasn't explicitly saved
                    # This ensures that only sections explicitly selected by the user are included
                    config[section_name] = False
            
            return config
        else:
            # No saved configuration, return defaults (for new profiles)
            return default_sections
    
    def set_sections_config(self, sections_dict):
        """Set sections configuration"""
        self.sections_config = sections_dict
    
    def can_be_used_by(self, user):
        """Check if user can use this profile"""
        # Creator can always use their own profiles
        if self.created_by == user:
            return True
        
        # System profiles can be used by everyone
        if self.profile_type == 'system':
            return True
        
        # Public profiles can be used by users in the same company
        # if self.is_public and self.company:
        #     # Check if user belongs to the same company
        #     try:
        #         user_company = user.cabinetuser.company
        #         return user_company == self.company
        #     except:
        #         return False
        
        # Check if user is specifically allowed
        return self.allowed_users.filter(id=user.id).exists()
    
    def increment_usage(self):
        """Increment usage count and update last used time"""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])
    
    @classmethod
    def get_available_profiles(cls, user):
        """Get all profiles available to a specific user"""
        from django.db.models import Q
        
        # Get user's company if available
        user_company = None
        try:
            user_company = user.cabinetuser.company
        except:
            pass
        
        # Build query
        query = Q(created_by=user)  # Own profiles
        query |= Q(profile_type='system')  # System profiles
        
        # if user_company:
        #     query |= Q(is_public=True, company=user_company)  # Public profiles in same company
        
        query |= Q(allowed_users=user)  # Specifically allowed profiles
        
        return cls.objects.filter(query, is_active=True).distinct()
    
    @classmethod
    def create_default_profiles(cls):
        """Create default system profiles"""
        from django.contrib.auth.models import User
        
        # Get or create system user for default profiles
        system_user, created = User.objects.get_or_create(
            username='system',
            defaults={
                'first_name': 'System',
                'last_name': 'User',
                'is_active': False,
                'is_staff': False,
            }
        )
        
        # Full Report Profile
        full_profile, created = cls.objects.get_or_create(
            name='Full Report',
            profile_type='system',
            created_by=system_user,
            defaults={
                'description': _('Complete risk assessment report with all sections'),
                'sections_config': {},  # All sections enabled by default
                'default_format': 'pdf',
                'default_language': 'uk',
                'is_active': True,
            }
        )
        
        # Executive Summary Profile
        summary_config = {
            # Original sections
            'statistics': True,
            'risk_distribution': True,
            'compliance_overview': True,
            'top_risks': True,
            'asset_details': False,
            'vulnerability_details': False,
            'risk_calculations': False,
            'treatment_details': False,
            'pci_dss': False,
            'iso27001': False,
            'compliance_gaps': False,
            'recommendations': True,
            'asset_tables': False,
            'vulnerability_tables': False,
            'treatment_tables': False,
            'charts': True,
            'graphs': False,
            'metrics': True,
            # New sections - Financial Analysis
            'financial_analysis': True,
            'cost_benefit_analysis': False,
            'roi_assessment': True,
            'budget_allocation': False,
            # New sections - Audit & Tracking
            'audit_trail': False,
            'activity_logs': False,
            'user_sessions': False,
            'modification_history': False,
            # New sections - Monitoring & Performance
            'monitoring_dashboard': True,
            'effectiveness_metrics': True,
            'performance_indicators': True,
            'treatment_effectiveness': False,
            # New sections - Management & Governance
            'responsibility_matrix': True,
            'approval_workflow': False,
            'stakeholder_analysis': True,
            'governance_structure': True,
            # Timeline & Trends sections
            'timeline_analysis': False,
            'trend_analysis': True,
            'historical_data': False,
            'deadline_tracking': False,
            # Risk Dependencies sections
            'dependency_analysis': False,
            'impact_assessment': False,
            'cascading_risks': False,
            'interdependency_matrix': False,
            # Extended Asset Details sections
            'asset_criticality': False,
            'asset_location': False,
            'asset_owners': False,
            'asset_lifecycle': False,
            # Threat Analysis sections
            'threat_analysis': False,
            'threat_scenarios': False,
            'probability_analysis': False,
            'threat_landscape': False,
            # Residual Risk & Priority sections
            'residual_risk_analysis': False,
            'acceptable_risk_analysis': True,
            'risk_appetite': True,
            'priority_matrix': True,
            'resource_allocation': False,
        }
        
        summary_profile, created = cls.objects.get_or_create(
            name='Executive Summary',
            profile_type='system',
            created_by=system_user,
            defaults={
                'description': _('High-level summary report for executives'),
                'sections_config': summary_config,
                'default_format': 'pdf',
                'default_language': 'uk',
                'is_active': True,
            }
        )
        
        # Compliance Report Profile
        compliance_config = {
            # Original sections
            'statistics': True,
            'risk_distribution': False,
            'compliance_overview': True,
            'top_risks': False,
            'asset_details': False,
            'vulnerability_details': False,
            'risk_calculations': False,
            'treatment_details': True,
            'pci_dss': True,
            'iso27001': True,
            'compliance_gaps': True,
            'recommendations': True,
            'asset_tables': False,
            'vulnerability_tables': False,
            'treatment_tables': True,
            'charts': True,
            'graphs': False,
            'metrics': False,
            # New sections - Financial Analysis
            'financial_analysis': False,
            'cost_benefit_analysis': True,
            'roi_assessment': False,
            'budget_allocation': True,
            # New sections - Audit & Tracking
            'audit_trail': True,
            'activity_logs': True,
            'user_sessions': False,
            'modification_history': True,
            # New sections - Monitoring & Performance
            'monitoring_dashboard': False,
            'effectiveness_metrics': False,
            'performance_indicators': False,
            'treatment_effectiveness': True,
            # New sections - Management & Governance
            'responsibility_matrix': False,
            'approval_workflow': True,
            'stakeholder_analysis': False,
            'governance_structure': True,
            # Timeline & Trends sections
            'timeline_analysis': True,
            'trend_analysis': False,
            'historical_data': True,
            'deadline_tracking': True,
            # Risk Dependencies sections
            'dependency_analysis': False,
            'impact_assessment': True,
            'cascading_risks': False,
            'interdependency_matrix': False,
            # Extended Asset Details sections
            'asset_criticality': False,
            'asset_location': False,
            'asset_owners': False,
            'asset_lifecycle': False,
            # Threat Analysis sections
            'threat_analysis': True,
            'threat_scenarios': True,
            'probability_analysis': True,
            'threat_landscape': False,
            # Residual Risk & Priority sections
            'residual_risk_analysis': True,
            'acceptable_risk_analysis': True,
            'risk_appetite': False,
            'priority_matrix': False,
            'resource_allocation': True,
        }
        
        compliance_profile, created = cls.objects.get_or_create(
            name='Compliance Report',
            profile_type='system',
            created_by=system_user,
            defaults={
                'description': _('Compliance-focused report for audits'),
                'sections_config': compliance_config,
                'default_format': 'pdf',
                'default_language': 'uk',
                'is_active': True,
            }
        )
        
        return [full_profile, summary_profile, compliance_profile]


class AcceptableRisk(models.Model):
    """Модель для налаштування допустимого рівня ризику для компанії та групи активів"""
    company = models.ForeignKey('app_conf.Company', on_delete=models.CASCADE, verbose_name=_('Company'))
    asset_group = models.ForeignKey('app_asset.AssetGroup', on_delete=models.CASCADE, verbose_name=_('Asset Group'))
    asset_type = models.ForeignKey('app_asset.AssetType', on_delete=models.CASCADE, null=True, blank=True, verbose_name=_('Asset Type'))
    criticality_level = models.ForeignKey('app_asset.CriticalityLevel', on_delete=models.CASCADE, verbose_name=_('Criticality Level'))
    acceptable_risk_level = models.ForeignKey(RiskLevel, on_delete=models.CASCADE, verbose_name=_('Acceptable Risk Level'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('Created By'))
    updated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='acceptable_risk_updated_by', verbose_name=_('Updated By'))

    class Meta:
        verbose_name = _('Acceptable Risk')
        verbose_name_plural = _('Acceptable Risks')
        unique_together = ['company', 'asset_group', 'asset_type', 'criticality_level']
        ordering = ['company__name', 'asset_group__name', 'criticality_level__name']

    def __str__(self):
        asset_type_str = f" - {self.asset_type.name}" if self.asset_type else ""
        return f"{self.company.name} - {self.asset_group.name}{asset_type_str} - {self.criticality_level.get_name()}"

    def get_acceptable_risk_level_name(self, language='uk'):
        """Повертає назву допустимого рівня ризику на вказаній мові"""
        return self.acceptable_risk_level.get_name_by_language(language) or self.acceptable_risk_level.get_name() or _('Undefined')


class AllowedSoftware(models.Model):
    """Allowed Software Register entries for Risk Assessment"""
    company = models.ForeignKey(
        'app_conf.Company',
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name=_('Company'),
        help_text=_('Leave blank to apply to all companies')
    )
    software_register = models.ForeignKey(
        'app_asset.SoftwareRegister',
        on_delete=models.CASCADE,
        verbose_name=_('Software')
    )
    notes = models.TextField(blank=True, verbose_name=_('Notes'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Created By')
    )

    class Meta:
        verbose_name = _('Allowed Software')
        verbose_name_plural = _('Allowed Software')
        unique_together = ['company', 'software_register']
        ordering = ['company__name', 'software_register__name']

    def __str__(self):
        company_str = self.company.name if self.company else _('All companies')
        return f"{company_str} — {self.software_register.name}"


class SoftwareVulnerability(models.Model):
    """Vulnerability assessment for Software Register entries (mirrors AssetVulnerability)."""
    software_register = models.ForeignKey(
        'app_asset.SoftwareRegister',
        on_delete=models.CASCADE,
        related_name='risk_vulnerabilities',
        verbose_name=_('Software'),
        db_column='software_id',
    )
    vulnerability = models.ForeignKey(
        Vulnerability,
        on_delete=models.CASCADE,
        verbose_name=_('Vulnerability')
    )
    modified_at = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Modified By')
    )
    status = models.CharField(
        max_length=10,
        choices=[('No', 'No'), ('Undefined', 'Undefined'), ('Yes', 'Yes')],
        default='Undefined',
        verbose_name=_('Status')
    )
    comment = models.TextField(blank=True, verbose_name=_('Comment'))

    @staticmethod
    def get_user_full_name(user):
        if user:
            return f"{user.first_name} {user.last_name}".strip() or user.username
        return ''

    class Meta:
        verbose_name = _('Software Vulnerability')
        verbose_name_plural = _('Software Vulnerabilities')
        unique_together = ('software_register', 'vulnerability')
        ordering = ['software_register', 'vulnerability']

    def __str__(self):
        return f"{self.software_register.name} — {self.vulnerability.get_name()} [{self.status}]"


class ExternalMediaVulnerability(models.Model):
    """Vulnerability assessment for External Media Register entries."""
    external_media_register = models.ForeignKey(
        'app_asset.ExternalMediaRegister',
        on_delete=models.CASCADE,
        related_name='risk_vulnerabilities',
        verbose_name=_('External Media'),
        db_column='external_media_id',
    )
    vulnerability = models.ForeignKey(
        Vulnerability,
        on_delete=models.CASCADE,
        verbose_name=_('Vulnerability')
    )
    modified_at = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_('Modified By')
    )
    status = models.CharField(
        max_length=10,
        choices=[('No', 'No'), ('Undefined', 'Undefined'), ('Yes', 'Yes')],
        default='Undefined',
        verbose_name=_('Status')
    )
    comment = models.TextField(blank=True, verbose_name=_('Comment'))

    @staticmethod
    def get_user_full_name(user):
        if user:
            return f"{user.first_name} {user.last_name}".strip() or user.username
        return ''

    class Meta:
        verbose_name = _('External Media Vulnerability')
        verbose_name_plural = _('External Media Vulnerabilities')
        unique_together = ('external_media_register', 'vulnerability')
        ordering = ['external_media_register', 'vulnerability']

    def __str__(self):
        return f"{self.external_media_register.name} — {self.vulnerability.get_name()} [{self.status}]"


from tinymce.models import HTMLField


class RiskAssessmentConfigGuide(models.Model):
    """Base Guide for Risk Assessment Configuration. Source content for translations."""
    base_content = HTMLField(
        _lazy("Base content"),
        blank=True,
        help_text=_lazy("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _lazy("Risk Assessment Config Guide")
        verbose_name_plural = _lazy("Risk Assessment Config Guides")

    def __str__(self):
        return _("Risk Assessment Configuration Guide")


class RiskAssessmentConfigGuideTranslation(models.Model):
    """Per-country (language) translations of the Risk Assessment Config Guide."""
    config_guide = models.ForeignKey(
        RiskAssessmentConfigGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_lazy("Config Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="risk_assessment_config_guide_translations",
        verbose_name=_lazy("Country")
    )
    content = HTMLField(
        _lazy("Content"),
        blank=True,
        help_text=_lazy("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _lazy("Risk Assessment Config Guide Translation")
        verbose_name_plural = _lazy("Risk Assessment Config Guide Translations")
        unique_together = ["config_guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.config_guide} — {self.country.name}"


class RiskAssessmentGuide(models.Model):
    """Base Guide for Risk Assessment. Source content for translations."""
    base_content = HTMLField(
        _lazy("Base content"),
        blank=True,
        help_text=_lazy("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _lazy("Risk Assessment Guide")
        verbose_name_plural = _lazy("Risk Assessment Guides")

    def __str__(self):
        return _("Risk Assessment Guide")


class RiskAssessmentGuideTranslation(models.Model):
    """Per-country (language) translations of the Risk Assessment Guide."""
    guide = models.ForeignKey(
        RiskAssessmentGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_lazy("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="risk_assessment_guide_translations",
        verbose_name=_lazy("Country")
    )
    content = HTMLField(
        _lazy("Content"),
        blank=True,
        help_text=_lazy("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _lazy("Risk Assessment Guide Translation")
        verbose_name_plural = _lazy("Risk Assessment Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class RiskReportGuide(models.Model):
    """Base Guide for Risk Report. Source content for translations."""
    base_content = HTMLField(
        _lazy("Base content"),
        blank=True,
        help_text=_lazy("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _lazy("Risk Report Guide")
        verbose_name_plural = _lazy("Risk Report Guides")

    def __str__(self):
        return _("Risk Report Guide")


class RiskReportGuideTranslation(models.Model):
    """Per-country (language) translations of the Risk Report Guide."""
    guide = models.ForeignKey(
        RiskReportGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_lazy("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="risk_report_guide_translations",
        verbose_name=_lazy("Country")
    )
    content = HTMLField(
        _lazy("Content"),
        blank=True,
        help_text=_lazy("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _lazy("Risk Report Guide Translation")
        verbose_name_plural = _lazy("Risk Report Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































