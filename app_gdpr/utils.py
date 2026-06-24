#  SecBoard\SecBoard\app_gdpr\utils.py

import json
import hashlib
import zipfile
import io
from datetime import timedelta, date
from django.utils import timezone
from django.core.serializers import serialize
from django.http import HttpResponse
from django.utils.translation import gettext as _
import logging

logger = logging.getLogger(__name__)


def anonymize_personal_data(data_subject):
    """
    Анонімізація персональних даних суб'єкта
    
    Args:
        data_subject: екземпляр DataSubject
    
    Returns:
        bool: True якщо успішно
    """
    try:
        # Зберігаємо hash email для можливості виявлення дублікатів
        email_hash = hashlib.sha256(data_subject.email.encode()).hexdigest()[:16]
        
        # Анонімізуємо дані
        data_subject.first_name = f"Anonymized_{email_hash}"
        data_subject.last_name = "User"
        data_subject.email = f"anonymized_{email_hash}@deleted.local"
        data_subject.phone = ""
        data_subject.is_anonymized = True
        
        # Якщо є зв'язаний користувач, деактивуємо
        if data_subject.user:
            data_subject.user.is_active = False
            data_subject.user.email = data_subject.email
            data_subject.user.save()
        
        data_subject.save()
        
        logger.info(f"Data subject anonymized: {email_hash}")
        return True
        
    except Exception as e:
        logger.error(f"Error anonymizing data subject: {e}")
        return False


