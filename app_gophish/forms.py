# app_gophish/forms.py

from django import forms
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from .models import (
    GophishServer, GophishGroup, GophishTemplate, GophishLandingPage,
    GophishSendingProfile, GophishCampaign
)
from .api_client import gophish_manager


class GophishServerForm(forms.ModelForm):
    """Form for creating and editing Gophish servers"""
    
    class Meta:
        model = GophishServer
        fields = ['name', 'base_url', 'api_key', 'company', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'base_url': forms.URLInput(attrs={'class': 'form-control'}),
            'api_key': forms.PasswordInput(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': _('Server Name'),
            'base_url': _('Base URL'),
            'api_key': _('API Key'),
            'company': _('Company'),
            'is_active': _('Active'),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter company choices based on user's AccessGophish permissions
        if self.user:
            from .views import get_user_accessible_companies_gophish
            accessible_companies = get_user_accessible_companies_gophish(self.user)
            
            if accessible_companies is not None:  # User has restricted access
                # Filter company queryset to only show accessible companies
                from app_conf.models import Company
                self.fields['company'].queryset = Company.objects.filter(
                    id__in=[company.id for company in accessible_companies]
                )
            # If accessible_companies is None, user has access to all companies (no filtering needed)
        
        # If editing an existing server, show the current API key
        if self.instance and self.instance.pk:
            # For existing servers, show the current API key in a text input
            self.fields['api_key'].widget = forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter new API key or leave unchanged',
                'readonly': True,
                'value': '••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••'
            })
            self.fields['api_key'].help_text = _('Current API key is hidden for security. Leave unchanged or enter a new one.')
        else:
            # For new servers, use password input
            self.fields['api_key'].widget = forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your Gophish API key'
            })
            self.fields['api_key'].help_text = _('Get this from Gophish Settings > Account Settings')
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.created_by = self.user
        if commit:
            instance.save()
        return instance
    
    def clean(self):
        cleaned_data = super().clean()
        base_url = cleaned_data.get('base_url')
        api_key = cleaned_data.get('api_key')
        company = cleaned_data.get('company')
        
        # Validate company access
        if self.user and company:
            from .views import get_user_accessible_companies_gophish
            accessible_companies = get_user_accessible_companies_gophish(self.user)
            
            if accessible_companies is not None:  # User has restricted access
                if company not in accessible_companies:
                    raise forms.ValidationError(_('You do not have permission to create/edit servers for this company.'))
        
        # Basic validation - don't test connection during form validation
        # Connection testing will be done after saving or manually
        if base_url and not base_url.startswith(('http://', 'https://')):
            raise forms.ValidationError(_('URL must start with http:// or https://'))
        
        # For editing existing servers, if API key is the placeholder value, keep the existing one
        if self.instance and self.instance.pk:
            if api_key == '••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••':
                # Keep the existing API key
                cleaned_data['api_key'] = self.instance.api_key
            elif api_key and len(api_key.strip()) < 10:
                raise forms.ValidationError(_('API key seems too short. Please check your API key.'))
        else:
            # For new servers, validate the API key
            if api_key and len(api_key.strip()) < 10:
                raise forms.ValidationError(_('API key seems too short. Please check your API key.'))
        
        return cleaned_data


