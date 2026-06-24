# SecBoard/app_std/admin.py
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from app_conf.models import Country
from .models import (
    PCIDSSRequirement, PCIDSSCategory, PCIDSSCategoryTranslation, AccessPCIDSS,
    ISO27002Theme, ISO27002Control, ISO27002ControlTranslation, AccessISO27002
)


class ActiveCountryInlineMixin:
    """Mixin to limit country choices to active records (same as app_risk / app_access)."""
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class PCIDSSCategoryTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = PCIDSSCategoryTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(PCIDSSCategory)
class PCIDSSCategoryAdmin(admin.ModelAdmin):
    list_display = (
        'get_name_display',
        'category_id',
        'code',
        'translations_count',
        'is_active'
    )
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = (
        'name',
        'name_local',
        'code',
        'category_id',
        'translations__name_local'
    )
    inlines = [PCIDSSCategoryTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('category_id', 'name', 'code'),
            'description': _('Default: English. For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'description': _('For other languages use the Translations inline below.'),
            'classes': ('collapse',),
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or obj.name_local or '—'
    get_name_display.short_description = _('PCI DSS Standard')

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return count
        return ''
    translations_count.short_description = _('Translations')


@admin.register(PCIDSSRequirement)
class PCIDSSRequirementAdmin(admin.ModelAdmin):
    list_display = ('requirement_number', 'category', 'get_title_display')
    list_filter = ('category',)
    search_fields = ('requirement_number', 'title', 'description')

    def get_title_display(self, obj):
        return (obj.get_title() or obj.title or '—')[:80]
    get_title_display.short_description = _('Title')


@admin.register(AccessPCIDSS)
class AccessPCIDSSAdmin(admin.ModelAdmin):
    list_display = ['group', 'description', 'has_access', 'can_edit', 'show_link']
    list_editable = ['has_access', 'can_edit', 'show_link']
    list_filter = ['has_access', 'can_edit', 'show_link']
    search_fields = ['group__name']


@admin.register(ISO27002Theme)
class ISO27002ThemeAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_name_display', 'get_description_display')
    search_fields = ('name', 'description', 'translations__description')
    list_filter = ('name',)

    def get_description_display(self, obj):
        return (obj.get_description() or obj.description or '—')[:80]
    get_description_display.short_description = _('Description')


class ISO27002ControlTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = ISO27002ControlTranslation
    extra = 1
    fields = ('country', 'title', 'control_description', 'purpose', 'guidance', 'other_information')
    autocomplete_fields = ['country']


@admin.register(ISO27002Control)
class ISO27002ControlAdmin(admin.ModelAdmin):
    list_display = (
        'control_number',
        'theme',
        'get_title_display',
        'control_type',
        'security_domain'
    )
    list_filter = (
        'theme',
        'control_type',
        'security_domain'
    )
    search_fields = (
        'control_number',
        'title',
        'control_description',
        'translations__title',
        'translations__control_description'
    )
    readonly_fields = (
        'information_security_properties',
        'cybersecurity_concepts',
        'operational_capabilities'
    )

    def get_title_display(self, obj):
        return (obj.get_title() or obj.title or '—')[:80]
    get_title_display.short_description = _('Title')

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('control_number', 'theme', 'control_type', 'security_domain')
        }),
        (_('Properties and Concepts'), {
            'fields': (
                'information_security_properties',
                'cybersecurity_concepts',
                'operational_capabilities'
            )
        }),
        (_('Content (default language)'), {
            'fields': ('title', 'control_description', 'purpose', 'guidance', 'other_information'),
            'description': _('Default (e.g. English). For other languages use Translations inline.'),
        }),
    )
    inlines = [ISO27002ControlTranslationInline]


@admin.register(AccessISO27002)
class AccessISO27002Admin(admin.ModelAdmin):
    list_display = ['group', 'description', 'has_access', 'can_edit', 'show_link']
    list_editable = ['has_access', 'can_edit', 'show_link']
    list_filter = ['has_access', 'can_edit', 'show_link']
    search_fields = ['group__name']