def export_data_subject_data(data_subject, format='json'):
    """
    Експорт всіх даних суб'єкта (право на переносимість даних - Article 20 GDPR)
    
    Args:
        data_subject: екземпляр DataSubject
        format: формат експорту ('json', 'csv', 'zip')
    
    Returns:
        HttpResponse: відповідь з файлом для завантаження
    """
    try:
        # Збираємо всі дані
        data = {
            'personal_information': {
                'first_name': data_subject.first_name,
                'last_name': data_subject.last_name,
                'email': data_subject.email,
                'phone': data_subject.phone,
                'created_date': str(data_subject.created_date),
            },
            'consents': [],
            'requests': [],
            'related_activities': []
        }
        
        # Додаємо згоди
        for consent in data_subject.consents.all():
            data['consents'].append({
                'type': consent.get_consent_type_display(),
                'given_date': str(consent.given_date),
                'is_active': consent.is_active,
                'withdrawn_date': str(consent.withdrawn_date) if consent.withdrawn_date else None,
            })
        
        # Додаємо DSR запити
        for request in data_subject.dsr_requests.all():
            data['requests'].append({
                'request_number': request.request_number,
                'type': request.get_request_type_display(),
                'date': str(request.request_date),
                'status': request.get_status_display(),
            })
        
        if format == 'json':
            # JSON експорт
            response = HttpResponse(
                json.dumps(data, indent=2, ensure_ascii=False),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="data_export_{data_subject.email}_{timezone.now().strftime("%Y%m%d")}.json"'
            
        elif format == 'zip':
            # ZIP архів з JSON файлом
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(
                    f'data_export_{data_subject.email}.json',
                    json.dumps(data, indent=2, ensure_ascii=False)
                )
            
            response = HttpResponse(buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="data_export_{data_subject.email}_{timezone.now().strftime("%Y%m%d")}.zip"'
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Data exported for data subject: {data_subject.email}")
        return response
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise


def calculate_dsr_deadline(request_date, base_days=30):
    """
    Розрахунок дедлайну для DSR (30 днів від запиту)
    
    Args:
        request_date: дата запиту
        base_days: базова кількість днів (за замовчуванням 30)
    
    Returns:
        date: дата дедлайну
    """
    if isinstance(request_date, date) and not isinstance(request_date, timezone.datetime):
        return request_date + timedelta(days=base_days)
    return (request_date + timedelta(days=base_days)).date()


def calculate_breach_notification_deadline(discovery_date):
    """
    Розрахунок 72-годинного дедлайну для повідомлення про витік (Article 33 GDPR)
    
    Args:
        discovery_date: дата виявлення витоку
    
    Returns:
        datetime: дата і час дедлайну
    """
    return discovery_date + timedelta(hours=72)


def check_consent_expiration(consent_record):
    """
    Перевірка, чи закінчився термін дії згоди
    
    Args:
        consent_record: екземпляр ConsentRecord
    
    Returns:
        bool: True якщо згода закінчилася
    """
    if not consent_record.expiration_date:
        return False
    
    return timezone.now().date() > consent_record.expiration_date


def apply_retention_policy(data_subject, policy):
    """
    Застосування політики утримання даних до суб'єкта
    
    Args:
        data_subject: екземпляр DataSubject
        policy: екземпляр DataRetentionPolicy
    
    Returns:
        bool: True якщо політика застосована
    """
    try:
        # Розрахувати дату видалення
        deletion_date = (
            data_subject.last_activity_date + 
            timedelta(days=policy.retention_period_days)
        ).date()
        
        data_subject.deletion_scheduled_date = deletion_date
        data_subject.save()
        
        logger.info(
            f"Retention policy '{policy.get_name()}' applied to {data_subject.email}. "
            f"Deletion scheduled for {deletion_date}"
        )
        return True
        
    except Exception as e:
        logger.error(f"Error applying retention policy: {e}")
        return False


def generate_unique_request_number(prefix='DSR'):
    """
    Генерація унікального номера запиту
    
    Args:
        prefix: префікс номера (DSR, BREACH, DPIA, тощо)
    
    Returns:
        str: унікальний номер
    """
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    return f"{prefix}-{timestamp}"


def generate_compliance_report_data(company=None, start_date=None, end_date=None):
    """
    Генерація даних для звіту про відповідність GDPR
    
    Args:
        company: компанія (необов'язково)
        start_date: дата початку періоду
        end_date: дата кінця періоду
    
    Returns:
        dict: дані для звіту
    """
    from .models import (
        DataSubject, 
        ConsentRecord, 
        DataSubjectRequest, 
        DataBreachIncident,
        DataProcessingActivity,
        DPIAAssessment
    )
    
    # Фільтри за компанією
    filters = {}
    if company:
        filters['company'] = company
    
    # Фільтри за датою
    date_filters = {}
    if start_date and end_date:
        date_filters['created_date__range'] = [start_date, end_date]
    
    report_data = {
        'report_date': timezone.now(),
        'company': company.name if company else 'All Companies',
        'period': {
            'start': start_date,
            'end': end_date
        },
        'data_subjects': {
            'total': DataSubject.objects.filter(**filters).count(),
            'with_active_consent': DataSubject.objects.filter(
                **filters, 
                consent_status='given'
            ).count(),
            'anonymized': DataSubject.objects.filter(
                **filters, 
                is_anonymized=True
            ).count(),
        },
        'consents': {
            'total': ConsentRecord.objects.filter(
                data_subject__company=company
            ).count() if company else ConsentRecord.objects.count(),
            'active': ConsentRecord.objects.filter(
                data_subject__company=company,
                is_active=True
            ).count() if company else ConsentRecord.objects.filter(is_active=True).count(),
            'withdrawn': ConsentRecord.objects.filter(
                data_subject__company=company,
                is_active=False
            ).count() if company else ConsentRecord.objects.filter(is_active=False).count(),
        },
        'dsr': {
            'total': DataSubjectRequest.objects.filter(**filters, **date_filters).count(),
            'pending': DataSubjectRequest.objects.filter(
                **filters, 
                status='pending'
            ).count(),
            'completed': DataSubjectRequest.objects.filter(
                **filters, 
                status='completed'
            ).count(),
            'overdue': sum(
                1 for dsr in DataSubjectRequest.objects.filter(**filters)
                if dsr.is_overdue()
            ),
        },
        'breaches': {
            'total': DataBreachIncident.objects.filter(**filters, **date_filters).count(),
            'by_severity': {
                'critical': DataBreachIncident.objects.filter(
                    **filters, 
                    severity='critical'
                ).count(),
                'high': DataBreachIncident.objects.filter(
                    **filters, 
                    severity='high'
                ).count(),
                'medium': DataBreachIncident.objects.filter(
                    **filters, 
                    severity='medium'
                ).count(),
                'low': DataBreachIncident.objects.filter(
                    **filters, 
                    severity='low'
                ).count(),
            },
            'reported_to_authority': DataBreachIncident.objects.filter(
                **filters, 
                reported_to_authority=True
            ).count(),
            'notification_overdue': sum(
                1 for breach in DataBreachIncident.objects.filter(**filters)
                if breach.is_notification_overdue()
            ),
        },
        'processing_activities': {
            'total': DataProcessingActivity.objects.filter(**filters).count(),
            'active': DataProcessingActivity.objects.filter(
                **filters, 
                is_active=True
            ).count(),
            'with_international_transfers': DataProcessingActivity.objects.filter(
                **filters, 
                international_transfers=True
            ).count(),
        },
        'dpias': {
            'total': DPIAAssessment.objects.filter(**filters).count(),
            'approved': DPIAAssessment.objects.filter(
                **filters, 
                status='approved'
            ).count(),
            'in_review': DPIAAssessment.objects.filter(
                **filters, 
                status='in_review'
            ).count(),
        },
    }
    
    return report_data


def pseudonymize_data(text):
    """
    Псевдонімізація тексту (заміна персональних даних на псевдоніми)
    
    Args:
        text: текст для псевдонімізації
    
    Returns:
        str: псевдонімізований текст
    """
    # Простий приклад - можна розширити з використанням NLP
    import re
    
    # Замінюємо email адреси
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    
    # Замінюємо номери телефонів (український формат)
    text = re.sub(r'\+?38\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}', '[PHONE]', text)
    
    # Замінюємо ІПН/код
    text = re.sub(r'\b\d{10}\b', '[ID_NUMBER]', text)
    
    return text


def validate_data_subject_request(request_data):
    """
    Валідація запиту суб'єкта даних
    
    Args:
        request_data: дані запиту
    
    Returns:
        tuple: (is_valid, errors)
    """
    errors = []
    
    # Перевірка обов'язкових полів
    required_fields = ['request_type', 'data_subject', 'request_description']
    for field in required_fields:
        if field not in request_data or not request_data[field]:
            errors.append(f"Field '{field}' is required")
    
    # Перевірка типу запиту
    valid_types = [
        'access', 'rectification', 'erasure', 'restriction', 
        'portability', 'object', 'automated_decision'
    ]
    if 'request_type' in request_data and request_data['request_type'] not in valid_types:
        errors.append(f"Invalid request type: {request_data['request_type']}")
    
    return (len(errors) == 0, errors)


def calculate_data_subject_risk_score(data_subject):
    """
    Розрахунок ризик-скору для суб'єкта даних
    
    Args:
        data_subject: екземпляр DataSubject
    
    Returns:
        dict: оцінка ризику
    """
    risk_score = 0
    risk_factors = []
    
    # Немає активної згоди
    if data_subject.consent_status != 'given':
        risk_score += 20
        risk_factors.append(_('No active consent'))
    
    # Прострочені DSR запити
    overdue_dsr = sum(
        1 for dsr in data_subject.dsr_requests.all()
        if dsr.is_overdue()
    )
    if overdue_dsr > 0:
        risk_score += overdue_dsr * 15
        risk_factors.append(_(f'{overdue_dsr} overdue DSR requests'))
    
    # Прострочена дата видалення
    if data_subject.deletion_scheduled_date:
        if timezone.now().date() > data_subject.deletion_scheduled_date:
            risk_score += 25
            risk_factors.append(_('Data retention period exceeded'))
    
    # Закінчені згоди
    expired_consents = sum(
        1 for consent in data_subject.consents.all()
        if check_consent_expiration(consent) and consent.is_active
    )
    if expired_consents > 0:
        risk_score += expired_consents * 10
        risk_factors.append(_(f'{expired_consents} expired consents'))
    
    # Визначення рівня ризику
    if risk_score >= 50:
        risk_level = 'high'
    elif risk_score >= 30:
        risk_level = 'medium'
    else:
        risk_level = 'low'
    
    return {
        'score': min(risk_score, 100),  # Максимум 100
        'level': risk_level,
        'factors': risk_factors
    }

