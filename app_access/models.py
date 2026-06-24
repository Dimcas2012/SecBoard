# SecBoard/app_access/models.py
import re
from django.db import models, transaction
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.utils.translation import gettext_lazy as _, gettext, get_language
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging
from mptt.models import MPTTModel, TreeForeignKey
from django.db.models import F, Q
from django.conf import settings
from encrypted_model_fields.fields import EncryptedCharField  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Map language code to country codes for translations (same as app_risk / app_keycert)
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


def get_country_for_language(lang_code):
    """Return first Country for given language code (for translation lookups)."""
    from app_conf.models import Country
    lc = (lang_code or '')[:2].lower()
    if lc == 'uk':
        lc = 'ua'
    if not lc:
        return None
    for country_code in LANGUAGE_COUNTRY_MAP.get(lc, []):
        try:
            return Country.objects.filter(code__iexact=country_code).first()
        except Exception:
            continue
    return None


class ThirdPartyOrganization(models.Model):
    """
    Model for storing Third Party Organizations
    """
    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name=_("Organization Name")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    contact_email = models.EmailField(
        blank=True,
        verbose_name=_("Contact Email")
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Contact Phone")
    )
    website = models.URLField(
        blank=True,
        verbose_name=_("Website")
    )
    address = models.TextField(
        blank=True,
        verbose_name=_("Address")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_third_party_organizations',
        verbose_name=_("Created By")
    )

    class Meta:
        verbose_name = _("Third Party Organization")
        verbose_name_plural = _("Third Party Organizations")
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def users_count(self):
        """Get count of users in this organization"""
        return self.third_party_users.count()


class ThirdPartyUser(models.Model):
    """
    Model for storing Third Party users information
    """
    first_name = models.CharField(
        max_length=100,
        verbose_name=_("First Name")
    )
    last_name = models.CharField(
        max_length=100,
        verbose_name=_("Last Name")
    )
    email = models.EmailField(
        unique=True,
        verbose_name=_("Email"),
        help_text=_("Email must be unique among all third party users")
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Phone")
    )
    organization = models.ForeignKey(
        ThirdPartyOrganization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='third_party_users',
        verbose_name=_("Organization")
    )
    # Зберігаємо старе поле для зворотної сумісності
    organization_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Organization Name (Legacy)"),
        help_text=_("Legacy field for backward compatibility")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    
    # Metadata fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_third_party_users',
        verbose_name=_("Created By")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )

    class Meta:
        verbose_name = _("Third Party User")
        verbose_name_plural = _("Third Party Users")
        ordering = ['first_name', 'last_name']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self):
        if self.email:
            # Перевіряємо унікальність email серед активних користувачів
            existing = ThirdPartyUser.objects.filter(
                email__iexact=self.email,
                is_active=True
            ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError({
                    'email': _("A third party user with this email already exists.")
                })


class ApiCredential(models.Model):
    """
    Model to store API credentials for users
    """
    ENVIRONMENT_CHOICES = [
        ('production', _('Production')),
        ('test', _('Test')),
        ('development', _('Development'))
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='api_credentials',
        verbose_name=_("User")
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("Credential Name")
    )
    url = models.URLField(
        verbose_name=_("API URL"),
        max_length=255
    )
    email = models.EmailField(
        verbose_name=_("Email")
    )
    password = EncryptedCharField(
        max_length=255,
        verbose_name=_("Password")
    )
    company = models.ForeignKey(
        'app_conf.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_credentials',
        verbose_name=_("Company")
    )
    information_system = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_credentials',
        verbose_name=_("Information System")
    )
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default='test',
        verbose_name=_("Environment")
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Default Credential")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )

    class Meta:
        verbose_name = _("API Credential")
        verbose_name_plural = _("API Credentials")
        ordering = ['-is_default', 'name']
        unique_together = [('user', 'name')]

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    def save(self, *args, **kwargs):
        # If this credential is set as default, unset default for other credentials
        if self.is_default:
            ApiCredential.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        # If this is the only credential for the user, make it default
        if not self.pk and not ApiCredential.objects.filter(user=self.user).exists():
            self.is_default = True
            
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        is_default = self.is_default
        super().delete(*args, **kwargs)
        
        # If the deleted credential was default, set another one as default
        if is_default:
            first_credential = ApiCredential.objects.filter(user=self.user).first()
            if first_credential:
                first_credential.is_default = True
                first_credential.save(update_fields=['is_default'])


class AccessRight(models.Model):
    """Access Right with name/code/description + per-country Translations (same pattern as AccessFunctionIS)."""
    system = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.CASCADE,
        related_name='access_rights',
        verbose_name=_("Information System")
    )
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Access Right Name"),
        max_length=200,
        blank=True,
        help_text=_("Right name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=200,
        blank=True,
        help_text=_("Right name in local language (use Translations inline for per-country names)")
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
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    color = models.CharField(_("Color"), max_length=7, default="#000000")
    order = models.PositiveIntegerField(_("Order"), default=0)
    environment = models.CharField(
        max_length=20,
        choices=[
            ('production', _('Production')),
            ('test', _('Test')),
            ('development', _('Development'))
        ],
        default='test',
        verbose_name=_("Environment")
    )
    is_object_specific = models.BooleanField(
        default=False,
        verbose_name=_("Object Specific Access Right"),
        help_text=_("If true, this access right is only available for specific objects and won't appear in default system access rights")
    )
    created_for_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='custom_access_rights',
        verbose_name=_("Created For Object"),
        help_text=_("The specific object this access right was created for")
    )
    class Meta:
        verbose_name = _("Access Right")
        verbose_name_plural = _("Access Rights")
        ordering = ['order', 'name']

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:80]

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '')[:80].strip()
            self.code = self._slugify_code(base) or ''
        super().save(*args, **kwargs)

    def get_name_by_language(self, lang):
        """Single language: return main name (multilingual removed for app_access)."""
        return self.name or self.name_local or ''

    def get_description_by_language(self, lang):
        """Single language: return main description (multilingual removed for app_access)."""
        return self.description or ''

    def get_name(self, language=None):
        return self.name or self.name_local or ''

    def get_description(self, language=None):
        return self.description or ''

    def get_local_name(self, country):
        try:
            t = self.translations.get(country=country)
            if t.name_local:
                return t.name_local
        except AccessRightTranslation.DoesNotExist:
            pass
        return self.name or self.name_local or _("Unnamed")

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except AccessRightTranslation.DoesNotExist:
            return self.description or ''

    def __str__(self):
        return self.get_name() or self.name or self.name_local or _("Unnamed")


class AccessRightTranslation(models.Model):
    """Translations of access right for different countries.
    Can be added in Django admin (Access Right → Translations inline) or in the application create/edit modals."""
    access_right = models.ForeignKey(
        AccessRight,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Access Right")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='access_right_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=200, help_text=_("Right name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))

    class Meta:
        verbose_name = _("Access Right Translation")
        verbose_name_plural = _("Access Right Translations")
        unique_together = ['access_right', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.access_right.name or self.access_right.name_local} - {self.country.name}: {self.name_local}"


class AccessRoles(models.Model):
    """Access Role with name/code/description + per-country Translations (same pattern as AccessRight)."""
    system = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.CASCADE,
        related_name='access_roles',
        verbose_name=_("Information System")
    )
    # Default (English) fields – for other languages use Translations (admin or modals)
    name = models.CharField(
        _("Role Name"),
        max_length=200,
        blank=True,
        help_text=_("Role name (default: English). For other languages add translations in admin (Translations inline) or in the application create/edit modals.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=200,
        blank=True,
        help_text=_("Role name in local language (use Translations inline for per-country names)")
    )
    code = models.CharField(
        _("Code"),
        max_length=80,
        blank=True,
        help_text=_("Unique code per system/environment (auto-generated from name if empty)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description (default: English). For other languages add translations in admin or in the application modals.")
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    color = models.CharField(_("Color"), max_length=7, default="#000000")
    functions = models.ManyToManyField(
        'AccessFunctionIS',
        related_name='roles',
        blank=True,
        verbose_name=_("Functions")
    )
    order = models.PositiveIntegerField(_("Order"), default=0)
    environment = models.CharField(
        max_length=20,
        choices=[
            ('production', _('Production')),
            ('test', _('Test')),
            ('development', _('Development'))
        ],
        default='test',
        verbose_name=_("Environment")
    )
    is_object_specific = models.BooleanField(
        default=False,
        verbose_name=_("Object Specific Role"),
        help_text=_("If true, this role is only available for specific objects and won't appear in default system roles")
    )
    created_for_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='custom_roles',
        verbose_name=_("Created For Object"),
        help_text=_("The specific object this role was created for")
    )
    class Meta:
        verbose_name = _("Access Role")
        verbose_name_plural = _("Access Roles")
        ordering = ['order', 'name', 'code']
        unique_together = [('system', 'code', 'environment')]

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:80]

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '')[:80].strip()
            self.code = self._slugify_code(base) or ''
            if self.code and self.pk is None:
                pass
            if self.code and self.system_id:
                from django.db.models import Count
                existing = AccessRoles.objects.filter(
                    system_id=self.system_id, environment=self.environment, code=self.code
                ).exclude(pk=self.pk)
                n = 0
                orig_code = self.code
                while existing.exists():
                    n += 1
                    self.code = f"{orig_code}-{n}"[:80]
                    existing = AccessRoles.objects.filter(
                        system_id=self.system_id, environment=self.environment, code=self.code
                    ).exclude(pk=self.pk)
        super().save(*args, **kwargs)

    def get_name_by_language(self, lang):
        """Single language: return main name (multilingual removed for app_access)."""
        return self.name or self.name_local or ''

    def get_description_by_language(self, lang):
        """Single language: return main description (multilingual removed for app_access)."""
        return self.description or ''

    def get_name(self, language=None):
        return self.name or self.name_local or ''

    def get_description(self, language=None):
        return self.description or ''

    def get_local_name(self, country):
        try:
            t = self.translations.get(country=country)
            if t.name_local:
                return t.name_local
        except AccessRolesTranslation.DoesNotExist:
            pass
        return self.name or self.name_local or _("Unnamed")

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except AccessRolesTranslation.DoesNotExist:
            return self.description or ''

    def __str__(self):
        return self.get_name() or self.name or self.name_local or _("Unnamed")


class AccessRolesTranslation(models.Model):
    """Translations of access role for different countries.
    Can be added in Django admin (Access Role → Translations inline) or in the application create/edit modals."""
    access_role = models.ForeignKey(
        AccessRoles,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Access Role")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='access_role_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=200, help_text=_("Role name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))

    class Meta:
        verbose_name = _("Access Role Translation")
        verbose_name_plural = _("Access Role Translations")
        unique_together = ['access_role', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.access_role.name or self.access_role.name_local} - {self.country.name}: {self.name_local}"


class AccessStatus(models.Model):
    """Access Status with single name/description (multilingual removed for app_access)."""
    system = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.CASCADE,
        related_name='access_status',
        verbose_name=_("Information System")
    )
    name = models.CharField(_("Name"), max_length=200, blank=True)
    description = models.TextField(_("Description"), blank=True)
    color = models.CharField(max_length=7, default="#000000", verbose_name=_("Color"))
    order = models.PositiveIntegerField(_("Order"), default=0)
    environment = models.CharField(
        max_length=20,
        choices=[
            ('production', _('Production')),
            ('test', _('Test')),
            ('development', _('Development'))
        ],
        default='test',
        verbose_name=_("Environment")
    )
    is_object_specific = models.BooleanField(
        default=False,
        verbose_name=_("Object Specific Status"),
        help_text=_("If true, this status is only available for specific objects and won't appear in default system statuses")
    )
    created_for_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='custom_statuses',
        verbose_name=_("Created For Object"),
        help_text=_("The specific object this status was created for")
    )

    class Meta:
        verbose_name = _("Access Status")
        verbose_name_plural = _("Access Statuses")
        ordering = ['order', 'name']

    def get_name(self, language=None):
        return self.name or ''

    def get_description(self, language=None):
        return self.description or ''

    def __str__(self):
        return self.name or ''


class AccessISAM(models.Model):
    """
    Model for managing access rights to Information Systems Access Matrix (ISAM)
    """
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE, 
        verbose_name=_("Group")
    )
    has_access_matrix = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Access Matrix")
    )
    can_edit_matrix = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Access Matrix")
    )
    has_access_records = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Records")
    )
    can_add_access_records = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Access Records")
    )
    can_edit_access_records = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Access Records")
    )
    can_delete_access_records = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Access Records")
    )
    has_access_config_is = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Config IS")
    )
    can_add_access_config_is = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Access Config IS")
    )
    can_edit_access_config_is = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Access Config IS")
    )
    can_delete_access_config_is = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Access Config IS")
    )
    has_access_manage_ar = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Manage Access Requests")
    )
    can_add_manage_ar = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Manage Access Requests")
    )
    can_edit_manage_ar = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Manage Access Requests")
    )
    can_delete_manage_ar = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Manage Access Requests")
    )
    has_access_notification_settings = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to Notification Settings")
    )
    can_add_notification_settings = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Notification Settings")
    )
    can_edit_notification_settings = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Notification Settings")
    )
    can_delete_notification_settings = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Notification Settings")
    )
    has_access_api = models.BooleanField(
        default=False, 
        verbose_name=_("Has access to API")
    )
    can_add_access_api = models.BooleanField(
        default=False, 
        verbose_name=_("Can add Access API")
    )
    can_edit_access_api = models.BooleanField(
        default=False, 
        verbose_name=_("Can edit Access API")
    )
    can_delete_access_api = models.BooleanField(
        default=False, 
        verbose_name=_("Can delete Access API")
    )
    companies = models.ManyToManyField(
        'app_conf.Company', 
        blank=True, 
        related_name='access_isam', 
        verbose_name=_("Companies")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )

    class Meta:
        verbose_name = _("Access to ISAM")
        verbose_name_plural = _("Access to ISAM")
        unique_together = [('group',)]

    def __str__(self):
        return f"{self.group.name} - Matrix: {self.has_access_matrix}, Records: {self.has_access_records}, Config: {self.has_access_config_is}, Manage AR: {self.has_access_manage_ar}, Notification Settings: {self.has_access_notification_settings}, API: {self.has_access_api}"


