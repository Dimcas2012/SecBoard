from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext
from django.core.exceptions import ValidationError
from app_conf.models import Company, Country
from tinymce.models import HTMLField
import json


class ComplianceFramework(models.Model):
    """
    Фреймворк compliance (PCI DSS, ISO 27001, SOC 2, HIPAA тощо)
    """
    
    FRAMEWORK_TYPE_CHOICES = [
        ('pci_dss', 'PCI DSS'),
        ('iso_27001', 'ISO 27001'),
        ('soc2', 'SOC 2'),
        ('hipaa', 'HIPAA'),
        ('gdpr', 'GDPR'),
        ('nist', 'NIST'),
        ('cobit', 'COBIT'),
        ('cis', 'CIS Controls'),
        ('custom', _('Custom')),
    ]
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('active', _('Active')),
        ('archived', _('Archived')),
    ]
    
    # Основна інформація
    name = models.CharField(
        _("Framework Name"),
        max_length=200,
        help_text=_("Name of compliance framework")
    )
    framework_type = models.CharField(
        _("Framework Type"),
        max_length=50,
        choices=FRAMEWORK_TYPE_CHOICES,
        default='custom'
    )
    version = models.CharField(
        _("Version"),
        max_length=50,
        default='1.0',
        help_text=_("Framework version (e.g., 4.0 for PCI DSS 4.0)")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Detailed description of the framework")
    )
    
    # Статус
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    # Template/Instance System
    is_template = models.BooleanField(
        _("Is Template"),
        default=False,
        help_text=_("This is a master template that can be applied to companies")
    )
    template = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instances',
        verbose_name=_("Template"),
        help_text=_("The template this framework is based on")
    )
    
    # Зв'язки
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Company"),
        related_name='compliance_frameworks',
        help_text=_("Company this framework instance applies to (null for templates)")
    )
    
    # Метадані
    is_mandatory = models.BooleanField(
        _("Is Mandatory"),
        default=False,
        help_text=_("Whether this framework is mandatory for the organization")
    )
    implementation_deadline = models.DateField(
        _("Implementation Deadline"),
        null=True,
        blank=True
    )
    
    # Lifecycle Management
    REVIEW_FREQUENCY_CHOICES = [
        ('quarterly', _('Quarterly')),
        ('semi_annual', _('Semi-Annual')),
        ('annual', _('Annual')),
        ('biennial', _('Biennial')),
    ]
    
    review_frequency = models.CharField(
        _("Review Frequency"),
        max_length=20,
        choices=REVIEW_FREQUENCY_CHOICES,
        default='annual',
        help_text=_("How often this framework should be reviewed")
    )
    next_review_date = models.DateField(
        _("Next Review Date"),
        null=True,
        blank=True,
        help_text=_("When the next review is scheduled")
    )
    last_review_date = models.DateField(
        _("Last Review Date"),
        null=True,
        blank=True,
        help_text=_("When the framework was last reviewed")
    )
    review_owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_framework_reviews',
        verbose_name=_("Review Owner"),
        help_text=_("Person responsible for framework reviews")
    )
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_frameworks',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("Framework Compliance")
        verbose_name_plural = _("Frameworks Compliance")
        ordering = ['name', 'version']
        indexes = [
            models.Index(fields=['is_template']),
            models.Index(fields=['template']),
            models.Index(fields=['company']),
        ]
    
    def __str__(self):
        if self.is_template:
            return f"{self.name} {self.version} [Template]"
        elif self.company:
            return f"{self.name} {self.version} - {self.company.name}"
        return f"{self.name} {self.version}"
    
    def apply_to_company(self, company, created_by=None):
        """
        Застосувати цей template до компанії (створити instance)
        """
        if not self.is_template:
            raise ValueError("Only templates can be applied to companies")
        
        # Створюємо копію framework для компанії
        instance = ComplianceFramework.objects.create(
            name=self.name,
            framework_type=self.framework_type,
            version=self.version,
            description=self.description,
            status='active',
            is_template=False,
            template=self,
            company=company,
            is_mandatory=self.is_mandatory,
            implementation_deadline=self.implementation_deadline,
            created_by=created_by
        )
        
        # Копіюємо всі категорії та контролі
        for category in self.categories.all():
            category.copy_to_framework(instance)
        
        return instance
    
    def sync_from_template(self):
        """
        Синхронізувати instance з template (оновити структуру)
        """
        if self.is_template or not self.template:
            return False
        
        # Sync basic info
        self.name = self.template.name
        self.framework_type = self.template.framework_type
        self.version = self.template.version
        self.description = self.template.description
        self.save()
        
        # Sync categories and controls
        template_categories = self.template.categories.all()
        
        for template_cat in template_categories:
            # Get or create category
            instance_cat, created = ControlCategory.objects.get_or_create(
                framework=self,
                code=template_cat.code,
                defaults={
                    'name': template_cat.name,
                    'description': template_cat.description,
                    'order': template_cat.order,
                }
            )
            
            if not created:
                # Update existing category
                instance_cat.name = template_cat.name
                instance_cat.description = template_cat.description
                instance_cat.order = template_cat.order
                instance_cat.save()
            
            # Sync controls
            for template_ctrl in template_cat.controls.all():
                instance_ctrl, ctrl_created = Control.objects.get_or_create(
                    category=instance_cat,
                    code=template_ctrl.code,
                    defaults={
                        'name': template_ctrl.name,
                        'description': template_ctrl.description,
                        'priority': template_ctrl.priority,
                        'required_evidence_count': template_ctrl.required_evidence_count,
                        'status': 'not_started',  # Reset status for instances
                    }
                )
                
                if not ctrl_created:
                    # Update existing control (preserve status and assignments)
                    instance_ctrl.name = template_ctrl.name
                    instance_ctrl.description = template_ctrl.description
                    instance_ctrl.priority = template_ctrl.priority
                    instance_ctrl.required_evidence_count = template_ctrl.required_evidence_count
                    instance_ctrl.save()
        
        return True
    
    def get_completion_percentage(self):
        """Розрахунок % виконання всіх контролів у фреймворку"""
        total_controls = Control.objects.filter(
            category__framework=self
        ).count()
        
        if total_controls == 0:
            return 0
        
        completed_controls = Control.objects.filter(
            category__framework=self,
            status='completed'
        ).count()
        
        return round((completed_controls / total_controls) * 100, 2)
    
    def get_controls_by_status(self):
        """Статистика контролів за статусами"""
        controls = Control.objects.filter(category__framework=self)
        return {
            'total': controls.count(),
            'not_started': controls.filter(status='not_started').count(),
            'in_progress': controls.filter(status='in_progress').count(),
            'ready_for_review': controls.filter(status='ready_for_review').count(),
            'completed': controls.filter(status='completed').count(),
            'failed': controls.filter(status='failed').count(),
        }
    
    def get_days_until_review(self):
        """Кількість днів до наступного review"""
        if not self.next_review_date:
            return None
        
        from datetime import date
        delta = self.next_review_date - date.today()
        return delta.days
    
    def is_review_overdue(self):
        """Чи прострочено review"""
        days = self.get_days_until_review()
        return days is not None and days < 0
    
    def get_review_status_color(self):
        """Колір статусу review (для UI)"""
        days = self.get_days_until_review()
        if days is None:
            return '#6c757d'  # Gray - not scheduled
        elif days < 0:
            return '#dc3545'  # Red - overdue
        elif days <= 30:
            return '#ffc107'  # Yellow - due soon
        else:
            return '#28a745'  # Green - on track


class ControlCategory(models.Model):
    """
    Категорія контролів (наприклад, "Network Security Controls")
    """
    
    # Основна інформація
    framework = models.ForeignKey(
        ComplianceFramework,
        on_delete=models.CASCADE,
        related_name='categories',
        verbose_name=_("Framework")
    )
    code = models.CharField(
        _("Category Code"),
        max_length=50,
        help_text=_("Unique identifier within framework (e.g., REQ-1)")
    )
    name = models.CharField(
        _("Category Name"),
        max_length=500,
        help_text=_("Name of the control category")
    )
    description = models.TextField(
        _("Description"),
        blank=True
    )
    
    # Порядок відображення
    order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for displaying categories")
    )
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Frameworks Control Category")
        verbose_name_plural = _("Frameworks Control Categories")
        ordering = ['framework', 'order', 'code']
        unique_together = [['framework', 'code']]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def copy_to_framework(self, target_framework):
        """
        Копіювати цю категорію і всі її контролі в інший framework
        """
        # Створюємо копію категорії
        new_category = ControlCategory.objects.create(
            framework=target_framework,
            code=self.code,
            name=self.name,
            description=self.description,
            order=self.order
        )
        
        # Копіюємо всі контролі
        for control in self.controls.all():
            Control.objects.create(
                category=new_category,
                identifier=control.identifier,  # ← ВАЖЛИВО! Зберігаємо identifier
                code=control.code,
                name=control.name,
                description=control.description,
                priority=control.priority,
                required_evidence_count=control.required_evidence_count,
                status='not_started',  # Скидаємо статус для нового instance
                # Копіюємо також інші поля для PCI DSS
                framework_requirement=control.framework_requirement if hasattr(control, 'framework_requirement') else '',
                framework_code=control.framework_code if hasattr(control, 'framework_code') else '',
                title=control.title if hasattr(control, 'title') else '',
                internal_id=control.internal_id if hasattr(control, 'internal_id') else '',
                domain=control.domain if hasattr(control, 'domain') and control.domain else None,
                testing_procedure=control.testing_procedure if control.testing_procedure else '',
                implementation_guidance=control.implementation_guidance if control.implementation_guidance else '',
            )
        
        return new_category
    
    def get_completion_percentage(self):
        """Розрахунок % виконання контролів у категорії"""
        total_controls = self.controls.count()
        
        if total_controls == 0:
            return 0
        
        completed_controls = self.controls.filter(status='completed').count()
        
        return round((completed_controls / total_controls) * 100, 2)


class Control(models.Model):
    """
    Окремий контроль (наприклад, 1.1.1 "Security policies documented")
    """
    
    STATUS_CHOICES = [
        ('not_started', _('Not Started')),
        ('in_progress', _('In Progress')),
        ('ready_for_review', _('Ready for Review')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('not_applicable', _('Not Applicable')),
    ]
    
    PRIORITY_CHOICES = [
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('critical', _('Critical')),
    ]
    
    # Основна інформація
    category = models.ForeignKey(
        ControlCategory,
        on_delete=models.CASCADE,
        related_name='controls',
        verbose_name=_("Category")
    )
    parent_control = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_controls',
        verbose_name=_("Parent Control"),
        help_text=_("For hierarchical controls (e.g., 1.1.1 is sub-control of 1.1)")
    )
    
    # Unique identifier field (from CSV UID) - used as unique key within category
    identifier = models.CharField(
        _("Identifier"),
        max_length=50,
        default='',
        blank=True,
        help_text=_("Unique identifier from source system (e.g., UID: a7vas8rb) - internal use")
    )
    
    # Display fields (from CSV) - visible in UI
    framework_requirement = models.CharField(
        _("Framework Requirement"),
        max_length=50,
        blank=True,
        default='',
        help_text=_("Framework requirement number (e.g., 1.1, 1.2)")
    )
    framework_code = models.CharField(
        _("Framework Code"),
        max_length=50,
        blank=True,
        default='',
        help_text=_("Framework code (e.g., 1.1, 1.1.1, 1.1.1.a)")
    )
    title = models.CharField(
        _("Title"),
        max_length=200,
        blank=True,
        default='',
        help_text=_("Short title from framework (e.g., 1.1, 1.1.1)")
    )
    
    # Internal/legacy fields - hidden
    code = models.CharField(
        _("Control Code"),
        max_length=50,
        help_text=_("Control code for display (e.g., 1.1.1)")
    )
    internal_id = models.CharField(
        _("Internal ID"),
        max_length=50,
        blank=True,
        default='',
        help_text=_("Internal ID from source system (e.g., NET-192, CFG-76) - hidden field")
    )
    domain = models.ForeignKey(
        'FrameworkDomain',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='controls',
        verbose_name=_("Domain"),
        help_text=_("Control domain (e.g., NETWORK_SECURITY, CRYPTOGRAPHIC_PROTECTIONS)")
    )
    
    name = models.CharField(
        _("Control Name"),
        max_length=500
    )
    description = models.TextField(
        _("Description"),
        help_text=_("Full description of the control requirement")
    )
    
    # Статус та пріоритет
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_started'
    )
    status_changed_date = models.DateTimeField(
        _("Status Changed Date"),
        null=True,
        blank=True,
        help_text=_("Date when status was last changed")
    )
    priority = models.CharField(
        _("Priority"),
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    
    # Вимоги до доказів
    required_evidence_count = models.IntegerField(
        _("Required Evidence Count"),
        default=0,
        help_text=_("Minimum number of evidence items required")
    )
    evidence_description = models.TextField(
        _("Evidence Description"),
        blank=True,
        help_text=_("Description of what evidence is needed")
    )
    
    # Відповідальний (responsible person)
    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_controls',
        verbose_name=_("Responsible")
    )
    
    # Терміни
    target_completion_date = models.DateField(
        _("Target Completion Date"),
        null=True,
        blank=True
    )
    actual_completion_date = models.DateField(
        _("Actual Completion Date"),
        null=True,
        blank=True
    )
    
    # Верифікація
    is_verified = models.BooleanField(
        _("Is Verified"),
        default=False
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_controls',
        verbose_name=_("Verified By")
    )
    verified_date = models.DateTimeField(
        _("Verified Date"),
        null=True,
        blank=True
    )
    verification_notes = models.TextField(
        _("Verification Notes"),
        blank=True
    )
    
    # Додаткові поля
    implementation_guidance = models.TextField(
        _("Implementation Guidance"),
        blank=True,
        help_text=_("Guidance on how to implement this control")
    )
    testing_procedure = models.TextField(
        _("Testing Procedure"),
        blank=True,
        help_text=_("How to test compliance with this control")
    )
    
    # Порядок відображення
    order = models.IntegerField(
        _("Display Order"),
        default=0
    )
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_controls',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("Frameworks Control")
        verbose_name_plural = _("Frameworks Controls")
        ordering = ['category', 'order', 'code']
        unique_together = [['category', 'code']]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_evidence_count(self):
        """Кількість прикріплених доказів"""
        return self.evidences.filter(is_active=True).count()
    
    def has_sufficient_evidence(self):
        """Чи достатньо доказів для виконання контролю"""
        return self.get_evidence_count() >= self.required_evidence_count
    
    def get_approved_evidence_count(self):
        """Кількість затверджених доказів"""
        return self.evidences.filter(
            is_active=True,
            approval_status='approved'
        ).count()


