# SecBoard\SecBoard\app_risk\forms.py
from django import forms
from django.utils import timezone
from .models import Threat, Vulnerability
from decimal import Decimal, ROUND_DOWN
from django.utils.translation import gettext as _
from django import forms
from django.utils.translation import gettext_lazy as _


class ThreatForm(forms.ModelForm):
    class Meta:
        model = Threat
        fields = ['name', 'description', 'risks',
                  'probability_scenario', 'probability',
                  'scenario_m', 'scenario_n', 'impact',
                  'financial_impact', 'operational_impact', 'reputational_impact']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'id': 'threat-name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'id': 'threat-description', 'rows': '3'}),
            'risks': forms.Textarea(attrs={'class': 'form-control', 'id': 'threat-risks', 'rows': '3'}),
            'probability_scenario': forms.Select(attrs={'class': 'form-select', 'id': 'threat-probability-scenario'}),
            'scenario_m': forms.NumberInput(attrs={'class': 'form-control scenario-param', 'id': 'threat-scenario-m'}),
            'scenario_n': forms.NumberInput(attrs={'class': 'form-control scenario-param', 'id': 'threat-scenario-n'}),
            'probability': forms.NumberInput(attrs={
                'class': 'form-control probability-input',
                'id': 'threat-probability',
                'step': '0.0001',
                'min': '0',
                'max': '1'
            }),
            'impact': forms.NumberInput(attrs={'class': 'form-control', 'id': 'threat-impact', 'step': '0.01', 'min': '0'}),
            'financial_impact': forms.Select(attrs={'class': 'form-select', 'id': 'threat-financial-impact'}),
            'operational_impact': forms.Select(attrs={'class': 'form-select', 'id': 'threat-operational-impact'}),
            'reputational_impact': forms.Select(attrs={'class': 'form-select', 'id': 'threat-reputational-impact'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['description'].required = False
        self.fields['risks'].required = False
        self.fields['probability'].required = True
        self.fields['impact'].required = True
        self.fields['scenario_m'].required = False
        self.fields['scenario_n'].required = False

    def clean_probability(self):
        probability = self.cleaned_data.get('probability')
        if probability is not None:
            return Decimal(str(probability)).quantize(Decimal('0.0001'), rounding=ROUND_DOWN)
        return probability

    def clean(self):
        cleaned_data = super().clean()
        probability_scenario = cleaned_data.get('probability_scenario')
        scenario_m = cleaned_data.get('scenario_m')
        scenario_n = cleaned_data.get('scenario_n')
        if probability_scenario in ['m_in_n_days', 'm_in_n_years']:
            if not scenario_m or not scenario_n:
                raise forms.ValidationError(_("Both M and N are required for this probability scenario."))
        elif probability_scenario in ['once_in_n_years']:
            if not scenario_n:
                raise forms.ValidationError(_("N is required for this probability scenario."))
        return cleaned_data



class VulnerabilityForm(forms.ModelForm):
    class Meta:
        model = Vulnerability
        fields = [
            'asset_group', 'asset_type', 'name', 'code', 'description',
            'scope', 'risk_mitigation_controls', 'pci_dss_requirement', 'iso27001_requirement', 'note',
            'threats',
        ]

    def __init__(self, *args, **kwargs):
        super(VulnerabilityForm, self).__init__(*args, **kwargs)
        self.fields['threats'].required = False

