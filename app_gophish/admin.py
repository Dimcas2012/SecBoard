# app_gophish/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import (
    GophishServer, GophishGroup, GophishTemplate, GophishLandingPage,
    GophishSendingProfile, GophishCampaign, GophishEvent, GophishSyncLog, AccessGophish,
    GophishGuide, GophishGuideTranslation
)
from .api_client import gophish_manager
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField


@admin.register(GophishServer)
class GophishServerAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_url', 'is_active', 'connection_status', 'created_by', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'base_url']
    readonly_fields = ['created_at', 'updated_at', 'connection_status']
    actions = ['delete_selected']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'base_url', 'api_key', 'is_active')
        }),
        (_('Metadata'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        (_('Connection Status'), {
            'fields': ('connection_status',),
            'classes': ('collapse',)
        }),
    )
    
    def connection_status(self, obj):
        """Display connection status with color coding"""
        try:
            if gophish_manager.test_server_connection(obj):
                return format_html('<span style="color: green;">✓ Connected</span>')
            else:
                return format_html('<span style="color: red;">✗ Connection Failed</span>')
        except:
            return format_html('<span style="color: orange;">? Unknown</span>')
    connection_status.short_description = _('Connection Status')
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class GophishGroupInline(admin.TabularInline):
    model = GophishGroup
    extra = 0
    readonly_fields = ['gophish_id', 'last_sync', 'target_count']
    
    def target_count(self, obj):
        if obj.pk:
            return obj.target_count
        return '-'
    target_count.short_description = _('Targets')


class GophishTemplateInline(admin.TabularInline):
    model = GophishTemplate
    extra = 0
    readonly_fields = ['gophish_id', 'last_sync']


class GophishLandingPageInline(admin.TabularInline):
    model = GophishLandingPage
    extra = 0
    readonly_fields = ['gophish_id', 'last_sync']


class GophishSendingProfileInline(admin.TabularInline):
    model = GophishSendingProfile
    extra = 0
    readonly_fields = ['gophish_id', 'last_sync']


class GophishCampaignInline(admin.TabularInline):
    model = GophishCampaign
    extra = 0
    readonly_fields = ['gophish_id', 'status', 'last_sync', 'total_targets']
    
    def total_targets(self, obj):
        if obj.pk:
            return obj.total_targets
        return '-'
    total_targets.short_description = _('Targets')


@admin.register(GophishGroup)
class GophishGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'server', 'target_count', 'last_sync']
    list_filter = ['server', 'last_sync']
    search_fields = ['name']
    readonly_fields = ['gophish_id', 'last_sync', 'created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('server', 'name', 'gophish_id')
        }),
        (_('Targets Data'), {
            'fields': ('targets_data',),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('last_sync', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GophishTemplate)
class GophishTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'server', 'subject', 'last_sync']
    list_filter = ['server', 'last_sync']
    search_fields = ['name', 'subject']
    readonly_fields = ['gophish_id', 'last_sync', 'created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('server', 'name', 'gophish_id', 'subject')
        }),
        (_('Content'), {
            'fields': ('html_content', 'text_content')
        }),
        (_('Metadata'), {
            'fields': ('last_sync', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GophishLandingPage)
class GophishLandingPageAdmin(admin.ModelAdmin):
    list_display = ['name', 'server', 'capture_credentials', 'capture_passwords', 'last_sync']
    list_filter = ['server', 'capture_credentials', 'capture_passwords', 'last_sync']
    search_fields = ['name']
    readonly_fields = ['gophish_id', 'last_sync', 'created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('server', 'name', 'gophish_id')
        }),
        (_('Content'), {
            'fields': ('html_content', 'redirect_url')
        }),
        (_('Settings'), {
            'fields': ('capture_credentials', 'capture_passwords')
        }),
        (_('Metadata'), {
            'fields': ('last_sync', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GophishSendingProfile)
class GophishSendingProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'server', 'from_address', 'smtp_host', 'last_sync']
    list_filter = ['server', 'last_sync']
    search_fields = ['name', 'from_address', 'smtp_host']
    readonly_fields = ['gophish_id', 'last_sync', 'created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('server', 'name', 'gophish_id')
        }),
        (_('Email Settings'), {
            'fields': ('from_address', 'from_name')
        }),
        (_('SMTP Settings'), {
            'fields': ('smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'ignore_cert_errors')
        }),
        (_('Metadata'), {
            'fields': ('last_sync', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class GophishEventInline(admin.TabularInline):
    model = GophishEvent
    extra = 0
    readonly_fields = ['event_type', 'target_email', 'timestamp', 'ip_address']
    can_delete = False


@admin.register(GophishCampaign)
class GophishCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'server', 'status', 'total_targets', 'emails_sent', 
        'emails_opened', 'credentials_submitted', 'created_by', 'created_at'
    ]
    list_filter = ['server', 'status', 'created_at']
    search_fields = ['name']
    readonly_fields = [
        'gophish_id', 'last_sync', 'created_at', 'updated_at',
        'total_targets', 'emails_sent', 'emails_opened', 'links_clicked',
        'credentials_submitted', 'data_submitted'
    ]
    filter_horizontal = ['groups']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('server', 'name', 'gophish_id', 'status')
        }),
        (_('Campaign Components'), {
            'fields': ('template', 'landing_page', 'sending_profile', 'groups')
        }),
        (_('Campaign Settings'), {
            'fields': ('launch_date', 'send_by_date', 'url')
        }),
        (_('Results'), {
            'fields': ('total_targets', 'emails_sent', 'emails_opened', 'links_clicked', 'credentials_submitted', 'data_submitted'),
            'classes': ('collapse',)
        }),
        (_('Raw Results Data'), {
            'fields': ('results_data',),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('created_by', 'last_sync', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(GophishEvent)
class GophishEventAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'event_type', 'target_email', 'target_name', 'timestamp', 'ip_address']
    list_filter = ['event_type', 'campaign__server', 'timestamp']
    search_fields = ['target_email', 'target_name', 'campaign__name']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        (_('Event Information'), {
            'fields': ('campaign', 'event_type', 'target_email', 'target_name', 'timestamp')
        }),
        (_('Technical Details'), {
            'fields': ('ip_address', 'user_agent', 'details'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GophishSyncLog)
class GophishSyncLogAdmin(admin.ModelAdmin):
    list_display = [
        'server', 'sync_type', 'status', 'started_at', 'completed_at', 
        'duration', 'records_processed', 'records_created', 'records_updated', 'records_failed'
    ]
    list_filter = ['server', 'sync_type', 'status', 'started_at']
    search_fields = ['server__name', 'error_message']
    readonly_fields = [
        'started_at', 'completed_at', 'duration', 'records_processed', 
        'records_created', 'records_updated', 'records_failed', 'details'
    ]
    date_hierarchy = 'started_at'
    
    fieldsets = (
        (_('Sync Information'), {
            'fields': ('server', 'sync_type', 'status', 'started_at', 'completed_at', 'duration')
        }),
        (_('Results'), {
            'fields': ('records_processed', 'records_created', 'records_updated', 'records_failed')
        }),
        (_('Error Information'), {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        (_('Details'), {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
    )
    
    def duration(self, obj):
        """Display sync duration"""
        if obj.duration:
            total_seconds = obj.duration.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return '-'
    duration.short_description = _('Duration')
    
    def has_add_permission(self, request):
        """Sync logs are created by tasks, not manually"""
        return False


@admin.register(AccessGophish)
class AccessGophishAdmin(admin.ModelAdmin):
    list_display = [
        'group', 'has_access', 'can_view_campaigns', 'can_view_templates', 
        'can_view_landing_pages', 'can_manage_servers', 'can_sync', 'companies_display'
    ]
    list_filter = [
        'has_access', 'can_view_campaigns', 'can_view_templates', 
        'can_view_landing_pages', 'can_manage_servers', 'can_sync'
    ]
    search_fields = ['group__name', 'description']
    filter_horizontal = ['companies']
    
    fieldsets = (
        (_('Group Access'), {
            'fields': ('group', 'description')
        }),
        (_('General Permissions'), {
            'fields': ('has_access',)
        }),
        (_('View Permissions'), {
            'fields': (
                'can_view_campaigns', 
                'can_view_templates', 
                'can_view_landing_pages',
                'can_view_sending_profiles',
                'can_view_groups'
            )
        }),
        (_('Management Permissions'), {
            'fields': ('can_manage_servers', 'can_sync')
        }),
        (_('Company Restrictions'), {
            'fields': ('companies',),
            'description': _('Leave empty to allow access to all companies')
        }),
    )
    
    def companies_display(self, obj):
        if obj.companies.exists():
            company_names = [company.name for company in obj.companies.all()]
            return ', '.join(company_names[:3]) + ('...' if len(company_names) > 3 else '')
        return _('All Companies')
    companies_display.short_description = _('Companies')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('group').prefetch_related('companies')


class GophishGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class GophishGuideTranslationInline(GophishGuideTranslationInlineMixin, admin.StackedInline):
    model = GophishGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/gophish_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(GophishGuide)
class GophishGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [GophishGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_gophish/gophishguide/change_form.html'

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
            extra_context['gophish_guide_translate_url'] = reverse('app_gophish:gophish_guide_translate')
        except Exception:
            extra_context['gophish_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['gophish_guide_translate_url'] = reverse('app_gophish:gophish_guide_translate')
        except Exception:
            extra_context['gophish_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)
