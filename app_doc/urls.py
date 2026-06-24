#  SecBoard\SecBoard\app_doc\urls.py
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static


from . import views


# app_name = 'app_doc'


urlpatterns = [
    path('reg_docs/', views.reg_docs, name='reg_docs'),
    path('reg_docs/guide/', views.reg_docs_guide, name='reg_docs_guide'),
    path('reg_docs/api/guide/translate/', views.reg_docs_guide_translate, name='reg_docs_guide_translate'),
    path('add_register_doc/', views.add_register_doc, name='add_register_doc'),
    path('delete_register_doc/<int:doc_id>/', views.delete_register_doc, name='delete_register_doc'),
    path('get-register-doc/<int:doc_id>/', views.get_register_doc, name='get_register_doc'),
    path('edit-register-doc/<int:doc_id>/', views.edit_register_doc, name='edit_register_doc'),
    path('register-doc/<int:doc_id>/related-docs/', views.get_related_docs, name='get_related_docs'),
    path('reg-docs/<int:doc_id>/html/', views.get_reg_doc_html, name='get_reg_doc_html'),
    path('approve-document/<int:doc_id>/', views.approve_document, name='approve_document'),
    path('document-approvals/<int:doc_id>/', views.document_approvals, name='document_approvals'),
    path('acknowledge-document/<int:doc_id>/', views.acknowledge_document, name='acknowledge_document'),
    path('get-file/<int:doc_id>/', views.get_file_content, name='get_file_content'),
    path('protected-file/<int:doc_id>/', views.protected_file_download, name='protected_file_download'),

    path('reg_docs/get_company_cabinet_users/', views.get_company_cabinet_users, name='get_company_cabinet_users'),
    path('reg_docs/get_company_groups/', views.get_company_groups, name='get_company_groups'),
    path('reg_docs/get_company_documents/', views.get_company_documents, name='get_company_documents'),
    path('reg_docs/get_company_register_docs/', views.get_company_register_docs, name='get_company_register_docs'),
    path('reg_docs/get_company_related_docs/', views.get_company_related_docs, name='get_company_related_docs'),

    path('related-docs/', views.related_docs, name='related_docs'),
    path('related-docs/list/', views.related_docs_list, name='related_docs_list'),
    path('related-docs/add/', views.add_related_doc, name='add_related_doc'),
    path('related-docs/<int:doc_id>/', views.get_related_doc, name='get_related_doc'),
    path('related-docs/<int:doc_id>/edit/', views.edit_related_doc, name='edit_related_doc'),
    path('related-docs/<int:doc_id>/delete/', views.delete_related_doc, name='delete_related_doc'),
    path('related-docs/<int:doc_id>/html/', views.get_related_doc_html, name='get_related_doc_html'),

    # Legislative Documents URLs
    path('legislative-docs/', views.legislative_docs, name='legislative_docs'),
    path('legislative-docs/add/', views.add_legislative_doc, name='add_legislative_doc'),
    path('legislative-docs/<int:doc_id>/', views.get_legislative_doc, name='get_legislative_doc'),
    path('legislative-docs/<int:doc_id>/edit/', views.edit_legislative_doc, name='edit_legislative_doc'),
    path('legislative-docs/<int:doc_id>/delete/', views.delete_legislative_doc, name='delete_legislative_doc'),
    path('legislative-docs/<int:doc_id>/html/', views.get_legislative_doc_html, name='get_legislative_doc_html'),
    path('legislative-docs/<int:doc_id>/pdf/', views.download_legislative_doc_pdf, name='download_legislative_doc_pdf'),
    path('legislative-docs/guide/', views.legislative_docs_guide, name='legislative_docs_guide'),
    path('legislative-docs/api/guide/translate/', views.legislative_docs_guide_translate, name='legislative_docs_guide_translate'),

    # AI Document Parsing URLs
    path('parse-document-ai/', views.parse_document_ai, name='parse_document_ai'),
    path('get-ai-models/', views.get_ai_models, name='get_ai_models'),
    path('check-ai-settings-version/', views.check_ai_settings_version, name='check_ai_settings_version'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)