class Evidence(models.Model):
    """
    Доказ виконання контролю (документ, скріншот, запис)
    """
    
    EVIDENCE_TYPE_CHOICES = [
        ('document', _('Document')),
        ('screenshot', _('Screenshot')),
        ('log', _('Log File')),
        ('policy', _('Policy')),
        ('procedure', _('Procedure')),
        ('certificate', _('Certificate')),
        ('report', _('Report')),
        ('other', _('Other')),
    ]
    
    APPROVAL_STATUS_CHOICES = [
        ('pending', _('Pending Review')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('needs_update', _('Needs Update')),
    ]
    
    # Основна інформація
    control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='evidences',
        verbose_name=_("Control")
    )
    
    title = models.CharField(
        _("Evidence Title"),
        max_length=500
    )
    description = models.TextField(
        _("Description"),
        blank=True
    )
    evidence_type = models.ForeignKey(
        'EvidenceType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evidences',
        verbose_name=_("Evidence Type"),
        help_text=_("Type of evidence")
    )
    evidence_type_old = models.CharField(
        _("Evidence Type (Old)"),
        max_length=50,
        choices=EVIDENCE_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text=_("Legacy field - will be migrated to evidence_type")
    )
    
    # Файл
    file = models.FileField(
        _("Evidence File"),
        upload_to='compliance/evidence/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text=_("Upload evidence file (PDF, image, etc.)")
    )
    file_size = models.IntegerField(
        _("File Size (bytes)"),
        null=True,
        blank=True
    )
    
    # Текстовий доказ (замість файлу)
    text_evidence = models.TextField(
        _("Text Evidence"),
        blank=True,
        help_text=_("Text-based evidence if no file is attached")
    )
    
    # Посилання
    external_link = models.URLField(
        _("External Link"),
        blank=True,
        help_text=_("Link to external evidence")
    )
    
    # Link to Mandatory Process
    mandatory_process = models.ForeignKey(
        'app_compliance.MandatoryProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='framework_control_evidences',
        verbose_name=_("Mandatory Process"),
        help_text=_("Link to a record from Mandatory Processes Registry")
    )
    
    # Link to Document Register
    register_document = models.ForeignKey(
        'app_doc.RegisterDocs',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='framework_control_evidences',
        verbose_name=_("Register Document"),
        help_text=_("Link to a document from Document Register")
    )
    
    # Link to Related Document
    related_document = models.ForeignKey(
        'app_doc.RelatedDocs',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='framework_control_evidences',
        verbose_name=_("Related Document"),
        help_text=_("Link to a related document")
    )
    
    # Статус схвалення
    approval_status = models.CharField(
        _("Approval Status"),
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending'
    )
    
    # Хто завантажив
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_evidences',
        verbose_name=_("Uploaded By")
    )
    uploaded_date = models.DateTimeField(_("Uploaded Date"), auto_now_add=True)
    
    # Хто перевірив
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_evidences',
        verbose_name=_("Reviewed By")
    )
    reviewed_date = models.DateTimeField(
        _("Reviewed Date"),
        null=True,
        blank=True
    )
    review_comments = models.TextField(
        _("Review Comments"),
        blank=True
    )
    
    # Термін дії
    expiration_date = models.DateField(
        _("Expiration Date"),
        null=True,
        blank=True,
        help_text=_("Date when evidence expires (e.g., for certificates)")
    )
    
    # Активність
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    # Аудит
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Frameworks Evidence")
        verbose_name_plural = _("Frameworks Evidences")
        ordering = ['-uploaded_date']
    
    def __str__(self):
        return f"{self.title} - {self.control.code}"
    
    def is_expired(self):
        """Чи прострочений доказ"""
        if self.expiration_date:
            return self.expiration_date < timezone.now().date()
        return False
    
    def save(self, *args, **kwargs):
        # Зберігаємо розмір файлу
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    @property
    def document_status(self):
        """Get document status from linked documents"""
        if self.register_document and self.register_document.status_doc:
            return self.register_document.status_doc
        if self.related_document and self.related_document.status_rel_doc:
            return self.related_document.status_rel_doc
        if self.mandatory_process and self.mandatory_process.source_document and self.mandatory_process.source_document.status_doc:
            return self.mandatory_process.source_document.status_doc
        return None
    
    @property
    def document_status_display(self):
        """Get localized document status"""
        status = self.document_status
        return str(status) if status else None


class ControlAssignment(models.Model):
    """
    Призначення контролю користувачу або групі
    """
    
    ASSIGNMENT_TYPE_CHOICES = [
        ('owner', _('Owner')),
        ('reviewer', _('Reviewer')),
        ('collaborator', _('Collaborator')),
    ]
    
    control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name=_("Control")
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='control_assignments',
        verbose_name=_("User")
    )
    assignment_type = models.CharField(
        _("Assignment Type"),
        max_length=20,
        choices=ASSIGNMENT_TYPE_CHOICES,
        default='collaborator'
    )
    
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='made_assignments',
        verbose_name=_("Assigned By")
    )
    assigned_date = models.DateTimeField(_("Assigned Date"), auto_now_add=True)
    
    notes = models.TextField(
        _("Assignment Notes"),
        blank=True
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    class Meta:
        verbose_name = _("Frameworks Control Assignment")
        verbose_name_plural = _("Frameworks Control Assignments")
        ordering = ['-assigned_date']
        unique_together = [['control', 'user', 'assignment_type']]
    
    def __str__(self):
        try:
            control_code = self.control.code
        except Control.DoesNotExist:
            control_code = _("Deleted control")
        user_display = getattr(self.user, "username", _("Deleted user"))
        return f"{user_display} - {control_code} ({self.assignment_type})"


class ComplianceAuditLog(models.Model):
    """
    Журнал аудиту всіх змін у compliance модулі
    """
    
    ACTION_CHOICES = [
        ('create', _('Created')),
        ('update', _('Updated')),
        ('delete', _('Deleted')),
        ('assign', _('Assigned')),
        ('verify', _('Verified')),
        ('approve', _('Approved')),
        ('reject', _('Rejected')),
        ('complete', _('Completed')),
        ('remind', _('Reminder sent')),
        ('export', _('Exported')),
    ]
    
    OBJECT_TYPE_CHOICES = [
        ('framework', _('Framework')),
        ('category', _('Category')),
        ('control', _('Control')),
        ('evidence', _('Evidence')),
        ('assignment', _('Assignment')),
        ('mandatory_process', _('Mandatory Process')),
    ]
    
    # Хто, що, коли
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='compliance_audit_logs',
        verbose_name=_("User")
    )
    action = models.CharField(
        _("Action"),
        max_length=20,
        choices=ACTION_CHOICES
    )
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True)
    
    # На який об'єкт
    object_type = models.CharField(
        _("Object Type"),
        max_length=20,
        choices=OBJECT_TYPE_CHOICES
    )
    object_id = models.IntegerField(_("Object ID"))
    object_repr = models.CharField(
        _("Object Representation"),
        max_length=500,
        help_text=_("String representation of the object")
    )
    
    # Деталі змін
    changes = models.TextField(
        _("Changes"),
        blank=True,
        help_text=_("JSON with before/after values")
    )
    
    # Контекст
    ip_address = models.GenericIPAddressField(
        _("IP Address"),
        null=True,
        blank=True
    )
    user_agent = models.TextField(_("User Agent"), blank=True)
    
    # Додаткові примітки
    notes = models.TextField(_("Notes"), blank=True)
    
    class Meta:
        verbose_name = _("Compliance Audit Log")
        verbose_name_plural = _("Compliance Audit Logs")
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['user', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.object_type} #{self.object_id}"
    
    def get_changes_dict(self):
        """Отримати зміни як словник"""
        if self.changes:
            try:
                return json.loads(self.changes)
            except json.JSONDecodeError:
                return {}
        return {}


class ControlMapping(models.Model):
    """
    Мапінг framework controls до інших framework, internal або local controls
    """
    
    source_control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='mapped_to',
        verbose_name=_("Source Control")
    )
    target_control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='mapped_from',
        verbose_name=_("Target Framework Control")
    )
    target_internal_control = models.ForeignKey(
        'InternalComplianceControl',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='framework_control_mappings',
        verbose_name=_("Target Internal Control")
    )
    target_local_control = models.ForeignKey(
        'LocalComplianceControl',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='framework_control_mappings',
        verbose_name=_("Target Local Control")
    )
    
    mapping_type = models.CharField(
        _("Mapping Type"),
        max_length=50,
        choices=[
            ('equivalent', _('Equivalent')),
            ('partial', _('Partial')),
            ('related', _('Related')),
        ],
        default='related'
    )
    
    notes = models.TextField(
        _("Mapping Notes"),
        blank=True
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Created By")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("Control Mapping")
        verbose_name_plural = _("Control Mappings")
        unique_together = [['source_control', 'target_control', 'target_internal_control', 'target_local_control', 'mapping_type']]
    
    def __str__(self):
        target = self.target_control or self.target_internal_control or self.target_local_control
        return f"{self.source_control.code} → {target}"
    
    def clean(self):
        if not self.target_control and not self.target_internal_control and not self.target_local_control:
            raise ValidationError(_('Select at least one target control for mapping'))
        if self.target_control and self.target_control.id == self.source_control.id:
            raise ValidationError(_('Cannot map control to itself'))
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ControlNote(models.Model):
    """
    Примітки до контролю з можливістю вкладення файлів
    """
    
    control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name=_("Control")
    )
    
    note = models.TextField(
        _("Note"),
        help_text=_("Note text")
    )
    
    attachment = models.FileField(
        _("Attachment"),
        upload_to='control_notes/%Y/%m/',
        null=True,
        blank=True,
        help_text=_("Optional file attachment")
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='control_notes',
        verbose_name=_("Created By")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text=_("Inactive notes are soft-deleted")
    )
    
    class Meta:
        verbose_name = _("Control Note")
        verbose_name_plural = _("Control Notes")
        ordering = ['-created_date']
    
    def __str__(self):
        return f"Note for {self.control.code} by {self.created_by.username if self.created_by else 'Unknown'}"
    
    @property
    def attachment_filename(self):
        """Повертає ім'я файлу без шляху"""
        if self.attachment:
            import os
            return os.path.basename(self.attachment.name)
        return None


class ControlNoteAttachment(models.Model):
    """
    Multiple file attachments for ControlNote
    """

    note = models.ForeignKey(
        ControlNote,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Note")
    )
    file = models.FileField(
        _("File"),
        upload_to='control_notes/%Y/%m/',
    )
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Control Note Attachment")
        verbose_name_plural = _("Control Note Attachments")
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Attachment for control note {self.note_id}"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name)


