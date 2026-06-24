#  SecBoard\SecBoard\app_keycert\urls.py
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views


urlpatterns = [


    path('keys-cert/', views.keys_cert, name='keys_cert'),
    path('guide/', views.keycert_guide, name='keycert_guide'),
    path('api/guide/translate/', views.keycert_guide_translate, name='keycert_guide_translate'),
    path('get-key-certs/', views.get_key_certs, name='get_key_certs'),
    path('get-key-cert/<int:key_cert_id>/', views.get_key_cert, name='get_key_cert'),
    path('add-key-cert/', views.add_key_cert, name='add_key_cert'),
    path('edit-key-cert/<int:key_cert_id>/', views.edit_key_cert, name='edit_key_cert'),
    path('delete-key-cert/<int:id>/', views.delete_key_cert, name='delete_key_cert'),
    path('api/owner-options/', views.get_keycert_owner_options, name='get_keycert_owner_options'),
    path('parse-certificate/',views.parse_certificate, name='parse_certificate'),
    path('send_reminder_now/', views.send_reminder_now, name='send_reminder_now'),
    path('actualize-key-cert/<int:key_cert_id>/', views.actualize_key_cert, name='actualize_key_cert'),
    path('get-key-cert-history/<int:key_cert_id>/', views.get_key_cert_history, name='get_key_cert_history'),

    path('check-services-status/', views.check_services_status, name='check_services_status'),



]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)