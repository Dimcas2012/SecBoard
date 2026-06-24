# SecBoard/app_asset/models.py
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import UniqueConstraint
from app_conf.models import Company
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy as _lazy
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.utils.translation import get_language
import logging
from app_cabinet.models import CabinetUser


# Map language code (from get_language()) to country codes for translations
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
    'hr': ['HR'],
    'sr': ['RS'],
    'tr': ['TR'],
    'ar': ['AE', 'SA'],
    'zh': ['CN'],
    'ja': ['JP'],
    'kk': ['KZ'],
    'be': ['BY'],
    'fi': ['FI'],
    'sv': ['SE'],
    'da': ['DK'],
    'no': ['NO'],
    'et': ['EE'],
    'lv': ['LV'],
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







class CriticalityLevel(models.Model):
    """
    Рівень критичності (Низький, Середній, Високий тощо)
    """
    name = models.CharField(
        _("Level Name"),
        max_length=50,
        help_text=_("Criticality level name, default: English (En). E.g. Low, Medium, High. For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=50,
        blank=True,
        help_text=_("Level name in local language (use Translations inline for per-country names)")
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='criticality_levels',
        verbose_name=_("Company"),
        help_text=_("Leave empty for organization-wide level")
    )
    code = models.CharField(
        _("Level Code"),
        max_length=50,
        help_text=_("Code unique per company (e.g., low, medium, high)")
    )
    cost = models.IntegerField(
        _("Cost"),
        validators=[
            MinValueValidator(0),
            MaxValueValidator(10)
        ],
        help_text=_("Value from 0 to 10")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default="#000000",
        help_text=_("Color in HEX format, e.g. #FF0000")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    description_confid = models.TextField(
        _("Confidentiality Description"),
        blank=True,
        help_text=_("Confidentiality description, default: English (En). For other languages use Translations inline.")
    )
    description_integ = models.TextField(
        _("Integrity Description"),
        blank=True,
        help_text=_("Integrity description, default: English (En). For other languages use Translations inline.")
    )
    description_avail = models.TextField(
        _("Availability Description"),
        blank=True,
        help_text=_("Availability description, default: English (En). For other languages use Translations inline.")
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    def get_name(self):
        """Get localized name based on current site language (via country for translations)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except CriticalityLevelTranslation.DoesNotExist:
                pass
        # No translation for current country: use name for English, name_local or name for others
        lang = (get_language() or '')[:2].lower()
        if lang == 'en':
            return self.name or self.name_local
        return self.name_local or self.name

    def get_local_name(self, country):
        """Get localized name for specific country"""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except CriticalityLevelTranslation.DoesNotExist:
            return self.name_local or self.name

    def _get_description_from_translations(self, attr):
        """Get CIA description for current site language/country, else fallback to base English field."""
        country = get_country_for_current_language()
        if country:
            try:
                trans = self.translations.get(country=country)
                val = getattr(trans, attr, None)
                if val and str(val).strip():
                    return val
            except CriticalityLevelTranslation.DoesNotExist:
                pass
        # Fallback: Basic Information (default English)
        return getattr(self, attr, None) or ''

    def get_description_confid(self):
        """Get Confidentiality description from CriticalityLevelTranslation (current country, else fallback)."""
        return self._get_description_from_translations('description_confid')

    def get_description_integ(self):
        """Get Integrity description from CriticalityLevelTranslation (current country, else fallback)."""
        return self._get_description_from_translations('description_integ')

    def get_description_avail(self):
        """Get Availability description from CriticalityLevelTranslation (current country, else fallback)."""
        return self._get_description_from_translations('description_avail')

    def __str__(self):
        return f"{self.get_name()} (Cost: {self.cost})"

    class Meta:
        verbose_name = _("Criticality Level")
        verbose_name_plural = _("Criticality Levels")
        ordering = ['display_order', 'cost', 'name']
        constraints = [
            UniqueConstraint(
                fields=['company', 'code'],
                name='app_asset_critlevel_company_code_uniq',
            ),
        ]


class CriticalityLevelTranslation(models.Model):
    """
    Переклади рівня критичності для різних країн
    """
    criticality_level = models.ForeignKey(
        CriticalityLevel,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Criticality Level")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='criticality_level_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=50,
        help_text=_("Level name in country's language")
    )
    description_confid = models.TextField(
        _("Confidentiality Description"),
        blank=True,
        help_text=_("Confidentiality description in country's language")
    )
    description_integ = models.TextField(
        _("Integrity Description"),
        blank=True,
        help_text=_("Integrity description in country's language")
    )
    description_avail = models.TextField(
        _("Availability Description"),
        blank=True,
        help_text=_("Availability description in country's language")
    )

    class Meta:
        verbose_name = _("Criticality Level Translation")
        verbose_name_plural = _("Criticality Level Translations")
        constraints = [
            UniqueConstraint(
                fields=['criticality_level', 'country'],
                name='app_asset_critleveltrans_cl_country_uniq',
            ),
        ]
        ordering = ['country__name']

    def __str__(self):
        return f"{self.criticality_level.name} - {self.country.name}: {self.name_local}"


class AssetGroup(models.Model):
    """
    Група активів (Інформаційні системи, Бази даних, Документи тощо)
    """
    name = models.CharField(
        _("Group Name"),
        max_length=100,
        help_text=_("Asset group name, default: English (En). E.g. Information Systems, Databases. For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Group name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Group Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., info_systems, databases)")
    )
    abbreviation = models.CharField(
        _("Abbreviation"),
        max_length=10,
        unique=True,
        help_text=_("Short abbreviation for the group")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#007bff',
        help_text=_("Hex color code for display")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description of this asset group, default: English (En). For other languages use Translations inline.")
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    show_in_software_register = models.BooleanField(
        _("Show in Software Register"),
        default=True,
        help_text=_("If checked, this group will be available in the Group/Type selector of the Software Register.")
    )
    show_in_external_media_register = models.BooleanField(
        _("Show in External Media Register"),
        default=True,
        help_text=_("If checked, this group will be available in the Group/Type selector of the External Media Register.")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("Asset Group")
        verbose_name_plural = _("Asset Groups")
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name_local or self.name

    def get_name(self):
        """Get localized name based on current site language (via country for translations)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except AssetGroupTranslation.DoesNotExist:
                pass
        # No translation for current language: default to EN (name)
        return self.name or self.name_local

    def get_local_name(self, country):
        """Get localized name for specific country. Default to EN if no translation."""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local or self.name
        except AssetGroupTranslation.DoesNotExist:
            return self.name or self.name_local

    def get_description(self):
        """Get localized description: translation for current country, else main description (same as Criticality Level)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.description:
                    return translation.description
            except AssetGroupTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_local_description(self, country):
        """Get localized description for specific country"""
        try:
            translation = self.translations.get(country=country)
            return translation.description or self.description or ''
        except AssetGroupTranslation.DoesNotExist:
            return self.description or ''


class AssetGroupTranslation(models.Model):
    """
    Переклади групи активів для різних країн
    """
    asset_group = models.ForeignKey(
        AssetGroup,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Asset Group")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='asset_group_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Group name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )

    class Meta:
        verbose_name = _("Asset Group Translation")
        verbose_name_plural = _("Asset Group Translations")
        unique_together = ['asset_group', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.asset_group.name} - {self.country.name}: {self.name_local}"

class AssetType(models.Model):
    """
    Тип активу (Сервер, База даних, Документ тощо)
    """
    name = models.CharField(
        _("Type Name"),
        max_length=100,
        help_text=_("Asset type name, default: English (En). E.g. Server, Database, Document. For other languages use Translations inline.")
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
        help_text=_("Unique code (e.g., server, database, document)")
    )
    group = models.ForeignKey(
        AssetGroup,
        on_delete=models.CASCADE,
        related_name='asset_types',
        verbose_name=_("Asset Group")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#007bff',
        help_text=_("Hex color code for display")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description of this asset type, default: English (En). For other languages use Translations inline.")
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("Asset Type")
        verbose_name_plural = _("Asset Types")
        ordering = ['display_order', 'name']
        unique_together = ['code', 'group']

    def __str__(self):
        return self.name_local or self.name

    def get_name(self):
        """Get localized name based on current site language (via country for translations)."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except AssetTypeTranslation.DoesNotExist:
                pass
        # No translation for current language: default to EN (name)
        return self.name or self.name_local

    def get_local_name(self, country):
        """Get localized name for specific country. Default to EN if no translation."""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local or self.name
        except AssetTypeTranslation.DoesNotExist:
            return self.name or self.name_local


class AssetTypeTranslation(models.Model):
    """
    Переклади типу активу для різних країн
    """
    asset_type = models.ForeignKey(
        AssetType,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Asset Type")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='asset_type_translations',
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
        verbose_name = _("Asset Type Translation")
        verbose_name_plural = _("Asset Type Translations")
        unique_together = ['asset_type', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.asset_type.name} - {self.country.name}: {self.name_local}"

class AssetAdministrator(models.Model):
    cabinet_user = models.ForeignKey(
        CabinetUser,
        on_delete=models.CASCADE,
        verbose_name=_("Cabinet User")
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_("Company")
    )

    def __str__(self):
        return f"{self.cabinet_user.user.get_full_name()} ({self.cabinet_user.department}/{self.cabinet_user.position})"

    @property
    def name(self):
        return self.cabinet_user.user.get_full_name()

    @property
    def department(self):
        return self.cabinet_user.department

    @property
    def position(self):
        return self.cabinet_user.position

    @property
    def email(self):
        return self.cabinet_user.user.email

    @property
    def phone(self):
        return self.cabinet_user.phone

    class Meta:
        verbose_name = _("Asset Administrator")
        verbose_name_plural = _("Asset Administrators")
        unique_together = ['cabinet_user', 'company']


class AssetOwner(models.Model):
    cabinet_user = models.ForeignKey(
        CabinetUser,
        on_delete=models.CASCADE,
        verbose_name=_("Cabinet User")
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name=_("Company")
    )

    def __str__(self):
        return f"{self.cabinet_user.user.get_full_name()} ({self.cabinet_user.department}/{self.cabinet_user.position})"

    @property
    def name(self):
        return self.cabinet_user.user.get_full_name()

    @property
    def department(self):
        return self.cabinet_user.department

    @property
    def position(self):
        return self.cabinet_user.position

    @property
    def email(self):
        return self.cabinet_user.user.email

    @property
    def phone(self):
        return self.cabinet_user.phone

    class Meta:
        verbose_name = _("Asset Owner")
        verbose_name_plural = _("Asset Owners")
        unique_together = ['cabinet_user', 'company']

class InformationAsset(models.Model):
    asset_id = models.CharField(max_length=20, unique=True, editable=False, verbose_name=_("Asset ID"))
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    company = models.ForeignKey(Company, on_delete=models.CASCADE, verbose_name=_("Company"))
    group = models.ForeignKey('AssetGroup', on_delete=models.SET_NULL, null=True, verbose_name=_("Group"))
    asset_type = models.ForeignKey('AssetType', on_delete=models.SET_NULL, null=True, verbose_name=_("Asset Type"))
    description = models.TextField(verbose_name=_("Description"))
    location = models.CharField(max_length=200, verbose_name=_("Location"))
    owners = models.ManyToManyField('AssetOwner', related_name='owned_assets', verbose_name=_("Owners"))
    administrators = models.ManyToManyField('AssetAdministrator', related_name='administered_assets',
                                            verbose_name=_("Administrators"))
    software_entries = models.ManyToManyField(
        'SoftwareRegister',
        related_name='information_assets',
        verbose_name=_("Software Register Entries"),
        blank=True,
        help_text=_("Software from Software Register linked to this asset")
    )
    confidentiality = models.ForeignKey('CriticalityLevel', on_delete=models.SET_NULL, null=True, related_name='confidentiality_assets', verbose_name=_("Confidentiality"))
    integrity = models.ForeignKey('CriticalityLevel', on_delete=models.SET_NULL, null=True, related_name='integrity_assets', verbose_name=_("Integrity"))
    availability = models.ForeignKey('CriticalityLevel', on_delete=models.SET_NULL, null=True, related_name='availability_assets', verbose_name=_("Availability"))
    registration_date = models.DateField(verbose_name=_("Registration Date"), null=True, blank=True)
    deletion_date = models.DateField(verbose_name=_("Deletion Date"), null=True, blank=True)
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    access_manage = models.BooleanField(default=False, verbose_name=_("Access Manage"), 
                                       help_text=_("Indicates if this asset can be used in access management"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    last_modified = models.DateTimeField(_("Last Modified"), auto_now=True)
    last_modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='modified_assets')
    actualization_date = models.DateTimeField(_("Actualization Date"), null=True, blank=True,
                                             help_text=_("Date when the asset was last actualized by owner"))
    actualized_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='actualized_assets',
                                     help_text=_("User who actualized this asset"))
    marked_no_longer_actual_at = models.DateTimeField(
        _("Marked no longer actual at"),
        null=True,
        blank=True,
        help_text=_("Date when the asset was marked as no longer actual by owner")
    )
    marked_no_longer_comment = models.TextField(
        _("Marked no longer actual comment"),
        blank=True,
        help_text=_("Optional comment when the asset was marked as no longer actual")
    )

    def save(self, *args, **kwargs):
        # Save the model first to get the ID
        if not self.pk:  # Якщо це новий об'єкт
            super().save(*args, **kwargs)
            # Після збереження генеруємо asset_id використовуючи ID
            self.asset_id = f"A{self.pk:06d}"  # Форматуємо ID як 6-значне число з ведучими нулями
            # Зберігаємо ще раз для оновлення asset_id
            super().save(update_fields=['asset_id'])
        else:
            # Якщо це існуючий об'єкт, просто зберігаємо його
            super().save(*args, **kwargs)

    def get_criticality(self):
        levels = [
            (self.confidentiality, self.confidentiality.cost if self.confidentiality else 0),
            (self.integrity, self.integrity.cost if self.integrity else 0),
            (self.availability, self.availability.cost if self.availability else 0)
        ]
        max_level = max(levels, key=lambda x: x[1])
        current_language = get_language()[:2]
        if max_level[0]:
            return {
                'name': max_level[0].get_name() if max_level[0] else '',
                'cost': max_level[0].cost,
                'color': max_level[0].color
            }
        return {'name': _("Undefined"), 'cost': 0, 'color': "#000000"}

    def get_quantitative_criticality(self):
        return self.get_criticality()['cost']

    def get_qualitative_criticality(self):
        return self.get_criticality()['name']

    def get_criticality_color(self):
        return self.get_criticality()['color']

    def get_criticality_display(self):
        criticality = self.get_criticality()
        return f"{criticality['name']} / {criticality['cost']}"

    def __str__(self):
        return f"{self.asset_id}: {self.name}"

    class Meta:
        verbose_name = _("Information Asset")
        verbose_name_plural = _("Information Assets")
        ordering = ['asset_id']



class AssetHistory(models.Model):
    """Модель для зберігання історії змін інформаційних активів"""
    ACTION_CREATED = 'created'
    ACTION_MODIFIED = 'modified'
    ACTION_DELETED = 'deleted'
    ACTION_OWNERS_CHANGED = 'owners_changed'
    ACTION_ADMINISTRATORS_CHANGED = 'administrators_changed'
    ACTION_CIA_CHANGED = 'cia_changed'
    ACTION_CIA_CONFIDENTIALITY_CHANGED = 'confidentiality_changed'
    ACTION_CIA_INTEGRITY_CHANGED = 'integrity_changed'
    ACTION_CIA_AVAILABILITY_CHANGED = 'availability_changed'

    ACTION_CHOICES = [
        (ACTION_CREATED, _('Created')),
        (ACTION_MODIFIED, _('Modified')),
        (ACTION_DELETED, _('Deleted')),
        (ACTION_OWNERS_CHANGED, _('Owners Changed')),
        (ACTION_ADMINISTRATORS_CHANGED, _('Administrators Changed')),
        (ACTION_CIA_CHANGED, _('CIA Changed')),
        (ACTION_CIA_CONFIDENTIALITY_CHANGED, _('Confidentiality Changed')),
        (ACTION_CIA_INTEGRITY_CHANGED, _('Integrity Changed')),
        (ACTION_CIA_AVAILABILITY_CHANGED, _('Availability Changed')),
    ]

    asset = models.ForeignKey(InformationAsset, on_delete=models.CASCADE, related_name='history', verbose_name=_("Asset"))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name=_("Action"))
    action_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Action By"))
    details = models.TextField(blank=True, verbose_name=_("Details"))
    # JSON поле для зберігання деталей змін (before/after)
    changes = models.JSONField(null=True, blank=True, verbose_name=_("Changes"))

    class Meta:
        verbose_name = _("Asset History")
        verbose_name_plural = _("Asset History")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['asset', '-timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.asset.asset_id} - {self.get_action_display()} at {self.timestamp}"

    def get_formatted_timestamp(self):
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S')

    def get_action_by_name(self):
        if self.action_by:
            return self.action_by.get_full_name() or self.action_by.username
        return _('System')


class InformationAssetSoftwareSelection(models.Model):
    information_asset = models.ForeignKey(
        InformationAsset,
        on_delete=models.CASCADE,
        related_name='software_selections',
        verbose_name=_("Information Asset"),
    )
    software_register = models.ForeignKey(
        'SoftwareRegister',
        on_delete=models.CASCADE,
        related_name='asset_selections',
        verbose_name=_("Software Register Entry"),
    )
    selected_version = models.CharField(
        _("Selected Version"),
        max_length=100,
        blank=True,
        default='',
    )
    selected_license_quantity = models.PositiveIntegerField(
        _("Selected License Quantity"),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Information Asset Software Selection")
        verbose_name_plural = _("Information Asset Software Selections")
        unique_together = ['information_asset', 'software_register']

    def __str__(self):
        return f"{self.information_asset} -> {self.software_register}"


class AccessAssets(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name=_("Group"))
    has_access = models.BooleanField(default=False, verbose_name=_("Has access to Information Assets"))
    can_edit = models.BooleanField(default=False, verbose_name=_("Can edit Information Assets"))
    manage_adm_own = models.BooleanField(default=False, verbose_name=_("Can edit Administrator and Owner Assets"))
    manage_types = models.BooleanField(default=False, verbose_name=_("Can edit Types Assets"))
    can_view_software_register = models.BooleanField(
        default=False,
        verbose_name=_("Can view Software Register"),
        help_text=_("Can open and view the Software Register page")
    )
    can_edit_software_register = models.BooleanField(
        default=False,
        verbose_name=_("Can edit Software Register"),
        help_text=_("Can add, edit and delete entries in Software Register")
    )
    can_view_external_media_register = models.BooleanField(
        default=False,
        verbose_name=_("Can view External Media Register"),
        help_text=_("Can open and view the External Media Register page")
    )
    can_edit_external_media_register = models.BooleanField(
        default=False,
        verbose_name=_("Can edit External Media Register"),
        help_text=_("Can add, edit and delete entries in External Media Register")
    )
    companies = models.ManyToManyField(Company, blank=True, related_name='access_assets', verbose_name=_("Companies"))
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = _("Access to Assets")
        verbose_name_plural = _("Access to Assets")

    def __str__(self):
        return f"{self.group.name} - Has Access: {self.has_access}, Edit: {self.can_edit}, View SW: {self.can_view_software_register}, Edit SW: {self.can_edit_software_register}"


class SoftwareStatus(models.Model):
    """
    Статус ПЗ (дозволено, заборонено тощо) – аналогічно Asset Types.
    """
    name = models.CharField(
        _("Status Name"),
        max_length=100,
        help_text=_("Default: English (En). E.g. Allowed, Forbidden.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True
    )
    code = models.CharField(
        _("Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., allowed, forbidden)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#6c757d',
        help_text=_("Hex color for display")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("Software Status")
        verbose_name_plural = _("Software Statuses")
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name_local or self.name

    def get_name(self):
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except SoftwareStatusTranslation.DoesNotExist:
                pass
        return self.name or self.name_local


class SoftwareStatusTranslation(models.Model):
    software_status = models.ForeignKey(
        SoftwareStatus,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Software Status")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='software_status_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100
    )

    class Meta:
        verbose_name = _("Software Status Translation")
        verbose_name_plural = _("Software Status Translations")
        unique_together = ['software_status', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.software_status.name} — {self.country.name}"


class SoftwareLicenseType(models.Model):
    """
    License type for software register entries (e.g., subscription, perpetual).
    """
    name = models.CharField(
        _("License Type Name"),
        max_length=100,
        help_text=_("Default: English (En). E.g. Subscription, Perpetual.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True
    )
    code = models.CharField(
        _("Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., subscription, perpetual)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#6c757d',
        help_text=_("Hex color for display")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("Software License Type")
        verbose_name_plural = _("Software License Types")
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name_local or self.name

    def get_name(self):
        country = get_country_for_current_language()
        if country:
            try:
                t = self.translations.get(country=country)
                if t.name_local:
                    return t.name_local
            except SoftwareLicenseTypeTranslation.DoesNotExist:
                pass
        return self.name or self.name_local


class SoftwareLicenseTypeTranslation(models.Model):
    software_license_type = models.ForeignKey(
        SoftwareLicenseType,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Software License Type")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='software_license_type_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100
    )

    class Meta:
        verbose_name = _("Software License Type Translation")
        verbose_name_plural = _("Software License Type Translations")
        unique_together = ['software_license_type', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.software_license_type.name} — {self.country.name}"


class SoftwareRegister(models.Model):
    """
    Реєстр дозволеного/забороненого програмного забезпечення.
    Register of allowed/forbidden software.
    """
    name = models.CharField(
        _("Software Name"),
        max_length=255,
        help_text=_("Name of the software product")
    )
    status = models.ForeignKey(
        SoftwareStatus,
        on_delete=models.PROTECT,
        related_name='software_entries',
        verbose_name=_("Status"),
        help_text=_("Allowed, Forbidden, etc.")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Optional description or justification")
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='software_register_entries',
        verbose_name=_("Company"),
        help_text=_("Leave empty for organization-wide rule")
    )
    version_pattern = models.CharField(
        _("Version Pattern"),
        max_length=100,
        blank=True,
        help_text=_("Optional version pattern (e.g. 1.2.*, any)")
    )
    # New fields
    manufacturer = models.CharField(
        _("Manufacturer"),
        max_length=255,
        blank=True,
        help_text=_("Vendor / manufacturer")
    )
    url = models.URLField(
        _("URL"),
        max_length=500,
        blank=True,
        help_text=_("Product or vendor URL")
    )
    group = models.ForeignKey(
        'AssetGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='software_entries',
        verbose_name=_("Asset Group"),
    )
    asset_type = models.ForeignKey(
        'AssetType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='software_entries',
        verbose_name=_("Asset Type"),
    )
    confidentiality = models.ForeignKey(
        'CriticalityLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confidentiality_software',
        verbose_name=_("Confidentiality"),
    )
    integrity = models.ForeignKey(
        'CriticalityLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='integrity_software',
        verbose_name=_("Integrity"),
    )
    availability = models.ForeignKey(
        'CriticalityLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='availability_software',
        verbose_name=_("Availability"),
    )
    license_type = models.CharField(
        _("License Type"),
        max_length=100,
        blank=True,
        help_text=_("Type of license")
    )
    license_quantity = models.PositiveIntegerField(
        _("License Quantity"),
        null=True,
        blank=True,
        help_text=_("Number of licenses")
    )
    license_valid_until = models.DateField(
        _("License Valid Until"),
        null=True,
        blank=True,
        help_text=_("License expiry date")
    )
    notes = models.TextField(
        _("Notes"),
        blank=True,
        help_text=_("Additional notes")
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display (lower numbers first)")
    )
    owners = models.ManyToManyField(
        AssetOwner,
        related_name='software_register_entries',
        verbose_name=_("Owners"),
        blank=True,
        help_text=_("Owners from Cabinet users (same as Assets Register)")
    )
    actualization_date = models.DateTimeField(
        _("Actualization date"),
        null=True,
        blank=True,
        help_text=_("Date when the entry was last actualized by owner")
    )
    actualized_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actualized_software_entries',
        verbose_name=_("Actualized by"),
        help_text=_("User who actualized this software entry")
    )
    marked_no_longer_actual_at = models.DateTimeField(
        _("Marked no longer actual at"),
        null=True,
        blank=True,
        help_text=_("Date when the entry was marked as no longer actual by owner")
    )
    marked_no_longer_comment = models.TextField(
        _("Marked no longer actual comment"),
        blank=True,
        default='',
        help_text=_("Optional comment when the entry was marked as no longer actual")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("Software Register Entry")
        verbose_name_plural = _("Software Register (Allowed/Forbidden)")
        ordering = ['display_order', 'name']

    def __str__(self):
        status_name = self.status.get_name() if self.status_id else ''
        return f"{self.name} ({status_name})"

    def get_license_type_name(self):
        code = (self.license_type or '').strip().lower()
        if not code:
            return ''
        try:
            return SoftwareLicenseType.objects.get(code=code, is_active=True).get_name()
        except SoftwareLicenseType.DoesNotExist:
            return self.license_type


class SoftwareRegisterHistory(models.Model):
    """Audit log for Software Register entry changes (who, when, what)."""
    ACTION_CREATED = 'created'
    ACTION_MODIFIED = 'modified'
    ACTION_DELETED = 'deleted'
    ACTION_CHOICES = [
        (ACTION_CREATED, _('Created')),
        (ACTION_MODIFIED, _('Modified')),
        (ACTION_DELETED, _('Deleted')),
    ]
    software_register = models.ForeignKey(
        SoftwareRegister,
        on_delete=models.SET_NULL,
        related_name='history',
        verbose_name=_("Software Register Entry"),
        null=True,
        blank=True,
    )
    entry_name = models.CharField(_("Entry name"), max_length=255, blank=True, help_text=_("Stored when entry is deleted"))
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name=_("Action"))
    action_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Action By"),
    )
    details = models.TextField(blank=True, verbose_name=_("Details"))
    changes = models.JSONField(null=True, blank=True, verbose_name=_("Changes"))

    class Meta:
        verbose_name = _("Software Register History")
        verbose_name_plural = _("Software Register History")
        ordering = ['-timestamp']

    def __str__(self):
        name = self.entry_name or (self.software_register.name if self.software_register else '')
        return f"{name or self.software_register_id} - {self.get_action_display()} at {self.timestamp}"


def software_register_file_upload_to(instance, filename):
    """Store under software_register/<entry_id>/<sanitized_filename>."""
    import os
    from django.utils.text import get_valid_filename
    safe_name = get_valid_filename(os.path.basename(filename)) or 'file'
    return f"software_register/{instance.software_register_id}/{safe_name}"


class SoftwareRegisterFile(models.Model):
    """One or more files attached to a Software Register entry; stores file hash (SHA256) for integrity."""
    software_register = models.ForeignKey(
        SoftwareRegister,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name=_("Software Register Entry")
    )
    file = models.FileField(
        _("File"),
        upload_to=software_register_file_upload_to,
        max_length=500,
        help_text=_("Upload one or more files (e.g. installers, licenses)")
    )
    file_hash = models.CharField(
        _("Hash (SHA256)"),
        max_length=64,
        blank=True,
        editable=False,
        help_text=_("SHA256 hash of the file content")
    )
    label = models.CharField(
        _("Label"),
        max_length=255,
        blank=True,
        help_text=_("Optional display name for the file")
    )
    uploaded_at = models.DateTimeField(_("Uploaded at"), auto_now_add=True)

    class Meta:
        verbose_name = _("Software Register File")
        verbose_name_plural = _("Software Register Files")
        ordering = ['uploaded_at']

    def __str__(self):
        return self.label or (self.file.name.split('/')[-1] if self.file else '')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.file and not self.file_hash:
            self._compute_and_save_hash()

    def _compute_and_save_hash(self):
        import hashlib
        try:
            self.file.open('rb')
            h = hashlib.sha256()
            for chunk in self.file.chunks():
                h.update(chunk)
            self.file.close()
            new_hash = h.hexdigest()
            if new_hash != self.file_hash:
                SoftwareRegisterFile.objects.filter(pk=self.pk).update(file_hash=new_hash)
                self.file_hash = new_hash
        except Exception:
            pass


# --- External Media Register (Реєстр зовнішніх носіїв) ---

class ExternalMediaStatus(models.Model):
    """Status for external media (e.g. Allowed, Forbidden)."""
    name = models.CharField(_("Status Name"), max_length=100)
    name_local = models.CharField(_("Local Name"), max_length=100, blank=True)
    code = models.CharField(_("Code"), max_length=50, unique=True)
    color = models.CharField(_("Color"), max_length=7, default='#6c757d')
    display_order = models.IntegerField(_("Display Order"), default=0)
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("External Media Status")
        verbose_name_plural = _("External Media Statuses")
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name_local or self.name

    def get_name(self):
        country = get_country_for_current_language()
        if country:
            try:
                t = ExternalMediaStatusTranslation.objects.get(status=self, country=country)
                if t.name_local:
                    return t.name_local
            except ExternalMediaStatusTranslation.DoesNotExist:
                pass
        return self.name or self.name_local


class ExternalMediaStatusTranslation(models.Model):
    status = models.ForeignKey(ExternalMediaStatus, on_delete=models.CASCADE, related_name='translations')
    country = models.ForeignKey('app_conf.Country', on_delete=models.CASCADE, related_name='external_media_status_translations')
    name_local = models.CharField(_("Local Name"), max_length=100)

    class Meta:
        unique_together = ['status', 'country']


class ExternalMediaRegister(models.Model):
    """Реєстр зовнішніх носіїв. Register of external media (USB, disks, etc.)."""
    name = models.CharField(_("Name"), max_length=255, help_text=_("Name or description of the media"))
    status = models.ForeignKey(
        ExternalMediaStatus,
        on_delete=models.PROTECT,
        related_name='external_media_entries',
        verbose_name=_("Status"),
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='external_media_register_entries',
        verbose_name=_("Company"),
    )
    group = models.ForeignKey(
        'AssetGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='external_media_register_entries',
        verbose_name=_("Asset Group"),
    )
    asset_type = models.ForeignKey(
        'AssetType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='external_media_register_entries',
        verbose_name=_("Asset Type"),
    )
    confidentiality = models.ForeignKey(
        'CriticalityLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confidentiality_external_media',
        verbose_name=_("Confidentiality"),
    )
    integrity = models.ForeignKey(
        'CriticalityLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='integrity_external_media',
        verbose_name=_("Integrity"),
    )
    availability = models.ForeignKey(
        'CriticalityLevel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='availability_external_media',
        verbose_name=_("Availability"),
    )
    serial_number = models.CharField(_("Serial number"), max_length=100, blank=True)
    description = models.TextField(_("Description"), blank=True)
    notes = models.TextField(_("Notes"), blank=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    display_order = models.IntegerField(_("Display Order"), default=0)
    owners = models.ManyToManyField(
        AssetOwner,
        related_name='external_media_register_entries',
        verbose_name=_("Owners"),
        blank=True,
        help_text=_("Owners from Cabinet users (same as Assets Register)")
    )
    actualization_date = models.DateTimeField(
        _("Actualization date"),
        null=True,
        blank=True,
        help_text=_("Date when the entry was last actualized by owner")
    )
    actualized_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actualized_external_media_entries',
        verbose_name=_("Actualized by"),
        help_text=_("User who actualized this external media entry")
    )
    marked_no_longer_actual_at = models.DateTimeField(
        _("Marked no longer actual at"),
        null=True,
        blank=True,
        help_text=_("Date when the entry was marked as no longer actual by owner")
    )
    marked_no_longer_comment = models.TextField(
        _("Marked no longer actual comment"),
        blank=True,
        default='',
        help_text=_("Optional comment when the entry was marked as no longer actual")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("External Media Register Entry")
        verbose_name_plural = _("External Media Register")
        ordering = ['display_order', 'name']

    def __str__(self):
        status_name = self.status.get_name() if self.status_id else ''
        return f"{self.name} ({status_name})"


class ExternalMediaRegisterHistory(models.Model):
    """Audit log for External Media Register changes."""
    ACTION_CREATED = 'created'
    ACTION_MODIFIED = 'modified'
    ACTION_DELETED = 'deleted'
    ACTION_CHOICES = [
        (ACTION_CREATED, _('Created')),
        (ACTION_MODIFIED, _('Modified')),
        (ACTION_DELETED, _('Deleted')),
    ]
    external_media_register = models.ForeignKey(
        ExternalMediaRegister,
        on_delete=models.SET_NULL,
        related_name='history',
        null=True,
        blank=True,
    )
    entry_name = models.CharField(_("Entry name"), max_length=255, blank=True)
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    action_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.TextField(blank=True)
    changes = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        name = self.entry_name or (self.external_media_register.name if self.external_media_register else '')
        return f"{name} - {self.get_action_display()} at {self.timestamp}"


def external_media_file_upload_to(instance, filename):
    import os
    from django.utils.text import get_valid_filename
    safe_name = get_valid_filename(os.path.basename(filename)) or 'file'
    return f"external_media_register/{instance.external_media_register_id}/{safe_name}"


class ExternalMediaRegisterFile(models.Model):
    """File attached to an External Media Register entry (with SHA256 hash)."""
    external_media_register = models.ForeignKey(
        ExternalMediaRegister,
        on_delete=models.CASCADE,
        related_name='files',
    )
    file = models.FileField(_("File"), upload_to=external_media_file_upload_to, max_length=500)
    file_hash = models.CharField(_("Hash (SHA256)"), max_length=64, blank=True, editable=False)
    label = models.CharField(_("Label"), max_length=255, blank=True)
    uploaded_at = models.DateTimeField(_("Uploaded at"), auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return self.label or (self.file.name.split('/')[-1] if self.file else '')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.file and not self.file_hash:
            self._compute_and_save_hash()

    def _compute_and_save_hash(self):
        import hashlib
        try:
            self.file.open('rb')
            h = hashlib.sha256()
            for chunk in self.file.chunks():
                h.update(chunk)
            self.file.close()
            new_hash = h.hexdigest()
            if new_hash != self.file_hash:
                ExternalMediaRegisterFile.objects.filter(pk=self.pk).update(file_hash=new_hash)
                self.file_hash = new_hash
        except Exception:
            pass


from tinymce.models import HTMLField


class AssetGuide(models.Model):
    """Base Guide for Information Assets. Source content for translations."""
    base_content = HTMLField(
        _lazy("Base content"),
        blank=True,
        help_text=_lazy("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _lazy("Asset Guide")
        verbose_name_plural = _lazy("Asset Guides")

    def __str__(self):
        return _("Information Assets Guide")


class AssetGuideTranslation(models.Model):
    """Per-country (language) translations of the Asset Guide."""
    asset_guide = models.ForeignKey(
        AssetGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_lazy("Asset Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="asset_guide_translations",
        verbose_name=_lazy("Country")
    )
    content = HTMLField(
        _lazy("Content"),
        blank=True,
        help_text=_lazy("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _lazy("Asset Guide Translation")
        verbose_name_plural = _lazy("Asset Guide Translations")
        unique_together = ["asset_guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.asset_guide} — {self.country.name}"


class SoftwareGuide(models.Model):
    """Base Guide for Software Register. Source content for translations."""
    base_content = HTMLField(
        _lazy("Base content"),
        blank=True,
        help_text=_lazy("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _lazy("Software Guide")
        verbose_name_plural = _lazy("Software Guides")

    def __str__(self):
        return _("Software Register Guide")


class SoftwareGuideTranslation(models.Model):
    """Per-country (language) translations of the Software Guide."""
    software_guide = models.ForeignKey(
        SoftwareGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_lazy("Software Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="software_guide_translations",
        verbose_name=_lazy("Country")
    )
    content = HTMLField(
        _lazy("Content"),
        blank=True,
        help_text=_lazy("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _lazy("Software Guide Translation")
        verbose_name_plural = _lazy("Software Guide Translations")
        unique_together = ["software_guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.software_guide} — {self.country.name}"


class ExternalMediaGuide(models.Model):
    """Base Guide for External Media Register. Source content for translations."""
    base_content = HTMLField(
        _lazy("Base content"),
        blank=True,
        help_text=_lazy("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _lazy("External Media Guide")
        verbose_name_plural = _lazy("External Media Guides")

    def __str__(self):
        return _("External Media Register Guide")


class ExternalMediaGuideTranslation(models.Model):
    """Per-country (language) translations of the External Media Guide."""
    external_media_guide = models.ForeignKey(
        ExternalMediaGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_lazy("External Media Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="external_media_guide_translations",
        verbose_name=_lazy("Country")
    )
    content = HTMLField(
        _lazy("Content"),
        blank=True,
        help_text=_lazy("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _lazy("External Media Guide Translation")
        verbose_name_plural = _lazy("External Media Guide Translations")
        unique_together = ["external_media_guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.external_media_guide} — {self.country.name}"


