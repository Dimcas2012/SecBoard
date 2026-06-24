from django import template
from django.utils import timezone
from datetime import datetime

register = template.Library()

@register.filter
def timeuntil_days(value):
    """
    Returns number of days between now and given date
    Negative number means date is in the past
    """
    if not value:
        return 0
        
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return 0
            
    now = timezone.now()
    delta = value - now if isinstance(value, datetime) else timezone.datetime.strptime(value, "%Y-%m-%d").date() - now.date()
    return delta.days

@register.filter
def percentage_of_days(days, max_days):
    """
    Returns percentage of days relative to max_days
    Used for progress bar width
    """
    if not days or not max_days:
        return 0
    
    percentage = (days / float(max_days)) * 100
    return min(max(percentage, 0), 100)  # Обмежуємо значення між 0 та 100 

@register.filter
def abs(value):
    """
    Returns absolute value
    """
    try:
        return __builtins__['abs'](int(value))
    except (ValueError, TypeError):
        return value 

@register.filter
def calculate_period_progress(request):
    now = timezone.now()
    start_date = request.access_record.start_date if hasattr(request, 'access_record') else request.start_date
    end_date = request.access_record.end_date if hasattr(request, 'access_record') else request.end_date
    
    if not all([start_date, end_date]):
        return {'percentage': 0, 'is_expired': False, 'is_active': False}
    
    total_duration = (end_date - start_date).total_seconds()
    if total_duration <= 0:
        return {'percentage': 0, 'is_expired': False, 'is_active': False}
        
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
    start_date = request.access_record.start_date if hasattr(request, 'access_record') else request.start_date
    end_date = request.access_record.end_date if hasattr(request, 'access_record') else request.end_date
    
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

@register.filter
def calculate_request_progress(request):
    return calculate_period_progress(request)

@register.filter
def get_request_remaining_days(request):
    return get_remaining_days(request)

@register.filter
def user_in_owners(owners, user):
    """Перевіряє чи користувач є серед власників системи"""
    try:
        return owners.filter(cabinet_user__user=user).exists()
    except:
        return False

@register.filter
def user_in_administrators(administrators, user):
    """Перевіряє чи користувач є серед адміністраторів системи"""
    try:
        return administrators.filter(cabinet_user__user=user).exists()
    except:
        return False

@register.filter
def user_is_approver(approver, user):
    """Перевіряє чи користувач є цим approver"""
    try:
        return hasattr(user, 'cabinet') and user.cabinet == approver.cabinet_user
    except:
        return False 