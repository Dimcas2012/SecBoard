from django import forms
from django.forms import inlineformset_factory, ModelMultipleChoiceField
from django.utils.translation import gettext as _
from tinymce.widgets import TinyMCE
from .models import Quiz, Question, Answer
from app_conf.models import Company
from app_cabinet.models import CabinetGroup, CabinetUser


class CabinetUserModelMultipleChoiceField(ModelMultipleChoiceField):
    """Choice field that displays user name with Department / Position (localized)."""
    def label_from_instance(self, obj):
        name = obj.user.get_full_name() or obj.user.username or ''
        dept = (obj.department.get_name() or '') if obj.department else ''
        pos = (obj.position.get_name() or '') if obj.position else ''
        extra = ' / '.join(x for x in (dept, pos) if x)
        if extra:
            return f"{name} — {extra}"
        return name or str(obj)


class QuizForm(forms.ModelForm):
    description = forms.CharField(
        widget=TinyMCE(attrs={'class': 'form-control', 'id': 'id_description'}),
        required=True,
        label=_("Description")
    )
    
    # Multiple companies selection
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.all(),
        required=True,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'id': 'id_companies',
            'size': '5'
        }),
        label=_("Companies")
    )
    
    cabinet_users = CabinetUserModelMultipleChoiceField(
        queryset=CabinetUser.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'id': 'id_cabinet_users',
            'size': '8'
        }),
        label=_("Cabinet Users")
    )

    class Meta:
        model = Quiz
        fields = ['title', 'description', 'shuffle_questions', 'shuffle_answers',
                  'is_active',
                  'passing_score', 'youtube_video_id', 'pdf_material', 'pdf_filename',
                  'companies', 'cabinet_groups', 'cabinet_users', 'page']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'shuffle_questions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'shuffle_answers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'passing_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'youtube_video_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'dQw4w9WgXcQ'}),
            'pdf_material': forms.FileInput(attrs={'class': 'form-control'}),
            'pdf_filename': forms.TextInput(attrs={'class': 'form-control'}),
            'cabinet_groups': forms.SelectMultiple(attrs={
                'class': 'form-control',
                'id': 'id_cabinet_groups',
                'size': '8'
            }),
            'page': forms.Select(attrs={'class': 'form-control'}),
        }
        
    class Media:
        js = ('tinymce/tinymce.min.js',)
        css = {
            'all': ('tinymce/tinymce.css',)
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Handle initial data for editing existing quiz
        if self.instance and self.instance.pk:
            # If editing, set the companies field from all companies assigned to the quiz
            selected_companies = self.instance.companies.all()
            if selected_companies.exists():
                self.fields['companies'].initial = selected_companies
                # Filter cabinet groups and users by selected companies
                self._filter_cabinet_fields_by_companies(selected_companies)
            else:
                # For existing quizzes without companies, start with empty cabinet fields
                self._filter_cabinet_fields_by_companies([])
        else:
            # For new quizzes, start with empty cabinet fields
            self._filter_cabinet_fields_by_companies([])
        
        # Make Companies required
        self.fields['companies'].required = True
        self.fields['cabinet_groups'].required = False  # Optional
        self.fields['cabinet_users'].required = False  # Optional
        
        # Set help text for fields
        self.fields['companies'].help_text = _("Select one or more companies (required)")
        self.fields['cabinet_groups'].help_text = _("Select specific cabinet groups (optional) - if none selected, all users from selected companies will have access")
        self.fields['cabinet_users'].help_text = _("Select specific cabinet users (optional) - if none selected, all users from selected companies will have access")
    
    def _filter_cabinet_fields_by_companies(self, companies):
        """Filter cabinet groups and users by companies"""
        if companies:
            # Convert to list if it's a queryset
            if hasattr(companies, 'values_list'):
                company_ids = list(companies.values_list('pk', flat=True))
            else:
                company_ids = [c.pk if hasattr(c, 'pk') else c for c in companies]
            
            # Filter cabinet groups by companies
            cabinet_groups = CabinetGroup.objects.filter(company_id__in=company_ids)
            self.fields['cabinet_groups'].queryset = cabinet_groups
            
            # Filter cabinet users by companies (only active users), with department/position for display
            cabinet_users = CabinetUser.objects.filter(
                company_id__in=company_ids, user__is_active=True
            ).select_related('user', 'department', 'position')
            self.fields['cabinet_users'].queryset = cabinet_users
            
            # If editing an existing quiz, set initial values for cabinet groups and users
            if self.instance and self.instance.pk:
                # Set initial values for cabinet groups (from all selected companies)
                selected_groups = self.instance.cabinet_groups.filter(company_id__in=company_ids)
                self.fields['cabinet_groups'].initial = selected_groups
                
                # Set initial values for cabinet users (from all selected companies)
                selected_users = self.instance.cabinet_users.filter(company_id__in=company_ids)
                self.fields['cabinet_users'].initial = selected_users
        else:
            # No companies selected, show empty querysets
            self.fields['cabinet_groups'].queryset = CabinetGroup.objects.none()
            self.fields['cabinet_users'].queryset = CabinetUser.objects.none()
    
    def filter_by_companies(self, accessible_companies):
        """Filter form choices based on accessible companies from AccessQuiz"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Convert set to list if necessary
        if isinstance(accessible_companies, set):
            accessible_companies = list(accessible_companies)
        
        logger.info(f"Filtering companies in QuizForm. Accessible companies: {[c.name for c in accessible_companies] if accessible_companies else 'None'}")
        
        if not accessible_companies:
            # If no accessible companies, show none
            logger.info("No accessible companies - showing empty querysets")
            self.fields['companies'].queryset = Company.objects.none()
            self.fields['cabinet_groups'].queryset = CabinetGroup.objects.none()
            self.fields['cabinet_users'].queryset = CabinetUser.objects.none()
            
            # Add error messages for required fields
            self.fields['companies'].help_text = _("No companies available based on your permissions")
            self.fields['cabinet_groups'].help_text = _("No cabinet groups available - no accessible companies")
            self.fields['cabinet_users'].help_text = _("No cabinet users available - no accessible companies")
            return
        
        # Filter company choices
        company_ids = [c.pk for c in accessible_companies]
        self.fields['companies'].queryset = Company.objects.filter(pk__in=company_ids)
        
        # Filter cabinet groups and users by accessible companies (only active users for cabinet_users)
        cabinet_groups = CabinetGroup.objects.filter(company__in=accessible_companies)
        cabinet_users = CabinetUser.objects.filter(
            company__in=accessible_companies, user__is_active=True
        ).select_related('user', 'department', 'position')
        
        self.fields['cabinet_groups'].queryset = cabinet_groups
        self.fields['cabinet_users'].queryset = cabinet_users
        
        groups_count = cabinet_groups.count()
        users_count = cabinet_users.count()
        
        # Update help text with counts
        self.fields['cabinet_groups'].help_text = _("Select specific cabinet groups (optional) - {} available - if none selected, all users from selected companies will have access").format(groups_count)
        self.fields['cabinet_users'].help_text = _("Select specific cabinet users (optional) - {} available - if none selected, all users from selected companies will have access").format(users_count)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            # Handle the companies field - clear existing companies and add the selected ones
            instance.companies.clear()
            if self.cleaned_data.get('companies'):
                instance.companies.set(self.cleaned_data['companies'])
            
            # Save many-to-many fields
            self.save_m2m()
        
        return instance


class QuestionForm(forms.ModelForm):
    text = forms.CharField(
        widget=TinyMCE(attrs={'class': 'form-control'}),
        required=True,
        label=_("Question Text")
    )
    
    class Meta:
        model = Question
        fields = ['text', 'order']
        widgets = {
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        
    class Media:
        js = ('tinymce/tinymce.min.js',)
        css = {
            'all': ('tinymce/tinymce.css',)
        }


class AnswerForm(forms.ModelForm):
    text = forms.CharField(
        widget=TinyMCE(attrs={'class': 'form-control'}),
        required=True,
        label=_("Answer Text")
    )
    
    class Meta:
        model = Answer
        fields = ['text', 'is_correct', 'score']
        widgets = {
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'score': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        
    class Media:
        js = ('tinymce/tinymce.min.js',)
        css = {
            'all': ('tinymce/tinymce.css',)
        }


# Create formsets for inline editing
QuestionFormSet = inlineformset_factory(
    Quiz, Question,
    form=QuestionForm,
    extra=1,
    can_delete=True
)

AnswerFormSet = inlineformset_factory(
    Question, Answer,
    form=AnswerForm,
    extra=2,
    can_delete=True
) 