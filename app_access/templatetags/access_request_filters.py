from django import template
from django.utils import timezone
from datetime import datetime

register = template.Library()

@register.filter
def calculate_period_progress(request):
    now = timezone.now()
    start_date = request.access_record.start_date
    end_date = request.access_record.end_date
    
    if not all([start_date, end_date]):
        return {'percentage': 0, 'is_expired': False, 'is_active': False}
    
    total_duration = (end_date - start_date).total_seconds()
    if now < start_date:
        return {'percentage': 0, 'is_expired': False, 'is_active': False}
    elif now > end_date:
        return {'percentage': 100, 'is_expired': True, 'is_active': False}
    
    elapsed = (now - start_date).total_seconds()
    percentage = min(100, max(0, (elapsed / total_duration) * 100))
    
    return {
        'percentage': percentage,
        'is_expired': False,
        'is_active': True
    }

@register.filter
def get_remaining_days(request):
    now = timezone.now()
    start_date = request.access_record.start_date
    end_date = request.access_record.end_date
    
    if not all([start_date, end_date]):
        return {'days': 0, 'is_expired': False, 'is_future': False}
    
    if now < start_date:
        days = (start_date - now).days
        return {'days': days, 'is_expired': False, 'is_future': True}
    elif now > end_date:
        days = (now - end_date).days
        return {'days': days, 'is_expired': True, 'is_future': False}
    
    days = (end_date - now).days
    return {'days': days, 'is_expired': False, 'is_future': False}

# Аналогічні фільтри для request period
@register.filter
def calculate_request_progress(request):
    return calculate_period_progress(request)

@register.filter
def get_request_remaining_days(request):
    return get_remaining_days(request) 