#  SecBoard\SecBoard\app_gdpr\forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from .models import (
    DataSubject,
    ConsentRecord,
    DataProcessingActivity,
    DataBreachIncident,
    DataSubjectRequest,
    DataRetentionPolicy,
    DPIAAssessment
)


class DataSubjectForm(forms.ModelForm):
    """Форма для створення/редагування суб'єкта даних"""
    
    class Meta:
        model = DataSubject
        fields = [
            'company',
            'user',
            'first_name',
            'last_name',
            'email',
            'phone',
            'consent_status',
            'data_retention_period_days',
            'deletion_scheduled_date'
        ]
        widgets = {
            'company': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'user': forms.Select(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'consent_status': forms.Select(attrs={'class': 'form-control'}),
            'data_retention_period_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'deletion_scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Company обов'язкове
        self.fields['company'].required = True
        self.fields['company'].empty_label = _("-- Select Company First --")
        if user:
            try:
                from .permissions import get_user_accessible_companies_gdpr
                accessible = get_user_accessible_companies_gdpr(user)
                if accessible is not None:
                    self.fields['company'].queryset = self.fields['company'].queryset.filter(id__in=[c.id for c in accessible])
            except Exception:
                pass
        
        # User опціональне, буде фільтруватись по Company
        self.fields['user'].required = False
        self.fields['user'].queryset = self.fields['user'].queryset.none()
        
        # Якщо форма має дані (редагування), фільтруємо користувачів
        if 'company' in self.data:
            try:
                company_id = int(self.data.get('company'))
                from django.contrib.auth.models import User
                from app_cabinet.models import CabinetUser
                # Отримуємо користувачів цієї компанії
                self.fields['user'].queryset = User.objects.filter(
                    cabinet__company_id=company_id
                ).select_related('cabinet__department', 'cabinet__position')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.company:
            from django.contrib.auth.models import User
            # При редагуванні показуємо користувачів компанії
            self.fields['user'].queryset = User.objects.filter(
                cabinet__company=self.instance.company
            ).select_related('cabinet__department', 'cabinet__position')


class ConsentRecordForm(forms.ModelForm):
    """Форма для запису згоди"""
    
    class Meta:
        model = ConsentRecord
        fields = [
            'data_subject',
            'consent_type',
            'consent_text',
            'expiration_date',
            'ip_address',
            'user_agent',
            'consent_method',
            'consent_version',
            'is_active'
        ]
        widgets = {
            'data_subject': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'consent_type': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'consent_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'required': 'required'}),
            'expiration_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-control'}),
            'user_agent': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'consent_method': forms.TextInput(attrs={'class': 'form-control', 'required': 'required'}),
            'consent_version': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            try:
                from .permissions import get_user_accessible_companies_gdpr
                accessible = get_user_accessible_companies_gdpr(user)
                if accessible is not None:
                    self.fields['data_subject'].queryset = self.fields['data_subject'].queryset.filter(company__in=accessible)
            except Exception:
                pass


class DataProcessingActivityForm(forms.ModelForm):
    """Форма для діяльності з обробки даних"""
    
    # Додаємо поля для шаблону
    activity_name = forms.CharField(
        label=_("Activity Name"),
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'required'})
    )
    description = forms.CharField(
        label=_("Description"),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'required': 'required'})
    )
    purpose = forms.CharField(
        label=_("Purpose"),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': 'required'})
    )
    data_categories = forms.CharField(
        label=_("Data Categories"),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': 'required'})
    )
    data_subjects = forms.CharField(
        label=_("Data Subjects"),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': 'required'})
    )
    recipients = forms.CharField(
        label=_("Recipients"),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )
    third_country_transfers = forms.CharField(
        label=_("Third Country Transfers"),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )
    retention_period = forms.CharField(
        label=_("Retention Period"),
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False
    )
    retention_period_days = forms.IntegerField(
        label=_("Retention Period (days)"),
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=True,
        initial=365
    )
    security_measures = forms.CharField(
        label=_("Security Measures"),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )
    start_date = forms.DateField(
        label=_("Start Date"),
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        required=False
    )
    end_date = forms.DateField(
        label=_("End Date"),
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        required=False
    )
    
    class Meta:
        model = DataProcessingActivity
        fields = [
            'activity_name',
            'company',
            'description',
            'purpose',
            'data_categories',
            'data_subjects',
            'legal_basis',
            'recipients',
            'third_country_transfers',
            'retention_period',
            'retention_period_days',
            'security_measures',
            'start_date',
            'end_date'
        ]
        widgets = {
            'company': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'legal_basis': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            self.fields['activity_name'].initial = instance.name
            self.fields['description'].initial = instance.description
            self.fields['purpose'].initial = instance.purpose
        if user:
            try:
                from .permissions import get_user_accessible_companies_gdpr
                accessible = get_user_accessible_companies_gdpr(user)
                if accessible is not None:
                    self.fields['company'].queryset = self.fields['company'].queryset.filter(id__in=[c.id for c in accessible])
            except Exception:
                pass
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Map form fields to model (name/description/purpose; translations in admin inline)
        instance.name = self.cleaned_data['activity_name']
        instance.description = self.cleaned_data['description']
        instance.purpose = self.cleaned_data['purpose']
        instance.data_categories = self.cleaned_data['data_categories']
        instance.data_subjects_categories = self.cleaned_data['data_subjects']
        instance.security_measures = self.cleaned_data.get('security_measures', '')
        # Встановлюємо значення за замовчуванням для обов'язкових полів
        instance.retention_period_days = self.cleaned_data.get('retention_period_days', 365)
        instance.is_active = True  # За замовчуванням активна
        if commit:
            instance.save()
        return instance


class DataBreachIncidentForm(forms.ModelForm):
    """Форма для реєстрації інциденту витоку даних"""
    
    class Meta:
        model = DataBreachIncident
        fields = [
            'title',
            'description',
            'incident_date',
            'discovery_date',
            'affected_subjects_count',
            'data_types_affected',
            'severity',
            'status',
            'immediate_actions',
            'mitigation_actions',
            'preventive_measures',
            'company',
            'assigned_to'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'incident_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'discovery_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'affected_subjects_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'data_types_affected': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'severity': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'immediate_actions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'mitigation_actions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'preventive_measures': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'company': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            try:
                from .permissions import get_user_accessible_companies_gdpr
                accessible = get_user_accessible_companies_gdpr(user)
                if accessible is not None:
                    self.fields['company'].queryset = self.fields['company'].queryset.filter(id__in=[c.id for c in accessible])
            except Exception:
                pass


class DataBreachReportForm(forms.ModelForm):
    """Форма для звіту про інцидент (з повідомленням регулятору)"""
    
    class Meta:
        model = DataBreachIncident
        fields = [
            'reported_to_authority',
            'authority_report_date',
            'subjects_notified',
            'subjects_notification_date'
        ]
        widgets = {
            'reported_to_authority': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'authority_report_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'subjects_notified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'subjects_notification_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }


class DataSubjectRequestForm(forms.ModelForm):
    """Форма для запиту суб'єкта даних (DSR)"""
    
    class Meta:
        model = DataSubjectRequest
        fields = [
            'request_type',
            'data_subject',
            'request_description',
            'company',
            'request_source',
            'verification_method',
            'is_verified'
        ]
        widgets = {
            'request_type': forms.Select(attrs={'class': 'form-control'}),
            'data_subject': forms.Select(attrs={'class': 'form-control'}),
            'request_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'company': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'request_source': forms.TextInput(attrs={'class': 'form-control'}),
            'verification_method': forms.TextInput(attrs={'class': 'form-control'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['company'].required = True
        self.fields['company'].empty_label = _('-- Select Company --')
        if user:
            try:
                from .permissions import get_user_accessible_companies_gdpr
                accessible = get_user_accessible_companies_gdpr(user)
                if accessible is not None:
                    self.fields['company'].queryset = self.fields['company'].queryset.filter(id__in=[c.id for c in accessible])
                    self.fields['data_subject'].queryset = self.fields['data_subject'].queryset.filter(company__in=accessible)
            except Exception:
                pass


class DSRProcessForm(forms.ModelForm):
    """Форма для обробки DSR"""
    
    class Meta:
        model = DataSubjectRequest
        fields = [
            'status',
            'assigned_to',
            'response_text',
            'rejection_reason'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'response_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'rejection_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DataRetentionPolicyForm(forms.ModelForm):
    """Форма для політики утримання даних (name/description + DataRetentionPolicyTranslation)."""

    class Meta:
        model = DataRetentionPolicy
        fields = [
            'name',
            'description',
            'data_category',
            'retention_period_days',
            'legal_basis',
            'deletion_method',
            'company',
            'auto_apply',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'data_category': forms.TextInput(attrs={'class': 'form-control'}),
            'retention_period_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'legal_basis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'deletion_method': forms.Select(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
            'auto_apply': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['name'].initial = self.instance.name or self.instance.get_name()
            self.fields['description'].initial = self.instance.description or self.instance.get_description()
        if user:
            try:
                from .permissions import get_user_accessible_companies_gdpr
                accessible = get_user_accessible_companies_gdpr(user)
                if accessible is not None:
                    self.fields['company'].queryset = self.fields['company'].queryset.filter(
                        id__in=[c.id for c in accessible]
                    )
            except Exception:
                pass


class DPIAAssessmentForm(forms.ModelForm):
    """Форма для DPIA оцінки"""
    
    class Meta:
        model = DPIAAssessment
        fields = [
            'project_name',
            'project_description',
            'processing_description',
            'data_types',
            'data_subjects',
            'necessity_assessment',
            'proportionality_assessment',
            'risks_identified',
            'overall_risk_level',
            'mitigation_measures',
            'residual_risk_level',
            'stakeholders_consulted',
            'dpo_consulted',
            'company',
            'conducted_by',
            'review_date'
        ]
        widgets = {
            'project_name': forms.TextInput(attrs={'class': 'form-control'}),
            'project_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'processing_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'data_types': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'data_subjects': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'necessity_assessment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'proportionality_assessment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'risks_identified': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'overall_risk_level': forms.Select(attrs={'class': 'form-control'}),
            'mitigation_measures': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'residual_risk_level': forms.Select(attrs={'class': 'form-control'}),
            'stakeholders_consulted': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'dpo_consulted': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
            'conducted_by': forms.Select(attrs={'class': 'form-control'}),
            'review_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            try:
                from .permissions import get_user_accessible_companies_gdpr
                accessible = get_user_accessible_companies_gdpr(user)
                if accessible is not None:
                    self.fields['company'].queryset = self.fields['company'].queryset.filter(id__in=[c.id for c in accessible])
            except Exception:
                pass


class DPIAApprovalForm(forms.ModelForm):
    """Форма для затвердження DPIA"""
    
    class Meta:
        model = DPIAAssessment
        fields = [
            'status',
            'approval_date'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'approval_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

