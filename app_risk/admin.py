from django.contrib import admin
from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    AccessRisk, RiskLevel, RiskLevelTranslation, Threat, ThreatTranslation, Vulnerability, VulnerabilityTranslation, AssetVulnerability, RiskTreatment,
    Treatment_type, TreatmentTypeTranslation, Treatment_status, TreatmentStatusTranslation, ScheduledReport, ScheduledReportExecution, 
    ScheduledReportAttachment, ReportProfile, RiskReportEmailConfig,
    FinancialImpact, FinancialImpactTranslation, OperationalImpact, OperationalImpactTranslation, ReputationalImpact, ReputationalImpactTranslation, AcceptableRisk,
    RiskTreatmentAttachment, ManualRiskLevelOverride, RiskTreatmentHistory,
    RiskAssessmentConfigGuide, RiskAssessmentConfigGuideTranslation,
    RiskAssessmentGuide, RiskAssessmentGuideTranslation,
    RiskReportGuide, RiskReportGuideTranslation
)
from django.utils.translation import gettext_lazy as _
from app_conf.models import Country
from tinymce.widgets import TinyMCE
from tinymce.models import HTMLField


class ActiveCountryInlineMixin:
    """Mixin to limit country choices to active records (same as app_keycert/app_doc)."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# Custom admin site for better organization
class RiskAssessmentAdminSite(admin.AdminSite):
    site_header = _('Risk Assessment Administration')
    site_title = _('Risk Assessment Admin')
    index_title = _('Risk Assessment Management')
    
    def get_app_list(self, request):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_list = super().get_app_list(request)
        
        # Reorganize the app list to group impact-related models
        for app in app_list:
            if app['app_label'] == 'app_risk':
                # Group impact models together
                impact_models = []
                other_models = []
                
                for model in app['models']:
                    if 'impact' in model['object_name'].lower():
                        impact_models.append(model)
                    else:
                        other_models.append(model)
                
                # Sort impact models by name
                impact_models.sort(key=lambda x: x['name'])
                other_models.sort(key=lambda x: x['name'])
                
                # Reorder models: threats first, then impacts, then others
                app['models'] = []
                
                # Add threats first
                threat_models = [m for m in other_models if 'threat' in m['object_name'].lower()]
                app['models'].extend(threat_models)
                
                # Add impact models
                app['models'].extend(impact_models)
                
                # Add remaining models
                remaining_models = [m for m in other_models if 'threat' not in m['object_name'].lower()]
                app['models'].extend(remaining_models)
        
        return app_list

# Create custom admin site instance
risk_admin_site = RiskAssessmentAdminSite(name='risk_admin')


# Register your models here.
class ThreatTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = ThreatTranslation
    extra = 1
    fields = ('country', 'name_local', 'description', 'risks')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


class ThreatAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_name_display', 'code', 'probability_scenario', 'probability', 'impact', 'calculated_risk', 'get_overall_impact_display', 'translations_count', 'is_active']
    list_filter = ['probability_scenario', 'financial_impact', 'operational_impact', 'reputational_impact', 'is_active']
    search_fields = ['name', 'code', 'name_local', 'translations__name_local', 'description']
    readonly_fields = ['calculated_risk', 'overall_impact_value', 'impact']
    list_editable = ['probability', 'is_active']
    actions = ['recalculate_risks', 'export_threats_data', 'populate_default_impact_levels']
    inlines = [ThreatTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',)
        }),
        (_('Risks'), {
            'fields': ('risks',),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',)
        }),
        (_('Probability'), {
            'fields': ('probability_scenario', 'scenario_m', 'scenario_n', 'probability'),
            'description': _('Set the probability scenario and values for risk calculation')
        }),
        (_('Impact Assessment'), {
            'fields': ('impact', 'financial_impact', 'operational_impact', 'reputational_impact', 'overall_impact_value', 'calculated_risk'),
            'description': _('Configure detailed impact assessment using the new methodology. The Impact field is automatically calculated and saved when Financial, Operational, or Reputational impacts are set. The overall impact is calculated as the average of the three impact types.')
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )

    def calculated_risk(self, obj):
        """Calculate risk using the new threat impact method if available"""
        if hasattr(obj, 'calculate_threat_impact'):
            return obj.calculate_threat_impact()
        return obj.probability * obj.impact
    calculated_risk.short_description = _('Calculated Risk')

    def overall_impact_value(self, obj):
        """Display the calculated overall impact value"""
        if hasattr(obj, 'calculate_overall_impact'):
            return f"{obj.calculate_overall_impact():.3f}"
        return _('Not calculated')
    overall_impact_value.short_description = _('Overall Impact (E)')

    def impact(self, obj):
        """Display the calculated impact value with explanation"""
        if obj.financial_impact or obj.operational_impact or obj.reputational_impact:
            calculated_value = obj.calculate_threat_impact()
            return f"{calculated_value:.2f} (Auto-calculated)"
        return f"{obj.impact:.2f}"
    impact.short_description = _('Impact (Auto-calculated)')

    def get_overall_impact_display(self, obj):
        """Display overall impact with color coding"""
        if hasattr(obj, 'calculate_overall_impact'):
            impact_value = obj.calculate_overall_impact()
            if impact_value <= 0.2:
                color = 'green'
                level = _('Low')
            elif impact_value <= 0.5:
                color = 'orange'
                level = _('Medium')
            elif impact_value <= 0.8:
                color = 'red'
                level = _('High')
            else:
                color = 'darkred'
                level = _('Critical')
            
            return f'<span style="color: {color}; font-weight: bold;">{level} ({impact_value:.3f})</span>'
        return _('Not set')
    get_overall_impact_display.short_description = _('Overall Impact Level (E)')
    get_overall_impact_display.allow_tags = True

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or _('Unnamed')
    get_name_display.short_description = _('Threat Name')

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
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('financial_impact', 'operational_impact', 'reputational_impact')
        return queryset

    def recalculate_risks(self, request, queryset):
        """Recalculate risks for selected threats"""
        updated_count = 0
        for threat in queryset:
            # Force recalculation by accessing the calculated fields
            threat.calculated_risk
            updated_count += 1
        
        self.message_user(request, _('Successfully recalculated risks for %d threat(s).') % updated_count)
    recalculate_risks.short_description = _('Recalculate risks for selected threats')

    def export_threats_data(self, request, queryset):
        """Export threats data to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="threats_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Name (UK)', 'Name (EN)', 'Name (RU)', 
            'Probability Scenario', 'Probability', 'Impact',
            'Financial Impact', 'Operational Impact', 'Reputational Impact',
            'Overall Impact', 'Calculated Risk'
        ])
        
        for threat in queryset:
            overall_impact = threat.calculate_overall_impact() if hasattr(threat, 'calculate_overall_impact') else 0
            calculated_risk = threat.calculate_threat_impact() if hasattr(threat, 'calculate_threat_impact') else threat.probability * threat.impact
            
            writer.writerow([
                threat.id,
                threat.get_name(),
                threat.get_name_by_language('uk'),
                threat.get_name_by_language('en'),
                threat.get_name_by_language('ru'),
                threat.probability_scenario,
                threat.probability,
                threat.impact,
                threat.financial_impact.get_name() if threat.financial_impact else '',
                threat.operational_impact.get_name() if threat.operational_impact else '',
                threat.reputational_impact.get_name() if threat.reputational_impact else '',
                f"{overall_impact:.3f}",
                f"{calculated_risk:.3f}"
            ])
        
        return response
    export_threats_data.short_description = _('Export selected threats to CSV')


