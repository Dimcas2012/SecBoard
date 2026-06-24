#  SecBoard\SecBoard\app_conf\admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import (ErrorLog, LogEntry, GoogleTagSettings, CelerySettings, 
                     SiteSettings, ContactSettings, AccessOption, MailServer, MailAccount, Email,
                     KnowledgeBaseCategory, KnowledgeBaseArticle, ContactMessage, Company, Country, CompanyType, CompanyTypeTranslation)





@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'level', 'logger_name', 'message_short', 'user')
    list_filter = ('level', 'logger_name', 'timestamp')
    search_fields = ('message', 'logger_name', 'user')
    readonly_fields = ('timestamp', 'level', 'logger_name', 'message', 'trace', 'request_path', 'user')

    def message_short(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message

    message_short.short_description = _("Message")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False




@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'error_type', 'error_message_short', 'request_path', 'user', 'resolved')
    list_filter = ('error_type', 'resolved', 'timestamp')
    search_fields = ('error_message', 'error_type', 'request_path', 'user')
    readonly_fields = ('timestamp', 'error_type', 'error_message', 'stack_trace',
                      'request_path', 'request_method', 'user')
    date_hierarchy = 'timestamp'
    list_per_page = 50
    actions = ['mark_as_resolved', 'mark_as_unresolved']

    def error_message_short(self, obj):
        return obj.error_message[:100] + '...' if len(obj.error_message) > 100 else obj.error_message
    error_message_short.short_description = _("Error Message")

    def mark_as_resolved(self, request, queryset):
        queryset.update(resolved=True)
    mark_as_resolved.short_description = _("Mark selected errors as resolved")

    def mark_as_unresolved(self, request, queryset):
        queryset.update(resolved=False)
    mark_as_unresolved.short_description = _("Mark selected errors as unresolved")


