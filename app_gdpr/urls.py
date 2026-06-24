#  SecBoard\SecBoard\app_gdpr\urls.py

from django.urls import path
from . import views

app_name = 'app_gdpr'

urlpatterns = [
    # Dashboard
    path('', views.ComplianceDashboardView.as_view(), name='compliance_dashboard'),
    
    # Data Subjects
    path('data-subjects/', views.DataSubjectListView.as_view(), name='data_subject_list'),
    path('data-subjects/create/', views.DataSubjectCreateView.as_view(), name='data_subject_create'),
    path('data-subjects/<int:pk>/', views.DataSubjectDetailView.as_view(), name='data_subject_detail'),
    path('data-subjects/<int:pk>/update/', views.DataSubjectUpdateView.as_view(), name='data_subject_update'),
    path('data-subjects/<int:pk>/export/', views.data_subject_export_view, name='data_subject_export'),
    path('data-subjects/<int:pk>/anonymize/', views.data_subject_anonymize_view, name='data_subject_anonymize'),
    
    # Consents
    path('consents/', views.ConsentRecordListView.as_view(), name='consent_list'),
    path('consents/create/', views.ConsentRecordCreateView.as_view(), name='consent_create'),
    path('consents/<int:pk>/', views.ConsentRecordDetailView.as_view(), name='consent_detail'),
    path('consents/<int:pk>/withdraw/', views.consent_withdraw_view, name='consent_withdraw'),
    
    # Data Subject Requests (DSR)
    path('dsr/', views.DSRDashboardView.as_view(), name='dsr_dashboard'),
    path('dsr/list/', views.DSRListView.as_view(), name='dsr_list'),
    path('dsr/create/', views.DSRCreateView.as_view(), name='dsr_create'),
    path('dsr/<int:pk>/', views.DSRDetailView.as_view(), name='dsr_detail'),
    path('dsr/<int:pk>/process/', views.DSRProcessView.as_view(), name='dsr_process'),
    path('dsr/<int:pk>/complete/', views.dsr_complete_view, name='dsr_complete'),
    path('dsr/<int:pk>/extend/', views.dsr_extend_deadline_view, name='dsr_extend'),
    
    # Data Breach Incidents
    path('breaches/', views.DataBreachListView.as_view(), name='breach_list'),
    path('breaches/create/', views.DataBreachCreateView.as_view(), name='breach_create'),
    path('breaches/<int:pk>/', views.DataBreachDetailView.as_view(), name='breach_detail'),
    path('breaches/<int:pk>/update/', views.DataBreachUpdateView.as_view(), name='breach_update'),
    path('breaches/<int:pk>/report/', views.breach_report_view, name='breach_report'),
    
    # Data Processing Activities
    path('activities/', views.DataProcessingActivityListView.as_view(), name='activity_list'),
    path('activities/create/', views.DataProcessingActivityCreateView.as_view(), name='activity_create'),
    path('activities/<int:pk>/', views.DataProcessingActivityDetailView.as_view(), name='activity_detail'),
    path('activities/<int:pk>/update/', views.DataProcessingActivityUpdateView.as_view(), name='activity_update'),
    
    # Data Retention Policies
    path('policies/', views.DataRetentionPolicyListView.as_view(), name='policy_list'),
    path('policies/create/', views.DataRetentionPolicyCreateView.as_view(), name='policy_create'),
    path('policies/<int:pk>/', views.DataRetentionPolicyDetailView.as_view(), name='policy_detail'),
    path('policies/<int:pk>/update/', views.DataRetentionPolicyUpdateView.as_view(), name='policy_update'),
    
    # DPIA Assessments
    path('dpia/', views.DPIAListView.as_view(), name='dpia_list'),
    path('dpia/create/', views.DPIACreateView.as_view(), name='dpia_create'),
    path('dpia/<int:pk>/', views.DPIADetailView.as_view(), name='dpia_detail'),
    path('dpia/<int:pk>/update/', views.DPIAUpdateView.as_view(), name='dpia_update'),
    path('dpia/<int:pk>/approve/', views.dpia_approve_view, name='dpia_approve'),
    
    # Reports
    path('reports/', views.ComplianceReportView.as_view(), name='compliance_report'),
    path('reports/generate/', views.generate_report_view, name='generate_report'),
    path('reports/export/excel/', views.export_compliance_report_excel, name='export_compliance_excel'),
    path('reports/export/pdf/', views.export_compliance_report_pdf, name='export_compliance_pdf'),

    # Guide (modal content API; resources stay under guide/download/)
    path('guide/', views.gdpr_guide_api, name='gdpr_guide'),
    path('guide/download/<int:resource_id>/', views.download_resource_view, name='download_resource'),
    path('api/guide/translate/', views.gdpr_guide_translate, name='gdpr_guide_translate'),

    # API endpoints
    path('api/users-by-company/<int:company_id>/', views.users_by_company_api, name='users_by_company_api'),
]