class GophishCampaignForm(forms.ModelForm):
    """Form for creating and editing Gophish campaigns"""
    
    class Meta:
        model = GophishCampaign
        fields = [
            'server', 'name', 'template', 'landing_page', 'sending_profile',
            'groups', 'launch_date', 'send_by_date', 'url'
        ]
        widgets = {
            'server': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'template': forms.Select(attrs={'class': 'form-control'}),
            'landing_page': forms.Select(attrs={'class': 'form-control'}),
            'sending_profile': forms.Select(attrs={'class': 'form-control'}),
            'groups': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'launch_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'send_by_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'url': forms.URLInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'server': _('Gophish Server'),
            'name': _('Campaign Name'),
            'template': _('Email Template'),
            'landing_page': _('Landing Page'),
            'sending_profile': _('Sending Profile'),
            'groups': _('Target Groups'),
            'launch_date': _('Launch Date'),
            'send_by_date': _('Send By Date'),
            'url': _('Campaign URL'),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter choices based on selected server
        if 'server' in self.data:
            server_id = self.data.get('server')
            if server_id:
                self.fields['template'].queryset = GophishTemplate.objects.filter(server_id=server_id)
                self.fields['landing_page'].queryset = GophishLandingPage.objects.filter(server_id=server_id)
                self.fields['sending_profile'].queryset = GophishSendingProfile.objects.filter(server_id=server_id)
                self.fields['groups'].queryset = GophishGroup.objects.filter(server_id=server_id)
        
        # If editing existing campaign
        elif self.instance.pk:
            if self.instance.server:
                self.fields['template'].queryset = GophishTemplate.objects.filter(server=self.instance.server)
                self.fields['landing_page'].queryset = GophishLandingPage.objects.filter(server=self.instance.server)
                self.fields['sending_profile'].queryset = GophishSendingProfile.objects.filter(server=self.instance.server)
                self.fields['groups'].queryset = GophishGroup.objects.filter(server=self.instance.server)
        
        # Only show active servers
        self.fields['server'].queryset = GophishServer.objects.filter(is_active=True)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.created_by = self.user
        if commit:
            instance.save()
            self.save_m2m()
        return instance
    
    def clean(self):
        cleaned_data = super().clean()
        server = cleaned_data.get('server')
        groups = cleaned_data.get('groups')
        
        # Validate that groups belong to the selected server
        if server and groups:
            for group in groups:
                if group.server != server:
                    raise forms.ValidationError(
                        _('All groups must belong to the selected server.')
                    )
        
        return cleaned_data


class GophishTemplateForm(forms.ModelForm):
    """Form for creating and editing Gophish templates"""
    
    class Meta:
        model = GophishTemplate
        fields = ['server', 'name', 'subject', 'html_content', 'text_content']
        widgets = {
            'server': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'html_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 15}),
            'text_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        }
        labels = {
            'server': _('Gophish Server'),
            'name': _('Template Name'),
            'subject': _('Email Subject'),
            'html_content': _('HTML Content'),
            'text_content': _('Text Content'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = GophishServer.objects.filter(is_active=True)
        self.fields['text_content'].required = False


class GophishLandingPageForm(forms.ModelForm):
    """Form for creating and editing Gophish landing pages"""
    
    class Meta:
        model = GophishLandingPage
        fields = [
            'server', 'name', 'html_content', 'capture_credentials',
            'capture_passwords', 'redirect_url'
        ]
        widgets = {
            'server': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'html_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 15}),
            'capture_credentials': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'capture_passwords': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'redirect_url': forms.URLInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'server': _('Gophish Server'),
            'name': _('Landing Page Name'),
            'html_content': _('HTML Content'),
            'capture_credentials': _('Capture Credentials'),
            'capture_passwords': _('Capture Passwords'),
            'redirect_url': _('Redirect URL'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = GophishServer.objects.filter(is_active=True)
        self.fields['redirect_url'].required = False


class GophishSendingProfileForm(forms.ModelForm):
    """Form for creating and editing Gophish sending profiles"""
    
    class Meta:
        model = GophishSendingProfile
        fields = [
            'server', 'name', 'from_address', 'from_name', 'smtp_host',
            'smtp_port', 'smtp_username', 'smtp_password', 'ignore_cert_errors'
        ]
        widgets = {
            'server': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'from_address': forms.EmailInput(attrs={'class': 'form-control'}),
            'from_name': forms.TextInput(attrs={'class': 'form-control'}),
            'smtp_host': forms.TextInput(attrs={'class': 'form-control'}),
            'smtp_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'smtp_username': forms.TextInput(attrs={'class': 'form-control'}),
            'smtp_password': forms.PasswordInput(attrs={'class': 'form-control'}),
            'ignore_cert_errors': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'server': _('Gophish Server'),
            'name': _('Profile Name'),
            'from_address': _('From Address'),
            'from_name': _('From Name'),
            'smtp_host': _('SMTP Host'),
            'smtp_port': _('SMTP Port'),
            'smtp_username': _('SMTP Username'),
            'smtp_password': _('SMTP Password'),
            'ignore_cert_errors': _('Ignore Certificate Errors'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = GophishServer.objects.filter(is_active=True)


class GophishGroupForm(forms.ModelForm):
    """Form for creating and editing Gophish groups"""
    
    class Meta:
        model = GophishGroup
        fields = ['server', 'name', 'targets_data']
        widgets = {
            'server': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'targets_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        }
        labels = {
            'server': _('Gophish Server'),
            'name': _('Group Name'),
            'targets_data': _('Targets (JSON format)'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = GophishServer.objects.filter(is_active=True)
    
    def clean_targets_data(self):
        """Validate that targets_data is valid JSON"""
        targets_data = self.cleaned_data.get('targets_data')
        if targets_data:
            try:
                import json
                json.loads(targets_data)
            except json.JSONDecodeError:
                raise forms.ValidationError(_('Invalid JSON format'))
        return targets_data


class CampaignLaunchForm(forms.Form):
    """Form for launching a campaign"""
    
    def __init__(self, campaign, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.campaign = campaign
        
        # Add fields based on campaign configuration
        if not campaign.launch_date:
            self.fields['launch_date'] = forms.DateTimeField(
                label=_('Launch Date'),
                widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
                help_text=_('When to launch the campaign (leave empty for immediate launch)')
            )
        
        self.fields['confirm'] = forms.BooleanField(
            label=_('Confirm Launch'),
            widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            help_text=_('I confirm that I want to launch this campaign')
        )
    
    def clean(self):
        cleaned_data = super().clean()
        confirm = cleaned_data.get('confirm')
        
        if not confirm:
            raise forms.ValidationError(_('You must confirm the campaign launch'))
        
        return cleaned_data


class SyncForm(forms.Form):
    """Form for manual synchronization"""
    
    SYNC_CHOICES = [
        ('full', _('Full Sync (All Data)')),
        ('campaigns', _('Campaigns Only')),
        ('groups', _('Groups Only')),
        ('templates', _('Templates Only')),
        ('landing_pages', _('Landing Pages Only')),
        ('sending_profiles', _('Sending Profiles Only')),
        ('results', _('Campaign Results Only')),
    ]
    
    server = forms.ModelChoiceField(
        queryset=GophishServer.objects.filter(is_active=True),
        label=_('Gophish Server'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    sync_type = forms.ChoiceField(
        choices=SYNC_CHOICES,
        label=_('Sync Type'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    force_update = forms.BooleanField(
        label=_('Force Update'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Force update even if data appears to be current')
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter server choices based on user's AccessGophish permissions
        if self.user:
            from .views import get_user_accessible_companies_gophish
            accessible_companies = get_user_accessible_companies_gophish(self.user)
            
            if accessible_companies is not None:  # User has restricted access
                self.fields['server'].queryset = GophishServer.objects.filter(
                    is_active=True,
                    company__in=accessible_companies
                )
            # If accessible_companies is None, user has access to all companies (no filtering needed)
