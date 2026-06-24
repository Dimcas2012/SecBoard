from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class AppConfConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_conf'
    verbose_name = _('config')
