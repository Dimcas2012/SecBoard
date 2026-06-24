#  SecBoard\SecBoard\SecBoard\urls.py
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from django.http import HttpResponse
from . import views_i18n
from .sitemaps import sitemaps
from . import api_docs
from . import privacy_views


def robots_txt(request):
    """Serve robots.txt file"""
    content = """User-agent: *
Allow: /
Disallow: /secboard_admin/
Disallow: /media/private/
Disallow: /api/internal/
Disallow: /*?page=*
Disallow: /*?sort=*
Disallow: /search?*
Disallow: /app_cabinet/
Disallow: /auth/

# Allow important static resources
Allow: /static/
Allow: /media/public/

# Sitemap location
Sitemap: {}/sitemap.xml

# Crawl delay for bots
Crawl-delay: 1""".format(request.build_absolute_uri('/').rstrip('/'))
    return HttpResponse(content, content_type="text/plain")

admin.site.site_url = getattr(settings, 'PUBLIC_BASE_URL', 'https://localhost/')
admin.site.site_header = 'SecBoard Administration'  # Customize admin header
admin.site.site_title = 'SecBoard Admin Portal'  # Customize browser title



urlpatterns = [
    # SEO and crawling
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    
    # API Documentation for AI agents
    path('api/schema/', api_docs.api_schema, name='api_schema'),
    path('api/info/', api_docs.platform_info, name='platform_info'),
    
    # Non-translatable URLs
    path('i18n/setlang/', views_i18n.set_language, name='set_language'),
    path('service-status/', views_i18n.status_service, name='service_status'),

    # Updated admin URL
    path('secboard_admin/', admin.site.urls),  # Changed from 'admin/'

    # TinyMCE Editor URLs
    path('tinymce/', include('tinymce.urls')),

    # Public About page (canonical namespace for reverse('app_conf:…'))
    path('about/', include(('app_conf.urls', 'app_conf'), namespace='app_conf')),
    
    # Webhook endpoints (non-translatable)
    path('app_soc/webhook/', include('app_soc.webhook_urls')),
    path('app_integration/webhook/', include('app_integration.webhook_urls')),
    
    # API endpoints (non-translatable)
    path('app_soc/api/', include('app_soc.api_urls')),

    # Other non-translatable URL patterns can go here
]

urlpatterns += i18n_patterns(
    path('about/', include(('app_conf.urls', 'app_conf'), namespace='app_conf_i18n')),
    path('', include('app_cabinet.urls')),
    path('app_doc/', include('app_doc.urls')),
    path('app_risk/', include('app_risk.urls')),
    path('app_asset/', include('app_asset.urls')),
    path('app_std/', include('app_std.urls')),
    path('app_incident/', include('app_incident.urls')),
    path('app_keycert/', include('app_keycert.urls')),
    path('app_study/', include('app_study.urls')),
    path('app_cabinet/', include('app_cabinet.urls')),
    path('app_access/', include('app_access.urls')),
    path('app_ai/', include('app_ai.urls')),
    path('app_soc/', include('app_soc.urls')),
    path('app_gophish/', include('app_gophish.urls')),
    path('app_gdpr/', include('app_gdpr.urls')),
    path('app_compliance/', include('app_compliance.urls')),
    path('app_tprm/', include('app_tprm.urls')),
    path('app_cif/', include('app_cif.urls')),
    path('app_integration/', include('app_integration.urls')),
    
    # Privacy and Legal pages
    path('privacy-policy/', privacy_views.privacy_policy, name='privacy_policy'),
    path('cookie-policy/', privacy_views.cookie_policy, name='cookie_policy'),
    path('terms-of-service/', privacy_views.terms_of_service, name='terms_of_service'),
    
    prefix_default_language=True
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