class SystemAccess(models.Model):
    asset = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.CASCADE,
        related_name='access_records',
        verbose_name=_("Information System")
    )
    access_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='access_records',
        verbose_name=_("Object")
    )
    environment = models.CharField(
        max_length=20,
        choices=[
            ('production', _('Production')),
            ('test', _('Test')),
            ('development', _('Development'))
        ],
        default='test',
        verbose_name=_("Environment")
    )
    roles = models.ManyToManyField(
        'AccessRoles',
        related_name='system_accesses',
        blank=True,
        verbose_name=_("Roles")
    )
    access_right = models.ForeignKey(
        'AccessRight',
        on_delete=models.SET_NULL,
        null=True,
        related_name='system_accesses',
        verbose_name=_("Access Right")
    )
    request_users = models.ManyToManyField(
        User,
        related_name='system_access_requests',
        blank=True,
        verbose_name=_("Request Users")
    )
    request_groups = models.ManyToManyField(
        Group,
        related_name='system_access_requests',
        blank=True,
        verbose_name=_("Request Groups")
    )
    access_users = models.ManyToManyField(
        User,
        related_name='system_access_granted',
        verbose_name=_("Access Users")
    )
    access_groups = models.ManyToManyField(
        Group,
        related_name='system_access_granted',
        verbose_name=_("Access Groups")
    )
    start_date = models.DateTimeField(
        verbose_name=_("Access Start Date"),
        default=timezone.now
    )
    end_date = models.DateTimeField(
        verbose_name=_("Access End Date"),
        null=True,
        blank=True
    )
    status = models.ForeignKey(
        AccessStatus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='system_accesses',
        verbose_name=_("Status")
    )
    last_review = models.DateTimeField(
        verbose_name=_("Last Review Date"),
        null=True,
        blank=True
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='access_reviews',
        verbose_name=_("Reviewed By")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_access',
        verbose_name=_("Created By")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='modified_access',
        verbose_name=_("Modified By")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Record Active")
    )
    description = models.TextField(
        verbose_name=_("Description"),
        blank=True,
        null=True
    )
    third_parties = models.BooleanField(
        default=False,
        verbose_name=_("Third Parties Access"),
        help_text=_("Access for third parties (customers, technical support, merchants, etc.)")
    )

    class Meta:
        verbose_name = _("System Access")
        verbose_name_plural = _("System Access Records")
        ordering = ['-modified_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['access_right']),
            models.Index(fields=['last_review']),
        ]
        permissions = [
            ("can_review_access", _("Can review access records")),
            ("can_grant_access", _("Can grant system access")),
            ("can_revoke_access", _("Can revoke system access")),
        ]

    def __str__(self):
        if self.access_object:
            object_part = f"{self.asset.name} - {self.access_object.get_name()}"
            if self.roles.exists():
                role_names = [role.get_name() or role.name or '' for role in self.roles.all()]
                return f"{object_part} - {', '.join(role_names)}"
            return object_part
        elif self.access_right:
            return f"{self.asset.name} - {self.access_right.get_name()}"
        else:
            return f"{self.asset.name} - {self.environment}"
    
    def get_display_name(self):
        """Повертає детальну назву для відображення в адмінці"""
        parts = [self.asset.name]
        
        if self.access_object:
            parts.append(f"Object: {self.access_object.get_name()}")
            
            # Показуємо ролі після об'єкта
            if self.roles.exists():
                role_names = [role.get_name() or role.name or '' for role in self.roles.all()]
                parts.append(f"Roles: {', '.join(role_names)}")
        
        if self.access_right:
            parts.append(f"Right: {self.access_right.get_name()}")
        
        # Якщо немає об'єкта, але є ролі, показуємо їх окремо
        if not self.access_object and self.roles.exists():
            role_names = [role.get_name() or role.name or '' for role in self.roles.all()]
            parts.append(f"Roles: {', '.join(role_names)}")
        
        parts.append(f"({self.environment})")
        
        return " | ".join(parts)

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': _("End date cannot be earlier than start date")
            })

        if not self.request_users.exists() and not self.request_groups.exists():
            raise ValidationError(_("At least one user or group must be assigned"))

    def update_status(self):
        """
        Updates the status based on end date and last review date
        """
        today = timezone.now().date()

        try:
            # Перевіряємо термін дії
            if self.end_date and today > self.end_date:
                expired_status = AccessStatus.objects.filter(system=self.asset, name='Закінчився').first() or AccessStatus.objects.filter(name__icontains='Закінчився').first()
                self.status = expired_status
            # Перевіряємо дату останнього перегляду
            elif not self.last_review or (timezone.now() - self.last_review).days > 90:
                pending_status = AccessStatus.objects.filter(system=self.asset, name__icontains='Очікує').first() or AccessStatus.objects.filter(name__icontains='Очікує').first()
                self.status = pending_status
            self.save(update_fields=['status'])
        except AccessStatus.DoesNotExist:
            # Логуємо помилку, якщо не знайдено потрібний статус
            logger.error(f"Required status not found for access record {self.id}")
        except Exception as e:
            logger.error(f"Error updating status for access record {self.id}: {str(e)}")

    def revoke_access(self, user):
        """
        Revokes access and records who did it
        """
        try:
            revoked_status = AccessStatus.objects.filter(system=self.asset, name__icontains='Відкликано').first() or AccessStatus.objects.filter(name__icontains='Відкликано').first()
            self.status = revoked_status
            self.modified_by = user
            self.save(update_fields=['status', 'modified_by'])
            logger.info(f"Access revoked for record {self.id} by user {user}")
            return True
        except AccessStatus.DoesNotExist:
            logger.error(f"Revoked status not found for access record {self.id}")
            return False
        except Exception as e:
            logger.error(f"Error revoking access for record {self.id}: {str(e)}")
            return False

    def review_access(self, user):
        """
        Records a review of the access
        """
        try:
            self.last_review = timezone.now()
            self.reviewed_by = user
            # Якщо статус був "Очікує перевірки", змінюємо його на активний
            if self.status and (self.status.name or '').strip() and 'Очікує' in (self.status.name or ''):
                active_status = AccessStatus.objects.filter(system=self.asset, name__icontains='Активний').first() or AccessStatus.objects.filter(name__icontains='Активний').first()
                if active_status:
                    self.status = active_status
            self.save(update_fields=['last_review', 'reviewed_by', 'status'])
            logger.info(f"Access reviewed for record {self.id} by user {user}")
            return True
        except Exception as e:
            logger.error(f"Error reviewing access for record {self.id}: {str(e)}")
            return False

    @property
    def is_expired(self):
        """
        Checks if access has expired
        """
        if not self.end_date:
            return False
        return not self.is_active or timezone.now().date() > self.end_date

    @property
    def needs_review(self):
        """
        Checks if access needs review
        """
        if not self.last_review:
            return True
        return (timezone.now() - self.last_review).days > 90

    @property
    def status_color(self):
        """
        Returns the color associated with the current status
        """
        return self.status.color if self.status else '#6c757d'  # secondary color as fallback

    def get_absolute_url(self):
        """
        Returns the URL for the access record detail view
        """
        return reverse('access_detail', kwargs={'pk': self.pk})



class AccessFunctionIS(MPTTModel):
    """Access Function with name/code/description + per-country Translations (same pattern as app_risk Treatment_status)."""
    asset = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.CASCADE,
        related_name='access_functions',
        verbose_name=_("Information System")
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_("Parent Function")
    )
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Access Function Name"),
        max_length=200,
        blank=True,
        help_text=_("Function name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=200,
        blank=True,
        help_text=_("Function name in local language (use Translations inline for per-country names)")
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
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    color = models.CharField(_("Color"), max_length=7, default="#000000")
    access_rights = models.ManyToManyField(
        'AccessRight',
        related_name='functions',
        blank=True,
        verbose_name=_("Access Rights")
    )
    order = models.PositiveIntegerField(_("Order"), default=0)
    environment = models.CharField(
        max_length=20,
        choices=[
            ('production', _('Production')),
            ('test', _('Test')),
            ('development', _('Development'))
        ],
        default='test',
        verbose_name=_("Environment")
    )
    is_object_specific = models.BooleanField(
        default=False,
        verbose_name=_("Object Specific Function"),
        help_text=_("If true, this function is only available for specific objects and won't appear in default system functions")
    )
    created_for_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='custom_functions',
        verbose_name=_("Created For Object"),
        help_text=_("The object this custom function was created for")
    )
    class MPTTMeta:
        order_insertion_by = ['order']

    class Meta:
        verbose_name = _("Access Function")
        verbose_name_plural = _("Access Functions")
        ordering = ['tree_id', 'lft']
        unique_together = [('asset', 'code', 'environment')]

    def get_name_by_language(self, lang):
        """Single language: return main name (multilingual removed for app_access)."""
        return self.name or self.name_local or ''

    def get_description_by_language(self, lang):
        """Single language: return main description (multilingual removed for app_access)."""
        return self.description or ''

    def get_name(self, language=None):
        return self.name or self.name_local or ''

    def get_description(self, language=None):
        return self.description or ''

    def get_local_name(self, country):
        try:
            t = self.translations.get(country=country)
            if t.name_local:
                return t.name_local
        except AccessFunctionISTranslation.DoesNotExist:
            pass
        return self.name or self.name_local or _("Unnamed")

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except AccessFunctionISTranslation.DoesNotExist:
            return self.description or ''

    def __str__(self):
        try:
            name_display = self.get_name() or self.name or self.name_local or _("Unnamed")
            return f"{name_display} ({self.asset.name if self.asset else 'No Asset'})"
        except Exception as e:
            logger.error(f"Error in AccessFunctionIS.__str__: {str(e)}")
            return self.name or self.name_local or _("Unnamed")

    def get_children_count(self):
        return self.get_children().count()

    def get_ancestors_list(self):
        return list(self.get_ancestors(include_self=False))

    def get_descendants_list(self):
        return list(self.get_descendants(include_self=False))

    def is_root_node(self):
        return self.parent is None

    def is_leaf_node(self):
        return not self.get_children().exists()

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:80]

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '')[:80].strip()
            self.code = self._slugify_code(base) or 'fn'
        if self.code and self.asset_id:
            existing = AccessFunctionIS.objects.filter(
                asset_id=self.asset_id, environment=self.environment, code=self.code
            ).exclude(pk=self.pk)
            n = 0
            orig_code = self.code
            while existing.exists():
                n += 1
                self.code = f"{orig_code}-{n}"[:80]
                existing = AccessFunctionIS.objects.filter(
                    asset_id=self.asset_id, environment=self.environment, code=self.code
                ).exclude(pk=self.pk)
        super().save(*args, **kwargs)
        # Оновлюємо дерево тільки для цієї гілки
        if self.parent:
            self.parent.refresh_from_db()

    def delete(self, *args, **kwargs):
        """Перевизначаємо метод видалення"""
        try:
            with transaction.atomic():
                super().delete(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error deleting function: {str(e)}", exc_info=True)
            raise


class AccessFunctionISTranslation(models.Model):
    """Translations of access function for different countries.
    Can be added in Django admin (Access Function → Translations inline) or in the application create/edit modals."""
    access_function = models.ForeignKey(
        AccessFunctionIS,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Access Function")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='access_function_is_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=200, help_text=_("Function name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))

    class Meta:
        verbose_name = _("Access Function Translation")
        verbose_name_plural = _("Access Function Translations")
        unique_together = ['access_function', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.access_function.name or self.access_function.name_local} - {self.country.name}: {self.name_local}"


class ApprovingPerson(models.Model):
   asset = models.ForeignKey(
       'app_asset.InformationAsset',
       on_delete=models.CASCADE,
       related_name='approving_persons'
   )
   cabinet_user = models.ForeignKey(
       'app_cabinet.CabinetUser',
       on_delete=models.CASCADE,
       related_name='approving_assets'
   )
   order = models.PositiveIntegerField()
   color = models.CharField(_("Color"), max_length=7, default="#000000")
   environment = models.CharField(
       max_length=20,
       choices=[
           ('production', _('Production')),
           ('test', _('Test')),
           ('development', _('Development'))
       ],
       default='test',
       verbose_name=_("Environment")
   )
   created_at = models.DateTimeField(auto_now_add=True)
   modified_at = models.DateTimeField(auto_now=True)

   class Meta:
       ordering = ['asset', 'order']
       verbose_name = _("Approving Person")
       verbose_name_plural = _("Approving Persons")
       constraints = [
           models.UniqueConstraint(
               fields=['asset', 'cabinet_user', 'order', 'environment'],
               name='unique_asset_user_order_environment'
           )
       ]

   def clean(self):
       existing_approvers = ApprovingPerson.objects.filter(
           asset=self.asset,
           order=self.order
       ).exclude(id=self.id)

       if existing_approvers.exists():
           raise ValidationError({
               'order': _("This order number is already used for this asset")
           })

       existing_same_user = ApprovingPerson.objects.filter(
           asset=self.asset,
           cabinet_user=self.cabinet_user
       ).exclude(id=self.id)

       if existing_same_user.exists():
           raise ValidationError({
               'cabinet_user': _("This user is already an approver for this asset")
           })



class AccessApprover(models.Model):
    MAX_APPROVAL_LEVELS = 10  # Можна змінити на потрібне значення
    
    APPROVING_STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('cancelled', _('Cancelled')),
    ]
    
    access = models.ForeignKey('SystemAccess', on_delete=models.CASCADE, related_name='approvers')
    cabinet_user = models.ForeignKey('app_cabinet.CabinetUser', on_delete=models.CASCADE)
    order = models.IntegerField(default=1)
    
    # Поля для approving status
    current_status = models.CharField(
        max_length=20,
        choices=APPROVING_STATUS_CHOICES,
        default='pending',
        verbose_name=_("Approving Status")
    )
    status_comment = models.TextField(
        blank=True,
        verbose_name=_("Status Comment")
    )
    status_changed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Status Changed At")
    )
    status_changed_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Status Changed By")
    )

    class Meta:
        ordering = ['order']
        unique_together = ['access', 'cabinet_user']

    def __str__(self):
        return f"{self.cabinet_user} - Level {self.order}"
    
    @property
    def status(self):
        """Повертає поточний статус approver'а"""
        return self.current_status
    
    def can_approve(self):
        """Перевіряє чи може цей approver затверджувати"""
        # Перевіряємо чи всі approvers попередніх рівнів затвердили
        if self.order == 1:
            return True  # Перший рівень завжди може затверджувати
        
        # Для вищих рівнів перевіряємо попередні рівні
        previous_levels = AccessApprover.objects.filter(
            access=self.access,
            order__lt=self.order
        )
        
        for prev_approver in previous_levels:
            if prev_approver.current_status != 'approved':
                return False  # Якщо хтось з попередніх рівнів не затвердив
        
        return True
    
    def set_status(self, status, user, comment=None):
        """Встановлює статус approver'а"""
        from django.utils import timezone
        
        if status not in ['pending', 'approved', 'rejected', 'cancelled']:
            raise ValueError("Invalid status")
        
        if status in ['approved', 'rejected'] and not self.can_approve():
            raise ValueError("Cannot approve: previous levels not completed")
        
        # Зберігаємо попередній статус для історії
        old_status = self.current_status
        
        # Оновлюємо статус
        self.current_status = status
        self.status_comment = comment or ''
        self.status_changed_at = timezone.now()
        self.status_changed_by = user
        self.save()
        
        # Створюємо запис в історії
        ApproverStatusHistory.objects.create(
            approver=self,
            old_status=old_status,
            new_status=status,
            comment=comment or '',
            changed_by=user
        )
        
        # Якщо approver відхилив - автоматично завершуємо весь процес
        if status == 'rejected':
            self._reject_all_pending_approvers(user, comment)
    
    def _reject_all_pending_approvers(self, user, comment):
        """Автоматично ставить статус 'cancelled' всім іншим approvers після відхилення"""
        from django.utils import timezone
        
        # Знаходимо всіх інших approvers цього access record
        other_approvers = AccessApprover.objects.filter(
            access=self.access
        ).exclude(id=self.id)
        
        for approver in other_approvers:
            if approver.current_status == 'pending':
                # Оновлюємо статус що процес було зупинено
                approver.current_status = 'cancelled'
                approver.status_comment = f"Approval process stopped due to rejection by {self.cabinet_user.user.get_full_name()}"
                approver.status_changed_at = timezone.now()
                approver.status_changed_by = user
                approver.save()
                
                # Створюємо запис в історії
                ApproverStatusHistory.objects.create(
                    approver=approver,
                    old_status='pending',
                    new_status='cancelled',
                    comment=approver.status_comment,
                    changed_by=user
                )
    
    def get_status_history(self):
        """Повертає історію змін статусу цього approver'а"""
        return self.status_history.all().order_by('-changed_at')


class ApproverStatusHistory(models.Model):
    """
    Model to store the history of approver status changes
    """
    approver = models.ForeignKey(
        AccessApprover,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name=_("Approver")
    )
    old_status = models.CharField(
        max_length=20,
        choices=AccessApprover.APPROVING_STATUS_CHOICES,
        verbose_name=_("Old Status")
    )
    new_status = models.CharField(
        max_length=20,
        choices=AccessApprover.APPROVING_STATUS_CHOICES,
        verbose_name=_("New Status")
    )
    comment = models.TextField(
        blank=True,
        verbose_name=_("Comment")
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Changed At")
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("Changed By")
    )

    class Meta:
        verbose_name = _("Approver Status History")
        verbose_name_plural = _("Approver Status History")
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.approver} - {self.old_status} -> {self.new_status}"


class AccessRequest(models.Model):
    ENVIRONMENT_CHOICES = [
        ('production', _('Production')),
        ('test', _('Test')),
        ('development', _('Development'))
    ]
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('cancelled', _('Cancelled')),
    ]
    
    REQUEST_TYPE_CHOICES = [
        ('grant', _('Grant Access')),
        ('revoke', _('Revoke Access')),
    ]

    request_type = models.CharField(
        max_length=20,
        choices=REQUEST_TYPE_CHOICES,
        default='grant',
        verbose_name=_("Request Type")
    )
    company = models.ForeignKey(
        'app_conf.Company',
        on_delete=models.CASCADE,
        verbose_name=_("Company")
    )
    system = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.CASCADE,
        verbose_name=_("Information System")
    )
    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default='test',
        verbose_name=_("Environment")
    )
    requested_for = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='access_requests_for',
        verbose_name=_("Requested For")
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='access_requests_by',
        verbose_name=_("Requested By")
    )
    # Deprecated: use access_records instead. Data migration required if legacy data exists.
    access_records = models.ManyToManyField(
        'SystemAccess',
        related_name='access_requests',
        verbose_name=_('Access Records'),
        blank=True
    )
    start_date = models.DateTimeField(
        verbose_name=_("Start Date")
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("End Date")
    )
    justification = models.TextField(
        verbose_name=_("Justification")
    )
    requirements = models.TextField(
        blank=True,
        verbose_name=_("Additional Requirements")
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )
    admin_comment = models.TextField(
        verbose_name=_("Admin Comment"),
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Request Status")
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Cancelled At")
    )
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_requests',
        verbose_name=_("Cancelled By")
    )
    cancellation_reason = models.TextField(
        blank=True,
        verbose_name=_("Cancellation Reason")
    )
    
    # Administrative status fields (after approval)
    ADMIN_STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('granted', _('Access Granted')),
        ('denied', _('Access Denied')),
        ('in_progress', _('In Progress')),
    ]
    
    admin_status = models.CharField(
        max_length=20,
        choices=ADMIN_STATUS_CHOICES,
        default='pending',
        verbose_name=_("Administrative Status")
    )
    admin_status_comment = models.TextField(
        blank=True,
        verbose_name=_("Administrative Status Comment")
    )
    admin_status_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Admin Status Changed At")
    )
    admin_status_changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_status_requests_changed',
        verbose_name=_("Admin Status Changed By")
    )
    
    # Third party fields
    third_party_first_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Third Party First Name")
    )
    third_party_last_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Third Party Last Name")
    )
    third_party_email = models.EmailField(
        blank=True,
        verbose_name=_("Third Party Email")
    )
    third_party_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Third Party Phone")
    )
    third_party_organization = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Third Party Organization")
    )
    third_party_description = models.TextField(
        blank=True,
        verbose_name=_("Third Party Description")
    )
    
    # Fields for multiple third party users
    third_party_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Third Party Count"),
        help_text=_("Number of third party users")
    )
    third_party_users_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Third Party Users Data"),
        help_text=_("JSON data containing all third party users information")
    )
    
    # Link to Third Party Users model
    third_party_users = models.ManyToManyField(
        'ThirdPartyUser',
        blank=True,
        related_name='access_requests',
        verbose_name=_("Third Party Users"),
        help_text=_("Third party users associated with this access request")
    )
    
    # Поле для зберігання конкретних Grant Access Record ID, які скасовуються
    revoked_grant_access_record_ids = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Revoked Grant Access Record IDs"),
        help_text=_("List of specific Grant Access Record IDs that are being revoked (format: [\"70.194.1\", \"70.194.2\"])")
    )
    
    # Fields for multiple cabinet users
    requested_for_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Requested For Count"),
        help_text=_("Number of cabinet users requested for")
    )
    requested_for_users_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Requested For Users Data"),
        help_text=_("JSON data containing all cabinet users information for whom access is requested")
    )
    requested_access_record_roles = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Requested Access Record Roles"),
        help_text=_("Selected Object Role per access record when submitting grant request: [{\"access_record_id\": id, \"role_id\": id}, ...]")
    )

    class Meta:
        verbose_name = _("Access Request")
        verbose_name_plural = _("Access Requests")
        ordering = ['-created_at']

    def __str__(self):
        return f"Access Request #{self.id} - {self.requested_for}"

    def clean(self):
        """Валідація моделі"""
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': _("End date cannot be earlier than start date")
            })

    def get_absolute_url(self):
        """Повертає URL для перегляду деталей запиту"""
        return reverse('get_request_details', kwargs={'request_id': self.id})
    
    def has_first_approval(self):
        """Чи є хоча б одне погодження від Approving Person."""
        return self.request_approvers.filter(current_status='approved').exists()

    def can_be_edited(self, user=None):
        """Чи може заявник редагувати grant-заявку до першого погодження."""
        if self.request_type != 'grant' or self.status != 'pending':
            return False
        if user and user != self.requested_by:
            return False
        if self.has_first_approval():
            return False
        return True

    def can_be_cancelled(self, user=None):
        """Перевіряє, чи може бути скасована заявка"""
        # Заявка може бути скасована тільки якщо вона у статусі 'pending'
        if self.status != 'pending':
            return False
            
        # Заявка може бути скасована тільки заявником
        if user and user != self.requested_by:
            return False
            
        # Перевіряємо, чи всі approvers ще не встановили статус 'approved'
        all_approved = self.request_approvers.filter(current_status='approved').count() == self.request_approvers.count()
        
        return not all_approved
    
    def cancel_request(self, user, reason=""):
        """Скасовує заявку"""
        if not self.can_be_cancelled(user):
            raise ValidationError(_("Request cannot be cancelled"))
            
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.cancelled_by = user
        self.cancellation_reason = reason
        self.save()
        
        # Встановлюємо статус 'cancelled' для всіх approvers
        self.request_approvers.filter(current_status='pending').update(
            current_status='cancelled',
            status_changed_at=timezone.now(),
            status_changed_by=user,
            status_comment=f"Request cancelled by requester: {reason}"
        )
    
    @property
    def is_period_expired(self):
        """Перевіряє, чи закінчився період доступу"""
        if not self.end_date:
            return False
        return timezone.now() > self.end_date
    
    @property
    def can_be_approved(self):
        """Перевіряє, чи може бути погоджена заявка (період не закінчився)"""
        return not self.is_period_expired
    
    @property
    def is_cancelled(self):
        """Перевіряє, чи скасована заявка"""
        return self.status == 'cancelled'
    
    @property
    def is_fully_approved(self):
        """Перевіряє, чи всі approvers дали згоду"""
        return (self.request_approvers.count() > 0 and 
                self.request_approvers.filter(current_status='approved').count() == self.request_approvers.count())

    def should_notify_administrators(self, notification_type='request_created', status_change_context=None):
        """
        Administrators are notified only after all Approving Persons have approved.
        If the request has no approvers, administrators are notified on the first event.
        """
        if not self.request_approvers.exists():
            return True

        ctx = status_change_context or {}
        if notification_type == 'request_created':
            return False
        if notification_type == 'status_changed':
            if ctx.get('status_type') == 'admin':
                return True
            return self.is_fully_approved
        return False

    def get_notifiable_request_approvers(self, event='request_created', status_change_context=None):
        """
        Approvers who should receive email notifications, respecting approval level order.

        event: 'request_created' | 'status_changed'
        status_change_context: optional dict with status_type, new_status, changed_approver_order,
            changed_approver_email
        """
        approvers = list(
            self.request_approvers.select_related('cabinet_user', 'cabinet_user__user').order_by('order', 'id')
        )
        if not approvers:
            return []

        ctx = status_change_context or {}

        if event == 'request_created':
            return [
                approver for approver in approvers
                if approver.current_status == 'pending' and approver.can_approve()
            ]

        if event != 'status_changed':
            return approvers

        status_type = ctx.get('status_type', 'approver')
        if status_type == 'admin':
            return [
                approver for approver in approvers
                if approver.current_status not in ('cancelled',) and approver.cabinet_user.user.email
            ]

        new_status = ctx.get('new_status', '')
        if new_status == 'rejected':
            return []

        if new_status != 'approved':
            return []

        changed_order = ctx.get('changed_approver_order')
        exclude_email = (ctx.get('changed_approver_email') or '').strip().lower()
        result = []
        for approver in approvers:
            if approver.current_status != 'pending' or not approver.can_approve():
                continue
            email = (approver.cabinet_user.user.email or '').strip()
            if not email:
                continue
            if exclude_email and email.lower() == exclude_email:
                continue
            if changed_order is not None and approver.order < changed_order:
                continue
            result.append(approver)
        return result
    
    def update_request_status(self):
        """Оновлює статус заявки на основі статусів approvers"""
        if self.status == 'cancelled':
            return  # Не оновлюємо статус скасованих заявок
            
        # Якщо є хоча б один rejected approver - заявка відхилена
        if self.request_approvers.filter(current_status='rejected').exists():
            self.status = 'rejected'
        # Якщо всі approvers approved - заявка схвалена
        elif self.is_fully_approved:
            self.status = 'approved'
        else:
            self.status = 'pending'
        
        self.save()

class AccessJustificationTemplate(models.Model):
    company = models.ForeignKey(
        "app_conf.Company",
        on_delete=models.CASCADE,
        related_name="access_justification_templates",
        verbose_name=_("Company"),
        null=True,
        blank=True,
    )
    name = models.CharField(_("Template Name"), max_length=255)
    content = models.TextField(_("Template Text"))
    is_active = models.BooleanField(_("Active"), default=True)
    sort_order = models.PositiveIntegerField(_("Sort Order"), default=0)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Access Justification Template")
        verbose_name_plural = _("Access Justification Templates")
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.get_name()

    def get_name(self):
        """Get localized template name based on current language."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.name_local:
                    return translation.name_local
            except AccessJustificationTemplateTranslation.DoesNotExist:
                pass
        return self.name

    def get_content(self):
        """Get localized template text based on current language."""
        country = get_country_for_current_language()
        if country:
            try:
                translation = self.translations.get(country=country)
                if translation.content:
                    return translation.content
            except AccessJustificationTemplateTranslation.DoesNotExist:
                pass
        return self.content


class AccessJustificationTemplateTranslation(models.Model):
    template = models.ForeignKey(
        AccessJustificationTemplate,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Template"),
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="access_justification_template_translations",
        verbose_name=_("Country"),
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=255,
        blank=True,
        help_text=_("Template name in country's language"),
    )
    content = models.TextField(
        _("Template Text"),
        blank=True,
        help_text=_("Template text in country's language"),
    )

    class Meta:
        verbose_name = _("Access Justification Template Translation")
        verbose_name_plural = _("Access Justification Template Translations")
        unique_together = ["template", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.template.name} - {self.country.name}"


class AccessRequestAttachment(models.Model):
    """
    Model for storing file attachments for access requests
    """
    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Access Request")
    )
    file = models.FileField(
        upload_to='access_requests/attachments/%Y/%m/%d/',
        verbose_name=_("File")
    )
    original_filename = models.CharField(
        max_length=255,
        verbose_name=_("Original Filename")
    )
    file_size = models.PositiveIntegerField(
        verbose_name=_("File Size (bytes)")
    )
    content_type = models.CharField(
        max_length=100,
        verbose_name=_("Content Type")
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Uploaded At")
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_attachments',
        verbose_name=_("Uploaded By")
    )

    class Meta:
        verbose_name = _("Access Request Attachment")
        verbose_name_plural = _("Access Request Attachments")
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} - {self.access_request}"

    def get_file_icon_class(self):
        """Get Bootstrap icon class based on file type"""
        icon_map = {
            'application/pdf': 'bi-file-earmark-pdf text-danger',
            'application/msword': 'bi-file-earmark-word text-primary',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'bi-file-earmark-word text-primary',
            'text/plain': 'bi-file-earmark-text text-secondary',
            'image/jpeg': 'bi-file-earmark-image text-info',
            'image/jpg': 'bi-file-earmark-image text-info',
            'image/png': 'bi-file-earmark-image text-info',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'bi-file-earmark-excel text-success',
            'application/vnd.ms-excel': 'bi-file-earmark-excel text-success'
        }
        return icon_map.get(self.content_type, 'bi-file-earmark text-secondary')

    def get_file_size_display(self):
        """Get human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class AccessRequestApprover(models.Model):
    """
    Model for storing approvers specific to each access request.
    This allows individual approver status per request instead of sharing status across all requests using the same access record.
    """
    APPROVING_STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('cancelled', _('Cancelled')),
    ]
    
    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name='request_approvers',
        verbose_name=_("Access Request")
    )
    # Reference to the original approver from the access record
    access_approver = models.ForeignKey(
        AccessApprover,
        on_delete=models.CASCADE,
        verbose_name=_("Access Approver")
    )
    # Copy of approver details for this specific request
    cabinet_user = models.ForeignKey(
        'app_cabinet.CabinetUser',
        on_delete=models.CASCADE,
        verbose_name=_("Cabinet User")
    )
    order = models.IntegerField(
        default=1,
        verbose_name=_("Order")
    )
    
    # Status fields specific to this request
    current_status = models.CharField(
        max_length=20,
        choices=APPROVING_STATUS_CHOICES,
        default='pending',
        verbose_name=_("Approving Status")
    )
    status_comment = models.TextField(
        blank=True,
        verbose_name=_("Status Comment")
    )
    status_changed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("Status Changed At")
    )
    status_changed_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='changed_request_approver_statuses',
        verbose_name=_("Status Changed By")
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )

    class Meta:
        ordering = ['order']
        unique_together = ['access_request', 'cabinet_user']
        verbose_name = _("Access Request Approver")
        verbose_name_plural = _("Access Request Approvers")

    def __str__(self):
        return f"{self.cabinet_user} - Level {self.order} (Request {self.access_request.id})"
    
    @property
    def status(self):
        """Повертає поточний статус approver'а"""
        return self.current_status
    
    def can_approve(self):
        """Перевіряє чи може цей approver затверджувати для цього конкретного запиту"""
        # Перевіряємо чи всі approvers попередніх рівнів затвердили для цього запиту
        if self.order == 1:
            return True  # Перший рівень завжди може затверджувати
        
        # Для вищих рівнів перевіряємо попередні рівні в цьому ж запиті
        previous_levels = AccessRequestApprover.objects.filter(
            access_request=self.access_request,
            order__lt=self.order
        )
        
        for prev_approver in previous_levels:
            if prev_approver.current_status != 'approved':
                return False  # Якщо хтось з попередніх рівнів не затвердив
        
        return True
    
    def set_status(self, status, user, comment=None):
        """Встановлює статус approver'а для цього конкретного запиту"""
        from django.utils import timezone
        
        if status not in ['pending', 'approved', 'rejected', 'cancelled']:
            raise ValueError("Invalid status")
        
        # Перевіряємо, чи заявка не скасована
        if self.access_request.is_cancelled:
            raise ValueError(_("Cannot change approver status for cancelled request"))
        
        if status in ['approved', 'rejected'] and not self.can_approve():
            raise ValueError("Cannot approve: previous levels not completed")
        
        # Зберігаємо попередній статус для історії
        old_status = self.current_status
        
        # Оновлюємо статус
        self.current_status = status
        self.status_comment = comment or ''
        self.status_changed_at = timezone.now()
        self.status_changed_by = user
        self.save()
        
        # Створюємо запис в історії
        AccessRequestApproverStatusHistory.objects.create(
            request_approver=self,
            access_request=self.access_request,
            old_status=old_status,
            new_status=status,
            comment=comment or '',
            changed_by=user,
            approver_cabinet_user=self.cabinet_user,
            approver_name=self.cabinet_user.user.get_full_name() if self.cabinet_user and self.cabinet_user.user else '',
            approver_email=self.cabinet_user.user.email if self.cabinet_user and self.cabinet_user.user else '',
            order_at_change=self.order
        )
        
        # Якщо approver відхилив - автоматично завершуємо весь процес для цього запиту
        if status == 'rejected':
            self._reject_all_pending_approvers(user, comment)
        
        # Оновлюємо статус заявки
        self.access_request.update_request_status()
    
    def _reject_all_pending_approvers(self, user, comment):
        """Автоматично ставить статус 'cancelled' всім іншим approvers цього запиту після відхилення"""
        from django.utils import timezone
        
        # Знаходимо всіх інших approvers цього запиту
        other_approvers = AccessRequestApprover.objects.filter(
            access_request=self.access_request
        ).exclude(id=self.id)
        
        for approver in other_approvers:
            if approver.current_status == 'pending':
                # Оновлюємо статус що процес було зупинено
                approver.current_status = 'cancelled'
                approver.status_comment = f"Approval process stopped due to rejection by {self.cabinet_user.user.get_full_name()}"
                approver.status_changed_at = timezone.now()
                approver.status_changed_by = user
                approver.save()
                
                # Створюємо запис в історії
                AccessRequestApproverStatusHistory.objects.create(
                    request_approver=approver,
                    access_request=approver.access_request,
                    old_status='pending',
                    new_status='cancelled',
                    comment=approver.status_comment,
                    changed_by=user,
                    approver_cabinet_user=approver.cabinet_user,
                    approver_name=approver.cabinet_user.user.get_full_name() if approver.cabinet_user and approver.cabinet_user.user else '',
                    approver_email=approver.cabinet_user.user.email if approver.cabinet_user and approver.cabinet_user.user else '',
                    order_at_change=approver.order
                )
    
    def get_status_history(self):
        """Повертає історію змін статусу цього approver'а для цього запиту"""
        return self.status_history.all().order_by('-changed_at')


class AccessRequestApproverStatusHistory(models.Model):
    """
    Model to store the history of request approver status changes
    """
    request_approver = models.ForeignKey(
        AccessRequestApprover,
        on_delete=models.SET_NULL,
        null=True,
        related_name='status_history',
        verbose_name=_("Request Approver")
    )
    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name='approver_status_history',
        verbose_name=_("Access Request"),
        null=True,
        blank=True
    )
    old_status = models.CharField(
        max_length=20,
        choices=AccessRequestApprover.APPROVING_STATUS_CHOICES,
        verbose_name=_("Old Status")
    )
    new_status = models.CharField(
        max_length=20,
        choices=AccessRequestApprover.APPROVING_STATUS_CHOICES,
        verbose_name=_("New Status")
    )
    comment = models.TextField(
        blank=True,
        verbose_name=_("Comment")
    )
    # Snapshot of approver at the time of change
    approver_cabinet_user = models.ForeignKey(
        'app_cabinet.CabinetUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Approver Cabinet User")
    )
    approver_name = models.CharField(max_length=255, blank=True)
    approver_email = models.EmailField(blank=True)
    order_at_change = models.IntegerField(default=1)
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Changed At")
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("Changed By")
    )

    class Meta:
        verbose_name = _("Access Request Approver Status History")
        verbose_name_plural = _("Access Request Approver Status History")
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.request_approver} - {self.old_status} -> {self.new_status}"


class ApiUser(models.Model):
    """
    Model to store users fetched from external API
    """
    user_id = models.IntegerField(
        verbose_name=_("User ID"),
        unique=True
    )
    email = models.EmailField(
        verbose_name=_("Email")
    )
    hash = models.CharField(
        max_length=255,
        verbose_name=_("Hash"),
        unique=True
    )
    first_name = models.CharField(
        max_length=100,
        verbose_name=_("First Name"),
        null=True,
        blank=True
    )
    last_name = models.CharField(
        max_length=100,
        verbose_name=_("Last Name"),
        null=True,
        blank=True
    )
    phone = models.CharField(
        max_length=20,
        verbose_name=_("Phone"),
        null=True,
        blank=True
    )
    last_login = models.DateTimeField(
        verbose_name=_("Last Login"),
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    sync = models.ForeignKey(
        'ApiSyncStatus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_("Sync ID")
    )
    api_credential = models.ForeignKey(
        'ApiCredential',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_users',
        verbose_name=_("Source API credential"),
        help_text=_("Credential used for the last successful sync of this user; used to drop users removed from that API."),
    )
    
    class Meta:
        verbose_name = _("API User")
        verbose_name_plural = _("API Users")
        ordering = ['-updated_at']
        
    def __str__(self):
        return f"{self.email} ({self.user_id})"

class ApiUserRole(models.Model):
    """
    Model to store roles fetched from the API
    """
    role_id = models.IntegerField(
        verbose_name=_("Role ID"),
        unique=True
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("Role Name")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    sync = models.ForeignKey(
        'ApiSyncStatus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roles',
        verbose_name=_("Sync ID")
    )
    
    class Meta:
        verbose_name = _("API User Role")
        verbose_name_plural = _("API User Roles")
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.role_id})"

