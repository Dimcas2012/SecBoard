from django import forms
from django.utils.translation import gettext as _
from .models import Incident, Classification, Incidenttype, Currentstate, IncidentFile, Company
from django.forms.fields import DateField
from app_conf.models import Company
from app_incident.utils import get_user_accessible_companies

class MultipleFileInput(forms.ClearableFileInput):
    """Custom widget that properly supports multiple file uploads"""
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    """Field for handling multiple file uploads"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # Handle both single and multiple file uploads
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class IncidentForm(forms.ModelForm):
    """Form for creating and editing incidents"""
    
    # Add a multiple file field (this will not be saved to the model directly)
    additional_files = MultipleFileField(
        required=False,
        label=_("Incident Report Files"),
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.doc,.docx,.xls,.xlsx,.txt,.jpg,.jpeg,.png'
        })
    )
    
    class Meta:
        model = Incident
        fields = [
            'company', 'occurrence_datetime', 'place', 'description',
            'classification', 'incident_type', 'features', 'responsible',
            'reported_by', 'reported_datetime', 'reports_and_records',
            'impact', 'measures_taken', 'additional_measures',
            'current_state', 'comment', 'file_incident'
        ]
        widgets = {
            'occurrence_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'reported_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'registered_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'features': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'reports_and_records': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'impact': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'measures_taken': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'additional_measures': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'place': forms.TextInput(attrs={'class': 'form-control'}),
            'responsible': forms.TextInput(attrs={'class': 'form-control'}),
            'reported_by': forms.TextInput(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
            'classification': forms.Select(attrs={'class': 'form-control'}),
            'incident_type': forms.Select(attrs={'class': 'form-control'}),
            'current_state': forms.Select(attrs={'class': 'form-control'}),
            'file_incident': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Access permissions for companies can be passed
        available_companies = kwargs.pop('available_companies', None)
        super(IncidentForm, self).__init__(*args, **kwargs)
        
        # If available companies are provided, limit the choices
        if available_companies:
            self.fields['company'].queryset = available_companies
        
        # Set required fields
        self.fields['place'].required = True
        self.fields['description'].required = True
        self.fields['responsible'].required = True
        self.fields['reported_by'].required = True
        
        # For the file field
        self.fields['file_incident'].widget.attrs.update({
            'accept': '.pdf,.doc,.docx,.xls,.xlsx,.txt,.jpg,.jpeg,.png'
        })
        self.fields['file_incident'].label = _("Main Incident Report File")


class IncidentFileForm(forms.ModelForm):
    """Form for incident file uploads"""
    class Meta:
        model = IncidentFile
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.txt,.jpg,.jpeg,.png'
            }),
        }

class IncidentFilterForm(forms.Form):
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        required=False,
        label=_("Company"),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    classification = forms.ModelChoiceField(
        queryset=Classification.objects.filter(is_active=True).order_by('name'),
        required=False,
        label=_("Classification"),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    incident_type = forms.ModelChoiceField(
        queryset=Incidenttype.objects.filter(is_active=True).order_by('name'),
        required=False,
        label=_("Incident Type"),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    current_state = forms.ModelChoiceField(
        queryset=Currentstate.objects.filter(is_active=True).order_by('name'),
        required=False,
        label=_("Current State"),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    date_from = forms.DateField(
        required=False,
        label=_("Date From"),
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        label=_("Date To"),
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            accessible_companies = get_user_accessible_companies(user)
            self.fields['company'].queryset = accessible_companies
            if len(accessible_companies) == 1:
                self.fields['company'].initial = accessible_companies.first() 