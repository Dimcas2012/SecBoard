from django.db import models
from django.contrib.auth.models import User, Group
from django.utils.translation import gettext_lazy as _, gettext, get_language
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from app_conf.models import Company
from app_cabinet.models import CabinetUser
import uuid


class TprmOwner(models.Model):
    """Owner person for TPRM vendors (separate catalogue from Asset Owner)."""

    cabinet_user = models.ForeignKey(
        CabinetUser,
        on_delete=models.CASCADE,
        related_name='tprm_owner_entries',
        verbose_name=_('Cabinet User'),
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='tprm_owners',
        verbose_name=_('Company'),
    )

    class Meta:
        verbose_name = _('TPRM Owner')
        verbose_name_plural = _('TPRM Owners')
        unique_together = [('cabinet_user', 'company')]

    def __str__(self):
        return f"{self.cabinet_user.user.get_full_name()} ({self.cabinet_user.department}/{self.cabinet_user.position})"

    @property
    def name(self):
        return self.cabinet_user.user.get_full_name()

    @property
    def department(self):
        return self.cabinet_user.department

    @property
    def position(self):
        return self.cabinet_user.position

    @property
    def email(self):
        return self.cabinet_user.user.email

    @property
    def phone(self):
        return self.cabinet_user.phone


def cabinet_users_active_for_company(company_id):
    """
    Cabinet users for a company eligible as TPRM owner candidates:
    Django user is active; employment window is current (same idea as CabinetUser.is_active_employee).
    """
    if not company_id:
        return CabinetUser.objects.none()
    today = timezone.localdate()
    return (
        CabinetUser.objects.filter(
            company_id=company_id,
            user__is_active=True,
        )
        .filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__date__lte=today)
        )
        .filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__date__gte=today)
        )
        .select_related('user', 'department', 'position', 'company')
        .order_by('user__last_name', 'user__first_name')
    )


# Map language code (from get_language()) to country codes for translations
LANGUAGE_COUNTRY_MAP = {
    'uk': ['UA'],
    'ru': ['RU'],
    'en': ['GB', 'US'],
    'pl': ['PL'],
    'de': ['DE'],
    'fr': ['FR'],
    'es': ['ES'],
    'it': ['IT'],
    'pt': ['PT'],
    'nl': ['NL'],
    'cs': ['CZ'],
    'sk': ['SK'],
    'ro': ['RO'],
    'bg': ['BG'],
    'hr': ['HR'],
    'sr': ['RS'],
    'tr': ['TR'],
    'ar': ['AE', 'SA'],
    'zh': ['CN'],
    'ja': ['JP'],
    'kk': ['KZ'],
    'be': ['BY'],
    'fi': ['FI'],
    'sv': ['SE'],
    'da': ['DK'],
    'no': ['NO'],
    'et': ['EE'],
    'lv': ['LV'],
    'lt': ['LT'],
}


def get_country_for_current_language():
    """Return Country for current Django language, or None if not found."""
    from app_conf.models import Country
    language_code = (get_language() or '')[:2].lower()
    if not language_code:
        return None
    for country_code in LANGUAGE_COUNTRY_MAP.get(language_code, []):
        try:
            return Country.objects.get(code__iexact=country_code)
        except Country.DoesNotExist:
            continue
    return None