class AccessCompliance(models.Model):
    """
    Model for controlling access to Compliance module
    Controls which groups can access compliance data and for which companies
    """
    group = models.ForeignKey(
        'auth.Group',
        on_delete=models.CASCADE,
        verbose_name=_("Group")
    )
    has_access = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Framework Compliance Dashboard")
    )
    can_view_frameworks = models.BooleanField(
        default=False,
        verbose_name=_("Can view frameworks")
    )
    can_edit_frameworks = models.BooleanField(
        default=False,
        verbose_name=_("Can edit frameworks")
    )
    can_add_frameworks = models.BooleanField(
        default=False,
        verbose_name=_("Can add new frameworks")
    )
    can_delete_frameworks = models.BooleanField(
        default=False,
        verbose_name=_("Can delete frameworks")
    )
    can_view_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can view controls")
    )
    can_edit_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can edit controls")
    )
    can_add_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can add new controls")
    )
    can_delete_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can delete controls")
    )
    can_view_instance_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can view instance controls"),
        help_text=_("View controls in framework instances (applied to companies)")
    )
    can_edit_instance_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can edit instance controls"),
        help_text=_("Edit controls in framework instances (status, responsible, evidence)")
    )
    can_manage_evidence = models.BooleanField(
        default=False,
        verbose_name=_("Can manage evidence")
    )
    can_approve_evidence = models.BooleanField(
        default=False,
        verbose_name=_("Can approve evidence")
    )
    can_view_reports = models.BooleanField(
        default=False,
        verbose_name=_("Can view compliance reports")
    )
    can_export = models.BooleanField(
        default=False,
        verbose_name=_("Can export frameworks and data"),
        help_text=_("Can export frameworks, controls, and compliance data to Excel")
    )
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='access_compliance',
        verbose_name=_("Companies"),
        help_text=_("Companies this group can access. Leave empty for all companies.")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    
    class Meta:
        verbose_name = _("Access to Framework Compliance")
        verbose_name_plural = _("Access to Framework Compliance")
        unique_together = ['group']
    
    def __str__(self):
        return f"{self.group.name} - Access: {self.has_access}"


class AccessLocalCompliance(models.Model):
    """
    Model for controlling access to Local Compliance module
    Controls which groups can access local compliance data and for which companies
    """
    group = models.ForeignKey(
        'auth.Group',
        on_delete=models.CASCADE,
        verbose_name=_("Group")
    )
    has_access = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Local Compliance Dashboard")
    )
    # Regulators permissions
    can_view_regulators = models.BooleanField(
        default=False,
        verbose_name=_("Can view regulators")
    )
    can_edit_regulators = models.BooleanField(
        default=False,
        verbose_name=_("Can edit regulators")
    )
    can_add_regulators = models.BooleanField(
        default=False,
        verbose_name=_("Can add new regulators")
    )
    can_delete_regulators = models.BooleanField(
        default=False,
        verbose_name=_("Can delete regulators")
    )
    # Requirements permissions
    can_view_requirements = models.BooleanField(
        default=False,
        verbose_name=_("Can view requirements")
    )
    can_edit_requirements = models.BooleanField(
        default=False,
        verbose_name=_("Can edit requirements")
    )
    can_add_requirements = models.BooleanField(
        default=False,
        verbose_name=_("Can add new requirements")
    )
    can_delete_requirements = models.BooleanField(
        default=False,
        verbose_name=_("Can delete requirements")
    )
    can_view_requirement_instances = models.BooleanField(
        default=False,
        verbose_name=_("Can view requirement instances"),
        help_text=_("View requirement instances (applied to companies)")
    )
    can_edit_requirement_instances = models.BooleanField(
        default=False,
        verbose_name=_("Can edit requirement instances"),
        help_text=_("Edit requirement instances (status, dates, etc.)")
    )
    # Controls permissions
    can_view_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can view local controls")
    )
    can_edit_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can edit local controls")
    )
    can_add_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can add new local controls")
    )
    can_delete_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can delete local controls")
    )
    # Evidence permissions
    can_manage_evidence = models.BooleanField(
        default=False,
        verbose_name=_("Can manage evidence")
    )
    can_approve_evidence = models.BooleanField(
        default=False,
        verbose_name=_("Can approve evidence")
    )
    # Reports permissions
    can_view_reports = models.BooleanField(
        default=False,
        verbose_name=_("Can view local compliance reports")
    )
    can_export = models.BooleanField(
        default=False,
        verbose_name=_("Can export local compliance data"),
        help_text=_("Can export requirements, controls, and compliance data to Excel")
    )
    # Company access
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='access_local_compliance',
        verbose_name=_("Companies"),
        help_text=_("Companies this group can access. Leave empty for all companies.")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    
    class Meta:
        verbose_name = _("Access to Local Compliance")
        verbose_name_plural = _("Access to Local Compliance")
        unique_together = ['group']
    
    def __str__(self):
        return f"{self.group.name} - Local Access: {self.has_access}"


# ========================
# Local Compliance Models
# ========================

