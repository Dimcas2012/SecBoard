#  SecBoard\SecBoard\app_suib\urls.py
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.i18n import JavaScriptCatalog
from . import views
from .views import set_user_timezone

# app_name = 'app_suib'


urlpatterns = [

    path('error/', views.error_page, name='error_page'),
    path('api-auth/', include('rest_framework.urls')),
    path('get_server_time/', views.get_server_time, name='get_server_time'),
    path('set_user_timezone/', set_user_timezone, name='set_user_timezone'),


]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)