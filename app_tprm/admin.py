from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField
from .models import (
    Vendor, VendorHistory, TprmOwner, VendorAssessment, VendorDocument,
    QuestionnaireTemplate, Question, VendorQuestionnaire, QuestionResponse,
    TPRMAccess, VendorSurveyLink, TprmGuide, TprmGuideTranslation, TprmLevel,
    TprmLevelTranslation, TprmRiskLevel, TprmStatusLevel, TprmCriticalityLevel,
    TprmSanctionsVerification, TprmDataAccessLevel, TprmDataAccessRights,
    cabinet_users_active_for_company,
)


class TprmLevelTranslationInline(admin.TabularInline):
    model = TprmLevelTranslation
    extra = 1
    fields = ('country', 'name_local', 'description_local')

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


class TprmLevelByTypeAdminBase(admin.ModelAdmin):
    """Base admin for a single TprmLevel type (proxy)."""
    list_display = ['name', 'code', 'color', 'display_order', 'cost', 'get_description_short', 'is_active']
    list_editable = ['display_order', 'cost', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering = ['display_order', 'cost', 'name']
    inlines = [TprmLevelTranslationInline]
    change_form_template = 'admin/app_tprm/tprmlevel/change_form.html'
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'color', 'display_order', 'cost', 'description', 'is_active')
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(type=self.level_type)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.type = self.level_type
        super().save_model(request, obj, form, change)

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or [])
        if 'type' not in exclude:
            exclude.append('type')  # set automatically in save_model
        return exclude

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['tprm_level_translate_url'] = request.build_absolute_uri(
                reverse('app_tprm:tprm_guide_translate')
            )
        except Exception:
            extra_context['tprm_level_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['tprm_level_translate_url'] = request.build_absolute_uri(
                reverse('app_tprm:tprm_guide_translate')
            )
        except Exception:
            extra_context['tprm_level_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


# Required for VendorAdmin.autocomplete_fields (Vendor FK points to TprmLevel).
# Hidden from app menu — each type is configured in its own section (Risk Levels, Status, etc.).
@admin.register(TprmLevel)
class TprmLevelAdmin(admin.ModelAdmin):
    list_display = ['type', 'name', 'code', 'color', 'display_order', 'cost', 'get_description_short', 'is_active']
    list_filter = ['type', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering = ['type', 'display_order', 'cost', 'name']
    inlines = [TprmLevelTranslationInline]

    def has_module_permission(self, request):
        return False  # hide from Home › App_Tprm menu; autocomplete still works


@admin.register(TprmRiskLevel)
class TprmRiskLevelAdmin(TprmLevelByTypeAdminBase):
    level_type = TprmLevel.TYPE_RISK_LEVEL
    list_display = ['name', 'code', 'color', 'display_order', 'cost', 'is_active']


@admin.register(TprmStatusLevel)
class TprmStatusLevelAdmin(TprmLevelByTypeAdminBase):
    level_type = TprmLevel.TYPE_STATUS


@admin.register(TprmCriticalityLevel)
class TprmCriticalityLevelAdmin(TprmLevelByTypeAdminBase):
    level_type = TprmLevel.TYPE_CRITICALITY


@admin.register(TprmSanctionsVerification)
class TprmSanctionsVerificationAdmin(TprmLevelByTypeAdminBase):
    level_type = TprmLevel.TYPE_SANCTIONS


@admin.register(TprmDataAccessLevel)
class TprmDataAccessLevelAdmin(TprmLevelByTypeAdminBase):
    level_type = TprmLevel.TYPE_DATA_ACCESS


@admin.register(TprmDataAccessRights)
class TprmDataAccessRightsAdmin(TprmLevelByTypeAdminBase):
    level_type = TprmLevel.TYPE_DATA_ACCESS_RIGHTS


@admin.register(TprmOwner)
class TprmOwnerAdmin(admin.ModelAdmin):
    list_display = ['id', 'cabinet_user', 'company']
    list_filter = ['company']
    search_fields = [
        'cabinet_user__user__username',
        'cabinet_user__user__first_name',
        'cabinet_user__user__last_name',
        'cabinet_user__user__email',
        'company__name',
    ]
    autocomplete_fields = ['cabinet_user', 'company']


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'is_active', 'risk_level', 'status', 'nda_in_contract', 'criticality_level', 'sanctions_verification_status', 'data_access_level', 'data_access_rights', 'contact_person', 'created_at']
    list_filter = ['is_active', 'risk_level', 'status', 'nda_in_contract', 'company', 'created_at']
    search_fields = ['name', 'contact_person', 'contact_email', 'contract', 'contract_validity', 'company__name']
    readonly_fields = [
        'created_at', 'updated_at',
        'actualization_date', 'actualized_by', 'marked_no_longer_actual_at', 'marked_no_longer_comment',
    ]
    autocomplete_fields = ['risk_level', 'status', 'criticality_level', 'sanctions_verification_status', 'data_access_level', 'data_access_rights']
    filter_horizontal = ('owners',)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'owners':
            qs = TprmOwner.objects.select_related('cabinet_user__user', 'company')
            obj_id = request.resolver_match.kwargs.get('object_id') if getattr(request, 'resolver_match', None) else None
            if obj_id:
                obj = Vendor.objects.filter(pk=obj_id).first()
                if obj and obj.company_id:
                    active_cu = list(
                        cabinet_users_active_for_company(obj.company_id).values_list('pk', flat=True)
                    )
                    selected_pks = list(obj.owners.values_list('pk', flat=True))
                    qs = qs.filter(company_id=obj.company_id).filter(
                        models.Q(cabinet_user_id__in=active_cu) | models.Q(pk__in=selected_pks)
                    )
            kwargs['queryset'] = qs.order_by(
                'cabinet_user__user__last_name',
                'cabinet_user__user__first_name',
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active', 'company', 'owners', 'description', 'contract', 'contract_validity', 'contract_end_date', 'website', 'services_provided')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'contact_email', 'contact_phone')
        }),
        ('Risk & Status', {
            'fields': ('risk_level', 'status', 'nda_in_contract', 'criticality_level', 'sanctions_verification_status', 'data_access_level', 'data_access_rights')
        }),
        ('Actualization', {
            'fields': ('actualization_date', 'actualized_by', 'marked_no_longer_actual_at', 'marked_no_longer_comment'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(VendorHistory)
class VendorHistoryAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'timestamp', 'action', 'action_by']
    list_filter = ['action', 'timestamp']
    search_fields = ['vendor__name', 'details']
    readonly_fields = ['vendor', 'timestamp', 'action', 'action_by', 'details', 'changes']
    ordering = ['-timestamp']

    def has_add_permission(self, request):
        return False


@admin.register(VendorAssessment)
class VendorAssessmentAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'assessment_date', 'status', 'overall_score', 'assessed_by']
    list_filter = ['status', 'assessment_date']
    search_fields = ['vendor__name']
    readonly_fields = ['created_at', 'updated_at', 'overall_score']
    
    fieldsets = (
        ('Assessment Information', {
            'fields': ('vendor', 'assessment_date', 'next_review_date', 'status')
        }),
        ('Scores', {
            'fields': ('security_score', 'compliance_score', 'financial_score', 
                      'operational_score', 'overall_score')
        }),
        ('Findings & Recommendations', {
            'fields': ('findings', 'recommendations')
        }),
        ('Review', {
            'fields': ('assessed_by', 'approved_by')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(VendorDocument)
class VendorDocumentAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'title', 'document_type', 'expiry_date', 'uploaded_at']
    list_filter = ['document_type', 'uploaded_at']
    search_fields = ['vendor__name', 'title']
    readonly_fields = ['uploaded_at']


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ['order', 'question_text', 'question_type', 'weight', 'parent_question', 'show_if_answer', 'is_required']
    ordering = ['order']
    autocomplete_fields = ['parent_question']


@admin.register(QuestionnaireTemplate)
class QuestionnaireTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active', 'question_count', 'conditional_count', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [QuestionInline]
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'
    
    def conditional_count(self, obj):
        count = obj.questions.filter(parent_question__isnull=False).count()
        if count > 0:
            return f"🔀 {count}"
        return "-"
    conditional_count.short_description = 'Branching'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['template', 'order', 'question_text_short', 'question_type', 'parent_question_info', 'weight', 'is_required']
    list_filter = ['template', 'question_type', 'is_required']
    search_fields = ['question_text']
    list_editable = ['order', 'weight']
    autocomplete_fields = ['parent_question']
    
    fieldsets = (
        ('Question Content', {
            'fields': ('template', 'question_text', 'question_type', 'choices', 'help_text')
        }),
        ('Conditional Logic', {
            'fields': ('parent_question', 'show_if_answer'),
            'description': 'Set parent question and condition to create branching logic'
        }),
        ('Scoring & Order', {
            'fields': ('order', 'weight', 'correct_answer', 'is_required')
        }),
    )
    
    def question_text_short(self, obj):
        text = obj.question_text[:60] + '...' if len(obj.question_text) > 60 else obj.question_text
        if obj.parent_question:
            return f"↳ {text}"
        return text
    question_text_short.short_description = 'Question'
    
    def parent_question_info(self, obj):
        if obj.parent_question:
            return f"If Q{obj.parent_question.order} = {obj.show_if_answer}"
        return "-"
    parent_question_info.short_description = 'Condition'


class QuestionResponseInline(admin.TabularInline):
    model = QuestionResponse
    extra = 0
    readonly_fields = ['question', 'score', 'answered_at']
    fields = ['question', 'response_text', 'response_bool', 'response_scale', 'score']


@admin.register(VendorQuestionnaire)
class VendorQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'template', 'status', 'percentage_score', 'completed_date']
    list_filter = ['status', 'template__category']
    search_fields = ['vendor__name']
    readonly_fields = ['total_score', 'max_score', 'percentage_score', 'created_at', 'updated_at']
    inlines = [QuestionResponseInline]
    
    fieldsets = (
        ('Questionnaire Information', {
            'fields': ('vendor', 'template', 'assessment', 'status')
        }),
        ('Dates', {
            'fields': ('started_date', 'completed_date')
        }),
        ('Scoring', {
            'fields': ('total_score', 'max_score', 'percentage_score')
        }),
        ('Review', {
            'fields': ('completed_by', 'reviewed_by', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TPRMAccess)
class TPRMAccessAdmin(admin.ModelAdmin):
    list_display = [
        'group',
        'has_access_vendors',
        'has_access_assessments',
        'has_access_questionnaires',
        'has_access_dashboard'
    ]
    list_filter = [
        'has_access_vendors',
        'has_access_assessments',
        'has_access_templates',
        'has_access_questionnaires'
    ]
    search_fields = ['group__name']
    filter_horizontal = ['companies']
    
    fieldsets = (
        (_('Group'), {
            'fields': ('group',)
        }),
        (_('Vendor Management'), {
            'fields': (
                'has_access_vendors',
                'can_edit_vendors',
                'can_delete_vendors'
            )
        }),
        (_('Vendor Assessment Management'), {
            'fields': (
                'has_access_assessments',
                'can_conduct_assessments',
                'can_approve_assessments'
            )
        }),
        (_('Document Management'), {
            'fields': (
                'has_access_documents',
                'can_upload_documents',
                'can_delete_documents'
            )
        }),
        (_('Questionnaire Template Management'), {
            'fields': (
                'has_access_templates',
                'can_edit_templates',
                'can_manage_questions'
            )
        }),
        (_('Questionnaire Management'), {
            'fields': (
                'has_access_questionnaires',
                'can_complete_questionnaires',
                'can_review_questionnaires'
            )
        }),
        (_('Dashboard and Reporting'), {
            'fields': (
                'has_access_dashboard',
                'can_generate_reports',
                'can_export_data'
            )
        }),
        (_('Risk Management'), {
            'fields': (
                'can_change_risk_level',
                'can_change_vendor_status'
            )
        }),
        (_('Company Access'), {
            'fields': (
                'companies',
                'description'
            )
        }),
    )


@admin.register(VendorSurveyLink)
class VendorSurveyLinkAdmin(admin.ModelAdmin):
    list_display = [
        'token_short', 'vendor', 'status', 'current_uses', 'max_uses',
        'expires_at', 'is_one_time_use', 'created_at', 'created_by'
    ]
    list_filter = ['status', 'is_one_time_use', 'created_at', 'expires_at']
    search_fields = ['token', 'vendor__name', 'notes']
    readonly_fields = [
        'token', 'created_at', 'updated_at', 'first_accessed_at',
        'last_accessed_at', 'current_uses', 'accessed_from_ip'
    ]
    
    fieldsets = (
        (_('Link Information'), {
            'fields': ('token', 'vendor', 'questionnaire', 'template', 'status')
        }),
        (_('Access Configuration'), {
            'fields': (
                'expires_at',
                'is_one_time_use',
                'max_uses',
                'current_uses'
            )
        }),
        (_('Access Tracking'), {
            'fields': (
                'first_accessed_at',
                'last_accessed_at',
                'accessed_from_ip'
            ),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('created_by', 'created_at', 'updated_at', 'notes'),
            'classes': ('collapse',)
        }),
    )
    
    def token_short(self, obj):
        return f"{obj.token[:12]}..." if len(obj.token) > 12 else obj.token
    token_short.short_description = 'Token'
    token_short.admin_order_field = 'token'
    
    def get_readonly_fields(self, request, obj=None):
        # Token should not be editable after creation
        if obj:
            return self.readonly_fields + ['token']
        return self.readonly_fields


class TprmGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class TprmGuideTranslationInline(TprmGuideTranslationInlineMixin, admin.StackedInline):
    model = TprmGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/tprm_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(TprmGuide)
class TprmGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [TprmGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_tprm/tprmguide/change_form.html'

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
            extra_context['tprm_guide_translate_url'] = reverse('app_tprm:tprm_guide_translate')
        except Exception:
            extra_context['tprm_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['tprm_guide_translate_url'] = reverse('app_tprm:tprm_guide_translate')
        except Exception:
            extra_context['tprm_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)