class CompanyType(models.Model):
    """
    Тип компанії (Банк, Кредитне бюро, Платіжна система тощо)
    """
    name = models.CharField(
        _("Type Name"),
        max_length=100,
        help_text=_("Company type name (e.g., Bank, Payment System)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Type name in local language (e.g., Банк, Платіжна система)")
    )
    code = models.CharField(
        _("Type Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., bank, payment_system)")
    )
    icon = models.CharField(
        _("Icon"),
        max_length=50,
        blank=True,
        help_text=_("Font Awesome icon class (e.g., fa-building, fa-credit-card)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#007bff',
        help_text=_("Hex color code for display (e.g., #007bff)")
    )
    
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='compliance_company_types',
        verbose_name=_("Companies"),
        help_text=_("Companies of this type")
    )
    
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description of this company type")
    )
    
    regulatory_requirements = models.TextField(
        _("Regulatory Requirements"),
        blank=True,
        help_text=_("Specific regulatory requirements for this type of company")
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Company Type")
        verbose_name_plural = _("Company Types")
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        if self.icon:
            return f"{self.name}"
        return f"{self.name}"


class RegulatorType(models.Model):
    """
    Тип регулятора (Financial, Banking, Securities тощо)
    """
    name = models.CharField(
        _("Type Name"),
        max_length=100,
        help_text=_("Regulator type name (e.g., Financial Regulator)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Type name in local language (e.g., Фінансовий регулятор)")
    )
    code = models.CharField(
        _("Type Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., financial, banking)")
    )
    icon = models.CharField(
        _("Icon"),
        max_length=50,
        blank=True,
        help_text=_("Font Awesome icon class (e.g., fa-landmark, fa-university)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#17a2b8',
        help_text=_("Hex color code for display (e.g., #17a2b8)")
    )
    
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='regulator_types',
        verbose_name=_("Companies"),
        help_text=_("Companies regulated by this type of regulator")
    )
    
    description = models.TextField(
        _("Description"),
        blank=True
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Regulator Type")
        verbose_name_plural = _("Regulator Types")
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name_local or self.name

    def get_local_name(self, country):
        """Get localized name for a specific country."""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except RegulatorTypeTranslation.DoesNotExist:
            return self.name_local or self.name


class RegulatorTypeTranslation(models.Model):
    """Переклади типів регуляторів для різних країн."""
    regulator_type = models.ForeignKey(
        RegulatorType,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Regulator Type")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='regulator_type_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Regulator type name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )

    class Meta:
        verbose_name = _("Regulator Type Translation")
        verbose_name_plural = _("Regulator Type Translations")
        unique_together = ['regulator_type', 'country']
        ordering = ['country__name']

    def __str__(self):
        return f"{self.regulator_type.name} - {self.country.name}: {self.name_local}"


class RequirementType(models.Model):
    """
    Тип вимоги (Закон, Постанова, Директива тощо)
    """
    name = models.CharField(
        _("Type Name"),
        max_length=100,
        help_text=_("Requirement type name (e.g., Law, Regulation)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Type name in local language (e.g., Закон, Постанова)")
    )
    code = models.CharField(
        _("Type Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., law, regulation)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#007bff',
        help_text=_("Hex color code for display")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    description = models.TextField(
        _("Description"),
        blank=True
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Requirement Type")
        verbose_name_plural = _("Requirement Types")
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name_local or self.name
    
    def get_local_name(self, country):
        """Get localized name for specific country"""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except RequirementTypeTranslation.DoesNotExist:
            return self.name_local or self.name


class RequirementTypeTranslation(models.Model):
    """
    Переклади типу вимоги для різних країн
    """
    requirement_type = models.ForeignKey(
        RequirementType,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Requirement Type")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='requirement_type_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Type name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )
    
    class Meta:
        verbose_name = _("Requirement Type Translation")
        verbose_name_plural = _("Requirement Type Translations")
        unique_together = ['requirement_type', 'country']
        ordering = ['country__name']
    
    def __str__(self):
        return f"{self.requirement_type.name} - {self.country.name}: {self.name_local}"


class EvidenceType(models.Model):
    """
    Тип доказу (Документ, Скріншот, Лог-файл тощо)
    """
    name = models.CharField(
        _("Type Name"),
        max_length=100,
        help_text=_("Evidence type name (e.g., Document, Screenshot)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Type name in local language (e.g., Документ, Скріншот)")
    )
    code = models.CharField(
        _("Type Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., document, screenshot)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#007bff',
        help_text=_("Hex color code for display")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    description = models.TextField(
        _("Description"),
        blank=True
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Evidence Type")
        verbose_name_plural = _("Evidence Types")
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name_local or self.name
    
    def get_name(self):
        """Get localized name based on current language"""
        return self.name_local or self.name
    
    def get_local_name(self, country):
        """Get localized name for specific country"""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except EvidenceTypeTranslation.DoesNotExist:
            return self.name_local or self.name


class EvidenceTypeTranslation(models.Model):
    """
    Переклади типу доказу для різних країн
    """
    evidence_type = models.ForeignKey(
        EvidenceType,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Evidence Type")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='evidence_type_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Type name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )
    
    class Meta:
        verbose_name = _("Evidence Type Translation")
        verbose_name_plural = _("Evidence Type Translations")
        unique_together = ['evidence_type', 'country']
        ordering = ['country__name']
    
    def __str__(self):
        return f"{self.evidence_type.name} - {self.country.name}: {self.name_local}"


class RequirementStatus(models.Model):
    """
    Статус вимоги (Чернетка, Активна, Призупинена, Архівована)
    """
    name = models.CharField(
        _("Status Name"),
        max_length=100,
        help_text=_("Status name (e.g., Draft, Active)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Status name in local language (e.g., Чернетка, Активна)")
    )
    code = models.CharField(
        _("Status Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., draft, active)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#28a745',
        help_text=_("Hex color code for display")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    description = models.TextField(
        _("Description"),
        blank=True
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Requirement Status")
        verbose_name_plural = _("Requirement Statuses")
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name_local or self.name
    
    def get_local_name(self, country):
        """Get localized name for specific country"""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except RequirementStatusTranslation.DoesNotExist:
            return self.name_local or self.name


class RequirementStatusTranslation(models.Model):
    """
    Переклади статусу вимоги для різних країн
    """
    requirement_status = models.ForeignKey(
        RequirementStatus,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Requirement Status")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='requirement_status_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Status name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )
    
    class Meta:
        verbose_name = _("Requirement Status Translation")
        verbose_name_plural = _("Requirement Status Translations")
        unique_together = ['requirement_status', 'country']
        ordering = ['country__name']
    
    def __str__(self):
        return f"{self.requirement_status.name} - {self.country.name}: {self.name_local}"


class RequirementPriority(models.Model):
    """
    Пріоритет вимоги (Низький, Середній, Високий, Критичний)
    """
    name = models.CharField(
        _("Priority Name"),
        max_length=100,
        help_text=_("Priority name (e.g., Low, Medium, High)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        blank=True,
        help_text=_("Priority name in local language (e.g., Низький, Середній)")
    )
    code = models.CharField(
        _("Priority Code"),
        max_length=50,
        unique=True,
        help_text=_("Unique code (e.g., low, medium, high)")
    )
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#ffc107',
        help_text=_("Hex color code for display")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order for display in lists (lower numbers first)")
    )
    description = models.TextField(
        _("Description"),
        blank=True
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    
    class Meta:
        verbose_name = _("Requirement Priority")
        verbose_name_plural = _("Requirement Priorities")
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name_local or self.name
    
    def get_local_name(self, country):
        """Get localized name for specific country"""
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except RequirementPriorityTranslation.DoesNotExist:
            return self.name_local or self.name


class RequirementPriorityTranslation(models.Model):
    """
    Переклади пріоритету вимоги для різних країн
    """
    requirement_priority = models.ForeignKey(
        RequirementPriority,
        on_delete=models.CASCADE,
        related_name='translations',
        verbose_name=_("Requirement Priority")
    )
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.CASCADE,
        related_name='requirement_priority_translations',
        verbose_name=_("Country")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=100,
        help_text=_("Priority name in country's language")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Description in country's language")
    )
    
    class Meta:
        verbose_name = _("Requirement Priority Translation")
        verbose_name_plural = _("Requirement Priority Translations")
        unique_together = ['requirement_priority', 'country']
        ordering = ['country__name']
    
    def __str__(self):
        return f"{self.requirement_priority.name} - {self.country.name}: {self.name_local}"


class LocalComplianceRegulator(models.Model):
    """
    Регулятор (НБУ, НКЦПФР, Мінфін тощо)
    """
    
    name = models.CharField(
        _("Regulator Name"),
        max_length=200,
        help_text=_("Name of regulatory body (e.g., National Bank of Ukraine)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=200,
        blank=True,
        help_text=_("Name in local language (e.g., Національний банк України)")
    )
    acronym = models.CharField(
        _("Acronym"),
        max_length=20,
        blank=True,
        help_text=_("Short name (e.g., NBU)")
    )
    
    country = models.ForeignKey(
        'app_conf.Country',
        on_delete=models.PROTECT,
        related_name='regulators',
        verbose_name=_("Country"),
        help_text=_("Country of the regulator")
    )
    
    regulator_type = models.ForeignKey(
        RegulatorType,
        on_delete=models.PROTECT,
        related_name='regulators',
        verbose_name=_("Regulator"),
        help_text=_("Type of regulator")
    )
    
    description = models.TextField(
        _("Description"),
        blank=True
    )
    
    website = models.URLField(
        _("Website"),
        blank=True
    )
    
    contact_email = models.EmailField(
        _("Contact Email"),
        blank=True
    )
    
    contact_phone = models.CharField(
        _("Contact Phone"),
        max_length=50,
        blank=True
    )
    
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#17a2b8',
        help_text=_("Hex color code for display (e.g., #17a2b8)")
    )
    
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='local_regulators',
        verbose_name=_("Companies"),
        help_text=_("Companies regulated by this regulator")
    )
    
    company_types = models.ManyToManyField(
        'CompanyType',
        blank=True,
        related_name='local_regulators',
        verbose_name=_("Company Types"),
        help_text=_("Types of companies this regulator oversees (e.g., Banks, Payment Systems)")
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_regulators',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("Local Compliance Regulator")
        verbose_name_plural = _("Local Compliance Regulators")
        ordering = ['country', 'name']
        indexes = [
            models.Index(fields=['country', 'is_active']),
            models.Index(fields=['regulator_type']),
        ]
    
    def __str__(self):
        if self.acronym:
            return f"{self.acronym} - {self.name}"
        return self.name


class LocalComplianceRequirement(models.Model):
    """
    Вимога регулятора (Закон, Постанова, Положення тощо)
    Підтримує Template/Instance систему для повторного використання
    """
    
    REQUIREMENT_TYPE_CHOICES = [
        ('law', _('Law')),
        ('regulation', _('Regulation')),
        ('directive', _('Directive')),
        ('resolution', _('Resolution')),
        ('ordinance', _('Ordinance')),
        ('guideline', _('Guideline')),
        ('standard', _('Standard')),
        ('circular', _('Circular')),
        ('instruction', _('Instruction')),
        ('other', _('Other')),
    ]
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('active', _('Active')),
        ('suspended', _('Suspended')),
        ('archived', _('Archived')),
    ]
    
    # Template/Instance System
    is_template = models.BooleanField(
        _("Is Template"),
        default=False,
        help_text=_("This is a master template that can be applied to companies")
    )
    template = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instances',
        verbose_name=_("Template"),
        help_text=_("The template this requirement is based on")
    )
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='local_compliance_requirements',
        verbose_name=_("Company"),
        help_text=_("Company this requirement instance belongs to (empty for templates)")
    )
    
    regulator = models.ForeignKey(
        LocalComplianceRegulator,
        on_delete=models.CASCADE,
        related_name='requirements',
        verbose_name=_("Regulator")
    )
    
    code = models.CharField(
        _("Requirement Code"),
        max_length=100,
        help_text=_("Official code/number (e.g., №77 від 15.06.2023)")
    )
    
    name = models.CharField(
        _("Requirement Name"),
        max_length=500,
        help_text=_("Full name of requirement")
    )
    
    name_local = models.CharField(
        _("Local Name"),
        max_length=500,
        blank=True,
        help_text=_("Name in local language")
    )
    
    requirement_type = models.CharField(
        _("Type"),
        max_length=50,
        choices=REQUIREMENT_TYPE_CHOICES,
        default='regulation'
    )
    
    description = models.TextField(
        _("Description"),
        blank=True
    )
    
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    # Applicability
    applicable_to = models.CharField(
        _("Applicable To"),
        max_length=200,
        blank=True,
        help_text=_("Which types of organizations (banks, financial institutions, etc.)")
    )
    
    # Important dates
    publication_date = models.DateField(
        _("Publication Date"),
        null=True,
        blank=True
    )
    
    effective_date = models.DateField(
        _("Effective Date"),
        null=True,
        blank=True,
        help_text=_("When requirement comes into force")
    )
    
    deadline_date = models.DateField(
        _("Compliance Deadline"),
        null=True,
        blank=True,
        help_text=_("Deadline for compliance")
    )
    
    review_date = models.DateField(
        _("Next Review Date"),
        null=True,
        blank=True
    )
    
    # References
    official_link = models.URLField(
        _("Official Link"),
        blank=True,
        help_text=_("Link to official document")
    )
    
    document_file = models.FileField(
        _("Document File"),
        upload_to='compliance/local_requirements/%Y/%m/',
        null=True,
        blank=True
    )
    
    # Metadata
    is_mandatory = models.BooleanField(
        _("Is Mandatory"),
        default=True
    )
    
    priority = models.CharField(
        _("Priority"),
        max_length=20,
        choices=Control.PRIORITY_CHOICES,
        default='medium'
    )
    
    company_types = models.ManyToManyField(
        'app_conf.CompanyType',
        blank=True,
        related_name='local_requirements',
        verbose_name=_("Company Types"),
        help_text=_("Company types this requirement applies to")
    )
    
    # Audit
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_local_requirements',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("Local Compliance Requirement")
        verbose_name_plural = _("Local Compliance Requirements")
        ordering = ['regulator', '-effective_date', 'code']
        indexes = [
            models.Index(fields=['regulator', 'status']),
            models.Index(fields=['effective_date']),
            models.Index(fields=['deadline_date']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def is_overdue(self):
        """Check if compliance deadline is overdue"""
        if self.deadline_date:
            return self.deadline_date < timezone.now().date()
        return False
    
    def days_until_deadline(self):
        """Days until compliance deadline"""
        if self.deadline_date:
            delta = self.deadline_date - timezone.now().date()
            return delta.days
        return None
    
    def apply_to_company(self, company, created_by=None):
        """
        Застосувати цей template до компанії (створити instance)
        """
        if not self.is_template:
            raise ValueError("Only templates can be applied to companies")
        
        # Створюємо копію requirement для компанії
        instance = LocalComplianceRequirement.objects.create(
            regulator=self.regulator,
            code=self.code,
            name=self.name,
            name_local=self.name_local,
            requirement_type=self.requirement_type,
            description=self.description,
            status=self.status,
            applicable_to=self.applicable_to,
            publication_date=self.publication_date,
            effective_date=self.effective_date,
            deadline_date=self.deadline_date,
            review_date=self.review_date,
            official_link=self.official_link,
            is_mandatory=self.is_mandatory,
            priority=self.priority,
            is_template=False,
            template=self,
            company=company,
            created_by=created_by
        )

        if self.company_types.exists():
            instance.company_types.set(self.company_types.all())

        # Копіюємо категорії та створюємо map
        category_map = {}
        for category in self.categories.all():
            new_category = category.copy_to_requirement(instance)
            category_map[category.id] = new_category
        
        # Копіюємо всі контролі з template
        for template_control in self.controls.filter(company__isnull=True):
            LocalComplianceControl.objects.create(
                requirement=instance,
                company=company,
                category=category_map.get(template_control.category_id),
                code=template_control.code,
                name=template_control.name,
                description=template_control.description,
                status='not_started',  # Скидаємо статус
                priority=template_control.priority,
                target_completion_date=template_control.target_completion_date,
                implementation_notes=template_control.implementation_notes,
                evidence_notes=template_control.evidence_notes,
                required_evidence_count=template_control.required_evidence_count,
                created_by=created_by
            )
        
        return instance
    
    def get_template_controls(self):
        """Отримати контролі template (без прив'язки до компанії)"""
        if self.is_template:
            return self.controls.filter(company__isnull=True)
        return self.controls.none()
    
    def get_controls_count(self):
        """Кількість контролів"""
        if self.is_template:
            return self.controls.filter(company__isnull=True).count()
        return self.controls.count()
    
    def get_instances_count(self):
        """Кількість instances для template"""
        if self.is_template:
            return self.instances.count()
        return 0


class LocalRequirementCategory(models.Model):
    """
    Категорія контролів для Local Compliance Requirement
    """

    requirement = models.ForeignKey(
        LocalComplianceRequirement,
        on_delete=models.CASCADE,
        related_name='categories',
        verbose_name=_("Requirement")
    )
    code = models.CharField(
        _("Category Code"),
        max_length=100,
        help_text=_("Unique identifier within requirement (e.g., CAT-1)")
    )
    name = models.CharField(
        _("Category Name"),
        max_length=500
    )
    description = models.TextField(
        _("Description"),
        blank=True
    )
    order = models.IntegerField(
        _("Display Order"),
        default=0
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("Local Requirement Category")
        verbose_name_plural = _("Local Requirement Categories")
        ordering = ['requirement', 'order', 'code']
        unique_together = [['requirement', 'code']]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def copy_to_requirement(self, target_requirement):
        """
        Копіювати категорію до іншої вимоги
        """
        return LocalRequirementCategory.objects.create(
            requirement=target_requirement,
            code=self.code,
            name=self.name,
            description=self.description,
            order=self.order
        )


class LocalRequirementNote(models.Model):
    """
    Notes for local requirement instances
    """

    requirement = models.ForeignKey(
        LocalComplianceRequirement,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name=_("Requirement"),
        help_text=_("Requirement this note belongs to")
    )
    note = models.TextField(_("Note"))
    attachment = models.FileField(
        _("Attachment"),
        upload_to='compliance/local_requirement_notes/%Y/%m/',
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='local_requirement_notes',
        verbose_name=_("Created By")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Local Requirement Note")
        verbose_name_plural = _("Local Requirement Notes")
        ordering = ['-created_date']

    def __str__(self):
        return f"Note for requirement {self.requirement_id}"

    @property
    def attachment_filename(self):
        if self.attachment:
            import os
            return os.path.basename(self.attachment.name)
        return None


class LocalRequirementNoteAttachment(models.Model):
    """
    Multiple file attachments for LocalRequirementNote
    """

    note = models.ForeignKey(
        LocalRequirementNote,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Note")
    )
    file = models.FileField(
        _("File"),
        upload_to='compliance/local_requirement_notes/%Y/%m/',
    )
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Local Requirement Note Attachment")
        verbose_name_plural = _("Local Requirement Note Attachments")
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Attachment for local requirement note {self.note_id}"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name)


class LocalComplianceControl(models.Model):
    """
    Контроль для виконання місцевої вимоги compliance
    """
    
    requirement = models.ForeignKey(
        LocalComplianceRequirement,
        on_delete=models.CASCADE,
        related_name='controls',
        verbose_name=_("Requirement")
    )
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='local_compliance_controls',
        verbose_name=_("Company"),
        help_text=_("Company this control applies to (null for template controls)")
    )
    category = models.ForeignKey(
        LocalRequirementCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='controls',
        verbose_name=_("Category")
    )
    
    code = models.CharField(
        _("Control Code"),
        max_length=100,
        help_text=_("Internal control code")
    )
    
    name = models.CharField(
        _("Control Name"),
        max_length=500
    )
    
    description = models.TextField(
        _("Description"),
        blank=True
    )
    
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Control.STATUS_CHOICES,
        default='not_started'
    )
    status_changed_date = models.DateTimeField(
        _("Status Changed Date"),
        null=True,
        blank=True
    )
    
    priority = models.CharField(
        _("Priority"),
        max_length=20,
        choices=Control.PRIORITY_CHOICES,
        default='medium'
    )
    
    # Assignment
    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_compliance_controls',
        verbose_name=_("Responsible")
    )
    
    # Dates
    target_completion_date = models.DateField(
        _("Target Completion Date"),
        null=True,
        blank=True
    )
    
    actual_completion_date = models.DateField(
        _("Actual Completion Date"),
        null=True,
        blank=True
    )
    
    # Implementation details
    implementation_notes = models.TextField(
        _("Implementation Notes"),
        blank=True
    )
    
    # Evidence
    evidence_files = models.FileField(
        _("Evidence Files"),
        upload_to='compliance/local_evidence/%Y/%m/',
        null=True,
        blank=True
    )
    
    evidence_notes = models.TextField(
        _("Evidence Notes"),
        blank=True
    )
    required_evidence_count = models.PositiveIntegerField(
        _("Required Evidence Count"),
        default=1,
        help_text=_("How many evidence items are required for this control")
    )
    
    # Verification
    is_verified = models.BooleanField(
        _("Is Verified"),
        default=False
    )
    
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_local_controls',
        verbose_name=_("Verified By")
    )
    
    verified_date = models.DateTimeField(
        _("Verified Date"),
        null=True,
        blank=True
    )
    
    # Link to framework control (optional)
    related_framework_control = models.ForeignKey(
        Control,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_compliance_mappings',
        verbose_name=_("Related Framework Control"),
        help_text=_("Link to related international framework control")
    )
    
    # Audit
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_local_controls',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("Local Compliance Control")
        verbose_name_plural = _("Local Compliance Controls")
        ordering = ['requirement', 'company', 'code']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['responsible']),
            models.Index(fields=['target_completion_date']),
        ]
        # Note: unique_together не використовується через можливість NULL в company
        # Унікальність забезпечується на рівні бізнес-логіки
    
    def __str__(self):
        if self.company:
            return f"{self.code} - {self.name} ({self.company.name})"
        return f"{self.code} - {self.name} [Template]"
    
    def is_overdue(self):
        """Check if control is overdue"""
        if self.target_completion_date and self.status not in ['completed', 'not_applicable']:
            return self.target_completion_date < timezone.now().date()
        return False

    def get_evidence_count(self):
        """Кількість прикріплених доказів"""
        return self.evidences.filter(is_active=True).count()

    def get_approved_evidence_count(self):
        """Кількість затверджених доказів"""
        return self.evidences.filter(is_active=True, approval_status='approved').count()

    def has_sufficient_evidence(self):
        """Чи достатньо доказів"""
        required = self.required_evidence_count or 0
        if required <= 0:
            return self.evidences.filter(is_active=True).exists()
        return self.get_evidence_count() >= required


class LocalControlEvidence(models.Model):
    """
    Докази для локальних контролів
    """

    EVIDENCE_TYPE_CHOICES = Evidence.EVIDENCE_TYPE_CHOICES
    APPROVAL_STATUS_CHOICES = Evidence.APPROVAL_STATUS_CHOICES

    control = models.ForeignKey(
        LocalComplianceControl,
        on_delete=models.CASCADE,
        related_name='evidences',
        verbose_name=_("Local Control")
    )
    title = models.CharField(_("Evidence Title"), max_length=500)
    description = models.TextField(_("Description"), blank=True)
    evidence_type = models.ForeignKey(
        'EvidenceType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_control_evidences',
        verbose_name=_("Evidence Type"),
        help_text=_("Type of evidence")
    )
    evidence_type_old = models.CharField(
        _("Evidence Type (Old)"),
        max_length=50,
        choices=EVIDENCE_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text=_("Legacy field - will be migrated to evidence_type")
    )
    file = models.FileField(
        _("Evidence File"),
        upload_to='compliance/local_control_evidence/%Y/%m/%d/',
        null=True,
        blank=True
    )
    file_size = models.IntegerField(_("File Size (bytes)"), null=True, blank=True)
    text_evidence = models.TextField(_("Text Evidence"), blank=True)
    external_link = models.URLField(_("External Link"), blank=True)
    mandatory_process = models.ForeignKey(
        'app_compliance.MandatoryProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_control_evidences',
        verbose_name=_("Mandatory Process"),
        help_text=_("Link to a record from Mandatory Processes Registry")
    )
    register_document = models.ForeignKey(
        'app_doc.RegisterDocs',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_control_evidences',
        verbose_name=_("Register Document"),
        help_text=_("Document from main document register used as evidence")
    )
    related_document = models.ForeignKey(
        'app_doc.RelatedDocs',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_control_evidences',
        verbose_name=_("Related Document"),
        help_text=_("Related document used as evidence")
    )
    approval_status = models.CharField(
        _("Approval Status"),
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_local_evidences',
        verbose_name=_("Uploaded By")
    )
    uploaded_date = models.DateTimeField(_("Uploaded Date"), auto_now_add=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_local_evidences',
        verbose_name=_("Reviewed By")
    )
    reviewed_date = models.DateTimeField(_("Reviewed Date"), null=True, blank=True)
    review_comments = models.TextField(_("Review Comments"), blank=True)
    expiration_date = models.DateField(_("Expiration Date"), null=True, blank=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("Local Control Evidence")
        verbose_name_plural = _("Local Control Evidences")
        ordering = ['-uploaded_date']

    def __str__(self):
        return f"{self.title} - {self.control.code}"

    def is_expired(self):
        if self.expiration_date:
            return self.expiration_date < timezone.now().date()
        return False

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    @property
    def document_status(self):
        """
        Resolve document status from linked registers/mandatory process:
        1) Register Document status_doc
        2) Related Document status_rel_doc
        3) Mandatory Process source_document.status_doc (if available)
        """
        # Avoid circular imports at module load
        from app_doc.models import DocStatus

        # 1) Direct register document
        if self.register_document and getattr(self.register_document, "status_doc", None):
            return self.register_document.status_doc

        # 2) Related document
        if self.related_document and getattr(self.related_document, "status_rel_doc", None):
            return self.related_document.status_rel_doc

        # 3) From mandatory process source_document
        if self.mandatory_process and getattr(self.mandatory_process, "source_document", None):
            source_doc = self.mandatory_process.source_document
            if source_doc and getattr(source_doc, "status_doc", None):
                return source_doc.status_doc

        return None

    @property
    def document_status_display(self):
        status = self.document_status
        if not status:
            return None
        # DocStatus.get_name_by_language already respects current language
        if hasattr(status, "get_name_by_language"):
            return status.get_name_by_language()
        # Fallback to string repr
        return str(status)


class LocalControlAssignment(models.Model):
    """
    Призначення користувачів до локальних контролів
    """

    CONTROL_ASSIGNMENT_CHOICES = ControlAssignment.ASSIGNMENT_TYPE_CHOICES

    control = models.ForeignKey(
        LocalComplianceControl,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name=_("Local Control")
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='local_control_assignments',
        verbose_name=_("User")
    )
    assignment_type = models.CharField(
        _("Assignment Type"),
        max_length=20,
        choices=CONTROL_ASSIGNMENT_CHOICES,
        default='collaborator'
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='local_assignments_made',
        verbose_name=_("Assigned By")
    )
    assigned_date = models.DateTimeField(_("Assigned Date"), auto_now_add=True)
    notes = models.TextField(_("Assignment Notes"), blank=True)
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Local Control Assignment")
        verbose_name_plural = _("Local Control Assignments")
        ordering = ['-assigned_date']
        unique_together = [['control', 'user', 'assignment_type']]

    def __str__(self):
        return f"{self.user} -> {self.control} ({self.assignment_type})"


class LocalControlNote(models.Model):
    """
    Примітки до локальних контролів
    """

    control = models.ForeignKey(
        LocalComplianceControl,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name=_("Local Control")
    )
    note = models.TextField(_("Note"))
    attachment = models.FileField(
        _("Attachment"),
        upload_to='compliance/local_control_notes/%Y/%m/',
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='local_control_notes',
        verbose_name=_("Created By")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Local Control Note")
        verbose_name_plural = _("Local Control Notes")
        ordering = ['-created_date']

    def __str__(self):
        return f"Note for {self.control.code}"

    @property
    def attachment_filename(self):
        if self.attachment:
            import os
            return os.path.basename(self.attachment.name)
        return None


class LocalControlNoteAttachment(models.Model):
    """
    Multiple file attachments for LocalControlNote
    """

    note = models.ForeignKey(
        LocalControlNote,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Note")
    )
    file = models.FileField(
        _("File"),
        upload_to='compliance/local_control_notes/%Y/%m/',
    )
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Local Control Note Attachment")
        verbose_name_plural = _("Local Control Note Attachments")
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Attachment for note {self.note_id}"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name)


class LocalControlMapping(models.Model):
    """
    Мапінги локальних контролів на інші локальні, internal або framework контролі
    """

    MAPPING_TYPE_CHOICES = [
        ('equivalent', _('Equivalent')),
        ('related', _('Related')),
        ('partial', _('Partial')),
    ]

    local_control = models.ForeignKey(
        LocalComplianceControl,
        on_delete=models.CASCADE,
        related_name='mappings',
        verbose_name=_("Local Control")
    )
    target_local_control = models.ForeignKey(
        LocalComplianceControl,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='incoming_mappings',
        verbose_name=_("Target Local Control")
    )
    target_internal_control = models.ForeignKey(
        'InternalComplianceControl',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='local_control_mappings',
        verbose_name=_("Target Internal Control")
    )
    target_framework_control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='local_control_mappings',
        verbose_name=_("Target Framework Control")
    )
    mapping_type = models.CharField(
        _("Mapping Type"),
        max_length=20,
        choices=MAPPING_TYPE_CHOICES,
        default='related'
    )
    notes = models.TextField(_("Mapping Notes"), blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Created By")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)

    class Meta:
        verbose_name = _("Local Control Mapping")
        verbose_name_plural = _("Local Control Mappings")
        unique_together = [
            ['local_control', 'target_local_control', 'target_internal_control', 'target_framework_control', 'mapping_type']
        ]

    def __str__(self):
        target = self.target_local_control or self.target_internal_control or self.target_framework_control
        return f"{self.local_control.code} → {target}"

    def clean(self):
        if not self.target_local_control and not self.target_internal_control and not self.target_framework_control:
            raise ValidationError(_('Select at least one target control for mapping'))
        if self.target_local_control and self.target_local_control_id == self.local_control_id:
            raise ValidationError(_('Cannot map control to itself'))

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ========================
# Internal Compliance Models
# ========================

class AccessInternalCompliance(models.Model):
    """
    Model for controlling access to Internal Compliance module
    Controls which groups can access internal compliance data and for which companies
    """
    group = models.ForeignKey(
        'auth.Group',
        on_delete=models.CASCADE,
        verbose_name=_("Group")
    )
    has_access = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Internal Compliance Dashboard")
    )
    # Sources permissions
    can_view_sources = models.BooleanField(
        default=False,
        verbose_name=_("Can view sources")
    )
    can_edit_sources = models.BooleanField(
        default=False,
        verbose_name=_("Can edit sources")
    )
    can_add_sources = models.BooleanField(
        default=False,
        verbose_name=_("Can add new sources")
    )
    can_delete_sources = models.BooleanField(
        default=False,
        verbose_name=_("Can delete sources")
    )
    # Requirements permissions
    can_view_requirements = models.BooleanField(
        default=False,
        verbose_name=_("Can view requirements")
    )
    can_edit_requirements = models.BooleanField(
        default=False,
        verbose_name=_("Can edit requirements")
    )
    can_add_requirements = models.BooleanField(
        default=False,
        verbose_name=_("Can add new requirements")
    )
    can_delete_requirements = models.BooleanField(
        default=False,
        verbose_name=_("Can delete requirements")
    )
    can_view_requirement_instances = models.BooleanField(
        default=False,
        verbose_name=_("Can view requirement instances"),
        help_text=_("View requirement instances (applied to companies)")
    )
    can_edit_requirement_instances = models.BooleanField(
        default=False,
        verbose_name=_("Can edit requirement instances"),
        help_text=_("Edit requirement instances (status, dates, etc.)")
    )
    # Controls permissions
    can_view_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can view internal controls")
    )
    can_edit_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can edit internal controls")
    )
    can_add_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can add new internal controls")
    )
    can_delete_controls = models.BooleanField(
        default=False,
        verbose_name=_("Can delete internal controls")
    )
    # Evidence permissions
    can_manage_evidence = models.BooleanField(
        default=False,
        verbose_name=_("Can manage evidence")
    )
    can_approve_evidence = models.BooleanField(
        default=False,
        verbose_name=_("Can approve evidence")
    )
    # Reports permissions
    can_view_reports = models.BooleanField(
        default=False,
        verbose_name=_("Can view internal compliance reports")
    )
    can_export = models.BooleanField(
        default=False,
        verbose_name=_("Can export internal compliance data"),
        help_text=_("Can export requirements, controls, and compliance data to Excel")
    )
    # Company access
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='access_internal_compliance',
        verbose_name=_("Companies"),
        help_text=_("Companies this group can access. Leave empty for all companies.")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    
    class Meta:
        verbose_name = _("Access to Internal Compliance")
        verbose_name_plural = _("Access to Internal Compliance")
        unique_together = ['group']
    
    def __str__(self):
        return f"{self.group.name} - Internal Access: {self.has_access}"


class InternalComplianceSource(models.Model):
    """
    Internal source of requirements (Department, Policy, Standard, etc.)
    """
    
    SOURCE_TYPE_CHOICES = [
        ('department', _('Department')),
        ('policy', _('Policy')),
        ('standard', _('Standard')),
        ('procedure', _('Procedure')),
        ('guideline', _('Guideline')),
        ('directive', _('Directive')),
        ('other', _('Other')),
    ]
    
    name = models.CharField(
        _("Source Name"),
        max_length=200,
        help_text=_("Name of internal source (e.g., IT Security Policy)")
    )
    name_local = models.CharField(
        _("Local Name"),
        max_length=200,
        blank=True,
        help_text=_("Name in local language")
    )
    acronym = models.CharField(
        _("Acronym"),
        max_length=20,
        blank=True,
        help_text=_("Short name (e.g., IT-SEC)")
    )
    
    source_type = models.CharField(
        _("Source Type"),
        max_length=50,
        choices=SOURCE_TYPE_CHOICES,
        default='policy'
    )
    
    description = models.TextField(
        _("Description"),
        blank=True
    )
    
    website = models.URLField(
        _("Website"),
        blank=True
    )
    
    contact_email = models.EmailField(
        _("Contact Email"),
        blank=True
    )
    
    contact_phone = models.CharField(
        _("Contact Phone"),
        max_length=50,
        blank=True
    )
    
    color = models.CharField(
        _("Color"),
        max_length=7,
        default='#28a745',
        help_text=_("Hex color code for display (e.g., #28a745)")
    )
    
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='internal_sources',
        verbose_name=_("Companies"),
        help_text=_("Companies this source applies to")
    )
    
    company_types = models.ManyToManyField(
        'CompanyType',
        blank=True,
        related_name='internal_sources',
        verbose_name=_("Company Types"),
        help_text=_("Types of companies this source applies to")
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_internal_sources',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("Internal Compliance Source")
        verbose_name_plural = _("Internal Compliance Sources")
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['source_type']),
        ]
    
    def __str__(self):
        if self.acronym:
            return f"{self.acronym} - {self.name}"
        return self.name


class InternalComplianceRequirement(models.Model):
    """
    Internal company requirement (Policy requirement, Standard requirement, etc.)
    Supports Template/Instance system for reuse
    """
    
    REQUIREMENT_TYPE_CHOICES = [
        ('policy', _('Policy')),
        ('standard', _('Standard')),
        ('procedure', _('Procedure')),
        ('guideline', _('Guideline')),
        ('directive', _('Directive')),
        ('rule', _('Rule')),
        ('other', _('Other')),
    ]
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('active', _('Active')),
        ('suspended', _('Suspended')),
        ('archived', _('Archived')),
    ]
    
    # Template/Instance System
    is_template = models.BooleanField(
        _("Is Template"),
        default=False,
        help_text=_("This is a master template that can be applied to companies")
    )
    template = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instances',
        verbose_name=_("Template"),
        help_text=_("The template this requirement is based on")
    )
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='internal_compliance_requirements',
        verbose_name=_("Company"),
        help_text=_("Company this requirement instance belongs to (empty for templates)")
    )
    
    source = models.ForeignKey(
        InternalComplianceSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requirements',
        verbose_name=_("Source")
    )
    
    code = models.CharField(
        _("Requirement Code"),
        max_length=100,
        help_text=_("Internal code/number (e.g., POL-001)")
    )
    
    name = models.CharField(
        _("Requirement Name"),
        max_length=500,
        help_text=_("Full name of requirement")
    )
    
    name_local = models.CharField(
        _("Local Name"),
        max_length=500,
        blank=True,
        help_text=_("Name in local language")
    )
    
    requirement_type = models.CharField(
        _("Type"),
        max_length=50,
        choices=REQUIREMENT_TYPE_CHOICES,
        default='policy'
    )
    
    description = models.TextField(
        _("Description"),
        blank=True
    )
    
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    # Applicability
    applicable_to = models.CharField(
        _("Applicable To"),
        max_length=200,
        blank=True,
        help_text=_("Which departments, teams, or processes this applies to")
    )
    
    # Important dates
    publication_date = models.DateField(
        _("Publication Date"),
        null=True,
        blank=True
    )
    
    effective_date = models.DateField(
        _("Effective Date"),
        null=True,
        blank=True,
        help_text=_("When requirement comes into force")
    )
    
    deadline_date = models.DateField(
        _("Compliance Deadline"),
        null=True,
        blank=True,
        help_text=_("Deadline for compliance")
    )
    
    review_date = models.DateField(
        _("Next Review Date"),
        null=True,
        blank=True
    )
    
    # References
    document = models.ForeignKey(
        'app_doc.RegisterDocs',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='internal_compliance_requirements',
        verbose_name=_("Document"),
        help_text=_("Document from Document Registry")
    )
    
    document_file = models.FileField(
        _("Document File"),
        upload_to='compliance/internal_requirements/%Y/%m/',
        null=True,
        blank=True
    )
    
    # Metadata
    is_mandatory = models.BooleanField(
        _("Is Mandatory"),
        default=True
    )
    
    priority = models.CharField(
        _("Priority"),
        max_length=20,
        choices=Control.PRIORITY_CHOICES,
        default='medium'
    )
    
    company_types = models.ManyToManyField(
        'app_conf.CompanyType',
        blank=True,
        related_name='internal_requirements',
        verbose_name=_("Company Types"),
        help_text=_("Company types this requirement applies to")
    )
    
    # Audit
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_internal_requirements',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("Internal Compliance Requirement")
        verbose_name_plural = _("Internal Compliance Requirements")
        ordering = ['source', '-effective_date', 'code']
        indexes = [
            models.Index(fields=['source', 'status']),
            models.Index(fields=['effective_date']),
            models.Index(fields=['deadline_date']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def is_overdue(self):
        """Check if compliance deadline is overdue"""
        if self.deadline_date:
            return self.deadline_date < timezone.now().date()
        return False
    
    def days_until_deadline(self):
        """Days until compliance deadline"""
        if self.deadline_date:
            delta = self.deadline_date - timezone.now().date()
            return delta.days
        return None
    
    def apply_to_company(self, company, created_by=None):
        """
        Apply this template to a company (create instance)
        """
        if not self.is_template:
            raise ValueError("Only templates can be applied to companies")
        
        # Create a copy of requirement for the company
        instance = InternalComplianceRequirement.objects.create(
            source=self.source,
            code=self.code,
            name=self.name,
            name_local=self.name_local,
            requirement_type=self.requirement_type,
            description=self.description,
            status=self.status,
            applicable_to=self.applicable_to,
            publication_date=self.publication_date,
            effective_date=self.effective_date,
            deadline_date=self.deadline_date,
            review_date=self.review_date,
            official_link=self.official_link,
            is_mandatory=self.is_mandatory,
            priority=self.priority,
            is_template=False,
            template=self,
            company=company,
            created_by=created_by
        )

        if self.company_types.exists():
            instance.company_types.set(self.company_types.all())

        # Copy categories and create map
        category_map = {}
        for category in self.categories.all():
            new_category = category.copy_to_requirement(instance)
            category_map[category.id] = new_category
        
        # Copy all controls from template
        for template_control in self.controls.filter(company__isnull=True):
            InternalComplianceControl.objects.create(
                requirement=instance,
                company=company,
                category=category_map.get(template_control.category_id),
                code=template_control.code,
                name=template_control.name,
                description=template_control.description,
                status='not_started',  # Reset status
                priority=template_control.priority,
                target_completion_date=template_control.target_completion_date,
                implementation_notes=template_control.implementation_notes,
                evidence_notes=template_control.evidence_notes,
                required_evidence_count=template_control.required_evidence_count,
                created_by=created_by
            )
        
        return instance
    
    def get_template_controls(self):
        """Get template controls (without company binding)"""
        if self.is_template:
            return self.controls.filter(company__isnull=True)
        return self.controls.none()
    
    def get_controls_count(self):
        """Number of controls"""
        if self.is_template:
            return self.controls.filter(company__isnull=True).count()
        return self.controls.count()
    
    def get_instances_count(self):
        """Number of instances for template"""
        if self.is_template:
            return self.instances.count()
        return 0
    
    def get_completion_percentage(self):
        """Calculate completion percentage of all controls in requirement"""
        if self.is_template:
            controls = self.controls.filter(company__isnull=True)
        else:
            controls = self.controls.all()
        
        total_controls = controls.count()
        
        if total_controls == 0:
            return 0
        
        completed_controls = controls.filter(status='completed').count()
        
        return round((completed_controls / total_controls) * 100, 2)
    
    def get_controls_by_status(self):
        """Statistics of controls by status"""
        if self.is_template:
            controls = self.controls.filter(company__isnull=True)
        else:
            controls = self.controls.all()
        
        return {
            'total': controls.count(),
            'not_started': controls.filter(status='not_started').count(),
            'in_progress': controls.filter(status='in_progress').count(),
            'ready_for_review': controls.filter(status='ready_for_review').count(),
            'completed': controls.filter(status='completed').count(),
            'failed': controls.filter(status='failed').count(),
            'not_applicable': controls.filter(status='not_applicable').count(),
        }


class InternalRequirementCategory(models.Model):
    """
    Category of controls for Internal Compliance Requirement
    """

    requirement = models.ForeignKey(
        InternalComplianceRequirement,
        on_delete=models.CASCADE,
        related_name='categories',
        verbose_name=_("Requirement")
    )
    code = models.CharField(
        _("Category Code"),
        max_length=100,
        help_text=_("Unique identifier within requirement (e.g., CAT-1)")
    )
    name = models.CharField(
        _("Category Name"),
        max_length=500
    )
    description = models.TextField(
        _("Description"),
        blank=True
    )
    order = models.IntegerField(
        _("Display Order"),
        default=0
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("Internal Requirement Category")
        verbose_name_plural = _("Internal Requirement Categories")
        ordering = ['requirement', 'order', 'code']
        unique_together = [['requirement', 'code']]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def copy_to_requirement(self, target_requirement):
        """
        Copy category to another requirement
        """
        return InternalRequirementCategory.objects.create(
            requirement=target_requirement,
            code=self.code,
            name=self.name,
            description=self.description,
            order=self.order
        )


class InternalRequirementNote(models.Model):
    """
    Notes for internal requirement templates
    """

    requirement = models.ForeignKey(
        InternalComplianceRequirement,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name=_("Requirement"),
        help_text=_("Requirement this note belongs to")
    )
    note = models.TextField(_("Note"))
    attachment = models.FileField(
        _("Attachment"),
        upload_to='compliance/internal_requirement_notes/%Y/%m/',
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='internal_requirement_notes',
        verbose_name=_("Created By")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Internal Requirement Note")
        verbose_name_plural = _("Internal Requirement Notes")
        ordering = ['-created_date']

    def __str__(self):
        return f"Note for requirement {self.requirement_id}"

    @property
    def attachment_filename(self):
        if self.attachment:
            import os
            return os.path.basename(self.attachment.name)
        return None


class InternalRequirementNoteAttachment(models.Model):
    """
    Multiple file attachments for InternalRequirementNote
    """

    note = models.ForeignKey(
        InternalRequirementNote,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Note")
    )
    file = models.FileField(
        _("File"),
        upload_to='compliance/internal_requirement_notes/%Y/%m/',
    )
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Internal Requirement Note Attachment")
        verbose_name_plural = _("Internal Requirement Note Attachments")
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Attachment for internal requirement note {self.note_id}"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name)


class InternalComplianceControl(models.Model):
    """
    Control for implementing internal compliance requirement
    """
    
    requirement = models.ForeignKey(
        InternalComplianceRequirement,
        on_delete=models.CASCADE,
        related_name='controls',
        verbose_name=_("Requirement")
    )
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='internal_compliance_controls',
        verbose_name=_("Company"),
        help_text=_("Company this control applies to (null for template controls)")
    )
    category = models.ForeignKey(
        InternalRequirementCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='controls',
        verbose_name=_("Category")
    )
    
    code = models.CharField(
        _("Control Code"),
        max_length=100,
        help_text=_("Internal control code")
    )
    
    name = models.CharField(
        _("Control Name"),
        max_length=500
    )
    
    description = models.TextField(
        _("Description"),
        blank=True
    )
    
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Control.STATUS_CHOICES,
        default='not_started'
    )
    status_changed_date = models.DateTimeField(
        _("Status Changed Date"),
        null=True,
        blank=True
    )
    
    priority = models.CharField(
        _("Priority"),
        max_length=20,
        choices=Control.PRIORITY_CHOICES,
        default='medium'
    )
    
    # Assignment
    responsible = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='internal_compliance_controls',
        verbose_name=_("Responsible")
    )
    
    # Dates
    target_completion_date = models.DateField(
        _("Target Completion Date"),
        null=True,
        blank=True
    )
    
    periodicity = models.PositiveIntegerField(
        _("Periodicity (days)"),
        null=True,
        blank=True,
        help_text=_("Periodicity in days")
    )
    
    actual_completion_date = models.DateField(
        _("Actual Completion Date"),
        null=True,
        blank=True
    )
    
    # Implementation details
    implementation_notes = models.TextField(
        _("Implementation Notes"),
        blank=True
    )
    
    # Evidence
    evidence_files = models.FileField(
        _("Evidence Files"),
        upload_to='compliance/internal_evidence/%Y/%m/',
        null=True,
        blank=True
    )
    
    evidence_notes = models.TextField(
        _("Evidence Notes"),
        blank=True
    )
    required_evidence_count = models.PositiveIntegerField(
        _("Required Evidence Count"),
        default=1,
        help_text=_("How many evidence items are required for this control")
    )
    
    # Verification
    is_verified = models.BooleanField(
        _("Is Verified"),
        default=False
    )
    
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_internal_controls',
        verbose_name=_("Verified By")
    )
    
    verified_date = models.DateTimeField(
        _("Verified Date"),
        null=True,
        blank=True
    )
    
    # Link to framework control (optional)
    related_framework_control = models.ForeignKey(
        Control,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='internal_compliance_mappings',
        verbose_name=_("Related Framework Control"),
        help_text=_("Link to related international framework control")
    )
    
    # Audit
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_internal_controls',
        verbose_name=_("Created By")
    )
    
    class Meta:
        verbose_name = _("Internal Compliance Control")
        verbose_name_plural = _("Internal Compliance Controls")
        ordering = ['requirement', 'company', 'code']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['responsible']),
            models.Index(fields=['target_completion_date']),
        ]
    
    def __str__(self):
        if self.company:
            return f"{self.code} - {self.name} ({self.company.name})"
        return f"{self.code} - {self.name} [Template]"
    
    def is_overdue(self):
        """Check if control is overdue"""
        if self.target_completion_date and self.status not in ['completed', 'not_applicable']:
            return self.target_completion_date < timezone.now().date()
        return False

    def get_evidence_count(self):
        """Number of attached evidence items"""
        return self.evidences.filter(is_active=True).count()

    def get_approved_evidence_count(self):
        """Number of approved evidence items"""
        return self.evidences.filter(is_active=True, approval_status='approved').count()

    def has_sufficient_evidence(self):
        """Check if sufficient evidence exists"""
        required = self.required_evidence_count or 0
        if required <= 0:
            return self.evidences.filter(is_active=True).exists()
        return self.get_evidence_count() >= required


class InternalControlEvidence(models.Model):
    """
    Evidence for internal controls
    """

    EVIDENCE_TYPE_CHOICES = Evidence.EVIDENCE_TYPE_CHOICES
    APPROVAL_STATUS_CHOICES = Evidence.APPROVAL_STATUS_CHOICES

    control = models.ForeignKey(
        InternalComplianceControl,
        on_delete=models.CASCADE,
        related_name='evidences',
        verbose_name=_("Internal Control")
    )
    title = models.CharField(_("Evidence Title"), max_length=500)
    description = models.TextField(_("Description"), blank=True)
    evidence_type = models.ForeignKey(
        'EvidenceType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='internal_control_evidences',
        verbose_name=_("Evidence Type"),
        help_text=_("Type of evidence")
    )
    evidence_type_old = models.CharField(
        _("Evidence Type (Old)"),
        max_length=50,
        choices=EVIDENCE_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text=_("Legacy field - will be migrated to evidence_type")
    )
    file = models.FileField(
        _("Evidence File"),
        upload_to='compliance/internal_control_evidence/%Y/%m/%d/',
        null=True,
        blank=True
    )
    file_size = models.IntegerField(_("File Size (bytes)"), null=True, blank=True)
    text_evidence = models.TextField(_("Text Evidence"), blank=True)
    external_link = models.URLField(_("External Link"), blank=True)
    mandatory_process = models.ForeignKey(
        'app_compliance.MandatoryProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='internal_control_evidences',
        verbose_name=_("Mandatory Process"),
        help_text=_("Link to a record from Mandatory Processes Registry")
    )
    
    # Link to Document Register
    register_document = models.ForeignKey(
        'app_doc.RegisterDocs',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='internal_control_evidences',
        verbose_name=_("Register Document"),
        help_text=_("Link to a document from Document Register")
    )
    
    # Link to Related Document
    related_document = models.ForeignKey(
        'app_doc.RelatedDocs',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='internal_control_evidences',
        verbose_name=_("Related Document"),
        help_text=_("Link to a related document")
    )
    
    approval_status = models.CharField(
        _("Approval Status"),
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending'
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_internal_evidences',
        verbose_name=_("Uploaded By")
    )
    uploaded_date = models.DateTimeField(_("Uploaded Date"), auto_now_add=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_internal_evidences',
        verbose_name=_("Reviewed By")
    )
    reviewed_date = models.DateTimeField(_("Reviewed Date"), null=True, blank=True)
    review_comments = models.TextField(_("Review Comments"), blank=True)
    expiration_date = models.DateField(_("Expiration Date"), null=True, blank=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)

    class Meta:
        verbose_name = _("Internal Control Evidence")
        verbose_name_plural = _("Internal Control Evidences")
        ordering = ['-uploaded_date']

    def __str__(self):
        return f"{self.title} - {self.control.code}"

    def is_expired(self):
        if self.expiration_date:
            return self.expiration_date < timezone.now().date()
        return False

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    @property
    def document_status(self):
        """Get document status from linked documents"""
        if self.register_document and self.register_document.status_doc:
            return self.register_document.status_doc
        if self.related_document and self.related_document.status_rel_doc:
            return self.related_document.status_rel_doc
        if self.mandatory_process and self.mandatory_process.source_document and self.mandatory_process.source_document.status_doc:
            return self.mandatory_process.source_document.status_doc
        return None
    
    @property
    def document_status_display(self):
        """Get localized document status"""
        status = self.document_status
        return str(status) if status else None


