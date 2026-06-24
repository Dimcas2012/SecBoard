from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('incident_register/', views.incident_register, name='incident_register'),
    path('incident_register/guide/', views.incident_register_guide, name='incident_register_guide'),
    path('incident_register/api/guide/translate/', views.incident_register_guide_translate, name='incident_register_guide_translate'),
    path('incident_add/', views.incident_add, name='incident_add'),
    path('incident_detail/<int:incident_id>/', views.incident_detail, name='incident_detail'),
    path('incident_edit/<int:incident_id>/', views.incident_edit, name='incident_edit'),
    path('incident_delete/<int:incident_id>/', views.incident_delete, name='incident_delete'),
    path('file_delete/<int:file_id>/', views.file_delete, name='file_delete'),
    path('delete_file_ajax/', views.delete_file_ajax, name='delete_incident_file'),
    path('delete_main_incident_file/', views.delete_main_incident_file, name='delete_main_incident_file'),
    path('export_incidents_excel/', views.export_incidents_excel, name='export_incidents_excel'),
    # Email functionality
    path('get_incident_email_template/', views.get_incident_email_template, name='get_incident_email_template'),
    path('send_incident_email/', views.send_incident_email, name='send_incident_email'),
    path('test_mail_account/', views.test_mail_account, name='test_mail_account'),
    path('get_company_users/', views.get_company_users, name='get_incident_company_users'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)