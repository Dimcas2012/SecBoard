from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Classification, ClassificationTranslation, Currentstate, CurrentstateTranslation, Incidenttype, IncidenttypeTranslation, AccessIncidents, Incident, IncidentRegisterGuide, IncidentRegisterGuideTranslation
from django.utils.translation import gettext_lazy as _
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField



class ActiveCountryInlineMixin:
    """Mixin to limit country choices to active records (same as app_doc/app_asset)."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ClassificationTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = ClassificationTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'get_description_display', 'color_display', 'translations_count', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'description', 'translations__name_local']
    inlines = [ClassificationTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Display'), {
            'fields': ('color',)
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

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '—'
    get_name_display.short_description = _("Classification")

    def get_description_display(self, obj):
        desc = obj.get_description()
        return desc[:50] + '...' if desc and len(desc) > 50 else (desc or '-')
    get_description_display.short_description = _("Description")

    def color_display(self, obj):
        return format_html('<span style="color: {};">⬤</span> {}', obj.color, obj.color)
    color_display.short_description = _("Color")

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


class CurrentstateTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = CurrentstateTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(Currentstate)
class CurrentstateAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'get_description_display', 'color_display', 'translations_count', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'description', 'translations__name_local']
    inlines = [CurrentstateTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Display'), {
            'fields': ('color',)
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

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '—'
    get_name_display.short_description = _("Current State")

    def get_description_display(self, obj):
        desc = obj.get_description()
        return desc[:50] + '...' if desc and len(desc) > 50 else (desc or '-')
    get_description_display.short_description = _("Description")

    def color_display(self, obj):
        return format_html('<span style="color: {};">⬤</span> {}', obj.color, obj.color)
    color_display.short_description = _("Color")

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


class IncidenttypeTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = IncidenttypeTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(Incidenttype)
class IncidenttypeAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'get_description_display', 'color_display', 'translations_count', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'description', 'translations__name_local']
    inlines = [IncidenttypeTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Display'), {
            'fields': ('color',)
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

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '—'
    get_name_display.short_description = _("Incident Type")

    def get_description_display(self, obj):
        desc = obj.get_description()
        return desc[:50] + '...' if desc and len(desc) > 50 else (desc or '-')
    get_description_display.short_description = _("Description")

    def color_display(self, obj):
        return format_html('<span style="color: {};">⬤</span> {}', obj.color, obj.color)
    color_display.short_description = _("Color")

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


@admin.register(AccessIncidents)
class AccessIncidentsAdmin(admin.ModelAdmin):
    list_display = ['group', 'description', 'has_access', 'can_edit', 'can_add', 'can_delete', 'can_mail', 'show_link', 'display_companies']
    list_editable = ['has_access', 'can_edit', 'can_add', 'can_delete', 'can_mail', 'show_link']
    list_filter = ['has_access', 'can_edit', 'can_add', 'can_delete', 'can_mail', 'show_link', 'companies']
    search_fields = ['group__name', 'companies__name']
    filter_horizontal = ['companies']

    def display_companies(self, obj):
        return ", ".join([company.name for company in obj.companies.all()])

    display_companies.short_description = _("Companies")


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ['id', 'company', 'occurrence_datetime', 'place', 'classification', 'incident_type', 'current_state', 'responsible', 'reported_by', 'created_at']
    list_filter = ['company', 'classification', 'incident_type', 'current_state', 'occurrence_datetime', 'created_at']
    search_fields = ['place', 'description', 'responsible', 'reported_by', 'registered_by', 'company__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'occurrence_datetime'
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('company', 'occurrence_datetime', 'place', 'description')
        }),
        (_('Classification'), {
            'fields': ('classification', 'incident_type', 'current_state')
        }),
        (_('Details'), {
            'fields': ('features', 'impact', 'measures_taken', 'additional_measures', 'reports_and_records', 'comment')
        }),
        (_('Responsible Parties'), {
            'fields': ('responsible', 'reported_by', 'reported_datetime', 'registered_by', 'registered_datetime')
        }),
        (_('Files'), {
            'fields': ('file_incident',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class IncidentRegisterGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class IncidentRegisterGuideTranslationInline(IncidentRegisterGuideTranslationInlineMixin, admin.StackedInline):
    model = IncidentRegisterGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/incident_register_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(IncidentRegisterGuide)
class IncidentRegisterGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [IncidentRegisterGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_incident/incidentregisterguide/change_form.html'

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
            extra_context['incident_register_guide_translate_url'] = reverse('incident_register_guide_translate')
        except Exception:
            extra_context['incident_register_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['incident_register_guide_translate_url'] = reverse('incident_register_guide_translate')
        except Exception:
            extra_context['incident_register_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)
