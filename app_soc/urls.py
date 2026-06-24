from django.urls import path
from . import views

app_name = 'app_soc'

urlpatterns = [
    # Dashboard and views
    path('fim/dashboard/', views.fim_alerts_dashboard, name='fim_dashboard'),
    path('fim/dashboard/guide/', views.fim_dashboard_guide, name='fim_dashboard_guide'),
    path('fim/dashboard/api/guide/translate/', views.fim_dashboard_guide_translate, name='fim_dashboard_guide_translate'),
    path('fim/alert/<str:alert_id>/', views.fim_alert_detail, name='fim_alert_detail'),
    path('agent/<str:agent_id>/', views.agent_detail, name='agent_detail'),
    
    
    # Webhook endpoints
    path('webhook/wazuh/fim/', views.wazuh_fim_webhook, name='wazuh_fim_webhook'),
    path('webhook/<str:client_id>/fim/', views.client_fim_webhook, name='client_fim_webhook'),
]
