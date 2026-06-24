"""
SecBoard deployment credentials loader.

Reads configuration from environment variables and the project-root `.env` file.
Copy this file to `credential.py` on first setup (credential.py is gitignored):

    cp SecBoard/credential.example.py SecBoard/credential.py
    cp .env.example .env

See `.env.example` for all supported variables and documentation.
"""
import os as _os

_BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))


def _load_env_file():
    """Parse .env file from project root and populate os.environ (existing vars take priority)."""
    env_path = _os.path.join(_BASE_DIR, '.env')
    if not _os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            _os.environ.setdefault(key, value)


_load_env_file()


def _get(key, default=''):
    return _os.environ.get(key, default)


def _get_list(key, default=''):
    """Comma-separated env var → list of stripped non-empty strings."""
    raw = _get(key, default)
    if not raw:
        return []
    return [item.strip() for item in raw.split(',') if item.strip()]


def _get_bool(key, default='0'):
    return _get(key, default).lower() in ('1', 'true', 'yes')


def _get_int(key, default='0'):
    try:
        return int(_get(key, default))
    except (ValueError, TypeError):
        return int(default)


# ---------------------------------------------------------------------------
# Exported variables — names match exactly what settings.py imports.
# All values come from environment / .env; defaults are safe demo placeholders.
# ---------------------------------------------------------------------------

secret_key = _get('SECRET_KEY', 'django-insecure-change-me-in-env-file')

recaptcha_public_key = _get('RECAPTCHA_PUBLIC_KEY', '')
recaptcha_private_key = _get('RECAPTCHA_PRIVATE_KEY', '')

webhook_encryption_key = _get('WEBHOOK_ENCRYPTION_KEY', '')

debug = _get_bool('DEBUG', '0')

database = {
    'default': {
        'ENGINE': _get('DB_ENGINE', 'django.db.backends.mysql'),
        'NAME': _get('DB_NAME', 'secboard_db'),
        'USER': _get('DB_USER', 'secboard_user'),
        'PASSWORD': _get('DB_PASSWORD', ''),
        'HOST': _get('DB_HOST', 'localhost'),
        'PORT': _get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET time_zone = '+00:00'; SET NAMES 'utf8mb4' COLLATE 'utf8mb4_unicode_ci';",
        },
    }
}

allowed_hosts = _get_list('ALLOWED_HOSTS', '127.0.0.1,localhost')

csrf_trusted_origins = _get_list('CSRF_TRUSTED_ORIGINS', 'http://127.0.0.1:8000,http://localhost:8000')

cors_allowed_origins = _get_list('CORS_ALLOWED_ORIGINS', '')

cors_allowed_origin_regexes = _get_list('CORS_ALLOWED_ORIGIN_REGEXES', '')

redis_host = _get('REDIS_HOST', 'localhost')
redis_port = _get_int('REDIS_PORT', '6379')
redis_db = _get_int('REDIS_DB', '0')

timezone = _get('TIMEZONE', 'Europe/Kyiv')

public_base_url = _get('PUBLIC_BASE_URL', 'https://localhost')
default_from_email = _get('DEFAULT_FROM_EMAIL', 'noreply@localhost')
site_domain = _get('SITE_DOMAIN', 'localhost')
site_protocol = _get('SITE_PROTOCOL', 'https')

# Hint for some setup flows (not AUTH_USER_MODEL); override per deployment in .env
default_admin_username = _get('DEFAULT_ADMIN_USERNAME', 'admin@your.site.domain')
