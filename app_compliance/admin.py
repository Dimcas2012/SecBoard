from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    ComplianceFramework, ControlCategory, Control,
    Evidence, ControlAssignment, ComplianceAuditLog, ControlMapping,
    AccessCompliance, AccessLocalCompliance, CompanyType, RegulatorType, RegulatorTypeTranslation,
    RequirementType, RequirementTypeTranslation,
    RequirementStatus, RequirementStatusTranslation,
    RequirementPriority, RequirementPriorityTranslation,
    EvidenceType, EvidenceTypeTranslation,
    LocalComplianceRegulator, LocalComplianceRequirement, LocalComplianceControl,
    AccessInternalCompliance, InternalComplianceSource, InternalComplianceRequirement,
    InternalComplianceControl, InternalRequirementCategory, InternalControlEvidence,
    InternalControlAssignment, InternalControlNote, InternalControlMapping, AccessControlMapping,
    InternalRequirementNote, InternalRequirementNoteAttachment,
    LocalRequirementNote, LocalRequirementNoteAttachment,
    FrameworkDomain,
    MandatoryProcess, ProcessAttachment, ProcessExecution, ProcessEvidenceFile,
    MandatoryProcessesGuide, MandatoryProcessesGuideTranslation,
    InternalComplianceGuide, InternalComplianceGuideTranslation,
    LocalComplianceGuide, LocalComplianceGuideTranslation,
    FrameworkComplianceGuide, FrameworkComplianceGuideTranslation
)
from app_conf.models import Country
from .views import get_user_accessible_companies
from app_conf.models import Company
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField


class ActiveCountryInlineMixin:
    """Mixin to limit country choices to active records."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ComplianceFramework)
class ComplianceFrameworkAdmin(admin.ModelAdmin):
    list_display = ('name', 'framework_type', 'version', 'is_template', 'template', 'company', 'status', 'instance_count', 'created_date')
    list_filter = ('is_template', 'framework_type', 'status', 'company', 'is_mandatory')
    search_fields = ('name', 'description', 'version', 'company__name')
    readonly_fields = ('created_date', 'updated_date', 'created_by', 'instance_count')
    list_editable = ('is_template',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'framework_type', 'version', 'description')
        }),
        ('Template System', {
            'fields': ('is_template', 'template', 'company'),
            'description': 'Templates can be applied to multiple companies. Instances are linked to one company and one template.'
        }),
        ('Status', {
            'fields': ('status', 'is_mandatory', 'implementation_deadline')
        }),
        ('Statistics', {
            'fields': ('instance_count',),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['convert_to_template', 'apply_to_all_companies', 'sync_instances']
    
    def instance_count(self, obj):
        """Кількість instances для template"""
        if obj.is_template:
            return obj.instances.count()
        return '-'
    instance_count.short_description = 'Instances'
    
    def convert_to_template(self, request, queryset):
        """Конвертувати в template"""
        count = 0
        for framework in queryset:
            if not framework.is_template:
                framework.is_template = True
                framework.company = None
                framework.save()
                count += 1
        
        self.message_user(request, f'{count} frameworks converted to templates')
    convert_to_template.short_description = 'Convert to template'
    
    def apply_to_all_companies(self, request, queryset):
        """Застосувати до доступних компаній (respects AccessCompliance)"""
        # Get only accessible companies based on AccessCompliance settings
        companies = get_user_accessible_companies(request.user)
        total_created = 0
        
        for framework in queryset.filter(is_template=True):
            for company in companies:
                # Check if already exists
                if not ComplianceFramework.objects.filter(company=company, template=framework).exists():
                    framework.apply_to_company(company, created_by=request.user)
                    total_created += 1
        
        self.message_user(request, f'{total_created} instances created for accessible companies')
    apply_to_all_companies.short_description = 'Apply to accessible companies'
    
    def sync_instances(self, request, queryset):
        """Синхронізувати instances з template"""
        count = 0
        for template in queryset.filter(is_template=True):
            for instance in template.instances.all():
                instance.sync_from_template()
                count += 1
        
        self.message_user(request, f'{count} instances synced')
    sync_instances.short_description = 'Sync instances from template'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ControlCategory)
class ControlCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'framework', 'order', 'created_date')
    list_filter = ('framework',)
    search_fields = ('code', 'name', 'description')
    readonly_fields = ('created_date', 'updated_date')
    ordering = ('framework', 'order', 'code')


@admin.register(Control)
class ControlAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'domain', 'status', 'priority', 'responsible', 'is_verified')
    list_filter = ('status', 'priority', 'is_verified', 'category__framework', 'domain')
    search_fields = ('code', 'name', 'description', 'domain')
    readonly_fields = ('created_date', 'updated_date', 'created_by', 'verified_date', 'actual_completion_date')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'parent_control', 'code', 'name', 'description', 'domain')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'responsible', 'target_completion_date', 'actual_completion_date')
        }),
        ('Evidence Requirements', {
            'fields': ('required_evidence_count', 'evidence_description')
        }),
        ('Implementation & Testing', {
            'fields': ('implementation_guidance', 'testing_procedure'),
            'classes': ('collapse',)
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_by', 'verified_date', 'verification_notes'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('order', 'created_date', 'updated_date', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter FrameworkDomain to show only active domains"""
        if db_field.name == 'domain':
            from .models import FrameworkDomain
            kwargs['queryset'] = FrameworkDomain.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ('title', 'control', 'evidence_type', 'approval_status', 'uploaded_by', 'uploaded_date', 'is_active')
    list_filter = ('evidence_type', 'approval_status', 'is_active', 'uploaded_date')
    search_fields = ('title', 'description', 'control__code', 'control__name')
    readonly_fields = ('uploaded_date', 'uploaded_by', 'reviewed_date', 'reviewed_by', 'created_date', 'updated_date', 'file_size')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('control', 'title', 'description', 'evidence_type', 'evidence_type_old')
        }),
        ('Evidence Content', {
            'fields': ('file', 'file_size', 'text_evidence', 'external_link')
        }),
        ('Approval', {
            'fields': ('approval_status', 'reviewed_by', 'reviewed_date', 'review_comments')
        }),
        ('Meta', {
            'fields': ('expiration_date', 'is_active', 'uploaded_by', 'uploaded_date'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ControlAssignment)
class ControlAssignmentAdmin(admin.ModelAdmin):
    list_display = ('control', 'user', 'assignment_type', 'assigned_by', 'assigned_date', 'is_active')
    list_filter = ('assignment_type', 'is_active', 'assigned_date')
    search_fields = ('control__code', 'control__name', 'user__username', 'user__email')
    readonly_fields = ('assigned_date',)


@admin.register(ComplianceAuditLog)
class ComplianceAuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'object_type', 'object_repr', 'timestamp', 'ip_address')
    list_filter = ('action', 'object_type', 'timestamp')
    search_fields = ('object_repr', 'user__username', 'notes')
    readonly_fields = ('user', 'action', 'timestamp', 'object_type', 'object_id', 'object_repr', 'changes', 'ip_address', 'user_agent')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ControlMapping)
