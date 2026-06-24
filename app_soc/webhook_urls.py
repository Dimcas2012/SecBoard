from django.urls import path
from . import views

app_name = 'app_soc_webhook'

urlpatterns = [
    # Webhook endpoint for Wazuh FIM alerts (legacy support)
    path('wazuh/fim/', views.wazuh_fim_webhook, name='wazuh_fim_webhook'),
    
    # Dynamic webhook endpoints for individual clients
    path('<str:client_id>/fim/', views.client_fim_webhook, name='client_fim_webhook'),
]
