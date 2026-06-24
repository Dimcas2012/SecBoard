from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from app_cabinet.models import CabinetUser

from .forms import CIFObjectForm, CIFPassportForm, CIFProtectionPlanForm
from .models import CIFObject, CIFPassport, CIFProtectionMeasure, CIFProtectionPlan, CIFSector
from .pagination_utils import CIF_TABLE_PAGE_SIZE_OPTIONS, get_cif_table_page_size
from .utils import (
    cif_access_required,
    cif_permission_required,
    filter_cif_objects_for_user,
    get_user_cif_permissions,
    user_can_access_cif_company,
)


ORDER_877_TASKS = {
    "ID": [
        "Провести інвентаризацію активів",
        "Призначити керівну посадову особу, відповідальну за кібербезпеку на всьому ОКІ",
        "Забезпечити належну взаємодію підрозділів ІТ та кіберзахисту",
        "Опрацювати вплив відомих вразливостей",
        "Залучити сторонню організацію для проведення незалежного аудиту інформаційної безпеки",
        "Забезпечити реагування на інформування постачальниками про визначені ними інциденти",
        "Забезпечити реагування на інформування постачальниками про виявлені ними вразливості",
        "Затвердити вимоги щодо кібербезпеки до постачальників ІКТ або послуг",
    ],
    "PR": [
        "Провести зміну паролів, встановлених за замовчуванням",
        "Забезпечити використання надійних паролів",
        "Забезпечити унікальність облікових даних",
        "Затвердити процедуру вчасного видалення облікових даних звільнених працівників",
        "Унеможливити отримання прав доступу до привілейованих облікових даних",
        "Провести сегментацію мережі",
        "Забезпечити виявлення невдалих спроб входу в систему",
        "Впровадити стійку до фішингу багатофакторну автентифікацію",
        "Запровадити базове навчання з кібербезпеки для всіх співробітників",
        "Запровадити додаткове навчання з кібербезпеки для персоналу підрозділу кіберзахисту",
        "Забезпечити шифрування при обміні інформацією",
        "Забезпечити захист інформації з обмеженим доступом",
        "Забезпечити захищеність електронної пошти від спуфінгу, фішингу та перехоплення",
        "Вимкнути встановлені за замовчуванням макроси та інший програмний код",
        "Забезпечити документування конфігураційних файлів ІКТ",
        "Забезпечити документування схеми розміщення та з’єднання обладнання мереж",
        "Затвердити процедури інсталяції ІКТ",
        "Забезпечити регулярне створення резервних копій конфігураційних файлів",
        "Затвердити, регулярно тестувати та вносити зміни до планів реагування",
        "Забезпечити збір журналів подій",
        "Забезпечити безпечне зберігання журналів подій",
        "Забезпечити заборону підключення неавторизованих пристроїв",
        "Забезпечити виявлення та обмеження використання Інтернет-послуг",
        "Забезпечити обмеження підключення ОКІІ до мережі Інтернет",
    ],
    "DE": [
        "Визначити порядок проведення моніторингу загроз та застосування відповідних тактик, технік і процедур",
    ],
    "RS": [
        "Забезпечити інформування про кіберінциденти",
        "Забезпечити використання результатів досліджень щодо вразливостей",
        "Забезпечити розміщення файлів security.txt та опрацювання отриманої завдяки їм інформації",
    ],
    "RC": [
        "Затвердити плани відновлення після інцидентів",
    ],
}


def _ensure_order_877_plan_structure(plan):
    if not plan.structure:
        plan.structure = (
            "1. Загальні відомості про ОКІІ\n"
            "2. Опис об'єкта критичної інформаційної інфраструктури\n"
            "3. Проєктні загрози\n"
            "4. Загальний порядок реагування на кіберінциденти/кібератаки\n"
            "5. План кіберзахисту ОКІІ\n"
            "6. Відомості про моніторинг рівня безпеки та внесення змін\n"
        )
        plan.save(update_fields=["structure", "updated_at"])


def _ensure_order_877_measures(plan):
    if plan.measures.exists():
        return
    for class_code, tasks in ORDER_877_TASKS.items():
        for index, task in enumerate(tasks, start=1):
            CIFProtectionMeasure.objects.create(
                protection_plan=plan,
                class_code=class_code,
                measure_number=str(index),
                name=task,
                implementation_status="not_started",
            )


def _save_measures_from_request(request, plan):
    for measure in plan.measures.all():
        status_key = f"measure_{measure.id}_status"
        deadline_key = f"measure_{measure.id}_deadline"
        notes_key = f"measure_{measure.id}_notes"
        current_state_key = f"measure_{measure.id}_current_state"
        planned_actions_key = f"measure_{measure.id}_planned_actions"
        additional_resources_key = f"measure_{measure.id}_additional_resources"
        responsible_cabinet_user_key = f"measure_{measure.id}_responsible_cabinet_user"
        if status_key in request.POST:
            measure.implementation_status = request.POST.get(status_key) or measure.implementation_status
        if deadline_key in request.POST:
            measure.deadline = request.POST.get(deadline_key) or None
        if notes_key in request.POST:
            measure.notes = (request.POST.get(notes_key) or "").strip()
        if current_state_key in request.POST:
            measure.current_state_and_resources = (request.POST.get(current_state_key) or "").strip()
        if planned_actions_key in request.POST:
            measure.planned_actions = (request.POST.get(planned_actions_key) or "").strip()
        if additional_resources_key in request.POST:
            measure.additional_resources = (request.POST.get(additional_resources_key) or "").strip()
        if responsible_cabinet_user_key in request.POST:
            cu_value = (request.POST.get(responsible_cabinet_user_key) or "").strip()
            measure.responsible_cabinet_user_id = int(cu_value) if cu_value.isdigit() else None
        measure.save()


