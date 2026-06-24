#  SecBoard\SecBoard\SecBoard\views_i18n.py
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import translate_url
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import check_for_language
from urllib.parse import urlparse
import json
import time
import os
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from redis import Redis
from django.contrib.auth.decorators import login_required
from SecBoard.celery import app


def _path_from_next_url(next_url):
    """Return URL path (with leading slash) from a path or absolute URL."""
    if not next_url:
        return '/'
    if '://' in next_url:
        return urlparse(next_url).path or '/'
    return next_url if next_url.startswith('/') else '/' + next_url


def _strip_language_prefix(path):
    for code, _ in settings.LANGUAGES:
        prefix = f'/{code}/'
        if path.startswith(prefix):
            return '/' + path[len(prefix):]
        if path == f'/{code}':
            return '/'
    return path


def _build_language_switched_url(next_url, language_code):
    """Switch language prefix on a path or absolute URL."""
    path = _path_from_next_url(next_url)
    path = _strip_language_prefix(path)
    if not path.startswith('/'):
        path = '/' + path
    translated = translate_url(path, language_code)
    lang_prefix = f'/{language_code}/'
    if translated == '/' or not translated.startswith(lang_prefix):
        translated = lang_prefix if translated == '/' else lang_prefix + translated.lstrip('/')
    return translated


@require_POST
def set_language(request):
    next_url = request.POST.get('next', request.GET.get('next'))
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = request.META.get('HTTP_REFERER')
        if not url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = '/'

    lang_code = request.POST.get('language', None)
    if lang_code and check_for_language(lang_code):
        next_trans = _build_language_switched_url(next_url, lang_code)
        response = HttpResponseRedirect(next_trans)
        translation.activate(lang_code)
        # Persist language in the user session for maximum stability
        if hasattr(request, 'session'):
            try:
                session_key = getattr(translation, 'LANGUAGE_SESSION_KEY', 'django_language')
                request.session[session_key] = lang_code
            except Exception:
                # In case sessions are not configured or unavailable, continue with cookie only
                pass
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME, lang_code,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
    else:
        response = HttpResponseRedirect(next_url or '/')

    return response

@csrf_exempt
@login_required
def status_service(request):
    """
    Direct service status check endpoint that completely bypasses Django's translation system.
    This function is defined at the project level to avoid app-specific middleware and translation issues.
    """
    try:
        # Check Redis status
        redis_client = Redis(host=settings.REDIS_HOST,
                            port=settings.REDIS_PORT,
                            db=settings.REDIS_DB)
        redis_status = redis_client.ping()
    except Exception as e:
        redis_status = False

    # Check Celery status
    try:
        from celery.app.control import Control
        control = Control(app=app)
        active_workers = control.inspect().active()
        celery_status = active_workers is not None and len(active_workers) > 0
    except Exception as e:
        celery_status = False

    # Check Beat status
    try:
        beat_status = False
        
        # Method 1: Check celerybeat-schedule files' last modified time
        beat_files = ['celerybeat-schedule.dat', 'celerybeat-schedule.dir', 'celerybeat-schedule.bak']
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        for filename in beat_files:
            file_path = os.path.join(base_dir, filename)
            if os.path.exists(file_path):
                # Check if file was modified in the last 5 minutes
                mod_time = os.path.getmtime(file_path)
                if (time.time() - mod_time) < 300:  # 300 seconds = 5 minutes
                    beat_status = True
                    break
        
        # Method 2: If file check didn't confirm, check for tasks
        if not beat_status:
            from django_celery_beat.models import PeriodicTask
            
            # Check if any task ran recently
            latest_task = PeriodicTask.objects.filter(
                enabled=True,
                last_run_at__isnull=False
            ).order_by('-last_run_at').first()

            if latest_task:
                # Check if any task ran in the last 5 minutes
                beat_status = latest_task.last_run_at > timezone.now() - timedelta(minutes=5)
            else:
                # Check for scheduled tasks
                has_scheduled_tasks = PeriodicTask.objects.filter(enabled=True).exists()
                beat_status = has_scheduled_tasks
                
        # Method 3: Try to ping the scheduler via Redis
        if not beat_status and redis_status:
            try:
                # Check if Beat has added a heartbeat key to Redis
                beat_heartbeat = redis_client.get('celery-beat-heartbeat')
                if beat_heartbeat:
                    last_heartbeat = float(beat_heartbeat)
                    # Check if heartbeat is within last minute
                    beat_status = (time.time() - last_heartbeat) < 60
            except:
                pass
    except Exception as e:
        beat_status = False

    # Create direct response with minimal processing
    response_data = {
        'celery_status': celery_status,
        'redis_status': redis_status,
        'beat_status': beat_status,
        'timestamp': timezone.now().isoformat()
    }
    
    # Bypass Django's translation system by direct string manipulation
    return HttpResponse(
        json.dumps(response_data),
        content_type='application/json'
    )

def raw_status_check():
    """
    Raw function that checks service status without any Django dependencies.
    This is called directly from middleware to bypass the entire Django request/response cycle.
    """
    try:
        # Check Redis status
        redis_client = Redis(host=settings.REDIS_HOST,
                            port=settings.REDIS_PORT,
                            db=settings.REDIS_DB)
        redis_status = redis_client.ping()
    except Exception:
        redis_status = False

    # Check Celery status
    try:
        from celery.app.control import Control
        control = Control(app=app)
        active_workers = control.inspect().active()
        celery_status = active_workers is not None and len(active_workers) > 0
    except Exception:
        celery_status = False

    # Check Beat status
    try:
        beat_status = False
        
        # Method 1: Check celerybeat-schedule files' last modified time
        beat_files = ['celerybeat-schedule.dat', 'celerybeat-schedule.dir', 'celerybeat-schedule.bak']
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        for filename in beat_files:
            file_path = os.path.join(base_dir, filename)
            if os.path.exists(file_path):
                # Check if file was modified in the last 5 minutes
                mod_time = os.path.getmtime(file_path)
                if (time.time() - mod_time) < 300:  # 300 seconds = 5 minutes
                    beat_status = True
                    break
        
        # Method 2: If file check didn't confirm, check for tasks
        if not beat_status:
            from django_celery_beat.models import PeriodicTask
            
            # Check if any task ran recently
            latest_task = PeriodicTask.objects.filter(
                enabled=True,
                last_run_at__isnull=False
            ).order_by('-last_run_at').first()

            if latest_task:
                # Check if any task ran in the last 5 minutes
                beat_status = latest_task.last_run_at > timezone.now() - timedelta(minutes=5)
            else:
                # Check for scheduled tasks
                has_scheduled_tasks = PeriodicTask.objects.filter(enabled=True).exists()
                beat_status = has_scheduled_tasks
                
        # Method 3: Try to ping the scheduler via Redis
        if not beat_status and redis_status:
            try:
                # Check if Beat has added a heartbeat key to Redis
                beat_heartbeat = redis_client.get('celery-beat-heartbeat')
                if beat_heartbeat:
                    last_heartbeat = float(beat_heartbeat)
                    # Check if heartbeat is within last minute
                    beat_status = (time.time() - last_heartbeat) < 60
            except:
                pass
    except Exception:
        beat_status = False

    # Return raw data
    return {
        'celery_status': celery_status,
        'redis_status': redis_status,
        'beat_status': beat_status,
        'timestamp': timezone.now().isoformat()
    }