from django.conf import settings
from django.urls import translate_url
from django.utils import translation
from django.utils.translation import check_for_language


def get_configured_language_codes():
    return {code for code, _ in settings.LANGUAGES}


def get_user_preferred_language(user):
    if not user or not user.is_authenticated:
        return ''
    try:
        cabinet_user = user.cabinet
    except Exception:
        return ''
    language = (cabinet_user.preferred_language or '').strip()
    if language and check_for_language(language):
        return language
    return ''


def apply_user_language(request, language_code, response=None):
    """Persist and activate a language for the current request (and optional response)."""
    if not language_code or not check_for_language(language_code):
        return response

    translation.activate(language_code)
    request.LANGUAGE_CODE = language_code

    if hasattr(request, 'session'):
        session_key = getattr(translation, 'LANGUAGE_SESSION_KEY', 'django_language')
        request.session[session_key] = language_code

    if response is not None:
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language_code,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
    return response


def build_language_prefixed_url(path, language_code):
    if not path:
        path = '/'
    if not language_code or not check_for_language(language_code):
        return path
    translated = translate_url(path, language_code)
    lang_prefix = f'/{language_code}/'
    if translated == '/' or not translated.startswith(lang_prefix):
        translated = lang_prefix if translated == '/' else lang_prefix + translated.lstrip('/')
    return translated


def apply_user_language_from_profile(request, user):
    language = get_user_preferred_language(user)
    if language:
        apply_user_language(request, language)
    return language
