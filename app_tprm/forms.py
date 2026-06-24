from django import forms
from django.forms.utils import flatatt
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from .models import Vendor, VendorAssessment, VendorDocument, QuestionnaireTemplate, Question, VendorQuestionnaire, TprmLevel
from app_conf.models import Company


def _tprm_level_qs(level_type):
    return TprmLevel.objects.filter(type=level_type, is_active=True).order_by('display_order', 'cost', 'name')


class TprmLevelSelect(forms.Select):
    """Select widget that shows option description as title (tooltip) on hover."""
    option_titles = None  # dict: value (pk) -> description string, set in form __init__

    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        attrs = {**self.attrs, **attrs}
        final_attrs = self.build_attrs(attrs, extra_attrs={'name': name})
        # When editing, value can be the model instance (TprmLevel); normalize to pk for comparison
        if value is not None and hasattr(value, 'pk'):
            value = value.pk
        titles = getattr(self, 'option_titles', None) or {}
        choices = list(self.choices)
        options = []
        for option_value, option_label in choices:
            if option_value == '':
                options.append(f'<option value="">{escape(option_label)}</option>')
                continue
            title = titles.get(str(option_value), '') or ''
            title_attr = f' title="{escape(title)}"' if title else ''
            selected = ' selected="selected"' if str(option_value) == str(value) else ''
            options.append(
                f'<option value="{escape(option_value)}"{title_attr}{selected}>{escape(option_label)}</option>'
            )
        return mark_safe(
            '<select' + flatatt(final_attrs) + '>\n'
            + '\n'.join(options) + '\n</select>'
        )


class VendorForm(forms.ModelForm):
    """Form for creating/editing vendors"""

    attachment_document_type = forms.ChoiceField(
        label=_('Document type for new attachments'),
        choices=VendorDocument.DOCUMENT_TYPE_CHOICES,
        required=False,
        initial='other',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Vendor
        fields = [
            'name', 'is_active', 'company', 'description', 'contract', 'contract_validity', 'contract_end_date', 'website',
            'contact_person', 'contact_email', 'contact_phone',
            'risk_level', 'status',
            'services_provided',
            'nda_in_contract',
            'criticality_level',
            'sanctions_verification_status',
            'data_access_level',
            'data_access_rights',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Enter vendor name')}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Describe the vendor')}),
            'contract': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': _('Describe the contract or agreement')}),
            'contract_validity': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': _('e.g. 12 months from signing, auto-renewal, indefinite until notice')}),
            'contract_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Contact person name')}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 234 567 8900'}),
            'risk_level': TprmLevelSelect(attrs={'class': 'form-control'}),
            'status': TprmLevelSelect(attrs={'class': 'form-control'}),
            'services_provided': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Services provided by vendor')}),
            'nda_in_contract': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'criticality_level': TprmLevelSelect(attrs={'class': 'form-control'}),
            'sanctions_verification_status': TprmLevelSelect(attrs={'class': 'form-control'}),
            'data_access_level': TprmLevelSelect(attrs={'class': 'form-control'}),
            'data_access_rights': TprmLevelSelect(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, level_type in [
            ('risk_level', TprmLevel.TYPE_RISK_LEVEL),
            ('status', TprmLevel.TYPE_STATUS),
            ('criticality_level', TprmLevel.TYPE_CRITICALITY),
            ('sanctions_verification_status', TprmLevel.TYPE_SANCTIONS),
            ('data_access_level', TprmLevel.TYPE_DATA_ACCESS),
            ('data_access_rights', TprmLevel.TYPE_DATA_ACCESS_RIGHTS),
        ]:
            qs = _tprm_level_qs(level_type)
            self.fields[field_name].queryset = qs
            self.fields[field_name].empty_label = _('—')
            # Show localized name in dropdown (not type prefix); use factory to avoid closure bug
            def _make_label_from(_qs):
                def _label_from_instance(obj):
                    return obj.get_name()
                return _label_from_instance
            self.fields[field_name].label_from_instance = _make_label_from(qs)
            # Own widget instance per field so option_titles are correct; show localized description as tooltip on hover
            self.fields[field_name].widget = TprmLevelSelect(attrs={'class': 'form-control'})
            self.fields[field_name].widget.option_titles = {
                str(obj.pk): (obj.get_description() or '').strip() for obj in qs
            }
            # Replaced widget does not get choices from the field; set them so the select has options
            empty_label = self.fields[field_name].empty_label or '—'
            self.fields[field_name].widget.choices = [
                ('', empty_label),
            ] + [(obj.pk, obj.get_name()) for obj in qs]


class VendorAssessmentForm(forms.ModelForm):
    """Form for creating/editing vendor assessments"""
    
    class Meta:
        model = VendorAssessment
        fields = [
            'vendor', 'assessment_date', 'next_review_date', 'status',
            'security_score', 'compliance_score', 'financial_score', 'operational_score',
            'findings', 'recommendations'
        ]
        widgets = {
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'assessment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_review_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'security_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'placeholder': '0-100'}),
            'compliance_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'placeholder': '0-100'}),
            'financial_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'placeholder': '0-100'}),
            'operational_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'placeholder': '0-100'}),
            'findings': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': _('Assessment findings')}),
            'recommendations': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': _('Recommendations')}),
        }


