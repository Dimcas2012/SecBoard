from django.urls import path
from . import views
from app_cabinet.views import site_statistics, get_site_statistics, export_statistics
from app_ai.views import (
    translate_po_page, start_translation, stop_translation, get_translation_progress,
    get_untranslated_strings, get_preview_translations, save_confirmed_translations,
    get_fuzzy_strings, start_fuzzy_fix, get_fuzzy_fix_progress, stop_fuzzy_fix,
    get_fuzzy_fix_preview, save_fuzzy_fixes,
)

urlpatterns = [
    path('', views.about, name='about'),  # /about/ will serve about page
    path('module/<str:module_name>/', views.module_detail, name='module_detail'),  # /about/module/<name>/ for detailed module pages
    path('contact/', views.contact, name='contact'),  # /about/contact/ for contact page
    path('partnership/', views.partnership, name='partnership'),  # /about/partnership/ for partnership page
    path('faq/', views.faq, name='faq'),  # /about/faq/ will serve FAQ page
    path('knowledge-base/', views.knowledge_base_list, name='knowledge_base_list'),
    path('knowledge-base/<slug:slug>/', views.knowledge_base_detail, name='knowledge_base_detail'),
    path('api/mail-servers/', views.get_mail_servers, name='get_mail_servers'),
    path('api/mail-accounts/', views.get_mail_accounts, name='get_mail_accounts'),
    path('license/activate/', views.license_activate, name='license_activate'),
    # Site Statistics URLs
    path('site_statistics/', site_statistics, name='site_statistics'),
    path('api/site_statistics/', get_site_statistics, name='get_site_statistics'),
    path('api/export_statistics/', export_statistics, name='export_statistics'),
    # Translation PO URLs
    path('translate-po/', translate_po_page, name='translate_po_page'),
    path('translate-po/start/', start_translation, name='start_translation'),
    path('translate-po/stop/', stop_translation, name='stop_translation'),
    path('translate-po/progress/', get_translation_progress, name='get_translation_progress'),
    path('translate-po/untranslated/<str:language>/', get_untranslated_strings, name='get_untranslated_strings'),
    path('translate-po/preview/', get_preview_translations, name='get_preview_translations'),
    path('translate-po/save-confirmed/', save_confirmed_translations, name='save_confirmed_translations'),
    # Fuzzy fix URLs
    path('translate-po/fuzzy/<str:language>/', get_fuzzy_strings, name='get_fuzzy_strings'),
    path('translate-po/fix-fuzzy/start/', start_fuzzy_fix, name='start_fuzzy_fix'),
    path('translate-po/fix-fuzzy/progress/', get_fuzzy_fix_progress, name='get_fuzzy_fix_progress'),
    path('translate-po/fix-fuzzy/stop/', stop_fuzzy_fix, name='stop_fuzzy_fix'),
    path('translate-po/fix-fuzzy/preview/', get_fuzzy_fix_preview, name='get_fuzzy_fix_preview'),
    path('translate-po/fix-fuzzy/save/', save_fuzzy_fixes, name='save_fuzzy_fixes'),
] 