#  SecBoard\SecBoard\app_risk\urls.py
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import ensure_csrf_cookie
from . import views
from .views import set_user_timezone
from . import ai_views
from . import vulnerability_views
from . import risk_assessment_views
from . import report_views

 


urlpatterns = [


    # Risk assessment
    path('risk_assessment_config/', views.risk_assessment_config, name='risk_assessment_config'),
    path('risk_assessment_config/guide/', views.risk_assessment_config_guide, name='risk_assessment_config_guide'),
    path('risk_assessment_config/api/guide/translate/', views.risk_assessment_config_guide_translate, name='risk_assessment_config_guide_translate'),
    path('edit_threat/<int:threat_id>/', views.edit_threat, name='edit_threat'),
    path('delete_threat/<int:threat_id>/', views.delete_threat, name='delete_threat'),
    path('get_threats/', views.get_threats, name='get_threats'),
    path('get_threat_translation_countries/', views.get_threat_translation_countries, name='get_threat_translation_countries'),
    path('get_threat_translation_detail/', views.get_threat_translation_detail, name='get_threat_translation_detail'),
    path('save_threat_translation/', views.save_threat_translation, name='save_threat_translation'),
    path('translate_threat_preview/', ai_views.translate_threat_preview, name='translate_threat_preview'),
    path('calculate_probability/', views.calculate_probability, name='calculate_probability'),
    path('translate/', views.translate_text, name='translate_text'),

    path('add_vulnerability/', views.add_vulnerability, name='add_vulnerability'),
    path('edit_vulnerability/<int:vulnerability_id>/', views.edit_vulnerability, name='edit_vulnerability'),
    path('delete_vulnerability/<int:vulnerability_id>/', ensure_csrf_cookie(views.delete_vulnerability), name='delete_vulnerability'),
    path('delete_selected_vulnerabilities/', ensure_csrf_cookie(views.delete_selected_vulnerabilities), name='delete_selected_vulnerabilities'),
    path('get_asset_groups/', views.get_asset_groups, name='get_asset_groups'),
    path('get_vulnerabilities/', views.get_vulnerabilities, name='get_vulnerabilities'),
    path('analyze_threats_ai/', ai_views.analyze_threats_ai, name='analyze_threats_ai'),
    path('analyze_multiply_threats_ai/<int:vulnerability_id>/', ai_views.analyze_multiply_threats_ai, name='analyze_multiply_threats_ai'),
    path('generate_vulnerabilities_ai/', ai_views.generate_vulnerabilities_ai, name='generate_vulnerabilities_ai'),
    path('generate_risk_mitigation_ai/', ai_views.generate_risk_mitigation_ai, name='generate_risk_mitigation_ai'),
    path('get_vulnerability_translation_countries/', vulnerability_views.get_vulnerability_translation_countries, name='get_vulnerability_translation_countries'),
    path('get_vulnerability_translation_detail/', vulnerability_views.get_vulnerability_translation_detail, name='get_vulnerability_translation_detail'),
    path('translate_vulnerability_ai_preview/', ai_views.translate_vulnerability_ai_preview, name='translate_vulnerability_ai_preview'),
    path('save_vulnerability_translation/', vulnerability_views.save_vulnerability_translation, name='save_vulnerability_translation'),
    path('translate_vulnerability_ai/', ai_views.translate_vulnerability_ai, name='translate_vulnerability_ai'),
    path('save_generated_vulnerabilities/', ai_views.save_generated_vulnerabilities, name='save_generated_vulnerabilities'),
    path('check_ai_provider/', ai_views.check_ai_provider, name='check_ai_provider'),
    path('translate-vulnerability-fields/', views.translate_vulnerability_fields, name='translate_vulnerability_fields'),
    path('translate-vulnerability/<int:vulnerability_id>/', views.translate_vulnerability, name='translate_vulnerability'),
    path('export-vulnerabilities-csv/', views.export_vulnerabilities_csv, name='export_vulnerabilities_csv'),
    path('export-vulnerabilities-xlsx/', views.export_vulnerabilities_xlsx, name='export_vulnerabilities_xlsx'),
    path('import-vulnerabilities-csv/', views.import_vulnerabilities_csv, name='import_vulnerabilities_csv'),
    path('download-vulnerabilities-template/', views.download_vulnerabilities_template, name='download_vulnerabilities_template'),

    path('get_vulnerability/', views.get_vulnerability, name='get_vulnerability'),
    path('update_vulnerability/', views.update_vulnerability, name='update_vulnerability'),

    path('risk_assessment/', views.risk_assessment, name='risk_assessment'),
    path('risk_assessment/guide/', views.risk_assessment_guide, name='risk_assessment_guide'),
    path('risk_assessment/api/guide/translate/', views.risk_assessment_guide_translate, name='risk_assessment_guide_translate'),
    path('asset-vulnerabilities-data/', views.asset_vulnerabilities_data, name='asset_vulnerabilities_data'),
    path('get-asset-vulnerabilities/', views.get_asset_vulnerabilities, name='get_asset_vulnerabilities'),
    path('save-asset-vulnerabilities/', views.save_asset_vulnerabilities, name='save_asset_vulnerabilities'),
    path('get-software-vulnerabilities/', views.get_software_vulnerabilities, name='get_software_vulnerabilities'),
    path('save-software-vulnerabilities/', views.save_software_vulnerabilities, name='save_software_vulnerabilities'),
    path('get-software-risks/', views.get_software_risks, name='get_software_risks'),
    path('get-external-media-vulnerabilities/', views.get_external_media_vulnerabilities, name='get_external_media_vulnerabilities'),
    path('save-external-media-vulnerabilities/', views.save_external_media_vulnerabilities, name='save_external_media_vulnerabilities'),
    path('get-external-media-risks/', views.get_external_media_risks, name='get_external_media_risks'),

    path('risk-calculation-data/', views.risk_calculation_data, name='risk_calculation_data'),
    path('export-asset-vulnerabilities/', views.export_asset_vulnerabilities, name='export_asset_vulnerabilities'),
    path('export-risk-calculation/', views.export_risk_calculation, name='export_risk_calculation'),
    path('export-risk-details/', views.export_risk_details, name='export_risk_details'),
    path('get-asset-risks/', views.get_asset_risks, name='get_asset_risks'),
    path('get_asset_groups_and_types/', views.get_asset_groups_and_types, name='get_asset_groups_and_types'),


    # path('error/', views.error_page, name='error_page'),
    # path('api-auth/', include('rest_framework.urls')),
    path('get_server_time/', views.get_server_time, name='get_server_time'),
    path('set_user_timezone/', set_user_timezone, name='set_user_timezone'),




    path('get-risk-treatment-data/', views.get_risk_treatment_data, name='get_risk_treatment_data'),
    path('update-risk-treatment-data/', views.update_risk_treatment_data, name='update_risk_treatment_data'),
    path('save-all-risk-treatments/', views.save_all_risk_treatments, name='save_all_risk_treatments'),
    path('bulk-update-risk-treatments/', risk_assessment_views.bulk_update_risk_treatments, name='bulk_update_risk_treatments'),
    path('clear-risk-treatments/', views.clear_risk_treatments, name='clear_risk_treatments'),
    path('export-risk-treatments/', views.export_risk_treatments, name='export_risk_treatments'),
    path('risk-assessment-dashboard/', views.risk_assessment_dashboard, name='risk_assessment_dashboard'),

    path('generate_note_ai/', ai_views.generate_note_ai, name='generate_note_ai'),
    path('generate_description_ai/', ai_views.generate_description_ai, name='generate_description_ai'),
    path('search_pcidss_requirement/', ai_views.search_pcidss_requirement, name='search_pcidss_requirement'),
    path('search_iso27001_requirement/', ai_views.search_iso27001_requirement, name='search_iso27001_requirement'),
    path('check_ai_provider/', ai_views.check_ai_provider, name='check_ai_provider'),

    path('risk-treatment/<int:treatment_id>/details/', vulnerability_views.get_treatment_details, name='treatment_details'),

    path('get_treatment_reference_data/', risk_assessment_views.get_treatment_reference_data, name='get_treatment_reference_data'),
    path('get_impact_levels/', risk_assessment_views.get_impact_levels, name='get_impact_levels'),
    path('impact-settings-summary/', risk_assessment_views.impact_settings_summary, name='impact_settings_summary'),

    # Add these new URLs for interactive dashboard features
    path('api/companies/', risk_assessment_views.get_companies_api, name='get_companies_api'),
    path('api/dashboard/filters/', risk_assessment_views.get_dashboard_filtered_data, name='get_dashboard_filtered_data'),
    path('api/dashboard/drilldown/', risk_assessment_views.get_drilldown_data, name='get_drilldown_data'),
    path('api/dashboard/realtime/', risk_assessment_views.get_realtime_updates, name='get_realtime_updates'),

    # Report generation URLs
    path('risk-report/', views.risk_report, name='risk_report'),
    path('risk-report/guide/', views.risk_report_guide, name='risk_report_guide'),
    path('risk-report/api/guide/translate/', views.risk_report_guide_translate, name='risk_report_guide_translate'),
    path('generate-risk-report/', report_views.generate_risk_report, name='generate_risk_report'),
    path('preview-risk-report/', report_views.preview_risk_report, name='preview_risk_report'),
    path('generate-risk-report-from-profile/', report_views.generate_risk_report_from_profile, name='generate_risk_report_from_profile'),
    path('preview-risk-report-page/', report_views.preview_risk_report_page, name='preview_risk_report_page'),
    path('preview-risk-report-from-profile-page/', report_views.preview_risk_report_from_profile_page, name='preview_risk_report_from_profile_page'),
    path('preview-email-content/', report_views.preview_email_content, name='preview_email_content'),
    path('download-attachment/<uuid:attachment_id>/', report_views.download_scheduled_report_attachment, name='download_scheduled_report_attachment'),
    path('scheduled-reports/execution/<uuid:execution_id>/view/', report_views.view_scheduled_report_snapshot, name='view_scheduled_report_snapshot'),
    path('preview-risk-report-from-profile/', report_views.preview_risk_report_from_profile, name='preview_risk_report_from_profile'),


    # Scheduled Reports
    path('scheduled-reports/', report_views.get_scheduled_reports, name='get_scheduled_reports'),
    path('scheduled-reports/create/', report_views.create_scheduled_report, name='create_scheduled_report'),
    path('scheduled-reports/<uuid:report_id>/', report_views.get_scheduled_report_details, name='get_scheduled_report_details'),
    path('scheduled-reports/<uuid:report_id>/update/', report_views.update_scheduled_report, name='update_scheduled_report'),
    path('scheduled-reports/<uuid:report_id>/delete/', report_views.delete_scheduled_report, name='delete_scheduled_report'),
    path('scheduled-reports/<uuid:report_id>/send-now/', report_views.send_scheduled_report_now, name='send_scheduled_report_now'),
    path('scheduled-reports/<uuid:report_id>/history/', report_views.get_scheduled_report_history, name='get_scheduled_report_history'),
    path('scheduled-reports/execution/<uuid:execution_id>/download/', report_views.download_scheduled_report_file, name='download_scheduled_report_file'),
    path('generate-risk-report-from-scheduled-execution/', report_views.generate_risk_report_from_scheduled_execution, name='generate_risk_report_from_scheduled_execution'),
    path('cabinet-users/', report_views.get_cabinet_users, name='get_cabinet_users'),

    # Report Profiles API
    path('report-profiles/', views.get_report_profiles, name='get_report_profiles'),
    path('report-profiles/create/', views.create_report_profile, name='create_report_profile'),
    path('report-profiles/<uuid:profile_id>/', views.get_report_profile_details, name='get_report_profile_details'),
    path('report-profiles/<uuid:profile_id>/update/', views.update_report_profile, name='update_report_profile'),
    path('report-profiles/<uuid:profile_id>/delete/', views.delete_report_profile, name='delete_report_profile'),
    path('report-profiles/<uuid:profile_id>/duplicate/', views.duplicate_report_profile, name='duplicate_report_profile'),
    path('report-profiles/<uuid:profile_id>/use/', views.use_report_profile, name='use_report_profile'),
    path('report-profiles/send-link/', report_views.send_profile_link, name='send_profile_link'),

    # Acceptable Risk URLs
    path('acceptable-risk/data/', views.get_acceptable_risk_data, name='get_acceptable_risk_data'),
    path('acceptable-risk/save/', views.save_acceptable_risk, name='save_acceptable_risk'),
    path('acceptable-risk/delete/<int:risk_id>/', views.delete_acceptable_risk, name='delete_acceptable_risk'),
    path('acceptable-risk/reference-data/', views.get_acceptable_risk_reference_data, name='get_acceptable_risk_reference_data'),

    # Allowed Software URLs
    path('allowed-software/data/', views.get_allowed_software_data, name='get_allowed_software_data'),
    path('allowed-software/save/', views.save_allowed_software, name='save_allowed_software'),
    path('allowed-software/delete/<int:sw_id>/', views.delete_allowed_software, name='delete_allowed_software'),
    path('allowed-software/reference-data/', views.get_allowed_software_reference_data, name='get_allowed_software_reference_data'),

    # Treatment Attachments URLs
    path('upload-treatment-attachment/', risk_assessment_views.upload_treatment_attachment, name='upload_treatment_attachment'),
    path('delete-treatment-attachment/', risk_assessment_views.delete_treatment_attachment, name='delete_treatment_attachment'),

    # Manual Risk Level Editing URLs
    path('get-risk-levels-for-editing/', risk_assessment_views.get_risk_levels_for_editing, name='get_risk_levels_for_editing'),
    path('update-risk-level-manual/', risk_assessment_views.update_risk_level_manual, name='update_risk_level_manual'),

    # Treatment History URLs
    path('get-treatment-history/', risk_assessment_views.get_treatment_history, name='get_treatment_history'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)