class TprmLevel(models.Model):
    """
    Configurable levels for TPRM (analogous to App_Asset › Criticality Levels).
    Types: risk_level, status, criticality_level, sanctions_verification, data_access_level.
    Managed in Home › App_Tprm.
    """
    TYPE_RISK_LEVEL = 'risk_level'
    TYPE_STATUS = 'status'
    TYPE_CRITICALITY = 'criticality_level'
    TYPE_SANCTIONS = 'sanctions_verification'
    TYPE_DATA_ACCESS = 'data_access_level'
    TYPE_DATA_ACCESS_RIGHTS = 'data_access_rights'
    TYPE_CHOICES = [
        (TYPE_RISK_LEVEL, _('Risk Level')),
        (TYPE_STATUS, _('Status')),
        (TYPE_CRITICALITY, _('Criticality level')),
        (TYPE_SANCTIONS, _('Sanctions verification')),
        (TYPE_DATA_ACCESS, _('Data Access Level')),
        (TYPE_DATA_ACCESS_RIGHTS, _('Data Access rights')),
    ]

    type = models.CharField(_('Type'), max_length=32, choices=TYPE_CHOICES, db_index=True)
    name = models.CharField(_('Name'), max_length=100)
    code = models.CharField(_('Code'), max_length=50)
    color = models.CharField(_('Color'), max_length=7, default='#6c757d')
    display_order = models.IntegerField(_('Display order'), default=0)
    cost = models.IntegerField(
        _('Cost'),
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text=_('Numeric value 0–10 for ordering/calculations')
    )
    description = models.TextField(_('Description'), blank=True)
    is_active = models.BooleanField(_('Is active'), default=True)
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)

    class Meta:
        verbose_name = _('TPRM Level')
        verbose_name_plural = _('TPRM Levels')
        ordering = ['type', 'display_order', 'cost', 'name']
        unique_together = [('type', 'code')]

    def __str__(self):
        return f"{self.get_type_display()}: {self.get_name()}"

    def get_name(self):
        """Localized name based on current site language."""
        country = get_country_for_current_language()
        if country:
            try:
                trans = self.translations.get(country=country)
                if trans.name_local and trans.name_local.strip():
                    return trans.name_local
            except TprmLevelTranslation.DoesNotExist:
                pass
        lang = (get_language() or '')[:2].lower()
        return self.name or ''

    def get_description(self):
        """Localized description based on current site language."""
        country = get_country_for_current_language()
        if country:
            try:
                trans = self.translations.get(country=country)
                if trans.description_local and trans.description_local.strip():
                    return trans.description_local
            except TprmLevelTranslation.DoesNotExist:
                pass
        return self.description or ''

    def get_description_short(self, max_len=60):
        """Short description for list display (localized)."""
        d = (self.get_description() or '').strip()
        if not d:
            return '—'
        if len(d) <= max_len:
            return d
        return d[:max_len].rsplit(' ', 1)[0] + '…' if ' ' in d[:max_len] else d[:max_len] + '…'

    get_description_short.short_description = _('Description')


class TprmLevelTranslation(models.Model):
    """Per-country (language) translations for TprmLevel name and description."""
    tprm_level = models.ForeignKey(
        TprmLevel,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_('TPRM Level')
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='tprm_level_translations',
        verbose_name=_('Country')
    )
    name_local = models.CharField(_('Local name'), max_length=100, blank=True)
    description_local = models.TextField(_('Local description'), blank=True)

    class Meta:
        verbose_name = _('TPRM Level translation')
        verbose_name_plural = _('TPRM Level translations')
        unique_together = [('tprm_level', 'country')]
        ordering = ['country__name']


# Proxy models for separate admin sections (Home › App_Tprm › …)
class TprmRiskLevel(TprmLevel):
    class Meta:
        proxy = True
        verbose_name = _('Risk Level')
        verbose_name_plural = _('Risk Levels')


class TprmStatusLevel(TprmLevel):
    class Meta:
        proxy = True
        verbose_name = _('Status')
        verbose_name_plural = _('Status')


class TprmCriticalityLevel(TprmLevel):
    class Meta:
        proxy = True
        verbose_name = _('Criticality level')
        verbose_name_plural = _('Criticality levels')


class TprmSanctionsVerification(TprmLevel):
    class Meta:
        proxy = True
        verbose_name = _('Sanctions verification')
        verbose_name_plural = _('Sanctions verification')


class TprmDataAccessLevel(TprmLevel):
    class Meta:
        proxy = True
        verbose_name = _('Data Access Level')
        verbose_name_plural = _('Data Access Levels')


class TprmDataAccessRights(TprmLevel):
    class Meta:
        proxy = True
        verbose_name = _('Data Access rights')
        verbose_name_plural = _('Data Access rights')


