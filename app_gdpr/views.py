#  SecBoard\SecBoard\app_gdpr\views.py

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.translation import gettext as _, get_language
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db import models
from .models import (
    DataSubject,
    ConsentRecord,
    DataProcessingActivity,
    DataBreachIncident,
    DataSubjectRequest,
    DataRetentionPolicy,
    DPIAAssessment,
    GdprGuideContent,
    GdprGuideContentTranslation,
)
from .forms import (
    DataSubjectForm,
    ConsentRecordForm,
    DataProcessingActivityForm,
    DataBreachIncidentForm,
    DataSubjectRequestForm,
    DSRProcessForm,
    DataRetentionPolicyForm,
    DPIAAssessmentForm
)
from .utils import (
    export_data_subject_data,
    anonymize_personal_data,
    generate_compliance_report_data
)
from .email_utils import (
    send_dsr_confirmation_email,
    send_dsr_completion_email
)
from .permissions import GDPRAccessMixin, gdpr_access_required, check_gdpr_access, get_user_accessible_companies_gdpr, has_company_access_gdpr
from .pagination_utils import GDPR_TABLE_PAGE_SIZE_OPTIONS, get_gdpr_table_page_size
from app_conf.models import Country
import logging

logger = logging.getLogger(__name__)


class GDPRListPaginationMixin:
    """Shared GET per_page pagination for GDPR ListView pages."""

    paginate_by = 25

    def get_paginate_by(self, queryset):
        return get_gdpr_table_page_size(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        per_page = get_gdpr_table_page_size(self.request)
        context['current_page_size'] = per_page
        context['page_size_options'] = GDPR_TABLE_PAGE_SIZE_OPTIONS
        paginator = context.get('paginator')
        if paginator is not None:
            context['is_paginated'] = paginator.count > 0
        return context


class ComplianceDashboardView(LoginRequiredMixin, GDPRAccessMixin, TemplateView):
    """Головний дашборд відповідності GDPR"""
    template_name = 'app_gdpr/gdpr_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get company filter from request
        selected_company_ids = self.request.GET.getlist('company')
        
        # Get accessible companies for user
        from app_conf.models import Company
        accessible_companies = get_user_accessible_companies_gdpr(self.request.user)
        
        if accessible_companies is None:
            # Superuser or staff - show all companies
            available_companies = Company.objects.all().order_by('name')
        elif accessible_companies:
            # Has specific accessible companies
            if isinstance(accessible_companies, list):
                # Convert list to QuerySet
                company_ids = [c.id if hasattr(c, 'id') else c for c in accessible_companies]
                available_companies = Company.objects.filter(id__in=company_ids).order_by('name')
            else:
                # Already a QuerySet
                available_companies = accessible_companies.order_by('name')
        else:
            # No access - empty QuerySet
            available_companies = Company.objects.none()
        
        # Filter by selected companies if any
        if selected_company_ids:
            # Convert to integers
            selected_ids = [int(cid) for cid in selected_company_ids]
            selected_companies = available_companies.filter(id__in=selected_ids)
            filter_companies = selected_companies
        else:
            selected_companies = None
            filter_companies = available_companies
        
        context['available_companies'] = available_companies
        context['selected_companies'] = selected_companies
        context['selected_company_ids'] = [int(cid) for cid in selected_company_ids] if selected_company_ids else []
        
        # Debug logging
        logger.debug(f"GDPR Dashboard - User: {self.request.user.username}")
        logger.debug(f"GDPR Dashboard - Available companies count: {available_companies.count()}")
        logger.debug(f"GDPR Dashboard - Selected company IDs: {selected_company_ids}")
        
        # Queryset filters based on selected companies
        if filter_companies and filter_companies.exists():
            data_subjects_qs = DataSubject.objects.filter(company__in=filter_companies)
            consents_qs = ConsentRecord.objects.filter(data_subject__company__in=filter_companies)
            dsr_qs = DataSubjectRequest.objects.filter(company__in=filter_companies)
            breaches_qs = DataBreachIncident.objects.filter(company__in=filter_companies)
            dpia_qs = DPIAAssessment.objects.filter(company__in=filter_companies)
            activities_qs = DataProcessingActivity.objects.filter(company__in=filter_companies)
            policies_qs = DataRetentionPolicy.objects.filter(company__in=filter_companies)
        else:
            # No companies accessible - return empty querysets
            data_subjects_qs = DataSubject.objects.none()
            consents_qs = ConsentRecord.objects.none()
            dsr_qs = DataSubjectRequest.objects.none()
            breaches_qs = DataBreachIncident.objects.none()
            dpia_qs = DPIAAssessment.objects.none()
            activities_qs = DataProcessingActivity.objects.none()
            policies_qs = DataRetentionPolicy.objects.none()
        
        # Основна статистика (перший ряд)
        context['data_subjects_count'] = data_subjects_qs.count()
        context['active_consents'] = consents_qs.filter(is_active=True).count()
        context['pending_dsr'] = dsr_qs.filter(status='pending').count()
        context['total_dsr'] = dsr_qs.count()
        context['open_breaches'] = breaches_qs.exclude(status='resolved').count()
        
        # Додаткова статистика (другий ряд)
        context['dpia_assessments'] = dpia_qs.count()
        context['data_activities'] = activities_qs.count()
        context['retention_policies'] = policies_qs.count()
        
        # Прострочені DSR
        overdue_dsr = [dsr for dsr in dsr_qs.filter(
            status__in=['pending', 'in_progress']
        ) if dsr.is_overdue()]
        context['overdue_dsr_count'] = len(overdue_dsr)
        
        # Критичні витоки
        context['critical_breaches'] = breaches_qs.filter(
            severity='critical',
            status__in=['detected', 'investigating']
        ).count()
        
        # Загальна кількість витоків
        context['total_breaches'] = breaches_qs.count()
        
        # Права для Quick Actions
        from .permissions import check_gdpr_access
        context['can_edit_data_subjects'] = check_gdpr_access(self.request.user, 'can_edit_data_subjects')
        context['can_manage_consents'] = check_gdpr_access(self.request.user, 'can_manage_consents')
        context['can_edit_activities'] = check_gdpr_access(self.request.user, 'can_edit_activities')
        context['can_edit_policies'] = check_gdpr_access(self.request.user, 'can_edit_policies')
        context['can_process_dsr'] = check_gdpr_access(self.request.user, 'can_process_dsr')
        context['can_edit_breaches'] = check_gdpr_access(self.request.user, 'can_edit_breaches')
        context['can_conduct_dpia'] = check_gdpr_access(self.request.user, 'can_conduct_dpia')
        context['can_generate_reports'] = check_gdpr_access(self.request.user, 'can_generate_reports')
        
        # Critical Alerts
        context['critical_alerts'] = []
        
        # Overdue DSRs
        if context['overdue_dsr_count'] > 0:
            context['critical_alerts'].append({
                'type': 'overdue_dsr',
                'title': _('Overdue DSR Requests'),
                'count': context['overdue_dsr_count'],
                'severity': 'danger',
                'url': 'app_gdpr:dsr_list'
            })
        
        # Critical Breaches
        if context['critical_breaches'] > 0:
            context['critical_alerts'].append({
                'type': 'critical_breach',
                'title': _('Critical Data Breaches'),
                'count': context['critical_breaches'],
                'severity': 'danger',
                'url': 'app_gdpr:breach_list'
            })
        
        # Expiring Consents (next 30 days)
        from datetime import datetime, timedelta
        today = timezone.now().date()
        expiring_consents = consents_qs.filter(
            is_active=True,
            expiration_date__lte=today + timedelta(days=30),
            expiration_date__gt=today
        ).count()
        if expiring_consents > 0:
            context['critical_alerts'].append({
                'type': 'expiring_consent',
                'title': _('Expiring Consents'),
                'count': expiring_consents,
                'severity': 'warning',
                'url': 'app_gdpr:consent_list'
            })
        
        # Upcoming Deadlines
        context['upcoming_deadlines'] = []
        
        # DSR deadlines (next 7 days)
        upcoming_dsr = dsr_qs.filter(
            status__in=['pending', 'in_progress'],
            due_date__lte=today + timedelta(days=7),
            due_date__gt=today
        ).order_by('due_date')[:5]
        
        for dsr in upcoming_dsr:
            days_left = (dsr.due_date - today).days
            context['upcoming_deadlines'].append({
                'type': 'dsr',
                'title': f"DSR #{dsr.id} - {dsr.request_type}",
                'deadline': dsr.due_date,
                'days_left': days_left,
                'severity': 'danger' if days_left <= 2 else 'warning',
                'url': f"app_gdpr:dsr_detail"
            })
        
        # Recent Activity (last 10 activities)
        context['recent_activities'] = []
        
        # Recent DSRs
        recent_dsrs = dsr_qs.order_by('-request_date')[:3]
        for dsr in recent_dsrs:
            context['recent_activities'].append({
                'type': 'dsr',
                'title': f"New DSR: {dsr.get_request_type_display()}",
                'description': f"Request #{dsr.request_number} from {dsr.data_subject.email}",
                'timestamp': dsr.request_date,
                'url': f"app_gdpr:dsr_detail"
            })
        
        # Recent Breaches
        recent_breaches = breaches_qs.order_by('-discovery_date')[:3]
        for breach in recent_breaches:
            context['recent_activities'].append({
                'type': 'breach',
                'title': f"Data Breach: {breach.title}",
                'description': f"Severity: {breach.get_severity_display()}",
                'timestamp': breach.discovery_date,
                'url': f"app_gdpr:breach_detail"
            })
        
        # Recent Consents
        recent_consents = consents_qs.order_by('-given_date')[:3]
        for consent in recent_consents:
            context['recent_activities'].append({
                'type': 'consent',
                'title': f"New Consent: {consent.get_consent_type_display()}",
                'description': f"Data Subject: {consent.data_subject.email}",
                'timestamp': consent.given_date,
                'url': f"app_gdpr:consent_detail"
            })
        
        # Sort by timestamp
        context['recent_activities'].sort(key=lambda x: x['timestamp'], reverse=True)
        context['recent_activities'] = context['recent_activities'][:10]
        
        # DSR Statistics for charts
        context['dsr_stats'] = {
            'in_progress': dsr_qs.filter(status='in_progress').count(),
            'completed': dsr_qs.filter(status='completed').count(),
            'rejected': dsr_qs.filter(status='rejected').count(),
        }
        
        # Breach Statistics for charts
        context['breach_stats'] = {
            'low': breaches_qs.filter(severity='low').count(),
            'medium': breaches_qs.filter(severity='medium').count(),
            'high': breaches_qs.filter(severity='high').count(),
            'critical': breaches_qs.filter(severity='critical').count(),
        }
        
        # Consent Statistics for charts
        context['consent_stats'] = {
            'withdrawn': consents_qs.filter(is_active=False).count(),
            'expired': data_subjects_qs.filter(consent_status='expired').count(),
            'pending': data_subjects_qs.filter(consent_status='pending').count(),
        }
        
        # Compliance Status Overview
        total_data_subjects = context['data_subjects_count']
        subjects_with_consent = consents_qs.filter(is_active=True).values('data_subject').distinct().count()
        consent_coverage = (subjects_with_consent / total_data_subjects * 100) if total_data_subjects > 0 else 0
        
        context['compliance_status'] = {
            'data_subject_coverage': {
                'percentage': min(100, (total_data_subjects / 100) * 100),  # Assume 100 is full coverage
                'current': total_data_subjects,
                'target': 100
            },
            'consent_management': {
                'percentage': consent_coverage,
                'current': subjects_with_consent,
                'target': total_data_subjects
            },
            'dsr_response_time': {
                'percentage': 85,  # Placeholder - would need actual calculation
                'current': 2.5,  # Average days
                'target': 3.0  # Target days
            },
            'breach_response': {
                'percentage': 90,  # Placeholder
                'current': 24,  # Average hours
                'target': 72  # Target hours
            }
        }
        
        return context


class GDPRGuideView(LoginRequiredMixin, GDPRAccessMixin, TemplateView):
    """Покрокова інструкція впровадження GDPR в компанії за допомогою модулів"""
    template_name = 'app_gdpr/gdpr_guide.html'
    required_gdpr_permission = 'has_access_compliance_dashboard'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        # для умовного показу прикладів створення
        context['can_edit_data_subjects'] = check_gdpr_access(self.request.user, 'can_edit_data_subjects')
        context['can_manage_consents'] = check_gdpr_access(self.request.user, 'can_manage_consents')
        context['can_process_dsr'] = check_gdpr_access(self.request.user, 'can_process_dsr')
        context['can_edit_breaches'] = check_gdpr_access(self.request.user, 'can_edit_breaches')
        context['can_conduct_dpia'] = check_gdpr_access(self.request.user, 'can_conduct_dpia')
        context['can_edit_activities'] = check_gdpr_access(self.request.user, 'can_edit_activities')
        context['can_edit_policies'] = check_gdpr_access(self.request.user, 'can_edit_policies')
        return context


@login_required
@gdpr_access_required('has_access_compliance_dashboard')
@require_http_methods(["GET"])
def gdpr_guide_api(request):
    """Return JSON { content: html } for the GDPR Guide modal (localized)."""
    lang = (get_language() or 'en')[:2]
    lang_to_code = {'uk': 'UA', 'en': 'GB', 'ru': 'RU'}
    code = lang_to_code.get(lang, 'GB')
    try:
        country = Country.objects.filter(code=code).first()
    except Exception:
        country = None
    content = ''
    guide = GdprGuideContent.objects.first()
    if guide:
        if country:
            trans = GdprGuideContentTranslation.objects.filter(guide=guide, country=country).first()
            if trans and trans.content:
                content = trans.content
        if not content and guide.base_content:
            content = guide.base_content
        if not content:
            trans = GdprGuideContentTranslation.objects.filter(guide=guide).select_related('country').first()
            if trans and trans.content:
                content = trans.content
    return JsonResponse({'content': content})


@login_required
@require_POST
def gdpr_guide_translate(request):
    """API for AI translation of GDPR Guide content (admin)."""
    try:
        data = json.loads(request.body)
        text = (data.get('text') or '').strip()
        country_id = data.get('country_id')
        if not text:
            return JsonResponse({'error': 'Text is required'}, status=400)
        if not country_id:
            return JsonResponse({'error': 'Country ID is required'}, status=400)
        country = Country.objects.get(id=country_id)
    except Country.DoesNotExist:
        return JsonResponse({'error': 'Country not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    lang_map = {
        'ua': 'uk', 'gb': 'en', 'us': 'en', 'uk': 'en', 'ru': 'ru',
        'kz': 'kk', 'by': 'be', 'md': 'ro', 'ge': 'ka', 'am': 'hy', 'az': 'az',
        'ch': 'de', 'at': 'de', 'be': 'nl', 'dk': 'da', 'no': 'no', 'se': 'sv',
        'fi': 'fi', 'ee': 'et', 'lv': 'lv', 'lt': 'lt', 'cz': 'cs', 'sk': 'sk',
        'hu': 'hu', 'ro': 'ro', 'bg': 'bg', 'pl': 'pl', 'fr': 'fr', 'es': 'es',
        'it': 'it', 'cn': 'zh-cn', 'jp': 'ja', 'kr': 'ko', 'tr': 'tr',
    }
    target = lang_map.get(country.code.lower(), country.code.lower())
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target=target)
        translated = translator.translate(text)
        return JsonResponse({
            'success': True,
            'translated_text': translated,
            'target_language': target,
            'country_name': country.name,
        })
    except Exception as e:
        err = str(e)
        if 'No support for the provided language' in err:
            return JsonResponse({
                'success': True,
                'translated_text': text,
                'target_language': target,
                'country_name': country.name,
                'warning': 'Language not supported, returned original',
            })
        return JsonResponse({'success': False, 'error': err}, status=500)


class DataSubjectListView(LoginRequiredMixin, GDPRAccessMixin, GDPRListPaginationMixin, ListView):
    """Список суб'єктів даних"""
    model = DataSubject
    template_name = 'app_gdpr/data_subject_list.html'
    context_object_name = 'data_subjects'
    required_gdpr_permission = 'has_access_data_subjects'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_edit_data_subjects'] = check_gdpr_access(self.request.user, 'can_edit_data_subjects')
        # companies filter for UI
        accessible_companies = get_user_accessible_companies_gdpr(self.request.user)
        if accessible_companies is None:
            from app_conf.models import Company
            context['accessible_companies'] = Company.objects.all()
        elif accessible_companies:
            context['accessible_companies'] = accessible_companies
        else:
            context['accessible_companies'] = []
        return context
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('company', 'user')
        
        # Company access filtering
        accessible = get_user_accessible_companies_gdpr(self.request.user)
        if accessible is None:
            pass  # Access to all
        elif not accessible:
            return qs.none()
        else:
            qs = qs.filter(company__in=accessible)
        
        # Search
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(email__icontains=search) |
                models.Q(phone__icontains=search)
            )
        
        # Company filter
        company = self.request.GET.get('company', '').strip()
        if company:
            qs = qs.filter(company_id=company)
        
        # Consent status filter
        consent_status = self.request.GET.get('consent_status', '').strip()
        if consent_status:
            qs = qs.filter(consent_status=consent_status)
        
        # Sorting
        sort_by = self.request.GET.get('sort', '-created_date')
        qs = qs.order_by(sort_by)
        
        return qs


