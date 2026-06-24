from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.translation import get_language
from django.db.models import Q, Prefetch
from django.contrib.auth.models import User
from app_cabinet.models import CabinetUser
from .models import AccessRequest
import logging

logger = logging.getLogger(__name__)


@login_required
def user_available_access(request):
    """
    Сторінка для відображення активних доступів користувачів.
    Показує доступи, які:
    - Мають статус Request Status = 'approved' (погоджені)
    - Мають статус Admin Status = 'granted' (надані)
    - Період доступу активний (start_date <= сьогодні <= end_date або end_date = None)
    """
    try:
        current_language = get_language()[:2]
        today = timezone.now().date()
        
        # Фільтруємо активні доступи
        active_access_requests = AccessRequest.objects.filter(
            status='approved',  # Погоджені запити
            admin_status='granted',  # Надані доступи
            start_date__date__lte=today,  # Період почався
        ).filter(
            Q(end_date__isnull=True) |  # Безстроковий доступ
            Q(end_date__date__gte=today)  # Або період ще не завершився
        ).select_related(
            'requested_for',
            'company',
            'system',
            'access_record',
            'access_record__access_object',
            'requested_by'
        ).prefetch_related(
            'access_record__roles',
            'system__owners__cabinet_user__user',
            'system__administrators__cabinet_user__user',
            'request_approvers__cabinet_user__user'
        )
        
        # Застосовуємо фільтри
        user_filter = request.GET.get('user', '').strip()
        if user_filter:
            # Фільтруємо по імені користувача (Cabinet Users, Third Party)
            filter_conditions = Q(
                # Cabinet Users
                Q(requested_for__first_name__icontains=user_filter) |
                Q(requested_for__last_name__icontains=user_filter) |
                Q(requested_for__username__icontains=user_filter) |
                Q(requested_for__email__icontains=user_filter) |
                # Single Third Party
                Q(third_party_first_name__icontains=user_filter) |
                Q(third_party_last_name__icontains=user_filter) |
                Q(third_party_email__icontains=user_filter) |
                Q(third_party_organization__icontains=user_filter)
            )
            
            # Додаємо фільтрацію по JSON полях для множинних користувачів
            # Для PostgreSQL можна використовувати JSONField lookups
            try:
                # Фільтрація по JSON даних третіх сторін
                filter_conditions |= Q(third_party_users_data__icontains=user_filter)
                # Фільтрація по JSON даних кабінетних користувачів
                filter_conditions |= Q(requested_for_users_data__icontains=user_filter)
            except Exception:
                # Fallback для баз даних, які не підтримують JSON lookups
                pass
            
            active_access_requests = active_access_requests.filter(filter_conditions)
        
        active_access_requests = active_access_requests.order_by('-created_at')
        
        # Підготовка даних для шаблону
        access_data = []
        for access_request in active_access_requests:
            # Визначаємо тип користувача та обробляємо дані
            user_entries = []
            
            # Перевіряємо, чи це Third Party запит
            is_third_party = (
                access_request.third_party_first_name or 
                access_request.third_party_last_name or 
                access_request.third_party_users_data
            )
            
            if is_third_party:
                # Обробляємо Third Party користувачів
                if access_request.third_party_users_data:
                    # Множинні Third Party користувачі
                    try:
                        import json
                        third_party_data = access_request.third_party_users_data
                        if isinstance(third_party_data, str):
                            third_party_data = json.loads(third_party_data)
                        
                        if third_party_data and len(third_party_data) > 0:
                            for user_data in third_party_data:
                                user_entries.append({
                                    'user_type': 'third_party',
                                    'user_display_name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                                    'user_email': user_data.get('email', ''),
                                    'user_department': user_data.get('organization', ''),
                                    'user_position': '',
                                    'user_phone': user_data.get('phone', ''),
                                    'user_description': user_data.get('description', ''),
                                })
                    except (json.JSONDecodeError, TypeError, KeyError, AttributeError):
                        # Fallback до одного Third Party користувача
                        user_entries.append({
                            'user_type': 'third_party',
                            'user_display_name': f"{access_request.third_party_first_name} {access_request.third_party_last_name}".strip(),
                            'user_email': access_request.third_party_email,
                            'user_department': access_request.third_party_organization or '',
                            'user_position': '',
                            'user_phone': access_request.third_party_phone,
                            'user_description': access_request.third_party_description,
                        })
                else:
                    # Один Third Party користувач
                    user_entries.append({
                        'user_type': 'third_party',
                        'user_display_name': f"{access_request.third_party_first_name} {access_request.third_party_last_name}".strip(),
                        'user_email': access_request.third_party_email,
                        'user_department': access_request.third_party_organization or '',
                        'user_position': '',
                        'user_phone': access_request.third_party_phone,
                        'user_description': access_request.third_party_description,
                    })
            else:
                # Обробляємо Cabinet користувачів
                # Перевіряємо множинних Cabinet користувачів
                if hasattr(access_request, 'requested_for_users_data') and access_request.requested_for_users_data:
                    try:
                        import json
                        cabinet_users_data = access_request.requested_for_users_data
                        if isinstance(cabinet_users_data, str):
                            cabinet_users_data = json.loads(cabinet_users_data)
                        
                        if cabinet_users_data and len(cabinet_users_data) > 0:
                            for user_data in cabinet_users_data:
                                user_entries.append({
                                    'user_type': 'cabinet_user',
                                    'user_display_name': user_data.get('name', ''),
                                    'user_email': user_data.get('email', ''),
                                    'user_department': user_data.get('department', ''),
                                    'user_position': user_data.get('position', ''),
                                    'user_phone': '',
                                    'user_description': '',
                                })
                    except (json.JSONDecodeError, TypeError, KeyError, AttributeError):
                        pass
                
                # Якщо немає множинних користувачів або помилка, використовуємо основного користувача
                if not user_entries:
                    user_display_name = access_request.requested_for.get_full_name() or access_request.requested_for.username
                    user_email = access_request.requested_for.email
                    user_department = ''
                    user_position = ''
                    
                    # Спробуємо отримати дані Cabinet користувача
                    try:
                        cabinet_user = CabinetUser.objects.get(user=access_request.requested_for)
                        if cabinet_user.department:
                            user_department = cabinet_user.department.get_name(current_language) or ''
                        
                        if cabinet_user.position:
                            user_position = cabinet_user.position.get_name(current_language) or ''
                    except CabinetUser.DoesNotExist:
                        pass
                    
                    user_entries.append({
                        'user_type': 'cabinet_user',
                        'user_display_name': user_display_name,
                        'user_email': user_email,
                        'user_department': user_department,
                        'user_position': user_position,
                        'user_phone': '',
                        'user_description': '',
                    })
            
            # Отримуємо назви системи та об'єкта
            system_name = access_request.system.name  # InformationAsset має поле 'name'
            
            # Для об'єкта потрібно перевірити структуру моделі
            if hasattr(access_request.access_record.access_object, 'name'):
                if current_language == 'uk':
                    object_name = access_request.access_record.access_object.get_name() or access_request.access_record.access_object.name or ''
                else:
                    object_name = access_request.access_record.access_object.get_name() or access_request.access_record.access_object.name or ''
            else:
                # Fallback якщо немає локалізованих полів
                object_name = getattr(access_request.access_record.access_object, 'name', str(access_request.access_record.access_object))
            
            # Отримуємо ролі
            roles = []
            for role in access_request.access_record.roles.all():
                if current_language == 'uk':
                    role_name = role.get_name() or role.name or ''
                else:
                    role_name = role.get_name() or role.name or ''
                
                roles.append({
                    'id': role.id,
                    'name': role_name,
                    'color': role.color or '#6c757d'
                })
            
            # Розраховуємо прогрес періоду
            progress_info = calculate_period_progress(access_request.start_date.date(), access_request.end_date.date() if access_request.end_date else None, today)
            
            # Створюємо запис для кожного користувача
            for user_entry in user_entries:
                access_data.append({
                    'id': access_request.id,
                    'user_type': user_entry['user_type'],
                    'user_display_name': user_entry['user_display_name'],
                    'user_email': user_entry['user_email'],
                    'user_department': user_entry['user_department'],
                    'user_position': user_entry['user_position'],
                    'user_phone': user_entry.get('user_phone', ''),
                    'user_description': user_entry.get('user_description', ''),
                    'company_name': access_request.company.name,
                    'system_name': system_name,
                    'object_name': object_name,
                    'environment': access_request.environment,
                    'roles': roles,
                    'start_date': access_request.start_date,
                    'end_date': access_request.end_date,
                    'progress_info': progress_info,
                    'created_at': access_request.created_at,
                    'requested_by': access_request.requested_by.get_full_name() or access_request.requested_by.username,
                    # Додаткові дані для групових запитів
                    'is_third_party': user_entry['user_type'] == 'third_party',
                    'is_multiple_users': len(user_entries) > 1,
                    'total_users_count': len(user_entries),
                    'user_index': user_entries.index(user_entry) + 1,
                    'group_type': 'third_party' if user_entry['user_type'] == 'third_party' else 'cabinet_user',
                })
        
        context = {
            'access_data': access_data,
            'total_count': len(access_data),
            'current_language': current_language,
            'current_user_filter': user_filter,
        }
        
        return render(request, 'app_access/user_available_access.html', context)
        
    except Exception as e:
        logger.error(f"Error in user_available_access view: {e}")
        context = {
            'access_data': [],
            'total_count': 0,
            'error_message': str(e),
            'current_language': get_language()[:2],
        }
        return render(request, 'app_access/user_available_access.html', context)


def calculate_period_progress(start_date, end_date, today):
    """
    Розраховує прогрес періоду доступу
    """
    if not start_date:
        return {'status': 'unknown', 'percentage': 0, 'class': 'bg-secondary'}
    
    if end_date is None:
        # Безстроковий доступ
        if start_date <= today:
            return {'status': 'indefinite', 'percentage': 100, 'class': 'bg-info'}
        else:
            return {'status': 'future', 'percentage': 0, 'class': 'bg-warning'}
    
    if today < start_date:
        # Доступ ще не почався
        return {'status': 'future', 'percentage': 0, 'class': 'bg-warning'}
    elif today > end_date:
        # Доступ закінчився (не повинно бути в цьому списку, але на всякий випадок)
        return {'status': 'expired', 'percentage': 100, 'class': 'bg-danger'}
    else:
        # Активний доступ
        total_days = (end_date - start_date).days
        if total_days <= 0:
            return {'status': 'active', 'percentage': 100, 'class': 'bg-success'}
        
        elapsed_days = (today - start_date).days
        percentage = min(100, max(0, (elapsed_days / total_days) * 100))
        return {'status': 'active', 'percentage': percentage, 'class': 'bg-success'} 