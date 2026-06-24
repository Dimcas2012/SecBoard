from django.contrib import admin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField
from .models import (
    AccessRequest, AccessRequestAttachment, AccessRequestApprover, AccessRequestApproverStatusHistory,
    SystemAccess, AccessRoles, AccessRight, AccessFunctionIS, AccessISAM,
    ApiCredential, ApiSyncStatus, ApiUser, ApiUserRole, ApiUserMerchant,
    ApiUserRoleMapping, ApiUserStatus, ApiUserPermissionHistory,
    ApiUserLoginHistory, ApiUserMerchantLink, ScheduledSync, AccessObjectIS,
    EmailNotificationHistory, EmailNotificationConfig, ThirdPartyUser, ThirdPartyOrganization,
    AccessRequestSequence, AccessJustificationTemplate, AccessJustificationTemplateTranslation,
    AccessRecordsGuide, AccessRecordsGuideTranslation,
    AccessConfigIsGuide, AccessConfigIsGuideTranslation,
    AccessMatrixGuide, AccessMatrixGuideTranslation,
    UserAccessRequestGuide, UserAccessRequestGuideTranslation,
    ManageAccessRequestsGuide, ManageAccessRequestsGuideTranslation,
    AccessNotificationGuide, AccessNotificationGuideTranslation,
)

@admin.register(ThirdPartyOrganization)
class ThirdPartyOrganizationAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'name',
        'contact_email',
        'contact_phone',
        'users_count',
        'is_active',
        'created_at'
    ]
    list_filter = [
        'is_active',
        'created_at',
        'created_by'
    ]
    search_fields = [
        'name',
        'description',
        'contact_email',
        'contact_phone',
        'website',
        'address'
    ]
    readonly_fields = [
        'created_at',
        'modified_at',
        'users_count'
    ]
    fieldsets = (
        (_('Organization Information'), {
            'fields': (
                'name',
                'description'
            )
        }),
        (_('Contact Information'), {
            'fields': (
                'contact_email',
                'contact_phone',
                'website',
                'address'
            )
        }),
        (_('Status'), {
            'fields': (
                'is_active',
            )
        }),
        (_('Statistics'), {
            'fields': (
                'users_count',
            ),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': (
                'created_at',
                'modified_at',
                'created_by'
            ),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Якщо це новий об'єкт
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ThirdPartyUser)
class ThirdPartyUserAdmin(admin.ModelAdmin):
    list_display = [
        'full_name',
        'email',
        'organization',
        'phone',
        'is_active',
        'access_requests_count',
        'created_at',
        'created_by',
        'edit_button'
    ]
    list_filter = [
        'is_active',
        'organization',
        'created_at',
        'created_by'
    ]
    search_fields = [
        'first_name',
        'last_name',
        'email',
        'organization__name',
        'organization_name',
        'phone'
    ]
    readonly_fields = [
        'created_at',
        'modified_at'
    ]
    fieldsets = (
        (_('Personal Information'), {
            'fields': (
                'first_name',
                'last_name',
                'email',
                'phone'
            )
        }),
        (_('Organization Information'), {
            'fields': (
                'organization',
                'organization_name',
                'description'
            )
        }),
        (_('Status'), {
            'fields': (
                'is_active',
            )
        }),
        (_('Timestamps'), {
            'fields': (
                'created_at',
                'modified_at',
                'created_by'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = _('Full Name')
    
    def access_requests_count(self, obj):
        """Show number of access requests for this user"""
        count = obj.access_requests.count()
        if count > 0:
            return format_html(
                '<span style="color: #417690; font-weight: bold;">{}</span>',
                count
            )
        return '0'
    access_requests_count.short_description = _('Access Requests')
    
    def edit_button(self, obj):
        """Custom edit button for Third Party Users"""
        if obj.pk:
            url = f'/secboard_admin/app_access/thirdpartyuser/{obj.pk}/change/'
            return format_html(
                '<a class="button" href="{}">{}</a>',
                url,
                _('Edit')
            )
        return '-'
    edit_button.short_description = _('Actions')
    edit_button.allow_tags = True
    
    def save_model(self, request, obj, form, change):
        if not change:  # if creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['activate_users', 'deactivate_users']
    
    def activate_users(self, request, queryset):
        """Activate selected third party users"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            _('Successfully activated {} third party users.').format(updated)
        )
    activate_users.short_description = _('Activate selected third party users')
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected third party users"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            _('Successfully deactivated {} third party users.').format(updated)
        )
    deactivate_users.short_description = _('Deactivate selected third party users')
    
    def get_queryset(self, request):
        """Optimize queryset with select_related for better performance"""
        return super().get_queryset(request).select_related('organization', 'created_by')
    
    def get_readonly_fields(self, request, obj=None):
        """Make created_by readonly when editing existing objects"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.pk:  # If editing existing object
            readonly_fields.append('created_by')
        return readonly_fields

@admin.register(AccessJustificationTemplate)
class AccessJustificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'translations_count', 'sort_order', 'is_active', 'updated_at')
    list_filter = ('company', 'is_active',)
    search_fields = ('name', 'content', 'company__name')
    ordering = ('sort_order', 'name')
    list_editable = ('sort_order', 'is_active')
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('company', 'name'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Template Text'), {
            'fields': ('content',),
            'description': _('Default: English (En). For other languages use Translations inline below.'),
        }),
    )

    class AccessJustificationTemplateTranslationInline(admin.TabularInline):
        model = AccessJustificationTemplateTranslation
        extra = 1
        fields = ('country', 'name_local', 'content')
        autocomplete_fields = ['country']

        def formfield_for_foreignkey(self, db_field, request, **kwargs):
            if db_field.name == 'country':
                kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
            return super().formfield_for_foreignkey(db_field, request, **kwargs)

        class Media:
            js = ('admin/js/access_justification_translation_helper.js',)
            css = {
                'all': ('admin/css/translation_helper.css',)
            }

    inlines = [AccessJustificationTemplateTranslationInline]

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


@admin.register(ApiCredential)
class ApiCredentialAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'company', 'information_system', 'environment', 'url', 'email', 'is_default', 'created_at', 'modified_at']
    list_filter = ['is_default', 'environment', 'user', 'company', 'information_system']
    search_fields = ['name', 'url', 'email', 'user__username', 'company__name', 'information_system__name']
    readonly_fields = ['created_at', 'modified_at']

@admin.register(ApiSyncStatus)
class ApiSyncStatusAdmin(admin.ModelAdmin):
    list_display = ['unique_id', 'credential', 'status', 'percent_complete', 'started_at', 'completed_at']
    list_filter = ['status', 'is_scheduled', 'credential']
    search_fields = ['unique_id', 'current_step']
    readonly_fields = ['started_at', 'completed_at', 'percent_complete']

@admin.register(ApiUser)
class ApiUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'user_id', 'first_name', 'last_name', 'last_login', 'created_at', 'updated_at']
    list_filter = ['sync', 'last_login']
    search_fields = ['email', 'first_name', 'last_name', 'hash']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ApiUserRole)
class ApiUserRoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'role_id', 'created_at', 'updated_at']
    search_fields = ['name', 'role_id']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ApiUserMerchant)
class ApiUserMerchantAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'updated_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ApiUserRoleMapping)
class ApiUserRoleMappingAdmin(admin.ModelAdmin):
    list_display = ['user', 'merchant', 'role', 'created_at', 'updated_at']
    list_filter = ['user', 'merchant', 'role']
    search_fields = ['user__email', 'merchant__name', 'role__name']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ApiUserStatus)
class ApiUserStatusAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'last_checked']
    list_filter = ['status']
    search_fields = ['user__email', 'raw_status']
    readonly_fields = ['last_checked']

@admin.register(ApiUserPermissionHistory)
class ApiUserPermissionHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'time', 'has_added_permissions', 'has_removed_permissions']
    list_filter = ['time', 'sync']
    search_fields = ['user__email']
    readonly_fields = ['time']

@admin.register(ApiUserLoginHistory)
class ApiUserLoginHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip', 'time']
    list_filter = ['time']
    search_fields = ['user__email', 'ip']
    readonly_fields = ['time']

@admin.register(ApiUserMerchantLink)
class ApiUserMerchantLinkAdmin(admin.ModelAdmin):
    list_display = ['user', 'merchant_name']
    search_fields = ['user__email', 'merchant_name']

