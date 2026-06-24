from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from app_asset.models import InformationAsset
from app_conf.models import Company


class CIFSector(models.Model):
    code = models.CharField(_("Sector code"), max_length=64, unique=True)
    name = models.CharField(_("Sector name"), max_length=255)
    name_local = models.CharField(_("Local name"), max_length=255, blank=True)
    description = models.TextField(_("Description"), blank=True)
    regulatory_body = models.CharField(_("Regulatory body"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("Critical infrastructure sector")
        verbose_name_plural = _("Critical infrastructure sectors")
        ordering = ["name"]

    def __str__(self):
        return self.name_local or self.name

    def get_local_name(self, country):
        try:
            translation = self.translations.get(country=country)
            return translation.name_local
        except CIFSectorTranslation.DoesNotExist:
            return self.name_local or self.name


class CIFSectorTranslation(models.Model):
    sector = models.ForeignKey(
        CIFSector,
        on_delete=models.CASCADE,
        related_name="translations",
        verbose_name=_("Sector"),
    )
    country = models.ForeignKey(
        "app_conf.Country",
        on_delete=models.CASCADE,
        related_name="cif_sector_translations",
        verbose_name=_("Country"),
    )
    name_local = models.CharField(_("Local name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        verbose_name = _("CIF sector translation")
        verbose_name_plural = _("CIF sector translations")
        ordering = ["country__name"]
        unique_together = ["sector", "country"]

    def __str__(self):
        return f"{self.sector.name} - {self.country.name}: {self.name_local}"


class CIFObject(models.Model):
    CATEGORY_CHOICES = (
        ("I", "I"),
        ("II", "II"),
        ("III", "III"),
        ("IV", "IV"),
    )
    STATUS_CHOICES = (
        ("draft", _("Draft")),
        ("active", _("Active")),
        ("archived", _("Archived")),
    )

    name = models.CharField(_("CIF object name"), max_length=255)
    edrpou = models.CharField(
        _("EDRPOU"),
        max_length=10,
        unique=True,
        validators=[RegexValidator(r"^\d{10}$", _("EDRPOU must contain exactly 10 digits."))],
    )
    category = models.CharField(_("Category"), max_length=3, choices=CATEGORY_CHOICES)
    sector = models.ForeignKey(
        CIFSector,
        on_delete=models.PROTECT,
        related_name="cif_objects",
        verbose_name=_("Sector"),
    )
    address = models.TextField(_("Address"), blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="cif_objects",
        verbose_name=_("Company"),
    )
    status = models.CharField(_("Status"), max_length=16, choices=STATUS_CHOICES, default="draft")
    responsible_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsible_cif_objects",
        verbose_name=_("Responsible person"),
    )
    critical_functions_count = models.PositiveIntegerField(_("Critical functions count"), default=0)
    is_passport_approved = models.BooleanField(_("Passport approved"), default=False)
    passport_approved_date = models.DateField(_("Passport approval date"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Critical infrastructure facility object")
        verbose_name_plural = _("Critical infrastructure facility objects")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.edrpou})"


class CIFPassport(models.Model):
    STATUS_CHOICES = (
        ("draft", _("Draft")),
        ("under_review", _("Under review")),
        ("approved", _("Approved")),
        ("rejected", _("Rejected")),
    )

    cif_object = models.OneToOneField(
        CIFObject,
        on_delete=models.CASCADE,
        related_name="passport",
        verbose_name=_("CIF object"),
    )
    version = models.CharField(_("Version"), max_length=20, default="1.0")
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default="draft")
    approval_date = models.DateField(_("Approval date"), null=True, blank=True)
    next_review_date = models.DateField(_("Next review date"), null=True, blank=True)
    general_info = models.TextField(_("General info"), blank=True, default="")
    critical_functions = models.TextField(_("Critical functions"), blank=True, default="")
    resources = models.TextField(_("Resources"), blank=True, default="")
    dependencies = models.TextField(_("Dependencies"), blank=True, default="")
    threats = models.TextField(_("Threats"), blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cif_passports",
        verbose_name=_("Created by"),
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_cif_passports",
        verbose_name=_("Approved by"),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("CIF passport")
        verbose_name_plural = _("CIF passports")

    def __str__(self):
        return f"{self.cif_object.name} passport v{self.version}"


class CIFCriticalFunction(models.Model):
    cif_object = models.ForeignKey(
        CIFObject,
        on_delete=models.CASCADE,
        related_name="critical_functions",
        verbose_name=_("CIF object"),
    )
    name = models.CharField(_("Function name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    priority = models.PositiveSmallIntegerField(
        _("Priority"),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    rto_hours = models.PositiveIntegerField(_("RTO (hours)"), default=0)
    rpo_hours = models.PositiveIntegerField(_("RPO (hours)"), default=0)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_cif_functions",
        verbose_name=_("Owner"),
    )
    related_assets = models.ManyToManyField(
        InformationAsset,
        blank=True,
        related_name="cif_critical_functions",
        verbose_name=_("Related assets"),
    )
    is_critical = models.BooleanField(_("Is critical"), default=True)

    class Meta:
        verbose_name = _("CIF critical function")
        verbose_name_plural = _("CIF critical functions")
        ordering = ["cif_object", "priority", "name"]

    def __str__(self):
        return f"{self.cif_object.name}: {self.name}"


class CIFProtectionPlanTemplate(models.Model):
    CATEGORY_CHOICES = CIFObject.CATEGORY_CHOICES

    category = models.CharField(_("Category"), max_length=3, choices=CATEGORY_CHOICES, unique=True)
    name = models.CharField(_("Template name"), max_length=255, default="Default")
    structure = models.TextField(_("Template structure"), blank=True, default="")
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("CIF protection plan template")
        verbose_name_plural = _("CIF protection plan templates")
        ordering = ["category"]

    def __str__(self):
        return f"{self.category} - {self.name}"


class CIFProtectionPlan(models.Model):
    STATUS_CHOICES = (
        ("draft", _("Draft")),
        ("active", _("Active")),
        ("archived", _("Archived")),
    )

    cif_object = models.OneToOneField(
        CIFObject,
        on_delete=models.CASCADE,
        related_name="protection_plan",
        verbose_name=_("CIF object"),
    )
    version = models.CharField(_("Version"), max_length=20, default="1.0")
    status = models.CharField(_("Status"), max_length=16, choices=STATUS_CHOICES, default="draft")
    approval_date = models.DateField(_("Approval date"), null=True, blank=True)
    next_review_date = models.DateField(_("Next review date"), null=True, blank=True)
    implementation_percent = models.DecimalField(_("Implementation %"), max_digits=5, decimal_places=2, default=Decimal("0.00"))
    id_percent = models.DecimalField(_("ID %"), max_digits=5, decimal_places=2, default=Decimal("0.00"))
    pr_percent = models.DecimalField(_("PR %"), max_digits=5, decimal_places=2, default=Decimal("0.00"))
    de_percent = models.DecimalField(_("DE %"), max_digits=5, decimal_places=2, default=Decimal("0.00"))
    rs_percent = models.DecimalField(_("RS %"), max_digits=5, decimal_places=2, default=Decimal("0.00"))
    rc_percent = models.DecimalField(_("RC %"), max_digits=5, decimal_places=2, default=Decimal("0.00"))
    structure = models.TextField(_("Structure"), blank=True, default="")
    responsible_person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsible_cif_plans",
        verbose_name=_("Responsible person"),
    )
    # Section 1. General information about CIIO
    okii_unique_identifier = models.CharField(_("OKII unique identifier"), max_length=255, blank=True, default="")
    okii_full_name = models.CharField(_("OKII full name"), max_length=512, blank=True, default="")
    okii_short_name = models.CharField(_("OKII short name"), max_length=255, blank=True, default="")

    registry_info_submitted = models.BooleanField(_("Registry information submitted"), default=False)
    registry_submission_date = models.DateField(_("Registry submission date"), null=True, blank=True)
    registry_inclusion_date = models.DateField(_("Registry inclusion date"), null=True, blank=True)
    registry_planned_submission_date = models.DateField(_("Planned registry submission date"), null=True, blank=True)
    registry_responsible_person = models.CharField(_("Registry responsible person"), max_length=255, blank=True, default="")

    cmu518_requirements_status = models.TextField(_("CMU #518 requirements status"), blank=True, default="")
    cmu518_responsible_person = models.CharField(_("CMU #518 responsible person"), max_length=255, blank=True, default="")
    cmu518_completion_percent = models.DecimalField(_("CMU #518 completion percent"), max_digits=5, decimal_places=2, default=Decimal("0.00"))
    cmu518_status_date = models.DateField(_("CMU #518 status date"), null=True, blank=True)
    cmu518_target_100_date = models.DateField(_("CMU #518 target 100 percent date"), null=True, blank=True)

    security_person_full_name = models.CharField(_("Security responsible full name"), max_length=255, blank=True, default="")
    security_person_position = models.CharField(_("Security responsible position"), max_length=255, blank=True, default="")
    security_person_department = models.CharField(_("Security responsible department"), max_length=255, blank=True, default="")
    security_contact_postal_address = models.TextField(_("Security contact postal address"), blank=True, default="")
    security_contact_phone = models.CharField(_("Security contact phone"), max_length=255, blank=True, default="")
    security_contact_email = models.EmailField(_("Security contact email"), blank=True, default="")

    # Section 2. CIIO description
    vital_service_description = models.TextField(_("Vital service description"), blank=True, default="")
    processed_information_types = models.TextField(_("Processed information types"), blank=True, default="")

    has_external_connections = models.BooleanField(_("Has internet or external ICS connections"), default=False)
    providers_full_names = models.TextField(_("Providers full names"), blank=True, default="")
    provider_has_protected_nodes = models.BooleanField(_("Provider has protected access nodes"), default=False)
    connection_ip_addresses = models.TextField(_("Connection IP addresses"), blank=True, default="")
    connection_phone = models.CharField(_("Connection phone"), max_length=255, blank=True, default="")
    connection_email = models.EmailField(_("Connection email"), blank=True, default="")
    other_connected_systems = models.TextField(_("Other connected systems"), blank=True, default="")

    interaction_description = models.TextField(_("Interaction description"), blank=True, default="")
    interaction_other_okii_name = models.CharField(_("Interaction other OKII full name"), max_length=512, blank=True, default="")
    interaction_other_okii_identifier = models.CharField(_("Interaction other OKII identifier"), max_length=255, blank=True, default="")
    interaction_phone = models.CharField(_("Interaction phone"), max_length=255, blank=True, default="")
    interaction_email = models.EmailField(_("Interaction email"), blank=True, default="")

    has_kszi_attestat_or_audit = models.BooleanField(_("Has KSZI attestat or independent audit"), default=False)
    kszi_attestat_details = models.TextField(_("KSZI attestat details"), blank=True, default="")
    kszi_certificate_or_audit_report = models.TextField(_("KSZI certificate or audit report"), blank=True, default="")
    kszi_other_info = models.TextField(_("KSZI other info"), blank=True, default="")

    has_misp_interaction = models.BooleanField(_("Has MISP interaction"), default=False)
    misp_cert_ua = models.BooleanField(_("MISP CERT-UA"), default=False)
    misp_ua = models.BooleanField(_("MISP-UA"), default=False)
    misp_nbu = models.BooleanField(_("MISP-NBU"), default=False)
    misp_ncscc = models.BooleanField(_("MISP NCSCC"), default=False)
    misp_other = models.TextField(_("MISP other"), blank=True, default="")

    has_cert_csirt_interaction = models.BooleanField(_("Has CERT/CSIRT interaction"), default=False)
    cert_csirt_team_name = models.CharField(_("CERT/CSIRT team name"), max_length=255, blank=True, default="")
    cert_csirt_ownership_type = models.CharField(_("CERT/CSIRT ownership type"), max_length=50, blank=True, default="")
    cert_csirt_affiliation_type = models.CharField(_("CERT/CSIRT affiliation type"), max_length=50, blank=True, default="")
    cert_csirt_contact_info = models.TextField(_("CERT/CSIRT contact info"), blank=True, default="")

    has_soc_interaction = models.BooleanField(_("Has SOC interaction"), default=False)
    soc_name = models.CharField(_("SOC name"), max_length=255, blank=True, default="")
    soc_affiliation_type = models.CharField(_("SOC affiliation type"), max_length=50, blank=True, default="")
    soc_contact_info = models.TextField(_("SOC contact info"), blank=True, default="")

    functional_scheme_file = models.FileField(
        _("Functional scheme file"),
        upload_to="app_cif/functional_schemes/",
        null=True,
        blank=True,
    )

    # Section 3. Project threats
    project_threats_description = models.TextField(
        _("Project threats description"),
        blank=True,
        default="",
    )

    # Section 4. General incident/cyberattack response order
    incident_response_general_order = models.TextField(
        _("General incident/cyberattack response order"),
        blank=True,
        default="",
    )

    # Section 6. Monitoring and plan change information
    monitoring_security_level_info = models.TextField(
        _("Monitoring security level information"),
        blank=True,
        default="",
    )
    monitoring_results_summary = models.TextField(
        _("Monitoring results summary"),
        blank=True,
        default="",
    )
    plan_change_info = models.TextField(
        _("Plan change information (Table 12)"),
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("CIF protection plan")
        verbose_name_plural = _("CIF protection plans")

    def __str__(self):
        return f"{self.cif_object.name} plan v{self.version}"

    def recalculate_progress(self, save=True):
        grouped = {
            "ID": {"total": 0, "done": 0},
            "PR": {"total": 0, "done": 0},
            "DE": {"total": 0, "done": 0},
            "RS": {"total": 0, "done": 0},
            "RC": {"total": 0, "done": 0},
        }
        for measure in self.measures.exclude(implementation_status="not_applicable"):
            grouped[measure.class_code]["total"] += 1
            if measure.implementation_status == "completed":
                grouped[measure.class_code]["done"] += 1

        values = {}
        total_all = done_all = 0
        for code, metric in grouped.items():
            total = metric["total"]
            done = metric["done"]
            percent = Decimal("0.00") if total == 0 else (Decimal(done) * Decimal("100.00") / Decimal(total)).quantize(Decimal("0.01"))
            values[f"{code.lower()}_percent"] = percent
            total_all += total
            done_all += done
        values["implementation_percent"] = (
            Decimal("0.00")
            if total_all == 0
            else (Decimal(done_all) * Decimal("100.00") / Decimal(total_all)).quantize(Decimal("0.01"))
        )

        for field_name, field_value in values.items():
            setattr(self, field_name, field_value)
        if save:
            self.save(update_fields=[*values.keys(), "updated_at"])
        return values

    def apply_template_for_category(self):
        template = CIFProtectionPlanTemplate.objects.filter(category=self.cif_object.category).first()
        if template and not self.structure:
            self.structure = template.structure
            self.save(update_fields=["structure", "updated_at"])


class CIFProtectionMeasure(models.Model):
    CLASS_CHOICES = (
        ("ID", "ID"),
        ("PR", "PR"),
        ("DE", "DE"),
        ("RS", "RS"),
        ("RC", "RC"),
    )
    STATUS_CHOICES = (
        ("not_started", _("Not started")),
        ("in_progress", _("In progress")),
        ("completed", _("Completed")),
        ("not_applicable", _("Not applicable")),
    )

    protection_plan = models.ForeignKey(
        CIFProtectionPlan,
        on_delete=models.CASCADE,
        related_name="measures",
        verbose_name=_("Protection plan"),
    )
    class_code = models.CharField(_("Class"), max_length=2, choices=CLASS_CHOICES)
    measure_number = models.CharField(_("Measure number"), max_length=32)
    name = models.CharField(_("Measure name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    current_state_and_resources = models.TextField(
        _("Current implementation state and available resources"),
        blank=True,
    )
    planned_actions = models.TextField(
        _("Planned actions for task implementation"),
        blank=True,
    )
    implementation_status = models.CharField(
        _("Implementation status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="not_started",
    )
    deadline = models.DateField(_("Deadline"), null=True, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cif_responsible_measures",
        verbose_name=_("Responsible"),
    )
    responsible_cabinet_user = models.ForeignKey(
        "app_cabinet.CabinetUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cif_responsible_measures",
        verbose_name=_("Responsible cabinet user"),
    )
    related_compliance_control = models.ForeignKey(
        "app_compliance.Control",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cif_measures",
        verbose_name=_("Related compliance control"),
    )
    evidence_files = models.ManyToManyField(
        "app_doc.RegisterDocs",
        blank=True,
        related_name="cif_measures",
        verbose_name=_("Evidence files"),
    )
    notes = models.TextField(_("Notes"), blank=True)
    additional_resources = models.TextField(
        _("Additional resources for task implementation"),
        blank=True,
    )

    class Meta:
        verbose_name = _("CIF protection measure")
        verbose_name_plural = _("CIF protection measures")
        ordering = ["protection_plan", "class_code", "measure_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["protection_plan", "class_code", "measure_number"],
                name="cif_measure_unique_number_per_plan",
            ),
        ]

    def __str__(self):
        return f"{self.class_code}-{self.measure_number}: {self.name}"

    @property
    def is_overdue(self):
        return bool(
            self.deadline
            and self.implementation_status not in {"completed", "not_applicable"}
            and self.deadline < timezone.now().date()
        )


class AccessCIF(models.Model):
    """
    Model for controlling access to CIF module.
    Controls which groups can access CIF data and for which companies.
    """
    group = models.ForeignKey(
        'auth.Group',
        on_delete=models.CASCADE,
        verbose_name=_("Group"),
    )
    has_access = models.BooleanField(
        default=False,
        verbose_name=_("Has access to CIF Dashboard"),
    )
    can_view_objects = models.BooleanField(
        default=False,
        verbose_name=_("Can view CIF objects"),
    )
    can_edit_objects = models.BooleanField(
        default=False,
        verbose_name=_("Can edit CIF objects"),
    )
    can_add_objects = models.BooleanField(
        default=False,
        verbose_name=_("Can add new CIF objects"),
    )
    can_delete_objects = models.BooleanField(
        default=False,
        verbose_name=_("Can delete CIF objects"),
    )
    can_view_passports = models.BooleanField(
        default=False,
        verbose_name=_("Can view passports"),
    )
    can_edit_passports = models.BooleanField(
        default=False,
        verbose_name=_("Can edit passports"),
    )
    can_approve_passports = models.BooleanField(
        default=False,
        verbose_name=_("Can approve passports"),
    )
    can_view_plans = models.BooleanField(
        default=False,
        verbose_name=_("Can view protection plans"),
    )
    can_edit_plans = models.BooleanField(
        default=False,
        verbose_name=_("Can edit protection plans"),
    )
    can_export = models.BooleanField(
        default=False,
        verbose_name=_("Can export CIF reports"),
    )
    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name='access_cif',
        verbose_name=_("Companies"),
        help_text=_("Companies this group can access. Leave empty for all companies."),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
    )

    class Meta:
        verbose_name = _("Access to CIF")
        verbose_name_plural = _("Access to CIF")
        unique_together = ['group']

    def __str__(self):
        return f"{self.group.name} - Access: {self.has_access}"


def _sync_cif_derived_fields(cif_object):
    function_count = cif_object.critical_functions.count()
    is_approved = bool(
        hasattr(cif_object, "passport")
        and cif_object.passport
        and cif_object.passport.status == "approved"
    )
    approved_date = cif_object.passport.approval_date if is_approved else None
    CIFObject.objects.filter(pk=cif_object.pk).update(
        critical_functions_count=function_count,
        is_passport_approved=is_approved,
        passport_approved_date=approved_date,
        updated_at=timezone.now(),
    )


def _recalculate_plan_for_measure(measure):
    if measure and measure.protection_plan_id:
        measure.protection_plan.recalculate_progress(save=True)


from django.db.models.signals import post_delete, post_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver(post_save, sender=CIFCriticalFunction)
@receiver(post_delete, sender=CIFCriticalFunction)
def cif_function_count_sync(sender, instance, **kwargs):
    _sync_cif_derived_fields(instance.cif_object)


@receiver(post_save, sender=CIFPassport)
@receiver(post_delete, sender=CIFPassport)
def cif_passport_sync(sender, instance, **kwargs):
    _sync_cif_derived_fields(instance.cif_object)


@receiver(post_save, sender=CIFProtectionPlan)
def cif_plan_apply_template(sender, instance, created, **kwargs):
    if created:
        instance.apply_template_for_category()


@receiver(post_save, sender=CIFProtectionMeasure)
@receiver(post_delete, sender=CIFProtectionMeasure)
def cif_measure_sync_progress(sender, instance, **kwargs):
    _recalculate_plan_for_measure(instance)