# Admin actions for impact management
def populate_default_impact_levels(modeladmin, request, queryset):
    """Populate default impact levels if none exist"""
    from .management.commands.populate_impact_levels import Command
    
    # Check if any impact levels exist
    if (FinancialImpact.objects.count() == 0 and 
        OperationalImpact.objects.count() == 0 and 
        ReputationalImpact.objects.count() == 0):
        
        # Run the populate command
        command = Command()
        command.handle()
        
        modeladmin.message_user(request, _('Default impact levels have been populated successfully.'))
    else:
        modeladmin.message_user(request, _('Impact levels already exist. Use the management command to repopulate if needed.'))
populate_default_impact_levels.short_description = _('Populate default impact levels')


# Impact Settings Summary Dashboard
class ImpactSettingsSummary(admin.ModelAdmin):
    """Summary dashboard for impact settings"""
    
    def changelist_view(self, request, extra_context=None):
        # Get summary statistics
        from django.db.models import Count, Avg
        
        financial_impacts = FinancialImpact.objects.count()
        operational_impacts = OperationalImpact.objects.count()
        reputational_impacts = ReputationalImpact.objects.count()
        
        threats_with_impacts = Threat.objects.filter(
            models.Q(financial_impact__isnull=False) |
            models.Q(operational_impact__isnull=False) |
            models.Q(reputational_impact__isnull=False)
        ).count()
        
        total_threats = Threat.objects.count()
        
        # Get impact value ranges
        financial_range = FinancialImpact.objects.aggregate(
            min_impact=Avg('impact_value'),
            max_impact=Avg('impact_value')
        )
        
        operational_range = OperationalImpact.objects.aggregate(
            min_impact=Avg('impact_value'),
            max_impact=Avg('impact_value')
        )
        
        reputational_range = ReputationalImpact.objects.aggregate(
            min_impact=Avg('impact_value'),
            max_impact=Avg('impact_value')
        )
        
        summary_data = {
            'financial_impacts': financial_impacts,
            'operational_impacts': operational_impacts,
            'reputational_impacts': reputational_impacts,
            'threats_with_impacts': threats_with_impacts,
            'total_threats': total_threats,
            'impact_coverage': f"{(threats_with_impacts / total_threats * 100):.1f}%" if total_threats > 0 else "0%",
            'financial_range': financial_range,
            'operational_range': operational_range,
            'reputational_range': reputational_range,
        }
        
        extra_context = extra_context or {}
        extra_context['summary_data'] = summary_data
        
        return super().changelist_view(request, extra_context)


class FinancialImpactTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = FinancialImpactTranslation
    extra = 1
    fields = ('country', 'name_local', 'description', 'criteria', 'examples')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(FinancialImpact)
class FinancialImpactAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'get_value_range', 'impact_value', 'color', 'translations_count', 'is_active']
    list_editable = ['color', 'is_active']
    list_filter = ['impact_value', 'is_active']
    search_fields = ['name', 'code', 'name_local', 'translations__name_local', 'description']
    ordering = ['min_value']
    actions = ['duplicate_impact', 'export_impact_data']
    inlines = [FinancialImpactTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Financial Values'), {
            'fields': ('min_value', 'max_value', 'impact_value'),
            'description': _('Set the financial impact range in UAH and corresponding impact value (0-1)')
        }),
        (_('Visualization'), {
            'fields': ('color',),
            'description': _('Choose a color for visual representation (hex format, e.g., #FF0000)')
        }),
        (_('Description, Criteria & Examples'), {
            'fields': ('description', 'criteria', 'examples'),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or _('Unnamed')
    get_name_display.short_description = _('Financial Impact Level')

    def get_value_range(self, obj):
        """Display the value range in a formatted way"""
        return f"{obj.min_value:,.0f} - {obj.max_value:,.0f} UAH"
    get_value_range.short_description = _('Value Range')

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

    def duplicate_impact(self, request, queryset):
        """Duplicate selected financial impact levels"""
        duplicated_count = 0
        for impact in queryset:
            impact.pk = None
            impact.name = f"{impact.name} (Copy)" if impact.name else ""
            impact.code = ""
            impact.save()
            duplicated_count += 1

        self.message_user(request, _('Successfully duplicated %d financial impact level(s).') % duplicated_count)
    duplicate_impact.short_description = _('Duplicate selected financial impact levels')

    def export_impact_data(self, request, queryset):
        """Export impact data to CSV"""
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="financial_impacts.csv"'

        writer = csv.writer(response)
        writer.writerow(['Name', 'Code', 'Name (UK)', 'Name (EN)', 'Name (RU)', 'Min Value', 'Max Value', 'Impact Value', 'Color'])

        for impact in queryset:
            writer.writerow([
                impact.get_name(),
                impact.code,
                impact.get_name_by_language('uk'),
                impact.get_name_by_language('en'),
                impact.get_name_by_language('ru'),
                impact.min_value,
                impact.max_value,
                impact.impact_value,
                impact.color
            ])

        return response
    export_impact_data.short_description = _('Export selected to CSV')


class OperationalImpactTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = OperationalImpactTranslation
    extra = 1
    fields = ('country', 'name_local', 'description', 'criteria', 'examples')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(OperationalImpact)
class OperationalImpactAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'get_downtime_range', 'impact_value', 'color', 'translations_count', 'is_active']
    list_editable = ['color', 'is_active']
    list_filter = ['impact_value', 'is_active']
    search_fields = ['name', 'code', 'name_local', 'translations__name_local', 'description']
    ordering = ['min_downtime_hours']
    actions = ['duplicate_impact', 'export_impact_data']
    inlines = [OperationalImpactTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Downtime Values'), {
            'fields': ('min_downtime_hours', 'max_downtime_hours', 'impact_value'),
            'description': _('Set the operational downtime range in hours and corresponding impact value (0-1)')
        }),
        (_('Visualization'), {
            'fields': ('color',),
            'description': _('Choose a color for visual representation (hex format, e.g., #FF0000)')
        }),
        (_('Description, Criteria & Examples'), {
            'fields': ('description', 'criteria', 'examples'),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or _('Unnamed')
    get_name_display.short_description = _('Operational Impact Level')

    def get_downtime_range(self, obj):
        return f"{obj.min_downtime_hours} - {obj.max_downtime_hours} hours"
    get_downtime_range.short_description = _('Downtime Range')

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')

    def duplicate_impact(self, request, queryset):
        duplicated_count = 0
        for impact in queryset:
            impact.pk = None
            impact.name = f"{impact.name} (Copy)" if impact.name else ""
            impact.code = ""
            impact.save()
            duplicated_count += 1
        self.message_user(request, _('Successfully duplicated %d operational impact level(s).') % duplicated_count)
    duplicate_impact.short_description = _('Duplicate selected operational impact levels')

    def export_impact_data(self, request, queryset):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="operational_impacts.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Code', 'Name (UK)', 'Name (EN)', 'Name (RU)', 'Min Downtime', 'Max Downtime', 'Impact Value', 'Color'])
        for impact in queryset:
            writer.writerow([
                impact.get_name(),
                impact.code,
                impact.get_name_by_language('uk'),
                impact.get_name_by_language('en'),
                impact.get_name_by_language('ru'),
                impact.min_downtime_hours,
                impact.max_downtime_hours,
                impact.impact_value,
                impact.color
            ])
        return response
    export_impact_data.short_description = _('Export selected to CSV')


class ReputationalImpactTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = ReputationalImpactTranslation
    extra = 1
    fields = ('country', 'name_local', 'description', 'criteria', 'examples')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(ReputationalImpact)
class ReputationalImpactAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'impact_value', 'color', 'get_impact_level', 'translations_count', 'is_active']
    list_editable = ['color', 'is_active']
    list_filter = ['impact_value', 'is_active']
    search_fields = ['name', 'code', 'description', 'translations__name_local']
    ordering = ['impact_value']
    actions = ['duplicate_impact', 'export_impact_data']
    inlines = [ReputationalImpactTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Impact Value'), {
            'fields': ('impact_value',),
            'description': _('Set the reputational impact value (0-1) for calculations')
        }),
        (_('Visualization'), {
            'fields': ('color',),
            'description': _('Choose a color for visual representation (hex format, e.g., #FF0000)')
        }),
        (_('Description, Criteria & Examples'), {
            'fields': ('description', 'criteria', 'examples'),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '—'
    get_name_display.short_description = _('Reputational Impact Level')

    def get_impact_level(self, obj):
        if obj.impact_value <= 0.2:
            return _('Low')
        elif obj.impact_value <= 0.5:
            return _('Medium')
        elif obj.impact_value <= 0.8:
            return _('High')
        return _('Critical')
    get_impact_level.short_description = _('Impact Level')

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')

    def duplicate_impact(self, request, queryset):
        duplicated_count = 0
        for impact in queryset:
            impact.pk = None
            impact.name = f"{impact.name or impact.name_local} (Copy)" if (impact.name or impact.name_local) else ""
            impact.name_local = ""
            impact.code = ""
            impact.save()
            duplicated_count += 1
        self.message_user(request, _('Successfully duplicated %d reputational impact level(s).') % duplicated_count)
    duplicate_impact.short_description = _('Duplicate selected reputational impact levels')

    def export_impact_data(self, request, queryset):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="reputational_impacts.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Code', 'Name (UK)', 'Name (EN)', 'Name (RU)', 'Impact Value', 'Color'])
        for impact in queryset:
            writer.writerow([
                impact.get_name(),
                impact.code,
                impact.get_name_by_language('uk'),
                impact.get_name_by_language('en'),
                impact.get_name_by_language('ru'),
                impact.impact_value,
                impact.color
            ])
        return response
    export_impact_data.short_description = _('Export selected to CSV')



@admin.register(AccessRisk)
class AccessRiskAdmin(admin.ModelAdmin):
    list_display = [
        'group',
        'has_access_assessment',
        'can_edit_assessment',
        'has_access_report',
        'can_edit_report',
        'has_access_config',
        'can_edit_config',
        'display_companies'
    ]
    list_editable = [
        'has_access_assessment',
        'can_edit_assessment',
        'has_access_report',
        'can_edit_report',
        'has_access_config',
        'can_edit_config'
    ]
    list_filter = [
        'has_access_assessment',
        'can_edit_assessment',
        'has_access_report',
        'can_edit_report',
        'has_access_config',
        'can_edit_config',
        'companies'
    ]
    search_fields = ['group__name', 'companies__name', 'description']
    filter_horizontal = ['companies']
    
    fieldsets = (
        (_('Group'), {
            'fields': ('group',)
        }),
        (_('Risk Assessment Permissions'), {
            'fields': (
                'has_access_assessment',
                'can_edit_assessment',
                'can_config_assessment',
            )
        }),
        (_('Risk Report Permissions'), {
            'fields': (
                'has_access_report',
                'can_add_report',
                'can_edit_report',
                'can_delete_report',
            )
        }),
        (_('Risk Configuration Permissions'), {
            'fields': (
                'has_access_config',
                'can_add_config',
                'can_edit_config',
                'can_delete_config',
            )
        }),
        (_('Companies and Description'), {
            'fields': (
                'companies',
                'description',
            )
        })
    )

    def display_companies(self, obj):
        return ", ".join([company.name for company in obj.companies.all()])
    display_companies.short_description = _("Companies")


class CriticalityLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'cost', 'color')
    search_fields = ('name',)

class RiskLevelTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = RiskLevelTranslation
    extra = 1
    fields = ('country', 'name_local')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(RiskLevel)
class RiskLevelAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'company', 'code', 'min_value', 'max_value', 'color', 'translations_count', 'is_active']
    list_editable = ['color', 'is_active']
    list_filter = ['is_active', 'company']
    search_fields = ['name', 'code', 'company__name', 'translations__name_local']
    inlines = [RiskLevelTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'company', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Values'), {
            'fields': ('min_value', 'max_value'),
            'description': _('Value range for this risk level (0 to 200)')
        }),
        (_('Display'), {
            'fields': ('color',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or '—'
    get_name_display.short_description = _('Risk Level')

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


@admin.register(ManualRiskLevelOverride)
class ManualRiskLevelOverrideAdmin(admin.ModelAdmin):
    list_display = ['asset', 'vulnerability', 'threat', 'manual_risk_level', 'created_by', 'created_at']
    list_filter = ['manual_risk_level', 'created_at', 'asset__company']
    search_fields = ['asset__name', 'vulnerability__name', 'threat__name', 'threat__translations__name_local', 'justification']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Asset Information', {
            'fields': ('asset', 'vulnerability', 'threat')
        }),
        ('Risk Level Override', {
            'fields': ('manual_risk_level', 'justification')
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class VulnerabilityTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = VulnerabilityTranslation
    extra = 1
    fields = ('country', 'name_local', 'description', 'scope', 'risk_mitigation_controls', 'pci_dss_requirement', 'iso27001_requirement', 'note')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            from django.db.models import Q
            qs = Country.objects.filter(is_active=True).order_by('display_order', 'name')
            object_id = request.resolver_match.kwargs.get('object_id')
            if object_id:
                used_ids = VulnerabilityTranslation.objects.filter(
                    vulnerability_id=object_id
                ).values_list('country_id', flat=True).distinct()
                if used_ids:
                    qs = Country.objects.filter(
                        Q(is_active=True) | Q(pk__in=list(used_ids))
                    ).order_by('display_order', 'name')
            kwargs['queryset'] = qs
            return super(ActiveCountryInlineMixin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class VulnerabilityAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'asset_group', 'asset_type', 'translations_count', 'is_active']
    list_editable = ['is_active']
    list_filter = ['asset_group', 'asset_type', 'is_active']
    search_fields = ['name', 'code', 'description', 'scope', 'translations__name_local']
    inlines = [VulnerabilityTranslationInline]
    exclude = ('name_local',)
    filter_horizontal = ('threats',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code', 'asset_group', 'asset_type'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',),
        }),
        (_('Scope & Controls'), {
            'fields': ('scope', 'risk_mitigation_controls', 'pci_dss_requirement', 'iso27001_requirement', 'note'),
            'description': _('Default. For other languages use the Translations inline below.'),
            'classes': ('collapse',),
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Threats'), {
            'fields': ('threats',)
        }),
    )

    def get_name_display(self, obj):
        return (obj.get_name() or obj.name or '')[:60]
    get_name_display.short_description = _('Vulnerability')

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


class TreatmentTypeTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = TreatmentTypeTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


class Treatment_typeAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'color', 'translations_count', 'is_active']
    list_editable = ['color', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'name_local', 'translations__name_local']
    inlines = [TreatmentTypeTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',),
        }),
        (_('Display'), {
            'fields': ('color',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or _('Unnamed')
    get_name_display.short_description = _('Treatment Type')

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')


class TreatmentStatusTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = TreatmentStatusTranslation
    extra = 1
    fields = ('country', 'name_local', 'description')
    autocomplete_fields = ['country']

    class Media:
        js = ('admin/js/translation_helper.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


class Treatment_statusAdmin(admin.ModelAdmin):
    list_display = ['get_name_display', 'code', 'color', 'translations_count', 'is_active']
    list_editable = ['color', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'name_local', 'translations__name_local']
    inlines = [TreatmentStatusTranslationInline]
    exclude = ('name_local',)

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'code'),
            'description': _('Default: English (En). For Ukrainian, Russian and other languages use the Translations inline below.'),
        }),
        (_('Description'), {
            'fields': ('description',),
            'description': _('Default: English (En). For other languages use the Translations inline below.'),
            'classes': ('collapse',),
        }),
        (_('Display'), {
            'fields': ('color',)
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
    )

    def get_name_display(self, obj):
        return obj.get_name() or obj.name or _('Unnamed')
    get_name_display.short_description = _('Treatment Status')

    def translations_count(self, obj):
        count = obj.translations.count()
        if count > 0:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
                count
            )
        return '-'
    translations_count.short_description = _('Translations')

class RiskTreatmentAdmin(admin.ModelAdmin):
    list_display = ('asset', 'vulnerability', 'treatment_type', 'status', 'deadline', 'last_modified')
    list_filter = ('treatment_type', 'status', 'deadline')
    search_fields = ('asset__name', 'asset__asset_id', 'vulnerability__name')
    raw_id_fields = ('asset', 'vulnerability', 'highest_risk_level')
    date_hierarchy = 'last_modified'


class RiskTreatmentHistoryAdmin(admin.ModelAdmin):
    list_display = ('treatment', 'field_name', 'old_value', 'new_value', 'changed_at', 'changed_by')
    list_filter = ('field_name', 'changed_at', 'changed_by')
    search_fields = ('treatment__asset__name', 'treatment__vulnerability__name', 'change_reason')
    readonly_fields = ('treatment', 'field_name', 'old_value', 'new_value', 'old_value_display', 'new_value_display', 'old_value_id', 'new_value_id', 'changed_at', 'changed_by', 'change_reason', 'ip_address', 'user_agent')
    date_hierarchy = 'changed_at'
    ordering = ('-changed_at',)

admin.site.register(Threat, ThreatAdmin)
admin.site.register(Vulnerability, VulnerabilityAdmin)
admin.site.register(Treatment_type, Treatment_typeAdmin)
admin.site.register(Treatment_status, Treatment_statusAdmin)
admin.site.register(RiskTreatment, RiskTreatmentAdmin)
admin.site.register(RiskTreatmentHistory, RiskTreatmentHistoryAdmin)


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'frequency', 'status', 'company', 'next_run_local', 'created_by']
    list_filter = ['report_type', 'frequency', 'status', 'company']
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at', 'last_run', 'next_run', 'run_count']
    filter_horizontal = ['email_recipients']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'description', 'status')
        }),
        (_('Report Configuration'), {
            'fields': ('report_type', 'report_language', 'company')
        }),
        (_('Scheduling'), {
            'fields': ('frequency', 'start_date', 'end_date', 'execution_time')
        }),
        (_('Weekly Schedule'), {
            'fields': ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'),
            'classes': ('collapse',)
        }),
        (_('Monthly Schedule'), {
            'fields': ('day_of_month',),
            'classes': ('collapse',)
        }),
        # Email settings moved to global admin (RiskReportEmailConfig)
        (_('Audit Information'), {
            'fields': ('created_by', 'created_at', 'updated_at', 'last_run', 'next_run', 'run_count'),
            'classes': ('collapse',)
        }),
    )
    
    def next_run_local(self, obj):
        """Display next run time in local timezone"""
        if obj.next_run:
            return obj.next_run.astimezone().strftime('%Y-%m-%d %H:%M')
        return _('Not scheduled')
    next_run_local.short_description = _('Next Run (Local)')
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ScheduledReportExecution)
class ScheduledReportExecutionAdmin(admin.ModelAdmin):
    list_display = ['scheduled_report', 'status', 'started_at_local', 'completed_at_local', 'email_sent', 'file_size']
    list_filter = ['status', 'email_sent', 'started_at']
    search_fields = ['scheduled_report__name', 'error_message']
    readonly_fields = ['started_at', 'completed_at', 'file_size']
    
    def started_at_local(self, obj):
        """Display started time in local timezone"""
        if obj.started_at:
            return obj.started_at.astimezone().strftime('%Y-%m-%d %H:%M')
        return ''
    started_at_local.short_description = _('Started At (Local)')
    
    def completed_at_local(self, obj):
        """Display completed time in local timezone"""
        if obj.completed_at:
            return obj.completed_at.astimezone().strftime('%Y-%m-%d %H:%M')
        return ''
    completed_at_local.short_description = _('Completed At (Local)')