class InternalControlAssignment(models.Model):
    """
    Assignment of users to internal controls
    """

    CONTROL_ASSIGNMENT_CHOICES = ControlAssignment.ASSIGNMENT_TYPE_CHOICES

    control = models.ForeignKey(
        InternalComplianceControl,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name=_("Internal Control")
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='internal_control_assignments',
        verbose_name=_("User")
    )
    assignment_type = models.CharField(
        _("Assignment Type"),
        max_length=20,
        choices=CONTROL_ASSIGNMENT_CHOICES,
        default='collaborator'
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='internal_assignments_made',
        verbose_name=_("Assigned By")
    )
    assigned_date = models.DateTimeField(_("Assigned Date"), auto_now_add=True)
    notes = models.TextField(_("Assignment Notes"), blank=True)
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Internal Control Assignment")
        verbose_name_plural = _("Internal Control Assignments")
        ordering = ['-assigned_date']
        unique_together = [['control', 'user', 'assignment_type']]

    def __str__(self):
        return f"{self.user} -> {self.control} ({self.assignment_type})"


class InternalControlNote(models.Model):
    """
    Notes for internal controls
    """

    control = models.ForeignKey(
        InternalComplianceControl,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name=_("Internal Control")
    )
    note = models.TextField(_("Note"))
    attachment = models.FileField(
        _("Attachment"),
        upload_to='compliance/internal_control_notes/%Y/%m/',
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='internal_control_notes',
        verbose_name=_("Created By")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Internal Control Note")
        verbose_name_plural = _("Internal Control Notes")
        ordering = ['-created_date']

    def __str__(self):
        return f"Note for {self.control.code}"

    @property
    def attachment_filename(self):
        if self.attachment:
            import os
            return os.path.basename(self.attachment.name)
        return None


class InternalControlNoteAttachment(models.Model):
    """
    Multiple file attachments for InternalControlNote
    """

    note = models.ForeignKey(
        InternalControlNote,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Note")
    )
    file = models.FileField(
        _("File"),
        upload_to='compliance/internal_control_notes/%Y/%m/',
    )
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Internal Control Note Attachment")
        verbose_name_plural = _("Internal Control Note Attachments")
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Attachment for note {self.note_id}"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name)


class FrameworkInstanceNote(models.Model):
    """
    Notes for framework company instances (Framework Company Requirement Detail)
    """

    framework = models.ForeignKey(
        ComplianceFramework,
        on_delete=models.CASCADE,
        related_name='notes',
        verbose_name=_("Framework"),
        help_text=_("Framework instance this note belongs to")
    )
    note = models.TextField(_("Note"))
    attachment = models.FileField(
        _("Attachment"),
        upload_to='compliance/framework_notes/%Y/%m/',
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='framework_notes',
        verbose_name=_("Created By")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)
    updated_date = models.DateTimeField(_("Updated Date"), auto_now=True)
    is_active = models.BooleanField(_("Is Active"), default=True)

    class Meta:
        verbose_name = _("Framework Instance Note")
        verbose_name_plural = _("Framework Instance Notes")
        ordering = ['-created_date']

    def __str__(self):
        return f"Note for framework {self.framework_id}"

    @property
    def attachment_filename(self):
        if self.attachment:
            import os
            return os.path.basename(self.attachment.name)
        return None


class FrameworkInstanceNoteAttachment(models.Model):
    """
    Multiple file attachments for FrameworkInstanceNote
    """

    note = models.ForeignKey(
        FrameworkInstanceNote,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Note")
    )
    file = models.FileField(
        _("File"),
        upload_to='compliance/framework_notes/%Y/%m/',
    )
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Framework Instance Note Attachment")
        verbose_name_plural = _("Framework Instance Note Attachments")
        ordering = ['uploaded_at']

    def __str__(self):
        return f"Attachment for framework note {self.note_id}"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name)