class DataSubjectDetailView(LoginRequiredMixin, GDPRAccessMixin, DetailView):
    """Деталі суб'єкта даних"""
    model = DataSubject
    template_name = 'app_gdpr/data_subject_detail.html'
    context_object_name = 'data_subject'
    required_gdpr_permission = 'has_access_data_subjects'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_edit_data_subjects'] = check_gdpr_access(self.request.user, 'can_edit_data_subjects')
        # deny access if company not allowed
        if not has_company_access_gdpr(self.request.user, getattr(self.object, 'company', None)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Company access denied")
        return context


class DataSubjectCreateView(LoginRequiredMixin, GDPRAccessMixin, CreateView):
    """Створення суб'єкта даних"""
    model = DataSubject
    form_class = DataSubjectForm
    template_name = 'app_gdpr/data_subject_form.html'
    success_url = reverse_lazy('app_gdpr:data_subject_list')
    required_gdpr_permission = 'can_edit_data_subjects'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class DataSubjectUpdateView(LoginRequiredMixin, GDPRAccessMixin, UpdateView):
    """Редагування суб'єкта даних"""
    model = DataSubject
    form_class = DataSubjectForm
    template_name = 'app_gdpr/data_subject_form.html'
    success_url = reverse_lazy('app_gdpr:data_subject_list')
    required_gdpr_permission = 'can_edit_data_subjects'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


@login_required
@gdpr_access_required('can_export_data_subjects')
def data_subject_export_view(request, pk):
    """Експорт даних суб'єкта (право на переносимість)"""
    data_subject = get_object_or_404(DataSubject, pk=pk)
    
    try:
        response = export_data_subject_data(data_subject, format='json')
        return response
    except Exception as e:
        messages.error(request, _(f'Error exporting data: {e}'))
        return redirect('app_gdpr:data_subject_detail', pk=pk)


@login_required
@gdpr_access_required('has_access_data_subjects')
def data_subject_anonymize_view(request, pk):
    """Анонімізація даних суб'єкта"""
    data_subject = get_object_or_404(DataSubject, pk=pk)
    
    if request.method == 'POST':
        if anonymize_personal_data(data_subject):
            messages.success(request, _('Data subject anonymized successfully'))
        else:
            messages.error(request, _('Error anonymizing data subject'))
        return redirect('app_gdpr:data_subject_list')
    
    return render(request, 'app_gdpr/data_subject_anonymize_confirm.html', {
        'data_subject': data_subject
    })


class ConsentRecordListView(LoginRequiredMixin, GDPRAccessMixin, GDPRListPaginationMixin, ListView):
    """Список записів згод"""
    model = ConsentRecord
    template_name = 'app_gdpr/consent_list.html'
    context_object_name = 'consents'
    required_gdpr_permission = 'has_access_consents'
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('data_subject__company')
        
        # Company access filtering
        accessible = get_user_accessible_companies_gdpr(self.request.user)
        if accessible is None:
            pass  # Access to all
        elif not accessible:
            return qs.none()
        else:
            qs = qs.filter(data_subject__company__in=accessible)
        
        # Search
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(data_subject__first_name__icontains=search) |
                models.Q(data_subject__last_name__icontains=search) |
                models.Q(data_subject__email__icontains=search)
            )
        
        # Consent type filter
        consent_type = self.request.GET.get('consent_type', '').strip()
        if consent_type:
            qs = qs.filter(consent_type=consent_type)
        
        # Status filter
        status = self.request.GET.get('status', '').strip()
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'withdrawn':
            qs = qs.filter(is_active=False)
        
        # Sorting
        sort_by = self.request.GET.get('sort', '-given_date')
        qs = qs.order_by(sort_by)
        
        return qs