class ApiUserMerchant(models.Model):
    """
    Model to store merchants/groups from the API
    """
    name = models.CharField(
        max_length=255,
        verbose_name=_("Merchant Name")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    sync = models.ForeignKey(
        'ApiSyncStatus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merchants',
        verbose_name=_("Sync ID")
    )
    
    class Meta:
        verbose_name = _("API User Merchant")
        verbose_name_plural = _("API User Merchants")
        ordering = ['name']
        
    def __str__(self):
        return self.name

class ApiUserRoleMapping(models.Model):
    """
    Model to store mapping between users, merchants and roles
    """
    user = models.ForeignKey(
        ApiUser,
        on_delete=models.CASCADE,
        related_name='role_mappings',
        verbose_name=_("User")
    )
    merchant = models.ForeignKey(
        ApiUserMerchant,
        on_delete=models.CASCADE,
        related_name='role_mappings',
        verbose_name=_("Merchant")
    )
    role = models.ForeignKey(
        ApiUserRole,
        on_delete=models.CASCADE,
        related_name='role_mappings',
        verbose_name=_("Role")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )
    sync = models.ForeignKey(
        'ApiSyncStatus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='role_mappings',
        verbose_name=_("Sync ID")
    )
    
    class Meta:
        verbose_name = _("API User Role Mapping")
        verbose_name_plural = _("API User Role Mappings")
        unique_together = [('user', 'merchant', 'role')]
        
    def __str__(self):
        return f"{self.user.email} - {self.merchant.name} - {self.role.name}"

class ApiUserStatus(models.Model):
    """
    Model to store user status from the API
    """
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('blocked', _('Blocked')),
        ('temporary_unavailable', _('Temporarily Unavailable')),
        ('unknown', _('Unknown'))
    ]
    
    user = models.OneToOneField(
        ApiUser,
        on_delete=models.CASCADE,
        related_name='status_info',
        verbose_name=_("User")
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='unknown',
        verbose_name=_("Status")
    )
    raw_status = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Raw Status Value")
    )
    last_checked = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Last Checked")
    )
    sync = models.ForeignKey(
        'ApiSyncStatus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_statuses',
        verbose_name=_("Sync ID")
    )
    
    class Meta:
        verbose_name = _("API User Status")
        verbose_name_plural = _("API User Statuses")
        
    def __str__(self):
        return f"{self.user.email} - {self.get_status_display()}"

class ApiUserPermissionHistory(models.Model):
    """
    Model to store permission history for API users
    """
    user = models.ForeignKey(
        ApiUser,
        on_delete=models.CASCADE,
        related_name='permission_history',
        verbose_name=_("User")
    )
    time = models.DateTimeField(
        verbose_name=_("Time")
    )
    added_permissions = models.JSONField(
        verbose_name=_("Added Permissions"),
        default=dict,
        blank=True
    )
    removed_permissions = models.JSONField(
        verbose_name=_("Removed Permissions"),
        default=dict,
        blank=True
    )
    raw_data = models.JSONField(
        verbose_name=_("Raw API Response"),
        default=dict,
        blank=True
    )
    sync = models.ForeignKey(
        'ApiSyncStatus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permission_histories',
        verbose_name=_("Sync ID")
    )
    
    class Meta:
        verbose_name = _("API User Permission History")
        verbose_name_plural = _("API User Permission History")
        ordering = ['-time']
        
    def __str__(self):
        return f"{self.user.email} - {self.time}"
    
    @property
    def has_added_permissions(self):
        """Check if there are any added permissions"""
        return bool(self.added_permissions)
    
    @property
    def has_removed_permissions(self):
        """Check if there are any removed permissions"""
        return bool(self.removed_permissions)
    
    @property
    def total_merchants_affected(self):
        """Count total merchants affected by this permission change"""
        added_merchants = set(self.added_permissions.keys()) if isinstance(self.added_permissions, dict) else set()
        removed_merchants = set(self.removed_permissions.keys()) if isinstance(self.removed_permissions, dict) else set()
        return len(added_merchants.union(removed_merchants))

class ApiSyncStatus(models.Model):
    """
    Model to track API sync progress and status
    """
    STATUS_CHOICES = [
        ('running', _('Running')),
        ('completed', _('Completed')),
        ('error', _('Error')),
        ('stopped', _('Stopped'))
    ]
    
    unique_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Sync ID"),
        help_text=_("Unique identifier for this synchronization")
    )
    is_scheduled = models.BooleanField(
        default=False,
        verbose_name=_("Is Scheduled"),
        help_text=_("Whether this sync was scheduled or manual")
    )
    credential = models.ForeignKey(
        ApiCredential,
        on_delete=models.CASCADE,
        related_name='sync_statuses',
        verbose_name=_("API Credential")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='running',
        verbose_name=_("Status")
    )
    current_step = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Current Step")
    )
    completed_steps = models.IntegerField(
        default=0,
        verbose_name=_("Completed Steps")
    )
    total_steps = models.IntegerField(
        default=0,
        verbose_name=_("Total Steps")
    )
    percent_complete = models.IntegerField(
        default=0,
        verbose_name=_("Percent Complete")
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Error Message")
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Started At")
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Completed At")
    )
    extra_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Extra Data")
    )
    
    class Meta:
        verbose_name = _("API Sync Status")
        verbose_name_plural = _("API Sync Statuses")
        ordering = ['-started_at']
        
    def __str__(self):
        return f"{self.credential.name} - {self.get_status_display()} ({self.percent_complete}%)"
        
    def update_progress(self, message, completed_steps, total_steps, extra_data=None):
        """
        Update the progress of the sync operation
        """
        self.current_step = message
        self.completed_steps = completed_steps
        self.total_steps = total_steps
        self.percent_complete = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
        
        # Store extra data if provided
        if extra_data:
            self.extra_data = extra_data
        
        self.save()

    def touch_step(self, message, completed_steps=None, total_steps=None):
        """Update step message; optionally completed/total for finer progress (no extra_data merge)."""
        self.current_step = message
        fields = ['current_step']
        if completed_steps is not None and total_steps is not None and total_steps > 0:
            self.completed_steps = completed_steps
            self.total_steps = total_steps
            self.percent_complete = int((completed_steps / total_steps) * 100)
            fields.extend(['completed_steps', 'total_steps', 'percent_complete'])
        self.save(update_fields=fields)

    def complete(self):
        """
        Mark the sync as completed
        """
        self.status = 'completed'
        self.percent_complete = 100
        self.completed_at = timezone.now()
        self.save()

    def error(self, message):
        """
        Mark the sync as errored with a message
        """
        self.status = 'error'
        self.error_message = message
        self.completed_at = timezone.now()
        self.save()

    def stop(self):
        """
        Mark the sync as stopped
        """
        self.status = 'stopped'
        self.completed_at = timezone.now()
        self.save()

class ApiUserLoginHistory(models.Model):
    """
    Model to store user login history from API
    """
    user = models.ForeignKey(ApiUser, on_delete=models.CASCADE, related_name='login_history')
    ip = models.CharField(max_length=45)  # IPv6 can be up to 45 chars
    time = models.DateTimeField()
    sync = models.ForeignKey(
        'ApiSyncStatus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_histories',
        verbose_name=_("Sync ID")
    )
    
    class Meta:
        ordering = ['-time']
        verbose_name = _('API User Login History')
        verbose_name_plural = _('API User Login Histories')

    def __str__(self):
        return f"{self.user.email} - {self.time} - {self.ip}"

class ApiUserMerchantLink(models.Model):
    """
    Model to store user merchant links
    """
    user = models.ForeignKey(
        ApiUser,
        on_delete=models.CASCADE,
        related_name='merchant_links',
        verbose_name=_("User")
    )
    merchant_name = models.CharField(
        max_length=255,
        verbose_name=_("Merchant Name")
    )
    sync = models.ForeignKey(
        'ApiSyncStatus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merchant_links',
        verbose_name=_("Sync ID")
    )
    
    class Meta:
        verbose_name = _("API User Merchant Link")
        verbose_name_plural = _("API User Merchant Links")
        ordering = ['merchant_name']
        unique_together = [('user', 'merchant_name')]

    def __str__(self):
        return f"{self.user.email} - {self.merchant_name}"

class ScheduledSync(models.Model):
    """
    Model to store scheduled API sync tasks
    """
    FREQUENCY_CHOICES = [
        ('once', _('Once')),
        ('hourly', _('Hourly')),
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('monthly', _('Monthly')),
    ]
    
    HOURLY_CYCLE_CHOICES = [
        (1, _('Every hour')),
        (2, _('Every 2 hours')),
        (3, _('Every 3 hours')),
        (4, _('Every 4 hours')),
        (6, _('Every 6 hours')),
        (8, _('Every 8 hours')),
        (12, _('Every 12 hours')),
    ]
    
    credential = models.ForeignKey(
        ApiCredential,
        on_delete=models.CASCADE,
        related_name='scheduled_syncs',
        verbose_name=_("API Credential")
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("Schedule Name")
    )
    frequency = models.CharField(
        max_length=10,
        choices=FREQUENCY_CHOICES,
        default='once',
        verbose_name=_("Frequency")
    )
    hourly_cycle = models.IntegerField(
        choices=HOURLY_CYCLE_CHOICES,
        default=1,
        verbose_name=_("Hourly Cycle"),
        help_text=_("How many hours between each sync when using hourly frequency")
    )
    scheduled_time = models.DateTimeField(
        verbose_name=_("Scheduled Time")
    )
    last_run = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Run")
    )
    next_run = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Next Run")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    periodic_task = models.OneToOneField(
        'django_celery_beat.PeriodicTask',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Periodic Task")
    )
    celery_task_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Celery Task ID")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='scheduled_syncs',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("Scheduled Sync")
        verbose_name_plural = _("Scheduled Syncs")
        ordering = ['-scheduled_time']
    
    def __str__(self):
        return f"{self.name} - {self.credential.name} ({self.get_frequency_display()})"
    
    def calculate_next_run(self):
        """Calculate the next run time based on frequency"""
        if self.frequency == 'once':
            return None
        
        if not self.scheduled_time:
            return None
            
        now = timezone.now()
        base_time = max(self.scheduled_time, now)
        
        if self.frequency == 'hourly':
            hours_to_add = self.hourly_cycle
            next_run = timezone.datetime(
                base_time.year, base_time.month, base_time.day,
                base_time.hour, self.scheduled_time.minute, self.scheduled_time.second,
                tzinfo=base_time.tzinfo
            ) + timezone.timedelta(hours=hours_to_add)
        elif self.frequency == 'daily':
            next_run = timezone.datetime(
                base_time.year, base_time.month, base_time.day,
                self.scheduled_time.hour, self.scheduled_time.minute, self.scheduled_time.second,
                tzinfo=base_time.tzinfo
            ) + timezone.timedelta(days=1)
        elif self.frequency == 'weekly':
            next_run = timezone.datetime(
                base_time.year, base_time.month, base_time.day,
                self.scheduled_time.hour, self.scheduled_time.minute, self.scheduled_time.second,
                tzinfo=base_time.tzinfo
            ) + timezone.timedelta(days=7)
        elif self.frequency == 'monthly':
            # Move to next month (this handles month boundaries correctly)
            if base_time.month == 12:
                next_month = 1
                next_year = base_time.year + 1
            else:
                next_month = base_time.month + 1
                next_year = base_time.year
                
            next_run = timezone.datetime(
                next_year, next_month, 1,  # Start with 1st day of next month
                self.scheduled_time.hour, self.scheduled_time.minute, self.scheduled_time.second,
                tzinfo=base_time.tzinfo
            )
        else:
            return None
            
        self.next_run = next_run
        self.save(update_fields=['next_run'])
        return next_run
        
    def update_or_create_task(self):
        """Create or update the periodic task for this scheduled sync"""
        from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule  # type: ignore[import-untyped]
        import json
        
        # Delete existing periodic task if it exists
        if self.periodic_task:
            try:
                self.periodic_task.delete()
            except:
                pass
            self.periodic_task = None
        
        # If this is not active or is a one-time task, don't create a periodic task
        if not self.is_active or self.frequency == 'once':
            self.save()
            return
        
        # Create appropriate schedule based on frequency
        if self.frequency == 'hourly':
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=self.hourly_cycle,
                period=IntervalSchedule.HOURS,
            )
            
            # Create the periodic task with interval schedule
            task = PeriodicTask.objects.create(
                name=f"API Sync: {self.name} ({self.credential.name})",
                task='app_access.tasks.sync_api_users_task',
                interval=schedule,
                kwargs=json.dumps({
                    'scheduled_sync_id': self.id,
                    'credential_id': self.credential.id
                }),
                enabled=True,
                description=f"Scheduled API sync for {self.credential.name} (Every {self.hourly_cycle} hours)"
            )
            
        elif self.frequency == 'daily':
            schedule, _ = CrontabSchedule.objects.get_or_create(
                minute=self.scheduled_time.minute,
                hour=self.scheduled_time.hour,
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
            )
            
            # Create the periodic task with crontab schedule
            task = PeriodicTask.objects.create(
                name=f"API Sync: {self.name} ({self.credential.name})",
                task='app_access.tasks.sync_api_users_task',
                crontab=schedule,
                kwargs=json.dumps({
                    'scheduled_sync_id': self.id,
                    'credential_id': self.credential.id
                }),
                enabled=True,
                description=f"Scheduled API sync for {self.credential.name} ({self.get_frequency_display()})"
            )
            
        elif self.frequency == 'weekly':
            schedule, _ = CrontabSchedule.objects.get_or_create(
                minute=self.scheduled_time.minute,
                hour=self.scheduled_time.hour,
                day_of_week=str(self.scheduled_time.weekday()),
                day_of_month='*',
                month_of_year='*',
            )
            
            # Create the periodic task with crontab schedule
            task = PeriodicTask.objects.create(
                name=f"API Sync: {self.name} ({self.credential.name})",
                task='app_access.tasks.sync_api_users_task',
                crontab=schedule,
                kwargs=json.dumps({
                    'scheduled_sync_id': self.id,
                    'credential_id': self.credential.id
                }),
                enabled=True,
                description=f"Scheduled API sync for {self.credential.name} ({self.get_frequency_display()})"
            )
            
        elif self.frequency == 'monthly':
            schedule, _ = CrontabSchedule.objects.get_or_create(
                minute=self.scheduled_time.minute,
                hour=self.scheduled_time.hour,
                day_of_week='*',
                day_of_month=str(self.scheduled_time.day),
                month_of_year='*',
            )
            
            # Create the periodic task with crontab schedule
            task = PeriodicTask.objects.create(
                name=f"API Sync: {self.name} ({self.credential.name})",
                task='app_access.tasks.sync_api_users_task',
                crontab=schedule,
                kwargs=json.dumps({
                    'scheduled_sync_id': self.id,
                    'credential_id': self.credential.id
                }),
                enabled=True,
                description=f"Scheduled API sync for {self.credential.name} ({self.get_frequency_display()})"
            )
            
        else:
            return
        
        # Link the task to this scheduled sync
        self.periodic_task = task
        self.save(update_fields=['periodic_task'])

