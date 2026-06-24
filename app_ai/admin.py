from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import APISettingsGroq, APISettingsClaude, APISettingsOllama, APISettingsGoogle, APISettingsDeepSeek, ModelChoice, AIAgentSettings, AIAssistantHistory


@admin.register(ModelChoice)
class ModelChoiceAdmin(admin.ModelAdmin):
    list_display = ['provider', 'model_id', 'model_name', 'is_active']
    list_filter = ['provider', 'is_active']
    search_fields = ['provider', 'model_id', 'model_name']
    list_editable = ['is_active']

@admin.register(APISettingsGoogle)
class APISettingsAdmin(admin.ModelAdmin):
    list_display = ['api_key', 'model_name', 'test_connection_button']
    
    def test_connection_button(self, obj):
        if not obj.id:
            return ""
        return format_html(
            '<button type="button" class="test-connection-btn" data-provider="google" data-id="{}">{}</button>',
            obj.id, _('Test Connection')
        )
    
    test_connection_button.short_description = _('Test Connection')
    
    class Media:
        js = ('admin/js/jquery.init.js', 'admin/js/test_connection.js')

@admin.register(APISettingsOllama)
class APISettingsOllamaAdmin(admin.ModelAdmin):
    list_display = ['api_url', 'model_name', 'test_connection_button']
    
    def test_connection_button(self, obj):
        if not obj.id:
            return ""
        return format_html(
            '<button type="button" class="test-connection-btn" data-provider="ollama" data-id="{}">{}</button>',
            obj.id, _('Test Connection')
        )
    
    test_connection_button.short_description = _('Test Connection')
    
    class Media:
        js = ('admin/js/jquery.init.js', 'admin/js/test_connection.js')

@admin.register(APISettingsClaude)
class APISettingsClaudeAdmin(admin.ModelAdmin):
    list_display = ['api_key', 'model_name', 'temperature', 'max_tokens', 'test_connection_button']
    list_filter = ['model_name']
    
    def test_connection_button(self, obj):
        if not obj.id:
            return ""
        return format_html(
            '<button type="button" class="test-connection-btn" data-provider="claude" data-id="{}">{}</button>',
            obj.id, _('Test Connection')
        )
    
    test_connection_button.short_description = _('Test Connection')
    
    class Media:
        js = ('admin/js/jquery.init.js', 'admin/js/test_connection.js')

@admin.register(APISettingsGroq)
class APISettingsGroqAdmin(admin.ModelAdmin):
    list_display = ['api_key', 'model_name', 'test_connection_button']
    list_filter = ['model_name']
    
    def test_connection_button(self, obj):
        if not obj.id:
            return ""
        return format_html(
            '<button type="button" class="test-connection-btn" data-provider="groq" data-id="{}">{}</button>',
            obj.id, _('Test Connection')
        )
    
    test_connection_button.short_description = _('Test Connection')
    
    class Media:
        js = ('admin/js/jquery.init.js', 'admin/js/test_connection.js')

@admin.register(APISettingsDeepSeek)
class APISettingsDeepSeekAdmin(admin.ModelAdmin):
    list_display = ['model_name', 'temperature', 'max_tokens', 'test_connection_button']
    list_filter = ['model_name']
    
    def test_connection_button(self, obj):
        if not obj.id:
            return ""
        return format_html(
            '<button type="button" class="test-connection-btn" data-provider="deepseek" data-id="{}">{}</button>',
            obj.id, _('Test Connection')
        )
    
    test_connection_button.short_description = _('Test Connection')
    
    class Media:
        js = ('admin/js/jquery.init.js', 'admin/js/test_connection.js')

@admin.register(AIAgentSettings)
class AIAgentSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'model_choice', 'is_active', 'enabled_for_all_pages']
    list_filter = ['is_active', 'enabled_for_all_pages', 'model_choice__provider']
    search_fields = ['user__username', 'user__email']
    fieldsets = (
        ('Основні налаштування', {
            'fields': ('user', 'model_choice', 'is_active')
        }),
        ('Опції відображення', {
            'fields': ('enabled_for_all_pages',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Для глобальних налаштувань користувач не обов'язковий
        if not obj:
            form.base_fields['user'].required = False
        return form

@admin.register(AIAssistantHistory)
class AIAssistantHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'model_choice', 'user_message_preview', 'page_type', 'is_success', 'tokens_info', 'response_time_ms', 'created_at']
    list_filter = ['is_success', 'page_type', 'model_choice__provider', 'created_at']
    search_fields = ['user__username', 'user__email', 'user_message', 'ai_response', 'page_url', 'page_description']
    readonly_fields = ['user', 'model_choice', 'user_message', 'ai_response', 'page_url', 'page_type', 'page_description', 
                       'is_success', 'error_message', 'created_at', 'response_time_ms', 'input_tokens', 'output_tokens', 'total_tokens']
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    fieldsets = (
        ('Основна інформація', {
            'fields': ('user', 'model_choice', 'created_at', 'is_success', 'response_time_ms')
        }),
        ('Токени', {
            'fields': ('input_tokens', 'output_tokens', 'total_tokens')
        }),
        ('Запит', {
            'fields': ('user_message',)
        }),
        ('Відповідь', {
            'fields': ('ai_response',)
        }),
        ('Контекст сторінки', {
            'fields': ('page_url', 'page_type', 'page_description')
        }),
        ('Помилка', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
    
    def user_message_preview(self, obj):
        """Прев'ю повідомлення користувача"""
        if obj.user_message:
            preview = obj.user_message[:100]
            if len(obj.user_message) > 100:
                preview += '...'
            return preview
        return '-'
    user_message_preview.short_description = _('User Message')
    
    def tokens_info(self, obj):
        """Інформація про токени"""
        if obj.total_tokens is not None:
            parts = []
            if obj.input_tokens is not None:
                parts.append(f"In: {obj.input_tokens}")
            if obj.output_tokens is not None:
                parts.append(f"Out: {obj.output_tokens}")
            if obj.total_tokens is not None:
                parts.append(f"Total: {obj.total_tokens}")
            return " / ".join(parts)
        return "-"
    tokens_info.short_description = _('Tokens')
    
    def has_add_permission(self, request):
        """Заборона додавання вручну - історія створюється автоматично"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Заборона редагування - історія доступна тільки для перегляду"""
        return False