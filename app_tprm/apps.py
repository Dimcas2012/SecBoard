from django.apps import AppConfig


class AppTprmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_tprm'

    def ready(self):
        from . import signals  # noqa: F401  # register signal handlers
