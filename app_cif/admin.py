from django.contrib import admin

from app_conf.models import Country
from .models import (
    AccessCIF,
    CIFCriticalFunction,
    CIFObject,
    CIFPassport,
    CIFProtectionMeasure,
    CIFProtectionPlan,
    CIFProtectionPlanTemplate,
    CIFSector,
    CIFSectorTranslation,
)


class CIFCriticalFunctionInline(admin.TabularInline):
    model = CIFCriticalFunction
    extra = 0


class CIFProtectionMeasureInline(admin.TabularInline):
    model = CIFProtectionMeasure
    extra = 0


class ActiveCountryInlineMixin:
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "country":
            kwargs["queryset"] = Country.objects.filter(is_active=True).order_by("display_order", "name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CIFSectorTranslationInline(ActiveCountryInlineMixin, admin.TabularInline):
    model = CIFSectorTranslation
    extra = 1
    fields = ("country", "name_local", "description")
    autocomplete_fields = ["country"]

    class Media:
        js = ("admin/js/translation_helper.js",)
        css = {"all": ("admin/css/translation_helper.css",)}


@admin.register(AccessCIF)
class AccessCIFAdmin(admin.ModelAdmin):
    list_display = (
        'group', 'has_access', 'can_view_objects', 'can_edit_objects',
        'can_view_passports', 'can_edit_passports', 'can_approve_passports',
        'can_view_plans', 'can_edit_plans', 'can_export', 'companies_list',
    )
    list_filter = (
        'has_access', 'can_view_objects', 'can_edit_objects', 'can_add_objects',
        'can_delete_objects', 'can_view_passports', 'can_edit_passports',
        'can_approve_passports', 'can_view_plans', 'can_edit_plans', 'can_export',
    )
    search_fields = ('group__name', 'description')
    filter_horizontal = ('companies',)

    fieldsets = (
        ('Group Information', {
            'fields': ('group', 'description'),
        }),
        ('Access Rights', {
            'fields': ('has_access',),
        }),
        ('Object Permissions', {
            'fields': ('can_view_objects', 'can_edit_objects', 'can_add_objects', 'can_delete_objects'),
        }),
        ('Passport Permissions', {
            'fields': ('can_view_passports', 'can_edit_passports', 'can_approve_passports'),
        }),
        ('Protection Plan Permissions', {
            'fields': ('can_view_plans', 'can_edit_plans'),
        }),
        ('Reports', {
            'fields': ('can_export',),
        }),
        ('Company Access', {
            'fields': ('companies',),
            'description': 'Select companies this group can access. Leave empty for all companies.',
        }),
    )

    def companies_list(self, obj):
        companies = obj.companies.all()
        if companies.exists():
            return ', '.join([c.name for c in companies[:3]]) + (
                f' (+{companies.count() - 3} more)' if companies.count() > 3 else ''
            )
        return 'All companies'
    companies_list.short_description = 'Companies'


@admin.register(CIFSector)
class CIFSectorAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "name_local", "regulatory_body", "translations_count")
    search_fields = ("code", "name", "name_local", "regulatory_body")
    inlines = [CIFSectorTranslationInline]
    actions = ["load_default_sectors"]

    def translations_count(self, obj):
        return obj.translations.count()
    translations_count.short_description = "Translations"

    @admin.action(description="Load default CIF sectors")
    def load_default_sectors(self, request, queryset):
        defaults = [
            {"code": "energy", "name": "Energy", "name_local": "Енергетика", "regulatory_body": "НКРЕКП"},
            {"code": "transport", "name": "Transport", "name_local": "Транспорт", "regulatory_body": "Мінінфраструктури"},
            {"code": "finance", "name": "Finance", "name_local": "Фінанси", "regulatory_body": "НБУ"},
            {"code": "telecom", "name": "Telecommunications", "name_local": "Телекомунікації", "regulatory_body": "НКЕК"},
            {"code": "healthcare", "name": "Healthcare", "name_local": "Охорона здоров'я", "regulatory_body": "МОЗ"},
            {"code": "water", "name": "Water Supply", "name_local": "Водопостачання", "regulatory_body": "Мінрегіон"},
            {"code": "government", "name": "Government Services", "name_local": "Державні послуги", "regulatory_body": "КМУ"},
            {"code": "digital", "name": "Digital Infrastructure", "name_local": "Цифрова інфраструктура", "regulatory_body": "Мінцифра"},
        ]
        created = 0
        for item in defaults:
            _, was_created = CIFSector.objects.get_or_create(
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "name_local": item["name_local"],
                    "regulatory_body": item["regulatory_body"],
                },
            )
            created += 1 if was_created else 0
        self.message_user(request, f"Default sectors loaded. Created: {created}, skipped: {len(defaults) - created}")


@admin.register(CIFObject)
class CIFObjectAdmin(admin.ModelAdmin):
    list_display = ("name", "edrpou", "category", "sector", "status", "is_passport_approved")
    list_filter = ("category", "sector", "status")
    search_fields = ("name", "edrpou")
    autocomplete_fields = ("company", "responsible_person")
    inlines = [CIFCriticalFunctionInline]


@admin.register(CIFPassport)
class CIFPassportAdmin(admin.ModelAdmin):
    list_display = ("cif_object", "version", "status", "approval_date", "next_review_date")
    list_filter = ("status",)
    search_fields = ("cif_object__name", "cif_object__edrpou")
    autocomplete_fields = ("cif_object", "created_by", "approved_by")


@admin.register(CIFProtectionPlan)
class CIFProtectionPlanAdmin(admin.ModelAdmin):
    list_display = ("cif_object", "version", "status", "implementation_percent", "next_review_date")
    list_filter = ("status",)
    search_fields = ("cif_object__name", "cif_object__edrpou")
    autocomplete_fields = ("cif_object", "responsible_person")
    readonly_fields = ("implementation_percent", "id_percent", "pr_percent", "de_percent", "rs_percent", "rc_percent")
    inlines = [CIFProtectionMeasureInline]


@admin.register(CIFProtectionPlanTemplate)
class CIFProtectionPlanTemplateAdmin(admin.ModelAdmin):
    list_display = ("category", "name", "updated_at")
    search_fields = ("name",)


@admin.register(CIFProtectionMeasure)
class CIFProtectionMeasureAdmin(admin.ModelAdmin):
    list_display = ("protection_plan", "class_code", "measure_number", "implementation_status", "deadline")
    list_filter = ("class_code", "implementation_status")
    search_fields = ("measure_number", "name", "protection_plan__cif_object__name")
    autocomplete_fields = ("protection_plan", "responsible", "related_compliance_control")
    filter_horizontal = ("evidence_files",)
