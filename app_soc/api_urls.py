from django.urls import path
from . import views
from . import views_analysis
from . import ai_analysis_views
from . import outgoing_webhook_views
from . import fim_settings_api
from .auto_status_rule import set_auto_status_rule, get_alert_status_history

app_name = 'app_soc_api'

urlpatterns = [
    # API endpoints (non-translatable)
    path('alert-stats/', views.alert_stats_api, name='alert_stats_api'),
    path('alert/<str:alert_id>/mark-processed/', views.mark_alert_processed, name='mark_alert_processed'),
    
    # Alert processing endpoints
    path('alert/<str:alert_id>/details/', views.alert_details_api, name='alert_details_api'),
    path('alert/<str:alert_id>/process/', views.alert_process_api, name='alert_process_api'),
    
    # Webhook Client API endpoints
    path('webhook-clients/', views.webhook_clients_api, name='webhook_clients_api'),
    path('webhook-clients/<str:client_id>/', views.webhook_client_detail_api, name='webhook_client_detail_api'),
    path('webhook-clients/<str:client_id>/auth/', views.webhook_client_auth_api, name='webhook_client_auth_api'),
    
    # Companies API endpoint
    path('companies/', views.companies_api, name='companies_api'),
    
    # Analysis Configuration API endpoints
    path('analysis-config/', views.analysis_config_api, name='analysis_config_api'),
    path('analysis-config/<int:config_id>/', views.analysis_config_detail_api, name='analysis_config_detail_api'),
    path('analysis-configs-public/', views.analysis_configs_public_api, name='analysis_configs_public_api'),
    
    # Clear All Alerts API endpoint
    path('clear-all-alerts/', views.clear_all_alerts_api, name='clear_all_alerts_api'),
    
    # Analysis Results API endpoints
    path('alert/<str:alert_id>/analysis-results/', views_analysis.analysis_results_api, name='analysis_results_api'),
    path('save-analysis-result/', views_analysis.save_analysis_result_api, name='save_analysis_result_api'),
    path('analysis-result/<str:analysis_id>/', views_analysis.analysis_result_detail_api, name='analysis_result_detail_api'),
    path('analysis-results/<str:hash_type>/<str:hash_value>/', views_analysis.analysis_results_by_hash_api, name='analysis_results_by_hash_api'),
    path('execute-analysis/', views_analysis.execute_analysis_api, name='execute_analysis_api'),
    path('debug-analysis-config/<int:config_id>/', views_analysis.debug_analysis_config_api, name='debug_analysis_config_api'),
    
    # AI Analysis API endpoints
    path('analyze-fim-alert-ai/', ai_analysis_views.analyze_fim_alert_ai, name='analyze_fim_alert_ai'),
    path('ai-models/', ai_analysis_views.get_ai_models_api, name='get_ai_models_api'),
    path('ai-providers/', ai_analysis_views.get_ai_providers_api, name='get_ai_providers_api'),
    
    # AI Analysis Results API endpoints
    path('save-ai-analysis-result/', ai_analysis_views.save_ai_analysis_result_api, name='save_ai_analysis_result_api'),
    path('ai-analysis-results/<str:alert_id>/', ai_analysis_views.ai_analysis_results_api, name='ai_analysis_results_api'),
    path('ai-analysis-result-detail/<str:analysis_id>/', ai_analysis_views.ai_analysis_result_detail_api, name='ai_analysis_result_detail_api'),
    
    # Outgoing Webhooks API endpoints
    path('outgoing-webhooks/', outgoing_webhook_views.outgoing_webhooks_api, name='outgoing_webhooks_api'),
    path('outgoing-webhooks/<int:webhook_id>/', outgoing_webhook_views.outgoing_webhook_detail_api, name='outgoing_webhook_detail_api'),
    path('outgoing-webhooks/<int:webhook_id>/test/', outgoing_webhook_views.test_outgoing_webhook_api, name='test_outgoing_webhook_api'),
    
    # Helper API endpoints for webhook configuration
    path('outgoing-webhooks/companies/', outgoing_webhook_views.companies_api, name='outgoing_webhook_companies_api'),
    path('outgoing-webhooks/webhook-clients/', outgoing_webhook_views.webhook_clients_api, name='outgoing_webhook_clients_api'),
    path('alert-webhooks/<str:alert_id>/', outgoing_webhook_views.alert_webhooks_api, name='alert_webhooks_api'),
    
    # FIM Settings API endpoints
    path('fim-settings/', fim_settings_api.fim_settings_api, name='fim_settings_api'),
    
    # Auto-status rule endpoints
    path('set-auto-status-rule/', set_auto_status_rule, name='set_auto_status_rule'),
    path('alert/<str:alert_id>/status-history/', get_alert_status_history, name='get_alert_status_history'),
]
