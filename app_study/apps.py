#  SecBoard\SecBoard\app_study\apps.py
from django.apps import AppConfig
from django.urls import path
from django.utils.translation import gettext_lazy as _


class AppStudyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_study'
    verbose_name = _('study')

    def ready(self):
        """Import signals when the app is ready"""
        import app_study.signals
        self._patch_admin_for_study_guides()

    def _patch_admin_for_study_guides(self):
        """Group all Study Guide models into one 'Study Guides – Settings' entry in admin."""
        from django.contrib import admin
        from django.urls import reverse

        from .admin_views import study_guides_settings_view, STUDY_GUIDE_MODEL_NAMES

        # Add URL for the combined Study Guides settings page (under admin)
        original_get_urls = admin.site.get_urls

        def custom_get_urls():
            urlpatterns = [
                path(
                    'app_study/study-guides/',
                    admin.site.admin_view(study_guides_settings_view),
                    name='app_study_study_guides',
                ),
            ] + original_get_urls()
            return urlpatterns

        admin.site.get_urls = custom_get_urls

        # In app list, replace the 2 Guide models with one "Study Guides – Settings" entry
        original_get_app_list = admin.site.get_app_list

        def custom_get_app_list(request, app_label=None):
            app_list = original_get_app_list(request, app_label=app_label)
            for app in app_list:
                if app.get('app_label') != 'app_study':
                    continue
                models = app.get('models') or []
                other = [m for m in models if m.get('object_name') not in STUDY_GUIDE_MODEL_NAMES]
                guides_url = reverse('admin:app_study_study_guides')
                synthetic = {
                    'name': _('Study Guides – Settings'),
                    'object_name': 'StudyGuidesSettings',
                    'model': None,
                    'admin_url': guides_url,
                    'add_url': None,
                    'perms': {'add': False, 'change': True, 'delete': False, 'view': True},
                }
                app['models'] = other + [synthetic]
            return app_list

        admin.site.get_app_list = custom_get_app_list
