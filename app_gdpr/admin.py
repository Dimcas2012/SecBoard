#  SecBoard\SecBoard\app_gdpr\admin.py

from django.contrib import admin
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField
from .models import (
    DataSubject,
    ConsentRecord,
    DataProcessingActivity,
    DataProcessingActivityTranslation,
    DataBreachIncident,
    DataSubjectRequest,
    DataRetentionPolicy,
    DataRetentionPolicyTranslation,
    DPIAAssessment,
    GDPRAccess,
    GDPRGuide,
    GdprGuideContent,
    GdprGuideContentTranslation,
)


@admin.register(DataSubject)
class DataSubjectAdmin(admin.ModelAdmin):
    list_display = [
        'email',
        'first_name',
        'last_name',
        'company',
        'consent_status_badge',
        'is_anonymized',
        'last_activity_date',
        'created_date'
    ]
    list_filter = [
        'consent_status',
        'is_anonymized',
        'company',
        'created_date'
    ]
    search_fields = [
        'email',
        'first_name',
        'last_name'
    ]
    readonly_fields = [
        'created_date',
        'updated_date',
        'last_activity_date'
    ]
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'user',
                'first_name',
                'last_name',
                'email',
                'phone',
                'company'
            )
        }),
        (_('GDPR Information'), {
            'fields': (
                'consent_status',
                'data_retention_period_days',
                'deletion_scheduled_date',
                'is_anonymized'
            )
        }),
        (_('Audit'), {
            'fields': (
                'created_date',
                'updated_date',
                'last_activity_date'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def consent_status_badge(self, obj):
        colors = {
            'given': {'bg': '#d4edda', 'text': '#155724'},
            'withdrawn': {'bg': '#f8d7da', 'text': '#721c24'},
            'expired': {'bg': '#fff3cd', 'text': '#856404'},
            'pending': {'bg': '#e2e3e5', 'text': '#383d41'}
        }
        color_scheme = colors.get(obj.consent_status, {'bg': '#e2e3e5', 'text': '#383d41'})
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 10px; border-radius: 3px; font-weight: 500;">{}</span>',
            color_scheme['bg'],
            color_scheme['text'],
            obj.get_consent_status_display()
        )
    consent_status_badge.short_description = _('Consent Status')


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = [
        'data_subject',
        'consent_type',
        'is_active_badge',
        'given_date',
        'expiration_date',
        'consent_version'
    ]
    list_filter = [
        'consent_type',
        'is_active',
        'given_date',
        'consent_method'
    ]
    search_fields = [
        'data_subject__email',
        'data_subject__first_name',
        'data_subject__last_name',
        'consent_text'
    ]
    readonly_fields = [
        'given_date',
        'withdrawn_date'
    ]
    fieldsets = (
        (_('Consent Information'), {
            'fields': (
                'data_subject',
                'consent_type',
                'consent_text',
                'consent_version'
            )
        }),
        (_('Status and Dates'), {
            'fields': (
                'is_active',
                'given_date',
                'withdrawn_date',
                'expiration_date'
            )
        }),
        (_('Technical Details'), {
            'fields': (
                'ip_address',
                'user_agent',
                'consent_method'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #d4edda; color: #155724; padding: 3px 10px; border-radius: 3px; font-weight: 500;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #f8d7da; color: #721c24; padding: 3px 10px; border-radius: 3px; font-weight: 500;">Withdrawn</span>'
        )
    is_active_badge.short_description = _('Status')


class DataProcessingActivityTranslationInline(admin.TabularInline):
    model = DataProcessingActivityTranslation
    extra = 1
    fields = ('country', 'name_local', 'description', 'purpose')
    autocomplete_fields = ['country']


@admin.register(DataProcessingActivity)
class DataProcessingActivityAdmin(admin.ModelAdmin):
    list_display = [
        'get_name_display',
        'company',
        'legal_basis',
        'retention_period_days',
        'international_transfers',
        'is_active',
        'responsible_person'
    ]
    list_filter = [
        'legal_basis',
        'international_transfers',
        'is_active',
        'company',
        'created_date'
    ]
    search_fields = [
        'name',
        'description',
        'translations__name_local'
    ]
    readonly_fields = [
        'created_date',
        'updated_date'
    ]
    inlines = [DataProcessingActivityTranslationInline]
    fieldsets = (
        (_('Activity Name'), {
            'fields': ('name',),
            'description': _('Default (e.g. English). For other languages use Translations inline below.'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'description': _('Default. For other languages use Translations inline below.'),
        }),
        (_('Purpose'), {
            'fields': ('purpose',),
            'description': _('Default. For other languages use Translations inline below.'),
        }),
        (_('Data Information'), {
            'fields': (
                'data_categories',
                'data_subjects_categories'
            )
        }),
        (_('Legal Basis'), {
            'fields': (
                'legal_basis',
                'legal_basis_description'
            )
        }),
        (_('Retention'), {
            'fields': (
                'retention_period_days',
                'retention_criteria'
            )
        }),
        (_('Data Processors and Transfers'), {
            'fields': (
                'processors',
                'international_transfers',
                'transfer_safeguards'
            )
        }),
        (_('Security'), {
            'fields': (
                'security_measures',
            )
        }),
        (_('Management'), {
            'fields': (
                'company',
                'responsible_person',
                'is_active'
            )
        }),
        (_('Audit'), {
            'fields': (
                'created_date',
                'updated_date'
            ),
            'classes': ('collapse',)
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '-'
    get_name_display.short_description = _("Activity Name")


@admin.register(DataBreachIncident)
class DataBreachIncidentAdmin(admin.ModelAdmin):
    list_display = [
        'incident_number',
        'title',
        'severity_badge',
        'status_badge',
        'incident_date',
        'affected_subjects_count',
        'reported_to_authority',
        'notification_overdue'
    ]
    list_filter = [
        'severity',
        'status',
        'reported_to_authority',
        'subjects_notified',
        'company',
        'incident_date'
    ]
    search_fields = [
        'incident_number',
        'title',
        'description'
    ]
    readonly_fields = [
        'created_date',
        'updated_date',
        'notification_deadline'
    ]
    fieldsets = (
        (_('Incident Information'), {
            'fields': (
                'incident_number',
                'title',
                'description',
                'company'
            )
        }),
        (_('Dates'), {
            'fields': (
                'incident_date',
                'discovery_date',
                'notification_deadline'
            )
        }),
        (_('Impact'), {
            'fields': (
                'affected_subjects_count',
                'data_types_affected',
                'severity',
                'status'
            )
        }),
        (_('Actions Taken'), {
            'fields': (
                'immediate_actions',
                'mitigation_actions',
                'preventive_measures'
            )
        }),
        (_('Notifications'), {
            'fields': (
                'reported_to_authority',
                'authority_report_date',
                'subjects_notified',
                'subjects_notification_date'
            )
        }),
        (_('Assignment'), {
            'fields': (
                'reported_by',
                'assigned_to'
            )
        }),
        (_('Audit'), {
            'fields': (
                'created_date',
                'updated_date'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def severity_badge(self, obj):
        colors = {
            'low': {'bg': '#d4edda', 'text': '#155724'},
            'medium': {'bg': '#fff3cd', 'text': '#856404'},
            'high': {'bg': '#ffe5d0', 'text': '#8b4513'},
            'critical': {'bg': '#f8d7da', 'text': '#721c24'}
        }
        color_scheme = colors.get(obj.severity, {'bg': '#e2e3e5', 'text': '#383d41'})
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color_scheme['bg'],
            color_scheme['text'],
            obj.get_severity_display()
        )
    severity_badge.short_description = _('Severity')
    
    def status_badge(self, obj):
        colors = {
            'detected': {'bg': '#e2e3e5', 'text': '#383d41'},
            'investigating': {'bg': '#cfe2ff', 'text': '#084298'},
            'contained': {'bg': '#cff4fc', 'text': '#055160'},
            'resolved': {'bg': '#d4edda', 'text': '#155724'},
            'reported': {'bg': '#fff3cd', 'text': '#856404'}
        }
        color_scheme = colors.get(obj.status, {'bg': '#e2e3e5', 'text': '#383d41'})
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 10px; border-radius: 3px; font-weight: 500;">{}</span>',
            color_scheme['bg'],
            color_scheme['text'],
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def notification_overdue(self, obj):
        if obj.is_notification_overdue():
            return format_html(
                '<span style="background-color: #f8d7da; color: #721c24; padding: 3px 10px; border-radius: 3px; font-weight: 500;">⚠ OVERDUE</span>'
            )
        elif not obj.reported_to_authority:
            return format_html(
                '<span style="background-color: #fff3cd; color: #856404; padding: 3px 10px; border-radius: 3px; font-weight: 500;">Pending</span>'
            )
        return format_html(
            '<span style="background-color: #d4edda; color: #155724; padding: 3px 10px; border-radius: 3px; font-weight: 500;">✓ Reported</span>'
        )
    notification_overdue.short_description = _('Notification Status')


@admin.register(DataSubjectRequest)
class DataSubjectRequestAdmin(admin.ModelAdmin):
    list_display = [
        'request_number',
        'request_type',
        'data_subject',
        'status_badge',
        'request_date',
        'due_date',
        'is_overdue_badge',
        'assigned_to'
    ]
    list_filter = [
        'request_type',
        'status',
        'is_verified',
        'company',
        'request_date'
    ]
    search_fields = [
        'request_number',
        'data_subject__email',
        'data_subject__first_name',
        'data_subject__last_name',
        'request_description'
    ]
    readonly_fields = [
        'request_date',
        'created_date',
        'updated_date'
    ]
    fieldsets = (
        (_('Request Information'), {
            'fields': (
                'request_number',
                'request_type',
                'data_subject',
                'company'
            )
        }),
        (_('Request Details'), {
            'fields': (
                'request_description',
                'request_source',
                'is_verified',
                'verification_method'
            )
        }),
        (_('Dates and Deadlines'), {
            'fields': (
                'request_date',
                'due_date',
                'extended_due_date',
                'completion_date'
            )
        }),
        (_('Processing'), {
            'fields': (
                'status',
                'assigned_to'
            )
        }),
        (_('Response'), {
            'fields': (
                'response_text',
                'response_sent_date',
                'rejection_reason'
            )
        }),
        (_('Audit'), {
            'fields': (
                'created_date',
                'updated_date'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': {'bg': '#e2e3e5', 'text': '#383d41'},
            'in_progress': {'bg': '#cfe2ff', 'text': '#084298'},
            'completed': {'bg': '#d4edda', 'text': '#155724'},
            'rejected': {'bg': '#f8d7da', 'text': '#721c24'},
            'extended': {'bg': '#fff3cd', 'text': '#856404'}
        }
        color_scheme = colors.get(obj.status, {'bg': '#e2e3e5', 'text': '#383d41'})
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 10px; border-radius: 3px; font-weight: 500;">{}</span>',
            color_scheme['bg'],
            color_scheme['text'],
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def is_overdue_badge(self, obj):
        if obj.is_overdue():
            return format_html(
                '<span style="background-color: #f8d7da; color: #721c24; padding: 3px 10px; border-radius: 3px; font-weight: 500;">⚠ OVERDUE</span>'
            )
        return format_html(
            '<span style="background-color: #d4edda; color: #155724; padding: 3px 10px; border-radius: 3px; font-weight: 500;">✓ On Time</span>'
        )
    is_overdue_badge.short_description = _('Deadline Status')


class DataRetentionPolicyTranslationInline(admin.TabularInline):
    model = DataRetentionPolicyTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']


@admin.register(DataRetentionPolicy)
class DataRetentionPolicyAdmin(admin.ModelAdmin):
    list_display = [
        'get_name_display',
        'data_category',
        'retention_period_days',
        'deletion_method',
        'auto_apply',
        'is_active',
        'company'
    ]
    list_filter = [
        'deletion_method',
        'auto_apply',
        'is_active',
        'company',
        'created_date'
    ]
    search_fields = [
        'name',
        'description',
        'data_category',
        'translations__name_local'
    ]
    readonly_fields = [
        'created_date',
        'updated_date'
    ]
    inlines = [DataRetentionPolicyTranslationInline]
    fieldsets = (
        (_('Policy Name'), {
            'fields': ('name',),
            'description': _('Default (e.g. English). For other languages use Translations inline below.'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'description': _('Default. For other languages use Translations inline below.'),
        }),
        (_('Policy Details'), {
            'fields': (
                'data_category',
                'retention_period_days',
                'deletion_method',
                'legal_basis'
            )
        }),
        (_('Settings'), {
            'fields': (
                'company',
                'auto_apply',
                'is_active'
            )
        }),
        (_('Audit'), {
            'fields': (
                'created_date',
                'updated_date'
            ),
            'classes': ('collapse',)
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '—'
    get_name_display.short_description = _('Name')


@admin.register(DPIAAssessment)
class DPIAAssessmentAdmin(admin.ModelAdmin):
    list_display = [
        'assessment_number',
        'project_name',
        'status_badge',
        'overall_risk_level_badge',
        'residual_risk_level_badge',
        'dpo_consulted',
        'approval_date',
        'company'
    ]
    list_filter = [
        'status',
        'overall_risk_level',
        'residual_risk_level',
        'dpo_consulted',
        'company',
        'created_date'
    ]
    search_fields = [
        'assessment_number',
        'project_name',
        'project_description'
    ]
    readonly_fields = [
        'created_date',
        'updated_date'
    ]
    fieldsets = (
        (_('Assessment Information'), {
            'fields': (
                'assessment_number',
                'project_name',
                'project_description',
                'company'
            )
        }),
        (_('Data Processing'), {
            'fields': (
                'processing_description',
                'data_types',
                'data_subjects'
            )
        }),
        (_('Necessity and Proportionality'), {
            'fields': (
                'necessity_assessment',
                'proportionality_assessment'
            )
        }),
        (_('Risk Assessment'), {
            'fields': (
                'risks_identified',
                'overall_risk_level',
                'mitigation_measures',
                'residual_risk_level'
            )
        }),
        (_('Consultations'), {
            'fields': (
                'stakeholders_consulted',
                'dpo_consulted',
                'conducted_by'
            )
        }),
        (_('Approval'), {
            'fields': (
                'status',
                'approval_date',
                'approved_by',
                'review_date'
            )
        }),
        (_('Audit'), {
            'fields': (
                'created_date',
                'updated_date'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'draft': {'bg': '#e2e3e5', 'text': '#383d41'},
            'in_review': {'bg': '#cfe2ff', 'text': '#084298'},
            'approved': {'bg': '#d4edda', 'text': '#155724'},
            'rejected': {'bg': '#f8d7da', 'text': '#721c24'},
            'requires_revision': {'bg': '#fff3cd', 'text': '#856404'}
        }
        color_scheme = colors.get(obj.status, {'bg': '#e2e3e5', 'text': '#383d41'})
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 10px; border-radius: 3px; font-weight: 500;">{}</span>',
            color_scheme['bg'],
            color_scheme['text'],
            obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def overall_risk_level_badge(self, obj):
        colors = {
            'low': {'bg': '#d4edda', 'text': '#155724'},
            'medium': {'bg': '#fff3cd', 'text': '#856404'},
            'high': {'bg': '#ffe5d0', 'text': '#8b4513'},
            'very_high': {'bg': '#f8d7da', 'text': '#721c24'}
        }
        color_scheme = colors.get(obj.overall_risk_level, {'bg': '#e2e3e5', 'text': '#383d41'})
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 10px; border-radius: 3px; font-weight: 500;">{}</span>',
            color_scheme['bg'],
            color_scheme['text'],
            obj.get_overall_risk_level_display()
        )
    overall_risk_level_badge.short_description = _('Overall Risk')
    
    def residual_risk_level_badge(self, obj):
        colors = {
            'low': {'bg': '#d4edda', 'text': '#155724'},
            'medium': {'bg': '#fff3cd', 'text': '#856404'},
            'high': {'bg': '#ffe5d0', 'text': '#8b4513'},
            'very_high': {'bg': '#f8d7da', 'text': '#721c24'}
        }
        color_scheme = colors.get(obj.residual_risk_level, {'bg': '#e2e3e5', 'text': '#383d41'})
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 10px; border-radius: 3px; font-weight: 500;">{}</span>',
            color_scheme['bg'],
            color_scheme['text'],
            obj.get_residual_risk_level_display()
        )
    residual_risk_level_badge.short_description = _('Residual Risk')


@admin.register(GDPRAccess)
class GDPRAccessAdmin(admin.ModelAdmin):
    list_display = [
        'group',
        'has_access_data_subjects',
        'has_access_dsr',
        'has_access_breach_management',
        'has_access_dpia',
        'has_access_compliance_dashboard'
    ]
    list_filter = [
        'has_access_data_subjects',
        'has_access_dsr',
        'has_access_breach_management',
        'has_access_dpia'
    ]
    search_fields = ['group__name']
    filter_horizontal = ['companies']
    
    fieldsets = (
        (_('Group'), {
            'fields': ('group',)
        }),
        (_('Data Subjects'), {
            'fields': (
                'has_access_data_subjects',
                'can_edit_data_subjects',
                'can_export_data_subjects'
            )
        }),
        (_('DSR Management'), {
            'fields': (
                'has_access_dsr',
                'can_process_dsr',
                'can_approve_dsr'
            )
        }),
        (_('Consent Management'), {
            'fields': (
                'has_access_consents',
                'can_manage_consents'
            )
        }),
        (_('Data Breach Management'), {
            'fields': (
                'has_access_breach_management',
                'can_report_breach',
                'can_investigate_breach',
                'can_edit_breaches'
            )
        }),
        (_('Processing Activities'), {
            'fields': (
                'can_edit_activities',
            )
        }),
        (_('Retention Policies'), {
            'fields': (
                'can_edit_policies',
            )
        }),
        (_('DPIA'), {
            'fields': (
                'has_access_dpia',
                'can_conduct_dpia',
                'can_approve_dpia'
            )
        }),
        (_('Compliance and Reporting'), {
            'fields': (
                'has_access_compliance_dashboard',
                'can_generate_reports'
            )
        }),
        (_('Company Access'), {
            'fields': (
                'companies',
                'description'
            )
        }),
    )


@admin.register(GDPRGuide)
class GDPRGuideAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'category',
        'file_type',
        'resource_id',
        'is_active_badge',
        'order',
        'file_preview',
        'created_at',
        'created_by'
    ]
    list_filter = [
        'category',
        'file_type',
        'is_active',
        'created_at'
    ]
    search_fields = [
        'title',
        'description',
        'resource_id'
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'created_by',
        'file_preview_large'
    ]
    list_editable = [
        'order'
    ]
    ordering = ['category', 'order', 'title']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'title',
                'description',
                'resource_id'
            )
        }),
        (_('File Details'), {
            'fields': (
                'category',
                'file',
                'file_type',
                'file_preview_large'
            )
        }),
        (_('Display Settings'), {
            'fields': (
                'is_active',
                'order'
            )
        }),
        (_('Metadata'), {
            'fields': (
                'created_at',
                'updated_at',
                'created_by'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def is_active_badge(self, obj):
        """Display active status as badge"""
        if obj.is_active:
            return format_html(
                '<span class="badge bg-success-subtle text-success">{}</span>',
                _('Active')
            )
        return format_html(
            '<span class="badge bg-secondary-subtle text-secondary">{}</span>',
            _('Inactive')
        )
    is_active_badge.short_description = _('Status')
    
    def file_preview(self, obj):
        """Display file icon and name"""
        if obj.file:
            return format_html(
                '<i class="{}"></i> <a href="{}" target="_blank">{}</a>',
                obj.get_file_icon(),
                obj.file.url,
                obj.file.name.split('/')[-1]
            )
        return '-'
    file_preview.short_description = _('File')
    
    def file_preview_large(self, obj):
        """Display detailed file information"""
        if obj.file:
            try:
                file_size = obj.file.size / 1024  # Convert to KB
                if file_size > 1024:
                    file_size_str = f"{file_size / 1024:.2f} MB"
                else:
                    file_size_str = f"{file_size:.2f} KB"
                
                return format_html(
                    '<div class="file-preview">'
                    '<p><i class="{}" style="font-size: 2rem;"></i></p>'
                    '<p><strong>{}:</strong> <a href="{}" target="_blank">{}</a></p>'
                    '<p><strong>{}:</strong> {}</p>'
                    '<p><strong>{}:</strong> {}</p>'
                    '</div>',
                    obj.get_file_icon(),
                    _('File'),
                    obj.file.url,
                    obj.file.name.split('/')[-1],
                    _('Size'),
                    file_size_str,
                    _('Type'),
                    obj.get_file_type_display()
                )
            except Exception as e:
                return format_html('<p class="text-danger">Error: {}</p>', str(e))
        return format_html('<p class="text-muted">{}</p>', _('No file uploaded'))
    file_preview_large.short_description = _('File Preview')
    
    def save_model(self, request, obj, form, change):
        """Save created_by field"""
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    class Media:
        css = {
            'all': ('admin/css/gdpr_guide_admin.css',)
        }
        js = ('admin/js/gdpr_guide_admin.js',)


class GdprGuideContentTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class GdprGuideContentTranslationInline(GdprGuideContentTranslationInlineMixin, admin.StackedInline):
    model = GdprGuideContentTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/gdpr_guide_content_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(GdprGuideContent)
class GdprGuideContentAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [GdprGuideContentTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_gdpr/gdprguidecontent/change_form.html'

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
            extra_context['gdpr_guide_content_translate_url'] = reverse('app_gdpr:gdpr_guide_translate')
        except Exception:
            extra_context['gdpr_guide_content_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['gdpr_guide_content_translate_url'] = reverse('app_gdpr:gdpr_guide_translate')
        except Exception:
            extra_context['gdpr_guide_content_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)
