from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AppIntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_integration'
    verbose_name = _('Integrations')
