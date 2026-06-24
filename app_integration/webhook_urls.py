from django.urls import path

from . import views

urlpatterns = [
    path('telegram/<int:pk>/', views.telegram_webhook, name='telegram_webhook'),
]