class AccessObjectIS(MPTTModel):
    """Access Object with name/code/description + per-country Translations (same pattern as AccessFunctionIS)."""
    asset = models.ForeignKey(
        'app_asset.InformationAsset',
        on_delete=models.CASCADE,
        related_name='access_objects',
        verbose_name=_("Information System")
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_("Parent Object")
    )
    # Default (English) fields – for other languages use Translations inline
    name = models.CharField(
        _("Access Object Name"),
        max_length=200,
        blank=True,
        help_text=_("Object name, default: English (En). For other languages use Translations inline.")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=200,
        blank=True,
        help_text=_("Object name in local language (use Translations inline for per-country names)")
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
        help_text=_("Description, default: English (En). For other languages use Translations inline.")
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    color = models.CharField(_("Color"), max_length=7, default="#6c757d")
    order = models.PositiveIntegerField(_("Order"), default=0)
    environment = models.CharField(
        max_length=20,
        choices=[
            ('production', _('Production')),
            ('test', _('Test')),
            ('development', _('Development'))
        ],
        default='test',
        verbose_name=_("Environment")
    )
    class MPTTMeta:
        order_insertion_by = ['order']

    class Meta:
        verbose_name = _("Access Object")
        verbose_name_plural = _("Access Objects")
        ordering = ['tree_id', 'lft']
        unique_together = [('asset', 'name', 'environment')]

    def get_name_by_language(self, lang):
        """Single language: return main name (multilingual removed for app_access)."""
        return self.name or self.name_local or ''

    def get_description_by_language(self, lang):
        """Single language: return main description (multilingual removed for app_access)."""
        return self.description or ''

    def get_name(self, language=None):
        return self.name or self.name_local or ''

    def get_description(self, language=None):
        return self.description or ''

    def get_local_name(self, country):
        try:
            t = self.translations.get(country=country)
            if t.name_local:
                return t.name_local
        except AccessObjectISTranslation.DoesNotExist:
            pass
        return self.name or self.name_local or _("Unnamed")

    def get_local_description(self, country):
        try:
            t = self.translations.get(country=country)
            return t.description or self.description or ''
        except AccessObjectISTranslation.DoesNotExist:
            return self.description or ''

    def __str__(self):
        try:
            name_display = self.get_name() or self.name or self.name_local or _("Unnamed")
            return f"{name_display} ({self.asset.name if self.asset else 'No Asset'})"
        except Exception as e:
            logger.error(f"Error in AccessObjectIS.__str__: {str(e)}")
            return self.name or self.name_local or _("Unnamed")

    def get_children_count(self):
        return self.get_children().count()

    def get_ancestors_list(self):
        return list(self.get_ancestors(include_self=False))

    def get_descendants_list(self):
        return list(self.get_descendants(include_self=False))

    def is_root_node(self):
        return self.parent is None

    def is_leaf_node(self):
        return not self.get_children().exists()

    def _slugify_code(self, value):
        if not value or not str(value).strip():
            return ''
        value = re.sub(r'[^\w\s-]', '', str(value))
        return re.sub(r'[-\s]+', '-', value).strip('-').lower()[:80]

    def save(self, *args, **kwargs):
        if not self.code or not self.code.strip():
            base = (self.name or self.name_local or '')[:80].strip()
            self.code = self._slugify_code(base) or ''
        super().save(*args, **kwargs)
        # Оновлюємо дерево тільки для цієї гілки
        if self.parent:
            self.parent.refresh_from_db()

    def delete(self, *args, **kwargs):
        """Перевизначаємо метод видалення"""
        try:
            with transaction.atomic():
                super().delete(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error deleting object: {str(e)}", exc_info=True)
            raise


class AccessObjectISTranslation(models.Model):
    """Translations of access object for different countries.
    Can be added in Django admin (Access Object → Translations inline) or in the application create/edit modals."""
    access_object = models.ForeignKey(
        AccessObjectIS,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Access Object")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='access_object_is_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(_("Local Name"), max_length=200, help_text=_("Object name in country's language"))
    description = models.TextField(_("Description"), blank=True, help_text=_("Description in country's language"))

    class Meta:
        verbose_name = _("Access Object Translation")
        verbose_name_plural = _("Access Object Translations")
        unique_together = ['access_object', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.access_object.name or self.access_object.name_local} - {self.country.name}: {self.name_local}"


class ObjectRoles(models.Model):
    """
    Model for managing roles assigned to specific objects
    """
    access_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        related_name='object_roles',
        verbose_name=_("Access Object")
    )
    role = models.ForeignKey(
        'AccessRoles',
        on_delete=models.CASCADE,
        related_name='object_assignments',
        verbose_name=_("Access Role")
    )
    order = models.PositiveIntegerField(
        verbose_name=_("Order"),
        default=0
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )

    class Meta:
        ordering = ['access_object', 'order']
        verbose_name = _("Object Role")
        verbose_name_plural = _("Object Roles")
        constraints = [
            models.UniqueConstraint(
                fields=['access_object', 'role'],
                name='unique_object_role'
            )
        ]

    def __str__(self):
        return f"{self.role} - {self.access_object}"

    def clean(self):
        existing_role = ObjectRoles.objects.filter(
            access_object=self.access_object,
            role=self.role
        ).exclude(id=self.id)

        if existing_role.exists():
            raise ValidationError({
                'role': _("This role is already assigned to this object")
            })

class ObjectAccessRights(models.Model):
    """
    Model for managing access rights assigned to specific objects
    """
    access_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        related_name='object_access_rights',
        verbose_name=_("Access Object")
    )
    access_right = models.ForeignKey(
        'AccessRight',
        on_delete=models.CASCADE,
        related_name='object_assignments',
        verbose_name=_("Access Right")
    )
    order = models.PositiveIntegerField(
        verbose_name=_("Order"),
        default=0
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )

    class Meta:
        ordering = ['access_object', 'order']
        verbose_name = _("Object Access Right")
        verbose_name_plural = _("Object Access Rights")
        constraints = [
            models.UniqueConstraint(
                fields=['access_object', 'access_right'],
                name='unique_object_access_right'
            )
        ]

    def __str__(self):
        return f"{self.access_right} - {self.access_object}"

    def clean(self):
        existing_right = ObjectAccessRights.objects.filter(
            access_object=self.access_object,
            access_right=self.access_right
        ).exclude(id=self.id)

        if existing_right.exists():
            raise ValidationError({
                'access_right': _("This access right is already assigned to this object")
            })



class AccessObjectFunction(models.Model):
    """
    Model for managing functions assigned to specific objects
    """
    access_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        related_name='object_functions',
        verbose_name=_("Access Object")
    )
    function = models.ForeignKey(
        'AccessFunctionIS',
        on_delete=models.CASCADE,
        related_name='object_assignments',
        verbose_name=_("Access Function")
    )
    order = models.PositiveIntegerField(
        verbose_name=_("Order"),
        default=0
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )

    class Meta:
        ordering = ['access_object', 'order']
        verbose_name = _("Object Function")
        verbose_name_plural = _("Object Functions")
        constraints = [
            models.UniqueConstraint(
                fields=['access_object', 'function'],
                name='unique_object_function'
            )
        ]

    def __str__(self):
        return f"{self.function} - {self.access_object}"

    def clean(self):
        # Перевірка, чи функція вже призначена об'єкту
        existing_function = AccessObjectFunction.objects.filter(
            access_object=self.access_object,
            function=self.function
        ).exclude(id=self.id)

        if existing_function.exists():
            raise ValidationError({
                'function': _("This function is already assigned to this object")
            })

        # Валідація, що функція належить тій же системі, що й об'єкт
        if self.function.asset != self.access_object.asset:
            raise ValidationError({
                'function': _("Function must belong to the same system as the object")
            })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def assign_function_with_children(cls, access_object, function, user=None, max_depth=3):
        """
        Присвоювання функції об'єкту разом з усіма дочірніми функціями
        """
        assigned_functions = []
        
        try:
            with transaction.atomic():
                # Присвоюємо батьківську функцію
                obj_func, created = cls.objects.get_or_create(
                    access_object=access_object,
                    function=function,
                    defaults={'order': 0}
                )
                if created:
                    assigned_functions.append(function)
                
                # Безпечний ітеративний підхід для дочірніх функцій
                # Використовуємо простий фільтр замість MPTT методів
                functions_to_process = [function]
                processed_ids = {function.id}
                current_depth = 0
                
                while functions_to_process and current_depth < max_depth:
                    next_level_functions = []
                    
                    for parent_func in functions_to_process:
                        # Отримуємо прямих дітей (не всіх нащадків)
                        children = AccessFunctionIS.objects.filter(
                            parent=parent_func,
                            asset=access_object.asset
                        ).exclude(id__in=processed_ids)
                        
                        for child in children:
                            # Перевіряємо, чи не створили циклічне посилання
                            if child.id not in processed_ids:
                                child_obj_func, child_created = cls.objects.get_or_create(
                                    access_object=access_object,
                                    function=child,
                                    defaults={'order': 0}
                                )
                                if child_created:
                                    assigned_functions.append(child)
                                    next_level_functions.append(child)
                                    processed_ids.add(child.id)
                    
                    functions_to_process = next_level_functions
                    current_depth += 1
                
                logger.info(
                    f"Functions assigned to object {access_object.id}: "
                    f"{[f.id for f in assigned_functions]} by user {user}"
                )
                
                return assigned_functions
                
        except Exception as e:
            logger.error(f"Error assigning functions to object: {str(e)}")
            raise

    @classmethod
    def remove_function_with_children(cls, access_object, function, user=None, max_depth=3):
        """
        Видалення функції об'єкта разом з усіма дочірніми функціями
        """
        removed_functions = []
        
        try:
            with transaction.atomic():
                # Безпечний ітеративний підхід для дочірніх функцій
                # Спочатку збираємо всі функції для видалення
                functions_to_remove = [function]
                processed_ids = {function.id}
                current_depth = 0
                
                while functions_to_remove and current_depth < max_depth:
                    next_level_functions = []
                    
                    for parent_func in functions_to_remove:
                        # Отримуємо прямих дітей
                        children = AccessFunctionIS.objects.filter(
                            parent=parent_func,
                            asset=access_object.asset
                        ).exclude(id__in=processed_ids)
                        
                        for child in children:
                            if child.id not in processed_ids:
                                next_level_functions.append(child)
                                processed_ids.add(child.id)
                    
                    functions_to_remove.extend(next_level_functions)
                    current_depth += 1
                
                # Видаляємо дочірні функції спочатку (в зворотному порядку)
                for func_to_remove in reversed(functions_to_remove):
                    assignments = cls.objects.filter(
                        access_object=access_object,
                        function=func_to_remove
                    )
                    if assignments.exists():
                        removed_functions.append(func_to_remove)
                        assignments.delete()
                
                logger.info(
                    f"Functions removed from object {access_object.id}: "
                    f"{[f.id for f in removed_functions]} by user {user}"
                )
                
                return removed_functions
                
        except Exception as e:
            logger.error(f"Error removing function and children for object {access_object.id}: {e}")
            return None, None


