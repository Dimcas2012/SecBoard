"""
Security utilities for Quiz Results and Access Control
Prevents IDOR vulnerabilities and enforces row-level security
"""

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.http import Http404
from functools import wraps
import logging
import uuid
from .models import Quiz, QuizAttempt, AccessQuiz
from app_cabinet.models import CabinetUser
from app_conf.models import Company

logger = logging.getLogger(__name__)


class QuizSecurityManager:
    """Centralized security manager for quiz-related operations"""
    
    @staticmethod
    def get_user_accessible_companies(user):
        """Get companies that a user can access based on their groups"""
        if not user.is_authenticated:
            return Company.objects.none()
            
        if user.is_superuser:
            return Company.objects.all()
        
        user_groups = user.groups.all()
        # Get companies from AccessQuiz where has_access_to_results is True
        access_quiz_entries = AccessQuiz.objects.filter(
            group__in=user_groups,
            has_access_to_results=True
        ).prefetch_related('companies')
        
        # Collect all companies from these entries
        allowed_company_ids = set()
        for entry in access_quiz_entries:
            company_ids = entry.companies.values_list('id', flat=True)
            allowed_company_ids.update(company_ids)
        
        return Company.objects.filter(id__in=allowed_company_ids)
    
    @staticmethod
    def can_view_quiz_results(user, target_user=None, company=None):
        """
        Check if a user can view quiz results
        
        Args:
            user: The requesting user
            target_user: The user whose results are being viewed (optional)
            company: The company context (optional)
            
        Returns:
            bool: True if access is allowed
        """
        if not user.is_authenticated:
            return False
            
        # Users can always view their own results
        if target_user and user == target_user:
            return True
            
        # Check company-based access
        accessible_companies = QuizSecurityManager.get_user_accessible_companies(user)
        
        if target_user:
            try:
                target_cabinet_user = CabinetUser.objects.get(user=target_user)
                if target_cabinet_user.company not in accessible_companies:
                    logger.warning(
                        f"User {user.username} attempted to access quiz results "
                        f"for user {target_user.username} from unauthorized company"
                    )
                    return False
            except CabinetUser.DoesNotExist:
                return False
                
        if company and company not in accessible_companies:
            return False
            
        return True
    
    @staticmethod
    def get_filtered_quiz_results(user):
        """
        Get quiz results filtered by user's access permissions
        Implements row-level security
        """
        accessible_companies = QuizSecurityManager.get_user_accessible_companies(user)
        
        if not accessible_companies.exists():
            return CabinetUser.objects.none(), []
        
        # Filter users by accessible companies
        cabinet_users = CabinetUser.objects.filter(
            company__in=accessible_companies
        ).prefetch_related('user', 'company')
        
        # Get accessible quizzes
        all_quizzes = Quiz.objects.all().prefetch_related(
            'companies', 'cabinet_groups', 'cabinet_users'
        )
        accessible_quizzes = []
        
        for quiz in all_quizzes:
            if (quiz.companies.filter(id__in=accessible_companies).exists() or
                quiz.cabinet_groups.filter(company__in=accessible_companies).exists() or
                quiz.cabinet_users.filter(company__in=accessible_companies).exists()):
                accessible_quizzes.append(quiz)
        
        return cabinet_users, accessible_quizzes
    
    @staticmethod
    def validate_quiz_access(user, quiz_id):
        """
        Validate that a user can access a specific quiz
        Raises PermissionDenied if access is not allowed
        """
        try:
            quiz = get_object_or_404(Quiz, id=quiz_id)
        except Http404:
            logger.warning(f"User {user.username} attempted to access non-existent quiz {quiz_id}")
            raise
            
        if not quiz.has_user_access(user):
            logger.warning(
                f"User {user.username} attempted unauthorized access to quiz {quiz_id}"
            )
            raise PermissionDenied("You do not have permission to access this quiz")
            
        return quiz
    
    @staticmethod
    def validate_attempt_access(user, attempt_id):
        """
        Validate that a user can access a specific quiz attempt
        Users can only access their own attempts or attempts from their accessible companies
        """
        try:
            attempt = get_object_or_404(QuizAttempt, id=attempt_id)
        except Http404:
            logger.warning(f"User {user.username} attempted to access non-existent attempt {attempt_id}")
            raise
            
        # Users can always access their own attempts
        if attempt.user == user:
            return attempt
            
        # Check if user can access other users' attempts based on company permissions
        if not QuizSecurityManager.can_view_quiz_results(user, attempt.user):
            logger.warning(
                f"User {user.username} attempted unauthorized access to "
                f"quiz attempt {attempt_id} by user {attempt.user.username}"
            )
            raise PermissionDenied("You do not have permission to access this quiz attempt")
            
        return attempt


def require_quiz_results_access(view_func):
    """
    Decorator to ensure user has access to quiz results functionality
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required")
            
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
            
        user_groups = request.user.groups.all()
        has_access = AccessQuiz.objects.filter(
            group__in=user_groups,
            has_access_to_results=True
        ).exists()
        
        if not has_access:
            logger.warning(
                f"User {request.user.username} attempted to access quiz results "
                "without proper permissions"
            )
            raise PermissionDenied("You do not have permission to view quiz results")
            
        return view_func(request, *args, **kwargs)
    return wrapper


def require_quiz_access(view_func):
    """
    Decorator to validate quiz access using quiz_id parameter
    """
    @wraps(view_func)
    def wrapper(request, quiz_id, *args, **kwargs):
        QuizSecurityManager.validate_quiz_access(request.user, quiz_id)
        return view_func(request, quiz_id, *args, **kwargs)
    return wrapper


def require_attempt_access(view_func):
    """
    Decorator to validate quiz attempt access using attempt_id parameter
    """
    @wraps(view_func)
    def wrapper(request, attempt_id, *args, **kwargs):
        QuizSecurityManager.validate_attempt_access(request.user, attempt_id)
        return view_func(request, attempt_id, *args, **kwargs)
    return wrapper


def generate_secure_token():
    """Generate a cryptographically secure token for sensitive operations"""
    return str(uuid.uuid4())


class QuizResultsAuditLogger:
    """Audit logging for quiz results access"""
    
    @staticmethod
    def log_access(user, action, target_user=None, quiz_id=None, attempt_id=None, 
                  ip_address=None, details=None):
        """
        Log quiz results access for security monitoring
        
        Args:
            user: The user performing the action
            action: Type of action (view_results, export_results, etc.)
            target_user: User whose data is being accessed (if different)
            quiz_id: Quiz ID being accessed
            attempt_id: Attempt ID being accessed
            ip_address: IP address of the request
            details: Additional details about the action
        """
        log_entry = {
            'user': user.username,
            'action': action,
            'target_user': target_user.username if target_user else None,
            'quiz_id': quiz_id,
            'attempt_id': attempt_id,
            'ip_address': ip_address,
            'details': details or {}
        }
        
        if target_user and target_user != user:
            # Log cross-user access
            logger.warning(
                f"AUDIT: User {user.username} accessed {action} for user {target_user.username} "
                f"(Quiz: {quiz_id}, Attempt: {attempt_id}, IP: {ip_address})"
            )
        else:
            logger.info(
                f"AUDIT: User {user.username} performed {action} "
                f"(Quiz: {quiz_id}, Attempt: {attempt_id}, IP: {ip_address})"
            )


def get_client_ip(request):
    """Get the real client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip 