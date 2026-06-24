from django.apps import AppConfig
from django.urls import path
from django.utils.translation import gettext_lazy as _


class AppRiskConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_risk'

    def ready(self):
        self._patch_admin_for_risk_guides()

    def _patch_admin_for_risk_guides(self):
        """Group all Risk Guide models into one 'Risk Guides – Settings' entry in admin."""
        from django.contrib import admin
        from django.urls import reverse

        from .admin_views import risk_guides_settings_view, RISK_GUIDE_MODEL_NAMES

        # Add URL for the combined Risk Guides settings page (under admin)
        original_get_urls = admin.site.get_urls

        def custom_get_urls():
            urlpatterns = [
                path(
                    'app_risk/risk-guides/',
                    admin.site.admin_view(risk_guides_settings_view),
                    name='app_risk_risk_guides',
                ),
            ] + original_get_urls()
            return urlpatterns

        admin.site.get_urls = custom_get_urls

        # In app list, replace the 3 Guide models with one "Risk Guides – Settings" entry
        original_get_app_list = admin.site.get_app_list

        def custom_get_app_list(request, app_label=None):
            app_list = original_get_app_list(request, app_label=app_label)
            for app in app_list:
                if app.get('app_label') != 'app_risk':
                    continue
                models = app.get('models') or []
                other = [m for m in models if m.get('object_name') not in RISK_GUIDE_MODEL_NAMES]
                guides_url = reverse('admin:app_risk_risk_guides')
                synthetic = {
                    'name': _('Risk Guides – Settings'),
                    'object_name': 'RiskGuidesSettings',
                    'model': None,
                    'admin_url': guides_url,
                    'add_url': None,
                    'perms': {'add': False, 'change': True, 'delete': False, 'view': True},
                }
                app['models'] = other + [synthetic]
            return app_list

        admin.site.get_app_list = custom_get_app_list
