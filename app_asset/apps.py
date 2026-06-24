from django.apps import AppConfig


class AppAssetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_asset'

    def ready(self):
        import app_asset.signals  # noqa
