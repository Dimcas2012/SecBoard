#  SecBoard\SecBoard\app_cabinet
from django.urls import path
from django.http import HttpResponsePermanentRedirect
from django.contrib.auth import views as auth_views
from . import views

def redirect_to_app_conf(request, url_name):
    """Generic redirect function to app_conf URLs"""
    from django.urls import reverse
    return HttpResponsePermanentRedirect(reverse(f'app_conf:{url_name}'))
from .views import get_user_data, refresh_user_from_ad
from .options_view import (
    get_departments, get_department, add_department, edit_department, delete_department,
    get_positions, get_position, add_position, edit_position, delete_position,
    get_department_positions, org_structure_view, org_structure_guide, org_structure_guide_translate, get_company_departments,
    get_company_users, get_company_positions, get_company_groups, get_group, get_group_users,
    create_group, edit_group, delete_group, groups_view, cabinet_groups_guide, cabinet_groups_guide_translate, users_view, cabinet_users_guide, cabinet_users_guide_translate, create_user,
    get_user, get_department_users, update_user, delete_user, get_system_users_not_in_cabinet,
    export_users_excel, get_companies, get_company, add_company, edit_company, delete_company,
    task_reminder_submit,
    task_reminder_schedules_list,
    task_reminder_schedule_detail,
    task_reminder_schedule_update,
    telegram_broadcast_submit,
    email_broadcast_submit,
    remove_user_from_group,
    set_user_force_two_factor,
    roles_view, get_role, get_role_groups_by_companies, get_platform_roles_by_company, create_role, edit_role, delete_role,
)

urlpatterns = [
    # Redirect old site_statistics URLs to new location in app_conf
    path('site_statistics/', lambda r: redirect_to_app_conf(r, 'site_statistics'), name='site_statistics_redirect'),
    path('api/site_statistics/', lambda r: redirect_to_app_conf(r, 'get_site_statistics')),
    path('api/export_statistics/', lambda r: redirect_to_app_conf(r, 'export_statistics')),
    
    path('', views.index, name='index'),
    path('first_login/', views.first_login, name='first_login'),
    path('update_profile/', views.update_profile, name='update_profile'),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('personal-cabinet/', views.personal_cabinet, name='personal_cabinet'),
    path('personal-cabinet/2fa/setup/', views.two_factor_setup, name='two_factor_setup'),
    path('personal-cabinet/2fa/verify/', views.two_factor_verify, name='two_factor_verify'),
    path('personal-cabinet/2fa/disable/', views.two_factor_disable, name='two_factor_disable'),
    path('personal-cabinet/2fa/backup/regenerate/', views.two_factor_regenerate_codes, name='two_factor_regenerate_codes'),
    path('unauthorized/', views.unauthorized_access, name='unauthorized'),
    path('login/', views.login_view, name='login'),
    path('login/2fa/', views.two_factor_challenge, name='two_factor_challenge'),
    path('login/2fa/setup/', views.force_two_factor_enroll, name='force_two_factor_enroll'),
    path('logout/', views.logout_view, name='logout'),

    # Password Reset URLs
    path('password_reset/',
         views.password_reset_request,
         name='password_reset'),
    
    path('password_reset/done/',
         views.password_reset_done,
         name='password_reset_done'),
    
    path('reset/<uidb64>/<token>/',
         views.password_reset_confirm,
         name='password_reset_confirm'),
    
    path('reset/done/',
         views.password_reset_complete,
         name='password_reset_complete'),

    # Password Change URL
    path('password_change/',
         views.password_change,
         name='password_change'),

    # Company related URLs
    path('cabinet/auth/<uidb64>/<token>/', views.cabinet_auth, name='cabinet_auth'),

    # Groups URLs
    path('groups/guide/', cabinet_groups_guide, name='cabinet_groups_guide'),
    path('groups/api/guide/translate/', cabinet_groups_guide_translate, name='cabinet_groups_guide_translate'),
    path('groups/', groups_view, name='groups'),
    path('groups/<int:pk>/', get_group, name='get_group'),
    path('groups/<int:pk>/users/', get_group_users, name='get_group_users'),
    path('groups/create/', create_group, name='create_group'),
    path('groups/<int:pk>/edit/', edit_group, name='edit_group'),
    path('groups/<int:pk>/delete/', delete_group, name='delete_group'),
    path('groups/<int:pk>/remove-user/', remove_user_from_group, name='remove_user_from_group'),

    # Companies URLs
    path('companies/', get_companies, name='get_companies'),
    path('companies/<int:pk>/', get_company, name='get_company'),
    path('companies/create/', add_company, name='add_company'),
    path('companies/<int:pk>/edit/', edit_company, name='edit_company'),
    path('companies/<int:pk>/delete/', delete_company, name='delete_company'),

    # Users URLs
    path('users/guide/', cabinet_users_guide, name='cabinet_users_guide'),
    path('users/api/guide/translate/', cabinet_users_guide_translate, name='cabinet_users_guide_translate'),
    path('users/', users_view, name='users'),
    path('users/create/', create_user, name='create_user'),
    path('users/<int:pk>/delete/', delete_user, name='delete_user'),
    path('users/<int:pk>/', get_user, name='get_user'),
    path('users/<int:pk>/update/', update_user, name='update_user'),
    path('users/<int:pk>/get/', get_user_data, name='get_user_data'),
    path('users/<int:pk>/refresh-ad/', refresh_user_from_ad, name='refresh_user_from_ad'),
    path('users/api/platform-roles-by-company/', get_platform_roles_by_company, name='get_platform_roles_by_company'),
    path('users/<int:pk>/tasks-content/', views.get_user_tasks_content, name='get_user_tasks_content'),
    path('users/<int:pk>/force-two-factor/', set_user_force_two_factor, name='set_user_force_two_factor'),
    path('users/export/', export_users_excel, name='export_users_excel'),
    path('users/task-reminder/', task_reminder_submit, name='task_reminder_submit'),
    path('users/telegram-broadcast/', telegram_broadcast_submit, name='telegram_broadcast_submit'),
    path('users/email-broadcast/', email_broadcast_submit, name='email_broadcast_submit'),
    path(
        'users/task-reminder-schedules/<int:pk>/update/',
        task_reminder_schedule_update,
        name='task_reminder_schedule_update',
    ),
    path(
        'users/task-reminder-schedules/<int:pk>/',
        task_reminder_schedule_detail,
        name='task_reminder_schedule_detail',
    ),
    path('users/task-reminder-schedules/', task_reminder_schedules_list, name='task_reminder_schedules_list'),

    # Roles (Manage roles) - under users section
    path('users/roles/', roles_view, name='roles'),
    path('users/roles/<int:role_id>/dashboard-config/', views.role_dashboard_config, name='role_dashboard_config'),
    path('users/roles/api/groups-by-companies/', get_role_groups_by_companies, name='get_role_groups_by_companies'),
    path('users/roles/<int:pk>/', get_role, name='get_role'),
    path('users/roles/create/', create_role, name='create_role'),
    path('users/roles/<int:pk>/edit/', edit_role, name='edit_role'),
    path('users/roles/<int:pk>/delete/', delete_role, name='delete_role'),

    # Executive View (role-based dashboard)
    path('executive-view/', views.executive_view, name='executive_view'),
    path('api/executive-view/metrics/', views.executive_view_metrics_api, name='executive_view_metrics_api'),

    # Company and Department URLs
    path('companies/<int:pk>/departments/', get_company_departments, name='get_company_departments'),
    path('companies/<int:pk>/positions/', get_company_positions, name='get_company_positions'),
    path('companies/<int:pk>/groups/', get_company_groups, name='get_company_groups'),
    path('companies/departments/', get_departments, name='get_departments'),
    path('companies/departments/add/', add_department, name='add_department'),
    path('companies/departments/<int:pk>/edit/', edit_department, name='edit_department'),
    path('companies/departments/<int:pk>/delete/', delete_department, name='delete_department'),
    path('companies/departments/<int:pk>/', get_department, name='get_department'),

    # Position URLs
    path('companies/positions/', get_positions, name='get_positions'),
    path('companies/positions/add/', add_position, name='add_position'),
    path('companies/positions/<int:pk>/', get_position, name='get_position'),
    path('companies/positions/<int:pk>/edit/', edit_position, name='edit_position'),
    path('companies/positions/<int:pk>/delete/', delete_position, name='delete_position'),
    # Additional URLs
    path('companies/<int:company_id>/departments/<int:department_id>/positions/',
         get_department_positions,
         name='get_department_positions'),

    path('api/company/<int:pk>/users/', get_company_users, name='get_company_users'),
    path('companies/departments/<int:department_id>/users/', get_department_users, name='get_department_users'),


    # Organization structure view
    path('companies/org-structure/guide/',
         org_structure_guide,
         name='org_structure_guide'),
    path('companies/org-structure/api/guide/translate/',
         org_structure_guide_translate,
         name='org_structure_guide_translate'),
    path('companies/org-structure/',
         org_structure_view,
         name='org_structure'),

    # Organization chart view
    path('org-chart/',
         views.org_chart_view,
         name='org_chart'),

    # Get system users not in cabinet
    path('system-users-not-in-cabinet/', 
         get_system_users_not_in_cabinet, 
         name='system_users_not_in_cabinet'),
]