class ConsentRecordDetailView(LoginRequiredMixin, GDPRAccessMixin, DetailView):
    """Деталі згоди"""
    model = ConsentRecord
    template_name = 'app_gdpr/consent_detail.html'
    context_object_name = 'consent'
    required_gdpr_permission = 'has_access_consents'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_manage_consents'] = check_gdpr_access(self.request.user, 'can_manage_consents')
        if not has_company_access_gdpr(self.request.user, getattr(self.object.data_subject, 'company', None)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Company access denied")
        return context


class ConsentRecordCreateView(LoginRequiredMixin, GDPRAccessMixin, CreateView):
    """Створення запису згоди"""
    model = ConsentRecord
    form_class = ConsentRecordForm
    template_name = 'app_gdpr/consent_form.html'
    success_url = reverse_lazy('app_gdpr:consent_list')
    required_gdpr_permission = 'can_manage_consents'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


@login_required
@gdpr_access_required('can_manage_consents')
def consent_withdraw_view(request, pk):
    """Відкликання згоди"""
    consent = get_object_or_404(ConsentRecord, pk=pk)
    
    if request.method == 'POST':
        consent.withdraw()
        messages.success(request, _('Consent withdrawn successfully'))
        return redirect('app_gdpr:consent_list')
    
    return render(request, 'app_gdpr/consent_withdraw_confirm.html', {
        'consent': consent
    })


class DSRDashboardView(LoginRequiredMixin, GDPRAccessMixin, TemplateView):
    """Дашборд запитів суб'єктів даних"""
    template_name = 'app_gdpr/dsr_dashboard.html'
    required_gdpr_permission = 'has_access_dsr'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['pending_dsr'] = DataSubjectRequest.objects.filter(status='pending')
        context['in_progress_dsr'] = DataSubjectRequest.objects.filter(status='in_progress')
        context['completed_dsr'] = DataSubjectRequest.objects.filter(status='completed')[:10]
        
        # Прострочені DSR
        overdue_dsr = [dsr for dsr in DataSubjectRequest.objects.filter(
            status__in=['pending', 'in_progress']
        ) if dsr.is_overdue()]
        context['overdue_dsr'] = overdue_dsr
        
        return context


class DSRListView(LoginRequiredMixin, GDPRAccessMixin, GDPRListPaginationMixin, ListView):
    """Список DSR"""
    model = DataSubjectRequest
    template_name = 'app_gdpr/dsr_list.html'
    context_object_name = 'requests'
    required_gdpr_permission = 'has_access_dsr'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_process_dsr'] = check_gdpr_access(self.request.user, 'can_process_dsr')
        
        # Add accessible companies for filter
        accessible_companies = get_user_accessible_companies_gdpr(self.request.user)
        if accessible_companies is None:
            from app_conf.models import Company
            context['accessible_companies'] = Company.objects.all()
        elif accessible_companies:
            context['accessible_companies'] = accessible_companies
        else:
            context['accessible_companies'] = []
        return context
    
    def get_queryset(self):
        from datetime import timedelta
        
        qs = super().get_queryset().select_related('company', 'data_subject', 'assigned_to')
        
        # Company access filtering
        accessible = get_user_accessible_companies_gdpr(self.request.user)
        if accessible is None:
            pass
        elif not accessible:
            return qs.none()
        else:
            qs = qs.filter(company__in=accessible)
        
        # Search
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(request_number__icontains=search) |
                models.Q(data_subject__first_name__icontains=search) |
                models.Q(data_subject__last_name__icontains=search) |
                models.Q(data_subject__email__icontains=search)
            )
        
        # Request type filter
        request_type = self.request.GET.get('request_type', '').strip()
        if request_type:
            qs = qs.filter(request_type=request_type)
        
        # Status filter
        status = self.request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)
        
        # Company filter
        company = self.request.GET.get('company', '').strip()
        if company:
            qs = qs.filter(company_id=company)
        
        # Due date filter
        due_filter = self.request.GET.get('due_filter', '').strip()
        if due_filter == 'overdue':
            today = timezone.now().date()
            qs = qs.filter(
                status__in=['pending', 'in_progress'],
                due_date__lt=today
            )
        elif due_filter == 'due_soon':
            today = timezone.now().date()
            qs = qs.filter(
                status__in=['pending', 'in_progress'],
                due_date__lte=today + timedelta(days=7),
                due_date__gte=today
            )
        
        # Sorting
        sort_by = self.request.GET.get('sort', '-request_date')
        qs = qs.order_by(sort_by)
        
        return qs