@admin.register(GoogleTagSettings)
class GoogleTagSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'enable_google_analytics', 'enable_google_tag_manager', 'enable_facebook_pixel', 'is_active', 'updated_at')
    list_filter = ('enable_google_analytics', 'enable_google_tag_manager', 'enable_facebook_pixel', 'is_active', 'updated_at')
    search_fields = ('google_analytics_id', 'google_tag_manager_id', 'facebook_pixel_id')
    
    fieldsets = (
        (_('Google Analytics Settings'), {
            'fields': ('enable_google_analytics', 'google_analytics_id'),
            'classes': ('collapse',),
        }),
        (_('Google Tag Manager Settings'), {
            'fields': ('enable_google_tag_manager', 'google_tag_manager_id'),
            'classes': ('collapse',),
        }),
        (_('Facebook Pixel Settings'), {
            'fields': ('enable_facebook_pixel', 'facebook_pixel_id'),
            'classes': ('collapse',),
        }),
        (_('Custom Scripts'), {
            'fields': ('custom_head_scripts', 'custom_body_scripts'),
            'classes': ('collapse',),
        }),
        (_('General Settings'), {
            'fields': ('is_active',),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        # Only allow one instance (singleton pattern)
        return not GoogleTagSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of the settings
        return False
    
    def response_add(self, request, obj, post_url_continue=None):
        # Redirect to change form after adding
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:app_conf_googletagsettings_change', args=[obj.pk]))
    
    def changelist_view(self, request, extra_context=None):
        # If no settings exist, create one and redirect to it
        if not GoogleTagSettings.objects.exists():
            settings = GoogleTagSettings.objects.create()
            from django.http import HttpResponseRedirect
            from django.urls import reverse
            return HttpResponseRedirect(reverse('admin:app_conf_googletagsettings_change', args=[settings.pk]))
        return super().changelist_view(request, extra_context)


@admin.register(CelerySettings)
class CelerySettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'enable_worker', 'enable_beat', 'auto_start_with_runserver', 'is_active', 'updated_at')
    list_filter = ('enable_worker', 'enable_beat', 'auto_start_with_runserver', 'use_windows_commands', 'is_active')
    search_fields = ('redis_host',)
    
    fieldsets = (
        (_('Celery Worker Settings'), {
            'fields': ('enable_worker', 'worker_concurrency', 'worker_loglevel'),
            'classes': ('collapse',),
        }),
        (_('Celery Beat Settings'), {
            'fields': ('enable_beat', 'beat_loglevel'),
            'classes': ('collapse',),
        }),
        (_('Redis Configuration'), {
            'fields': ('redis_host', 'redis_port', 'redis_db', 'redis_password'),
            'classes': ('collapse',),
        }),
        (_('Auto-start Settings'), {
            'fields': ('auto_start_with_runserver', 'use_windows_commands', 'kill_existing_processes'),
        }),
        (_('Custom Commands'), {
            'fields': ('custom_worker_command', 'custom_beat_command'),
            'classes': ('collapse',),
            'description': _('Leave empty to use default commands. Custom commands will override all other settings.'),
        }),
        (_('General Settings'), {
            'fields': ('is_active',),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        # Only allow one instance (singleton pattern)
        return not CelerySettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of the settings
        return False
    
    def response_add(self, request, obj, post_url_continue=None):
        # Redirect to change form after adding
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:app_conf_celerysettings_change', args=[obj.pk]))
    
    def changelist_view(self, request, extra_context=None):
        # If no settings exist, create one and redirect to it
        if not CelerySettings.objects.exists():
            import platform
            settings = CelerySettings.objects.create(
                use_windows_commands=platform.system() == 'Windows'
            )
            from django.http import HttpResponseRedirect
            from django.urls import reverse
            return HttpResponseRedirect(reverse('admin:app_conf_celerysettings_change', args=[settings.pk]))
        return super().changelist_view(request, extra_context)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'project_type_badge', 'site_domain', 'site_protocol', 'is_active', 'updated_at')
    list_filter = ('project_type', 'site_protocol', 'is_active')
    search_fields = ('site_name', 'site_domain')
    
    fieldsets = (
        (_('Project Configuration'), {
            'fields': ('project_type',),
            'description': _('Select project type: Production (default blue), Test (red navbar), or Demo (green navbar). This affects the navbar color and site name display.'),
        }),
        (_('DEMO Credentials'), {
            'fields': ('demo_login', 'demo_password'),
            'description': _('When Project Type is DEMO, these credentials are shown on the login page for users to copy. Leave empty to hide.'),
        }),
        (_('Site Information'), {
            'fields': ('site_name', 'site_description'),
        }),
        (_('Site URL Settings'), {
            'fields': ('site_domain', 'site_protocol'),
            'description': _('These settings are used in email notifications and other system URLs.'),
        }),
        (_('Public Pages Visibility'), {
            'fields': (
                'show_about_page',
                'show_knowledge_base',
                'show_faq_page',
                'show_partnership_page',
                'show_contact_page',
            ),
            'description': _('Control which informational pages under /about/ are publicly accessible and visible in navigation.'),
        }),
        (_('Email Settings'), {
            'fields': ('default_from_email',),
            'description': _('Configure default email address for system notifications.'),
        }),
        (_('License Information'), {
            'fields': (
                'license_status_display',
                'license_company_display',
                'license_expiration_display',
                'license_hardware_id_display',
                'license_max_users_display',
                # 'license_modules_display',  # Disabled
                'license_activated_at_display',
                'license_last_heartbeat_display',
                'license_last_validated_display',
                'license_send_heartbeat_display',
            ),
            'description': _('Current license information and status.'),
        }),
        (_('General Settings'), {
            'fields': ('is_active',),
        }),
    )
    
    def project_type_badge(self, obj):
        colors = {
            'prod': '#2c3e50',
            'test': '#dc3545',
            'demo': '#28a745'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600;">{}</span>',
            colors.get(obj.project_type, '#6c757d'),
            obj.get_project_type_display()
        )
    project_type_badge.short_description = _('Project Type')
    
    def license_status_display(self, obj):
        """Display license status with is_active and is_blocked."""
        try:
            from app_conf.models import SecureLicense
            from app_conf.license_manager import LicenseValidator
            from app_conf.hardware_binding import HardwareFingerprint
            
            # Шукати всі ліцензії (не тільки активні), щоб показати статус блокування
            license_obj = SecureLicense.objects.order_by('-id').first()
            if not license_obj:
                return format_html('<span style="color: red; font-weight: bold;">No license found</span>')
            
            # Перевірка статусу блокування (ПЕРШОЮ, щоб мати пріоритет)
            is_blocked = getattr(license_obj, 'is_blocked', False)
            block_reason = getattr(license_obj, 'block_reason', '')
            
            if is_blocked:
                status_html = format_html(
                    '<span style="color: red; font-weight: bold;">🚫 Blocked</span>'
                )
                if block_reason:
                    status_html += format_html(
                        '<br><small style="color: #721c24;">Reason: {}</small>',
                        block_reason[:100]
                    )
                return status_html
            
            # Перевірка is_active
            if not license_obj.is_active:
                return format_html('<span style="color: orange; font-weight: bold;">⚠ Inactive</span>')
            
            # Перевірка валідності
            is_valid, error = LicenseValidator.validate_license(license_obj)
            if is_valid:
                return format_html('<span style="color: green; font-weight: bold;">✓ Active and Valid</span>')
            else:
                return format_html(
                    '<span style="color: red; font-weight: bold;">✗ Invalid: {}</span>',
                    error[:50] if error else 'Unknown error'
                )
        except Exception as e:
            return format_html('<span style="color: orange;">Error: {}</span>', str(e)[:50])
    license_status_display.short_description = _('License Status')
    
    def license_company_display(self, obj):
        """Display license company name."""
        try:
            from app_conf.models import SecureLicense
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            if not license_obj:
                return '-'
            license_data = license_obj.get_license_data()
            if license_data:
                return license_data.get('company', 'Unknown')
            return 'Unable to read license data'
        except Exception:
            return '-'
    license_company_display.short_description = _('Company')
    
    def license_expiration_display(self, obj):
        """Display license expiration date."""
        try:
            from app_conf.models import SecureLicense
            from app_conf.license_manager import LicenseValidator
            from django.utils import timezone
            
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            if not license_obj:
                return '-'
            
            license_data = license_obj.get_license_data()
            if not license_data:
                return format_html('<span style="color: red;">Unable to read license data</span>')
            
            expiration_str = license_data.get('expiration_date')
            if not expiration_str:
                return '-'
            
            from datetime import datetime
            expiration_date = datetime.strptime(expiration_str, '%Y-%m-%d').date()
            today = timezone.now().date()
            days_remaining = (expiration_date - today).days
            
            if days_remaining < 0:
                return format_html(
                    '<span style="color: red; font-weight: bold;">Expired on {}</span>',
                    expiration_str
                )
            elif days_remaining < 30:
                return format_html(
                    '<span style="color: orange; font-weight: bold;">{} ({} days remaining)</span>',
                    expiration_str, days_remaining
                )
            else:
                return format_html(
                    '<span style="color: green;">{} ({} days remaining)</span>',
                    expiration_str, days_remaining
                )
        except Exception as e:
            return format_html('<span style="color: orange;">Error: {}</span>', str(e)[:50])
    license_expiration_display.short_description = _('Expiration Date')
    
    def license_hardware_id_display(self, obj):
        """Display license Server ID (hardware_id in license data is actually Server ID)."""
        try:
            from app_conf.models import SecureLicense
            from app_conf.hardware_binding import HardwareFingerprint
            
            license_obj = SecureLicense.objects.order_by('-id').first()  # Шукати всі, не тільки активні
            if not license_obj:
                return '-'
            
            license_data = license_obj.get_license_data()
            if not license_data:
                return 'Unable to read license data'
            
            # ВАЖЛИВО: hardware_id в license_data - це Server ID (хеш від Hardware ID + HTTP_HOST)
            license_server_id = license_data.get('hardware_id', '').strip()
            # Також перевірити hardware_fingerprint в об'єкті ліцензії (теж Server ID)
            stored_server_id = (license_obj.hardware_fingerprint or '').strip()
            
            # Поточний Server ID
            current_server_id = HardwareFingerprint.get_server_id().strip()
            
            # Використовувати license_server_id якщо є, інакше stored_server_id
            license_server_id = license_server_id or stored_server_id
            
            # Використовувати поточний Server ID для відображення та копіювання
            display_server_id = current_server_id
            
            match_status = license_server_id == current_server_id
            status_color = 'green' if match_status else 'red'
            status_text = 'matches current Server ID' if match_status else f'mismatch! License Server ID: {license_server_id[:16] if license_server_id else "N/A"}...'
            
            # Унікальний ID для кнопки
            button_id = f'server_id_copy_btn_{id(obj)}'
            
            return format_html(
                '''
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="color: {};">{}... ({})</span>
                    <button type="button" id="{}" onclick="copyServerIdToClipboard('{}', '{}')" 
                            style="padding: 4px 8px; background: #417690; color: white; border: none; 
                                   border-radius: 3px; cursor: pointer; font-size: 11px;"
                            title="Copy Server ID to clipboard">
                        📋 Copy
                    </button>
                </div>
                <script>
                if (typeof copyServerIdToClipboard === 'undefined') {{
                    function copyServerIdToClipboard(serverId, buttonId) {{
                        navigator.clipboard.writeText(serverId).then(function() {{
                            var btn = document.getElementById(buttonId);
                            if (btn) {{
                                var originalText = btn.innerHTML;
                                btn.innerHTML = '✓ Copied!';
                                btn.style.background = '#28a745';
                                setTimeout(function() {{
                                    btn.innerHTML = originalText;
                                    btn.style.background = '#417690';
                                }}, 2000);
                            }}
                        }}, function(err) {{
                            // Fallback for older browsers
                            var textArea = document.createElement('textarea');
                            textArea.value = serverId;
                            textArea.style.position = 'fixed';
                            textArea.style.left = '-999999px';
                            document.body.appendChild(textArea);
                            textArea.select();
                            try {{
                                document.execCommand('copy');
                                var btn = document.getElementById(buttonId);
                                if (btn) {{
                                    var originalText = btn.innerHTML;
                                    btn.innerHTML = '✓ Copied!';
                                    btn.style.background = '#28a745';
                                    setTimeout(function() {{
                                        btn.innerHTML = originalText;
                                        btn.style.background = '#417690';
                                    }}, 2000);
                                }}
                            }} catch (err) {{
                                alert('Failed to copy: ' + err);
                            }}
                            document.body.removeChild(textArea);
                        }});
                    }}
                }}
                </script>
                ''',
                status_color,
                display_server_id[:16] if display_server_id else 'N/A',
                status_text,
                button_id,
                display_server_id,
                button_id
            )
        except Exception as e:
            return format_html('<span style="color: orange;">Error: {}</span>', str(e)[:50])
    license_hardware_id_display.short_description = _('Server ID')
    
    def license_max_users_display(self, obj):
        """Display license max users."""
        try:
            from app_conf.models import SecureLicense
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            if not license_obj:
                return '-'
            license_data = license_obj.get_license_data()
            if license_data:
                max_users = license_data.get('max_users', 0)
                return format_html('<span style="font-weight: bold;">{}</span>', max_users)
            return '-'
        except Exception:
            return '-'
    license_max_users_display.short_description = _('Max Users')
    
    # Module display disabled
    # def license_modules_display(self, obj):
    #     """Display enabled license modules."""
    #     try:
    #         from app_conf.models import SecureLicense
    #         from app_conf.license_manager import ModuleAccessController
    #         
    #         license_obj = SecureLicense.objects.filter(is_active=True).first()
    #         if not license_obj:
    #             return '-'
    #         
    #         enabled_modules = ModuleAccessController.get_enabled_modules(license_obj)
    #         if not enabled_modules:
    #             return format_html('<span style="color: #999;">No modules enabled</span>')
    #         
    #         # enabled_modules - це список словників з ключами 'key', 'name', 'name_uk', 'app', 'description'
    #         # Використовуємо 'name' або 'name_uk' для відображення
    #         module_names_list = []
    #         for module in enabled_modules:
    #             if isinstance(module, dict):
    #                 # Використовуємо 'name_uk' якщо є, інакше 'name'
    #                 module_name = module.get('name_uk') or module.get('name') or module.get('key', 'Unknown')
    #                 module_names_list.append(module_name)
    #             else:
    #                 # Якщо це не словник, використовуємо як є
    #                 module_names_list.append(str(module))
    #         
    #         if module_names_list:
    #             return format_html(
    #                 '<span style="color: green;">{}</span>',
    #                 ', '.join(module_names_list)
    #             )
    #         return format_html('<span style="color: #999;">No modules enabled</span>')
    #     except Exception as e:
    #         return format_html('<span style="color: orange;">Error: {}</span>', str(e)[:50])
    # license_modules_display.short_description = _('Enabled Modules')
    
    def license_activated_at_display(self, obj):
        """Display license activation date."""
        try:
            from app_conf.models import SecureLicense
            
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            if not license_obj:
                return '-'
            
            # Використовуємо created_at як дату активації, або перший heartbeat
            activated_at = license_obj.created_at
            first_heartbeat = license_obj.heartbeats.order_by('timestamp').first()
            if first_heartbeat and first_heartbeat.timestamp < activated_at:
                activated_at = first_heartbeat.timestamp
            
            return format_html(
                '<span style="color: #417690; font-weight: 500;">{}</span>',
                activated_at.strftime('%Y-%m-%d %H:%M:%S') if activated_at else '-'
            )
        except Exception as e:
            return format_html('<span style="color: orange;">Error: {}</span>', str(e)[:50])
    license_activated_at_display.short_description = _('Activated At')
    
    def license_last_heartbeat_display(self, obj):
        """Display last heartbeat time."""
        try:
            from app_conf.models import SecureLicense
            from django.utils import timezone
            
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            if not license_obj:
                return '-'
            
            last_heartbeat = license_obj.heartbeats.order_by('-timestamp').first()
            if not last_heartbeat:
                return format_html('<span style="color: #999;">Never</span>')
            
            delta = timezone.now() - last_heartbeat.timestamp
            if delta.total_seconds() < 3600:
                minutes = int(delta.total_seconds() / 60)
                color = 'green' if minutes < 15 else 'orange'
                return format_html(
                    '<span style="color: {};">{} ({} min ago)</span>',
                    color,
                    last_heartbeat.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    minutes
                )
            elif delta.total_seconds() < 86400:
                hours = int(delta.total_seconds() / 3600)
                return format_html(
                    '<span style="color: orange;">{} ({} hours ago)</span>',
                    last_heartbeat.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    hours
                )
            else:
                days = int(delta.total_seconds() / 86400)
                return format_html(
                    '<span style="color: red;">{} ({} days ago)</span>',
                    last_heartbeat.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    days
                )
        except Exception as e:
            return format_html('<span style="color: orange;">Error: {}</span>', str(e)[:50])
    license_last_heartbeat_display.short_description = _('Last Heartbeat')
    
    def license_last_validated_display(self, obj):
        """Display last validation time."""
        try:
            from app_conf.models import SecureLicense
            from django.utils import timezone
            
            license_obj = SecureLicense.objects.filter(is_active=True).first()
            if not license_obj:
                return '-'
            
            if license_obj.last_validated:
                delta = timezone.now() - license_obj.last_validated
                if delta.total_seconds() < 3600:
                    minutes = int(delta.total_seconds() / 60)
                    return format_html(
                        '<span style="color: green;">{} ({} min ago)</span>',
                        license_obj.last_validated.strftime('%Y-%m-%d %H:%M:%S'),
                        minutes
                    )
                elif delta.total_seconds() < 86400:
                    hours = int(delta.total_seconds() / 3600)
                    return format_html(
                        '<span style="color: orange;">{} ({} hours ago)</span>',
                        license_obj.last_validated.strftime('%Y-%m-%d %H:%M:%S'),
                        hours
                    )
                else:
                    days = int(delta.total_seconds() / 86400)
                    return format_html(
                        '<span style="color: red;">{} ({} days ago)</span>',
                        license_obj.last_validated.strftime('%Y-%m-%d %H:%M:%S'),
                        days
                    )
            return format_html('<span style="color: #999;">Never validated</span>')
        except Exception as e:
            return format_html('<span style="color: orange;">Error: {}</span>', str(e)[:50])
    license_last_validated_display.short_description = _('Last Validated')
    
    def license_send_heartbeat_display(self, obj):
        """Display button to manually send heartbeat."""
        from django.urls import reverse
        return format_html(
            '''
            <div>
                <button type="button" id="send_heartbeat_btn" class="send-heartbeat-btn"
                        onclick="sendHeartbeat()"
                        style="padding: 8px 15px; background: #417690; color: white; border: none;
                               border-radius: 3px; cursor: pointer; font-size: 12px;">
                    📡 Send Heartbeat
                </button>
                <div id="heartbeat_result" style="margin-top: 10px;"></div>
            </div>
            <script>
            function sendHeartbeat() {{
                var btn = document.getElementById('send_heartbeat_btn');
                var result = document.getElementById('heartbeat_result');
                var originalText = btn.innerHTML;
                
                btn.disabled = true;
                btn.innerHTML = '⏳ Sending...';
                result.innerHTML = '<span style="color: #666;">Sending heartbeat...</span>';
                
                // Get CSRF token from form or cookies
                function getCSRFToken() {{
                    // Try to get from form first (Django admin way)
                    var csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
                    if (csrfInput) {{
                        return csrfInput.value;
                    }}
                    // Fallback to cookies
                    function getCookie(name) {{
                        var cookieValue = null;
                        if (document.cookie && document.cookie !== '') {{
                            var cookies = document.cookie.split(';');
                            for (var i = 0; i < cookies.length; i++) {{
                                var cookie = cookies[i].trim();
                                if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                                    break;
                                }}
                            }}
                        }}
                        return cookieValue;
                    }}
                    return getCookie('csrftoken');
                }}
                
                var csrftoken = getCSRFToken();
                
                if (!csrftoken) {{
                    result.innerHTML = '<span style="color: red; font-weight: bold;">✗ Error: CSRF token not found</span>';
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                    return;
                }}
                
                fetch('{}', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrftoken
                    }},
                    credentials: 'same-origin',
                    body: JSON.stringify({{}})
                }})
                .then(response => {{
                    if (!response.ok) {{
                        return response.text().then(text => {{
                            throw new Error('HTTP ' + response.status + ': ' + text.substring(0, 100));
                        }});
                    }}
                    return response.json();
                }})
                .then(data => {{
                    if (data.success) {{
                        // Check if license is blocked
                        if (data.message && data.message.indexOf('blocked') !== -1) {{
                            result.innerHTML = '<span style="color: red; font-weight: bold;">✗ ' + data.message + '</span>';
                        }} else {{
                            result.innerHTML = '<span style="color: green; font-weight: bold;">✓ ' + data.message + '</span>';
                        }}
                        // Reload page after 2 seconds to show updated status and heartbeat time
                        setTimeout(function() {{
                            window.location.reload();
                        }}, 2000);
                    }} else {{
                        result.innerHTML = '<span style="color: red; font-weight: bold;">✗ ' + data.message + '</span>';
                        // Also reload on error to show updated status
                        setTimeout(function() {{
                            window.location.reload();
                        }}, 2000);
                    }}
                }})
                .catch(error => {{
                    result.innerHTML = '<span style="color: red; font-weight: bold;">✗ Error: ' + error.message + '</span>';
                }})
                .finally(() => {{
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                }});
            }}
            </script>
            ''',
            reverse('admin:app_conf_sitesettings_send_heartbeat')
        )
    license_send_heartbeat_display.short_description = _('Send Heartbeat')
    
    readonly_fields = ('created_at', 'updated_at', 'license_status_display', 'license_company_display', 
                       'license_expiration_display', 'license_hardware_id_display', 'license_max_users_display',
                       # 'license_modules_display',  # Disabled
                       'license_activated_at_display', 'license_last_heartbeat_display',
                       'license_last_validated_display', 'license_send_heartbeat_display')
    
    def has_add_permission(self, request):
        # Only allow one instance (singleton pattern)
        return not SiteSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of the settings
        return False
    
    def response_add(self, request, obj, post_url_continue=None):
        # Redirect to change form after adding
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:app_conf_sitesettings_change', args=[obj.pk]))
    
    def changelist_view(self, request, extra_context=None):
        # If no settings exist, create one and redirect to it
        if not SiteSettings.objects.exists():
            settings = SiteSettings.objects.create()
            from django.http import HttpResponseRedirect
            from django.urls import reverse
            return HttpResponseRedirect(reverse('admin:app_conf_sitesettings_change', args=[settings.pk]))
        return super().changelist_view(request, extra_context)
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                'send-heartbeat/',
                self.admin_site.admin_view(self.send_heartbeat_view),
                name='app_conf_sitesettings_send_heartbeat',
            ),
        ]
        return custom_urls + urls
    
    def send_heartbeat_view(self, request):
        """View to manually send heartbeat."""
        from django.http import JsonResponse
        from django.views.decorators.csrf import csrf_exempt
        from app_conf.models import SecureLicense
        from app_conf.license_server_api import LicenseServerAPI
        import logging
        
        logger = logging.getLogger(__name__)
        
        if request.method != 'POST':
            return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
        
        try:
            # Шукати всі ліцензії (не тільки активні), щоб можна було синхронізувати статус блокування
            license_obj = SecureLicense.objects.order_by('-id').first()
            if not license_obj:
                return JsonResponse({
                    'success': False,
                    'message': 'No license found'
                })
            
            logger.info(f"Manual heartbeat request for license {license_obj.id}")
            
            # Збір статистики використання
            from django.contrib.auth.models import User
            from app_conf.models import Company
            from django.utils import timezone
            usage_stats = {
                'total_users': User.objects.count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'companies': Company.objects.count(),
                'timestamp': str(timezone.now()),
            }
            
            success, response_data = LicenseServerAPI.send_heartbeat(license_obj.license_key, usage_stats)
            
            # Синхронізувати статус блокування з сервера
            update_fields = []
            error_message = ''
            if response_data:
                # Перевірити чи помилка "License not found" - це також блокування
                error_msg = response_data.get('error', '')
                if 'License not found' in error_msg or 'license not found' in error_msg.lower():
                    # Якщо ліцензія не знайдена на сервері, вважаємо її заблокованою
                    response_data['is_blocked'] = True
                    response_data['block_reason'] = 'License not found on server'
                    logger.critical(f"License not found on server - blocking license {license_obj.id}")
                
                server_is_blocked = response_data.get('is_blocked', False)
                server_block_reason = response_data.get('block_reason', '') or ''
                
                # Переконатися, що block_reason завжди є рядком (не None)
                if server_block_reason is None:
                    server_block_reason = ''
                
                # Оновити локальний статус блокування
                if license_obj.is_blocked != server_is_blocked:
                    license_obj.is_blocked = server_is_blocked
                    update_fields.append('is_blocked')
                    if server_is_blocked:
                        logger.critical(f"License blocked by server! Reason: {server_block_reason}")
                    else:
                        logger.info("License unblocked by server")
                
                if license_obj.block_reason != server_block_reason:
                    license_obj.block_reason = server_block_reason
                    update_fields.append('block_reason')
                
                # Якщо ліцензія заблокована на сервері, деактивувати локально
                if server_is_blocked:
                    if license_obj.is_active:
                        license_obj.is_active = False
                        update_fields.append('is_active')
                    error_message = f"License is blocked: {server_block_reason}" if server_block_reason else "License is blocked"
                
                # Перевірити чи сервер повернув помилку
                if response_data.get('status') == 'error':
                    error_message = response_data.get('message', 'Unknown error')
                elif not response_data.get('license_valid', True):
                    error_message = 'License is no longer valid on server'
            
            # Зберегти зміни якщо є
            if update_fields:
                license_obj.save(update_fields=update_fields)
                logger.info(f"Updated license {license_obj.id} fields: {update_fields}")
            
            # Створити запис LicenseHeartbeat для відображення в admin
            from app_conf.models import LicenseHeartbeat
            LicenseHeartbeat.objects.create(
                license=license_obj,
                response_code=200 if success and not error_message else 0,
                response_data=response_data,
                usage_stats=usage_stats,
                success=success and not error_message,
                error_message=error_message if error_message else ('' if success else 'Connection failed')
            )
            
            if success:
                logger.info(f"Heartbeat sent successfully for license {license_obj.id}")
                message = 'Heartbeat sent successfully!'
                if response_data and response_data.get('is_blocked'):
                    message = f"License is blocked: {response_data.get('block_reason', 'Blocked by server')}"
                return JsonResponse({
                    'success': True,
                    'message': message
                })
            else:
                if response_data:
                    error_msg = response_data.get('error') or response_data.get('message', 'Unknown error')
                    if isinstance(response_data, dict) and 'status' in response_data:
                        error_msg = response_data.get('message', 'License server unreachable')
                    # Якщо помилка "License not found", показуємо як блокування
                    if 'License not found' in error_msg or 'license not found' in error_msg.lower():
                        error_msg = 'License not found on server (blocked)'
                else:
                    error_msg = 'License server unreachable (connection failed)'
                logger.warning(f"Heartbeat failed for license {license_obj.id}: {error_msg}")
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                })
        except Exception as e:
            logger.error(f"Error in send_heartbeat_view: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })


@admin.register(ContactSettings)
class ContactSettingsAdmin(admin.ModelAdmin):
    list_display = ('support_email', 'contact_email', 'enable_contact_auto_reply', 'is_active', 'updated_at')
    list_filter = ('enable_contact_auto_reply', 'is_active')
    search_fields = ('support_email', 'contact_email', 'contact_phone')
    
    fieldsets = (
        (_('General Email Settings'), {
            'fields': ('support_email', 'contact_notification_users'),
            'description': _('Configure general email addresses and users for contact form notifications.'),
        }),
        (_('Inquiry Type Specific Recipients'), {
            'fields': (
                'general_notification_users',
                'support_notification_users',
                'sales_notification_users', 
                'partnership_notification_users',
                'security_notification_users',
                'feedback_notification_users',
                'other_notification_users'
            ),
            'description': _('Configure specific recipients for different inquiry types. If no specific recipients are set, general recipients will be used.'),
        }),
        (_('Auto-Reply Settings'), {
            'fields': ('enable_contact_auto_reply', 'contact_auto_reply_account', 'auto_reply_subject', 'auto_reply_body'),
            'description': _('Configure automatic reply sent to users who submit contact form. Use {name} for user name and {subject} for message subject in the body.'),
        }),
        (_('Contact Information'), {
            'fields': ('contact_address', 'contact_phone', 'contact_email', 'working_hours'),
            'description': _('Information displayed on the contact page.'),
        }),
        (_('Social Media'), {
            'fields': ('facebook_url', 'twitter_url', 'linkedin_url', 'telegram_url', 'github_url'),
            'description': _('Social media profile links.'),
        }),
        (_('General Settings'), {
            'fields': ('is_active',),
        }),
    )
    
    filter_horizontal = (
        'contact_notification_users',
        'general_notification_users',
        'support_notification_users',
        'sales_notification_users',
        'partnership_notification_users', 
        'security_notification_users',
        'feedback_notification_users',
        'other_notification_users'
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        # Only allow one instance (singleton pattern)
        return not ContactSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of the settings
        return False
    
    def response_add(self, request, obj, post_url_continue=None):
        # Redirect to change form after adding
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(reverse('admin:app_conf_contactsettings_change', args=[obj.pk]))
    
    def changelist_view(self, request, extra_context=None):
        # If no settings exist, create one and redirect to it
        if not ContactSettings.objects.exists():
            settings = ContactSettings.objects.create()
            from django.http import HttpResponseRedirect
            from django.urls import reverse
            return HttpResponseRedirect(reverse('admin:app_conf_contactsettings_change', args=[settings.pk]))
        return super().changelist_view(request, extra_context)


@admin.register(AccessOption)
class AccessOptionAdmin(admin.ModelAdmin):
    list_display = ('group', 'has_access', 'description_short')
    list_filter = ('has_access', 'group')
    search_fields = ('group__name', 'description')
    list_editable = ('has_access',)
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else obj.description
    description_short.short_description = _("Description")


@admin.register(MailServer)
class MailServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'smtp_host', 'smtp_port', 'use_tls', 'use_ssl', 'imap_host', 'imap_port')
    list_filter = ('use_tls', 'use_ssl', 'imap_use_ssl')
    search_fields = ('name', 'smtp_host', 'imap_host')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name',)
        }),
        (_('SMTP Settings'), {
            'fields': ('smtp_host', 'smtp_port', 'use_tls', 'use_ssl'),
            'description': _('Configure SMTP server settings for sending emails')
        }),
        (_('IMAP Settings'), {
            'fields': ('imap_host', 'imap_port', 'imap_use_ssl'),
            'description': _('Configure IMAP server settings for receiving emails (optional)'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MailAccount)
class MailAccountAdmin(admin.ModelAdmin):
    list_display = ('username', 'server', 'is_active', 'show_password')
    list_filter = ('is_active', 'server', 'show_password')
    search_fields = ('username', 'server__name')
    
    fieldsets = (
        (_('Account Information'), {
            'fields': ('username', 'password', 'server', 'user')
        }),
        (_('Settings'), {
            'fields': ('is_active', 'show_password'),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('server', 'user')
    
    def test_email_action(self, request, queryset):
        """Test email sending for selected accounts"""
        from .email_utils import send_test_email
        
        success_count = 0
        for account in queryset:
            if account.is_active:
                success, message = send_test_email(account)
                if success:
                    success_count += 1
                    self.message_user(request, f"Test email sent successfully for {account.username}")
                else:
                    self.message_user(request, f"Failed to send test email for {account.username}: {message}", level='ERROR')
            else:
                self.message_user(request, f"Skipped inactive account {account.username}", level='WARNING')
        
        if success_count > 0:
            self.message_user(request, f"Successfully sent {success_count} test emails")
    
    test_email_action.short_description = _("Send test email")
    actions = [test_email_action]


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'from_email', 'to_email', 'created_at', 'email_type', 'is_read')
    list_filter = ('email_type', 'is_read', 'account', 'created_at')
    search_fields = ('subject', 'from_email', 'to_email', 'body')
    readonly_fields = ('message_id', 'date', 'created_at')
    # Removed date_hierarchy to avoid timezone issues
    
    fieldsets = (
        (_('Email Information'), {
            'fields': ('account', 'message_id', 'from_email', 'to_email', 'subject', 'date', 'email_type')
        }),
        (_('Content'), {
            'fields': ('body',)
        }),
        (_('Status'), {
            'fields': ('is_read',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('account', 'account__server')
    
    def mark_as_read_action(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"Marked {queryset.count()} emails as read")
    
    def mark_as_unread_action(self, request, queryset):
        queryset.update(is_read=False)
        self.message_user(request, f"Marked {queryset.count()} emails as unread")
    
    mark_as_read_action.short_description = _("Mark as read")
    mark_as_unread_action.short_description = _("Mark as unread")
    actions = [mark_as_read_action, mark_as_unread_action]


@admin.register(KnowledgeBaseCategory)
class KnowledgeBaseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_type', 'color', 'icon', 'article_count_display', 'order', 'is_active')
    list_filter = ('category_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'slug', 'category_type', 'description')
        }),
        (_('Display Settings'), {
            'fields': ('icon', 'color', 'order')
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def article_count_display(self, obj):
        count = obj.get_article_count()
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px;">{}</span>',
            '#28a745' if count > 0 else '#6c757d',
            count
        )
    article_count_display.short_description = _('Articles')


@admin.register(KnowledgeBaseArticle)
class KnowledgeBaseArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'article_type', 'priority_badge', 'author', 
                    'is_published', 'is_featured', 'views_count', 'published_at')
    list_filter = ('is_published', 'is_featured', 'article_type', 'priority', 
                   'category', 'published_at', 'created_at')
    search_fields = ('title', 'summary', 'content', 'tags')
    list_editable = ('is_published', 'is_featured')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'slug', 'category', 'article_type', 'priority')
        }),
        (_('Content'), {
            'fields': ('summary', 'content'),
            'classes': ('wide',)
        }),
        (_('Tags & Keywords'), {
            'fields': ('tags',),
            'classes': ('collapse',)
        }),
        (_('SEO Settings'), {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        (_('Publishing'), {
            'fields': ('author', 'is_published', 'is_featured', 'published_at')
        }),
        (_('Statistics'), {
            'fields': ('views_count',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('views_count', 'created_at', 'updated_at')
    
    def priority_badge(self, obj):
        colors = {
            'critical': '#dc3545',
            'high': '#fd7e14',
            'medium': '#ffc107',
            'low': '#28a745',
            'info': '#17a2b8'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.priority, '#6c757d'),
            obj.get_priority_display()
        )
    priority_badge.short_description = _('Priority')
    
    def save_model(self, request, obj, form, change):
        if not obj.author:
            obj.author = request.user
        super().save_model(request, obj, form, change)
    
    def publish_articles(self, request, queryset):
        queryset.update(is_published=True)
        self.message_user(request, f"Published {queryset.count()} articles")
    
    def unpublish_articles(self, request, queryset):
        queryset.update(is_published=False)
        self.message_user(request, f"Unpublished {queryset.count()} articles")
    
    publish_articles.short_description = _("Publish selected articles")
    unpublish_articles.short_description = _("Unpublish selected articles")
    actions = [publish_articles, unpublish_articles]
    
    class Media:
        css = {
            'all': ('admin/css/knowledge_base.css',)
        }
        js = ('admin/js/knowledge_base.js',)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject_type_badge', 'subject_short', 'status_badge', 
                    'is_read', 'created_at', 'assigned_to')
    list_filter = ('status', 'subject_type', 'is_read', 'created_at')
    search_fields = ('name', 'email', 'company', 'subject', 'message')
    list_editable = ('is_read', 'assigned_to')
    readonly_fields = ('name', 'email', 'phone', 'company', 'subject_type', 'subject', 
                      'message', 'ip_address', 'user_agent', 'created_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Contact Information'), {
            'fields': ('name', 'email', 'phone', 'company')
        }),
        (_('Message Details'), {
            'fields': ('subject_type', 'subject', 'message'),
            'classes': ('wide',)
        }),
        (_('Status & Assignment'), {
            'fields': ('status', 'is_read', 'assigned_to', 'responded_at', 'closed_at')
        }),
        (_('Metadata'), {
            'fields': ('ip_address', 'user_agent', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subject_short(self, obj):
        return obj.subject[:50] + '...' if len(obj.subject) > 50 else obj.subject
    subject_short.short_description = _('Subject')
    
    def subject_type_badge(self, obj):
        colors = {
            'general': '#6c757d',
            'support': '#17a2b8',
            'sales': '#28a745',
            'partnership': '#ffc107',
            'security': '#dc3545',
            'feedback': '#007bff',
            'other': '#6c757d'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 5px; font-size: 0.85rem;">{}</span>',
            colors.get(obj.subject_type, '#6c757d'),
            obj.get_subject_type_display()
        )
    subject_type_badge.short_description = _('Type')
    
    def status_badge(self, obj):
        colors = {
            'new': '#dc3545',
            'in_progress': '#ffc107',
            'responded': '#17a2b8',
            'closed': '#28a745'
        }
        icons = {
            'new': '✉️',
            'in_progress': '⏳',
            'responded': '✅',
            'closed': '🔒'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 5px; font-size: 0.85rem;">{} {}</span>',
            colors.get(obj.status, '#6c757d'),
            icons.get(obj.status, ''),
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def mark_as_read(self, request, queryset):
        count = queryset.update(is_read=True)
        self.message_user(request, f"Marked {count} messages as read")
    
    def mark_as_unread(self, request, queryset):
        count = queryset.update(is_read=False)
        self.message_user(request, f"Marked {count} messages as unread")
    
    def mark_as_responded(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(status='new').update(status='responded', responded_at=timezone.now())
        self.message_user(request, f"Marked {count} messages as responded")
    
    def mark_as_closed(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(status='closed', closed_at=timezone.now())
        self.message_user(request, f"Closed {count} messages")
    
    mark_as_read.short_description = _("Mark as read")
    mark_as_unread.short_description = _("Mark as unread")
    mark_as_responded.short_description = _("Mark as responded")
    mark_as_closed.short_description = _("Close messages")
    
    actions = [mark_as_read, mark_as_unread, mark_as_responded, mark_as_closed]
    
    def has_add_permission(self, request):
        # Contact messages are created through the contact form only
        return False


@admin.register(Company)
class CompanyConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'company_types_display', 'countries_display')
    list_filter = ('group', 'company_types', 'countries')
    search_fields = ('name', 'group__name')
    filter_horizontal = ('company_types', 'countries')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'group')
        }),
        (_('Company Classification'), {
            'fields': ('company_types',),
            'description': _('Select one or more company types that describe this company')
        }),
        (_('Geography'), {
            'fields': ('countries',),
            'description': _('Select countries where this company operates')
        }),
    )
    
    def company_types_display(self, obj):
        """Display company types with color badges"""
        if not obj.pk:
            return '-'
        
        types = obj.company_types.all()
        if not types:
            return format_html('<em style="color: #6c757d;">{}</em>', _('No types assigned'))
        
        badges = []
        for company_type in types:
            badges.append(
                f'<span style="display: inline-block; margin: 2px; padding: 4px 8px; '
                f'background: {company_type.color}; color: white; border-radius: 3px; '
                f'font-size: 0.85rem; font-weight: 500;">'
                f'{company_type.name_local or company_type.name}</span>'
            )
        
        return format_html(' '.join(badges))
    
    company_types_display.short_description = _('Company Types')
    
    def countries_display(self, obj):
        """Display countries with flags"""
        if not obj.pk:
            return '-'
        
        countries = obj.countries.filter(is_active=True).order_by('display_order', 'name')
        if not countries:
            return format_html('<em style="color: #6c757d;">{}</em>', _('No countries assigned'))
        
        flags = []
        for country in countries[:5]:  # Show max 5 flags
            if country.flag_emoji:
                flags.append(
                    f'<span style="font-size: 1.2rem; margin: 0 2px;" title="{country.name}">'
                    f'{country.flag_emoji}</span>'
                )
        
        result = ''.join(flags)
        if countries.count() > 5:
            result += f' <span style="color: #6c757d; font-size: 0.85rem;">+{countries.count() - 5}</span>'
        
        return format_html(result)
    
    countries_display.short_description = _('Countries')


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('flag_display', 'name', 'name_local', 'code', 'color_display', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'name_local', 'code')
    ordering = ('display_order', 'name')
    list_editable = ('display_order', 'is_active')
    readonly_fields = ('created_date', 'updated_date')

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'name_local', 'code')
        }),
        (_('Display'), {
            'fields': ('flag_emoji', 'color', 'display_order')
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Audit'), {
            'fields': ('created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )

    def flag_display(self, obj):
        if obj.flag_emoji:
            return format_html('<span style="font-size: 1.5rem;">{}</span>', obj.flag_emoji)
        return '-'
    flag_display.short_description = _('Flag')

    def color_display(self, obj):
        return format_html(
            '<span style="display: inline-block; width: 30px; height: 15px; background-color: {}; border: 1px solid #ccc;"></span> {}',
            obj.color,
            obj.color
        )
    color_display.short_description = _('Color')


class CompanyTypeTranslationInline(admin.TabularInline):
    model = CompanyTypeTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    verbose_name = _('Company Type Translation')
    verbose_name_plural = _('Company Type Translations')
    autocomplete_fields = ['country']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(CompanyType)
class CompanyTypeConfigAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'code', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    list_editable = ('name', 'display_order', 'is_active')
    ordering = ('display_order', 'name')
    actions = ['activate_types', 'deactivate_types']
    list_per_page = 50
    exclude = ('name_local',)
    inlines = [CompanyTypeTranslationInline]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code')
        }),
        (_('Display'), {
            'fields': ('color', 'display_order')
        }),
        (_('Details'), {
            'fields': ('description',),
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
            'background-color: {}; border: 1px solid #ddd; border-radius: 3px; '
            'vertical-align: middle; margin-right: 5px;"></span> {}',
            obj.color,
            obj.color
        )
    color_badge.short_description = _('Color')
    
    def activate_types(self, request, queryset):
        """Activate selected company types"""
        updated = queryset.update(is_active=True)
        self.message_user(request, _(f'{updated} company type(s) activated successfully'))
    activate_types.short_description = _('Activate selected company types')
    
    def deactivate_types(self, request, queryset):
        """Deactivate selected company types"""
        updated = queryset.update(is_active=False)
        self.message_user(request, _(f'{updated} company type(s) deactivated successfully'))
    deactivate_types.short_description = _('Deactivate selected company types')