class ObjectRoleFunctions(models.Model):
    """
    Model for managing function assignments to roles for specific objects.
    This allows object-specific role-function relationships without affecting global role definitions.
    """
    object_role = models.ForeignKey(
        'ObjectRoles',
        on_delete=models.CASCADE,
        related_name='role_functions',
        verbose_name=_("Object Role")
    )
    function = models.ForeignKey(
        'AccessFunctionIS',
        on_delete=models.CASCADE,
        related_name='object_role_assignments',
        verbose_name=_("Access Function")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )

    class Meta:
        ordering = ['object_role', 'function']
        verbose_name = _("Object Role Function")
        verbose_name_plural = _("Object Role Functions")
        constraints = [
            models.UniqueConstraint(
                fields=['object_role', 'function'],
                name='unique_object_role_function'
            )
        ]

    def __str__(self):
        return f"{self.object_role} - {self.function}"

    def clean(self):
        # Перевірка, чи функція призначена об'єкту
        if not AccessObjectFunction.objects.filter(
            access_object=self.object_role.access_object,
            function=self.function,
            is_active=True
        ).exists():
            raise ValidationError(
                _("Function must be assigned to the object before being assigned to a role")
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class RoleFunctionRightMapping(models.Model):
    """
    Model for storing system-level (role, function, right) mappings.
    Allows the same function in different roles to have different access rights.
    """
    role = models.ForeignKey(
        'AccessRoles',
        on_delete=models.CASCADE,
        related_name='function_right_mappings',
        verbose_name=_("Access Role")
    )
    function = models.ForeignKey(
        'AccessFunctionIS',
        on_delete=models.CASCADE,
        related_name='role_right_mappings',
        verbose_name=_("Function")
    )
    access_right = models.ForeignKey(
        'AccessRight',
        on_delete=models.CASCADE,
        related_name='role_function_mappings',
        verbose_name=_("Access Right")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )

    class Meta:
        ordering = ['role', 'function', 'access_right']
        verbose_name = _("Role Function Right Mapping")
        verbose_name_plural = _("Role Function Right Mappings")
        constraints = [
            models.UniqueConstraint(
                fields=['role', 'function', 'access_right'],
                name='unique_role_function_right'
            )
        ]

    def __str__(self):
        return f"{self.role} - {self.function} - {self.access_right}"


class ObjectRoleFunctionRightMapping(models.Model):
    """
    Per-role object matrix: (object, role, function, right).
    Allows the same function in different roles to have different rights on the object.
    """
    access_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        related_name='role_function_right_mappings',
        verbose_name=_("Access Object")
    )
    role = models.ForeignKey(
        'AccessRoles',
        on_delete=models.CASCADE,
        related_name='object_function_right_mappings',
        verbose_name=_("Access Role")
    )
    function = models.ForeignKey(
        'AccessFunctionIS',
        on_delete=models.CASCADE,
        related_name='object_role_right_mappings',
        verbose_name=_("Function")
    )
    access_right = models.ForeignKey(
        'AccessRight',
        on_delete=models.CASCADE,
        related_name='object_role_function_mappings',
        verbose_name=_("Access Right")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        ordering = ['access_object', 'role', 'function', 'access_right']
        verbose_name = _("Object Role Function Right Mapping")
        verbose_name_plural = _("Object Role Function Right Mappings")
        constraints = [
            models.UniqueConstraint(
                fields=['access_object', 'role', 'function', 'access_right'],
                name='unique_object_role_function_right'
            )
        ]

    def __str__(self):
        return f"{self.access_object} - {self.role} - {self.function} - {self.access_right}"


class ObjectFunctionRightMapping(models.Model):
    """
    Model for storing object-specific function-right mappings (legacy, no role).
    Each object can have its own matrix configuration independent of other objects.
    """
    access_object = models.ForeignKey(
        'AccessObjectIS',
        on_delete=models.CASCADE,
        related_name='function_right_mappings',
        verbose_name=_("Access Object")
    )
    function = models.ForeignKey(
        'AccessFunctionIS',
        on_delete=models.CASCADE,
        related_name='object_right_mappings',
        verbose_name=_("Function")
    )
    access_right = models.ForeignKey(
        'AccessRight',
        on_delete=models.CASCADE,
        related_name='object_function_mappings',
        verbose_name=_("Access Right")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_object_mappings',
        verbose_name=_("Created By")
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_object_mappings',
        verbose_name=_("Modified By")
    )

    class Meta:
        ordering = ['access_object', 'function', 'access_right']
        verbose_name = _("Object Function Right Mapping")
        verbose_name_plural = _("Object Function Right Mappings")
        constraints = [
            models.UniqueConstraint(
                fields=['access_object', 'function', 'access_right'],
                name='unique_object_function_right'
            )
        ]

    def __str__(self):
        return f"{self.access_object} - {self.function} - {self.access_right}"

    def clean(self):
        # Перевірка, чи функція призначена об'єкту
        if not AccessObjectFunction.objects.filter(
            access_object=self.access_object,
            function=self.function,
            is_active=True
        ).exists():
            raise ValidationError({
                'function': _("Function must be assigned to the object")
            })

        # Перевірка, чи право доступу призначене об'єкту
        if not ObjectAccessRights.objects.filter(
            access_object=self.access_object,
            access_right=self.access_right,
            is_active=True
        ).exists():
            raise ValidationError({
                'access_right': _("Access right must be assigned to the object")
            })

        # Перевірка, чи функція та право належать тій же системі, що й об'єкт
        if self.function.asset != self.access_object.asset:
            raise ValidationError({
                'function': _("Function must belong to the same system as the object")
            })

        if self.access_right.system != self.access_object.asset:
            raise ValidationError({
                'access_right': _("Access right must belong to the same system as the object")
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class AccessRequestAdminStatusHistory(models.Model):
    """
    Model to store the history of admin status changes for access requests
    """
    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name='admin_status_history',
        verbose_name=_("Access Request")
    )
    old_status = models.CharField(
        max_length=20,
        choices=AccessRequest.ADMIN_STATUS_CHOICES,
        verbose_name=_("Old Status")
    )
    new_status = models.CharField(
        max_length=20,
        choices=AccessRequest.ADMIN_STATUS_CHOICES,
        verbose_name=_("New Status")
    )
    comment = models.TextField(
        blank=True,
        verbose_name=_("Comment")
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Changed At")
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_status_changes_history',
        verbose_name=_("Changed By")
    )

    class Meta:
        verbose_name = _("Access Request Admin Status History")
        verbose_name_plural = _("Access Request Admin Status History")
        ordering = ['-changed_at']

    def __str__(self):
        return f"Request {self.access_request.id}: {self.old_status} → {self.new_status} at {self.changed_at}"


class EmailNotificationHistory(models.Model):
    """
    Model to store the history of email notifications sent by the system
    """
    NOTIFICATION_TYPES = [
        ('access_request_created', _('Access Request Created')),
        ('access_request_status_changed', _('Access Request Status Changed')),
        ('admin_status_changed', _('Admin Status Changed')),
        ('access_granted', _('Access Granted')),
        ('access_denied', _('Access Denied')),
        ('request_approved', _('Request Approved')),
        ('request_rejected', _('Request Rejected')),
        ('access_status_changed', _('Access Status Changed')),
    ]
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('sent', _('Sent')),
        ('failed', _('Failed')),
        ('retrying', _('Retrying')),
    ]
    
    # Notification details
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        verbose_name=_("Notification Type")
    )
    subject = models.CharField(
        max_length=500,
        verbose_name=_("Email Subject")
    )
    
    # Recipients
    recipients = models.JSONField(
        verbose_name=_("Recipients"),
        help_text=_("List of email addresses that received this notification")
    )
    recipients_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Recipients Count")
    )
    
    # Related objects
    access_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='email_notifications',
        verbose_name=_("Access Request")
    )
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_notifications',
        verbose_name=_("Triggered By")
    )
    
    # Sending details
    mail_account = models.ForeignKey(
        'app_conf.MailAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Mail Account Used")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Sent At")
    )
    
    # Error handling
    error_message = models.TextField(
        blank=True,
        verbose_name=_("Error Message")
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Retry Count")
    )
    max_retries = models.PositiveIntegerField(
        default=3,
        verbose_name=_("Max Retries")
    )
    
    # Additional data
    template_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Template Data"),
        help_text=_("Additional data used for email template rendering")
    )
    
    class Meta:
        verbose_name = _("Email Notification History")
        verbose_name_plural = _("Email Notification History")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification_type']),
            models.Index(fields=['status']),
            models.Index(fields=['access_request']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.access_request_id if self.access_request else 'N/A'} - {self.status}"
    
    def mark_as_sent(self):
        """Mark notification as successfully sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_failed(self, error_message):
        """Mark notification as failed with error message"""
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count'])
    
    def can_retry(self):
        """Check if notification can be retried"""
        return self.status == 'failed' and self.retry_count < self.max_retries
    
    def mark_for_retry(self):
        """Mark notification for retry"""
        if self.can_retry():
            self.status = 'retrying'
            self.save(update_fields=['status'])
            return True
        return False
    
    @classmethod
    def create_notification(cls, notification_type, subject, recipients, access_request=None, 
                          triggered_by=None, mail_account=None, template_data=None):
        """
        Create a new email notification history record
        
        Args:
            notification_type (str): Type of notification
            subject (str): Email subject
            recipients (list): List of recipient email addresses
            access_request (AccessRequest, optional): Related access request
            triggered_by (User, optional): User who triggered the notification
            mail_account (MailAccount, optional): Mail account used for sending
            template_data (dict, optional): Additional template data
        
        Returns:
            EmailNotificationHistory: Created notification record
        """
        return cls.objects.create(
            notification_type=notification_type,
            subject=subject,
            recipients=recipients if isinstance(recipients, list) else [recipients],
            recipients_count=len(recipients) if isinstance(recipients, list) else 1,
            access_request=access_request,
            triggered_by=triggered_by,
            mail_account=mail_account,
            template_data=template_data or {}
        )
    
    @property
    def is_successful(self):
        """Check if notification was sent successfully"""
        return self.status == 'sent'
    
    @property
    def is_pending(self):
        """Check if notification is pending"""
        return self.status in ['pending', 'retrying']
    
    @property
    def recipients_display(self):
        """Get formatted string of recipients"""
        if not self.recipients:
            return ""
        return ", ".join(self.recipients[:3]) + ("..." if len(self.recipients) > 3 else "")

class EmailNotificationConfig(models.Model):
    """
    Model for configuring email notifications for access requests
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('grant', _('Grant Access Request')),
        ('revoke', _('Revoke Access Request')),
    ]

    # Basic configuration
    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name=_("Configuration Name"),
        help_text=_("Name for this notification configuration")
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        default='grant',
        verbose_name=_("Notification Type"),
        help_text=_("Applies to grant or revoke access requests (matches request type)"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Enable Email Notifications"),
        help_text=_("Enable or disable email notifications")
    )
    
    # Notification triggers
    send_on_request_created = models.BooleanField(
        default=True,
        verbose_name=_("Send on Request Created"),
        help_text=_("Send notification when a new access request is created")
    )
    send_on_status_changed = models.BooleanField(
        default=True,
        verbose_name=_("Send on Status Changed"),
        help_text=_("Send notification when request status changes")
    )
    send_on_admin_status_changed = models.BooleanField(
        default=True,
        verbose_name=_("Send on Admin Status Changed"),
        help_text=_("Send notification when admin status changes")
    )
    
    # Recipient configuration
    notify_owners = models.BooleanField(
        default=True,
        verbose_name=_("Notify Owners"),
        help_text=_("Send notifications to system owners")
    )
    notify_administrators = models.BooleanField(
        default=True,
        verbose_name=_("Notify Administrators"),
        help_text=_("Send notifications to system administrators")
    )
    notify_requested_for = models.BooleanField(
        default=False,
        verbose_name=_("Notify Requested For"),
        help_text=_("Send notifications to the user for whom access is requested")
    )
    notify_requested_by = models.BooleanField(
        default=True,
        verbose_name=_("Notify Requested By"),
        help_text=_("Send notifications to the user who created the request")
    )
    notify_approving_persons = models.BooleanField(
        default=True,
        verbose_name=_("Notify Approving Persons"),
        help_text=_("Send notifications to approving persons")
    )
    
    # Third Party Configuration
    notify_third_party = models.BooleanField(
        default=False,
        verbose_name=_("Notify Third Party"),
        help_text=_("Send notifications to third party email if provided")
    )
    include_third_party_info_in_emails = models.BooleanField(
        default=True,
        verbose_name=_("Include Third Party Info in Emails"),
        help_text=_("Include third party information in email templates")
    )
    
    # Additional recipients
    additional_recipients = models.TextField(
        blank=True,
        verbose_name=_("Additional Recipients"),
        help_text=_("Additional email addresses separated by commas")
    )
    
    # Email template configuration
    use_custom_templates = models.BooleanField(
        default=False,
        verbose_name=_("Use Custom Templates"),
        help_text=_("Use custom email templates instead of default ones")
    )
    
    # Request created template
    request_created_subject_template = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Request Created Subject Template"),
        help_text=_("Custom subject template for request created notifications. Use variables like {company_name}, {system_name}, etc.")
    )
    request_created_html_template = models.TextField(
        blank=True,
        verbose_name=_("Request Created HTML Template"),
        help_text=_("Custom HTML template for request created notifications")
    )
    request_created_text_template = models.TextField(
        blank=True,
        verbose_name=_("Request Created Text Template"),
        help_text=_("Custom text template for request created notifications")
    )
    
    # Status changed template
    status_changed_subject_template = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Status Changed Subject Template"),
        help_text=_("Custom subject template for status changed notifications")
    )
    status_changed_html_template = models.TextField(
        blank=True,
        verbose_name=_("Status Changed HTML Template"),
        help_text=_("Custom HTML template for status changed notifications")
    )
    status_changed_text_template = models.TextField(
        blank=True,
        verbose_name=_("Status Changed Text Template"),
        help_text=_("Custom text template for status changed notifications")
    )
    
    # Mail server configuration
    mail_server = models.ForeignKey(
        'app_conf.MailServer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Mail Server"),
        help_text=_("Specific mail server to use for sending notifications. If not set, default will be used.")
    )
    
    # Mail account configuration
    mail_account = models.ForeignKey(
        'app_conf.MailAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Mail Account"),
        help_text=_("Specific mail account to use for sending notifications. If not set, default will be used.")
    )
    
    # System/Company filters
    companies = models.ManyToManyField(
        'app_conf.Company',
        blank=True,
        verbose_name=_("Companies"),
        help_text=_("Limit this configuration to specific companies. If empty, applies to all companies.")
    )
    systems = models.ManyToManyField(
        'app_asset.InformationAsset',
        blank=True,
        verbose_name=_("Systems"),
        help_text=_("Limit this configuration to specific systems. If empty, applies to all systems.")
    )
    
    # Priority and ordering
    priority = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Priority"),
        help_text=_("Configuration priority. Lower numbers have higher priority.")
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_email_configs',
        verbose_name=_("Created By")
    )
    modified_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified At")
    )
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_email_configs',
        verbose_name=_("Modified By")
    )
    
    class Meta:
        verbose_name = _("Email Notification Configuration")
        verbose_name_plural = _("Email Notification Configurations")
        ordering = ['priority', 'name']
        
    def __str__(self):
        status = _("Active") if self.is_active else _("Inactive")
        return f"{self.name} ({status})"
    
    def clean(self):
        """Валідація моделі"""
        if self.use_custom_templates:
            if self.send_on_request_created and not self.request_created_subject_template:
                raise ValidationError({
                    'request_created_subject_template': _('Subject template is required when using custom templates for request created notifications')
                })
            if self.send_on_status_changed and not self.status_changed_subject_template:
                raise ValidationError({
                    'status_changed_subject_template': _('Subject template is required when using custom templates for status changed notifications')
                })
    
    def get_additional_recipients_list(self):
        """Повертає список додаткових отримувачів"""
        if not self.additional_recipients:
            return []
        
        emails = []
        for email in self.additional_recipients.split(','):
            email = email.strip()
            if email:
                emails.append(email)
        return emails
    
    def applies_to_request(self, access_request):
        """Перевіряє, чи застосовується конфігурація до цього запиту"""
        if not self.is_active:
            return False
        
        # Перевіряємо компанію
        if self.companies.exists() and access_request.company not in self.companies.all():
            return False
        
        # Перевіряємо систему
        if self.systems.exists() and access_request.system not in self.systems.all():
            return False

        request_type = getattr(access_request, 'request_type', None)
        if request_type and self.notification_type != request_type:
            return False

        return True

    def get_recipients_for_request(self, access_request, notification_type='request_created', status_change_context=None):
        """Повертає список отримувачів для запиту"""
        recipients = []
        
        # Власники системи
        if self.notify_owners:
            for owner in access_request.system.owners.all():
                if owner.cabinet_user.user.email:
                    recipients.append({
                        'email': owner.cabinet_user.user.email,
                        'name': owner.cabinet_user.user.get_full_name() or owner.cabinet_user.user.username,
                        'role': 'Owner'
                    })
        
        # Адміністратори системи (після повного погодження Approving Persons)
        if self.notify_administrators and access_request.should_notify_administrators(
            notification_type, status_change_context
        ):
            for admin in access_request.system.administrators.all():
                if admin.cabinet_user.user.email:
                    recipients.append({
                        'email': admin.cabinet_user.user.email,
                        'name': admin.cabinet_user.user.get_full_name() or admin.cabinet_user.user.username,
                        'role': 'Administrator'
                    })
        
        # Користувач, для якого запитується доступ
        if self.notify_requested_for and access_request.requested_for.email:
            recipients.append({
                'email': access_request.requested_for.email,
                'name': access_request.requested_for.get_full_name() or access_request.requested_for.username,
                'role': 'Requested For'
            })
        
        # Користувач, який створив запит
        if self.notify_requested_by and access_request.requested_by.email:
            recipients.append({
                'email': access_request.requested_by.email,
                'name': access_request.requested_by.get_full_name() or access_request.requested_by.username,
                'role': 'Requested By'
            })
        
        # Особи, що затверджують (з урахуванням послідовності рівнів)
        if self.notify_approving_persons:
            event = 'request_created' if notification_type == 'request_created' else 'status_changed'
            ctx = dict(status_change_context or {})
            if notification_type == 'status_changed' and 'status_type' not in ctx:
                ctx.setdefault('status_type', 'approver')
            for approver in access_request.get_notifiable_request_approvers(event, ctx):
                email = approver.cabinet_user.user.email
                if email:
                    recipients.append({
                        'email': email,
                        'name': approver.cabinet_user.user.get_full_name() or approver.cabinet_user.user.username,
                        'role': f'Approver (Level {approver.order})'
                    })
        
        # Третя сторона (підтримка множинних користувачів)
        if self.notify_third_party:
            # Перевіряємо, чи є множинні третіх сторін
            if access_request.third_party_users_data and isinstance(access_request.third_party_users_data, list):
                # Додаємо всіх третіх сторін з JSON даних
                for user in access_request.third_party_users_data:
                    email = user.get('email')
                    if email:
                        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                        if not name:
                            name = email
                        recipients.append({
                            'email': email,
                            'name': name,
                            'role': 'Third Party'
                        })
            elif access_request.third_party_email:
                # Використовуємо одну третю сторону з основних полів
                third_party_name = f"{access_request.third_party_first_name} {access_request.third_party_last_name}".strip()
                if not third_party_name:
                    third_party_name = access_request.third_party_email
                recipients.append({
                    'email': access_request.third_party_email,
                    'name': third_party_name,
                    'role': 'Third Party'
                })
        
        # Додаткові отримувачі
        for email in self.get_additional_recipients_list():
            recipients.append({
                'email': email,
                'name': email,
                'role': 'Additional Recipient'
            })
        
        # Видаляємо дублікати
        unique_recipients = []
        seen_emails = set()
        for recipient in recipients:
            if recipient['email'] not in seen_emails:
                unique_recipients.append(recipient)
                seen_emails.add(recipient['email'])
        
        return unique_recipients
    
    @classmethod
    def get_active_config_for_request(cls, access_request):
        """Повертає активну конфігурацію для запиту з найвищим пріоритетом"""
        configs = cls.objects.filter(is_active=True).order_by('priority')
        
        for config in configs:
            if config.applies_to_request(access_request):
                return config
        
        return None