@admin.register(ScheduledSync)
class ScheduledSyncAdmin(admin.ModelAdmin):
    list_display = ['name', 'credential', 'frequency', 'scheduled_time', 'last_run', 'next_run', 'is_active']
    list_filter = ['frequency', 'is_active', 'credential']
    search_fields = ['name', 'credential__name']
    readonly_fields = ['last_run', 'next_run', 'created_at', 'celery_task_id']

@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'company',
        'system',
        'requested_for',
        'requested_by',
        'third_party_users_count',
        'access_records_display',
        'created_at'
    ]
    list_filter = [
        'company',
        'system',
        'created_at',
        'third_party_users'
    ]
    search_fields = [
        'requested_for__username',
        'requested_for__first_name',
        'requested_for__last_name',
        'requested_by__username',
        'justification',
        'third_party_users__first_name',
        'third_party_users__last_name',
        'third_party_users__email'
    ]
    readonly_fields = [
        'created_at',
        'modified_at',
        'access_records_display',
        'effective_requested_for_display',
    ]
    filter_horizontal = [
        'third_party_users',
        'access_records'
    ]
    actions = ['delete_selected_with_history', 'delete_all_requests']
    fieldsets = (
        (_('Request Information'), {
            'fields': (
                'company',
                'system',
                'effective_requested_for_display',
                'requested_for',
                'requested_by',
                'access_records_display',
                'access_records'
            ),
            'description': _(
                'For third-party grants, Requested for is often the submitter (technical FK). '
                'Effective requested for shows who actually receives access.'
            ),
        }),
        (_('Access Details'), {
            'fields': (
                'start_date',
                'end_date',
                'justification',
                'requirements',
                'notes'
            )
        }),
        (_('Third Party Information'), {
            'fields': (
                'third_party_users',
                'third_party_first_name',
                'third_party_last_name',
                'third_party_email',
                'third_party_phone',
                'third_party_organization',
                'third_party_description'
            ),
            'classes': ('collapse',)
        }),

        (_('Timestamps'), {
            'fields': (
                'created_at',
                'modified_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def third_party_users_count(self, obj):
        return obj.third_party_users.count()
    third_party_users_count.short_description = _('Third Party Users Count')

    def effective_requested_for_display(self, obj):
        from app_access.access_request_view import get_effective_requested_for_summary
        return get_effective_requested_for_summary(obj) or '—'
    effective_requested_for_display.short_description = _('Effective requested for (UI)')
    
    def access_records_display(self, obj):
        """Показує Access Records з детальною інформацією"""
        records = obj.access_records.all()
        if not records:
            return _('No access records')
        
        display_list = []
        for record in records:
            display_list.append(record.get_display_name())
        
        return format_html('<br>'.join(display_list))
    access_records_display.short_description = _('Access Records')
    
    def delete_selected_with_history(self, request, queryset):
        """Видаляє обрані запити разом з усією історією"""
        from django.db import transaction
        
        deleted_count = 0
        related_deleted = {
            'attachments': 0,
            'approvers': 0,
            'approver_history': 0,
            'email_notifications': 0,
            'access_records': 0
        }
        
        with transaction.atomic():
            for access_request in queryset:
                # Видаляємо пов'язані записи
                related_deleted['attachments'] += access_request.attachments.count()
                access_request.attachments.all().delete()
                
                related_deleted['approvers'] += access_request.approvers.count()
                access_request.approvers.all().delete()
                
                # Видаляємо історію затверджувачів
                from .models import AccessRequestApproverStatusHistory
                approver_history = AccessRequestApproverStatusHistory.objects.filter(
                    request_approver__access_request=access_request
                )
                related_deleted['approver_history'] += approver_history.count()
                approver_history.delete()
                
                # Видаляємо email сповіщення
                from .models import EmailNotificationHistory
                email_notifications = EmailNotificationHistory.objects.filter(
                    access_request=access_request
                )
                related_deleted['email_notifications'] += email_notifications.count()
                email_notifications.delete()
                
                # Видаляємо AccessRecord записи
                related_deleted['access_records'] += access_request.access_records.count()
                access_request.access_records.all().delete()
                
                # Видаляємо сам запит
                access_request.delete()
                deleted_count += 1
        
        # Формуємо повідомлення
        message_parts = [f"Видалено {deleted_count} запитів доступу"]
        if related_deleted['attachments'] > 0:
            message_parts.append(f"{related_deleted['attachments']} вкладень")
        if related_deleted['approvers'] > 0:
            message_parts.append(f"{related_deleted['approvers']} затверджувачів")
        if related_deleted['approver_history'] > 0:
            message_parts.append(f"{related_deleted['approver_history']} записів історії затверджувачів")
        if related_deleted['email_notifications'] > 0:
            message_parts.append(f"{related_deleted['email_notifications']} email сповіщень")
        if related_deleted['access_records'] > 0:
            message_parts.append(f"{related_deleted['access_records']} записів доступу (історія Grant/Revoke)")
        
        self.message_user(
            request,
            f"{'. '.join(message_parts)}."
        )
    delete_selected_with_history.short_description = _('Delete selected access requests with all history')
    
    def delete_all_requests(self, request, queryset):
        """Видаляє всі запити доступу (попередження)"""
        from django.contrib import messages
        
        # Показуємо попередження
        messages.warning(
            request,
            _('This action will delete ALL access requests in the system. This action cannot be undone!')
        )
        
        # Підраховуємо кількість
        total_requests = AccessRequest.objects.count()
        total_attachments = AccessRequestAttachment.objects.count()
        total_approvers = AccessRequestApprover.objects.count()
        total_approver_history = AccessRequestApproverStatusHistory.objects.count()
        total_email_notifications = EmailNotificationHistory.objects.count()
        total_access_records = SystemAccess.objects.count()
        
        # Показуємо статистику
        messages.info(
            request,
            f"Total records to be deleted: {total_requests} requests, {total_attachments} attachments, "
            f"{total_approvers} approvers, {total_approver_history} approver history records, "
            f"{total_email_notifications} email notifications, {total_access_records} access records"
        )
        
        # Запитуємо підтвердження
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        
        return HttpResponseRedirect(
            reverse('admin:app_access_accessrequest_changelist') + 
            f'?action=confirm_delete_all&count={total_requests}'
        )
    delete_all_requests.short_description = _('Delete ALL access requests (DANGEROUS)')
    
    def get_actions(self, request):
        """Кастомізуємо дії"""
        actions = super().get_actions(request)
        
        # Додаємо дію для видалення всіх запитів тільки для суперкористувачів
        if request.user.is_superuser:
            actions['delete_all_requests'] = self.get_action('delete_all_requests')
        
        return actions
    
    def changelist_view(self, request, extra_context=None):
        """Додаємо кастомні кнопки в changelist"""
        extra_context = extra_context or {}
        
        # Додаємо кнопки тільки для суперкористувачів
        if request.user.is_superuser:
            from django.urls import reverse
            extra_context['show_admin_buttons'] = True
            extra_context['confirm_delete_all_url'] = reverse('admin_confirm_delete_all_requests')
            extra_context['delete_by_filter_url'] = reverse('admin_delete_requests_by_filter')
        
        return super().changelist_view(request, extra_context)


@admin.register(AccessRequestAttachment)
class AccessRequestAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        'original_filename',
        'access_request',
        'file_size_display',
        'content_type',
        'uploaded_by',
        'uploaded_at'
    ]
    list_filter = [
        'content_type',
        'uploaded_at',
        'uploaded_by'
    ]
    search_fields = [
        'original_filename',
        'access_request__id',
        'uploaded_by__username'
    ]
    readonly_fields = [
        'file_size',
        'uploaded_at'
    ]

    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = _('File Size')


@admin.register(AccessRequestApprover)
class AccessRequestApproverAdmin(admin.ModelAdmin):
    list_display = [
        'access_request',
        'cabinet_user',
        'order',
        'current_status',
        'status_changed_at',
        'status_changed_by'
    ]
    list_filter = [
        'current_status',
        'order',
        'status_changed_at'
    ]
    search_fields = [
        'access_request__id',
        'cabinet_user__user__username',
        'cabinet_user__user__first_name',
        'cabinet_user__user__last_name'
    ]
    readonly_fields = [
        'created_at',
        'status_changed_at'
    ]
    ordering = ['access_request', 'order']


@admin.register(AccessRequestApproverStatusHistory)
class AccessRequestApproverStatusHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'request_approver',
        'old_status',
        'new_status',
        'changed_at',
        'changed_by'
    ]
    list_filter = [
        'old_status',
        'new_status',
        'changed_at'
    ]
    search_fields = [
        'request_approver__access_request__id',
        'request_approver__cabinet_user__user__username',
        'changed_by__username',
        'comment'
    ]
    readonly_fields = [
        'changed_at'
    ]
    ordering = ['-changed_at']


@admin.register(SystemAccess)
class SystemAccessAdmin(admin.ModelAdmin):
    list_display = [
        'display_name',
        'status',
        'start_date',
        'end_date',
        'is_active',
        'created_by'
    ]
    
    def display_name(self, obj):
        return obj.get_display_name()
    display_name.short_description = _('Access Record')
    list_filter = [
        'is_active',
        'status',
        'asset',
        'created_at'
    ]
    filter_horizontal = [
        'roles',
        'access_users',
        'access_groups',
        'request_users',
        'request_groups'
    ]
    search_fields = [
        'asset__name',
        'access_users__username',
        'access_groups__name'
    ]
    readonly_fields = [
        'created_at',
        'created_by',
        'modified_at',
        'modified_by'
    ]


@admin.register(AccessRoles)
class AccessRolesAdmin(admin.ModelAdmin):
    list_display = [
        'get_name_display',
        'code',
        'system',
        'order',
        'is_active'
    ]
    list_editable = ['order', 'is_active']
    list_filter = ['system', 'is_active']
    search_fields = ['name', 'code']
    exclude = ('name_local',)
    filter_horizontal = ['functions']

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code', 'system', 'order'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'classes': ('collapse',),
        }),
        (_('Display'), {
            'fields': ('color',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Configuration'), {
            'fields': ('environment', 'is_object_specific', 'created_for_object', 'functions'),
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '-'
    get_name_display.short_description = _('Access Role')


@admin.register(AccessRight)
class AccessRightAdmin(admin.ModelAdmin):
    list_display = [
        'get_name_display',
        'code',
        'system',
        'order',
        'is_active'
    ]
    list_editable = ['order', 'is_active']
    list_filter = ['system', 'is_active']
    search_fields = ['name', 'code']
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code', 'system', 'order'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'classes': ('collapse',),
        }),
        (_('Display'), {
            'fields': ('color',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Configuration'), {
            'fields': ('environment', 'is_object_specific', 'created_for_object'),
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '-'
    get_name_display.short_description = _('Access Right')


@admin.register(AccessFunctionIS)
class AccessFunctionISAdmin(admin.ModelAdmin):
    list_display = [
        'get_name_display',
        'code',
        'asset',
        'parent',
        'order',
        'is_active'
    ]
    list_editable = ['order', 'is_active']
    list_filter = ['asset', 'is_active']
    search_fields = ['name', 'code']
    exclude = ('name_local',)
    filter_horizontal = ['access_rights']
    mptt_level_indent = 20

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code', 'asset', 'parent', 'order'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'classes': ('collapse',),
        }),
        (_('Display'), {
            'fields': ('color',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Configuration'), {
            'fields': ('environment', 'access_rights', 'is_object_specific', 'created_for_object'),
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '-'
    get_name_display.short_description = _('Access Function')


@admin.register(AccessISAM)
class AccessISAMAdmin(admin.ModelAdmin):
    class Media:
        css = {
            'all': ('admin/css/accessisam_changelist.css',),
        }

    list_display = [
        'group',
        'has_access_matrix',
        'can_edit_matrix',
        'has_access_records',
        'can_add_access_records',
        'can_edit_access_records',
        'can_delete_access_records',
        'has_access_config_is',
        'can_add_access_config_is',
        'can_edit_access_config_is',
        'can_delete_access_config_is',
        'has_access_manage_ar',
        'can_add_manage_ar',
        'can_edit_manage_ar',
        'can_delete_manage_ar',
        'has_access_notification_settings',
        'can_add_notification_settings',
        'can_edit_notification_settings',
        'can_delete_notification_settings',
        'has_access_api',
        'can_add_access_api',
        'can_edit_access_api',
        'can_delete_access_api',
        'companies_display'
    ]
    list_filter = [
        'has_access_matrix',
        'can_edit_matrix',
        'has_access_records',
        'can_add_access_records',
        'can_edit_access_records',
        'can_delete_access_records',
        'has_access_config_is',
        'can_add_access_config_is',
        'can_edit_access_config_is',
        'can_delete_access_config_is',
        'has_access_manage_ar',
        'can_add_manage_ar',
        'can_edit_manage_ar',
        'can_delete_manage_ar',
        'has_access_notification_settings',
        'can_add_notification_settings',
        'can_edit_notification_settings',
        'can_delete_notification_settings',
        'has_access_api',
        'can_add_access_api',
        'can_edit_access_api',
        'can_delete_access_api',
        'companies'
    ]
    search_fields = [
        'group__name',
        'description'
    ]
    filter_horizontal = ['companies']
    fieldsets = (
        (_('Group'), {
            'fields': (
                'group',
            )
        }),
        (_('Access to Matrix'), {
            'fields': (
                'has_access_matrix',
                'can_edit_matrix',
            )
        }),
        (_('Access to Records'), {
            'fields': (
                'has_access_records',
                'can_add_access_records',
                'can_edit_access_records',
                'can_delete_access_records',
            )
        }),
        (_('Access to Config IS'), {
            'fields': (
                'has_access_config_is',
                'can_add_access_config_is',
                'can_edit_access_config_is',
                'can_delete_access_config_is',
            )
        }),
        (_('Access to Manage Access Requests'), {
            'fields': (
                'has_access_manage_ar',
                'can_add_manage_ar',
                'can_edit_manage_ar',
                'can_delete_manage_ar',
            )
        }),
        (_('Access to Notification Settings'), {
            'fields': (
                'has_access_notification_settings',
                'can_add_notification_settings',
                'can_edit_notification_settings',
                'can_delete_notification_settings',
            )
        }),
        (_('Access to API'), {
            'fields': (
                'has_access_api',
                'can_add_access_api',
                'can_edit_access_api',
                'can_delete_access_api',
            )
        }),
        (_('Companies'), {
            'fields': (
                'companies',
            )
        }),
        (_('Description'), {
            'fields': (
                'description',
            )
        })
    )

    def companies_display(self, obj):
        return ", ".join([company.name for company in obj.companies.all()[:3]]) + ("..." if obj.companies.count() > 3 else "")
    companies_display.short_description = _('Companies')


@admin.register(AccessObjectIS)
class AccessObjectISAdmin(admin.ModelAdmin):
    list_display = [
        'get_name_display',
        'code',
        'asset',
        'parent',
        'order',
        'is_active'
    ]
    list_editable = ['order', 'is_active']
    list_filter = ['asset', 'is_active']
    search_fields = ['name', 'code']
    exclude = ('name_local',)
    mptt_level_indent = 20

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code', 'asset', 'parent', 'order'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'classes': ('collapse',),
        }),
        (_('Display'), {
            'fields': ('color',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Configuration'), {
            'fields': ('environment',),
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '-'
    get_name_display.short_description = _('Access Object')


@admin.register(EmailNotificationHistory)
class EmailNotificationHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'notification_type',
        'access_request',
        'recipients_count',
        'status',
        'triggered_by',
        'created_at',
        'sent_at'
    ]
    list_filter = [
        'notification_type',
        'status',
        'created_at',
        'sent_at',
        'mail_account'
    ]
    search_fields = [
        'subject',
        'access_request__id',
        'triggered_by__username',
        'triggered_by__first_name',
        'triggered_by__last_name'
    ]
    readonly_fields = [
        'created_at',
        'sent_at',
        'recipients_display'
    ]
    fieldsets = (
        (_('Notification Details'), {
            'fields': (
                'notification_type',
                'subject',
                'status',
                'access_request',
                'triggered_by'
            )
        }),
        (_('Recipients'), {
            'fields': (
                'recipients',
                'recipients_count',
                'recipients_display'
            )
        }),
        (_('Sending Details'), {
            'fields': (
                'mail_account',
                'created_at',
                'sent_at'
            )
        }),
        (_('Error Handling'), {
            'fields': (
                'error_message',
                'retry_count',
                'max_retries'
            ),
            'classes': ('collapse',)
        }),
        (_('Additional Data'), {
            'fields': (
                'template_data',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def recipients_display(self, obj):
        return obj.recipients_display
    recipients_display.short_description = _('Recipients (Display)')
    
    def has_add_permission(self, request):
        # Заборонити ручне створення записів
        return False
    
    def has_change_permission(self, request, obj=None):
        # Дозволити тільки перегляд
        return False

@admin.register(EmailNotificationConfig)
class EmailNotificationConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'notification_type',
        'is_active',
        'priority',
        'config_summary',
        'created_by',
        'created_at'
    ]
    list_filter = [
        'notification_type',
        'is_active',
        'send_on_request_created',
        'send_on_status_changed',
        'send_on_admin_status_changed',
        'use_custom_templates',
        'companies',
        'systems',
        'created_at'
    ]
    search_fields = [
        'name',
        'additional_recipients'
    ]
    readonly_fields = [
        'created_at',
        'modified_at',
        'created_by',
        'modified_by'
    ]
    filter_horizontal = [
        'companies',
        'systems'
    ]
    
    fieldsets = (
        (_('Basic Configuration'), {
            'fields': (
                'name',
                'notification_type',
                'is_active',
                'priority'
            )
        }),
        (_('Notification Triggers'), {
            'fields': (
                'send_on_request_created',
                'send_on_status_changed',
                'send_on_admin_status_changed'
            )
        }),
        (_('Recipients Configuration'), {
            'fields': (
                'notify_owners',
                'notify_administrators',
                'notify_requested_for',
                'notify_requested_by',
                'notify_approving_persons',
                'notify_third_party',
                'include_third_party_info_in_emails',
                'additional_recipients'
            )
        }),
        (_('Template Configuration'), {
            'fields': (
                'use_custom_templates',
                'request_created_subject_template',
                'request_created_html_template',
                'request_created_text_template',
                'status_changed_subject_template',
                'status_changed_html_template',
                'status_changed_text_template'
            ),
            'classes': ('collapse',)
        }),
        (_('Filters'), {
            'fields': (
                'companies',
                'systems'
            ),
            'classes': ('collapse',)
        }),
        (_('Mail Configuration'), {
            'fields': (
                'mail_server',
                'mail_account',
            )
        }),
        (_('Metadata'), {
            'fields': (
                'created_at',
                'created_by',
                'modified_at',
                'modified_by'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def config_summary(self, obj):
        """Відображає коротке резюме конфігурації"""
        summary = []
        
        # Типи сповіщень
        notifications = []
        if obj.send_on_request_created:
            notifications.append(str(_('Created')))
        if obj.send_on_status_changed:
            notifications.append(str(_('Status')))
        if obj.send_on_admin_status_changed:
            notifications.append(str(_('Admin')))
        summary.append(str(_('Notifications: {}').format(', '.join(notifications))))
        
        # Отримувачі
        recipients = []
        if obj.notify_owners:
            recipients.append(str(_('Owners')))
        if obj.notify_administrators:
            recipients.append(str(_('Admins')))
        if obj.notify_requested_for:
            recipients.append(str(_('For')))
        if obj.notify_requested_by:
            recipients.append(str(_('By')))
        if obj.notify_approving_persons:
            recipients.append(str(_('Approvers')))
        if obj.additional_recipients:
            recipients.append(str(_('Additional')))
        summary.append(str(_('Recipients: {}').format(', '.join(recipients))))
        
        # Фільтри
        filters = []
        if obj.companies.exists():
            filters.append(str(_('Companies: {}').format(obj.companies.count())))
        if obj.systems.exists():
            filters.append(str(_('Systems: {}').format(obj.systems.count())))
        if filters:
            summary.append(str(_('Filters: {}').format(', '.join(filters))))
        else:
            summary.append(str(_('Filters: All')))
        
        return format_html('<br>'.join(summary))
    config_summary.short_description = _('Configuration Summary')
    
    def save_model(self, request, obj, form, change):
        """Зберігаємо інформацію про користувача"""
        if not change:  # Новий об'єкт
            obj.created_by = request.user
        obj.modified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AccessRequestSequence)
class AccessRequestSequenceAdmin(admin.ModelAdmin):
    list_display = [
        'sequence_id',
        'order_number',
        'grant_request',
        'access_record',
        'revoke_request',
        'sequence_status',
        'created_at',
        'revoked_at'
    ]
    list_filter = [
        'sequence_status',
        'order_number',
        'created_at',
        'revoked_at',
        'grant_request__request_type',
        'revoke_request__request_type'
    ]
    search_fields = [
        'sequence_id',
        'grant_request__id',
        'revoke_request__id',
        'access_record__asset__name'
    ]
    readonly_fields = [
        'sequence_id',
        'order_number',
        'created_at',
        'revoked_at'
    ]
    fieldsets = (
        (_('Sequence Information'), {
            'fields': (
                'sequence_id',
                'order_number',
                'sequence_status',
            )
        }),
        (_('Requests'), {
            'fields': (
                'grant_request',
                'revoke_request',
            )
        }),
        (_('Access Record'), {
            'fields': (
                'access_record',
            )
        }),
        (_('Timestamps'), {
            'fields': (
                'created_at',
                'revoked_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Заборонити ручне створення записів"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Дозволити тільки перегляд"""
        return False


class AccessRecordsGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AccessRecordsGuideTranslationInline(AccessRecordsGuideTranslationInlineMixin, admin.StackedInline):
    model = AccessRecordsGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/access_records_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(AccessRecordsGuide)
class AccessRecordsGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [AccessRecordsGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_access/accessrecordsguide/change_form.html'

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
            extra_context['access_records_guide_translate_url'] = reverse('access_records_guide_translate')
        except Exception:
            extra_context['access_records_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['access_records_guide_translate_url'] = reverse('access_records_guide_translate')
        except Exception:
            extra_context['access_records_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class AccessConfigIsGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AccessConfigIsGuideTranslationInline(AccessConfigIsGuideTranslationInlineMixin, admin.StackedInline):
    model = AccessConfigIsGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/access_config_is_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(AccessConfigIsGuide)
class AccessConfigIsGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [AccessConfigIsGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_access/accessconfigisguide/change_form.html'

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
            extra_context['access_config_is_guide_translate_url'] = reverse('access_config_is_guide_translate')
        except Exception:
            extra_context['access_config_is_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['access_config_is_guide_translate_url'] = reverse('access_config_is_guide_translate')
        except Exception:
            extra_context['access_config_is_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class AccessMatrixGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AccessMatrixGuideTranslationInline(AccessMatrixGuideTranslationInlineMixin, admin.StackedInline):
    model = AccessMatrixGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/access_matrix_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(AccessMatrixGuide)
class AccessMatrixGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [AccessMatrixGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_access/accessmatrixguide/change_form.html'

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
            extra_context['access_matrix_guide_translate_url'] = reverse('access_matrix_guide_translate')
        except Exception:
            extra_context['access_matrix_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['access_matrix_guide_translate_url'] = reverse('access_matrix_guide_translate')
        except Exception:
            extra_context['access_matrix_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class UserAccessRequestGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class UserAccessRequestGuideTranslationInline(UserAccessRequestGuideTranslationInlineMixin, admin.StackedInline):
    model = UserAccessRequestGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/user_access_request_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(UserAccessRequestGuide)
class UserAccessRequestGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [UserAccessRequestGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_access/useraccessrequestguide/change_form.html'

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
            extra_context['user_access_request_guide_translate_url'] = reverse('user_access_request_guide_translate')
        except Exception:
            extra_context['user_access_request_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['user_access_request_guide_translate_url'] = reverse('user_access_request_guide_translate')
        except Exception:
            extra_context['user_access_request_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class ManageAccessRequestsGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class ManageAccessRequestsGuideTranslationInline(ManageAccessRequestsGuideTranslationInlineMixin, admin.StackedInline):
    model = ManageAccessRequestsGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/manage_access_requests_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(ManageAccessRequestsGuide)
class ManageAccessRequestsGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [ManageAccessRequestsGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_access/manageaccessrequestsguide/change_form.html'

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
            extra_context['manage_access_requests_guide_translate_url'] = reverse('manage_access_requests_guide_translate')
        except Exception:
            extra_context['manage_access_requests_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['manage_access_requests_guide_translate_url'] = reverse('manage_access_requests_guide_translate')
        except Exception:
            extra_context['manage_access_requests_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class AccessNotificationGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AccessNotificationGuideTranslationInline(AccessNotificationGuideTranslationInlineMixin, admin.StackedInline):
    model = AccessNotificationGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/access_notification_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(AccessNotificationGuide)
class AccessNotificationGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [AccessNotificationGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_access/accessnotificationguide/change_form.html'

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
            extra_context['access_notification_guide_translate_url'] = reverse('access_notification_guide_translate')
        except Exception:
            extra_context['access_notification_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['access_notification_guide_translate_url'] = reverse('access_notification_guide_translate')
        except Exception:
            extra_context['access_notification_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)
