# app_cabinet/middleware.py
from django.utils import timezone
from django.utils import translation
from .models import UserSession, UserActivity
from .language_utils import (
    apply_user_language,
    apply_user_language_from_profile,
    get_user_preferred_language,
)
import uuid


def _request_has_language_prefix(request):
    """True when the URL already specifies a language (e.g. /en/..., /uk/...)."""
    return bool(translation.get_language_from_path(request.path_info))


class UserPreferredLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Do not override LocaleMiddleware: URL prefix must win over profile preference.
        if request.user.is_authenticated and not _request_has_language_prefix(request):
            apply_user_language_from_profile(request, request.user)

        response = self.get_response(request)

        if request.user.is_authenticated and not _request_has_language_prefix(request):
            language = get_user_preferred_language(request.user)
            if language:
                apply_user_language(request, language, response)

        return response



class UserSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            session_key = request.session.session_key or request.session.create()
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get(
                'REMOTE_ADDR')

            # Fix for duplicate sessions - handle case where multiple sessions exist
            try:
                # First, try to get an existing session
                sessions = UserSession.objects.filter(
                    session_key=session_key
                )
                
                if sessions.count() > 1:
                    # If multiple sessions exist, keep the most recent one and delete others
                    most_recent = sessions.order_by('-login_time').first()
                    sessions.exclude(id=most_recent.id).delete()
                    session = most_recent
                    created = False
                elif sessions.count() == 1:
                    # If exactly one session exists, use it
                    session = sessions.first()
                    created = False
                else:
                    # If no session exists, create one
                    session = UserSession.objects.create(
                        session_key=session_key,
                        user=request.user,
                        ip_address=ip_address,
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
                    created = True
                
            except Exception as e:
                # As a fallback, create a new session with a unique session key
                unique_key = f"{session_key}_{uuid.uuid4().hex[:8]}"
                session = UserSession.objects.create(
                    session_key=unique_key,
                    user=request.user,
                    ip_address=ip_address,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                created = True

            if not created:
                session.ip_address = ip_address
                session.user_agent = request.META.get('HTTP_USER_AGENT', '')
                session.save()

            # Track page views except static/media
            if not any(request.path.startswith(prefix) for prefix in ['/static/', '/media/']):
                UserActivity.objects.create(
                    user=request.user,
                    session=session,
                    action='view_page',
                    url=request.path,
                    details={'method': request.method}
                )

        return self.get_response(request)


def track_user_activity(user, session, action, details=None, url=None):
    UserActivity.objects.create(
        user=user,
        session=session,
        action=action,
        details=details or {},
        url=url or ''
    )


def track_user_logout(user):
    try:
        session = UserSession.objects.filter(
            user=user,
            logout_time__isnull=True
        ).latest('login_time')

        session.logout_time = timezone.now()
        session.save()

        track_user_activity(
            user=user,
            session=session,
            action='logout',
            details={'logout_type': 'normal'}
        )
    except UserSession.DoesNotExist:
        pass