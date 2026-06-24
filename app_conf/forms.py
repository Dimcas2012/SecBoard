# SecBoard/app_conf/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import ContactMessage


class ContactForm(forms.ModelForm):
    """Form for contact page"""
    
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'company', 'subject_type', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Your Name'),
                'required': True,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('your.email@example.com'),
                'required': True,
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Phone Number (optional)'),
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Company or Organization (optional)'),
            }),
            'subject_type': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Message Subject'),
                'required': True,
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _('Your message...'),
                'required': True,
            }),
        }
        labels = {
            'name': _('Full Name'),
            'email': _('Email Address'),
            'phone': _('Phone Number'),
            'company': _('Company/Organization'),
            'subject_type': _('Inquiry Type'),
            'subject': _('Subject'),
            'message': _('Message'),
        }
    
    def clean_message(self):
        """Validate message length"""
        message = self.cleaned_data.get('message')
        if message and len(message) < 10:
            raise forms.ValidationError(_('Message must be at least 10 characters long.'))
        return message