@admin.register(ScheduledReportAttachment)
class ScheduledReportAttachmentAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'scheduled_report', 'file_size_display', 'uploaded_by', 'uploaded_at']
    list_filter = ['uploaded_at', 'scheduled_report']
    search_fields = ['original_filename', 'scheduled_report__name', 'uploaded_by__username']
    readonly_fields = ['uploaded_at', 'file_size']
    
    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = _('File Size')


@admin.register(RiskReportEmailConfig)
class RiskReportEmailConfigAdmin(admin.ModelAdmin):
    list_display = ['send_email', 'use_default_email_settings', 'mail_server', 'mail_account', 'updated_at']
    fieldsets = (
        (_('Global Email Settings for Risk Reports'), {
            'fields': ('send_email', 'use_default_email_settings', 'mail_server', 'mail_account', 'default_subject', 'default_body')
        }),
        (_('Meta'), {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['updated_at']
    actions = ['send_test_email_to_me']

    def has_add_permission(self, request):
        # Enforce singleton: allow add only if none exists
        return RiskReportEmailConfig.objects.count() == 0

    def send_test_email_to_me(self, request, queryset):
        """Admin action: send a test email using current global settings to the current user's email."""
        from django.contrib import messages
        from django.core.mail import EmailMessage
        import smtplib
        import ssl
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # Validate selection
        config = queryset.first() if queryset.exists() else RiskReportEmailConfig.objects.first()
        if not config:
            messages.error(request, _('No configuration found.'))
            return

        recipient = request.user.email
        if not recipient:
            messages.error(request, _('Your user has no email. Please set your email in the user profile.'))
            return

        if not config.send_email:
            messages.warning(request, _('Global setting "Send Email" is disabled. Enable it to test.'))
            # Continue anyway to test connectivity

        subject = f"Test: {config.default_subject or 'Risk Assessment Report'}"
        body = (config.default_body or 'Please view your report at the link below.')
        body += '\n\nThis is a test email from Risk Report Email Settings.'

        try:
            # Always prefer direct SMTP via selected Mail Account for test sends if available
            if config.mail_account:
                smtp_host = config.mail_account.server.smtp_host
                smtp_port = config.mail_account.server.smtp_port
                use_ssl = getattr(config.mail_account.server, 'use_ssl', False)
                use_tls = getattr(config.mail_account.server, 'use_tls', False)
                username = config.mail_account.username
                password = config.mail_account.password

                msg = MIMEMultipart()
                msg['From'] = username
                msg['To'] = recipient
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))

                if use_ssl:
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    server = smtplib.SMTP_SSL(host=smtp_host, port=smtp_port, context=context)
                else:
                    server = smtplib.SMTP(host=smtp_host, port=smtp_port)
                    if use_tls:
                        server.starttls()

                server.login(username, password)
                server.send_message(msg)
                server.quit()
            else:
                from_email = config.mail_account.username if config.mail_account else None
                email = EmailMessage(subject=subject, body=body, from_email=from_email, to=[recipient])
                email.send(fail_silently=False)

            messages.success(request, _('Test email sent to {}').format(recipient))
        except Exception as e:
            messages.error(request, _('Failed to send test email: {}').format(str(e)))

    send_test_email_to_me.short_description = _('Send test email to me')

@admin.register(ReportProfile)
class ReportProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'profile_type', 'created_by', 'is_active', 'is_public', 'usage_count', 'last_used_at']
    list_filter = ['profile_type', 'is_active', 'is_public', 'created_at']
    search_fields = ['name', 'description', 'created_by__username', 'created_by__first_name', 'created_by__last_name']
    readonly_fields = ['created_at', 'updated_at', 'last_used_at', 'usage_count']
    filter_horizontal = ['allowed_users']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'description', 'profile_type', 'is_active')
        }),
        (_('Ownership and Sharing'), {
            'fields': ('created_by', 'is_public', 'allowed_users')
        }),
        (_('Default Settings'), {
            'fields': ('default_format', 'default_language')
        }),
        (_('Sections Configuration'), {
            'fields': ('sections_config',),
            'description': _('JSON configuration of enabled/disabled report sections. Use the web interface for easier editing.')
        }),
        (_('Usage Statistics'), {
            'fields': ('usage_count', 'last_used_at'),
            'classes': ('collapse',)
        }),
        (_('Audit Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Filter queryset based on user permissions"""
        qs = super().get_queryset(request)
        
        # Superusers can see all profiles
        if request.user.is_superuser:
            return qs
        
        # Regular users can see:
        # 1. Their own profiles
        # 2. System profiles
        # 3. Public profiles from their company
        # 4. Profiles they're specifically allowed to use
        user_company = None
        try:
            user_company = request.user.cabinetuser.company
        except:
            pass
        
        from django.db.models import Q
        query = Q(created_by=request.user)  # Own profiles
        query |= Q(profile_type='system')  # System profiles
        
        # if user_company:
        #     query |= Q(is_public=True, company=user_company)  # Public profiles in same company
        
        query |= Q(allowed_users=request.user)  # Specifically allowed profiles
        
        return qs.filter(query).distinct()
    
    def save_model(self, request, obj, form, change):
        """Set created_by and company for new profiles"""
        if not change:  # Creating new object
            obj.created_by = request.user
            
            # Set company for user profiles if user has a company
            # if obj.profile_type in ['user', 'shared']:
            #     try:
            #         user_company = request.user.cabinetuser.company
            #         if user_company:
            #             obj.company = user_company
            #     except:
            #         pass
        
        super().save_model(request, obj, form, change)
    
    def has_change_permission(self, request, obj=None):
        """Check if user can change this profile"""
        if not obj:
            return super().has_change_permission(request, obj)
        
        # Superusers can edit all profiles
        if request.user.is_superuser:
            return True
        
        # Users can edit their own profiles
        if obj.created_by == request.user:
            return True
        
        # System profiles can only be edited by superusers
        if obj.profile_type == 'system':
            return False
        
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Check if user can delete this profile"""
        if not obj:
            return super().has_delete_permission(request, obj)
        
        # Superusers can delete all profiles except system profiles
        if request.user.is_superuser:
            return obj.profile_type != 'system'
        
        # Users can delete their own profiles (except system profiles)
        if obj.created_by == request.user and obj.profile_type != 'system':
            return True
        
        return False
    
    actions = ['duplicate_profile', 'activate_profiles', 'deactivate_profiles']
    
    def duplicate_profile(self, request, queryset):
        """Duplicate selected profiles"""
        duplicated_count = 0
        for profile in queryset:
            if profile.can_be_used_by(request.user):
                # Create a copy
                new_profile = ReportProfile.objects.create(
                    name=f"{profile.name} (Copy)",
                    description=profile.description,
                    profile_type='user',  # Always create as user profile
                    created_by=request.user,
                    sections_config=profile.sections_config.copy() if profile.sections_config else {},
                    default_format=profile.default_format,
                    default_language=profile.default_language,
                    is_active=True,
                    is_public=False,
                )
                
                # Set company if user has one
                # try:
                #     user_company = request.user.cabinetuser.company
                #     if user_company:
                #         new_profile.company = user_company
                #         new_profile.save()
                # except:
                #     pass
                
                duplicated_count += 1
        
        self.message_user(request, _('Successfully duplicated %d profile(s).') % duplicated_count)
    duplicate_profile.short_description = _('Duplicate selected profiles')
    
    def activate_profiles(self, request, queryset):
        """Activate selected profiles"""
        updated = queryset.update(is_active=True)
        self.message_user(request, _('Successfully activated %d profile(s).') % updated)
    activate_profiles.short_description = _('Activate selected profiles')
    
    def deactivate_profiles(self, request, queryset):
        """Deactivate selected profiles"""
        updated = queryset.update(is_active=False)
        self.message_user(request, _('Successfully deactivated %d profile(s).') % updated)
    deactivate_profiles.short_description = _('Deactivate selected profiles')


@admin.register(AcceptableRisk)
class AcceptableRiskAdmin(admin.ModelAdmin):
    list_display = ['company', 'asset_group', 'asset_type', 'criticality_level', 'acceptable_risk_level', 'created_at', 'updated_at']
    list_filter = ['company', 'asset_group', 'asset_type', 'criticality_level', 'acceptable_risk_level', 'created_at']
    search_fields = ['company__name', 'asset_group__name', 'asset_group__code', 'asset_group__abbreviation', 'asset_type__name', 'asset_type__code', 'criticality_level__name', 'criticality_level__code', 'acceptable_risk_level__name', 'acceptable_risk_level__translations__name_local']
    ordering = ['company__name', 'asset_group__name', 'criticality_level__name']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('company', 'asset_group', 'asset_type', 'criticality_level', 'acceptable_risk_level')
        }),
        (_('Audit Information'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RiskTreatmentAttachment)
class RiskTreatmentAttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'treatment', 'file_type', 'file_size', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at', 'treatment__asset__company']
    search_fields = ['filename', 'treatment__asset__name', 'treatment__vulnerability__name']
    readonly_fields = ['file_size', 'uploaded_at', 'uploaded_by']
    ordering = ['-uploaded_at']
    
    fieldsets = (
        (_('File Information'), {
            'fields': ('treatment', 'file', 'filename', 'file_type', 'file_size', 'description')
        }),
        (_('Upload Information'), {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.uploaded_by = request.user
            # Set filename and file size if not provided
            if obj.file and not obj.filename:
                obj.filename = obj.file.name.split('/')[-1]
            if obj.file and not obj.file_size:
                obj.file_size = obj.file.size
            if obj.file and not obj.file_type:
                import os
                obj.file_type = os.path.splitext(obj.file.name)[1].lower()
        super().save_model(request, obj, form, change)


class RiskAssessmentConfigGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class RiskAssessmentConfigGuideTranslationInline(RiskAssessmentConfigGuideTranslationInlineMixin, admin.StackedInline):
    model = RiskAssessmentConfigGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/risk_assessment_config_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(RiskAssessmentConfigGuide)
class RiskAssessmentConfigGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [RiskAssessmentConfigGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_risk/riskassessmentconfigguide/change_form.html'

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
            extra_context['risk_assessment_config_guide_translate_url'] = reverse('risk_assessment_config_guide_translate')
        except Exception:
            extra_context['risk_assessment_config_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['risk_assessment_config_guide_translate_url'] = reverse('risk_assessment_config_guide_translate')
        except Exception:
            extra_context['risk_assessment_config_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class RiskAssessmentGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class RiskAssessmentGuideTranslationInline(RiskAssessmentGuideTranslationInlineMixin, admin.StackedInline):
    model = RiskAssessmentGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/risk_assessment_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(RiskAssessmentGuide)
class RiskAssessmentGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [RiskAssessmentGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_risk/riskassessmentguide/change_form.html'

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
            extra_context['risk_assessment_guide_translate_url'] = reverse('risk_assessment_guide_translate')
        except Exception:
            extra_context['risk_assessment_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['risk_assessment_guide_translate_url'] = reverse('risk_assessment_guide_translate')
        except Exception:
            extra_context['risk_assessment_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)


class RiskReportGuideTranslationInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.filter(is_active=True).order_by('display_order', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class RiskReportGuideTranslationInline(RiskReportGuideTranslationInlineMixin, admin.StackedInline):
    model = RiskReportGuideTranslation
    extra = 1
    fields = ('country', 'content')
    autocomplete_fields = ['country']
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 12})},
    }

    class Media:
        js = ('admin/js/risk_report_guide_admin.js',)
        css = {'all': ('admin/css/translation_helper.css',)}


@admin.register(RiskReportGuide)
class RiskReportGuideAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'has_base', 'translations_count')
    inlines = [RiskReportGuideTranslationInline]
    formfield_overrides = {
        HTMLField: {'widget': TinyMCE(attrs={'rows': 16})},
    }
    change_form_template = 'admin/app_risk/riskreportguide/change_form.html'

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
            extra_context['risk_report_guide_translate_url'] = reverse('risk_report_guide_translate')
        except Exception:
            extra_context['risk_report_guide_translate_url'] = ''
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context['risk_report_guide_translate_url'] = reverse('risk_report_guide_translate')
        except Exception:
            extra_context['risk_report_guide_translate_url'] = ''
        return super().add_view(request, form_url, extra_context)

