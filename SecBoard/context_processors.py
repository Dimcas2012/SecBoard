from app_cabinet.views import (
    quiz_result_link, 
    show_assets_link,
    show_software_register_link,
    show_external_media_register_link,
    show_access_matrix_link,
    show_access_records_link,
    show_access_config_is_link,
    show_manage_ar_link,
    show_user_access_request_link,
    show_notification_settings_link,
    show_api_link,
    show_incidents_link, 
    show_keys_cert_link, 
    show_fim_dashboard_link,
    show_gophish_link,
    show_risk_assessment_link, 
    show_docs_link, 
    show_pcidss_link, 
    show_iso27002_link, 
    show_risk_assessment_config_link,
    show_quiz_manager_link,
    show_page_manager_link,
    show_legdocs_link,
    show_org_chart_link,
    show_mandatory_processes_link,
    show_gdpr_compliance_link,
    show_compliance_link,
    show_local_compliance_link,
    show_internal_compliance_link,
    show_cif_link,
    show_integration_link,
)
from app_cabinet.permissions import has_permission

def menu_visibility(request):
    """
    Context processor that adds menu visibility flags to all templates
    """
    from app_access.matrix_view import has_any_isam_access
    from app_conf.models import AccessOption
    
    # Check if user has options access through AccessOption model
    is_Options_member = AccessOption.user_has_options_access(request.user) if request.user.is_authenticated else False
    
    # Check if user has any ISAM access through AccessISAM model
    is_ISAM_member = has_any_isam_access(request.user)

    # AccessOptions permissions
    cabinet_access = {}
    if request.user.is_authenticated:
        cabinet_access = {
            'has_access_users': has_permission(request.user, 'users', 'view'),
            'has_access_groups': has_permission(request.user, 'groups', 'view'),
            'has_access_org_structure': has_permission(request.user, 'org_structure', 'view'),
            'has_access_org_chart': has_permission(request.user, 'org_chart', 'view'),
            'has_access_site_statistics': has_permission(request.user, 'site_statistics', 'view'),
        }

    cif_permissions = {}
    if request.user.is_authenticated:
        from app_cif.utils import get_user_cif_permissions
        cif_permissions = get_user_cif_permissions(request.user)

    return {
        'is_ISAM_member': is_ISAM_member,
        'is_Options_member': is_Options_member,
        'cabinet_access': cabinet_access,
        'quiz_result_link': quiz_result_link(request),
        'show_assets_link': show_assets_link(request),
        'show_software_register_link': show_software_register_link(request),
        'show_external_media_register_link': show_external_media_register_link(request),
        'show_access_matrix_link': show_access_matrix_link(request),
        'show_access_records_link': show_access_records_link(request),
        'show_access_config_is_link': show_access_config_is_link(request),
        'show_manage_ar_link': show_manage_ar_link(request),
        'show_user_access_request_link': show_user_access_request_link(request),
        'show_notification_settings_link': show_notification_settings_link(request),
        'show_api_link': show_api_link(request),
        'show_incidents_link': show_incidents_link(request),
        'show_keys_cert_link': show_keys_cert_link(request),
        'show_fim_dashboard_link': show_fim_dashboard_link(request),
        'show_gophish_link': show_gophish_link(request),
        'access_risk_assessment_show_link': show_risk_assessment_link(request.user),
        'show_docs_link': show_docs_link(request),
        'show_legdocs_link': show_legdocs_link(request),
        'show_pcidss_link': show_pcidss_link(request),
        'show_iso27002_link': show_iso27002_link(request),
        'show_risk_assessment_config_link': show_risk_assessment_config_link(request),
        'show_quiz_manager_link': show_quiz_manager_link(request),
        'show_page_manager_link': show_page_manager_link(request),
        'show_org_chart_link': show_org_chart_link(request),
        'show_mandatory_processes_link': show_mandatory_processes_link(request),
        'show_gdpr_compliance_link': show_gdpr_compliance_link(request),
        'compliance_has_access': show_compliance_link(request),
        'local_compliance_has_access': show_local_compliance_link(request),
        'internal_compliance_has_access': show_internal_compliance_link(request),
        'cif_has_access': show_cif_link(request),
        'cif_permissions': cif_permissions,
        'show_integration_link': show_integration_link(request),
    } 