class DSRDetailView(LoginRequiredMixin, GDPRAccessMixin, DetailView):
    """Деталі DSR"""
    model = DataSubjectRequest
    template_name = 'app_gdpr/dsr_detail.html'
    context_object_name = 'dsr'
    required_gdpr_permission = 'has_access_dsr'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_process_dsr'] = check_gdpr_access(self.request.user, 'can_process_dsr')
        context['can_approve_dsr'] = check_gdpr_access(self.request.user, 'can_approve_dsr')
        if not has_company_access_gdpr(self.request.user, getattr(self.object, 'company', None)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Company access denied")
        return context


class DSRCreateView(LoginRequiredMixin, GDPRAccessMixin, CreateView):
    """Створення DSR"""
    model = DataSubjectRequest
    form_class = DataSubjectRequestForm
    template_name = 'app_gdpr/dsr_form.html'
    success_url = reverse_lazy('app_gdpr:dsr_list')
    required_gdpr_permission = 'can_process_dsr'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Надіслати підтвердження
        try:
            send_dsr_confirmation_email(self.object)
        except Exception as e:
            logger.error(f"Error sending DSR confirmation: {e}")
        
        messages.success(self.request, _('DSR created successfully'))
        return response


class DSRProcessView(LoginRequiredMixin, GDPRAccessMixin, UpdateView):
    """Обробка DSR"""
    model = DataSubjectRequest
    form_class = DSRProcessForm
    template_name = 'app_gdpr/dsr_process.html'
    success_url = reverse_lazy('app_gdpr:dsr_list')
    required_gdpr_permission = 'can_process_dsr'


@login_required
@gdpr_access_required('can_approve_dsr')
def dsr_complete_view(request, pk):
    """Завершення DSR"""
    dsr = get_object_or_404(DataSubjectRequest, pk=pk)
    
    if request.method == 'POST':
        dsr.status = 'completed'
        dsr.completion_date = timezone.now()
        dsr.response_sent_date = timezone.now()
        dsr.save()
        
        # Надіслати повідомлення про завершення
        try:
            send_dsr_completion_email(dsr)
        except Exception as e:
            logger.error(f"Error sending DSR completion email: {e}")
        
        messages.success(request, _('DSR completed successfully'))
        return redirect('app_gdpr:dsr_detail', pk=pk)
    
    return render(request, 'app_gdpr/dsr_complete_confirm.html', {'dsr': dsr})


@login_required
@gdpr_access_required('can_process_dsr')
def dsr_extend_deadline_view(request, pk):
    """Продовження терміну DSR"""
    dsr = get_object_or_404(DataSubjectRequest, pk=pk)
    
    if request.method == 'POST':
        dsr.extend_deadline()
        messages.success(request, _('DSR deadline extended by 60 days'))
        return redirect('app_gdpr:dsr_detail', pk=pk)
    
    return render(request, 'app_gdpr/dsr_extend_confirm.html', {'dsr': dsr})


class DataBreachListView(LoginRequiredMixin, GDPRAccessMixin, GDPRListPaginationMixin, ListView):
    """Список інцидентів витоку даних"""
    model = DataBreachIncident
    template_name = 'app_gdpr/breach_list.html'
    context_object_name = 'breaches'
    required_gdpr_permission = 'has_access_breach_management'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_edit_breaches'] = check_gdpr_access(self.request.user, 'can_edit_breaches')
        
        # Add accessible companies for filter
        accessible_companies = get_user_accessible_companies_gdpr(self.request.user)
        if accessible_companies is None:
            from app_conf.models import Company
            context['accessible_companies'] = Company.objects.all()
        elif accessible_companies:
            context['accessible_companies'] = accessible_companies
        else:
            context['accessible_companies'] = []
        return context
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('company', 'reported_by', 'assigned_to')
        
        # Company access filtering
        accessible = get_user_accessible_companies_gdpr(self.request.user)
        if accessible is None:
            pass
        elif not accessible:
            return qs.none()
        else:
            qs = qs.filter(company__in=accessible)
        
        # Search
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(incident_number__icontains=search) |
                models.Q(title__icontains=search) |
                models.Q(description__icontains=search)
            )
        
        # Severity filter
        severity = self.request.GET.get('severity', '').strip()
        if severity:
            qs = qs.filter(severity=severity)
        
        # Status filter
        status = self.request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)
        
        # Company filter
        company = self.request.GET.get('company', '').strip()
        if company:
            qs = qs.filter(company_id=company)
        
        # Sorting
        sort_by = self.request.GET.get('sort', '-incident_date')
        qs = qs.order_by(sort_by)
        
        return qs


