# app_gophish/urls.py

from django.urls import path
from . import views

app_name = 'app_gophish'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('guide/', views.gophish_guide, name='gophish_guide'),
    path('api/guide/translate/', views.gophish_guide_translate, name='gophish_guide_translate'),
    
    # Servers
    path('servers/', views.server_list, name='server_list'),
    path('servers/create/', views.server_create, name='server_create'),
    path('servers/<int:server_id>/', views.server_detail, name='server_detail'),
    path('servers/<int:server_id>/edit/', views.server_edit, name='server_edit'),
    path('servers/<int:server_id>/sync/', views.server_sync_direct, name='server_sync_direct'),
    path('servers/<int:server_id>/delete/', views.server_delete, name='server_delete'),
    
    # Campaigns
    path('campaigns/', views.campaign_list, name='campaign_list'),
    path('campaigns/export/', views.campaign_export_excel, name='campaign_export_excel'),
    path('campaigns/<int:campaign_id>/', views.campaign_detail, name='campaign_detail'),
    path('campaigns/<int:campaign_id>/events/export/', views.campaign_events_export_excel, name='campaign_events_export_excel'),
    
    # Landing Pages
    path('landing-pages/', views.landing_page_list, name='landing_page_list'),
    path('landing-pages/<int:page_id>/preview/', views.landing_page_preview, name='landing_page_preview'),
    
    # Email Templates
    path('email-templates/', views.email_template_list, name='email_template_list'),
    path('email-templates/<int:template_id>/', views.email_template_detail, name='email_template_detail'),
    
    # Sending Profiles
    path('sending-profiles/', views.sending_profile_list, name='sending_profile_list'),
    
    # Groups
    path('groups/', views.group_list, name='group_list'),
    
    # Events
    path('events/', views.events_list, name='events_list'),
    path('events/export/', views.events_export_excel, name='events_export_excel'),
    
    # Synchronization
    path('sync/', views.sync_data, name='sync_data'),
    path('sync/logs/', views.sync_logs, name='sync_logs'),
    path('sync/logs/<int:log_id>/', views.sync_log_detail, name='sync_log_detail'),
    
    # API endpoints
    path('api/campaigns/<int:campaign_id>/events/', views.campaign_events_api, name='campaign_events_api'),
    path('api/load-server-data/', views.ajax_load_server_data, name='ajax_load_server_data'),
    path('api/servers/<int:server_id>/test-connection/', views.test_server_connection, name='test_server_connection'),
    path('api/servers/<int:server_id>/diagnose/', views.diagnose_server, name='diagnose_server'),
    
    # Webhooks
    path('webhook/', views.webhook_handler, name='webhook_handler'),
]
