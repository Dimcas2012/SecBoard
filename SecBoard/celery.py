# SecBoard/SecBoard/celery.py
import os
import sys
from celery import Celery

# Add the SecBoard directory to Python path (same as manage.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SECBOARD_DIR = os.path.join(BASE_DIR, 'SecBoard')

# Add SecBoard directory to Python path
if SECBOARD_DIR not in sys.path:
    sys.path.append(SECBOARD_DIR)

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SecBoard.settings')

# Create the Celery app
app = Celery('SecBoard')

# Import and use celeryconfig from this package (works under Gunicorn/any cwd)
from . import celeryconfig
app.config_from_object(celeryconfig)

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

if __name__ == '__main__':
    app.start()