class ControlMappingAdmin(admin.ModelAdmin):
    list_display = ('source_control', 'target_control', 'mapping_type', 'created_by', 'created_date')
    list_filter = ('mapping_type', 'created_date')
    search_fields = ('source_control__code', 'target_control__code', 'notes')
    readonly_fields = ('created_date', 'created_by')
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AccessCompliance)
class AccessComplianceAdmin(admin.ModelAdmin):
    list_display = ('group', 'has_access', 'can_view_frameworks', 'can_edit_frameworks', 'can_view_instance_controls', 'can_edit_instance_controls', 'can_export', 'can_view_reports', 'companies_list')
    list_filter = ('has_access', 'can_view_frameworks', 'can_edit_frameworks', 'can_view_instance_controls', 'can_edit_instance_controls', 'can_export', 'can_view_reports')
    search_fields = ('group__name', 'description')
    filter_horizontal = ('companies',)
    
    fieldsets = (
        ('Group Information', {
            'fields': ('group', 'description')
        }),
        ('Access Rights', {
            'fields': ('has_access',)
        }),
        ('Framework Permissions', {
            'fields': ('can_view_frameworks', 'can_edit_frameworks', 'can_add_frameworks', 'can_delete_frameworks')
        }),
        ('Template Control Permissions', {
            'fields': ('can_view_controls', 'can_edit_controls', 'can_add_controls', 'can_delete_controls'),
            'description': 'Permissions for managing controls in Template Frameworks'
        }),
        ('Instance Control Permissions', {
            'fields': ('can_view_instance_controls', 'can_edit_instance_controls'),
            'description': 'Permissions for viewing and editing controls in Framework Instances (applied to companies)'
        }),
        ('Evidence & Reports', {
            'fields': ('can_manage_evidence', 'can_approve_evidence', 'can_export', 'can_view_reports')
        }),
        ('Company Access', {
            'fields': ('companies',),
            'description': 'Select companies this group can access. Leave empty for all companies.'
        }),
    )
    
    def companies_list(self, obj):
        """Список компаній"""
        companies = obj.companies.all()
        if companies.exists():
            return ', '.join([c.name for c in companies[:3]]) + (f' (+{companies.count() - 3} more)' if companies.count() > 3 else '')
        return 'All companies'
    companies_list.short_description = 'Companies'


@admin.register(AccessLocalCompliance)
class AccessLocalComplianceAdmin(admin.ModelAdmin):
    list_display = ('group', 'has_access', 'can_view_regulators', 'can_edit_regulators', 'can_view_requirements', 'can_edit_requirements', 'can_view_controls', 'can_edit_controls', 'can_export', 'can_view_reports', 'companies_list')
    list_filter = ('has_access', 'can_view_regulators', 'can_edit_regulators', 'can_view_requirements', 'can_edit_requirements', 'can_view_controls', 'can_edit_controls', 'can_export', 'can_view_reports')
    search_fields = ('group__name', 'description')
    filter_horizontal = ('companies',)
    
    fieldsets = (
        ('Group Information', {
            'fields': ('group', 'description')
        }),
        ('Access Rights', {
            'fields': ('has_access',)
        }),
        ('Regulator Permissions', {
            'fields': ('can_view_regulators', 'can_edit_regulators', 'can_add_regulators', 'can_delete_regulators')
        }),
        ('Requirement Permissions', {
            'fields': ('can_view_requirements', 'can_edit_requirements', 'can_add_requirements', 'can_delete_requirements'),
            'description': 'Permissions for managing requirement templates'
        }),
        ('Requirement Instance Permissions', {
            'fields': ('can_view_requirement_instances', 'can_edit_requirement_instances'),
            'description': 'Permissions for viewing and editing requirement instances (applied to companies)'
        }),
        ('Control Permissions', {
            'fields': ('can_view_controls', 'can_edit_controls', 'can_add_controls', 'can_delete_controls'),
            'description': 'Permissions for managing local compliance controls'
        }),
        ('Evidence & Reports', {
            'fields': ('can_manage_evidence', 'can_approve_evidence', 'can_export', 'can_view_reports')
        }),
        ('Company Access', {
            'fields': ('companies',),
            'description': 'Select companies this group can access. Leave empty for all companies.'
        }),
    )
    
    def companies_list(self, obj):
        """Список компаній"""
        companies = obj.companies.all()
        if companies.exists():
            return ', '.join([c.name for c in companies[:3]]) + (f' (+{companies.count() - 3} more)' if companies.count() > 3 else '')
        return 'All companies'
    companies_list.short_description = 'Companies'