class SystemAccessStatusHistory(models.Model):
    """
    Model to store the history of status changes for SystemAccess records
    """
    access_record = models.ForeignKey(
        SystemAccess,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name=_("Access Record")
    )
    old_status = models.ForeignKey(
        AccessStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='old_status_history',
        verbose_name=_("Old Status")
    )
    new_status = models.ForeignKey(
        AccessStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='new_status_history',
        verbose_name=_("New Status")
    )
    change_reason = models.TextField(
        blank=True,
        verbose_name=_("Change Reason")
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Changed At")
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='access_record_status_changes',
        verbose_name=_("Changed By")
    )
    revoke_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_access_records',
        verbose_name=_("Revoke Request"),
        help_text=_("The revoke request that caused this status change (if applicable)")
    )

    class Meta:
        verbose_name = _("Access Record Status History")
        verbose_name_plural = _("Access Record Status History")
        ordering = ['-changed_at']

    def __str__(self):
        old_name = (self.old_status.name or str(self.old_status)) if self.old_status else 'None'
        new_name = (self.new_status.name or str(self.new_status)) if self.new_status else 'None'
        return f"Access Record {self.access_record.id}: {old_name} → {new_name} at {self.changed_at}"


class AccessRequestSequence(models.Model):
    """
    Model to store the sequence of Grant and Revoke requests for each Access Record
    Each Access Record in a Grant Request gets a unique ID and can be linked to a Revoke Request
    """
    # Унікальний ID для кожного Access Record в Grant Request
    sequence_id = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Sequence ID"),
        help_text=_("Unique identifier for this access record sequence")
    )
    
    # Зв'язок з Access Request (Grant)
    grant_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.CASCADE,
        related_name='access_sequences',
        verbose_name=_("Grant Request"),
        help_text=_("The grant request that created this access record")
    )
    
    # Зв'язок з Access Record
    access_record = models.ForeignKey(
        SystemAccess,
        on_delete=models.CASCADE,
        related_name='access_sequences',
        verbose_name=_("Access Record"),
        help_text=_("The access record in this sequence")
    )
    
    # Зв'язок з Revoke Request (якщо є)
    revoke_request = models.ForeignKey(
        AccessRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_sequences',
        verbose_name=_("Revoke Request"),
        help_text=_("The revoke request that cancelled this access record")
    )
    
    # Статус послідовності
    SEQUENCE_STATUS_CHOICES = [
        ('active', _('Active')),
        ('revoked', _('Revoked')),
        ('expired', _('Expired')),
    ]
    
    sequence_status = models.CharField(
        max_length=20,
        choices=SEQUENCE_STATUS_CHOICES,
        default='active',
        verbose_name=_("Sequence Status")
    )
    
    # Додаткові поля
    order_number = models.PositiveIntegerField(
        verbose_name=_("Order Number"),
        help_text=_("Order number within the grant request (1, 2, 3, etc.)")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Revoked At")
    )
    
    class Meta:
        verbose_name = _("Access Request Sequence")
        verbose_name_plural = _("Access Request Sequences")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sequence_id']),
            models.Index(fields=['grant_request']),
            models.Index(fields=['revoke_request']),
            models.Index(fields=['sequence_status']),
        ]

    def __str__(self):
        return f"Sequence {self.sequence_id}: Grant #{self.grant_request.id} → Revoke #{self.revoke_request.id if self.revoke_request else 'None'}"

    def save(self, *args, **kwargs):
        # Автоматично встановлюємо порядковий номер якщо не вказано
        if not self.order_number:
            # Знаходимо максимальний порядковий номер для цього grant request
            max_order = AccessRequestSequence.objects.filter(
                grant_request=self.grant_request
            ).aggregate(models.Max('order_number'))['order_number__max'] or 0
            self.order_number = max_order + 1
        
        # Автоматично генеруємо sequence_id якщо не вказано
        if not self.sequence_id:
            self.sequence_id = self.generate_sequence_id()
        super().save(*args, **kwargs)

    def generate_sequence_id(self):
        """Генерує унікальний ID для послідовності у форматі AccessRecordID.GrantRequestID.OrderNumber"""
        # Використовуємо встановлений порядковий номер
        return f"{self.access_record.id}.{self.grant_request.id}.{self.order_number}"

    def revoke_sequence(self, revoke_request):
        """Відмічає послідовність як скасовану"""
        self.revoke_request = revoke_request
        self.sequence_status = 'revoked'
        self.revoked_at = timezone.now()
        self.save()

    @property
    def is_revoked(self):
        """Перевіряє чи послідовність скасована"""
        return self.sequence_status == 'revoked'

    @property
    def is_active(self):
        """Перевіряє чи послідовність активна"""
        return self.sequence_status == 'active'


from tinymce.models import HTMLField


class AccessRecordsGuide(models.Model):
    """Base Guide for Access Records page. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Access Records Guide")
        verbose_name_plural = _("Access Records Guides")

    def __str__(self):
        return gettext("Access Records Guide")


class AccessRecordsGuideTranslation(models.Model):
    """Per-country (language) translations of the Access Records Guide."""
    guide = models.ForeignKey(
        AccessRecordsGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="access_records_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Access Records Guide Translation")
        verbose_name_plural = _("Access Records Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class AccessConfigIsGuide(models.Model):
    """Base Guide for Access Config IS page. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Access Config IS Guide")
        verbose_name_plural = _("Access Config IS Guides")

    def __str__(self):
        return gettext("Access Config IS Guide")


class AccessConfigIsGuideTranslation(models.Model):
    """Per-country (language) translations of the Access Config IS Guide."""
    guide = models.ForeignKey(
        AccessConfigIsGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="access_config_is_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Access Config IS Guide Translation")
        verbose_name_plural = _("Access Config IS Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class AccessMatrixGuide(models.Model):
    """Base Guide for Access Matrix page. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Access Matrix Guide")
        verbose_name_plural = _("Access Matrix Guides")

    def __str__(self):
        return gettext("Access Matrix Guide")


class AccessMatrixGuideTranslation(models.Model):
    """Per-country (language) translations of the Access Matrix Guide."""
    guide = models.ForeignKey(
        AccessMatrixGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="access_matrix_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Access Matrix Guide Translation")
        verbose_name_plural = _("Access Matrix Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class UserAccessRequestGuide(models.Model):
    """Base Guide for User Access Request page. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("User Access Request Guide")
        verbose_name_plural = _("User Access Request Guides")

    def __str__(self):
        return gettext("User Access Request Guide")


class UserAccessRequestGuideTranslation(models.Model):
    """Per-country (language) translations of the User Access Request Guide."""
    guide = models.ForeignKey(
        UserAccessRequestGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="user_access_request_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("User Access Request Guide Translation")
        verbose_name_plural = _("User Access Request Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class ManageAccessRequestsGuide(models.Model):
    """Base Guide for Manage Access Requests page. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Manage Access Requests Guide")
        verbose_name_plural = _("Manage Access Requests Guides")

    def __str__(self):
        return gettext("Manage Access Requests Guide")


class ManageAccessRequestsGuideTranslation(models.Model):
    """Per-country (language) translations of the Manage Access Requests Guide."""
    guide = models.ForeignKey(
        ManageAccessRequestsGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="manage_access_requests_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Manage Access Requests Guide Translation")
        verbose_name_plural = _("Manage Access Requests Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class AccessNotificationGuide(models.Model):
    """Base Guide for Access Notification page. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Access Notification Guide")
        verbose_name_plural = _("Access Notification Guides")

    def __str__(self):
        return gettext("Access Notification Guide")


class AccessNotificationGuideTranslation(models.Model):
    """Per-country (language) translations of the Access Notification Guide."""
    guide = models.ForeignKey(
        AccessNotificationGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="access_notification_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Access Notification Guide Translation")
        verbose_name_plural = _("Access Notification Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"
