from django.urls import path
from django.shortcuts import redirect
from django.http import HttpResponsePermanentRedirect
from . import views

def redirect_to_app_conf(request, url_name, **kwargs):
    """Generic redirect function to app_conf URLs"""
    from django.urls import reverse
    return HttpResponsePermanentRedirect(reverse(f'app_conf:{url_name}', kwargs=kwargs))

urlpatterns = [
    # Redirect old translate-po URLs to new location in app_conf
    path('translate-po/', lambda r: redirect_to_app_conf(r, 'translate_po_page'), name='translate_po_page_redirect'),
    path('translate-po/start/', lambda r: redirect_to_app_conf(r, 'start_translation')),
    path('translate-po/stop/', lambda r: redirect_to_app_conf(r, 'stop_translation')),
    path('translate-po/progress/', lambda r: redirect_to_app_conf(r, 'get_translation_progress')),
    path('translate-po/untranslated/<str:language>/', lambda r, language: redirect_to_app_conf(r, 'get_untranslated_strings', language=language)),
    path('translate-po/preview/', lambda r: redirect_to_app_conf(r, 'get_preview_translations')),
    path('translate-po/save-confirmed/', lambda r: redirect_to_app_conf(r, 'save_confirmed_translations')),
    
    # Test connection URLs
    path('test-connection/google/<int:api_id>/', views.test_google_connection, name='test_google_connection'),
    path('test-connection/claude/<int:api_id>/', views.test_claude_connection, name='test_claude_connection'),
    path('test-connection/groq/<int:api_id>/', views.test_groq_connection, name='test_groq_connection'),
    path('test-connection/ollama/<int:api_id>/', views.test_ollama_connection, name='test_ollama_connection'),
    path('test-connection/deepseek/<int:api_id>/', views.test_deepseek_connection, name='test_deepseek_connection'),
    # AI Assistant URLs
    path('assistant/page-context/', views.get_page_context, name='ai_assistant_page_context'),
    path('assistant/chat/', views.ai_assistant_chat, name='ai_assistant_chat'),
    path('assistant/settings/', views.get_ai_agent_settings, name='ai_assistant_settings'),
    path('assistant/previous-conversations/', views.get_previous_conversations, name='ai_assistant_previous_conversations'),
] 