from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import AccessIntegration, TelegramBot
from .telegram_client import (
    TelegramAPIError,
    test_bot_connection,
    update_bot_connection_status,
)
from .utils import register_bot_webhook


@admin.register(TelegramBot)
class TelegramBotAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'display_username',
        'company',
        'is_active',
        'connection_status',
        'use_webhook',
        'created_by',
        'updated_at',
    ]
    list_filter = ['is_active', 'use_webhook', 'last_connection_ok', 'company']
    search_fields = ['name', 'bot_username', 'company__name']
    readonly_fields = [
        'bot_username',
        'bot_id',
        'last_connection_check',
        'last_connection_ok',
        'created_at',
        'updated_at',
        'connection_status',
    ]
    filter_horizontal = []
    fieldsets = (
        (_('Basic information'), {
            'fields': ('name', 'company', 'description', 'is_active'),
        }),
        (_('Telegram credentials'), {
            'fields': ('bot_token', 'bot_username', 'bot_id', 'default_chat_id'),
        }),
        (_('Commands'), {
            'fields': ('respond_to_start', 'start_message'),
        }),
        (_('Webhook'), {
            'fields': ('use_webhook', 'webhook_secret'),
        }),
        (_('Connection status'), {
            'fields': ('connection_status', 'last_connection_check', 'last_connection_ok'),
            'classes': ('collapse',),
        }),
        (_('Metadata'), {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def connection_status(self, obj):
        if not obj.pk:
            return '—'
        try:
            if test_bot_connection(obj.bot_token):
                return format_html('<span style="color: green;">✓ {}</span>', _('Connected'))
        except TelegramAPIError:
            pass
        if obj.last_connection_ok:
            return format_html('<span style="color: green;">✓ {}</span>', _('Last check OK'))
        return format_html('<span style="color: red;">✗ {}</span>', _('Connection failed'))

    connection_status.short_description = _('Connection status')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        try:
            bot_info = test_bot_connection(obj.bot_token)
            update_bot_connection_status(obj, True, bot_info)
        except TelegramAPIError:
            update_bot_connection_status(obj, False)
            return
        if obj.respond_to_start or obj.use_webhook:
            register_bot_webhook(obj)


@admin.register(AccessIntegration)
class AccessIntegrationAdmin(admin.ModelAdmin):
    list_display = [
        'group',
        'has_access',
        'can_view_integrations',
        'can_manage_integrations',
        'can_test_connections',
        'companies_list',
    ]
    list_filter = [
        'has_access',
        'can_view_integrations',
        'can_manage_integrations',
        'can_test_connections',
    ]
    search_fields = ('group__name', 'description')
    filter_horizontal = ('companies',)
    fieldsets = (
        (_('Group information'), {
            'fields': ('group', 'description'),
        }),
        (_('Access rights'), {
            'fields': (
                'has_access',
                'can_view_integrations',
                'can_manage_integrations',
                'can_test_connections',
            ),
        }),
        (_('Company access'), {
            'fields': ('companies',),
            'description': _('Leave empty to allow access to all companies.'),
        }),
    )

    def companies_list(self, obj):
        companies = obj.companies.all()
        if not companies.exists():
            return _('All companies')
        return ', '.join(company.name for company in companies[:5])

    companies_list.short_description = _('Companies')
