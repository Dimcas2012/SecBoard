#  SecBoard\SecBoard\app_suib\admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db import models
from django.urls import reverse
from .models import CriticalityLevel, AssetGroup, AssetAdministrator, AssetOwner, \
    InformationAsset, AccessAssets, AssetType, AssetGuide, AssetGuideTranslation, AssetGroupTranslation, AssetTypeTranslation, CriticalityLevelTranslation, \
    SoftwareRegister, SoftwareRegisterFile, SoftwareStatus, SoftwareStatusTranslation, \
    SoftwareLicenseType, SoftwareLicenseTypeTranslation, SoftwareGuide, SoftwareGuideTranslation, \
    ExternalMediaRegister, ExternalMediaRegisterFile, ExternalMediaStatus, ExternalMediaStatusTranslation, \
    ExternalMediaGuide, ExternalMediaGuideTranslation
from django.utils.translation import gettext_lazy as _
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField


@admin.register(AccessAssets)
class AccessAssetsAdmin(admin.ModelAdmin):
    list_display = ['group', 'has_access', 'can_edit', 'manage_adm_own', 'manage_types', 'can_view_software_register', 'can_edit_software_register', 'can_view_external_media_register', 'can_edit_external_media_register', 'display_companies']
    list_editable = ['has_access', 'can_edit', 'manage_adm_own', 'manage_types', 'can_view_software_register', 'can_edit_software_register', 'can_view_external_media_register', 'can_edit_external_media_register']
    list_filter = ['has_access', 'can_edit', 'manage_adm_own', 'manage_types', 'can_view_software_register', 'can_edit_software_register', 'can_view_external_media_register', 'can_edit_external_media_register', 'companies']
    search_fields = ['group__name', 'companies__name']
    filter_horizontal = ['companies']

    def display_companies(self, obj):
        return ", ".join([company.name for company in obj.companies.all()])
    display_companies.short_description = _("Companies")


class SoftwareRegisterFileInline(admin.TabularInline):
    model = SoftwareRegisterFile
    extra = 0
    fields = ('file', 'label', 'file_hash', 'uploaded_at')
    readonly_fields = ('file_hash', 'uploaded_at')
    verbose_name = _("Attached File")
    verbose_name_plural = _("Attached Files")


@admin.register(SoftwareRegister)
class SoftwareRegisterAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'company', 'manufacturer', 'version_pattern', 'is_active', 'display_order', 'updated_date')
    list_filter = ('status', 'is_active', 'company')
    search_fields = ('name', 'description', 'version_pattern', 'manufacturer', 'notes')
    list_editable = ('is_active', 'display_order')
    ordering = ('display_order', 'name')
    list_per_page = 50
    list_select_related = ('status', 'company')
    inlines = [SoftwareRegisterFileInline]

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'status', 'description', 'notes'),
        }),
        (_('Vendor'), {
            'fields': ('manufacturer', 'url'),
        }),
        (_('Scope'), {
            'fields': ('company', 'version_pattern'),
            'description': _('Leave company empty for organization-wide rule.'),
        }),
        (_('License'), {
            'fields': ('license_type', 'license_quantity', 'license_valid_until'),
        }),
        (_('Display'), {
            'fields': ('display_order', 'is_active'),
        }),
    )
    readonly_fields = ('created_date', 'updated_date')


class ActiveCountryInlineMixinForExternalMedia:
    """Mixin to limit country choices (used by External Media inlines)."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# --- External Media Register admin ---
class ExternalMediaRegisterFileInline(admin.TabularInline):
    model = ExternalMediaRegisterFile
    extra = 0
    fields = ('file', 'label', 'file_hash', 'uploaded_at')
    readonly_fields = ('file_hash', 'uploaded_at')


@admin.register(ExternalMediaRegister)
class ExternalMediaRegisterAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'status', 'company', 'group', 'asset_type',
        'confidentiality', 'integrity', 'availability',
        'serial_number', 'is_active', 'display_order', 'updated_date'
    )
    list_filter = ('status', 'is_active', 'company')
    search_fields = ('name', 'description', 'serial_number', 'notes')
    list_editable = ('is_active', 'display_order')
    ordering = ('display_order', 'name')
    inlines = [ExternalMediaRegisterFileInline]
    readonly_fields = ('created_date', 'updated_date')


class ExternalMediaStatusTranslationInline(ActiveCountryInlineMixinForExternalMedia, admin.TabularInline):
    model = ExternalMediaStatusTranslation
    extra = 1
    fields = ('country', 'name_local')
    autocomplete_fields = ['country']


@admin.register(ExternalMediaStatus)
class ExternalMediaStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'color', 'is_active', 'display_order')
    list_filter = ('is_active',)
    ordering = ('display_order', 'name')
    inlines = [ExternalMediaStatusTranslationInline]


class ActiveCountryInlineMixin:
    """Mixin to limit country choices to active records."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SoftwareStatusTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = SoftwareStatusTranslation
    extra = 1
    fields = ('country', 'name_local')
    autocomplete_fields = ['country']