class DataBreachDetailView(LoginRequiredMixin, GDPRAccessMixin, DetailView):
    """Деталі інциденту"""
    model = DataBreachIncident
    template_name = 'app_gdpr/breach_detail.html'
    context_object_name = 'breach'
    required_gdpr_permission = 'has_access_breach_management'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_edit_breaches'] = check_gdpr_access(self.request.user, 'can_edit_breaches')
        context['can_investigate_breach'] = check_gdpr_access(self.request.user, 'can_investigate_breach')
        if not has_company_access_gdpr(self.request.user, getattr(self.object, 'company', None)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Company access denied")
        return context


class DataBreachCreateView(LoginRequiredMixin, GDPRAccessMixin, CreateView):
    """Створення інциденту витоку"""
    model = DataBreachIncident
    form_class = DataBreachIncidentForm
    template_name = 'app_gdpr/breach_form.html'
    success_url = reverse_lazy('app_gdpr:breach_list')
    required_gdpr_permission = 'can_report_breach'
    
    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        return super().form_valid(form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class DataBreachUpdateView(LoginRequiredMixin, GDPRAccessMixin, UpdateView):
    """Редагування інциденту"""
    model = DataBreachIncident
    form_class = DataBreachIncidentForm
    template_name = 'app_gdpr/breach_form.html'
    success_url = reverse_lazy('app_gdpr:breach_list')
    required_gdpr_permission = 'can_investigate_breach'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


@login_required
@gdpr_access_required('can_investigate_breach')
def breach_report_view(request, pk):
    """Повідомлення про витік регулятору"""
    breach = get_object_or_404(DataBreachIncident, pk=pk)
    
    if request.method == 'POST':
        breach.reported_to_authority = True
        breach.authority_report_date = timezone.now()
        breach.status = 'reported'
        breach.save()
        
        messages.success(request, _('Breach reported to authority'))
        return redirect('app_gdpr:breach_detail', pk=pk)
    
    return render(request, 'app_gdpr/breach_report_confirm.html', {'breach': breach})


class DataProcessingActivityListView(LoginRequiredMixin, GDPRAccessMixin, GDPRListPaginationMixin, ListView):
    """Список діяльності з обробки даних"""
    model = DataProcessingActivity
    template_name = 'app_gdpr/activity_list.html'
    context_object_name = 'activities'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_edit_activities'] = check_gdpr_access(self.request.user, 'can_edit_activities')
        
        # Add accessible companies for filter
        accessible_companies = get_user_accessible_companies_gdpr(self.request.user)
        if accessible_companies is None:
            from app_conf.models import Company
            context['accessible_companies'] = Company.objects.all()
        elif accessible_companies:
            context['accessible_companies'] = accessible_companies
        else:
            context['accessible_companies'] = []
        return context
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('company', 'responsible_person')
        
        # Company access filtering
        accessible = get_user_accessible_companies_gdpr(self.request.user)
        if accessible is None:
            pass
        elif not accessible:
            return qs.none()
        else:
            qs = qs.filter(company__in=accessible)
        
        # Search
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(name__icontains=search) |
                models.Q(description__icontains=search) |
                models.Q(translations__name_local__icontains=search)
            ).distinct()
        
        # Legal basis filter
        legal_basis = self.request.GET.get('legal_basis', '').strip()
        if legal_basis:
            qs = qs.filter(legal_basis=legal_basis)
        
        # Company filter
        company = self.request.GET.get('company', '').strip()
        if company:
            qs = qs.filter(company_id=company)
        
        # Sorting
        sort_by = self.request.GET.get('sort', 'name')
        qs = qs.order_by(sort_by)
        
        return qs


class DataProcessingActivityDetailView(LoginRequiredMixin, GDPRAccessMixin, DetailView):
    """Деталі діяльності"""
    model = DataProcessingActivity
    template_name = 'app_gdpr/activity_detail.html'
    context_object_name = 'activity'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_edit_activities'] = check_gdpr_access(self.request.user, 'can_edit_activities')
        if not has_company_access_gdpr(self.request.user, getattr(self.object, 'company', None)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Company access denied")
        return context


class DataProcessingActivityCreateView(LoginRequiredMixin, GDPRAccessMixin, CreateView):
    """Створення діяльності"""
    model = DataProcessingActivity
    form_class = DataProcessingActivityForm
    template_name = 'app_gdpr/activity_form.html'
    success_url = reverse_lazy('app_gdpr:activity_list')
    required_gdpr_permission = 'can_edit_activities'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class DataProcessingActivityUpdateView(LoginRequiredMixin, GDPRAccessMixin, UpdateView):
    """Редагування діяльності"""
    model = DataProcessingActivity
    form_class = DataProcessingActivityForm
    template_name = 'app_gdpr/activity_form.html'
    success_url = reverse_lazy('app_gdpr:activity_list')
    required_gdpr_permission = 'can_edit_activities'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class DataRetentionPolicyListView(LoginRequiredMixin, GDPRAccessMixin, GDPRListPaginationMixin, ListView):
    """Список політик утримання"""
    model = DataRetentionPolicy
    template_name = 'app_gdpr/policy_list.html'
    context_object_name = 'policies'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_edit_policies'] = check_gdpr_access(self.request.user, 'can_edit_policies')
        
        # Add accessible companies for filter
        accessible_companies = get_user_accessible_companies_gdpr(self.request.user)
        if accessible_companies is None:
            from app_conf.models import Company
            context['accessible_companies'] = Company.objects.all()
        elif accessible_companies:
            context['accessible_companies'] = accessible_companies
        else:
            context['accessible_companies'] = []
        return context
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('company')
        
        # Company access filtering
        accessible = get_user_accessible_companies_gdpr(self.request.user)
        if accessible is None:
            pass
        elif not accessible:
            return qs.none()
        else:
            qs = qs.filter(company__in=accessible)
        
        # Search
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(name__icontains=search) |
                models.Q(description__icontains=search) |
                models.Q(translations__name_local__icontains=search) |
                models.Q(data_category__icontains=search)
            ).distinct()
        
        # Deletion method filter
        deletion_method = self.request.GET.get('deletion_method', '').strip()
        if deletion_method:
            qs = qs.filter(deletion_method=deletion_method)
        
        # Status filter
        status = self.request.GET.get('status', '').strip()
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)
        
        # Company filter
        company = self.request.GET.get('company', '').strip()
        if company:
            qs = qs.filter(company_id=company)
        
        # Sorting
        sort_by = self.request.GET.get('sort', 'name')
        qs = qs.order_by(sort_by)
        
        return qs


class DataRetentionPolicyDetailView(LoginRequiredMixin, GDPRAccessMixin, DetailView):
    """Деталі політики"""
    model = DataRetentionPolicy
    template_name = 'app_gdpr/policy_detail.html'
    context_object_name = 'policy'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_edit_policies'] = check_gdpr_access(self.request.user, 'can_edit_policies')
        if not has_company_access_gdpr(self.request.user, getattr(self.object, 'company', None)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Company access denied")
        return context
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_edit_policies'] = check_gdpr_access(self.request.user, 'can_edit_policies')
        return context


class DataRetentionPolicyCreateView(LoginRequiredMixin, GDPRAccessMixin, CreateView):
    """Створення політики"""
    model = DataRetentionPolicy
    form_class = DataRetentionPolicyForm
    template_name = 'app_gdpr/policy_form.html'
    success_url = reverse_lazy('app_gdpr:policy_list')
    required_gdpr_permission = 'can_edit_policies'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class DataRetentionPolicyUpdateView(LoginRequiredMixin, GDPRAccessMixin, UpdateView):
    """Редагування політики"""
    model = DataRetentionPolicy
    form_class = DataRetentionPolicyForm
    template_name = 'app_gdpr/policy_form.html'
    success_url = reverse_lazy('app_gdpr:policy_list')
    required_gdpr_permission = 'can_edit_policies'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class DPIAListView(LoginRequiredMixin, GDPRAccessMixin, GDPRListPaginationMixin, ListView):
    """Список DPIA оцінок"""
    model = DPIAAssessment
    template_name = 'app_gdpr/dpia_list.html'
    context_object_name = 'dpias'
    required_gdpr_permission = 'has_access_dpia'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_conduct_dpia'] = check_gdpr_access(self.request.user, 'can_conduct_dpia')
        context['can_approve_dpia'] = check_gdpr_access(self.request.user, 'can_approve_dpia')
        
        # Add accessible companies for filter
        accessible_companies = get_user_accessible_companies_gdpr(self.request.user)
        if accessible_companies is None:
            from app_conf.models import Company
            context['accessible_companies'] = Company.objects.all()
        elif accessible_companies:
            context['accessible_companies'] = accessible_companies
        else:
            context['accessible_companies'] = []
        return context
    
    def get_queryset(self):
        qs = super().get_queryset().select_related('company', 'conducted_by', 'approved_by')
        
        # Company access filtering
        accessible = get_user_accessible_companies_gdpr(self.request.user)
        if accessible is None:
            pass
        elif not accessible:
            return qs.none()
        else:
            qs = qs.filter(company__in=accessible)
        
        # Search
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(assessment_number__icontains=search) |
                models.Q(project_name__icontains=search) |
                models.Q(project_description__icontains=search)
            )
        
        # Status filter
        status = self.request.GET.get('status', '').strip()
        if status:
            qs = qs.filter(status=status)
        
        # Risk level filter
        risk_level = self.request.GET.get('risk_level', '').strip()
        if risk_level:
            qs = qs.filter(overall_risk_level=risk_level)
        
        # Company filter
        company = self.request.GET.get('company', '').strip()
        if company:
            qs = qs.filter(company_id=company)
        
        # Sorting
        sort_by = self.request.GET.get('sort', '-created_date')
        qs = qs.order_by(sort_by)
        
        return qs


