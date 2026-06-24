from django import forms
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from app_cabinet.models import CabinetUser

from .models import (
    CIFCriticalFunction,
    CIFObject,
    CIFPassport,
    CIFProtectionMeasure,
    CIFProtectionPlan,
    CIFProtectionPlanTemplate,
)


class CIFObjectForm(forms.ModelForm):
    edrpou = forms.CharField(
        max_length=10,
        validators=[RegexValidator(r"^\d{10}$", _("EDRPOU must contain exactly 10 digits."))],
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "1234567890"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        users_qs = self.fields["responsible_person"].queryset
        cabinet_rows = (
            CabinetUser.objects.filter(user__in=users_qs)
            .select_related("user", "department", "position")
        )
        cabinet_by_user_id = {row.user_id: row for row in cabinet_rows}

        def responsible_label(user_obj):
            full_name = (user_obj.get_full_name() or user_obj.username).strip()
            cabinet = cabinet_by_user_id.get(user_obj.id)
            if not cabinet:
                return full_name
            department = ""
            if cabinet.department:
                department = cabinet.department.get_name() if hasattr(cabinet.department, "get_name") else str(cabinet.department)
            position = ""
            if cabinet.position:
                position = cabinet.position.get_name() if hasattr(cabinet.position, "get_name") else str(cabinet.position)
            return f"{full_name} / {department or '-'} / {position or '-'}"

        self.fields["responsible_person"].label_from_instance = responsible_label

    class Meta:
        model = CIFObject
        fields = [
            "name",
            "edrpou",
            "category",
            "sector",
            "address",
            "company",
            "status",
            "responsible_person",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "sector": forms.Select(attrs={"class": "form-select"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "company": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "responsible_person": forms.Select(attrs={"class": "form-select"}),
        }


class CIFPassportForm(forms.ModelForm):
    general_info = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("Enter general information"),
            }
        ),
    )
    critical_functions = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("Enter critical functions"),
            }
        ),
    )
    resources = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("Enter resources"),
            }
        ),
    )
    dependencies = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("Enter dependencies"),
            }
        ),
    )
    threats = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": _("Enter threats"),
            }
        ),
    )

    class Meta:
        model = CIFPassport
        fields = [
            "version",
            "status",
            "approval_date",
            "next_review_date",
            "general_info",
            "critical_functions",
            "resources",
            "dependencies",
            "threats",
        ]
        widgets = {
            "version": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "approval_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "next_review_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ["general_info", "critical_functions", "resources", "dependencies", "threats"]:
            value = self.initial.get(field_name, None)
            if value in ({}, []):
                self.initial[field_name] = ""


class CIFProtectionPlanForm(forms.ModelForm):
    template = forms.ModelChoiceField(
        queryset=CIFProtectionPlanTemplate.objects.all(),
        required=False,
        empty_label=_("Select template"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Template is auto-selected by CIF category when possible."),
    )

    class Meta:
        model = CIFProtectionPlan
        fields = [
            "version",
            "status",
            "approval_date",
            "next_review_date",
            "responsible_person",
            "okii_unique_identifier",
            "okii_full_name",
            "okii_short_name",
            "registry_info_submitted",
            "registry_submission_date",
            "registry_inclusion_date",
            "registry_planned_submission_date",
            "registry_responsible_person",
            "cmu518_requirements_status",
            "cmu518_responsible_person",
            "cmu518_completion_percent",
            "cmu518_status_date",
            "cmu518_target_100_date",
            "security_person_full_name",
            "security_person_position",
            "security_person_department",
            "security_contact_postal_address",
            "security_contact_phone",
            "security_contact_email",
            "vital_service_description",
            "processed_information_types",
            "has_external_connections",
            "providers_full_names",
            "provider_has_protected_nodes",
            "connection_ip_addresses",
            "connection_phone",
            "connection_email",
            "other_connected_systems",
            "interaction_description",
            "interaction_other_okii_name",
            "interaction_other_okii_identifier",
            "interaction_phone",
            "interaction_email",
            "has_kszi_attestat_or_audit",
            "kszi_attestat_details",
            "kszi_certificate_or_audit_report",
            "kszi_other_info",
            "has_misp_interaction",
            "misp_cert_ua",
            "misp_ua",
            "misp_nbu",
            "misp_ncscc",
            "misp_other",
            "has_cert_csirt_interaction",
            "cert_csirt_team_name",
            "cert_csirt_ownership_type",
            "cert_csirt_affiliation_type",
            "cert_csirt_contact_info",
            "has_soc_interaction",
            "soc_name",
            "soc_affiliation_type",
            "soc_contact_info",
            "functional_scheme_file",
            "project_threats_description",
            "incident_response_general_order",
            "monitoring_security_level_info",
            "monitoring_results_summary",
            "plan_change_info",
            "structure",
        ]
        widgets = {
            "version": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "approval_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "next_review_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "responsible_person": forms.Select(attrs={"class": "form-select"}),
            "okii_unique_identifier": forms.TextInput(attrs={"class": "form-control"}),
            "okii_full_name": forms.TextInput(attrs={"class": "form-control"}),
            "okii_short_name": forms.TextInput(attrs={"class": "form-control"}),
            "registry_info_submitted": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "registry_submission_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "registry_inclusion_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "registry_planned_submission_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "registry_responsible_person": forms.TextInput(attrs={"class": "form-control"}),
            "cmu518_requirements_status": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "cmu518_responsible_person": forms.TextInput(attrs={"class": "form-control"}),
            "cmu518_completion_percent": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": 0, "max": 100}),
            "cmu518_status_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "cmu518_target_100_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "security_person_full_name": forms.TextInput(attrs={"class": "form-control"}),
            "security_person_position": forms.TextInput(attrs={"class": "form-control"}),
            "security_person_department": forms.TextInput(attrs={"class": "form-control"}),
            "security_contact_postal_address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "security_contact_phone": forms.TextInput(attrs={"class": "form-control"}),
            "security_contact_email": forms.EmailInput(attrs={"class": "form-control"}),
            "vital_service_description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "processed_information_types": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "has_external_connections": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "providers_full_names": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "provider_has_protected_nodes": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "connection_ip_addresses": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "connection_phone": forms.TextInput(attrs={"class": "form-control"}),
            "connection_email": forms.EmailInput(attrs={"class": "form-control"}),
            "other_connected_systems": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "interaction_description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "interaction_other_okii_name": forms.TextInput(attrs={"class": "form-control"}),
            "interaction_other_okii_identifier": forms.TextInput(attrs={"class": "form-control"}),
            "interaction_phone": forms.TextInput(attrs={"class": "form-control"}),
            "interaction_email": forms.EmailInput(attrs={"class": "form-control"}),
            "has_kszi_attestat_or_audit": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "kszi_attestat_details": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "kszi_certificate_or_audit_report": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "kszi_other_info": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "has_misp_interaction": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "misp_cert_ua": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "misp_ua": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "misp_nbu": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "misp_ncscc": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "misp_other": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "has_cert_csirt_interaction": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "cert_csirt_team_name": forms.TextInput(attrs={"class": "form-control"}),
            "cert_csirt_ownership_type": forms.TextInput(attrs={"class": "form-control"}),
            "cert_csirt_affiliation_type": forms.TextInput(attrs={"class": "form-control"}),
            "cert_csirt_contact_info": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "has_soc_interaction": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "soc_name": forms.TextInput(attrs={"class": "form-control"}),
            "soc_affiliation_type": forms.TextInput(attrs={"class": "form-control"}),
            "soc_contact_info": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "functional_scheme_file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "project_threats_description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "incident_response_general_order": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "monitoring_security_level_info": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "monitoring_results_summary": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "plan_change_info": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "structure": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }

    def save(self, commit=True):
        plan = super().save(commit=False)
        template = self.cleaned_data.get("template")
        if template and not plan.structure:
            plan.structure = template.structure
        if commit:
            plan.save()
        return plan


class CIFCriticalFunctionForm(forms.ModelForm):
    class Meta:
        model = CIFCriticalFunction
        fields = ["name", "description", "priority", "rto_hours", "rpo_hours", "owner", "related_assets", "is_critical"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "priority": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 5}),
            "rto_hours": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "rpo_hours": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "related_assets": forms.SelectMultiple(attrs={"class": "form-select"}),
            "is_critical": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class CIFProtectionMeasureForm(forms.ModelForm):
    class Meta:
        model = CIFProtectionMeasure
        fields = [
            "class_code",
            "measure_number",
            "name",
            "description",
            "implementation_status",
            "deadline",
            "responsible",
            "related_compliance_control",
            "evidence_files",
            "notes",
        ]
        widgets = {
            "class_code": forms.Select(attrs={"class": "form-select"}),
            "measure_number": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "implementation_status": forms.Select(attrs={"class": "form-select"}),
            "deadline": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "responsible": forms.Select(attrs={"class": "form-select"}),
            "related_compliance_control": forms.Select(attrs={"class": "form-select"}),
            "evidence_files": forms.SelectMultiple(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
