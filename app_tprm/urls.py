from django.urls import path
from . import views

app_name = 'app_tprm'

urlpatterns = [
    path('', views.tprm_dashboard, name='dashboard'),
    path('guide/', views.tprm_guide, name='tprm_guide'),
    path('api/guide/translate/', views.tprm_guide_translate, name='tprm_guide_translate'),
    path('vendors/', views.vendor_list, name='vendor_list'),
    path('vendors/add/', views.vendor_add, name='vendor_add'),
    path('vendors/<int:pk>/', views.vendor_detail, name='vendor_detail'),
    path('vendors/<int:pk>/edit/', views.vendor_edit, name='vendor_edit'),
    path('vendors/<int:pk>/delete/', views.vendor_delete, name='vendor_delete'),
    path('vendors/<int:pk>/actualize/', views.actualize_vendor, name='vendor_actualize'),
    path('vendors/<int:pk>/history/', views.get_vendor_history, name='get_vendor_history'),
    path('api/tprm/owners/all/', views.get_all_tprm_owners, name='get_all_tprm_owners'),
    path('vendors/export-xlsx/', views.export_vendors_xlsx, name='export_vendors_xlsx'),
    path('vendors/import-xlsx/', views.import_vendors_xlsx, name='import_vendors_xlsx'),
    path('vendors/import-template-xlsx/', views.vendor_import_template_xlsx, name='vendor_import_template_xlsx'),
    
    # Vendor Documents
    path('vendors/<int:vendor_pk>/documents/add/', views.vendor_document_add, name='vendor_document_add'),
    path('documents/<int:pk>/delete/', views.vendor_document_delete, name='vendor_document_delete'),
    path('vendors/<int:vendor_pk>/documents/bulk-delete/', views.vendor_document_bulk_delete, name='vendor_document_bulk_delete'),
    path('assessments/add/', views.assessment_add, name='assessment_add'),
    path('reports/', views.reports, name='reports'),
    
    # Questionnaires
    path('questionnaires/', views.questionnaire_list, name='questionnaire_list'),
    path('questionnaires/start/<int:vendor_pk>/<int:template_pk>/', views.questionnaire_start, name='questionnaire_start'),
    path('questionnaires/<int:pk>/fill/', views.questionnaire_fill, name='questionnaire_fill'),
    path('questionnaires/<int:pk>/view/', views.questionnaire_view, name='questionnaire_view'),
    
    # Questionnaire Templates Management
    path('templates/', views.template_list, name='template_list'),
    path('templates/add/', views.template_add, name='template_add'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:pk>/duplicate/', views.template_duplicate, name='template_duplicate'),
    
    # External Survey Links Management
    path('survey-links/', views.survey_link_list, name='survey_link_list'),
    path('survey-links/create/', views.survey_link_create, name='survey_link_create'),
    path('survey-links/<int:pk>/', views.survey_link_detail, name='survey_link_detail'),
    path('survey-links/<int:pk>/edit/', views.survey_link_edit, name='survey_link_edit'),
    path('survey-links/<int:pk>/revoke/', views.survey_link_revoke, name='survey_link_revoke'),
    path('survey-links/<int:pk>/delete/', views.survey_link_delete, name='survey_link_delete'),
    
    # Public external access (no authentication required)
    path('survey/<str:token>/', views.survey_link_access, name='survey_link_access'),
    
    # AJAX endpoint for getting questionnaires
    path('ajax/questionnaires/<int:vendor_id>/', views.survey_link_get_questionnaires, name='survey_link_get_questionnaires'),
]

