from django import forms
from django.utils.translation import gettext_lazy as _

from .models import TelegramBot
from .utils import get_company_queryset_for_user


class TelegramBotForm(forms.ModelForm):
    class Meta:
        model = TelegramBot
        fields = [
            'name',
            'bot_token',
            'default_chat_id',
            'respond_to_start',
            'start_message',
            'use_webhook',
            'webhook_secret',
            'company',
            'is_active',
            'description',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'bot_token': forms.PasswordInput(attrs={'class': 'form-control form-control-sm'}),
            'default_chat_id': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'respond_to_start': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_message': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 4}),
            'use_webhook': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'webhook_secret': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'company': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }
        labels = {
            'name': _('Name'),
            'bot_token': _('Bot token'),
            'default_chat_id': _('Default chat ID'),
            'respond_to_start': _('Respond to /start'),
            'start_message': _('Start message'),
            'use_webhook': _('Use webhook'),
            'webhook_secret': _('Webhook secret'),
            'company': _('Company'),
            'is_active': _('Active'),
            'description': _('Description'),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['company'].queryset = get_company_queryset_for_user(self.user)

        if self.instance and self.instance.pk:
            self.fields['bot_token'].widget = forms.PasswordInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': '••••••••••••••••',
                'autocomplete': 'new-password',
            })
            self.fields['bot_token'].required = False
            self.fields['bot_token'].help_text = _(
                'Token is hidden. Leave empty to keep the current token, or enter a new token to replace it.',
            )

    def clean_bot_token(self):
        token = (self.cleaned_data.get('bot_token') or '').strip()
        if self.instance and self.instance.pk and not token:
            return self.instance.bot_token
        if not token:
            raise forms.ValidationError(_('Bot token is required.'))
        return token
