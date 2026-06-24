# D:\Python\MyProject\SecBoard\SecBoard\app_cabinet\forms.py
from django import forms
from app_study.models import Page
from app_conf.models import MailAccount
from app_study.validators import validate_password_pci_dss
from tinymce.widgets import TinyMCE
import re
import os
import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.translation import gettext_lazy as _, check_for_language

from app_cabinet.models import CabinetUser
from django.contrib.auth.models import User
from .input_security import PersonalCabinetSecurityValidator, PersonalCabinetAuditLogger, get_client_ip

logger = logging.getLogger(__name__)


class MailAccountForm(forms.ModelForm):
    show_password = forms.BooleanField(required=False, initial=False, label=_("Show Password"))
    send_test_email = forms.BooleanField(required=False, initial=False, label=_("Send Test Email"))
    test_email_recipient = forms.EmailField(required=False, label=_("Test Email Recipient"))

    class Meta:
        model = MailAccount
        fields = ['server', 'username', 'password', 'is_active', 'show_password', 'send_test_email', 'test_email_recipient']
        widgets = {
            'password': forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['password'].initial = self.instance.get_masked_password()

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if self.instance.pk and password == '*' * 8:
            return self.instance.password
        return password

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('send_test_email'):
            if not cleaned_data.get('test_email_recipient'):
                raise forms.ValidationError(_("Test email recipient is required when sending a test email."))
        return cleaned_data


class UpdateProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        help_text=_("Leave empty if you don't want to change it")
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        help_text=_("Confirm new password")
    )

    class Meta:
        model = CabinetUser
        fields = ['first_name', 'last_name', 'phone', 'preferred_language', 'telegram_chat_id', 'avatar']
        widgets = {
            'phone': forms.TextInput(attrs={'placeholder': _('Enter your phone number')}),
            'avatar': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/gif'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
        language_choices = [('', _('Use browser default'))] + list(settings.LANGUAGES)
        self.fields['preferred_language'] = forms.ChoiceField(
            choices=language_choices,
            required=False,
            label=_('Default language'),
            help_text=_('Preferred interface language for your account.'),
            widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        )
        if self.instance and self.instance.pk:
            self.fields['preferred_language'].initial = self.instance.preferred_language or ''
        self.fields['telegram_chat_id'].required = False
        self.fields['telegram_chat_id'].label = _('Telegram Chat ID')

    def clean_first_name(self):
        """Validate and sanitize first name to prevent XSS attacks"""
        first_name = self.cleaned_data.get('first_name')
        validator = PersonalCabinetSecurityValidator()
        
        try:
            return validator.validate_and_sanitize_text_field(first_name, 'first_name', 30)
        except ValidationError as e:
            if self.request:
                ip = get_client_ip(self.request)
                PersonalCabinetAuditLogger.log_malicious_input_attempt(
                    self.request.user, 'first_name', first_name, ip
                )
            raise e

    def clean_last_name(self):
        """Validate and sanitize last name to prevent XSS attacks"""
        last_name = self.cleaned_data.get('last_name')
        validator = PersonalCabinetSecurityValidator()
        
        try:
            return validator.validate_and_sanitize_text_field(last_name, 'last_name', 30)
        except ValidationError as e:
            if self.request:
                ip = get_client_ip(self.request)
                PersonalCabinetAuditLogger.log_malicious_input_attempt(
                    self.request.user, 'last_name', last_name, ip
                )
            raise e

    def clean_phone(self):
        """Validate phone number and prevent injection attacks"""
        phone = self.cleaned_data.get('phone')
        if not phone:
            return phone
        
        # Remove common formatting characters for validation
        cleaned_phone = re.sub(r'[\s\-\(\)\+]', '', phone)
        
        # Check if contains only digits and allowed formatting characters
        if not re.match(r'^\+?[\d\s\-\(\)]+$', phone):
            if self.request:
                ip = get_client_ip(self.request)
                PersonalCabinetAuditLogger.log_malicious_input_attempt(
                    self.request.user, 'phone', phone, ip
                )
            raise ValidationError(_('Phone number contains invalid characters.'))
        
        # Check length (international format)
        if len(cleaned_phone) < 7 or len(cleaned_phone) > 15:
            raise ValidationError(_('Phone number must be between 7 and 15 digits.'))
        
        return phone

    def clean_preferred_language(self):
        language = (self.cleaned_data.get('preferred_language') or '').strip()
        if language and not check_for_language(language):
            raise ValidationError(_('Select a valid language.'))
        return language

    def clean_telegram_chat_id(self):
        chat_id = (self.cleaned_data.get('telegram_chat_id') or '').strip()
        if chat_id and not re.match(r'^-?\d+$', chat_id):
            raise ValidationError(_('Telegram Chat ID must contain digits only.'))
        return chat_id

    def clean_avatar(self):
        """Validate avatar upload for security issues"""
        avatar = self.cleaned_data.get('avatar')
        if not avatar:
            return avatar
        
        # Only validate when a new file was uploaded (UploadedFile has content_type).
        # Existing ImageFieldFile from the instance has no content_type attribute.
        if not getattr(avatar, 'content_type', None):
            return avatar

        # Check file size (2MB limit)
        if avatar.size > 2 * 1024 * 1024:
            raise ValidationError(_('Avatar file size must not exceed 2MB.'))
        
        # Check file type
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'image/gif']
        if avatar.content_type not in allowed_types:
            raise ValidationError(_('Avatar must be a JPEG, PNG, or GIF image.'))
        
        # Check file extension
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        file_extension = avatar.name.lower().split('.')[-1]
        if f'.{file_extension}' not in allowed_extensions:
            raise ValidationError(_('Invalid file extension for avatar.'))
        
        # Check for potentially malicious file names
        if re.search(r'[<>:"/\\|?*]', avatar.name):
            if self.request:
                ip = get_client_ip(self.request)
                PersonalCabinetAuditLogger.log_malicious_input_attempt(
                    self.request.user, 'avatar', avatar.name, ip
                )
            raise ValidationError(_('Avatar filename contains invalid characters.'))
        
        return avatar

    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        # Validate privilege escalation attempts
        if self.request:
            validator = PersonalCabinetSecurityValidator()
            try:
                validator.validate_privilege_escalation_attempt(
                    self.request.user,
                    target_user_id=self.instance.user.id if self.instance.user else None,
                    company_change=None,  # Company changes not allowed in this form
                    department_change=None,  # Department changes not allowed in this form
                    position_change=None   # Position changes not allowed in this form
                )
            except ValidationError as e:
                ip = get_client_ip(self.request)
                PersonalCabinetAuditLogger.log_privilege_escalation_attempt(
                    self.request.user, 'profile_update', ip, str(e)
                )
                raise e

        if new_password1 or new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError(_("The two password fields didn't match."))

            # Add password validation
            try:
                validate_password(new_password1)
            except ValidationError as error:
                self.add_error('new_password1', error)

        return cleaned_data

    def save(self, commit=True):
        # Track changed fields for audit logging
        changed_fields = []
        user = self.instance.user
        
        if user.first_name != self.cleaned_data['first_name']:
            changed_fields.append('first_name')
            user.first_name = self.cleaned_data['first_name']
            
        if user.last_name != self.cleaned_data['last_name']:
            changed_fields.append('last_name')
            user.last_name = self.cleaned_data['last_name']

        if self.cleaned_data.get('new_password1'):
            changed_fields.append('password')
            user.set_password(self.cleaned_data['new_password1'])

        if 'phone' in self.changed_data:
            changed_fields.append('phone')

        if 'avatar' in self.changed_data:
            changed_fields.append('avatar')

        if 'preferred_language' in self.changed_data:
            changed_fields.append('preferred_language')

        if 'telegram_chat_id' in self.changed_data:
            changed_fields.append('telegram_chat_id')

        if commit:
            user.save()
            self.instance.save()
            
            # Log the profile update for audit purposes
            if self.request and changed_fields:
                ip = get_client_ip(self.request)
                PersonalCabinetAuditLogger.log_profile_update(
                    self.request.user, changed_fields, ip
                )

        return self.instance

class LoginForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('Enter your email address')})
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise ValidationError(_("There is no user registered with this email address."))
        return email


class SetPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        strip=False,
        validators=[validate_password_pci_dss],
        help_text=_("Enter a new password."),
    )
    new_password2 = forms.CharField(
        label=_("Confirm new password"),
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text=_("Enter the same password as before, for verification."),
    )

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError(_("The two password fields didn't match."))
        return password2

    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')
        user = getattr(self, 'user', None)
        
        if user and user.check_password(password):
            raise ValidationError(
                _("The new password must be different from the current password."),
                code='password_same'
            )
            
        return password

    def save(self, user):
        self.user = user  # Store user for validation
        password = self.cleaned_data["new_password1"]
        user.set_password(password)
        user.save()
        return user

class PageAdminForm(forms.ModelForm):
    content = forms.CharField(widget=TinyMCE(), required=False, label=_("Content"))
    link_url = forms.URLField(required=False, widget=forms.URLInput(attrs={'placeholder': 'https://example.com'}), label=_("Link URL"))
    youtube_id = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'placeholder': 'dQw4w9WgXcQ'}), label=_("YouTube ID"))
    video_file = forms.FileField(
        required=False, 
        label=_("Video File"),
        help_text=_("Upload video file (MP4, WebM, OGV)")
    )
    audio_file = forms.FileField(
        required=False, 
        label=_("Audio File"),
        help_text=_("Upload audio file (MP3, WAV, OGG)")
    )

    class Meta:
        model = Page
        fields = '__all__'
        exclude = ['html_content']  # Hide html_content field from admin
    
    class Media:
        js = ('tinymce/tinymce.min.js',)
        css = {
            'all': ('tinymce/tinymce.css',)
        }

    def clean_youtube_id(self):
        youtube_id = self.cleaned_data.get('youtube_id')
        if youtube_id:
            if not re.match(r'^[\w-]{11}$', youtube_id):
                raise forms.ValidationError(_("Invalid YouTube ID. It should be 11 characters long and contain only letters, numbers, hyphens and underscores."))
        return youtube_id

    def clean_video_file(self):
        video_file = self.cleaned_data.get('video_file')
        if video_file:
            # Check file extension
            allowed_extensions = ['.mp4', '.webm', '.ogv', '.avi', '.mov']
            file_extension = os.path.splitext(video_file.name)[1].lower()
            if file_extension not in allowed_extensions:
                raise forms.ValidationError(_("Invalid video file format. Allowed formats: MP4, WebM, OGV, AVI, MOV"))
            
            # Check file size (max 100MB)
            if video_file.size > 100 * 1024 * 1024:
                raise forms.ValidationError(_("Video file is too large. Maximum size is 100MB."))
        
        return video_file

    def clean_audio_file(self):
        audio_file = self.cleaned_data.get('audio_file')
        if audio_file:
            # Check file extension
            allowed_extensions = ['.mp3', '.wav', '.ogg', '.m4a', '.aac']
            file_extension = os.path.splitext(audio_file.name)[1].lower()
            if file_extension not in allowed_extensions:
                raise forms.ValidationError(_("Invalid audio file format. Allowed formats: MP3, WAV, OGG, M4A, AAC"))
            
            # Check file size (max 50MB)
            if audio_file.size > 50 * 1024 * 1024:
                raise forms.ValidationError(_("Audio file is too large. Maximum size is 50MB."))
        
        return audio_file

    def clean(self):
        cleaned_data = super().clean()
        use_html = cleaned_data.get('use_html')
        content = cleaned_data.get('content')

        if not use_html and not content:
            raise forms.ValidationError(_("TinyMCE content is required when 'Use HTML' is not selected."))

        return cleaned_data


class CabinetUserEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = CabinetUser
        fields = ['company', 'department', 'position', 'phone', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def clean_phone(self):
        """Validate phone number format when provided."""
        phone = self.cleaned_data.get('phone')
        if not phone:
            return phone
        from .security_validators import PersonalCabinetSecurityValidator
        try:
            return PersonalCabinetSecurityValidator.validate_phone_number(phone)
        except ValidationError:
            raise

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get('first_name') is not None:
            instance.user.first_name = self.cleaned_data['first_name']
        if self.cleaned_data.get('last_name') is not None:
            instance.user.last_name = self.cleaned_data['last_name']
        if self.cleaned_data.get('email') is not None:
            instance.user.email = self.cleaned_data['email']
            instance.user.username = self.cleaned_data['email']
        if commit:
            instance.user.save()
            instance.save()
        return instance

class MessageForm(forms.Form):
    subject = forms.CharField(
        label=_('Subject'),
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    message = forms.CharField(
        label=_('Message'),
        widget=TinyMCE(attrs={'class': 'form-control'})
    )
    
    class Media:
        js = ('tinymce/tinymce.min.js',)
        css = {
            'all': ('tinymce/tinymce.css',)
        }