@admin.register(SoftwareStatus)
class SoftwareStatusAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'code', 'translations_count', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    inlines = [SoftwareStatusTranslationInline]
    exclude = ('name_local',)
    readonly_fields = ('created_date', 'updated_date')

    def color_badge(self, obj):
        return format_html(
            '<span style="display:inline-block;width:20px;height:20px;background-color:{};border:1px solid #ddd;border-radius:3px;"></span> {}',
            obj.color, obj.color
        )
    color_badge.short_description = _('Color')

    def translations_count(self, obj):
        n = obj.translations.count()
        return format_html('<span style="background:#10b981;color:white;padding:2px 6px;border-radius:3px;">{}</span>', n) if n else '-'
    translations_count.short_description = _('Translations')


class SoftwareLicenseTypeTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = SoftwareLicenseTypeTranslation
    extra = 1
    fields = ('country', 'name_local')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(SoftwareLicenseType)
class SoftwareLicenseTypeAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'code', 'translations_count', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    inlines = [SoftwareLicenseTypeTranslationInline]
    exclude = ('name_local',)
    readonly_fields = ('created_date', 'updated_date')

    def color_badge(self, obj):
        return format_html(
            '<span style="display:inline-block;width:20px;height:20px;background-color:{};border:1px solid #ddd;border-radius:3px;"></span> {}',
            obj.color, obj.color
        )
    color_badge.short_description = _('Color')

    def translations_count(self, obj):
        n = obj.translations.count()
        return format_html('<span style="background:#10b981;color:white;padding:2px 6px;border-radius:3px;">{}</span>', n) if n else '-'
    translations_count.short_description = _('Translations')


class AssetGroupTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = AssetGroupTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']
    
    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


class AssetTypeTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = AssetTypeTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']
    
    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


class AssetTypeInline(admin.TabularInline):
    model = AssetType
    extra = 1
    fields = ('name', 'code', 'color', 'display_order', 'is_active')


@admin.register(AssetGroup)
class AssetGroupAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'code', 'abbreviation', 'translations_count', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'abbreviation', 'description')
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    inlines = [AssetGroupTranslationInline, AssetTypeInline]
    exclude = ('name_local',)
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code', 'abbreviation'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Display'), {
            'fields': ('color', 'display_order')
        }),
        (_('Description'), {
            'fields': ('description',),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('is_active', 'show_in_software_register', 'show_in_external_media_register')
        }),
    )
    
    readonly_fields = ('created_date', 'updated_date')
    
    def color_badge(self, obj):
        """Display color badge"""
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; '
            'background-color: {}; border: 1px solid #ddd; border-radius: 3px;"></span> {}',
            obj.color,
            obj.color
        )
    color_badge.short_description = _('Color')
    
    def translations_count(self, obj):
        """Count of translations"""
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')