class VendorDocumentForm(forms.ModelForm):
    """Form for uploading vendor documents"""
    
    class Meta:
        model = VendorDocument
        fields = ['vendor', 'document_type', 'title', 'description', 'file', 'expiry_date']
        widgets = {
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Document title')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Document description')}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class VendorFilterForm(forms.Form):
    """Form for filtering vendors"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': _('Search by name, contact, email...')
        })
    )
    
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        required=False,
        empty_label=_('All Companies'),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    risk_level = forms.ModelChoiceField(
        queryset=TprmLevel.objects.none(),
        required=False,
        empty_label=_('All Risk Levels'),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    status = forms.ModelChoiceField(
        queryset=TprmLevel.objects.none(),
        required=False,
        empty_label=_('All Statuses'),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    nda_in_contract = forms.ChoiceField(
        required=False,
        choices=[('', _('Any')), ('1', _('Yes')), ('0', _('No'))],
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )

    is_active = forms.ChoiceField(
        required=False,
        choices=[('', _('Any')), ('1', _('Active')), ('0', _('Inactive'))],
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )

    include_inactive = forms.BooleanField(
        required=False,
        label=_('Show inactive vendors'),
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    criticality_level = forms.ModelChoiceField(
        queryset=TprmLevel.objects.none(),
        required=False,
        empty_label=_('All levels'),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    sanctions_verification_status = forms.ModelChoiceField(
        queryset=TprmLevel.objects.none(),
        required=False,
        empty_label=_('All statuses'),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    data_access_level = forms.ModelChoiceField(
        queryset=TprmLevel.objects.none(),
        required=False,
        empty_label=_('All levels'),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    data_access_rights = forms.ModelChoiceField(
        queryset=TprmLevel.objects.none(),
        required=False,
        empty_label=_('All'),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['risk_level'].queryset = _tprm_level_qs(TprmLevel.TYPE_RISK_LEVEL)
        self.fields['status'].queryset = _tprm_level_qs(TprmLevel.TYPE_STATUS)
        self.fields['criticality_level'].queryset = _tprm_level_qs(TprmLevel.TYPE_CRITICALITY)
        self.fields['sanctions_verification_status'].queryset = _tprm_level_qs(TprmLevel.TYPE_SANCTIONS)
        self.fields['data_access_level'].queryset = _tprm_level_qs(TprmLevel.TYPE_DATA_ACCESS)
        self.fields['data_access_rights'].queryset = _tprm_level_qs(TprmLevel.TYPE_DATA_ACCESS_RIGHTS)


class QuestionnaireTemplateForm(forms.ModelForm):
    """Form for creating/editing questionnaire templates"""
    
    class Meta:
        model = QuestionnaireTemplate
        fields = ['name', 'description', 'category', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Template name')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Describe the questionnaire purpose')}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class QuestionForm(forms.ModelForm):
    """Form for creating/editing questions"""
    
    class Meta:
        model = Question
        fields = [
            'question_text', 'question_type', 'choices', 'parent_question', 
            'show_if_answer', 'weight', 'correct_answer', 'order', 'is_required', 'help_text'
        ]
        widgets = {
            'question_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': _('Enter question text')}),
            'question_type': forms.Select(attrs={'class': 'form-control'}),
            'choices': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': _('["Option 1", "Option 2", "Option 3"]')}),
            'parent_question': forms.Select(attrs={'class': 'form-control'}),
            'show_if_answer': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('yes/no/1-3/option')}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100}),
            'correct_answer': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Expected answer')}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'help_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': _('Help text for respondents')}),
        }
    
    def __init__(self, *args, **kwargs):
        template = kwargs.pop('template', None)
        super().__init__(*args, **kwargs)
        
        if template:
            # Only show questions from the same template as parent options
            self.fields['parent_question'].queryset = Question.objects.filter(template=template)
            self.fields['parent_question'].empty_label = _('No parent (root question)')


# Django FormSet for managing multiple questions
from django.forms import inlineformset_factory

QuestionFormSet = inlineformset_factory(
    QuestionnaireTemplate,
    Question,
    form=QuestionForm,
    extra=1,
    can_delete=True,
    fields=['question_text', 'question_type', 'parent_question', 'show_if_answer', 'weight', 'order', 'is_required']
)


class VendorSurveyLinkForm(forms.ModelForm):
    """Form for creating/editing vendor survey links"""
    
    class Meta:
        from .models import VendorSurveyLink
        model = VendorSurveyLink
        fields = [
            'vendor', 'questionnaire', 'template',
            'expires_at', 'is_one_time_use', 'max_uses',
            'notes'
        ]
        widgets = {
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'questionnaire': forms.Select(attrs={'class': 'form-control'}),
            'template': forms.Select(attrs={'class': 'form-control'}),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'is_one_time_use': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_uses': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 1000
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Internal notes about this link')
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get vendor from data (POST) or initial (GET with pre-filled vendor)
        vendor = None
        vendor_id = None
        
        # Check POST data first
        if 'vendor' in self.data:
            try:
                vendor_id = int(self.data.get('vendor'))
                vendor = Vendor.objects.get(pk=vendor_id) if vendor_id else None
            except (ValueError, TypeError, Vendor.DoesNotExist):
                pass
        
        # Check initial data (for GET requests with pre-filled vendor)
        if not vendor and 'vendor' in self.initial:
            vendor = self.initial.get('vendor')
            if vendor:
                vendor_id = vendor.pk if hasattr(vendor, 'pk') else vendor
        
        # Check instance (for edit forms)
        if not vendor and self.instance and self.instance.pk and self.instance.vendor:
            vendor = self.instance.vendor
            vendor_id = vendor.pk
        
        # Set questionnaire queryset based on vendor
        if vendor_id:
            self.fields['questionnaire'].queryset = VendorQuestionnaire.objects.filter(
                vendor_id=vendor_id
            )
        else:
            self.fields['questionnaire'].queryset = VendorQuestionnaire.objects.none()
        
        # Make questionnaire and template optional (at least one required)
        self.fields['questionnaire'].required = False
        self.fields['template'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        questionnaire = cleaned_data.get('questionnaire')
        template = cleaned_data.get('template')
        
        # At least one of questionnaire or template must be provided
        if not questionnaire and not template:
            raise forms.ValidationError(
                _('Either questionnaire or template must be selected.')
            )
        
        # If questionnaire is selected, ensure template matches
        if questionnaire and template:
            if questionnaire.template != template:
                raise forms.ValidationError(
                    _('Selected template must match the questionnaire template.')
                )
        
        return cleaned_data

