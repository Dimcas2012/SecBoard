from django.urls import path

from . import views

app_name = 'app_integration'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('telegram/', views.telegram_bot_list, name='telegram_bot_list'),
    path('telegram/create/', views.telegram_bot_create, name='telegram_bot_create'),
    path('telegram/<int:pk>/edit/', views.telegram_bot_edit, name='telegram_bot_edit'),
    path('telegram/<int:pk>/delete/', views.telegram_bot_delete, name='telegram_bot_delete'),
    path(
        'telegram/<int:pk>/test-connection/',
        views.telegram_bot_test_connection,
        name='telegram_bot_test_connection',
    ),
    path(
        'telegram/<int:pk>/send-test-message/',
        views.telegram_bot_send_test_message,
        name='telegram_bot_send_test_message',
    ),
    path(
        'telegram/<int:pk>/configure-webhook/',
        views.telegram_bot_configure_webhook,
        name='telegram_bot_configure_webhook',
    ),
    path(
        'telegram/<int:pk>/webhook-status/',
        views.telegram_bot_webhook_status,
        name='telegram_bot_webhook_status',
    ),
]

