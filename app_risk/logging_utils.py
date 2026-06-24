# app_risk/logging_utils.py
import logging
import json
import traceback
from datetime import datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from functools import wraps
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q

# Створюємо спеціальний логер для Risk Assessment
risk_logger = logging.getLogger('app_risk')

class RiskAssessmentLogger:
    """
    Клас для детального логування всіх дій в Risk Assessment модулі
    """
    
    @staticmethod
    def log_user_action(user, action, details=None, asset_id=None, request_path=None, level='INFO'):
        """
        Логування дій користувача
        """
        try:
            message_parts = [f"User: {user.username if user.is_authenticated else 'Anonymous'}"]
            message_parts.append(f"Action: {action}")
            
            if asset_id:
                message_parts.append(f"Asset ID: {asset_id}")
            
            if details:
                if isinstance(details, dict):
                    details_str = json.dumps(details, ensure_ascii=False, indent=2)
                else:
                    details_str = str(details)
                message_parts.append(f"Details: {details_str}")
            
            message = " | ".join(message_parts)
            
            # Логування в файл
            if hasattr(risk_logger, level.lower()):
                getattr(risk_logger, level.lower())(message)
            else:
                risk_logger.info(message)  # Fallback для невідомих рівнів
            
            # Логування в базу даних
            try:
                from .models import RiskAssessmentAuditLog
                from app_asset.models import InformationAsset
                
                # Визначаємо тип дії
                action_type = 'VIEW'
                if 'CREATE' in action.upper() or 'SAVE' in action.upper():
                    action_type = 'CREATE'
                elif 'UPDATE' in action.upper() or 'MODIFY' in action.upper():
                    action_type = 'UPDATE'
                elif 'DELETE' in action.upper():
                    action_type = 'DELETE'
                elif 'EXPORT' in action.upper():
                    action_type = 'EXPORT'
                elif 'ACCESS' in action.upper():
                    action_type = 'ACCESS'
                elif 'ERROR' in action.upper():
                    action_type = 'ERROR'
                elif 'SECURITY' in action.upper():
                    action_type = 'SECURITY'
                
                # Визначаємо рівень серйозності
                severity = 'LOW'
                if level.upper() == 'WARNING':
                    severity = 'MEDIUM'
                elif level.upper() == 'ERROR':
                    severity = 'HIGH'
                elif 'CRITICAL' in action.upper() or 'SECURITY' in action.upper():
                    severity = 'CRITICAL'
                
                # Знаходимо актив, якщо asset_id надано
                asset_obj = None
                if asset_id:
                    try:
                        asset_obj = InformationAsset.objects.filter(
                            Q(asset_id=asset_id) | Q(id=asset_id)
                        ).first()
                    except:
                        pass
                
                with transaction.atomic():
                    RiskAssessmentAuditLog.objects.create(
                        user=user if user and user.is_authenticated else None,
                        action_type=action_type,
                        action_name=action,
                        asset=asset_obj,
                        request_path=request_path,
                        additional_data=details,
                        severity=severity,
                        success=level.upper() != 'ERROR'
                    )
            except Exception as db_error:
                risk_logger.error(f"Failed to log to database: {str(db_error)}")
                
        except Exception as e:
            risk_logger.error(f"Error in log_user_action: {str(e)}")
    
    @staticmethod
    def log_data_access(user, data_type, asset_id=None, filters=None, request_path=None):
        """
        Логування доступу до даних
        """
        details = {
            'data_type': data_type,
            'timestamp': timezone.now().isoformat(),
            'filters': filters or {}
        }
        
        RiskAssessmentLogger.log_user_action(
            user=user,
            action=f"DATA_ACCESS_{data_type.upper()}",
            details=details,
            asset_id=asset_id,
            request_path=request_path,
            level='INFO'
        )
    
    @staticmethod
    def log_data_modification(user, operation, data_type, data_before=None, data_after=None, 
                            asset_id=None, request_path=None):
        """
        Логування модифікації даних
        """
        details = {
            'operation': operation,  # CREATE, UPDATE, DELETE
            'data_type': data_type,
            'timestamp': timezone.now().isoformat(),
            'data_before': data_before,
            'data_after': data_after
        }
        
        RiskAssessmentLogger.log_user_action(
            user=user,
            action=f"DATA_MODIFICATION_{operation}_{data_type.upper()}",
            details=details,
            asset_id=asset_id,
            request_path=request_path,
            level='WARNING'
        )
    
    @staticmethod
    def log_export_action(user, export_type, filters=None, record_count=None, request_path=None):
        """
        Логування експорту даних
        """
        details = {
            'export_type': export_type,
            'timestamp': timezone.now().isoformat(),
            'filters': filters or {},
            'record_count': record_count
        }
        
        RiskAssessmentLogger.log_user_action(
            user=user,
            action=f"EXPORT_{export_type.upper()}",
            details=details,
            request_path=request_path,
            level='WARNING'
        )
    
    @staticmethod
    def log_error(user, error_type, error_message, stack_trace=None, request_path=None, 
                  additional_context=None):
        """
        Логування помилок
        """
        details = {
            'error_type': error_type,
            'error_message': error_message,
            'timestamp': timezone.now().isoformat(),
            'stack_trace': stack_trace,
            'additional_context': additional_context or {}
        }
        
        RiskAssessmentLogger.log_user_action(
            user=user,
            action=f"ERROR_{error_type.upper()}",
            details=details,
            request_path=request_path,
            level='ERROR'
        )
    
    @staticmethod
    def log_security_event(user, event_type, details=None, request_path=None, severity='WARNING'):
        """
        Логування подій безпеки
        """
        security_details = {
            'event_type': event_type,
            'timestamp': timezone.now().isoformat(),
            'user_ip': getattr(user, 'ip_address', None),
            'user_agent': getattr(user, 'user_agent', None),
            'details': details or {}
        }
        
        RiskAssessmentLogger.log_user_action(
            user=user,
            action=f"SECURITY_{event_type.upper()}",
            details=security_details,
            request_path=request_path,
            level=severity
        )

