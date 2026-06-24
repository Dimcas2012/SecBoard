# SecBoard/app_std/urls.py
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.views.decorators.csrf import csrf_exempt


urlpatterns = [
    # PCI DSS URLs
    path('pcidss/', views.pcidss_requirements, name='pcidss_requirements'),
    path('edit_pcidss_requirement/<int:requirement_id>/', views.edit_pcidss_requirement,
         name='edit_pcidss_requirement'),
    path('get_pcidss_requirement/<int:requirement_id>/', views.get_pcidss_requirement, name='get_pcidss_requirement'),
    path('translate_pcidss_fields/', views.translate_pcidss_fields, name='translate_pcidss_fields'),
    path('export-pcidss-requirements/', views.export_pcidss_requirements, name='export_pcidss_requirements'),
    path('import-pcidss-requirements/', views.import_pcidss_requirements, name='import_pcidss_requirements'),
    path('add-pcidss-requirement/', views.add_pcidss_requirement, name='add_pcidss_requirement'),
    path('delete-pcidss-requirements/', views.delete_pcidss_requirements, name='delete_pcidss_requirements'),
    
    # PCI DSS AI Search URLs
    path('search-pcidss-with-google/', views.search_pcidss_with_google, name='search_pcidss_with_google'),
    path('search-pcidss-with-claude/', views.search_pcidss_with_claude, name='search_pcidss_with_claude'),
    path('search-pcidss-with-deepseek/', views.search_pcidss_with_deepseek, name='search_pcidss_with_deepseek'),

    # ISO 27002 URLs
    path('iso27002/', views.iso27002_controls, name='iso27002_controls'),
    path('edit-iso-control/<int:control_id>/', views.edit_iso_control, name='edit_iso_control'),
    path('get-iso-control/<int:control_id>/', views.get_iso_control, name='get_iso_control'),
    path('translate-iso27002-fields/', views.translate_iso27002_fields, name='translate_iso27002_fields'),
    path('export-iso27002-controls/', views.export_iso27002_controls, name='export_iso27002_controls'),
    path('import-iso27002-controls/', views.import_iso27002_controls, name='import_iso27002_controls'),
    path('add-iso-control/', views.add_iso_control, name='add_iso_control'),
    path('delete-iso27002-controls/', views.delete_iso27002_controls, name='delete_iso27002_controls'),
    
    # ISO 27002 AI Search URLs
    path('search-iso27002-with-google/', csrf_exempt(views.search_iso27002_with_google), name='search_iso27002_with_google'),
    path('search-iso27002-with-claude/', csrf_exempt(views.search_iso27002_with_claude), name='search_iso27002_with_claude'),
    path('search-iso27002-with-deepseek/', csrf_exempt(views.search_iso27002_with_deepseek), name='search_iso27002_with_deepseek'),

    # PCI DSS Documents
    path('pcidss/documents/', views.pcidss_documents, name='pcidss_documents'),
    path('pcidss/documents/upload/', csrf_exempt(views.upload_pcidss_document), name='upload_pcidss_document'),
    path('pcidss/documents/view/<int:document_id>/', views.view_pcidss_document, name='view_pcidss_document'),
    path('pcidss/documents/delete/<int:document_id>/', csrf_exempt(views.delete_pcidss_document), name='delete_pcidss_document'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)