def _cabinet_user_display(cabinet_user):
    if not cabinet_user:
        return "-"
    full_name = cabinet_user.user.get_full_name() or cabinet_user.user.username
    department = (
        cabinet_user.department.get_name()
        if cabinet_user.department and hasattr(cabinet_user.department, "get_name")
        else (str(cabinet_user.department) if cabinet_user.department else "-")
    )
    position = (
        cabinet_user.position.get_name()
        if cabinet_user.position and hasattr(cabinet_user.position, "get_name")
        else (str(cabinet_user.position) if cabinet_user.position else "-")
    )
    return f"{full_name} / {department} / {position}"


def _get_cif_object_or_404(request, pk):
    cif_object = get_object_or_404(CIFObject.objects.select_related("sector", "company"), pk=pk)
    if not user_can_access_cif_company(request.user, cif_object.company):
        raise Http404
    return cif_object


def _get_cif_object_list_context(request):
    queryset = filter_cif_objects_for_user(
        request.user,
        CIFObject.objects.select_related("sector", "company").all(),
    )
    search = (request.GET.get("search") or "").strip()
    category = (request.GET.get("category") or "").strip()
    sector_id = (request.GET.get("sector") or "").strip()
    status = (request.GET.get("status") or "").strip()

    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(edrpou__icontains=search))
    if category:
        queryset = queryset.filter(category=category)
    if sector_id:
        queryset = queryset.filter(sector_id=sector_id)
    if status:
        queryset = queryset.filter(status=status)

    per_page = get_cif_table_page_size(request)
    paginator = Paginator(queryset.order_by("name"), per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    return {
        "objects": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": paginator.count > 0,
        "current_page_size": per_page,
        "page_size_options": CIF_TABLE_PAGE_SIZE_OPTIONS,
        "pagination_item_label": _("objects"),
        "sectors": CIFSector.objects.order_by("name"),
        "category_choices": CIFObject.CATEGORY_CHOICES,
        "status_choices": CIFObject.STATUS_CHOICES,
        "active_filters": {
            "search": search,
            "category": category,
            "sector": sector_id,
            "status": status,
            "per_page": per_page,
        },
    }


def _get_cif_dashboard_stats(request):
    accessible_objects = filter_cif_objects_for_user(request.user, CIFObject.objects.all())
    accessible_plans = CIFProtectionPlan.objects.filter(cif_object__in=accessible_objects)
    accessible_measures = CIFProtectionMeasure.objects.filter(protection_plan__in=accessible_plans)
    accessible_passports = CIFPassport.objects.filter(cif_object__in=accessible_objects)

    return {
        "total_objects": accessible_objects.count(),
        "approved_passports": accessible_objects.filter(is_passport_approved=True).count(),
        "active_plans": accessible_plans.filter(status="active").count(),
        "completed_measures": accessible_measures.filter(implementation_status="completed").count(),
        "upcoming_deadlines": accessible_measures.filter(
            implementation_status__in=["not_started", "in_progress"],
            deadline__isnull=False,
        ).order_by("deadline")[:10],
        "overdue_measures": accessible_measures.filter(
            implementation_status__in=["not_started", "in_progress"],
            deadline__lt=timezone.now().date(),
        ).count(),
        "review_alerts": accessible_passports.filter(
            next_review_date__lte=timezone.now().date() + timezone.timedelta(days=30),
        ).count(),
        "plan_stats": accessible_plans.aggregate(
            avg_id=Count("id", filter=Q(id_percent__gt=0)),
            avg_pr=Count("id", filter=Q(pr_percent__gt=0)),
            avg_de=Count("id", filter=Q(de_percent__gt=0)),
            avg_rs=Count("id", filter=Q(rs_percent__gt=0)),
            avg_rc=Count("id", filter=Q(rc_percent__gt=0)),
        ),
    }


@cif_access_required
def cif_object_list(request):
    dashboard_url = reverse("app_cif:dashboard")
    if request.GET:
        return redirect(f"{dashboard_url}?{request.GET.urlencode()}")
    return redirect(dashboard_url)


@cif_permission_required('can_add_objects')
def cif_object_create(request):
    if request.method == "POST":
        form = CIFObjectForm(request.POST)
        if form.is_valid():
            cif_object = form.save(commit=False)
            if not user_can_access_cif_company(request.user, cif_object.company):
                messages.error(request, _("You do not have access to this company."))
                return redirect("app_cif:dashboard")
            cif_object.save()
            messages.success(request, _("CIF object created."))
            return redirect("app_cif:dashboard")
    else:
        form = CIFObjectForm()
    return render(
        request,
        "app_cif/cif_object_form.html",
        {"form": form, "cif_permissions": get_user_cif_permissions(request.user)},
    )


@cif_permission_required('can_view_objects')
def cif_object_detail(request, pk):
    cif_object = _get_cif_object_or_404(request, pk)
    passport, _passport_created = CIFPassport.objects.get_or_create(cif_object=cif_object)
    plan, _plan_created = CIFProtectionPlan.objects.get_or_create(cif_object=cif_object)
    incidents = cif_object.incidents.all() if hasattr(cif_object, "incidents") else []

    context = {
        "cif_object": cif_object,
        "passport": passport,
        "plan": plan,
        "functions": cif_object.critical_functions.select_related("owner").prefetch_related("related_assets"),
        "measures": plan.measures.select_related("responsible").all(),
        "incidents": incidents,
        "cif_permissions": get_user_cif_permissions(request.user),
    }
    return render(request, "app_cif/cif_object_detail.html", context)


@cif_permission_required('can_edit_passports')
def cif_passport_edit(request, pk):
    cif_object = _get_cif_object_or_404(request, pk)
    passport, _passport_created = CIFPassport.objects.get_or_create(cif_object=cif_object)
    if request.method == "POST":
        form = CIFPassportForm(request.POST, instance=passport)
        if form.is_valid():
            passport = form.save(commit=False)
            if not passport.created_by_id:
                passport.created_by = request.user
            passport.save()
            messages.success(request, _("Passport updated."))
            return redirect("app_cif:cif_object_detail", pk=pk)
    else:
        form = CIFPassportForm(instance=passport)
    return render(request, "app_cif/cif_passport_form.html", {"form": form, "cif_object": cif_object})


@cif_permission_required('can_approve_passports')
def cif_passport_approve(request, pk):
    cif_object = _get_cif_object_or_404(request, pk)
    passport, _passport_created = CIFPassport.objects.get_or_create(cif_object=cif_object)
    passport.status = "approved"
    passport.approval_date = timezone.now().date()
    passport.approved_by = request.user
    passport.save(update_fields=["status", "approval_date", "approved_by", "updated_at"])
    messages.success(request, _("Passport approved."))
    return redirect("app_cif:cif_object_detail", pk=pk)


@cif_permission_required('can_edit_plans')
def cif_protection_plan_edit(request, pk):
    cif_object = _get_cif_object_or_404(request, pk)
    plan, _plan_created = CIFProtectionPlan.objects.get_or_create(cif_object=cif_object)
    _ensure_order_877_plan_structure(plan)
    _ensure_order_877_measures(plan)
    if request.method == "POST":
        form = CIFProtectionPlanForm(request.POST, request.FILES, instance=plan)
        if form.is_valid():
            form.save()
            _save_measures_from_request(request, plan)
            messages.success(request, _("Protection plan updated."))
            return redirect("app_cif:cif_object_detail", pk=pk)
    else:
        form = CIFProtectionPlanForm(instance=plan)
    grouped_measures = {
        "ID": plan.measures.filter(class_code="ID").order_by("measure_number"),
        "PR": plan.measures.filter(class_code="PR").order_by("measure_number"),
        "DE": plan.measures.filter(class_code="DE").order_by("measure_number"),
        "RS": plan.measures.filter(class_code="RS").order_by("measure_number"),
        "RC": plan.measures.filter(class_code="RC").order_by("measure_number"),
    }
    cabinet_users = (
        CabinetUser.objects.select_related("user", "department", "position")
        .filter(company=cif_object.company)
        .order_by("user__last_name", "user__first_name", "user__username")
    )
    cabinet_user_choices = [(cu.id, _cabinet_user_display(cu)) for cu in cabinet_users]
    return render(
        request,
        "app_cif/cif_protection_plan_form.html",
        {
            "form": form,
            "cif_object": cif_object,
            "plan": plan,
            "grouped_measures": grouped_measures,
            "cabinet_user_choices": cabinet_user_choices,
        },
    )


@cif_permission_required('can_export')
def cif_generate_report(request, pk):
    cif_object = _get_cif_object_or_404(request, pk)
    content = (
        f"CIF report\n"
        f"Object: {cif_object.name}\n"
        f"EDRPOU: {cif_object.edrpou}\n"
        f"Category: {cif_object.category}\n"
        f"Passport status: {getattr(cif_object.passport, 'status', 'n/a')}\n"
    )
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="cif-report-{cif_object.pk}.txt"'
    return response


@cif_access_required
def cif_dashboard(request):
    cif_permissions = get_user_cif_permissions(request.user)
    if not cif_permissions["has_access"] and not cif_permissions["can_view_objects"]:
        messages.error(request, _("You do not have permission for this action"))
        return redirect("index")

    context = {"cif_permissions": cif_permissions}
    if cif_permissions["has_access"]:
        context.update(_get_cif_dashboard_stats(request))
    if cif_permissions["can_view_objects"]:
        context.update(_get_cif_object_list_context(request))

    return render(request, "app_cif/dashboard.html", context)
