import json
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField
from .models import WazuhFIMAlert, WazuhAgent, WebhookClient, WebhookAuthConfig, AccessFIM, AnalysisConfig, AnalysisResult, AIAnalysisResult, FimDashboardGuide, FimDashboardGuideTranslation


@admin.register(WazuhFIMAlert)
class WazuhFIMAlertAdmin(admin.ModelAdmin):
    list_display = [
        'alert_id', 'file_name', 'alert_type', 'level', 'agent_name', 
        'timestamp', 'processed', 'is_critical_display'
    ]
    list_filter = [
        'alert_type', 'level', 'processed', 'agent_name', 'timestamp'
    ]
    search_fields = [
        'alert_id', 'file_name', 'file_path', 'description', 'agent_name', 'agent_id'
    ]
    readonly_fields = [
        'alert_id', 'received_at', 'raw_data_display', 'file_hashes_display'
    ]
    fieldsets = (
        ('Alert Information', {
            'fields': ('alert_id', 'rule_id', 'rule_name', 'level', 'description', 'alert_type')
        }),
        ('File Information', {
            'fields': ('file_path', 'file_name', 'file_size', 'file_hashes_display')
        }),
        ('Agent Information', {
            'fields': ('agent_id', 'agent_name', 'agent_ip')
        }),
        ('Timestamps', {
            'fields': ('timestamp', 'received_at')
        }),
        ('Processing Status', {
            'fields': ('processed', 'processed_at', 'status', 'tags')
        }),
        ('Raw Data', {
            'fields': ('raw_data_display',),
            'classes': ('collapse',)
        }),
    )
    
    def is_critical_display(self, obj):
        if obj.is_critical():
            return format_html('<span style="color: red; font-weight: bold;">CRITICAL</span>')
        elif obj.is_high_severity():
            return format_html('<span style="color: orange;">HIGH</span>')
        else:
            return format_html('<span style="color: green;">NORMAL</span>')
    is_critical_display.short_description = 'Severity'
    
    def raw_data_display(self, obj):
        if obj.raw_data:
            return format_html('<pre>{}</pre>', json.dumps(obj.raw_data, indent=2))
        return '-'
    raw_data_display.short_description = 'Raw Data'
    
    def file_hashes_display(self, obj):
        hashes = []
        if obj.file_hash_md5:
            hashes.append(f'MD5: {obj.file_hash_md5}')
        if obj.file_hash_sha1:
            hashes.append(f'SHA1: {obj.file_hash_sha1}')
        if obj.file_hash_sha256:
            hashes.append(f'SHA256: {obj.file_hash_sha256}')
        return format_html('<br>'.join(hashes)) if hashes else '-'
    file_hashes_display.short_description = 'File Hashes'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


@admin.register(WazuhAgent)
class WazuhAgentAdmin(admin.ModelAdmin):
    list_display = [
        'agent_name', 'agent_id', 'agent_ip', 'platform', 'status', 
        'last_seen', 'alert_count_display'
    ]
    list_filter = ['status', 'platform', 'os_name', 'first_seen', 'last_seen']
    search_fields = ['agent_name', 'agent_id', 'agent_ip']
    readonly_fields = ['agent_id', 'first_seen', 'alert_count_display', 'metadata_display']
    
    fieldsets = (
        ('Agent Information', {
            'fields': ('agent_id', 'agent_name', 'agent_ip', 'agent_version')
        }),
        ('System Information', {
            'fields': ('platform', 'os_name', 'os_version')
        }),
        ('Status', {
            'fields': ('status', 'first_seen', 'last_seen')
        }),
        ('Statistics', {
            'fields': ('alert_count_display',)
        }),
        ('Metadata', {
            'fields': ('metadata_display',),
            'classes': ('collapse',)
        }),
    )
    
    def alert_count_display(self, obj):
        count = obj.get_alert_count()
        if count > 0 and obj.agent_id:
            url = reverse('admin:app_soc_wazuhfimalert_changelist') + f'?agent_id__exact={obj.agent_id}'
            return format_html('<a href="{}">{} alerts</a>', url, count)
        return f'{count} alerts'
    alert_count_display.short_description = 'Total Alerts'
    
    def metadata_display(self, obj):
        if obj.metadata:
            return format_html('<pre>{}</pre>', json.dumps(obj.metadata, indent=2))
        return '-'
    metadata_display.short_description = 'Metadata'


