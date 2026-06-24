#  SecBoard\SecBoard\app_keycert\admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db import models
from django.urls import reverse
from .models import AccessKeyCert, Revocationstatus, RevocationstatusTranslation, Typekeycert, TypekeycertTranslation, KeyCertificates, KeyCertGuide, KeyCertGuideTranslation
from django.utils.translation import gettext_lazy as _
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField


class ActiveCountryInlineMixin:
    """Mixin to limit country choices to active records (same as app_doc/app_incident)."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class TypekeycertTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = TypekeycertTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(Typekeycert)
class TypekeycertAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'color_display', 'translations_count', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'description', 'translations__name_local']
    inlines = [TypekeycertTranslationInline]
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
    get_name_display.short_description = _("Key/Certificate Type")

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


class RevocationstatusTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = RevocationstatusTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(Revocationstatus)
class RevocationstatusAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'color_display', 'translations_count', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'description', 'translations__name_local']
    inlines = [RevocationstatusTranslationInline]
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
    get_name_display.short_description = _("Revocation Status")

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



@admin.register(AccessKeyCert)
class AccessKeyCertAdmin(admin.ModelAdmin):
    list_display = ['group', 'description', 'has_access', 'can_edit', 'show_link', 'display_companies']
    list_editable = ['has_access', 'can_edit', 'show_link']
    list_filter = ['has_access', 'can_edit', 'show_link', 'companies']
    search_fields = ['group__name', 'companies__name']
    filter_horizontal = ['companies']

    def display_companies(self, obj):
        return ", ".join([company.name for company in obj.companies.all()])
    display_companies.short_description = _("Companies")



@admin.register(KeyCertificates)
class KeyCertificatesAdmin(admin.ModelAdmin):
    list_display = ['key_cert_num', 'company', 'type_key_sert', 'owner', 'expiry_date', 'revocation_status', 'enable_reminder', 'created_at']
    list_filter = ['company', 'type_key_sert', 'revocation_status', 'enable_reminder', 'expiry_date', 'created_at']
    search_fields = ['key_cert_num', 'purpose', 'location', 'owner__name', 'company__name', 'cert_hash']
    readonly_fields = ['created_at', 'updated_at', 'added_by', 'updated_by']
    date_hierarchy = 'expiry_date'

    fieldsets = (
        (_('Identification'), {
            'fields': ('company', 'key_cert_num', 'type_key_sert', 'cert_hash')
        }),
        (_('Usage & Location'), {
            'fields': ('purpose', 'location', 'owner', 'access_control')
        }),
        (_('Status'), {
            'fields': ('expiry_date', 'revocation_status', 'notes')
        }),
        (_('Reminders'), {
            'fields': ('enable_reminder',)
        }),
        (_('Audit'), {
            'fields': ('added_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class KeyCertGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class KeyCertGuideTranslationInline(KeyCertGuideTranslationInlineMixin, admin.StackedInline):
    model = KeyCertGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/keycert_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(KeyCertGuide)
class KeyCertGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [KeyCertGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_keycert/keycertguide/change_form.html'

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
            extra_context['keycert_guide_translate_url'] = reverse('keycert_guide_translate')
        except Exception:
            extra_context['keycert_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['keycert_guide_translate_url'] = reverse('keycert_guide_translate')
        except Exception:
            extra_context['keycert_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