@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'code', 'group', 'translations_count', 'is_active', 'display_order')
    list_filter = ('is_active', 'group')
    search_fields = ('name', 'code', 'description', 'group__name', 'group__code')
    list_editable = ('display_order', 'is_active')
    ordering = ('group__display_order', 'group__name', 'display_order', 'name')
    inlines = [AssetTypeTranslationInline]
    exclude = ('name_local',)
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code', 'group'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Display'), {
            'fields': ('color', 'display_order')
        }),
        (_('Description'), {
            'fields': ('description',),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ('created_date', 'updated_date')
    
    def color_badge(self, obj):
        """Display color badge"""
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; '
            'background-color: {}; border: 1px solid #ddd; border-radius: 3px;"></span> {}',
            obj.color,
            obj.color
        )
    color_badge.short_description = _('Color')
    
    def translations_count(self, obj):
        """Count of translations"""
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')



class InformationAssetAdmin(admin.ModelAdmin):
    list_display = ('asset_id', 'name', 'company', 'is_active', 'access_manage', 'get_criticality_display')
    search_fields = ('asset_id', 'name')
    list_filter = ('company', 'group', 'asset_type', 'is_active', 'access_manage')
    list_editable = ('is_active', 'access_manage')

    def get_criticality_display(self, obj):
        criticality = obj.get_criticality()
        return format_html('<span style="color: {};">{} / {}</span>',
                           criticality['color'], criticality['name'], criticality['cost'])
    get_criticality_display.short_description = _("Criticality")


class CriticalityLevelTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = CriticalityLevelTranslation
    extra = 1
    fields = ('country', 'name_local', 'description_confid', 'description_integ', 'description_avail')
    autocomplete_fields = ['country']
    
    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(CriticalityLevel)
class CriticalityLevelAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'company', 'code', 'cost', 'translations_count', 'is_active', 'display_order')
    list_filter = ('is_active', 'cost', 'company')
    search_fields = ('name', 'code', 'company__name')
    list_editable = ('display_order', 'is_active', 'cost')
    ordering = ('display_order', 'cost', 'name')
    inlines = [CriticalityLevelTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'company', 'code', 'cost', 'description_confid', 'description_integ', 'description_avail'),
            'description': _('Default: English (En). For other languages and CIA descriptions use the Translations inline below.'),
        }),
        (_('Display'), {
            'fields': ('color', 'display_order')
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ('created_date', 'updated_date')
    
    def color_badge(self, obj):
        """Display color badge"""
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; '
            'background-color: {}; border: 1px solid #ddd; border-radius: 3px;"></span> {}',
            obj.color,
            obj.color
        )
    color_badge.short_description = _('Color')
    
    def translations_count(self, obj):
        """Count of translations"""
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


admin.site.register(AssetAdministrator)
admin.site.register(AssetOwner)
admin.site.register(InformationAsset, InformationAssetAdmin)


class AssetGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AssetGuideTranslationInline(AssetGuideTranslationInlineMixin, admin.StackedInline):
    model = AssetGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/asset_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(AssetGuide)
class AssetGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [AssetGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_asset/assetguide/change_form.html'

    def has_base(self, obj):
        return bool(obj and obj.base_content)
    has_base.short_description = _('Has base content')

    def translations_count(self, obj):
        if not obj or not obj.pk:
            return '-'
        n = obj.translations.count()
        return format_html('<span style="background:#10b981;color:white;padding:2px 6px;border-radius:3px;">{}</span>', n) if n else '-'
    translations_count.short_description = _('Translations')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['asset_guide_translate_url'] = reverse('asset_guide_translate')
        except Exception:
            extra_context['asset_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['asset_guide_translate_url'] = reverse('asset_guide_translate')
        except Exception:
            extra_context['asset_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class SoftwareGuideTranslationInlineMixin:
    """Add AI translate button to each inline translation."""
    pass


class SoftwareGuideTranslationInline(SoftwareGuideTranslationInlineMixin, admin.StackedInline):
    model = SoftwareGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/software_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(SoftwareGuide)
class SoftwareGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [SoftwareGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_asset/softwareguide/change_form.html'

    def has_base(self, obj):
        return bool(obj and obj.base_content)
    has_base.short_description = _('Has base content')

    def translations_count(self, obj):
        if not obj or not obj.pk:
            return '-'
        n = obj.translations.count()
        return format_html('<span style="background:#10b981;color:white;padding:2px 6px;border-radius:3px;">{}</span>', n) if n else '-'
    translations_count.short_description = _('Translations')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['software_guide_translate_url'] = reverse('software_guide_translate')
        except Exception:
            extra_context['software_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['software_guide_translate_url'] = reverse('software_guide_translate')
        except Exception:
            extra_context['software_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class ExternalMediaGuideTranslationInlineMixin:
    """Add AI translate button to each inline translation."""
    pass


class ExternalMediaGuideTranslationInline(ExternalMediaGuideTranslationInlineMixin, admin.StackedInline):
    model = ExternalMediaGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/external_media_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(ExternalMediaGuide)
class ExternalMediaGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [ExternalMediaGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_asset/externalmediaguide/change_form.html'

    def has_base(self, obj):
        return bool(obj and obj.base_content)
    has_base.short_description = _('Has base content')

    def translations_count(self, obj):
        if not obj or not obj.pk:
            return '-'
        n = obj.translations.count()
        return format_html('<span style="background:#10b981;color:white;padding:2px 6px;border-radius:3px;">{}</span>', n) if n else '-'
    translations_count.short_description = _('Translations')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['external_media_guide_translate_url'] = reverse('external_media_guide_translate')
        except Exception:
            extra_context['external_media_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['external_media_guide_translate_url'] = reverse('external_media_guide_translate')
        except Exception:
            extra_context['external_media_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)