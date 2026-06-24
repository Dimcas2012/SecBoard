#  SecBoard\SecBoard\app_access\urls.py
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import ensure_csrf_cookie
from . import views, manage_is_core_view, manage_is_objects_view, access_is_view, access_request_view, matrix_view, api_view, notification_view, user_available_access_view, excel_export, admin_views
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse

 

 

urlpatterns = [
    # API Request URLs
    path('api-request/', api_view.api_request_page, name='api_request_page'),
    path('api-request/answer/', api_view.api_request_answer, name='api_request_answer'),    
    path('api-request/test-base64/', api_view.test_base64_decode, name='test_base64_decode'),   
    path('api-request/sync-users/', api_view.sync_api_users, name='sync_api_users'),
    path('api-request/synced-users/', api_view.api_synced_users, name='api_synced_users'),
    path('api-request/clear-sync-data/', api_view.clear_sync_data, name='clear_sync_data'),
    path('api-request/refresh-token/<int:credential_id>/', api_view.refresh_token, name='refresh_token'),
    path('api-request/export-xlsx/', api_view.export_api_users_xlsx, name='export_api_users_xlsx'),
    path('api-request/export-merchants-xlsx/', api_view.export_all_merchants_xlsx, name='export_all_merchants_xlsx'),
    
    # API Credential URLs
    path('api-request/save-credential/', api_view.save_api_credential, name='save_api_credential'),
    path('api-request/delete-credential/', api_view.delete_api_credential, name='delete_api_credential'),
    path('api-request/get-credential/<int:credential_id>/', api_view.get_api_credential, name='get_api_credential'),
    path('api-request/get-user-statuses/<int:user_id>/', api_view.get_user_access_statuses, name='get_user_access_statuses'),
    path('api-request/get-access-record-history/<int:access_record_id>/', api_view.get_access_record_history, name='get_access_record_history'),
    path('api-request/get-merchant-role-history/<int:user_id>/<str:merchant>/<str:role>/', api_view.get_merchant_role_history, name='get_merchant_role_history'),
    path('access-requests/<int:access_record_id>/', api_view.get_access_requests_by_record, name='get_access_requests_by_record'),
    path('access-sequence/<int:request_id>/', access_request_view.get_access_sequence_view, name='get_access_sequence'),
    
    path('access-records/', access_is_view.access_is, name='access_records'),
    path('access-records/guide/', access_is_view.access_records_guide, name='access_records_guide'),
    path('access-records/api/guide/translate/', access_is_view.access_records_guide_translate, name='access_records_guide_translate'),
    path('access/add/', access_is_view.add_access, name='add_access'),
    path('access/edit/<int:access_id>/', access_is_view.edit_access, name='edit_access'),
    path('access/get/<int:access_id>/', access_is_view.get_access, name='get_access'),
    path('access/delete/<int:access_id>/', access_is_view.delete_access, name='delete_access'),
    path('access/bulk-delete/', access_is_view.bulk_delete_access, name='bulk_delete_access'),
    path('get-systems-by-company/', access_is_view.get_systems_by_company, name='get_systems_by_company'),
    path('get-cabinet-users-and-groups/', access_is_view.get_cabinet_users_and_groups, name='get_cabinet_users_and_groups'),
    path('access/update/', access_is_view.update_access, name='update_access'),
    path('get-company-systems/', access_is_view.get_company_systems, name='get_company_systems'),
    path('access/company-systems/<int:company_id>/', access_is_view.get_company_systems, name='get_company_systems'),
    path('system-filters/<int:system_id>/', access_is_view.get_system_filters, name='get_system_filters'),
    path('system-objects/<int:system_id>/', access_is_view.get_system_objects, name='get_system_objects'),
    path('object-filters/<int:object_id>/', access_is_view.get_object_filters, name='get_object_filters'),
    path('company-systems/<int:company_id>/', access_request_view.get_company_systems_for_filter, name='get_company_systems_for_filter'),
    path('system-objects-filter/<int:system_id>/', access_request_view.get_system_objects_for_filter, name='get_system_objects_for_filter'),
    path('access-status/update/<int:access_id>/',  access_is_view.update_access_status, name='update_access_status'),
    
    # Access Record Approvers URLs
    path('access/<int:access_id>/approvers/update/', access_is_view.update_access_record_approvers, name='update_access_record_approvers'),
    path('access/<int:access_id>/approvers/', access_is_view.get_access_approvers, name='get_access_approvers'),
    path('access/<int:access_id>/available-approvers/', access_is_view.get_available_approvers, name='get_available_approvers'),
    path('system-default-approvers/<int:system_id>/<str:environment>/', access_is_view.get_system_default_approvers, name='get_system_default_approvers'),


    path('access_config_is/guide/', manage_is_core_view.access_config_is_guide, name='access_config_is_guide'),
    path('access_config_is/api/guide/translate/', manage_is_core_view.access_config_is_guide_translate, name='access_config_is_guide_translate'),
    path('access_config_is/', manage_is_core_view.access_config_is, name='access_config_is'),
    path('access-rights/', manage_is_core_view.access_right_list, name='access_right_list'),
    path('access-rights/<int:right_id>/', manage_is_core_view.access_right_detail, name='access_right_detail'),
    path('functions/', manage_is_core_view.get_functions, name='get_functions'),
    path('functions/add/', manage_is_core_view.add_function, name='add_function'),
    path('functions/<int:function_id>/detail/', manage_is_core_view.function_detail, name='function_detail'),
    path('functions/<int:function_id>/edit/', manage_is_core_view.edit_function, name='edit_function'),
    path('functions/<int:function_id>/delete/', manage_is_core_view.delete_function, name='delete_function'),
    path('functions/system/', manage_is_core_view.get_system_functions, name='get_system_functions'),
    path('functions/save/', manage_is_core_view.save_function, name='save_function'),
    path('functions/update-order/', manage_is_core_view.update_functions_order, name='update_functions_order'),
    
    # Objects URLs
    path('objects/system/', manage_is_objects_view.get_system_objects, name='get_system_objects'),
    path('objects/save/', manage_is_objects_view.save_object, name='save_object'),
    path('objects/<int:object_id>/detail/', manage_is_objects_view.object_detail, name='object_detail'),
    path('objects/<int:object_id>/copy/', manage_is_objects_view.copy_object, name='copy_object'),
    path('objects/<int:object_id>/delete/', manage_is_objects_view.delete_object, name='delete_object'),
    path('objects/update-order/', manage_is_objects_view.update_objects_order, name='update_objects_order'),
    
    # Object Approving Persons URLs

    
    # Object Roles URLs
    path('object-roles/<int:object_id>/', manage_is_objects_view.get_object_roles, name='get_object_roles'),
    path('object-roles/add/', manage_is_objects_view.add_object_roles, name='add_object_roles'),
    path('object-roles/<int:object_id>/update/', manage_is_objects_view.update_object_roles, name='update_object_roles'),
    path('object-roles/<int:object_id>/update-order/', manage_is_objects_view.update_object_roles_order, name='update_object_roles_order'),
    path('object-roles/<int:object_id>/available/', manage_is_objects_view.get_object_available_roles, name='get_object_available_roles'),
    path('object-roles/save-custom/', manage_is_objects_view.save_custom_object_role, name='save_custom_object_role'),
    path('object-roles/edit-custom/', manage_is_objects_view.edit_custom_object_role, name='edit_custom_object_role'),
    path('object-roles/delete-custom/', manage_is_objects_view.delete_custom_object_role, name='delete_custom_object_role'),
    path('object-roles/<int:object_id>/custom/', manage_is_objects_view.get_custom_object_roles, name='get_custom_object_roles'),
    
    # Object Access Rights URLs
    path('object-access-rights/<int:object_id>/', manage_is_objects_view.get_object_access_rights, name='get_object_access_rights'),
    path('object-access-rights/add/', manage_is_objects_view.add_object_access_rights, name='add_object_access_rights'),
    path('object-access-rights/<int:object_id>/available/', manage_is_objects_view.get_object_available_access_rights, name='get_object_available_access_rights'),
    path('object-access-rights/save-custom/', manage_is_objects_view.save_custom_object_access_right, name='save_custom_object_access_right'),
    path('object-access-rights/edit-custom/', manage_is_objects_view.edit_custom_object_access_right, name='edit_custom_object_access_right'),
    path('object-access-rights/delete-custom/', manage_is_objects_view.delete_custom_object_access_right, name='delete_custom_object_access_right'),
    path('object-access-rights/<int:object_id>/custom/', manage_is_objects_view.get_custom_object_access_rights, name='get_custom_object_access_rights'),
    
    # Object Functions URLs
    path('object-functions/<int:object_id>/', manage_is_objects_view.get_object_functions, name='get_object_functions'),
    path('object-functions/add/', manage_is_objects_view.add_object_functions, name='add_object_functions'),
    path('object-functions/<int:object_id>/<int:function_id>/remove/', manage_is_objects_view.remove_object_function, name='remove_object_function'),
    path('object-functions/<int:object_id>/available/', manage_is_objects_view.get_object_available_functions, name='get_object_available_functions'),
    path('object-functions/<int:object_id>/update-order/', manage_is_objects_view.update_object_functions_order, name='update_object_functions_order'),
    path('object-functions/<int:object_id>/custom/', manage_is_objects_view.get_custom_object_functions, name='get_custom_object_functions'),
    path('object-functions/save-custom/', manage_is_objects_view.save_custom_object_function, name='save_custom_object_function'),
    path('object-functions/edit-custom/', manage_is_objects_view.edit_custom_object_function, name='edit_custom_object_function'),
    path('object-functions/delete-custom/', manage_is_objects_view.delete_custom_object_function, name='delete_custom_object_function'),
    path('object-functions/update-order/', manage_is_objects_view.update_functions_order, name='update_functions_order'),
    path('object-functions/update-assigned-order/', manage_is_objects_view.update_assigned_functions_order, name='update_assigned_functions_order'),
    

    
    # Functions Management URLs  
    path('functions-management/tree/', manage_is_objects_view.get_functions_tree, name='get_functions_tree'),
    path('functions-management/create/', manage_is_objects_view.create_function, name='create_function'),
    path('functions-management/<int:function_id>/', manage_is_objects_view.function_management_detail, name='function_management_detail'),
    
    path('status/', manage_is_core_view.access_status_list, name='access_status_list'),
    path('status/system/', manage_is_core_view.get_system_statuses, name='get_system_statuses'),
    path('status/<int:status_id>/', manage_is_core_view.access_status_detail, name='access_status_detail'),


    path('status/save/', manage_is_core_view.save_status, name='save_status'),
    path('status/<int:status_id>/', manage_is_core_view.status_detail, name='status_detail'),
    path('status/update-order/', manage_is_core_view.update_status_order, name='update_status_order'),
    path('approving-persons/add/', manage_is_core_view.add_approving_persons, name='add_approving_persons'),
    path('approving-persons/<int:asset_id>/', manage_is_core_view.get_approving_persons, name='get_approving_persons'),
    path('approving-persons/<int:asset_id>/edit/', manage_is_core_view.edit_approving_persons, name='edit_approving_persons'),
    path('approving-persons/<int:asset_id>/update/', 
         manage_is_core_view.update_approving_persons, 
         name='update_approving_persons'),
    path('cabinet-users/<int:company_id>/', manage_is_core_view.get_cabinet_users, name='get_cabinet_users'),
    path('access/approvers/<int:access_id>/', manage_is_core_view.get_access_approvers, name='get_access_approvers'),
    path('access/approvers/<int:access_id>/save/', manage_is_core_view.save_access_approvers, name='save_access_approvers'),
    path('access/approvers/update/', manage_is_core_view.update_access_approvers, name='update_access_approvers'),
    path('roles/save/', manage_is_core_view.save_role, name='save_role'),
    path('roles/delete/', manage_is_core_view.delete_role, name='delete_role'),
    path('roles/get/', manage_is_core_view.get_role, name='get_role'),
    path('roles/system/', manage_is_core_view.get_system_roles, name='get_system_roles'),
    path('get-company-and-system/', manage_is_core_view.get_company_and_system, name='get_company_and_system'),
    path('access-rights/system/', manage_is_core_view.get_system_access_rights, name='get_system_access_rights'),
    path('access-rights/save/', manage_is_core_view.save_access_right, name='save_access_right'),
    path('roles/<int:role_id>/functions/', manage_is_objects_view.get_role_functions, name='get_role_functions'),
    path('roles/<int:role_id>/functions/update/', manage_is_core_view.update_role_functions, name='update_role_functions'),
    path('roles-functions/system/', manage_is_core_view.get_roles_functions, name='get_roles_functions'),
    path('access-rights/update-order/', manage_is_core_view.update_access_rights_order, name='update_access_rights_order'),
    path('roles/update-order/', manage_is_core_view.update_roles_order, name='update_roles_order'),
    path('functions/update-order/', manage_is_core_view.update_functions_order, name='update_functions_order'),
    # path('test-role-matrix/<int:role_id>/<int:system_id>/',
    #      lambda request, role_id, system_id: JsonResponse({
    #          'debug': True,
    #          'role_id': role_id,
    #          'system_id': system_id
    #      }),
    #      name='test_role_matrix'),

    path('role-matrix/<int:role_id>/<int:system_id>/', matrix_view.get_role_matrix_for_tooltip, name='get_role_matrix_for_tooltip'),
    path('access-matrix/guide/', matrix_view.access_matrix_guide, name='access_matrix_guide'),
    path('access-matrix/api/guide/translate/', matrix_view.access_matrix_guide_translate, name='access_matrix_guide_translate'),
    path('access-matrix/', matrix_view.access_matrix_is, name='access_matrix_is'),
    path('matrix/<int:system_id>/', matrix_view.get_access_matrix, name='get_access_matrix'),
    path('matrix/update-mapping/', matrix_view.update_matrix_mapping, name='update_matrix_mapping'),
    path('matrix/clear/', matrix_view.clear_matrix, name='clear_matrix'),
    path('matrix/apply-default/', matrix_view.apply_default_matrix, name='apply_default_matrix'),
    path('matrix/objects/<int:system_id>/', matrix_view.get_system_objects, name='get_matrix_system_objects'),
    path('matrix/export-excel/', excel_export.export_access_matrix_excel, name='export_access_matrix_excel'),
    path('matrix/copy-between-environments/', matrix_view.copy_matrix_between_environments, name='copy_matrix_between_environments'),

    path('user-access-request/guide/', access_request_view.user_access_request_guide, name='user_access_request_guide'),
    path('user-access-request/api/guide/translate/', access_request_view.user_access_request_guide_translate, name='user_access_request_guide_translate'),
    path('user-access-request/', access_request_view.user_access_request, name='user_access_request'),
    path('revoke-access-form/', access_request_view.revoke_access_form, name='revoke_access_form'),
    path('get-approved-access-requests/<int:company_id>/<int:system_id>/<str:environment>/<str:user_type>/<str:user_id>/', access_request_view.get_approved_access_requests, name='get_approved_access_requests'),
    path('get-third-party-organizations/<int:company_id>/<int:system_id>/<str:environment>/', access_request_view.get_third_party_organizations, name='get_third_party_organizations'),
    path('get-third-party-users/<int:company_id>/<int:system_id>/<str:environment>/<str:organization_id>/', access_request_view.get_third_party_users_by_org, name='get_third_party_users_by_org'),
    path('user-available-access/', user_available_access_view.user_available_access, name='user_available_access'),
    path('get-available-systems/<int:company_id>/', access_request_view.get_available_systems, name='get_available_systems'),
    path('get-available-objects/<int:system_id>/', access_request_view.get_available_objects, name='get_available_objects'),
    path('get-available-users/<int:system_id>/<int:object_id>/', access_request_view.get_available_users, name='get_available_users'),
    path('get-available-users/<int:system_id>/', access_request_view.get_available_users_by_system, name='get_available_users_by_system'),
    path('get-access-justification-templates/', access_request_view.get_access_justification_templates, name='get_access_justification_templates'),
    path('get-access-records/<int:system_id>/<int:object_id>/<str:user_id>/', access_request_view.get_access_records, name='get_access_records'),
    path('get-access-records-by-system/<int:system_id>/<str:user_id>/', access_request_view.get_access_records_by_system, name='get_access_records_by_system'),
    path('get-user-current-access/<int:system_id>/<int:object_id>/<int:user_id>/', access_request_view.get_user_current_access, name='get_user_current_access'),
    path('get-user-active-requests/<int:system_id>/', access_request_view.get_user_active_requests, name='get_user_active_requests'),
    path('submit-access-request/', access_request_view.submit_access_request, name='submit_access_request'),
    path('get-access-request-edit-data/<int:request_id>/', access_request_view.get_access_request_edit_data, name='get_access_request_edit_data'),
    path('edit-access-request/<int:request_id>/', access_request_view.edit_access_request, name='edit_access_request'),
    path('check-duplicate-request/', access_request_view.check_duplicate_request, name='check_duplicate_request'),
    path('create-third-party-organization/', access_request_view.create_third_party_organization, name='create_third_party_organization'),
    path('create-third-party-user/', access_request_view.create_third_party_user, name='create_third_party_user'),
    path('get-third-party-users/', access_request_view.get_third_party_users, name='get_third_party_users'),
    path('get-request-details/<int:request_id>/', access_request_view.get_request_details, name='get_request_details'),
    path('manage-access-requests/guide/', manage_is_core_view.manage_access_requests_guide, name='manage_access_requests_guide'),
    path('manage-access-requests/api/guide/translate/', manage_is_core_view.manage_access_requests_guide_translate, name='manage_access_requests_guide_translate'),
    path('manage-access-requests/', manage_is_core_view.admin_access_requests, name='manage_access_requests'),
    path('approve-access-requests/', manage_is_core_view.admin_access_requests, name='approve_access_requests'),
    path('export-access-requests-excel/', excel_export.export_access_requests_excel, name='export_access_requests_excel'),


    path('set-admin-status/<int:request_id>/', access_request_view.set_admin_status, name='set_admin_status'),

    path('approver-history/<int:approver_id>/', access_request_view.get_approver_history, name='approver_history'),
    path('set-approver-status/<int:approver_id>/', access_request_view.set_approver_status, name='set_approver_status'),
    path('cancel-request/<int:request_id>/', access_request_view.cancel_access_request, name='cancel_access_request'),
    path('scheduled-syncs/', api_view.scheduled_syncs, name='scheduled_syncs'),
    path('api-request/convert-to-once/', api_view.convert_to_once, name='convert_to_once'),
    path('status-direct/', api_view.direct_service_status, name='direct_service_status'),
    path('check-api-status/', api_view.check_api_status, name='check_api_status'),

    # Access Notification URLs
    path('access-notification/guide/', notification_view.access_notification_guide, name='access_notification_guide'),
    path('access-notification/api/guide/translate/', notification_view.access_notification_guide_translate, name='access_notification_guide_translate'),
    path('access-notification/', notification_view.access_notification, name='access_notification'),
    path('email-config/list/', notification_view.get_email_configurations, name='get_email_configurations'),
    path('email-config/detail/<int:config_id>/', notification_view.get_email_configuration_detail, name='get_email_configuration_detail'),
    path('email-config/save/', notification_view.save_email_configuration, name='save_email_configuration'),
    

    path('email-config/delete/<int:config_id>/', notification_view.delete_email_configuration, name='delete_email_configuration'),
    path('email-config/toggle-status/<int:config_id>/', notification_view.toggle_configuration_status, name='toggle_configuration_status'),
    path('email-config/test-send/', notification_view.test_email_send, name='test_email_send'),
    path('email-config/preview/', notification_view.preview_email_template, name='preview_email_template'),
    
    # Notification History URLs
    path('notification-history/', notification_view.get_notification_history, name='get_notification_history'),
    path('notification-history/retry/<int:notification_id>/', notification_view.retry_failed_notification, name='retry_failed_notification'),

    # Object Roles & Functions URLs
    path('object-roles-functions/<int:object_id>/', manage_is_objects_view.get_object_roles_functions, name='get_object_roles_functions'),
    path('object-role-functions/<int:object_id>/<int:role_id>/', manage_is_objects_view.get_object_role_functions, name='get_object_role_functions'),
    path('object-role-functions/<int:object_id>/<int:role_id>/update/', manage_is_objects_view.update_object_role_functions, name='update_object_role_functions'),
    
    # Environment Copy URLs
    path('copy-environment-data/', manage_is_objects_view.copy_environment_data, name='copy_environment_data'),

    # Objects export (Object Management)
    path('objects/export-excel/', excel_export.export_objects_excel, name='export_objects_excel'),
    
    # Admin URLs for bulk deletion
    path('admin/confirm-delete-all-requests/', admin_views.confirm_delete_all_requests, name='admin_confirm_delete_all_requests'),
    path('admin/delete-requests-by-filter/', admin_views.delete_requests_by_filter, name='admin_delete_requests_by_filter'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)