class DPIADetailView(LoginRequiredMixin, GDPRAccessMixin, DetailView):
    """Деталі DPIA"""
    model = DPIAAssessment
    template_name = 'app_gdpr/dpia_detail.html'
    context_object_name = 'dpia'
    required_gdpr_permission = 'has_access_dpia'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .permissions import check_gdpr_access
        context['can_conduct_dpia'] = check_gdpr_access(self.request.user, 'can_conduct_dpia')
        context['can_approve_dpia'] = check_gdpr_access(self.request.user, 'can_approve_dpia')
        if not has_company_access_gdpr(self.request.user, getattr(self.object, 'company', None)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Company access denied")
        return context


class DPIACreateView(LoginRequiredMixin, GDPRAccessMixin, CreateView):
    """Створення DPIA"""
    model = DPIAAssessment
    form_class = DPIAAssessmentForm
    template_name = 'app_gdpr/dpia_form.html'
    success_url = reverse_lazy('app_gdpr:dpia_list')
    required_gdpr_permission = 'can_conduct_dpia'
    
    def form_valid(self, form):
        form.instance.conducted_by = self.request.user
        return super().form_valid(form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class DPIAUpdateView(LoginRequiredMixin, GDPRAccessMixin, UpdateView):
    """Редагування DPIA"""
    model = DPIAAssessment
    form_class = DPIAAssessmentForm
    template_name = 'app_gdpr/dpia_form.html'
    success_url = reverse_lazy('app_gdpr:dpia_list')
    required_gdpr_permission = 'can_conduct_dpia'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


@login_required
@gdpr_access_required('can_approve_dpia')
def dpia_approve_view(request, pk):
    """Затвердження DPIA"""
    dpia = get_object_or_404(DPIAAssessment, pk=pk)
    
    if request.method == 'POST':
        dpia.status = 'approved'
        dpia.approval_date = timezone.now().date()
        dpia.approved_by = request.user
        dpia.save()
        
        messages.success(request, _('DPIA approved successfully'))
        return redirect('app_gdpr:dpia_detail', pk=pk)
    
    return render(request, 'app_gdpr/dpia_approve_confirm.html', {'dpia': dpia})


class ComplianceReportView(LoginRequiredMixin, GDPRAccessMixin, TemplateView):
    """Звіт про відповідність GDPR з підтримкою фільтрації по компаніях"""
    template_name = 'app_gdpr/compliance_report.html'
    required_gdpr_permission = 'can_generate_reports'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get company filter from request
        from app_conf.models import Company
        selected_company_ids = self.request.GET.getlist('company')
        
        # Get accessible companies for user
        accessible_companies = get_user_accessible_companies_gdpr(self.request.user)
        
        if accessible_companies is None:
            # Superuser or staff - show all companies
            available_companies = Company.objects.all().order_by('name')
        elif accessible_companies:
            # Has specific accessible companies
            if isinstance(accessible_companies, list):
                company_ids = [c.id if hasattr(c, 'id') else c for c in accessible_companies]
                available_companies = Company.objects.filter(id__in=company_ids).order_by('name')
            else:
                available_companies = accessible_companies.order_by('name')
        else:
            available_companies = Company.objects.none()
        
        # Filter by selected companies if any
        selected_companies = None
        filter_companies = None
        
        if selected_company_ids:
            selected_ids = [int(cid) for cid in selected_company_ids]
            selected_companies = available_companies.filter(id__in=selected_ids)
            filter_companies = selected_companies
        else:
            filter_companies = None  # Will show all accessible companies in report
        
        context['available_companies'] = available_companies
        context['selected_companies'] = selected_companies
        context['selected_company_ids'] = [int(cid) for cid in selected_company_ids] if selected_company_ids else []
        
        # Генеруємо дані звіту з фільтрацією
        if filter_companies and filter_companies.exists():
            # Generate report for specific companies
            report_data = {}
            for key in ['data_subjects', 'consents', 'dsr', 'breaches', 'processing_activities', 'dpias']:
                report_data[key] = {
                    'total': 0,
                    'active': 0,
                    'pending': 0,
                    'completed': 0,
                    'overdue': 0,
                    'with_active_consent': 0,
                    'anonymized': 0,
                    'withdrawn': 0,
                    'by_severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0},
                    'reported_to_authority': 0,
                    'notification_overdue': 0,
                    'with_international_transfers': 0,
                    'approved': 0,
                    'in_review': 0,
                }
            
            # Aggregate data from all selected companies
            for company in filter_companies:
                company_report = generate_compliance_report_data(company=company)
                
                # Merge data
                report_data['data_subjects']['total'] += company_report['data_subjects']['total']
                report_data['data_subjects']['with_active_consent'] += company_report['data_subjects']['with_active_consent']
                report_data['data_subjects']['anonymized'] += company_report['data_subjects']['anonymized']
                
                report_data['consents']['total'] += company_report['consents']['total']
                report_data['consents']['active'] += company_report['consents']['active']
                report_data['consents']['withdrawn'] += company_report['consents']['withdrawn']
                
                report_data['dsr']['total'] += company_report['dsr']['total']
                report_data['dsr']['pending'] += company_report['dsr']['pending']
                report_data['dsr']['completed'] += company_report['dsr']['completed']
                report_data['dsr']['overdue'] += company_report['dsr']['overdue']
                
                report_data['breaches']['total'] += company_report['breaches']['total']
                for severity in ['critical', 'high', 'medium', 'low']:
                    report_data['breaches']['by_severity'][severity] += company_report['breaches']['by_severity'][severity]
                report_data['breaches']['reported_to_authority'] += company_report['breaches']['reported_to_authority']
                report_data['breaches']['notification_overdue'] += company_report['breaches']['notification_overdue']
                
                report_data['processing_activities']['total'] += company_report['processing_activities']['total']
                report_data['processing_activities']['active'] += company_report['processing_activities']['active']
                report_data['processing_activities']['with_international_transfers'] += company_report['processing_activities']['with_international_transfers']
                
                report_data['dpias']['total'] += company_report['dpias']['total']
                report_data['dpias']['approved'] += company_report['dpias']['approved']
                report_data['dpias']['in_review'] += company_report['dpias']['in_review']
            
            report_data['report_date'] = timezone.now()
            report_data['company'] = ', '.join([c.name for c in filter_companies])
            report_data['period'] = {'start': None, 'end': None}
        else:
            # Generate report for all accessible companies
            report_data = generate_compliance_report_data()
        
        context.update(report_data)
        
        return context


@login_required
@gdpr_access_required('can_generate_reports')
def generate_report_view(request):
    """Генерація звіту"""
    if request.method == 'POST':
        # Логіка генерації звіту
        messages.success(request, _('Report generated successfully'))
        return redirect('app_gdpr:compliance_report')
    
    return redirect('app_gdpr:compliance_dashboard')


@login_required
@gdpr_access_required('can_generate_reports')
def export_compliance_report_excel(request):
    """
    Експорт GDPR Compliance звіту в Excel з підтримкою фільтрації по компаніях
    """
    from .reports import export_gdpr_compliance_to_excel
    from app_conf.models import Company
    
    try:
        # Get company filter from request
        selected_company_ids = request.GET.getlist('company')
        
        # Get accessible companies for user
        accessible_companies = get_user_accessible_companies_gdpr(request.user)
        
        if accessible_companies is None:
            available_companies = Company.objects.all()
        elif accessible_companies:
            if isinstance(accessible_companies, list):
                company_ids = [c.id if hasattr(c, 'id') else c for c in accessible_companies]
                available_companies = Company.objects.filter(id__in=company_ids)
            else:
                available_companies = accessible_companies
        else:
            available_companies = Company.objects.none()
        
        # Filter by selected companies
        filter_companies = None
        if selected_company_ids:
            selected_ids = [int(cid) for cid in selected_company_ids]
            filter_companies = available_companies.filter(id__in=selected_ids)
        
        # Generate report data
        if filter_companies and filter_companies.exists():
            report_data = {}
            for key in ['data_subjects', 'consents', 'dsr', 'breaches', 'processing_activities', 'dpias']:
                report_data[key] = {
                    'total': 0, 'active': 0, 'pending': 0, 'completed': 0, 'overdue': 0,
                    'with_active_consent': 0, 'anonymized': 0, 'withdrawn': 0,
                    'by_severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0},
                    'reported_to_authority': 0, 'notification_overdue': 0,
                    'with_international_transfers': 0, 'approved': 0, 'in_review': 0,
                }
            
            for company in filter_companies:
                company_report = generate_compliance_report_data(company=company)
                report_data['data_subjects']['total'] += company_report['data_subjects']['total']
                report_data['data_subjects']['with_active_consent'] += company_report['data_subjects']['with_active_consent']
                report_data['data_subjects']['anonymized'] += company_report['data_subjects']['anonymized']
                report_data['consents']['total'] += company_report['consents']['total']
                report_data['consents']['active'] += company_report['consents']['active']
                report_data['consents']['withdrawn'] += company_report['consents']['withdrawn']
                report_data['dsr']['total'] += company_report['dsr']['total']
                report_data['dsr']['pending'] += company_report['dsr']['pending']
                report_data['dsr']['completed'] += company_report['dsr']['completed']
                report_data['dsr']['overdue'] += company_report['dsr']['overdue']
                report_data['breaches']['total'] += company_report['breaches']['total']
                for severity in ['critical', 'high', 'medium', 'low']:
                    report_data['breaches']['by_severity'][severity] += company_report['breaches']['by_severity'][severity]
                report_data['breaches']['reported_to_authority'] += company_report['breaches']['reported_to_authority']
                report_data['breaches']['notification_overdue'] += company_report['breaches']['notification_overdue']
                report_data['processing_activities']['total'] += company_report['processing_activities']['total']
                report_data['processing_activities']['active'] += company_report['processing_activities']['active']
                report_data['processing_activities']['with_international_transfers'] += company_report['processing_activities']['with_international_transfers']
                report_data['dpias']['total'] += company_report['dpias']['total']
                report_data['dpias']['approved'] += company_report['dpias']['approved']
                report_data['dpias']['in_review'] += company_report['dpias']['in_review']
        else:
            report_data = generate_compliance_report_data()
            filter_companies = None
        
        # Generate Excel file
        excel_file = export_gdpr_compliance_to_excel(report_data, filter_companies)
        
        # Create response
        response = HttpResponse(
            excel_file.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        filename = f"GDPR_Compliance_Report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        logger.info(f"GDPR Compliance Report exported to Excel by {request.user.username}")
        
        return response
        
    except ImportError as e:
        messages.error(request, _('Excel export is not available. Missing required libraries.'))
        logger.error(f"Excel export failed: {e}")
        return redirect('app_gdpr:compliance_report')
    except Exception as e:
        messages.error(request, _('Failed to export report: %(error)s') % {'error': str(e)})
        logger.error(f"Excel export failed: {e}")
        return redirect('app_gdpr:compliance_report')


@login_required
@gdpr_access_required('can_generate_reports')
def export_compliance_report_pdf(request):
    """
    Експорт GDPR Compliance звіту в PDF з підтримкою фільтрації по компаніях
    """
    from .reports import export_gdpr_compliance_to_pdf
    from app_conf.models import Company
    
    try:
        # Get company filter from request
        selected_company_ids = request.GET.getlist('company')
        
        # Get accessible companies for user
        accessible_companies = get_user_accessible_companies_gdpr(request.user)
        
        if accessible_companies is None:
            available_companies = Company.objects.all()
        elif accessible_companies:
            if isinstance(accessible_companies, list):
                company_ids = [c.id if hasattr(c, 'id') else c for c in accessible_companies]
                available_companies = Company.objects.filter(id__in=company_ids)
            else:
                available_companies = accessible_companies
        else:
            available_companies = Company.objects.none()
        
        # Filter by selected companies
        filter_companies = None
        if selected_company_ids:
            selected_ids = [int(cid) for cid in selected_company_ids]
            filter_companies = available_companies.filter(id__in=selected_ids)
        
        # Generate report data
        if filter_companies and filter_companies.exists():
            report_data = {}
            for key in ['data_subjects', 'consents', 'dsr', 'breaches', 'processing_activities', 'dpias']:
                report_data[key] = {
                    'total': 0, 'active': 0, 'pending': 0, 'completed': 0, 'overdue': 0,
                    'with_active_consent': 0, 'anonymized': 0, 'withdrawn': 0,
                    'by_severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0},
                    'reported_to_authority': 0, 'notification_overdue': 0,
                    'with_international_transfers': 0, 'approved': 0, 'in_review': 0,
                }
            
            for company in filter_companies:
                company_report = generate_compliance_report_data(company=company)
                report_data['data_subjects']['total'] += company_report['data_subjects']['total']
                report_data['data_subjects']['with_active_consent'] += company_report['data_subjects']['with_active_consent']
                report_data['data_subjects']['anonymized'] += company_report['data_subjects']['anonymized']
                report_data['consents']['total'] += company_report['consents']['total']
                report_data['consents']['active'] += company_report['consents']['active']
                report_data['consents']['withdrawn'] += company_report['consents']['withdrawn']
                report_data['dsr']['total'] += company_report['dsr']['total']
                report_data['dsr']['pending'] += company_report['dsr']['pending']
                report_data['dsr']['completed'] += company_report['dsr']['completed']
                report_data['dsr']['overdue'] += company_report['dsr']['overdue']
                report_data['breaches']['total'] += company_report['breaches']['total']
                for severity in ['critical', 'high', 'medium', 'low']:
                    report_data['breaches']['by_severity'][severity] += company_report['breaches']['by_severity'][severity]
                report_data['breaches']['reported_to_authority'] += company_report['breaches']['reported_to_authority']
                report_data['breaches']['notification_overdue'] += company_report['breaches']['notification_overdue']
                report_data['processing_activities']['total'] += company_report['processing_activities']['total']
                report_data['processing_activities']['active'] += company_report['processing_activities']['active']
                report_data['processing_activities']['with_international_transfers'] += company_report['processing_activities']['with_international_transfers']
                report_data['dpias']['total'] += company_report['dpias']['total']
                report_data['dpias']['approved'] += company_report['dpias']['approved']
                report_data['dpias']['in_review'] += company_report['dpias']['in_review']
        else:
            report_data = generate_compliance_report_data()
            filter_companies = None
        
        # Generate PDF file
        pdf_file = export_gdpr_compliance_to_pdf(report_data, filter_companies)
        
        # Create response
        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
        
        filename = f"GDPR_Compliance_Report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        logger.info(f"GDPR Compliance Report exported to PDF by {request.user.username}")
        
        return response
        
    except ImportError as e:
        messages.error(request, _('PDF export is not available. Missing required libraries.'))
        logger.error(f"PDF export failed: {e}")
        return redirect('app_gdpr:compliance_report')
    except Exception as e:
        messages.error(request, _('Failed to export report: %(error)s') % {'error': str(e)})
        logger.error(f"PDF export failed: {e}")
        return redirect('app_gdpr:compliance_report')


@login_required
@gdpr_access_required()
def users_by_company_api(request, company_id):
    """API endpoint для отримання користувачів за компанією з Department та Position"""
    from django.contrib.auth.models import User
    from app_cabinet.models import CabinetUser
    
    try:
        # Отримуємо користувачів компанії з інформацією про департамент та посаду
        users = User.objects.filter(
            cabinet__company_id=company_id
        ).select_related(
            'cabinet__department',
            'cabinet__position'
        ).order_by('first_name', 'last_name', 'username')
        
        users_data = []
        for user in users:
            try:
                cabinet = user.cabinet
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': user.get_full_name() or user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'department': cabinet.department.get_name() if cabinet.department else None,
                    'position': cabinet.position.get_name() if cabinet.position else None,
                }
                users_data.append(user_data)
            except CabinetUser.DoesNotExist:
                # Користувач без cabinet профілю
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': user.get_full_name() or user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'department': None,
                    'position': None,
                }
                users_data.append(user_data)
        
        return JsonResponse({
            'success': True,
            'users': users_data,
            'count': len(users_data)
        })
        
    except Exception as e:
        logger.error(f"Error loading users for company {company_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'users': []
        }, status=500)