@admin.register(WebhookClient)
class WebhookClientAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'client_id', 'ip_address', 'port', 'client_type', 
        'environment', 'enabled', 'webhook_url_display', 'auth_status_display'
    ]
    list_filter = ['client_type', 'environment', 'enabled', 'created_at']
    search_fields = ['name', 'client_id', 'ip_address', 'description']
    readonly_fields = ['client_id', 'created_at', 'updated_at', 'webhook_url_display', 'auth_status_display']
    
    fieldsets = (
        ('Client Information', {
            'fields': ('client_id', 'name', 'ip_address', 'port', 'client_type', 'environment')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Status', {
            'fields': ('enabled', 'created_at', 'updated_at')
        }),
        ('Webhook Information', {
            'fields': ('webhook_url_display', 'auth_status_display')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    def webhook_url_display(self, obj):
        url = obj.get_webhook_url()
        return format_html('<code>{}</code>', url)
    webhook_url_display.short_description = 'Webhook URL'
    
    def auth_status_display(self, obj):
        auth_config = obj.get_auth_config()
        if auth_config:
            if auth_config.enabled and auth_config.auth_type != 'none':
                return format_html(
                    '<span style="color: green;">✓ {}</span>', 
                    auth_config.get_auth_type_display()
                )
            else:
                return format_html('<span style="color: orange;">⚠ Disabled</span>')
        else:
            return format_html('<span style="color: red;">✗ No Auth</span>')
    auth_status_display.short_description = 'Authentication'


@admin.register(WebhookAuthConfig)
class WebhookAuthConfigAdmin(admin.ModelAdmin):
    list_display = [
        'client', 'auth_type', 'enabled', 'created_at', 'updated_at'
    ]
    list_filter = ['auth_type', 'enabled', 'created_at']
    search_fields = ['client__name', 'client__client_id']
    readonly_fields = ['created_at', 'updated_at', 'auth_data_display']
    
    fieldsets = (
        ('Client', {
            'fields': ('client',)
        }),
        ('Authentication Settings', {
            'fields': ('auth_type', 'enabled')
        }),
        ('Encrypted Data', {
            'fields': ('auth_data_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def auth_data_display(self, obj):
        if obj.encrypted_data:
            try:
                auth_data = obj.get_auth_data()
                # Hide sensitive values for display
                display_data = {}
                for key, value in auth_data.items():
                    if key in ['password', 'token', 'header_value']:
                        display_data[key] = '***HIDDEN***'
                    else:
                        display_data[key] = value
                return format_html('<pre>{}</pre>', json.dumps(display_data, indent=2))
            except Exception as e:
                return format_html('<span style="color: red;">Error decrypting: {}</span>', str(e))
        return '-'
    auth_data_display.short_description = 'Authentication Data (Decrypted)'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client')


@admin.register(AccessFIM)
class AccessFIMAdmin(admin.ModelAdmin):
    list_display = [
        'group', 'has_access', 'can_edit', 'can_add', 'can_delete', 
        'can_configure', 'companies_display'
    ]
    list_filter = ['has_access', 'can_edit', 'can_add', 'can_delete', 'can_configure']
    search_fields = ['group__name', 'description']
    filter_horizontal = ['companies']
    
    fieldsets = (
        ('Group Access', {
            'fields': ('group', 'description')
        }),
        ('FIM Dashboard Permissions', {
            'fields': ('has_access',)
        }),
        ('FIM Alerts Permissions', {
            'fields': ('can_edit',)
        }),
        ('Webhook Clients Permissions', {
            'fields': ('can_add', 'can_delete', 'can_configure')
        }),
        ('Company Restrictions', {
            'fields': ('companies',),
            'description': 'Leave empty to allow access to all companies'
        }),
    )
    
    def companies_display(self, obj):
        if obj.companies.exists():
            company_names = [company.name for company in obj.companies.all()]
            return ', '.join(company_names[:3]) + ('...' if len(company_names) > 3 else '')
        return 'All Companies'
    companies_display.short_description = 'Companies'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('group').prefetch_related('companies')


@admin.register(AnalysisConfig)
class AnalysisConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'data_type', 'method', 'url_display', 'enabled', 'timeout', 
        'created_by', 'created_at', 'credential_status'
    ]
    list_filter = ['data_type', 'method', 'enabled', 'created_at']
    search_fields = ['name', 'url']
    readonly_fields = ['created_at', 'updated_at', 'credential_status']
    
    fieldsets = (
        ('Configuration', {
            'fields': ('name', 'data_type', 'method', 'url')
        }),
        ('Credentials', {
            'fields': ('credential_status',),
            'description': 'Use the API views to set credentials securely'
        }),
        ('Settings', {
            'fields': ('enabled', 'timeout')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def url_display(self, obj):
        return format_html('<code style="word-break: break-all;">{}</code>', obj.url[:100] + ('...' if len(obj.url) > 100 else ''))
    url_display.short_description = 'URL'
    
    def credential_status(self, obj):
        if obj.encrypted_credential:
            return format_html('<span style="color: green;">✓ Configured</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Set</span>')
    credential_status.short_description = 'Credential Status'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = [
        'analysis_id', 'alert', 'analysis_service', 'hash_type', 'hash_value_short',
        'status', 'threat_level', 'detection_rate_display', 'created_at', 'analyzed_by'
    ]
    list_filter = ['status', 'threat_level', 'hash_type', 'analysis_service', 'created_at']
    search_fields = ['analysis_id', 'hash_value', 'alert__alert_id', 'analysis_service']
    readonly_fields = ['analysis_id', 'created_at', 'updated_at', 'detection_rate']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Analysis Information', {
            'fields': ('analysis_id', 'alert', 'analysis_config', 'analysis_service')
        }),
        ('Hash Data', {
            'fields': ('hash_type', 'hash_value')
        }),
        ('Results', {
            'fields': ('status', 'threat_level', 'detections', 'total_engines', 'detection_rate')
        }),
        ('Detailed Results', {
            'fields': ('raw_response', 'engine_results', 'file_info', 'behavior_analysis'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('analysis_url', 'permalink', 'scan_date', 'analyzed_by', 'created_at', 'updated_at')
        }),
    )
    
    def hash_value_short(self, obj):
        return f"{obj.hash_value[:16]}..." if len(obj.hash_value) > 16 else obj.hash_value
    hash_value_short.short_description = 'Hash Value'
    
    def detection_rate_display(self, obj):
        return f"{obj.detection_rate:.1f}%"
    detection_rate_display.short_description = 'Detection Rate'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('alert', 'analysis_config', 'analyzed_by')


@admin.register(AIAnalysisResult)
class AIAnalysisResultAdmin(admin.ModelAdmin):
    list_display = [
        'analysis_id', 'alert', 'ai_provider', 'ai_model', 'analysis_type',
        'risk_level', 'confidence', 'created_at', 'analyzed_by'
    ]
    list_filter = ['ai_provider', 'analysis_type', 'risk_level', 'confidence', 'created_at']
    search_fields = ['analysis_id', 'alert__alert_id', 'ai_provider', 'ai_model']
    readonly_fields = ['analysis_id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Analysis Information', {
            'fields': ('analysis_id', 'alert', 'analysis_type', 'analysis_depth')
        }),
        ('AI Configuration', {
            'fields': ('ai_provider', 'ai_model', 'temperature')
        }),
        ('Results', {
            'fields': ('risk_level', 'confidence', 'summary')
        }),
        ('Detailed Results', {
            'fields': ('key_findings', 'recommendations', 'alert_context'),
            'classes': ('collapse',)
        }),
        ('Configuration Data', {
            'fields': ('custom_prompt', 'included_info', 'analysis_config'),
            'classes': ('collapse',)
        }),
        ('Raw Data', {
            'fields': ('raw_response',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('analyzed_by', 'created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('alert', 'analyzed_by')


class FimDashboardGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class FimDashboardGuideTranslationInline(FimDashboardGuideTranslationInlineMixin, admin.StackedInline):
    model = FimDashboardGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/fim_dashboard_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(FimDashboardGuide)
class FimDashboardGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [FimDashboardGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_soc/fimdashboardguide/change_form.html'

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
            extra_context['fim_dashboard_guide_translate_url'] = reverse('app_soc:fim_dashboard_guide_translate')
        except Exception:
            extra_context['fim_dashboard_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['fim_dashboard_guide_translate_url'] = reverse('app_soc:fim_dashboard_guide_translate')
        except Exception:
            extra_context['fim_dashboard_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)