# ========================
# Local Compliance Admin
# ========================

# CompanyType management moved to Country/Company admin
# @admin.register(CompanyType)
class CompanyTypeAdmin(admin.ModelAdmin):
    list_display = ('icon_display', 'name', 'name_local', 'code', 'color_display', 'companies_count', 'is_active', 'display_order')
    list_filter = ('is_active', 'companies')
    search_fields = ('name', 'name_local', 'code', 'description')
    list_editable = ('name', 'name_local', 'display_order', 'is_active')
    ordering = ('display_order', 'name')
    filter_horizontal = ('companies',)
    actions = ['activate_types', 'deactivate_types', 'duplicate_type']
    list_per_page = 50
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'name_local', 'code')
        }),
        ('Display', {
            'fields': ('icon', 'color', 'display_order')
        }),
        ('Companies', {
            'fields': ('companies',),
            'description': 'Select companies of this type'
        }),
        ('Details', {
            'fields': ('description', 'regulatory_requirements')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('companies_list',),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_date', 'updated_date', 'companies_list')
    
    # Додаткові поля для форми
    class Media:
        css = {
            'all': ('admin/css/company_type_admin.css',)
        }
        js = ('admin/js/company_type_admin.js',)
    
    def icon_display(self, obj):
        """Відображення іконки"""
        from django.utils.html import format_html
        if obj.icon:
            return format_html('<i class="fas {}"></i>', obj.icon)
        return "-"
    icon_display.short_description = 'Icon'
    
    def color_display(self, obj):
        """Відображення кольору"""
        from django.utils.html import format_html
        return format_html(
            '<span style="display: inline-block; width: 30px; height: 15px; background-color: {}; border: 1px solid #ccc;"></span> {}',
            obj.color,
            obj.color
        )
    color_display.short_description = 'Color'
    
    def companies_count(self, obj):
        """Кількість компаній"""
        return obj.companies.count()
    companies_count.short_description = 'Companies'
    
    def companies_list(self, obj):
        """Список компаній"""
        companies = obj.companies.all()
        if companies.exists():
            return ', '.join([c.name for c in companies[:10]]) + (f' (+{companies.count() - 10} more)' if companies.count() > 10 else '')
        return '-'
    companies_list.short_description = 'Companies List'
    
    # Actions
    def activate_types(self, request, queryset):
        """Активувати вибрані типи"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} company type(s) activated')
    activate_types.short_description = 'Activate selected company types'
    
    def deactivate_types(self, request, queryset):
        """Деактивувати вибрані типи"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} company type(s) deactivated')
    deactivate_types.short_description = 'Deactivate selected company types'
    
    def duplicate_type(self, request, queryset):
        """Дублювати вибрані типи"""
        from django.contrib import messages
        count = 0
        for company_type in queryset:
            # Створити копію
            new_code = f"{company_type.code}_copy"
            # Перевірити чи код вже існує
            counter = 1
            while CompanyType.objects.filter(code=new_code).exists():
                new_code = f"{company_type.code}_copy_{counter}"
                counter += 1
            
            new_type = CompanyType.objects.create(
                name=f"{company_type.name} (Copy)",
                name_local=f"{company_type.name_local} (Копія)" if company_type.name_local else "",
                code=new_code,
                icon=company_type.icon,
                color=company_type.color,
                description=company_type.description,
                regulatory_requirements=company_type.regulatory_requirements,
                display_order=company_type.display_order + 1,
                is_active=False  # Деактивована по замовчуванню
            )
            # Копіювати companies
            new_type.companies.set(company_type.companies.all())
            count += 1
        
        self.message_user(request, f'{count} company type(s) duplicated')
    duplicate_type.short_description = 'Duplicate selected company types'


class RegulatorTypeTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = RegulatorTypeTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(RegulatorType)
class RegulatorTypeAdmin(admin.ModelAdmin):
    list_display = (
        'color_badge', 'icon_display', 'name', 'code',
        'translations_count', 'companies_count', 'is_active', 'display_order'
    )
    list_filter = ('is_active', 'companies')
    search_fields = ('name', 'name_local', 'code', 'description')
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    filter_horizontal = ('companies',)
    inlines = [RegulatorTypeTranslationInline]

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code')
        }),
        (_('Display'), {
            'fields': ('icon', 'color', 'display_order')
        }),
        (_('Details'), {
            'fields': ('name_local', 'description', 'companies'),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )

    readonly_fields = ('created_date', 'updated_date')

    def color_badge(self, obj):
        """Display color badge similar to RequirementPriority form."""
        from django.utils.html import format_html
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; '
            'background-color: {}; border: 1px solid #ddd; border-radius: 3px;"></span> {}',
            obj.color,
            obj.color
        )
    color_badge.short_description = _('Color')

    def icon_display(self, obj):
        """Display icon preview."""
        from django.utils.html import format_html
        if obj.icon:
            return format_html('<i class="fas {}"></i>', obj.icon)
        return '-'
    icon_display.short_description = _('Icon')

    def translations_count(self, obj):
        """Count of translations."""
        count = obj.translations.count()
        if count > 0:
            from django.utils.html import format_html
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')

    def companies_count(self, obj):
        """Number of companies linked to this regulator type."""
        return obj.companies.count()
    companies_count.short_description = _('Companies')


class RequirementTypeTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = RequirementTypeTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']
    
    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(RequirementType)
class RequirementTypeAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'code', 'translations_count', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    inlines = [RequirementTypeTranslationInline]
    exclude = ('name_local',)
    
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
        from django.utils.html import format_html
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; '
            'background-color: {}; border: 1px solid #ddd; border-radius: 3px;"></span> {}',
            obj.color,
            obj.color
        )
    color_badge.short_description = _('Color')
    
    def translations_count(self, obj):
        """Count of translations"""
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


class EvidenceTypeTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = EvidenceTypeTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']
    
    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(EvidenceType)
class EvidenceTypeAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'code', 'translations_count', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    inlines = [EvidenceTypeTranslationInline]
    exclude = ('name_local',)
    
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
        from django.utils.html import format_html
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; '
            'background-color: {}; border: 1px solid #ddd; border-radius: 3px;"></span> {}',
            obj.color,
            obj.color
        )
    color_badge.short_description = _('Color')
    
    def translations_count(self, obj):
        """Count of translations"""
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


class RequirementStatusTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = RequirementStatusTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']
    
    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(RequirementStatus)
class RequirementStatusAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'code', 'translations_count', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    inlines = [RequirementStatusTranslationInline]
    exclude = ('name_local',)
    
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
        from django.utils.html import format_html
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; '
            'background-color: {}; border: 1px solid #ddd; border-radius: 3px;"></span> {}',
            obj.color,
            obj.color
        )
    color_badge.short_description = _('Color')
    
    def translations_count(self, obj):
        """Count of translations"""
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


class RequirementPriorityTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = RequirementPriorityTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']
    
    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {
            'all': ('admin/css/translation_helper.css',)
        }


@admin.register(RequirementPriority)
class RequirementPriorityAdmin(admin.ModelAdmin):
    list_display = ('color_badge', 'name', 'code', 'translations_count', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    inlines = [RequirementPriorityTranslationInline]
    exclude = ('name_local',)
    
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
        from django.utils.html import format_html
        return format_html(
            '<span style="display: inline-block; width: 20px; height: 20px; '
            'background-color: {}; border: 1px solid #ddd; border-radius: 3px;"></span> {}',
            obj.color,
            obj.color
        )
    color_badge.short_description = _('Color')
    
    def translations_count(self, obj):
        """Count of translations"""
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


@admin.register(LocalComplianceRegulator)
class LocalComplianceRegulatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'acronym', 'country_display', 'regulator_type_display', 'company_types_display', 'color_display', 'companies_count', 'is_active', 'requirements_count', 'created_date')
    list_filter = ('country', 'regulator_type', 'company_types', 'is_active', 'companies', 'created_date')
    search_fields = ('name', 'name_local', 'acronym', 'description', 'website')
    readonly_fields = ('created_date', 'updated_date', 'created_by', 'requirements_count', 'companies_list')
    filter_horizontal = ('companies', 'company_types')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'name_local', 'acronym')
        }),
        ('Classification', {
            'fields': ('country', 'regulator_type', 'color'),
            'description': 'Select country first, then choose companies from that country'
        }),
        ('Company Types', {
            'fields': ('company_types',),
            'description': 'Select the types of companies this regulator oversees (e.g., Banks, Payment Systems)'
        }),
        ('Contact Information', {
            'fields': ('website', 'contact_email', 'contact_phone')
        }),
        ('Details', {
            'fields': ('description',)
        }),
        ('Companies', {
            'fields': ('companies',),
            'description': 'Companies regulated by this regulator. Filter based on selected country.'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('requirements_count', 'companies_list'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    class Media:
        js = ('admin/js/regulator_country_filter.js',)
    
    def country_display(self, obj):
        """Відображення країни з прапором"""
        if obj.country:
            if obj.country.flag_emoji:
                return f"{obj.country.flag_emoji} {obj.country.name}"
            return obj.country.name
        return "-"
    country_display.short_description = 'Country'
    
    def regulator_type_display(self, obj):
        """Відображення типу регулятора з іконкою та кольором"""
        from django.utils.html import format_html
        if obj.regulator_type:
            if obj.regulator_type.icon:
                return format_html(
                    '<span style="color: {};"><i class="fas {}"></i> {}</span>',
                    obj.regulator_type.color,
                    obj.regulator_type.icon,
                    obj.regulator_type.name
                )
            else:
                return format_html(
                    '<span style="color: {};">{}</span>',
                    obj.regulator_type.color,
                    obj.regulator_type.name
                )
        return "-"
    regulator_type_display.short_description = 'Regulator Type'
    
    def company_types_display(self, obj):
        """Display company types with color badges"""
        from django.utils.html import format_html
        if not obj.pk:
            return '-'
        
        types = obj.company_types.all()
        if not types:
            return format_html('<em style="color: #6c757d;">-</em>')
        
        badges = []
        for company_type in types[:3]:  # Показувати максимум 3
            badges.append(
                f'<span style="display: inline-block; margin: 2px; padding: 3px 6px; '
                f'background: {company_type.color}; color: white; border-radius: 3px; '
                f'font-size: 0.75rem; font-weight: 500;">'
                f'{company_type.name_local or company_type.name}</span>'
            )
        
        result = ' '.join(badges)
        if types.count() > 3:
            result += f' <span style="color: #6c757d;">+{types.count() - 3}</span>'
        
        return format_html(result)
    company_types_display.short_description = 'Company Types'
    
    def color_display(self, obj):
        """Відображення кольору"""
        from django.utils.html import format_html
        return format_html(
            '<span style="display: inline-block; width: 30px; height: 15px; background-color: {}; border: 1px solid #ccc;"></span>',
            obj.color
        )
    color_display.short_description = 'Color'
    
    def companies_count(self, obj):
        """Кількість компаній"""
        return obj.companies.count()
    companies_count.short_description = 'Companies'
    
    def companies_list(self, obj):
        """Список компаній"""
        companies = obj.companies.all()
        if companies.exists():
            return ', '.join([c.name for c in companies[:5]]) + (f' (+{companies.count() - 5} more)' if companies.count() > 5 else '')
        return '-'
    companies_list.short_description = 'Companies List'
    
    def requirements_count(self, obj):
        """Кількість вимог"""
        return obj.requirements.count()
    requirements_count.short_description = 'Requirements'
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Фільтрувати companies на основі обраної country"""
        if db_field.name == "companies":
            # Отримати ID країни з GET параметрів (при edit) або з POST (при save)
            country_id = None
            
            # Спробувати отримати з URL (edit mode)
            if request.resolver_match and 'object_id' in request.resolver_match.kwargs:
                object_id = request.resolver_match.kwargs['object_id']
                try:
                    regulator = LocalComplianceRegulator.objects.get(pk=object_id)
                    if regulator.country:
                        country_id = regulator.country.id
                except LocalComplianceRegulator.DoesNotExist:
                    pass
            
            # Якщо є country_id, фільтруємо companies
            if country_id:
                kwargs["queryset"] = Company.objects.filter(countries__id=country_id).distinct()
            else:
                # Показати всі компанії якщо країна не вибрана
                kwargs["queryset"] = Company.objects.all()
        
        return super().formfield_for_manytomany(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LocalComplianceRequirement)
class LocalComplianceRequirementAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'regulator', 'is_template', 'requirement_type', 'status', 'priority', 'effective_date', 'deadline_date', 'is_mandatory', 'instances_count')
    list_filter = ('is_template', 'regulator', 'status', 'requirement_type', 'is_mandatory', 'priority', 'effective_date')
    search_fields = ('code', 'name', 'name_local', 'description', 'applicable_to')
    readonly_fields = ('created_date', 'updated_date', 'created_by', 'controls_count', 'instances_count')
    date_hierarchy = 'effective_date'
    
    fieldsets = (
        ('Template System', {
            'fields': ('is_template', 'template'),
            'description': 'Templates can be applied to multiple companies. Leave template blank for new templates.'
        }),
        ('Basic Information', {
            'fields': ('regulator', 'code', 'name', 'name_local', 'requirement_type')
        }),
        ('Details', {
            'fields': ('description', 'applicable_to')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'is_mandatory')
        }),
        ('Important Dates', {
            'fields': ('publication_date', 'effective_date', 'deadline_date', 'review_date')
        }),
        ('References', {
            'fields': ('official_link', 'document_file')
        }),
        ('Statistics', {
            'fields': ('controls_count', 'instances_count'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['apply_to_companies', 'mark_as_template']
    
    def controls_count(self, obj):
        """Кількість контролів"""
        return obj.get_controls_count()
    controls_count.short_description = 'Controls'
    
    def instances_count(self, obj):
        """Кількість instances"""
        if obj.is_template:
            count = obj.get_instances_count()
            return f'{count} instances' if count > 0 else 'No instances'
        return '-'
    instances_count.short_description = 'Instances'
    
    def apply_to_companies(self, request, queryset):
        """Застосувати template до доступних компаній (respects AccessCompliance)"""
        from django.db import transaction
        
        # Get only accessible companies based on AccessCompliance settings
        templates = queryset.filter(is_template=True)
        companies = get_user_accessible_companies(request.user)
        total_created = 0
        
        with transaction.atomic():
            for template in templates:
                for company in companies:
                    try:
                        template.apply_to_company(company, created_by=request.user)
                        total_created += 1
                    except Exception:
                        # Skip if already exists
                        continue
        
        self.message_user(request, f'{total_created} instances created for accessible companies')
    apply_to_companies.short_description = 'Apply templates to accessible companies'
    
    def mark_as_template(self, request, queryset):
        """Позначити як template"""
        count = queryset.update(is_template=True)
        self.message_user(request, f'{count} requirements marked as templates')
    mark_as_template.short_description = 'Mark as template'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LocalComplianceControl)
class LocalComplianceControlAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'company', 'requirement', 'status', 'priority', 'responsible', 'target_completion_date', 'is_verified')
    list_filter = ('company', 'requirement__regulator', 'status', 'priority', 'is_verified', 'target_completion_date')
    search_fields = ('code', 'name', 'description', 'requirement__code', 'requirement__name', 'company__name')
    readonly_fields = ('created_date', 'updated_date', 'created_by', 'verified_date', 'actual_completion_date')
    date_hierarchy = 'target_completion_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('requirement', 'company', 'code', 'name', 'description')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'responsible')
        }),
        ('Dates', {
            'fields': ('target_completion_date', 'actual_completion_date')
        }),
        ('Implementation', {
            'fields': ('implementation_notes', 'evidence_files', 'evidence_notes')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_by', 'verified_date'),
            'classes': ('collapse',)
        }),
        ('Framework Link', {
            'fields': ('related_framework_control',),
            'classes': ('collapse',),
            'description': 'Optional link to related international framework control'
        }),
        ('Audit', {
            'fields': ('created_by', 'created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_in_progress']
    
    def mark_as_completed(self, request, queryset):
        """Позначити як виконано"""
        from django.utils import timezone
        count = queryset.update(status='completed', actual_completion_date=timezone.now().date())
        self.message_user(request, f'{count} controls marked as completed')
    mark_as_completed.short_description = 'Mark as completed'
    
    def mark_as_in_progress(self, request, queryset):
        """Позначити як в процесі"""
        count = queryset.update(status='in_progress')
        self.message_user(request, f'{count} controls marked as in progress')
    mark_as_in_progress.short_description = 'Mark as in progress'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ========================
# Internal Compliance Admin
# ========================

@admin.register(AccessInternalCompliance)
class AccessInternalComplianceAdmin(admin.ModelAdmin):
    list_display = ('group', 'has_access', 'can_view_sources', 'can_edit_sources', 'can_view_requirements', 'can_edit_requirements', 'can_view_controls', 'can_edit_controls', 'can_export', 'can_view_reports', 'companies_list')
    list_filter = ('has_access', 'can_view_sources', 'can_edit_sources', 'can_view_requirements', 'can_edit_requirements', 'can_view_controls', 'can_edit_controls', 'can_export', 'can_view_reports')
    search_fields = ('group__name', 'description')
    filter_horizontal = ('companies',)
    
    fieldsets = (
        ('Group Information', {
            'fields': ('group', 'description')
        }),
        ('Access Rights', {
            'fields': ('has_access',)
        }),
        ('Source Permissions', {
            'fields': ('can_view_sources', 'can_edit_sources', 'can_add_sources', 'can_delete_sources')
        }),
        ('Requirement Permissions', {
            'fields': ('can_view_requirements', 'can_edit_requirements', 'can_add_requirements', 'can_delete_requirements'),
            'description': 'Permissions for managing requirement templates'
        }),
        ('Requirement Instance Permissions', {
            'fields': ('can_view_requirement_instances', 'can_edit_requirement_instances'),
            'description': 'Permissions for viewing and editing requirement instances (applied to companies)'
        }),
        ('Control Permissions', {
            'fields': ('can_view_controls', 'can_edit_controls', 'can_add_controls', 'can_delete_controls'),
            'description': 'Permissions for managing internal compliance controls'
        }),
        ('Evidence & Reports', {
            'fields': ('can_manage_evidence', 'can_approve_evidence', 'can_export', 'can_view_reports')
        }),
        ('Company Access', {
            'fields': ('companies',),
            'description': 'Select companies this group can access. Leave empty for all companies.'
        }),
    )
    
    def companies_list(self, obj):
        """List of companies"""
        companies = obj.companies.all()
        if companies.exists():
            return ', '.join([c.name for c in companies[:3]]) + (f' (+{companies.count() - 3} more)' if companies.count() > 3 else '')
        return 'All companies'
    companies_list.short_description = 'Companies'


@admin.register(InternalComplianceSource)
class InternalComplianceSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'acronym', 'source_type', 'is_active', 'created_date', 'created_by')
    list_filter = ('source_type', 'is_active', 'created_date')
    search_fields = ('name', 'name_local', 'acronym', 'description')
    readonly_fields = ('created_date', 'updated_date', 'created_by')
    filter_horizontal = ('companies', 'company_types')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'name_local', 'acronym', 'source_type', 'description')
        }),
        ('Contact Information', {
            'fields': ('website', 'contact_email', 'contact_phone')
        }),
        ('Display', {
            'fields': ('color',)
        }),
        ('Applicability', {
            'fields': ('companies', 'company_types')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InternalComplianceRequirement)
class InternalComplianceRequirementAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'source', 'is_template', 'requirement_type', 'status', 'priority', 'effective_date', 'deadline_date', 'is_mandatory', 'instances_count')
    list_filter = ('is_template', 'source', 'status', 'requirement_type', 'is_mandatory', 'priority', 'effective_date')
    search_fields = ('code', 'name', 'name_local', 'description', 'applicable_to')
    readonly_fields = ('created_date', 'updated_date', 'created_by', 'controls_count', 'instances_count')
    date_hierarchy = 'effective_date'
    
    fieldsets = (
        ('Template System', {
            'fields': ('is_template', 'template'),
            'description': 'Templates can be applied to multiple companies. Leave template blank for new templates.'
        }),
        ('Basic Information', {
            'fields': ('source', 'code', 'name', 'name_local', 'requirement_type')
        }),
        ('Details', {
            'fields': ('description', 'applicable_to')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'is_mandatory')
        }),
        ('Important Dates', {
            'fields': ('publication_date', 'effective_date', 'deadline_date', 'review_date')
        }),
        ('References', {
            'fields': ('official_link', 'document_file')
        }),
        ('Statistics', {
            'fields': ('controls_count', 'instances_count'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['apply_to_companies', 'mark_as_template']
    
    def controls_count(self, obj):
        """Number of controls"""
        return obj.get_controls_count()
    controls_count.short_description = 'Controls'
    
    def instances_count(self, obj):
        """Number of instances"""
        return obj.get_instances_count()
    instances_count.short_description = 'Instances'
    
    def apply_to_companies(self, request, queryset):
        """Apply templates to companies"""
        templates = queryset.filter(is_template=True)
        if not templates.exists():
            self.message_user(request, 'Please select templates to apply', level='error')
            return
        
        # This would typically show a form to select companies
        # For now, just show a message
        self.message_user(request, f'{templates.count()} templates selected. Use the detail view to apply to companies.')
    apply_to_companies.short_description = 'Apply templates to companies'
    
    def mark_as_template(self, request, queryset):
        """Mark requirements as templates"""
        count = queryset.update(is_template=True)
        self.message_user(request, f'{count} requirements marked as templates')
    mark_as_template.short_description = 'Mark as template'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InternalComplianceControl)
class InternalComplianceControlAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'company', 'requirement', 'status', 'priority', 'responsible', 'target_completion_date', 'is_verified')
    list_filter = ('company', 'requirement__source', 'status', 'priority', 'is_verified', 'target_completion_date')
    search_fields = ('code', 'name', 'description', 'requirement__code', 'requirement__name', 'company__name')
    readonly_fields = ('created_date', 'updated_date', 'created_by', 'verified_date', 'actual_completion_date')
    date_hierarchy = 'target_completion_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('requirement', 'company', 'category', 'code', 'name', 'description')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'status_changed_date')
        }),
        ('Assignment', {
            'fields': ('responsible',)
        }),
        ('Dates', {
            'fields': ('target_completion_date', 'actual_completion_date')
        }),
        ('Implementation', {
            'fields': ('implementation_notes',)
        }),
        ('Evidence', {
            'fields': ('evidence_notes', 'required_evidence_count')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_by', 'verified_date')
        }),
        ('Mapping', {
            'fields': ('related_framework_control',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_in_progress']
    
    def mark_as_completed(self, request, queryset):
        """Mark as completed"""
        from django.utils import timezone
        count = queryset.update(status='completed', actual_completion_date=timezone.now().date())
        self.message_user(request, f'{count} controls marked as completed')
    mark_as_completed.short_description = 'Mark as completed'
    
    def mark_as_in_progress(self, request, queryset):
        """Mark as in progress"""
        count = queryset.update(status='in_progress')
        self.message_user(request, f'{count} controls marked as in progress')
    mark_as_in_progress.short_description = 'Mark as in progress'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AccessControlMapping)
class AccessControlMappingAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'has_access', 'get_companies_count', 'get_companies_list')
    list_filter = ('has_access', 'companies')
    search_fields = ('group__name',)
    filter_horizontal = ('companies',)
    
    fieldsets = (
        (_('Group Access'), {
            'fields': ('group', 'has_access')
        }),
        (_('Companies'), {
            'fields': ('companies',),
            'description': _('Select companies this group can access. Leave empty for all companies.')
        }),
    )
    
    def get_companies_count(self, obj):
        """Кількість компаній"""
        count = obj.companies.count()
        if count == 0:
            return _("All companies")
        return count
    get_companies_count.short_description = _('Companies Count')
    
    def get_companies_list(self, obj):
        """Список компаній"""
        companies = obj.companies.all()[:3]
        if companies:
            names = ", ".join([c.name for c in companies])
            if obj.companies.count() > 3:
                names += f" (+{obj.companies.count() - 3} more)"
            return names
        return _("All companies")
    get_companies_list.short_description = _('Companies')
    
    actions = ['grant_access', 'revoke_access']
    
    def grant_access(self, request, queryset):
        """Надати доступ"""
        count = queryset.update(has_access=True)
        self.message_user(request, _(f'{count} groups granted access'))
    grant_access.short_description = _('Grant access')
    
    def revoke_access(self, request, queryset):
        """Відкликати доступ"""
        count = queryset.update(has_access=False)
        self.message_user(request, _(f'{count} groups access revoked'))
    revoke_access.short_description = _('Revoke access')


# ========================
# Framework Domain Admin
# ========================

@admin.register(FrameworkDomain)
class FrameworkDomainAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'display_order', 'is_active', 'controls_count', 'created_date')
    list_filter = ('is_active', 'created_date')
    search_fields = ('code', 'name', 'description')
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Display Settings', {
            'fields': ('display_order', 'is_active')
        }),
        ('Statistics', {
            'fields': ('controls_count',),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_date', 'updated_date', 'controls_count')
    
    def controls_count(self, obj):
        """Кількість контролів з цим доменом"""
        return Control.objects.filter(domain=obj).count()
    controls_count.short_description = _('Controls Count')


# ========================
# Mandatory Processes Admin
# ========================

class ProcessAttachmentInline(admin.TabularInline):
    model = ProcessAttachment
    extra = 0
    readonly_fields = ['uploaded_at', 'uploaded_by', 'file_size']
    fields = ['file', 'filename', 'description', 'uploaded_at', 'uploaded_by', 'file_size']
    can_delete = True

class ProcessExecutionInline(admin.TabularInline):
    model = ProcessExecution
    extra = 0
    fields = ['execution_date', 'executed_by', 'status', 'notes']
    readonly_fields = ['created_at']
    can_delete = True

@admin.register(MandatoryProcess)
class MandatoryProcessAdmin(admin.ModelAdmin):
    list_display = ['process_name', 'company', 'frequency', 'get_responsible_persons', 'get_additional_persons',
                   'next_due_date', 'priority', 'status_display', 'is_active']
    list_filter = ['company', 'frequency', 'priority', 'is_active', 'groups']
    search_fields = ['process_name', 'description', 'responsible_person__username', 'additional_person__username']
    filter_horizontal = ['groups', 'responsible_person', 'additional_person']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by', 'status_display']
    inlines = [ProcessAttachmentInline, ProcessExecutionInline]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('process_name', 'description', 'company', 'source_document')
        }),
        (_('Scheduling'), {
            'fields': ('frequency', 'next_due_date', 'last_completed_date', 'priority')
        }),
        (_('Assignment'), {
            'fields': ('responsible_person', 'additional_person', 'groups', 'is_active')
        }),
        (_('Status'), {
            'fields': ('status_display',),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    def status_display(self, obj):
        status = obj.status
        colors = {
            'upcoming': 'blue',
            'overdue': 'red', 
            'completed': 'green',
            'in_progress': 'orange'
        }
        color = colors.get(status, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', 
                          color, status.title())
    status_display.short_description = _('Status')
    
    def get_responsible_persons(self, obj):
        """Display responsible persons"""
        return ", ".join([user.get_full_name() or user.username for user in obj.responsible_person.all()])
    get_responsible_persons.short_description = _('Responsible Persons')
    
    def get_additional_persons(self, obj):
        """Display additional persons"""
        return ", ".join([user.get_full_name() or user.username for user in obj.additional_person.all()])
    get_additional_persons.short_description = _('Additional Persons')
    
    def save_model(self, request, obj, form, change):
        """Track who created or updated the record"""
        if not change:  # New object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

class ProcessEvidenceFileInline(admin.TabularInline):
    """Inline для відображення файлів доказів в ProcessExecution"""
    model = ProcessEvidenceFile
    extra = 0
    readonly_fields = ('file_name', 'file_size', 'file_type', 'uploaded_by', 'uploaded_at', 'get_file_size_display', 'is_archive_display')
    fields = ('file', 'file_name', 'get_file_size_display', 'file_type', 'is_archive_display', 'description', 'uploaded_by', 'uploaded_at')
    can_delete = True
    
    def get_file_size_display(self, obj):
        if obj:
            return obj.get_file_size_display()
        return '-'
    get_file_size_display.short_description = _('File Size')
    
    def is_archive_display(self, obj):
        if obj:
            return '✓' if obj.is_archive() else '✗'
        return '-'
    is_archive_display.short_description = _('Is Archive')
    is_archive_display.boolean = True


@admin.register(ProcessExecution)
class ProcessExecutionAdmin(admin.ModelAdmin):
    list_display = ['process', 'execution_date', 'executed_by', 'status', 'notes_preview']
    list_filter = ['status', 'execution_date', 'process']
    search_fields = ['process__process_name', 'executed_by__username', 'notes']
    readonly_fields = ['created_at']
    inlines = [ProcessEvidenceFileInline]
    
    fieldsets = (
        (_('Execution Details'), {
            'fields': ('process', 'execution_date', 'executed_by', 'status')
        }),
        (_('Documentation'), {
            'fields': ('notes', 'evidence_file')
        }),
        (_('Metadata'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def notes_preview(self, obj):
        if obj.notes:
            return obj.notes[:100] + '...' if len(obj.notes) > 100 else obj.notes
        return '-'
    notes_preview.short_description = _('Notes Preview')


@admin.register(ProcessAttachment)
class ProcessAttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'process', 'file_size_formatted', 'uploaded_by', 'uploaded_at']
    list_filter = ['uploaded_at', 'uploaded_by']
    search_fields = ['filename', 'description', 'process__process_name']
    readonly_fields = ['uploaded_at', 'file_size']
    
    fieldsets = (
        (_('File Information'), {
            'fields': ('file', 'filename', 'description')
        }),
        (_('Process'), {
            'fields': ('process',)
        }),
        (_('Upload Information'), {
            'fields': ('uploaded_by', 'uploaded_at', 'file_size'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set uploaded_by on creation
            obj.uploaded_by = request.user
            if obj.file:
                obj.file_size = obj.file.size
        super().save_model(request, obj, form, change)


@admin.register(ProcessEvidenceFile)
class ProcessEvidenceFileAdmin(admin.ModelAdmin):
    """Admin для управління файлами доказів виконання процесів"""
    list_display = ('file_name', 'execution', 'file_type', 'get_file_size_display', 'is_archive_display', 'uploaded_by', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at', 'execution__process')
    search_fields = ('file_name', 'execution__process__process_name', 'description')
    readonly_fields = ('file_name', 'file_size', 'file_type', 'uploaded_by', 'uploaded_at', 'get_file_size_display', 'is_archive_display')
    fieldsets = (
        (_('File Information'), {
            'fields': ('execution', 'file', 'file_name', 'file_type', 'file_size', 'get_file_size_display', 'is_archive_display')
        }),
        (_('Metadata'), {
            'fields': ('description', 'uploaded_by', 'uploaded_at')
        }),
    )
    
    def get_file_size_display(self, obj):
        if obj:
            return obj.get_file_size_display()
        return '-'
    get_file_size_display.short_description = _('File Size')
    
    def is_archive_display(self, obj):
        if obj:
            return '✓' if obj.is_archive() else '✗'
        return '-'
    is_archive_display.short_description = _('Is Archive')
    is_archive_display.boolean = True


class MandatoryProcessesGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MandatoryProcessesGuideTranslationInline(MandatoryProcessesGuideTranslationInlineMixin, admin.StackedInline):
    model = MandatoryProcessesGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/mandatory_processes_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(MandatoryProcessesGuide)
class MandatoryProcessesGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [MandatoryProcessesGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_compliance/mandatoryprocessesguide/change_form.html'

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
            extra_context['mandatory_processes_guide_translate_url'] = reverse('compliance:mandatory_processes_guide_translate')
        except Exception:
            extra_context['mandatory_processes_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['mandatory_processes_guide_translate_url'] = reverse('compliance:mandatory_processes_guide_translate')
        except Exception:
            extra_context['mandatory_processes_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class LocalComplianceGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class LocalComplianceGuideTranslationInline(LocalComplianceGuideTranslationInlineMixin, admin.StackedInline):
    model = LocalComplianceGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/local_compliance_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(LocalComplianceGuide)
class LocalComplianceGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [LocalComplianceGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_compliance/localcomplianceguide/change_form.html'

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
            extra_context['local_compliance_guide_translate_url'] = reverse('compliance:local_compliance_guide_translate')
        except Exception:
            extra_context['local_compliance_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['local_compliance_guide_translate_url'] = reverse('compliance:local_compliance_guide_translate')
        except Exception:
            extra_context['local_compliance_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class InternalComplianceGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class InternalComplianceGuideTranslationInline(InternalComplianceGuideTranslationInlineMixin, admin.StackedInline):
    model = InternalComplianceGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/internal_compliance_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(InternalComplianceGuide)
class InternalComplianceGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [InternalComplianceGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_compliance/internalcomplianceguide/change_form.html'

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
            extra_context['internal_compliance_guide_translate_url'] = reverse('compliance:internal_compliance_guide_translate')
        except Exception:
            extra_context['internal_compliance_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['internal_compliance_guide_translate_url'] = reverse('compliance:internal_compliance_guide_translate')
        except Exception:
            extra_context['internal_compliance_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class FrameworkComplianceGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class FrameworkComplianceGuideTranslationInline(FrameworkComplianceGuideTranslationInlineMixin, admin.StackedInline):
    model = FrameworkComplianceGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/framework_compliance_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(FrameworkComplianceGuide)
class FrameworkComplianceGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [FrameworkComplianceGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_compliance/frameworkcomplianceguide/change_form.html'

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
            extra_context['framework_compliance_guide_translate_url'] = reverse('compliance:framework_compliance_guide_translate')
        except Exception:
            extra_context['framework_compliance_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['framework_compliance_guide_translate_url'] = reverse('compliance:framework_compliance_guide_translate')
        except Exception:
            extra_context['framework_compliance_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)
