from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from .models import (
    AccessRequest, AccessRequestAttachment, AccessRequestApprover, 
    AccessRequestApproverStatusHistory, EmailNotificationHistory, SystemAccess
)


# Guide model names used to group them in admin app_list (see apps.py)
ACCESS_GUIDE_MODEL_NAMES = {
    'AccessRecordsGuide',
    'AccessConfigIsGuide',
    'AccessMatrixGuide',
    'UserAccessRequestGuide',
    'ManageAccessRequestsGuide',
    'AccessNotificationGuide',
}


@staff_member_required
def access_guides_settings_view(request):
    """Single settings page for all Access Guides (replaces 6 separate menu items in admin)."""
    guides = [
        (_('Access Records Guides'), 'admin:app_access_accessrecordsguide_changelist'),
        (_('Access Config IS Guides'), 'admin:app_access_accessconfigisguide_changelist'),
        (_('Access Matrix Guides'), 'admin:app_access_accessmatrixguide_changelist'),
        (_('User Access Request Guides'), 'admin:app_access_useraccessrequestguide_changelist'),
        (_('Manage Access Requests Guides'), 'admin:app_access_manageaccessrequestsguide_changelist'),
        (_('Access Notification Guides'), 'admin:app_access_accessnotificationguide_changelist'),
    ]
    context = {
        'title': _('Access Guides – Settings'),
        'guides': [(label, reverse(url_name)) for label, url_name in guides],
        'opts': AccessRequest._meta,  # for breadcrumbs app_label
    }
    return render(request, 'admin/app_access/access_guides_settings.html', context)


@staff_member_required
def confirm_delete_all_requests(request):
    """Підтвердження видалення всіх Access Requests"""
    
    if request.method == 'POST':
        if request.POST.get('confirm') == 'yes':
            # Виконуємо видалення
            with transaction.atomic():
                # Підраховуємо кількість записів для видалення
                total_requests = AccessRequest.objects.count()
                total_attachments = AccessRequestAttachment.objects.count()
                total_approvers = AccessRequestApprover.objects.count()
                total_approver_history = AccessRequestApproverStatusHistory.objects.count()
                total_email_notifications = EmailNotificationHistory.objects.count()
                total_access_records = SystemAccess.objects.count()
                
                # Видаляємо всі записи
                EmailNotificationHistory.objects.all().delete()
                AccessRequestApproverStatusHistory.objects.all().delete()
                AccessRequestApprover.objects.all().delete()
                AccessRequestAttachment.objects.all().delete()
                AccessRequest.objects.all().delete()
                SystemAccess.objects.all().delete()
                
                # Показуємо повідомлення про успіх
                messages.success(
                    request,
                    f"Successfully deleted {total_requests} access requests, "
                    f"{total_attachments} attachments, {total_approvers} approvers, "
                    f"{total_approver_history} approver history records, "
                    f"{total_email_notifications} email notifications, "
                    f"{total_access_records} access records."
                )
            
            return HttpResponseRedirect(reverse('admin:app_access_accessrequest_changelist'))
        else:
            # Скасування
            messages.info(request, _('Deletion cancelled.'))
            return HttpResponseRedirect(reverse('admin:app_access_accessrequest_changelist'))
    
    # Показуємо форму підтвердження
    context = {
        'title': _('Confirm Delete All Access Requests'),
        'opts': AccessRequest._meta,
        'total_requests': AccessRequest.objects.count(),
        'total_attachments': AccessRequestAttachment.objects.count(),
        'total_approvers': AccessRequestApprover.objects.count(),
        'total_approver_history': AccessRequestApproverStatusHistory.objects.count(),
        'total_email_notifications': EmailNotificationHistory.objects.count(),
        'total_access_records': SystemAccess.objects.count(),
    }
    
    return render(request, 'admin/app_access/accessrequest/confirm_delete_all.html', context)


@staff_member_required
def delete_requests_by_filter(request):
    """Видалення запитів за фільтром"""
    
    if request.method == 'POST':
        # Отримуємо параметри фільтра
        company_id = request.POST.get('company_id')
        system_id = request.POST.get('system_id')
        status = request.POST.get('status')
        admin_status = request.POST.get('admin_status')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        
        # Формуємо фільтр
        queryset = AccessRequest.objects.all()
        
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if system_id:
            queryset = queryset.filter(system_id=system_id)
        if status:
            queryset = queryset.filter(status=status)
        if admin_status:
            queryset = queryset.filter(admin_status=admin_status)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Підраховуємо кількість
        count = queryset.count()
        
        if count == 0:
            messages.warning(request, _('No requests found matching the specified criteria.'))
            return HttpResponseRedirect(reverse('admin:app_access_accessrequest_changelist'))
        
        # Виконуємо видалення
        with transaction.atomic():
            # Видаляємо пов'язані записи
            for access_request in queryset:
                access_request.attachments.all().delete()
                access_request.approvers.all().delete()
                
                # Видаляємо історію затверджувачів
                AccessRequestApproverStatusHistory.objects.filter(
                    request_approver__access_request=access_request
                ).delete()
                
                # Видаляємо email сповіщення
                EmailNotificationHistory.objects.filter(
                    access_request=access_request
                ).delete()
                
                # Видаляємо AccessRecord записи
                access_request.access_records.all().delete()
            
            # Видаляємо самі запити
            queryset.delete()
        
        messages.success(
            request,
            f"Successfully deleted {count} access requests matching the specified criteria."
        )
        
        return HttpResponseRedirect(reverse('admin:app_access_accessrequest_changelist'))
    
    # Показуємо форму фільтра
    from app_asset.models import Company, InformationSystem
    
    context = {
        'title': _('Delete Access Requests by Filter'),
        'opts': AccessRequest._meta,
        'companies': Company.objects.all(),
        'systems': InformationSystem.objects.all(),
        'status_choices': AccessRequest.STATUS_CHOICES,
        'admin_status_choices': AccessRequest.ADMIN_STATUS_CHOICES,
    }
    
    return render(request, 'admin/app_access/accessrequest/delete_by_filter.html', context) 