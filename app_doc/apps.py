from django.apps import AppConfig
from django.urls import path
from django.utils.translation import gettext_lazy as _


class AppDocConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_doc'

    def ready(self):
        self._patch_admin_for_doc_guides()

    def _patch_admin_for_doc_guides(self):
        """Group all Doc Guide models into one 'Doc Guides – Settings' entry in admin."""
        from django.contrib import admin
        from django.urls import reverse

        from .admin_views import doc_guides_settings_view, DOC_GUIDE_MODEL_NAMES

        # Add URL for the combined Doc Guides settings page (under admin)
        original_get_urls = admin.site.get_urls

        def custom_get_urls():
            urlpatterns = [
                path(
                    'app_doc/doc-guides/',
                    admin.site.admin_view(doc_guides_settings_view),
                    name='app_doc_doc_guides',
                ),
            ] + original_get_urls()
            return urlpatterns

        admin.site.get_urls = custom_get_urls

        # In app list, replace the Guide models with one "Doc Guides – Settings" entry
        original_get_app_list = admin.site.get_app_list

        def custom_get_app_list(request, app_label=None):
            app_list = original_get_app_list(request, app_label=app_label)
            for app in app_list:
                if app.get('app_label') != 'app_doc':
                    continue
                models = app.get('models') or []
                other = [m for m in models if m.get('object_name') not in DOC_GUIDE_MODEL_NAMES]
                guides_url = reverse('admin:app_doc_doc_guides')
                synthetic = {
                    'name': _('Doc Guides – Settings'),
                    'object_name': 'DocGuidesSettings',
                    'model': None,
                    'admin_url': guides_url,
                    'add_url': None,
                    'perms': {'add': False, 'change': True, 'delete': False, 'view': True},
                }
                app['models'] = other + [synthetic]
            return app_list

        admin.site.get_app_list = custom_get_app_list