def log_risk_action(action_type, data_type=None):
    """
    Декоратор для автоматичного логування дій
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = timezone.now()
            user = request.user if hasattr(request, 'user') else None
            request_path = request.path if hasattr(request, 'path') else None
            
            # Логування початку дії
            RiskAssessmentLogger.log_user_action(
                user=user,
                action=f"START_{action_type}",
                details={'start_time': start_time.isoformat()},
                request_path=request_path,
                level='DEBUG'
            )
            
            try:
                # Виконання оригінальної функції
                result = view_func(request, *args, **kwargs)
                
                # Логування успішного завершення
                end_time = timezone.now()
                duration = (end_time - start_time).total_seconds()
                
                RiskAssessmentLogger.log_user_action(
                    user=user,
                    action=f"SUCCESS_{action_type}",
                    details={
                        'duration_seconds': duration,
                        'end_time': end_time.isoformat()
                    },
                    request_path=request_path,
                    level='INFO'
                )
                
                return result
                
            except Exception as e:
                # Логування помилки
                end_time = timezone.now()
                duration = (end_time - start_time).total_seconds()
                
                RiskAssessmentLogger.log_error(
                    user=user,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    stack_trace=traceback.format_exc(),
                    request_path=request_path,
                    additional_context={
                        'action_type': action_type,
                        'duration_seconds': duration,
                        'args': str(args),
                        'kwargs': str(kwargs)
                    }
                )
                
                # Повторно викидаємо помилку
                raise
        
        return wrapper
    return decorator

def log_data_access_decorator(data_type):
    """
    Декоратор для логування доступу до даних
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user if hasattr(request, 'user') else None
            request_path = request.path if hasattr(request, 'path') else None
            
            # Збираємо фільтри з GET параметрів
            filters = dict(request.GET.items()) if hasattr(request, 'GET') else {}
            asset_id = filters.get('asset_id')
            
            # Логування доступу до даних
            RiskAssessmentLogger.log_data_access(
                user=user,
                data_type=data_type,
                asset_id=asset_id,
                filters=filters,
                request_path=request_path
            )
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator

class AuditMiddleware:
    """
    Middleware для автоматичного логування всіх запитів до Risk Assessment
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Перевіряємо, чи це запит до Risk Assessment модуля
        if request.path.startswith('/app_risk/') or 'risk' in request.path.lower():
            start_time = timezone.now()
            
            # Управління сесіями користувачів
            self.manage_user_session(request, start_time)
            
            # Логування запиту
            # RiskAssessmentLogger.log_user_action(
            #     user=request.user if hasattr(request, 'user') else None,
            #     action="HTTP_REQUEST",
            #     details={
            #         'method': request.method,
            #         'path': request.path,
            #         'query_params': dict(request.GET.items()),
            #         'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            #         'ip_address': self.get_client_ip(request),
            #         'timestamp': start_time.isoformat()
            #     },
            #     request_path=request.path,
            #     level='DEBUG'
            # )
        
        response = self.get_response(request)
        
        # Логування відповіді для Risk Assessment запитів
        if request.path.startswith('/app_risk/') or 'risk' in request.path.lower():
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            RiskAssessmentLogger.log_user_action(
                user=request.user if hasattr(request, 'user') else None,
                action="HTTP_RESPONSE",
                details={
                    'status_code': response.status_code,
                    'duration_seconds': duration,
                    'response_size': len(response.content) if hasattr(response, 'content') else 0,
                    'timestamp': end_time.isoformat()
                },
                request_path=request.path,
                level='WARNING'
            )
        
        return response
    
    def manage_user_session(self, request, start_time):
        """Управління сесіями користувачів"""
        try:
            from .models import RiskAssessmentSession
            
            if hasattr(request, 'user') and request.user.is_authenticated:
                session_key = request.session.session_key
                if not session_key:
                    request.session.create()
                    session_key = request.session.session_key
                
                # Отримуємо або створюємо сесію
                session, created = RiskAssessmentSession.objects.get_or_create(
                    user=request.user,
                    session_key=session_key,
                    defaults={
                        'ip_address': self.get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'is_active': True
                    }
                )
                
                # Оновлюємо лічильник дій
                if not created:
                    session.actions_count += 1
                    session.save()
                
        except Exception as e:
            risk_logger.error(f"Error managing user session: {str(e)}")
    
    def get_client_ip(self, request):
        """Отримання IP адреси клієнта"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip 