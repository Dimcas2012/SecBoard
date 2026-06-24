# SecBoard\SecBoard\app_study\urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.urls import path, include

urlpatterns = [

    path('quiz/', include([

        path('list/', views.quiz_list, name='quiz_list'),
        path('start/<int:quiz_id>/', views.start_quiz, name='start_quiz'),
        path('submit/<int:attempt_id>/', views.submit_quiz, name='submit_quiz'),
        path('result/<int:attempt_id>/', views.quiz_result, name='quiz_result'),
        # Add secure token-based access for results (temporarily disabled)
        # path('secure-result/<uuid:secure_token>/', views.quiz_result_secure, name='quiz_result_secure'),
        path('history/', views.quiz_history, name='quiz_history'),

    ])),

    # Quiz Manager routes
    path('quiz-manager/', views.quiz_manager, name='quiz_manager'),
    path('quiz-manager/export-results/', views.export_quiz_manager_results, name='export_quiz_manager_results'),
    path('quiz-manager/toggle-active/<int:quiz_id>/', views.quiz_toggle_active, name='quiz_toggle_active'),
    path('quiz-manager/guide/', views.quiz_manager_guide, name='quiz_manager_guide'),
    path('quiz-manager/api/guide/translate/', views.quiz_manager_guide_translate, name='quiz_manager_guide_translate'),
    path('quiz-manager/create/', views.quiz_create, name='quiz_create'),
    path('quiz-manager/edit/<int:quiz_id>/', views.quiz_edit, name='quiz_edit'),
    path('quiz-manager/delete/<int:quiz_id>/', views.quiz_delete, name='quiz_delete'),
    
    # Question Management routes
    path('quiz-manager/quiz/<int:quiz_id>/question/create/', views.question_create, name='question_create'),
    path('quiz-manager/question/edit/<int:question_id>/', views.question_edit, name='question_edit'),
    path('quiz-manager/question/delete/<int:question_id>/', views.question_delete, name='question_delete'),
    
    # Answer Management routes
    path('quiz-manager/question/<int:question_id>/answer/create/', views.answer_create, name='answer_create'),
    path('quiz-manager/answer/edit/<int:answer_id>/', views.answer_edit, name='answer_edit'),
    path('quiz-manager/answer/delete/<int:answer_id>/', views.answer_delete, name='answer_delete'),


    path('quiz-results/', views.quiz_results, name='quiz_results'),
    path('protected-media/quiz-pdf/<int:quiz_id>/', views.protected_pdf_serve, name='protected_quiz_pdf'),
    path('get-file/<int:quiz_id>/', views.get_quiz_file_content, name='get_quiz_file_content'),
    
    # Export routes
    path('export-quiz/<int:quiz_id>/', views.export_quiz_results, name='export_quiz_results'),
    path('export-all-results/', views.export_all_results, name='export_all_results'),
    
    # API routes
    path('quiz/available/', views.get_available_quizzes, name='get_available_quizzes'),
    path('get-cabinet-data-by-company/', views.get_cabinet_data_by_company, name='get_cabinet_data_by_company'),
    path('quiz/<int:quiz_id>/users/', views.quiz_users_api, name='quiz_users_api'),
    path('quiz/<int:quiz_id>/results/', views.quiz_results_api, name='quiz_results_api'),
    path('quiz/<int:quiz_id>/simulate-pass/', views.simulate_quiz_pass_api, name='simulate_quiz_pass_api'),
    
    # Email reminder API routes
    path('email-accounts/', views.email_accounts_api, name='email_accounts_api'),
    path('quiz/<int:quiz_id>/default-template/', views.quiz_default_template_api, name='quiz_default_template_api'),
    path('quiz/<int:quiz_id>/send-test-email/', views.send_test_email_api, name='send_test_email_api'),
    path('quiz/<int:quiz_id>/send-reminders/', views.send_reminder_emails_api, name='send_reminder_emails_api'),
    
    # Scheduled reminders API endpoints
    path('quiz/<int:quiz_id>/scheduled-reminders/', views.scheduled_reminders_api, name='scheduled_reminders_api'),
    path('quiz/<int:quiz_id>/reminder-logs/', views.reminder_logs_api, name='reminder_logs_api'),

    # Page Manager routes
    path('page-manager/', views.page_manager, name='page_manager'),
    path('page-manager/toggle-active/<int:page_id>/', views.page_toggle_active, name='page_toggle_active'),
    path('page-manager/guide/', views.page_manager_guide, name='page_manager_guide'),
    path('page-manager/api/guide/translate/', views.page_manager_guide_translate, name='page_manager_guide_translate'),
    path('page-manager/create/', views.page_create, name='page_create'),
    path('page-manager/edit/<int:page_id>/', views.page_edit, name='page_edit'),
    path('page-manager/delete/<int:page_id>/', views.page_delete, name='page_delete'),
    
    # Page View route
    path('page/<slug:slug>/', views.page_view, name='page_view'),
    
    # Document download route
    path('protected-media/page-document/<int:document_id>/', views.protected_document_serve, name='protected_page_document'),
    
    # Learning Hub route
    path('learning-hub/', views.learning_hub, name='learning_hub'),
]