class InternalControlMapping(models.Model):
    """
    Mappings of internal controls to other internal, local or framework controls
    """

    MAPPING_TYPE_CHOICES = [
        ('equivalent', _('Equivalent')),
        ('related', _('Related')),
        ('partial', _('Partial')),
    ]

    internal_control = models.ForeignKey(
        InternalComplianceControl,
        on_delete=models.CASCADE,
        related_name='mappings',
        verbose_name=_("Internal Control")
    )
    target_internal_control = models.ForeignKey(
        InternalComplianceControl,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='incoming_mappings',
        verbose_name=_("Target Internal Control")
    )
    target_local_control = models.ForeignKey(
        'LocalComplianceControl',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='internal_control_mappings',
        verbose_name=_("Target Local Control")
    )
    target_framework_control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='internal_control_mappings',
        verbose_name=_("Target Framework Control")
    )
    mapping_type = models.CharField(
        _("Mapping Type"),
        max_length=20,
        choices=MAPPING_TYPE_CHOICES,
        default='related'
    )
    notes = models.TextField(_("Mapping Notes"), blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Created By")
    )
    created_date = models.DateTimeField(_("Created Date"), auto_now_add=True)

    class Meta:
        verbose_name = _("Internal Control Mapping")
        verbose_name_plural = _("Internal Control Mappings")
        unique_together = [
            ['internal_control', 'target_internal_control', 'target_local_control', 'target_framework_control', 'mapping_type']
        ]

    def __str__(self):
        target = self.target_internal_control or self.target_local_control or self.target_framework_control
        return f"{self.internal_control.code} → {target}"

    def clean(self):
        if not self.target_internal_control and not self.target_local_control and not self.target_framework_control:
            raise ValidationError(_('Select at least one target control for mapping'))
        if self.target_internal_control and self.target_internal_control_id == self.internal_control_id:
            raise ValidationError(_('Cannot map control to itself'))

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ========================
# Access Control Mappings
# ========================

class AccessControlMapping(models.Model):
    """
    Управління доступом груп до компаній для Compliance Management
    """
    
    # Group access
    group = models.ForeignKey(
        'auth.Group',
        on_delete=models.CASCADE,
        verbose_name=_("Group")
    )
    
    # Company access
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='access_control_mappings',
        verbose_name=_("Companies"),
        help_text=_("Companies this group can access. Leave empty for all companies.")
    )
    
    # Access permission
    has_access = models.BooleanField(
        default=False,
        verbose_name=_("Has access to Control Mapping")
    )
    
    class Meta:
        verbose_name = _("Access Control Mapping")
        verbose_name_plural = _("Access Control Mappings")
        unique_together = [['group']]
    
    def __str__(self):
        companies_count = self.companies.count()
        access_status = _("Access") if self.has_access else _("No Access")
        if companies_count > 0:
            return f"{self.group.name} - {companies_count} companies ({access_status})"
        else:
            return f"{self.group.name} - All companies ({access_status})"


# ========================
# Framework Domain
# ========================

class FrameworkDomain(models.Model):
    """
    Домени фреймворків для категоризації контролів
    (наприклад, NETWORK_SECURITY, CRYPTOGRAPHIC_PROTECTIONS, ACCESS_CONTROL тощо)
    """
    
    code = models.CharField(
        _("Domain Code"),
        max_length=100,
        unique=True,
        help_text=_("Unique code for the domain (e.g., NETWORK_SECURITY)")
    )
    name = models.CharField(
        _("Domain Name"),
        max_length=200,
        help_text=_("Human-readable name for the domain")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Detailed description of the domain")
    )
    display_order = models.IntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Order in which domains should be displayed")
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text=_("Whether this domain is active and available for use")
    )
    created_date = models.DateTimeField(
        _("Created Date"),
        auto_now_add=True
    )
    updated_date = models.DateTimeField(
        _("Updated Date"),
        auto_now=True
    )
    
    class Meta:
        verbose_name = _("Framework Domain")
        verbose_name_plural = _("Framework Domains")
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


# ========================
# Mandatory Processes Models
# ========================

class ProcessFrequency(models.TextChoices):
    """Frequency choices for mandatory processes"""
    DAILY = 'daily', _('Daily')
    WEEKLY = 'weekly', _('Weekly')
    MONTHLY = 'monthly', _('Monthly')
    QUARTERLY = 'quarterly', _('Quarterly')
    SEMI_ANNUALLY = 'semi_annually', _('Semi-annually (6 months)')
    ANNUALLY = 'annually', _('Annually')
    AS_NEEDED = 'as_needed', _('As needed')