class GDPRGuideView(LoginRequiredMixin, GDPRAccessMixin, TemplateView):
    """Інтерактивний гід по впровадженню GDPR"""
    template_name = 'app_gdpr/gdpr_guide.html'
    required_gdpr_permission = 'has_access_compliance_dashboard'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Отримати доступні компанії користувача
        accessible_companies = get_user_accessible_companies_gdpr(user)
        
        # Базовий queryset з фільтрацією по компаніям
        if accessible_companies is None:
            # Доступ до всіх компаній
            data_subjects_qs = DataSubject.objects.all()
            consents_qs = ConsentRecord.objects.all()
            dsr_qs = DataSubjectRequest.objects.all()
            breaches_qs = DataBreachIncident.objects.all()
            dpia_qs = DPIAAssessment.objects.all()
            activities_qs = DataProcessingActivity.objects.all()
            policies_qs = DataRetentionPolicy.objects.all()
        elif accessible_companies:
            # Доступ до конкретних компаній
            data_subjects_qs = DataSubject.objects.filter(company__in=accessible_companies)
            consents_qs = ConsentRecord.objects.filter(data_subject__company__in=accessible_companies)
            dsr_qs = DataSubjectRequest.objects.filter(company__in=accessible_companies)
            breaches_qs = DataBreachIncident.objects.filter(company__in=accessible_companies)
            dpia_qs = DPIAAssessment.objects.filter(company__in=accessible_companies)
            activities_qs = DataProcessingActivity.objects.filter(company__in=accessible_companies)
            policies_qs = DataRetentionPolicy.objects.filter(company__in=accessible_companies)
        else:
            # Немає доступу до жодної компанії
            data_subjects_qs = DataSubject.objects.none()
            consents_qs = ConsentRecord.objects.none()
            dsr_qs = DataSubjectRequest.objects.none()
            breaches_qs = DataBreachIncident.objects.none()
            dpia_qs = DPIAAssessment.objects.none()
            activities_qs = DataProcessingActivity.objects.none()
            policies_qs = DataRetentionPolicy.objects.none()
        
        # Підрахунок прогресу (9 кроків)
        progress_steps = []
        completed_count = 0
        
        # Крок 1: Доступ до модуля (завжди виконано, якщо користувач тут)
        progress_steps.append({
            'id': 'step_access',
            'title': _('Access GDPR module and review guide'),
            'completed': True,
            'description': _("You're here now!"),
        })
        completed_count += 1
        
        # Крок 2: Створити хоча б 1 Data Subject
        has_data_subjects = data_subjects_qs.exists()
        progress_steps.append({
            'id': 'step_data_subjects',
            'title': _('Set up Data Subjects registry'),
            'completed': has_data_subjects,
            'in_progress': not has_data_subjects,
            'description': _('Create at least 1 Data Subject'),
            'action_url': 'app_gdpr:data_subject_create',
            'learn_more': '#section-inventory',
        })
        if has_data_subjects:
            completed_count += 1
        
        # Крок 3: Записати хоча б 1 Consent
        has_consents = consents_qs.exists()
        progress_steps.append({
            'id': 'step_consents',
            'title': _('Configure Consent management'),
            'completed': has_consents,
            'description': _('Record at least 1 Consent for a Data Subject'),
            'action_url': 'app_gdpr:consent_create',
            'learn_more': '#section-inventory',
            'requires_previous': not has_data_subjects,
        })
        if has_consents:
            completed_count += 1
        
        # Крок 4: Створити хоча б 1 DSR
        has_dsr = dsr_qs.exists()
        progress_steps.append({
            'id': 'step_dsr',
            'title': _('Establish DSR workflow'),
            'completed': has_dsr,
            'description': _('Create and process at least 1 Data Subject Request'),
            'action_url': 'app_gdpr:dsr_create',
            'learn_more': '#section-dsr',
            'requires_previous': not has_consents,
        })
        if has_dsr:
            completed_count += 1
        
        # Крок 5: Задокументувати хоча б 1 Breach
        has_breaches = breaches_qs.exists()
        progress_steps.append({
            'id': 'step_breaches',
            'title': _('Implement breach response procedures'),
            'completed': has_breaches,
            'description': _('Document breach response plan (can use test incident)'),
            'action_url': 'app_gdpr:breach_create',
            'learn_more': '#section-breaches',
            'requires_previous': not has_dsr,
        })
        if has_breaches:
            completed_count += 1
        
        # Крок 6: Провести хоча б 1 DPIA
        has_dpia = dpia_qs.exists()
        progress_steps.append({
            'id': 'step_dpia',
            'title': _('Conduct DPIA for high-risk activities'),
            'completed': has_dpia,
            'description': _('Create at least 1 DPIA Assessment'),
            'action_url': 'app_gdpr:dpia_create',
            'learn_more': '#section-dpia',
            'requires_previous': not has_breaches,
        })
        if has_dpia:
            completed_count += 1
        
        # Крок 7: Задокументувати хоча б 1 Processing Activity
        has_activities = activities_qs.exists()
        progress_steps.append({
            'id': 'step_activities',
            'title': _('Document processing activities (Art. 30)'),
            'completed': has_activities,
            'description': _('Register at least 1 Processing Activity'),
            'action_url': 'app_gdpr:activity_create',
            'learn_more': '#section-activities',
            'requires_previous': not has_dpia,
        })
        if has_activities:
            completed_count += 1
        
        # Крок 8: Визначити хоча б 1 Retention Policy
        has_policies = policies_qs.exists()
        progress_steps.append({
            'id': 'step_policies',
            'title': _('Define retention policies'),
            'completed': has_policies,
            'description': _('Create at least 1 Data Retention Policy'),
            'action_url': 'app_gdpr:policy_create',
            'learn_more': '#section-policies',
            'requires_previous': not has_activities,
        })
        if has_policies:
            completed_count += 1
        
        # Крок 9: Переглянути звіти
        # Вважаємо виконаним, якщо всі попередні кроки виконано
        all_previous_completed = has_data_subjects and has_consents and has_dsr and has_breaches and has_dpia and has_activities and has_policies
        progress_steps.append({
            'id': 'step_reports',
            'title': _('Generate compliance reports'),
            'completed': all_previous_completed,
            'description': _('Review dashboard and generate your first report'),
            'action_url': 'app_gdpr:compliance_report',
            'learn_more': '#section-reporting',
            'requires_previous': not all_previous_completed,
        })
        if all_previous_completed:
            completed_count += 1
        
        # Підрахунок відсотка прогресу
        total_steps = 9
        progress_percentage = int((completed_count / total_steps) * 100)
        
        # Додати до контексту
        context['progress_steps'] = progress_steps
        context['completed_count'] = completed_count
        context['total_steps'] = total_steps
        context['progress_percentage'] = progress_percentage
        
        # Права доступу для кнопок
        from .permissions import check_gdpr_access
        context['can_edit_data_subjects'] = check_gdpr_access(user, 'can_edit_data_subjects')
        context['can_manage_consents'] = check_gdpr_access(user, 'can_manage_consents')
        context['can_process_dsr'] = check_gdpr_access(user, 'can_process_dsr')
        context['can_approve_dsr'] = check_gdpr_access(user, 'can_approve_dsr')
        context['can_edit_breaches'] = check_gdpr_access(user, 'can_edit_breaches')
        context['can_investigate_breach'] = check_gdpr_access(user, 'can_investigate_breach')
        context['can_conduct_dpia'] = check_gdpr_access(user, 'can_conduct_dpia')
        context['can_approve_dpia'] = check_gdpr_access(user, 'can_approve_dpia')
        context['can_edit_activities'] = check_gdpr_access(user, 'can_edit_activities')
        context['can_edit_policies'] = check_gdpr_access(user, 'can_edit_policies')
        context['can_generate_reports'] = check_gdpr_access(user, 'can_generate_reports')
        
        # Завантажувані ресурси з бази даних
        from .models import GDPRGuide
        resources = GDPRGuide.objects.filter(is_active=True)
        
        # Групувати ресурси по категоріях
        context['resources_by_category'] = {
            'checklist': resources.filter(category='checklist'),
            'template': resources.filter(category='template'),
            'email': resources.filter(category='email'),
            'form': resources.filter(category='form'),
            'guide': resources.filter(category='guide'),
        }
        
        return context


@login_required
@gdpr_access_required()
def download_resource_view(request, resource_id):
    """Download GDPR guide resource file"""
    from django.http import FileResponse, Http404
    from .models import GDPRGuide
    
    try:
        resource = GDPRGuide.objects.get(pk=resource_id, is_active=True)
    except GDPRGuide.DoesNotExist:
        raise Http404("Resource not found")
    
    if not resource.file:
        raise Http404("File not found")
    
    # Open file and return as response
    try:
        response = FileResponse(resource.file.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{resource.file.name.split("/")[-1]}"'
        return response
    except Exception as e:
        logger.error(f"Error downloading resource {resource_id}: {e}")
        raise Http404("Error downloading file")