class Vendor(models.Model):
    """Third-party vendor/supplier"""
    
    name = models.CharField(_('Vendor Name'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    contract = models.TextField(
        _('Contract'),
        blank=True,
        help_text=_('Summary or description of the agreement with this vendor')
    )
    contract_validity = models.TextField(
        _('Contract validity period'),
        blank=True,
        help_text=_('Optional: how long the contract is valid (e.g. fixed term, renewal rules)')
    )
    contract_end_date = models.DateField(
        _('Contract end date'),
        null=True,
        blank=True,
        help_text=_('Optional: explicit end date of the contract')
    )
    website = models.URLField(_('Website'), blank=True)
    contact_person = models.CharField(_('Contact Person'), max_length=255, blank=True)
    contact_email = models.EmailField(_('Contact Email'), blank=True)
    contact_phone = models.CharField(_('Contact Phone'), max_length=50, blank=True)
    
    risk_level = models.ForeignKey(
        TprmLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors_risk',
        limit_choices_to={'type': TprmLevel.TYPE_RISK_LEVEL, 'is_active': True},
        verbose_name=_('Risk Level')
    )
    status = models.ForeignKey(
        TprmLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors_status',
        limit_choices_to={'type': TprmLevel.TYPE_STATUS, 'is_active': True},
        verbose_name=_('Status')
    )
    
    services_provided = models.TextField(_('Services Provided'), blank=True)
    nda_in_contract = models.BooleanField(
        _('NDA in contract'),
        default=False,
        help_text=_('Presence of non-disclosure provisions in the contract')
    )
    criticality_level = models.ForeignKey(
        TprmLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors_criticality',
        limit_choices_to={'type': TprmLevel.TYPE_CRITICALITY, 'is_active': True},
        verbose_name=_('Criticality level for the company')
    )
    sanctions_verification_status = models.ForeignKey(
        TprmLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors_sanctions',
        limit_choices_to={'type': TprmLevel.TYPE_SANCTIONS, 'is_active': True},
        verbose_name=_('Sanctions list verification status')
    )
    data_access_level = models.ForeignKey(
        TprmLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors_data_access',
        limit_choices_to={'type': TprmLevel.TYPE_DATA_ACCESS, 'is_active': True},
        verbose_name=_('Data Access Level')
    )
    data_access_rights = models.ForeignKey(
        TprmLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendors_data_access_rights',
        limit_choices_to={'type': TprmLevel.TYPE_DATA_ACCESS_RIGHTS, 'is_active': True},
        verbose_name=_('Data Access rights')
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='vendors',
        verbose_name=_('Company'),
        null=True,
        blank=True
    )
    owners = models.ManyToManyField(
        'TprmOwner',
        related_name='owned_vendors',
        blank=True,
        verbose_name=_('Owners'),
    )

    is_active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Uncheck to mark the vendor as inactive without deleting the record.')
    )

    actualization_date = models.DateTimeField(
        _('Actualization date'),
        null=True,
        blank=True,
        help_text=_('When the vendor record was last confirmed as actual by an owner.')
    )
    actualized_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actualized_vendors',
        verbose_name=_('Actualized by'),
        help_text=_('User who last actualized this vendor record.')
    )
    marked_no_longer_actual_at = models.DateTimeField(
        _('Marked no longer actual at'),
        null=True,
        blank=True,
        help_text=_('When the owner marked this record as no longer actual.')
    )
    marked_no_longer_comment = models.TextField(
        _('Marked no longer actual comment'),
        blank=True,
        help_text=_('Optional comment when marked as no longer actual.')
    )

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_vendors', verbose_name=_('Created By'))
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Vendor')
        verbose_name_plural = _('Vendors')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class VendorHistory(models.Model):
    """Audit trail for vendor changes (similar to app_asset AssetHistory)."""

    ACTION_CREATED = 'created'
    ACTION_MODIFIED = 'modified'
    ACTION_OWNERS_CHANGED = 'owners_changed'
    ACTION_ACTUALIZED = 'actualized'
    ACTION_MARKED_NOT_ACTUAL = 'marked_not_actual'

    ACTION_CHOICES = [
        (ACTION_CREATED, _('Created')),
        (ACTION_MODIFIED, _('Modified')),
        (ACTION_OWNERS_CHANGED, _('Owners changed')),
        (ACTION_ACTUALIZED, _('Actualized')),
        (ACTION_MARKED_NOT_ACTUAL, _('Marked as no longer actual')),
    ]

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name=_('Vendor'),
    )
    timestamp = models.DateTimeField(_('Timestamp'), auto_now_add=True)
    action = models.CharField(_('Action'), max_length=50, choices=ACTION_CHOICES)
    action_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendor_history_actions',
        verbose_name=_('Action by'),
    )
    details = models.TextField(_('Details'), blank=True)
    changes = models.JSONField(_('Changes'), null=True, blank=True)

    class Meta:
        verbose_name = _('Vendor history')
        verbose_name_plural = _('Vendor history')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['vendor', '-timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f'{self.vendor_id} — {self.action} @ {self.timestamp}'

    def get_action_by_name(self):
        if self.action_by:
            return self.action_by.get_full_name() or self.action_by.username
        return gettext('System')


class VendorAssessment(models.Model):
    """Risk assessment for a vendor"""
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    ]
    
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='assessments', verbose_name=_('Vendor'))
    assessment_date = models.DateField(_('Assessment Date'))
    next_review_date = models.DateField(_('Next Review Date'), null=True, blank=True)
    
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Assessment scores (0-100)
    security_score = models.IntegerField(_('Security Score'), validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    compliance_score = models.IntegerField(_('Compliance Score'), validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    financial_score = models.IntegerField(_('Financial Score'), validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    operational_score = models.IntegerField(_('Operational Score'), validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    
    overall_score = models.IntegerField(_('Overall Score'), validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    
    findings = models.TextField(_('Findings'), blank=True)
    recommendations = models.TextField(_('Recommendations'), blank=True)
    
    assessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assessments_conducted', verbose_name=_('Assessed By'))
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessments_approved', verbose_name=_('Approved By'))
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Vendor Assessment')
        verbose_name_plural = _('Vendor Assessments')
        ordering = ['-assessment_date']
    
    def __str__(self):
        return f"{self.vendor.name} - {self.assessment_date}"
    
    def save(self, *args, **kwargs):
        # Calculate overall score as average of all scores
        scores = [s for s in [self.security_score, self.compliance_score, 
                             self.financial_score, self.operational_score] if s is not None]
        if scores:
            self.overall_score = sum(scores) // len(scores)
        super().save(*args, **kwargs)


class VendorDocument(models.Model):
    """Documents related to vendors"""
    
    DOCUMENT_TYPE_CHOICES = [
        ('contract', _('Contract')),
        ('sla', _('SLA')),
        ('security_cert', _('Security Certificate')),
        ('compliance_cert', _('Compliance Certificate')),
        ('insurance', _('Insurance')),
        ('other', _('Other')),
    ]
    
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='documents', verbose_name=_('Vendor'))
    document_type = models.CharField(_('Document Type'), max_length=50, choices=DOCUMENT_TYPE_CHOICES)
    title = models.CharField(_('Title'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    file = models.FileField(_('File'), upload_to='tprm/documents/')
    
    expiry_date = models.DateField(_('Expiry Date'), null=True, blank=True)
    
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name=_('Uploaded By'))
    uploaded_at = models.DateTimeField(_('Uploaded At'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Vendor Document')
        verbose_name_plural = _('Vendor Documents')
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.vendor.name} - {self.title}"


class QuestionnaireTemplate(models.Model):
    """Template for vendor assessment questionnaires"""
    
    CATEGORY_CHOICES = [
        ('security', _('Security')),
        ('compliance', _('Compliance')),
        ('financial', _('Financial')),
        ('operational', _('Operational')),
        ('privacy', _('Data Privacy')),
        ('business', _('Business Continuity')),
    ]
    
    name = models.CharField(_('Template Name'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    category = models.CharField(_('Category'), max_length=50, choices=CATEGORY_CHOICES)
    is_active = models.BooleanField(_('Active'), default=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name=_('Created By'))
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Questionnaire Template')
        verbose_name_plural = _('Questionnaire Templates')
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.get_category_display()} - {self.name}"
    
    def get_total_score(self):
        return self.questions.aggregate(total=models.Sum('weight'))['total'] or 0


class Question(models.Model):
    """Individual question with conditional branching logic"""
    
    QUESTION_TYPE_CHOICES = [
        ('yes_no', _('Yes/No')),
        ('multiple_choice', _('Multiple Choice')),
        ('scale', _('Scale (1-5)')),
        ('text', _('Text Response')),
    ]
    
    template = models.ForeignKey(QuestionnaireTemplate, on_delete=models.CASCADE, related_name='questions', verbose_name=_('Template'))
    question_text = models.TextField(_('Question Text'))
    question_type = models.CharField(_('Question Type'), max_length=20, choices=QUESTION_TYPE_CHOICES, default='yes_no')
    
    # For multiple choice questions
    choices = models.JSONField(_('Answer Choices'), default=list, blank=True)
    
    # Conditional Logic / Branching
    parent_question = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='child_questions',
        verbose_name=_('Parent Question'),
        help_text=_('Show this question only if parent meets condition')
    )
    show_if_answer = models.CharField(
        _('Show If Answer'), 
        max_length=255, 
        blank=True,
        help_text=_('Condition: yes/no/option/1-3 (range)')
    )
    
    # Scoring
    weight = models.IntegerField(_('Weight'), default=1)
    correct_answer = models.CharField(_('Correct Answer'), max_length=255, blank=True)
    
    order = models.IntegerField(_('Order'), default=0)
    is_required = models.BooleanField(_('Required'), default=True)
    help_text = models.TextField(_('Help Text'), blank=True)
    
    class Meta:
        verbose_name = _('Question')
        verbose_name_plural = _('Questions')
        ordering = ['template', 'order']
    
    def __str__(self):
        return f"{self.template.name} - Q{self.order}: {self.question_text[:50]}"
    
    def should_show(self, responses_dict):
        """Check if question should be shown based on conditional logic"""
        if not self.parent_question:
            return True
        
        parent_response = responses_dict.get(self.parent_question.pk)
        if not parent_response:
            return False
        
        condition = self.show_if_answer.lower()
        
        if self.parent_question.question_type == 'yes_no':
            if condition == 'yes':
                return parent_response.response_bool == True
            elif condition == 'no':
                return parent_response.response_bool == False
        elif self.parent_question.question_type == 'scale':
            if '-' in condition:
                min_val, max_val = map(int, condition.split('-'))
                return min_val <= (parent_response.response_scale or 0) <= max_val
            else:
                return parent_response.response_scale == int(condition)
        elif self.parent_question.question_type == 'multiple_choice':
            return parent_response.response_choice == condition
        
        return True


class VendorQuestionnaire(models.Model):
    """Completed questionnaire for a vendor"""
    
    STATUS_CHOICES = [
        ('not_started', _('Not Started')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('reviewed', _('Reviewed')),
    ]
    
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='questionnaires', verbose_name=_('Vendor'))
    template = models.ForeignKey(QuestionnaireTemplate, on_delete=models.PROTECT, verbose_name=_('Template'))
    assessment = models.ForeignKey(VendorAssessment, on_delete=models.CASCADE, null=True, blank=True, related_name='questionnaires')
    
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='not_started')
    
    started_date = models.DateTimeField(_('Started Date'), null=True, blank=True)
    completed_date = models.DateTimeField(_('Completed Date'), null=True, blank=True)
    
    total_score = models.IntegerField(_('Total Score'), default=0)
    max_score = models.IntegerField(_('Maximum Score'), default=0)
    percentage_score = models.DecimalField(_('Percentage Score'), max_digits=5, decimal_places=2, default=0)
    
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_questionnaires')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_questionnaires')
    
    notes = models.TextField(_('Notes'), blank=True)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('Vendor Questionnaire')
        verbose_name_plural = _('Vendor Questionnaires')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.vendor.name} - {self.template.name}"
    
    def calculate_score(self):
        total = 0
        max_total = 0
        
        for response in self.responses.all():
            max_total += response.question.weight
            if response.score is not None:
                total += response.score
        
        self.total_score = total
        self.max_score = max_total
        if max_total > 0:
            self.percentage_score = (total / max_total) * 100
        else:
            self.percentage_score = 0
        
        self.save()


class QuestionResponse(models.Model):
    """Response to a specific question"""
    
    questionnaire = models.ForeignKey(VendorQuestionnaire, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    
    response_text = models.TextField(_('Response'), blank=True)
    response_choice = models.CharField(_('Selected Choice'), max_length=255, blank=True)
    response_bool = models.BooleanField(_('Yes/No'), null=True, blank=True)
    response_scale = models.IntegerField(_('Scale'), null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    score = models.IntegerField(_('Score'), null=True, blank=True)
    
    evidence_document = models.ForeignKey(VendorDocument, on_delete=models.SET_NULL, null=True, blank=True)
    evidence_notes = models.TextField(_('Evidence Notes'), blank=True)
    
    answered_at = models.DateTimeField(_('Answered At'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('Question Response')
        verbose_name_plural = _('Question Responses')
        unique_together = ['questionnaire', 'question']
        ordering = ['question__order']
    
    def __str__(self):
        return f"{self.questionnaire.vendor.name} - {self.question.question_text[:30]}"
    
    def auto_score(self):
        if self.question.question_type == 'yes_no' and self.response_bool is not None:
            if self.question.correct_answer.lower() == 'yes' and self.response_bool:
                self.score = self.question.weight
            elif self.question.correct_answer.lower() == 'no' and not self.response_bool:
                self.score = self.question.weight
            else:
                self.score = 0
        elif self.question.question_type == 'scale' and self.response_scale is not None:
            self.score = int((self.response_scale / 5) * self.question.weight)
        
        self.save()


class TPRMAccess(models.Model):
    """Права доступу до модуля TPRM (Third-Party Risk Management)"""
    
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        verbose_name=_("Group")
    )
    
    # Vendor Management
    has_access_vendors = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Vendors")
    )
    can_edit_vendors = models.BooleanField(
        default=False,
        verbose_name=_("Can create/edit Vendors")
    )
    can_delete_vendors = models.BooleanField(
        default=False,
        verbose_name=_("Can delete Vendors")
    )
    
    # Vendor Assessment Management
    has_access_assessments = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Vendor Assessments")
    )
    can_conduct_assessments = models.BooleanField(
        default=False,
        verbose_name=_("Can conduct Vendor Assessments")
    )
    can_approve_assessments = models.BooleanField(
        default=False,
        verbose_name=_("Can approve Vendor Assessments")
    )
    
    # Document Management
    has_access_documents = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Vendor Documents")
    )
    can_upload_documents = models.BooleanField(
        default=False,
        verbose_name=_("Can upload Vendor Documents")
    )
    can_delete_documents = models.BooleanField(
        default=False,
        verbose_name=_("Can delete Vendor Documents")
    )
    
    # Questionnaire Template Management
    has_access_templates = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Questionnaire Templates")
    )
    can_edit_templates = models.BooleanField(
        default=False,
        verbose_name=_("Can create/edit Questionnaire Templates")
    )
    can_manage_questions = models.BooleanField(
        default=False,
        verbose_name=_("Can manage Questions")
    )
    
    # Questionnaire Management
    has_access_questionnaires = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Vendor Questionnaires")
    )
    can_complete_questionnaires = models.BooleanField(
        default=False,
        verbose_name=_("Can complete Questionnaires")
    )
    can_review_questionnaires = models.BooleanField(
        default=False,
        verbose_name=_("Can review Questionnaires")
    )
    
    # Dashboard and Reporting
    has_access_dashboard = models.BooleanField(
        default=False,
        verbose_name=_("Has access to TPRM Dashboard")
    )
    can_generate_reports = models.BooleanField(
        default=False,
        verbose_name=_("Can generate TPRM Reports")
    )
    can_export_data = models.BooleanField(
        default=False,
        verbose_name=_("Can export TPRM data")
    )
    
    # Risk Management
    can_change_risk_level = models.BooleanField(
        default=False,
        verbose_name=_("Can change Vendor Risk Level")
    )
    can_change_vendor_status = models.BooleanField(
        default=False,
        verbose_name=_("Can change Vendor Status")
    )
    
    # Company filtering
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='tprm_access',
        verbose_name=_("Companies")
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    
    class Meta:
        verbose_name = _("TPRM Access")
        verbose_name_plural = _("TPRM Access")
        unique_together = [('group',)]
    
    def __str__(self):
        return f"{self.group.name} - TPRM Access"


class VendorSurveyLink(models.Model):
    """Unique external link for vendor to access questionnaire"""
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('expired', _('Expired')),
        ('used', _('Used')),
        ('revoked', _('Revoked')),
    ]
    
    # Unique token for external access
    token = models.CharField(
        _('Token'),
        max_length=64,
        unique=True,
        db_index=True,
        help_text=_('Unique token for external access')
    )
    
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='survey_links',
        verbose_name=_('Vendor')
    )
    
    questionnaire = models.ForeignKey(
        VendorQuestionnaire,
        on_delete=models.CASCADE,
        related_name='external_links',
        verbose_name=_('Questionnaire'),
        null=True,
        blank=True
    )
    
    template = models.ForeignKey(
        QuestionnaireTemplate,
        on_delete=models.CASCADE,
        related_name='external_links',
        verbose_name=_('Template'),
        null=True,
        blank=True,
        help_text=_('Template to use if questionnaire not yet created')
    )
    
    # Link configuration
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    expires_at = models.DateTimeField(
        _('Expires At'),
        null=True,
        blank=True,
        help_text=_('Link expiration date (leave empty for no expiration)')
    )
    
    is_one_time_use = models.BooleanField(
        _('One-Time Use'),
        default=False,
        help_text=_('Link can only be used once')
    )
    
    max_uses = models.IntegerField(
        _('Maximum Uses'),
        default=1,
        help_text=_('Maximum number of times link can be accessed')
    )
    
    current_uses = models.IntegerField(
        _('Current Uses'),
        default=0,
        help_text=_('Number of times link has been accessed')
    )
    
    # Access tracking
    first_accessed_at = models.DateTimeField(
        _('First Accessed At'),
        null=True,
        blank=True
    )
    
    last_accessed_at = models.DateTimeField(
        _('Last Accessed At'),
        null=True,
        blank=True
    )
    
    accessed_from_ip = models.GenericIPAddressField(
        _('Accessed From IP'),
        null=True,
        blank=True
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_survey_links',
        verbose_name=_('Created By')
    )
    
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True
    )
    
    notes = models.TextField(
        _('Notes'),
        blank=True,
        help_text=_('Internal notes about this link')
    )
    
    class Meta:
        verbose_name = _('Vendor Survey Link')
        verbose_name_plural = _('Vendor Survey Links')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['vendor', 'status']),
        ]
    
    def __str__(self):
        return f"{self.vendor.name} - {self.token[:8]}..."
    
    def save(self, *args, **kwargs):
        # Generate unique token if not set
        if not self.token:
            self.token = self.generate_unique_token()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_unique_token():
        """Generate a unique token for external access"""
        while True:
            token = str(uuid.uuid4()).replace('-', '')
            if not VendorSurveyLink.objects.filter(token=token).exists():
                return token
    
    def is_valid(self):
        """Check if link is still valid"""
        if self.status != 'active':
            return False
        
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        
        if self.is_one_time_use and self.current_uses >= 1:
            return False
        
        if self.current_uses >= self.max_uses:
            return False
        
        return True
    
    def record_access(self, ip_address=None):
        """Record that link was accessed"""
        now = timezone.now()
        
        if not self.first_accessed_at:
            self.first_accessed_at = now
        
        self.last_accessed_at = now
        self.current_uses += 1
        
        if ip_address:
            self.accessed_from_ip = ip_address
        
        # Update status if needed
        if self.is_one_time_use and self.current_uses >= 1:
            self.status = 'used'
        elif self.current_uses >= self.max_uses:
            self.status = 'used'
        
        self.save()
    
    def get_questionnaire_or_create(self):
        """Get existing questionnaire or create new one from template"""
        if self.questionnaire:
            return self.questionnaire
        
        if not self.template:
            return None
        
        # Create new questionnaire
        questionnaire = VendorQuestionnaire.objects.create(
            vendor=self.vendor,
            template=self.template,
            status='not_started'
        )
        
        # Create responses for all questions
        for question in self.template.questions.all():
            QuestionResponse.objects.create(
                questionnaire=questionnaire,
                question=question
            )
        
        # Link questionnaire to this link
        self.questionnaire = questionnaire
        self.save()
        
        return questionnaire
    
    def get_absolute_url(self, request=None):
        """Get absolute URL for this external link using Site Domain from Site URL Settings"""
        from django.urls import reverse
        
        path = reverse('app_tprm:survey_link_access', kwargs={'token': self.token})
        
        # Primary: Use Site Domain from SiteSettings (Site URL Settings)
        # This ensures external links always use the configured domain, not the request host
        try:
            from app_conf.models import SiteSettings
            site_settings = SiteSettings.get_settings()
            if site_settings and site_settings.site_domain and site_settings.site_domain.strip():
                # Use get_site_url() method which combines protocol + domain
                base = site_settings.get_site_url().rstrip('/')
                return f"{base}{path}"
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not load SiteSettings for external link URL: {e}")
        
        # Fallback to PUBLIC_BASE_URL from settings
        try:
            from django.conf import settings
            base = getattr(settings, 'PUBLIC_BASE_URL', '')
            if base and base.strip():
                return f"{base.rstrip('/')}{path}"
        except Exception:
            pass
        
        # Last resort: Use request if available
        if request:
            return request.build_absolute_uri(path)
        
        # Final fallback: return relative path
        return path


from tinymce.models import HTMLField


class TprmGuide(models.Model):
    """Base Guide for TPRM. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("TPRM Guide")
        verbose_name_plural = _("TPRM Guides")

    def __str__(self):
        return gettext("TPRM Guide")


class TprmGuideTranslation(models.Model):
    """Per-country (language) translations of the TPRM Guide."""
    guide = models.ForeignKey(
        TprmGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="tprm_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("TPRM Guide Translation")
        verbose_name_plural = _("TPRM Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"