class ProcessStatus(models.TextChoices):
    """Status choices for processes"""
    UPCOMING = 'upcoming', _('Upcoming')
    OVERDUE = 'overdue', _('Overdue')
    COMPLETED = 'completed', _('Completed')
    IN_PROGRESS = 'in_progress', _('In Progress')


class MandatoryProcess(models.Model):
    """Model for mandatory processes and procedures"""
    
    process_name = models.CharField(max_length=255, verbose_name=_("Process Name"))
    description = models.TextField(verbose_name=_("Description"))
    company = models.ForeignKey(
        'app_conf.Company', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name=_("Company")
    )
    source_document = models.ForeignKey(
        'app_doc.RegisterDocs', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name=_("Source Document"),
        help_text=_("Document that defines this process")
    )
    source_document_section = models.TextField(
        blank=True,
        verbose_name=_("Source Document Section"),
        help_text=_("Specific section or paragraph from the source document")
    )
    attachment_file = models.FileField(
        upload_to='process_attachments/',
        null=True,
        blank=True,
        verbose_name=_("Attachment File"),
        help_text=_("Additional documentation or procedures file")
    )
    frequency = models.CharField(
        max_length=20, 
        choices=ProcessFrequency.choices, 
        verbose_name=_("Frequency")
    )
    responsible_person = models.ManyToManyField(
        User, 
        blank=True,
        verbose_name=_("Responsible Person"),
        related_name='responsible_processes'
    )
    additional_person = models.ManyToManyField(
        User, 
        blank=True,
        verbose_name=_("Additional Person"),
        related_name='additional_processes'
    )
    next_due_date = models.DateField(verbose_name=_("Next Due Date"), null=True, blank=True)
    last_completed_date = models.DateField(verbose_name=_("Last Completed Date"), null=True, blank=True)
    priority = models.CharField(
        max_length=10,
        choices=[
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
            ('critical', _('Critical'))
        ],
        default='medium',
        verbose_name=_("Priority")
    )
    reminder_days = models.PositiveIntegerField(
        default=7,
        verbose_name=_("Reminder Days"),
        help_text=_("Number of days before due date to send reminder email")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    groups = models.ManyToManyField(
        Group, 
        blank=True, 
        verbose_name=_("Access Groups"),
        help_text=_("Groups that can view and manage this process")
    )
    access_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='mandatory_process_access_records',
        verbose_name=_("Access Users"),
        help_text=_("Cabinet users that can view this process. If both groups and access users are empty, access is not regulated.")
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_processes',
        verbose_name=_("Created By")
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='updated_processes',
        verbose_name=_("Updated By")
    )
    
    class Meta:
        verbose_name = _("Mandatory Process")
        verbose_name_plural = _("Mandatory Processes")
        db_table = 'app_doc_mandatoryprocess'  # Temporary: keep old table name until migration
        ordering = ['next_due_date', 'priority', 'process_name']
        indexes = [
            models.Index(fields=['next_due_date']),
            models.Index(fields=['frequency']),
            models.Index(fields=['priority']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.process_name
    
    @property
    def status(self):
        """Get current status based on due date"""
        if not self.next_due_date:
            return ProcessStatus.UPCOMING
        
        today = timezone.now().date()
        if self.next_due_date < today:
            return ProcessStatus.OVERDUE
        elif self.last_completed_date and self.last_completed_date >= self.next_due_date:
            return ProcessStatus.COMPLETED
        else:
            return ProcessStatus.UPCOMING
    
    @property
    def days_until_due(self):
        """Calculate days until due date"""
        if not self.next_due_date:
            return None
        
        today = timezone.now().date()
        delta = self.next_due_date - today
        return delta.days
    
    def should_send_reminder(self):
        """Check if reminder should be sent today"""
        if not self.next_due_date or not self.is_active:
            return False
        
        today = timezone.now().date()
        days_until_due = self.days_until_due
        
        # Send reminder if we're exactly at the reminder_days threshold
        return days_until_due == self.reminder_days
    
    def has_access(self, user):
        """Check if user has access to this process. If no groups and no access_users, access is not regulated (allow)."""
        if user.is_superuser:
            return True
        if self.responsible_person.filter(id=user.id).exists() or self.additional_person.filter(id=user.id).exists():
            return True
        
        # Check if user belongs to the same company
        if self.company and hasattr(user, 'cabinet'):
            if user.cabinet.company != self.company:
                return False
        
        # If neither groups nor access_users set, access is not regulated
        has_groups = self.groups.exists()
        has_access_users = self.access_users.exists()
        if not has_groups and not has_access_users:
            return True
        
        if self.access_users.filter(id=user.id).exists():
            return True
        return self.groups.filter(id__in=user.groups.all()).exists()
    
    def can_edit(self, user):
        """Check if user can edit this process"""
        # Import here to avoid circular imports
        from app_doc.views import check_user_mandatory_edit_access
        
        if user.is_superuser:
            return True
        
        # First check AccessMandatory permissions - this is the primary access control
        if not check_user_mandatory_edit_access(user):
            return False
        
        # If user has AccessMandatory edit rights, then check if they are involved in this specific process
        # Check if user is creator, responsible person, or additional person
        if (user == self.created_by or 
            self.responsible_person.filter(id=user.id).exists() or 
            self.additional_person.filter(id=user.id).exists()):
            return True
        
        # If user has AccessMandatory edit rights but is not involved in this specific process,
        # they can still edit it (this allows admins to edit any process)
        return True


class ProcessAttachment(models.Model):
    """Model for process file attachments"""
    
    process = models.ForeignKey(
        MandatoryProcess,
        on_delete=models.CASCADE,
        verbose_name=_("Process"),
        related_name='attachments'
    )
    file = models.FileField(
        upload_to='process_attachments/',
        verbose_name=_("File"),
        help_text=_("Attachment file")
    )
    filename = models.CharField(
        max_length=255,
        verbose_name=_("Original Filename"),
        help_text=_("Original name of the uploaded file")
    )
    description = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional description of the file")
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Uploaded At")
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Uploaded By")
    )
    file_size = models.PositiveIntegerField(
        default=0,
        verbose_name=_("File Size (bytes)")
    )
    
    class Meta:
        verbose_name = _("Process Attachment")
        verbose_name_plural = _("Process Attachments")
        db_table = 'app_doc_processattachment'  # Temporary: keep old table name until migration
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['process']),
            models.Index(fields=['uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.process.process_name} - {self.filename}"
    
    @property
    def file_size_formatted(self):
        """Return formatted file size"""
        size = self.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"


class ProcessExecution(models.Model):
    """Model for tracking process execution history"""
    
    process = models.ForeignKey(
        MandatoryProcess, 
        on_delete=models.CASCADE,
        verbose_name=_("Process"),
        related_name='executions'
    )
    execution_date = models.DateTimeField(default=timezone.now, verbose_name=_("Execution Date"))
    executed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name=_("Executed By")
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('completed', _('Completed')),
            ('partial', _('Partially Completed')),
            ('failed', _('Failed')),
            ('in_progress', _('In Progress'))
        ],
        default='completed',
        verbose_name=_("Status")
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    evidence_file = models.FileField(
        upload_to='process_evidence/',
        null=True,
        blank=True,
        verbose_name=_("Evidence File"),
        help_text=_("Upload evidence of process completion")
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    
    class Meta:
        verbose_name = _("Process Execution")
        verbose_name_plural = _("Process Executions")
        db_table = 'app_doc_processexecution'  # Temporary: keep old table name until migration
        ordering = ['-execution_date']
        indexes = [
            models.Index(fields=['process']),
            models.Index(fields=['execution_date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.process.process_name} - {self.execution_date.strftime('%Y-%m-%d')}"


class ProcessEvidenceFile(models.Model):
    """
    Модель для зберігання множинних файлів доказів виконання процесу
    Підтримує завантаження декількох файлів включаючи архіви
    """
    
    execution = models.ForeignKey(
        ProcessExecution,
        on_delete=models.CASCADE,
        related_name='evidence_files',
        verbose_name=_("Process Execution")
    )
    
    file = models.FileField(
        upload_to='process_evidence/%Y/%m/%d/',
        verbose_name=_("Evidence File"),
        help_text=_("Upload evidence file (PDF, images, archives, etc.)")
    )
    
    file_name = models.CharField(
        max_length=255,
        verbose_name=_("File Name"),
        help_text=_("Original file name")
    )
    
    file_size = models.BigIntegerField(
        verbose_name=_("File Size (bytes)"),
        null=True,
        blank=True
    )
    
    file_type = models.CharField(
        max_length=50,
        verbose_name=_("File Type"),
        blank=True,
        help_text=_("File extension/MIME type")
    )
    
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_process_evidence_files',
        verbose_name=_("Uploaded By")
    )
    
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Uploaded At")
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional description for this file")
    )
    
    class Meta:
        verbose_name = _("Process Evidence File")
        verbose_name_plural = _("Process Evidence Files")
        db_table = 'app_doc_processevidencefile'  # Temporary: keep old table name until migration
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['execution']),
            models.Index(fields=['uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.file_name} ({self.execution})"
    
    def save(self, *args, **kwargs):
        # Автоматично заповнюємо file_name та file_size
        if self.file and not self.file_name:
            self.file_name = self.file.name.split('/')[-1]
        
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except:
                pass
        
        # Визначаємо тип файлу
        if self.file_name and not self.file_type:
            import os
            ext = os.path.splitext(self.file_name)[1].lower()
            self.file_type = ext[1:] if ext else 'unknown'
        
        super().save(*args, **kwargs)
    
    def get_file_size_display(self):
        """Повертає розмір файлу в читабельному форматі"""
        if not self.file_size:
            return "Unknown"
        
        size = float(self.file_size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    def is_archive(self):
        """Перевіряє чи файл є архівом"""
        archive_extensions = ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz']
        return self.file_type.lower() in archive_extensions


class MandatoryProcessesGuide(models.Model):
    """Base Guide for Mandatory Processes. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Mandatory Processes Guide")
        verbose_name_plural = _("Mandatory Processes Guides")
        db_table = 'app_doc_mandatoryprocessesguide'  # Temporary: keep old table name until migration

    def __str__(self):
        return gettext("Mandatory Processes Guide")


class MandatoryProcessesGuideTranslation(models.Model):
    """Per-country (language) translations of the Mandatory Processes Guide."""
    guide = models.ForeignKey(
        MandatoryProcessesGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="mandatory_processes_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Mandatory Processes Guide Translation")
        verbose_name_plural = _("Mandatory Processes Guide Translations")
        db_table = 'app_doc_mandatoryprocessesguidetranslation'  # Temporary: keep old table name until migration
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class InternalComplianceGuide(models.Model):
    """Base Guide for Internal Compliance Dashboard. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Internal Compliance Guide")
        verbose_name_plural = _("Internal Compliance Guides")

    def __str__(self):
        return gettext("Internal Compliance Guide")


class InternalComplianceGuideTranslation(models.Model):
    """Per-country (language) translations of the Internal Compliance Guide."""
    guide = models.ForeignKey(
        InternalComplianceGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="internal_compliance_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Internal Compliance Guide Translation")
        verbose_name_plural = _("Internal Compliance Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class LocalComplianceGuide(models.Model):
    """Base Guide for Local Compliance Dashboard. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Local Compliance Guide")
        verbose_name_plural = _("Local Compliance Guides")

    def __str__(self):
        return gettext("Local Compliance Guide")


class LocalComplianceGuideTranslation(models.Model):
    """Per-country (language) translations of the Local Compliance Guide."""
    guide = models.ForeignKey(
        LocalComplianceGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="local_compliance_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Local Compliance Guide Translation")
        verbose_name_plural = _("Local Compliance Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"


class FrameworkComplianceGuide(models.Model):
    """Base Guide for Framework Compliance Dashboard. Source content for translations."""
    base_content = HTMLField(
        _("Base content"),
        blank=True,
        help_text=_("Default guide content (rich text). Use as source for AI translations.")
    )

    class Meta:
        verbose_name = _("Framework Compliance Guide")
        verbose_name_plural = _("Framework Compliance Guides")

    def __str__(self):
        return gettext("Framework Compliance Guide")


class FrameworkComplianceGuideTranslation(models.Model):
    """Per-country (language) translations of the Framework Compliance Guide."""
    guide = models.ForeignKey(
        FrameworkComplianceGuide,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Guide")
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="framework_compliance_guide_translations",
        verbose_name=_("Country")
    )
    content = HTMLField(
        _("Content"),
        blank=True,
        help_text=_("Guide content in this country's language.")
    )

    class Meta:
        verbose_name = _("Framework Compliance Guide Translation")
        verbose_name_plural = _("Framework Compliance Guide Translations")
        unique_together = ["guide", "country"]
        ordering = ["country__name"]

    def __str__(self):
        return f"{self.guide} — {self.country.name}"