#  SecBoard\SecBoard\app_suib\admin.py
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db import models
from .models import (RegisterDocs, RelatedDocs, DocType, DocTypeTranslation, AccessDocs, DocStatus, DocStatusTranslation, AccessClassification, AccessClassificationTranslation,
                     RegulatorName, LegislativeDoc, AccessLegislativeDoc, AccessMandatory,
                     RegDocsGuide, RegDocsGuideTranslation,
                     LegislativeDocsGuide, LegislativeDocsGuideTranslation)
from django.utils.translation import gettext_lazy as _
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField

class RelatedDocsInline(admin.TabularInline):
    model = RegisterDocs.related_docs.through
    extra = 1
    verbose_name = _("Related Document")
    verbose_name_plural = _("Related Documents")

@admin.register(RegisterDocs)
class RegisterDocsAdmin(admin.ModelAdmin):
    list_display = ['name_doc', 'company', 'type_doc', 'access_classification', 'vers_doc',
                    'date_doc', 'description', 'file_doc_link', 'vers_doc_html_preview','status_doc', 'display_groups']
    filter_horizontal = ['related_docs', 'groups']
    inlines = [RelatedDocsInline]
    fields = ['name_doc', 'company', 'type_doc', 'access_classification', 'vers_doc', 'vers_doc_html','status_doc',
              'date_doc', 'description', 'file_doc', 'related_docs', 'groups']
    list_filter = ['company', 'groups', 'access_classification']

    def display_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])
    display_groups.short_description = _("Groups")

    def file_doc_link(self, obj):
        if obj.file_doc:
            return mark_safe('<a href="{0}" download>Download</a>'.format(obj.file_doc.url))
        else:
            return '-'
    file_doc_link.short_description = _('Download')

    def vers_doc_html_preview(self, obj):
        if obj.vers_doc_html:
            return mark_safe(obj.vers_doc_html[:100] + '...')
        return '-'
    vers_doc_html_preview.short_description = _('HTML version (preview)')

@admin.register(RelatedDocs)
class RelatedDocsAdmin(admin.ModelAdmin):
    list_display = [ 'name_rel_doc', 'company', 'access_classification', 'date_rel_doc', 'vers_rel_doc', 'status_rel_doc',
                    'description_rel_doc', 'file_rel_doc', 'vers_rel_doc_html_preview', 'display_groups']
    fields = ['name_rel_doc', 'company', 'access_classification', 'date_rel_doc', 'vers_rel_doc', 'status_rel_doc', 'vers_rel_doc_html',
              'description_rel_doc', 'file_rel_doc', 'groups']
    filter_horizontal = ['groups']
    list_filter = ['company', 'groups', 'status_rel_doc', 'access_classification']

    def display_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])
    display_groups.short_description = _("Groups")

    def vers_rel_doc_html_preview(self, obj):
        if obj.vers_rel_doc_html:
            return mark_safe(obj.vers_rel_doc_html[:100] + '...')
        return '-'
    vers_rel_doc_html_preview.short_description = _('HTML version (preview)')



