from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import set_language
from django.contrib import admin

urlpatterns = [
    path('i18n/setlang/', set_language, name='set_language'),
    path('secboard_admin/', admin.site.urls),
]

urlpatterns += i18n_patterns(
    path('app_access/', include('app_access.urls')),  # Змінюємо префікс на app_access
    path('app_asset/', include('app_asset.urls')),
    prefix_default_language=False
) 