@admin.register(AccessDocs)
class AccessDocsAdmin(admin.ModelAdmin):
    list_display = ['group', 'has_access', 'can_edit', 'display_companies']
    list_editable = ['has_access', 'can_edit']
    list_filter = ['has_access', 'can_edit', 'companies']
    search_fields = ['group__name', 'description']
    filter_horizontal = ['companies']
    ordering = ['group__name']
    
    fieldsets = (
        (_('Group Access'), {
            'fields': ('group', 'has_access', 'can_edit')
        }),
        (_('Companies'), {
            'fields': ('companies',),
            'description': _('Select companies this group can access documents for')
        }),
        (_('Description'), {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
    )
    
    def display_companies(self, obj):
        """Display selected companies in list view"""
        companies = obj.companies.all()
        if companies:
            company_names = [company.name for company in companies[:3]]  # Show first 3
            result = ', '.join(company_names)
            if len(companies) > 3:
                result += f' (+{len(companies) - 3} more)'
            return result
        return _('No companies selected')
    display_companies.short_description = _('Companies')
    display_companies.admin_order_field = 'companies__name'

@admin.register(AccessLegislativeDoc)
class AccessLegislativeDocAdmin(admin.ModelAdmin):
    list_display = ['group', 'has_access', 'can_edit', 'show_link']
    list_editable = ['has_access', 'can_edit', 'show_link']
    list_filter = ['has_access', 'can_edit', 'show_link']
    search_fields = ['group__name']

@admin.register(AccessMandatory)
class AccessMandatoryAdmin(admin.ModelAdmin):
    list_display = ['group', 'has_access', 'can_edit', 'display_companies', 'description_preview']
    list_editable = ['has_access', 'can_edit']
    list_filter = ['has_access', 'can_edit']
    search_fields = ['group__name', 'description']
    filter_horizontal = ['companies']
    
    fieldsets = (
        (_('Access Control'), {
            'fields': ('group', 'has_access', 'can_edit')
        }),
        (_('Company Restrictions'), {
            'fields': ('companies',),
            'description': _('Leave empty to allow access to all companies, or select specific companies to restrict access.')
        }),
        (_('Description'), {
            'fields': ('description',)
        }),
    )
    
    def display_companies(self, obj):
        """Display companies in a readable format"""
        companies = obj.companies.all()
        if not companies.exists():
            return format_html('<span style="color: green;">All Companies</span>')
        return ", ".join([company.name for company in companies])
    display_companies.short_description = _('Companies')
    
    def description_preview(self, obj):
        """Show a preview of the description"""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_preview.short_description = _('Description')


class ActiveCountryInlineMixin:
    """Mixin to limit country choices to active records (same as app_asset)."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class DocTypeTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = DocTypeTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(DocType)
class DocTypeAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'color_display', 'translations_count', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'name_local', 'description']
    inlines = [DocTypeTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For other languages use the Document Type Translations inline below.'),
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
        return obj.get_name() or obj.name or '-'
    get_name_display.short_description = _("DocType")

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


class DocStatusTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = DocStatusTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(DocStatus)
class DocStatusAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'color_display', 'translations_count', 'is_active', 'sort_order']
    list_editable = ['sort_order', 'is_active']
    list_filter = ['is_active', 'sort_order']
    search_fields = ['name', 'code', 'name_local', 'description']
    ordering = ['sort_order', 'id']
    inlines = [DocStatusTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Document Status Translations inline below.'),
        }),
        (_('Display'), {
            'fields': ('color', 'sort_order')
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
        return obj.get_name() or obj.name or '-'
    get_name_display.short_description = _("DocStatus")

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

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('sort_order', 'id')

class AccessClassificationTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = AccessClassificationTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(AccessClassification)
class AccessClassificationAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'icon_display', 'color_display', 'translations_count', 'sort_order', 'is_active']
    list_editable = ['sort_order', 'is_active']
    list_filter = ['is_active', 'sort_order']
    search_fields = ['name', 'code', 'description']
    ordering = ['sort_order', 'id']
    inlines = [AccessClassificationTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
        }),
        (_('Display'), {
            'fields': ('color', 'icon', 'sort_order')
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
        return obj.get_name() or obj.name or ''
    get_name_display.short_description = _("Access Classification")

    def icon_display(self, obj):
        return format_html('<i class="fas {}"></i> {}', obj.icon, obj.icon)
    icon_display.short_description = _("Icon")

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

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('sort_order', 'id')

@admin.register(RegulatorName)
class RegulatorNameAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'color_display', 'website', 'is_active']
    search_fields = ['name', 'code', 'description']
    list_filter = ['is_active']
    list_editable = ['is_active']
    
    def color_display(self, obj):
        return format_html('<span style="color: {}; font-weight: bold;">■ {}</span>', 
                          obj.color, obj.color)
    color_display.short_description = _("Color")

@admin.register(LegislativeDoc)
class LegislativeDocAdmin(admin.ModelAdmin):
    list_display = ['title', 'doc_number', 'get_doc_type_name', 'issuing_authority', 
                   'regulator', 'issue_date', 'effective_date', 'get_companies_display', 'has_pdf', 'has_html', 'is_active']
    list_filter = ['doc_type', 'is_active', 'company', 'regulator', 'groups']
    search_fields = ['title', 'doc_number', 'issuing_authority', 'description']
    filter_horizontal = ['company', 'groups']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    list_editable = ['is_active']
    date_hierarchy = 'effective_date'
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'doc_number', 'doc_type', 'issuing_authority', 'regulator', 'original_url', 'description')
        }),
        (_('Dates'), {
            'fields': ('issue_date', 'effective_date', 'expiration_date')
        }),
        (_('Content'), {
            'fields': ('pdf_file', 'html_content')
        }),
        (_('Access Control'), {
            'fields': ('company', 'groups', 'is_active')
        }),
        (_('Metadata'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    def has_pdf(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank"><span style="color: green;">✓</span></a>', obj.pdf_file.url)
        return format_html('<span style="color: red;">✗</span>')
    has_pdf.short_description = _('PDF')
    
    def has_html(self, obj):
        if obj.html_content:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    has_html.short_description = _('HTML')
    
    def get_doc_type_name(self, obj):
        if obj.doc_type:
            return obj.doc_type.get_name()
        return "-"
    get_doc_type_name.short_description = _("Document Type")
    
    def get_companies_display(self, obj):
        """Display companies as comma-separated list"""
        companies = obj.company.all()
        if companies.exists():
            return ", ".join([company.name for company in companies])
        return "-"
    get_companies_display.short_description = _("Companies")
    
    def save_model(self, request, obj, form, change):
        """Track who created or updated the record"""
        if not change:  # New object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class RegDocsGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class RegDocsGuideTranslationInline(RegDocsGuideTranslationInlineMixin, admin.StackedInline):
    model = RegDocsGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/reg_docs_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(RegDocsGuide)
class RegDocsGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [RegDocsGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_doc/regdocsguide/change_form.html'

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
            extra_context['reg_docs_guide_translate_url'] = reverse('reg_docs_guide_translate')
        except Exception:
            extra_context['reg_docs_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['reg_docs_guide_translate_url'] = reverse('reg_docs_guide_translate')
        except Exception:
            extra_context['reg_docs_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class LegislativeDocsGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class LegislativeDocsGuideTranslationInline(LegislativeDocsGuideTranslationInlineMixin, admin.StackedInline):
    model = LegislativeDocsGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/legislative_docs_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(LegislativeDocsGuide)
class LegislativeDocsGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [LegislativeDocsGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_doc/legislativedocsguide/change_form.html'

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
            extra_context['legislative_docs_guide_translate_url'] = reverse('legislative_docs_guide_translate')
        except Exception:
            extra_context['legislative_docs_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['legislative_docs_guide_translate_url'] = reverse('legislative_docs_guide_translate')
        except Exception:
            extra_context['legislative_docs_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)
