from django.urls import path
from django.shortcuts import render
from django.views.generic.base import RedirectView
from . import views
from . import process_views

app_name = 'compliance'

urlpatterns = [
    # Dashboard
    path('guide/', views.framework_compliance_guide, name='framework_compliance_guide'),
    path('api/guide/translate/', views.framework_compliance_guide_translate, name='framework_compliance_guide_translate'),
    path('', RedirectView.as_view(pattern_name='compliance:dashboard', permanent=False)),
    
    # Local Compliance Dashboard
    path('local/guide/', views.local_compliance_guide, name='local_compliance_guide'),
    path('local/api/guide/translate/', views.local_compliance_guide_translate, name='local_compliance_guide_translate'),
    path('local/', views.local_compliance_dashboard, name='local_compliance'),
    
    # Internal Compliance Dashboard
    path('internal/guide/', views.internal_compliance_guide, name='internal_compliance_guide'),
    path('internal/api/guide/translate/', views.internal_compliance_guide_translate, name='internal_compliance_guide_translate'),
    path('internal/', views.internal_compliance_dashboard, name='internal_compliance'),
    
    # Internal Requirements Templates endpoints
    path('internal/requirements/', views.internal_requirements_library, name='internal_requirements_library'),
    path('internal/requirements/create/', views.internal_requirement_template_create, name='internal_requirement_template_create'),
    path('internal/requirements/<int:requirement_id>/', views.internal_requirement_template_detail, name='internal_requirement_template_detail'),
    path('internal/requirements/<int:requirement_id>/edit/', views.internal_requirement_template_edit, name='internal_requirement_template_edit'),
    path('internal/requirements/<int:requirement_id>/delete/', views.internal_requirement_template_delete, name='internal_requirement_template_delete'),
    path('internal/requirements/export/excel/', views.internal_requirements_export_excel, name='internal_requirements_export_excel'),
    path('internal/requirements/import/excel/', views.internal_requirements_import_excel, name='internal_requirements_import_excel'),
    path('internal/requirements/import/ai/', views.internal_requirements_import_ai, name='internal_requirements_import_ai'),
    path('internal/requirements/save-ai/', views.internal_requirements_save_ai, name='internal_requirements_save_ai'),
    path('internal/requirements/excel-template/', views.internal_requirements_excel_template, name='internal_requirements_excel_template'),
    
    # Internal Requirement Notes
    path('internal/requirements/<int:requirement_id>/notes/create/', views.internal_requirement_note_create, name='internal_requirement_note_create'),
    path('internal/requirement-notes/<int:note_id>/update/', views.internal_requirement_note_update, name='internal_requirement_note_update'),
    path('internal/requirement-notes/<int:note_id>/delete/', views.internal_requirement_note_delete, name='internal_requirement_note_delete'),
    path('internal/requirement-note-attachments/<int:attachment_id>/delete/', views.internal_requirement_note_attachment_delete, name='internal_requirement_note_attachment_delete'),
    
    # Internal Control Detail
    path('internal/controls/<int:control_id>/', views.internal_control_detail, name='internal_control_detail'),
    
    # Internal Requirement Categories & Controls CRUD
    path('internal/requirements/<int:requirement_id>/categories/create/', views.internal_requirement_category_create, name='internal_requirement_category_create'),
    path('internal/requirements/categories/<int:category_id>/update/', views.internal_requirement_category_update, name='internal_requirement_category_update'),
    path('internal/requirements/categories/<int:category_id>/delete/', views.internal_requirement_category_delete, name='internal_requirement_category_delete'),
    path('internal/requirements/<int:requirement_id>/controls/create/', views.internal_requirement_control_create, name='internal_requirement_control_create'),
    path('internal/controls/<int:control_id>/update/', views.internal_requirement_control_update, name='internal_requirement_control_update'),
    path('internal/controls/<int:control_id>/delete/', views.internal_requirement_control_delete, name='internal_requirement_control_delete'),
    
    # Internal Control Operations
    path('internal/controls/<int:control_id>/assign/', views.internal_control_assign, name='internal_control_assign'),
    path('internal/controls/<int:control_id>/set-responsible/', views.internal_control_set_responsible, name='internal_control_set_responsible'),
    path('internal/controls/<int:control_id>/update-status/', views.internal_control_update_status, name='internal_control_update_status'),
    path('internal/control-assignments/<int:assignment_id>/delete/', views.internal_control_assignment_delete, name='internal_control_assignment_delete'),
    path('internal/controls/<int:control_id>/evidences/create/', views.internal_control_evidence_create, name='internal_control_evidence_create'),
    path('internal/control-evidences/<int:evidence_id>/edit/', views.internal_control_evidence_edit, name='internal_control_evidence_edit'),
    path('internal/control-evidences/<int:evidence_id>/update/', views.internal_control_evidence_update, name='internal_control_evidence_update'),
    path('internal/control-evidences/<int:evidence_id>/delete/', views.internal_control_evidence_delete, name='internal_control_evidence_delete'),
    path('internal/control-evidences/<int:evidence_id>/approve/', views.internal_control_evidence_approve, name='internal_control_evidence_approve'),
    path('internal/control-evidences/<int:evidence_id>/reject/', views.internal_control_evidence_reject, name='internal_control_evidence_reject'),
    path('internal/controls/<int:control_id>/notes/create/', views.internal_control_note_create, name='internal_control_note_create'),
    path('internal/control-notes/<int:note_id>/delete/', views.internal_control_note_delete, name='internal_control_note_delete'),
    path('internal/control-notes/<int:note_id>/update/', views.internal_control_note_update, name='internal_control_note_update'),
    path('internal/note-attachments/<int:attachment_id>/delete/', views.internal_control_note_attachment_delete, name='internal_control_note_attachment_delete'),
    path('internal/control-mapping/create/', views.internal_control_mapping_create, name='internal_control_mapping_create'),
    path('internal/control-mapping/<int:mapping_id>/delete/', views.internal_control_mapping_delete, name='internal_control_mapping_delete'),
    
    # Framework URLs
    path('frameworks/', views.compliance_dashboard, name='dashboard'),
    path('frameworks/templates/', views.framework_list, name='framework_list'),
    path('frameworks/instances/', views.framework_instances_list, name='framework_instances_list'),
    path('frameworks/new/', views.framework_create_form, name='framework_create_form'),
    path('frameworks/<int:framework_id>/', views.framework_detail, name='framework_detail'),
    path('frameworks/<int:framework_id>/edit/', views.framework_edit_form, name='framework_edit_form'),
    path('frameworks/create/', views.framework_create, name='framework_create'),
    path('frameworks/<int:framework_id>/update/', views.framework_update, name='framework_update'),
    path('frameworks/<int:framework_id>/delete/', views.framework_delete, name='framework_delete'),
    
    # Category URLs
    path('frameworks/<int:framework_id>/categories/create/', views.category_create, name='category_create'),
    path('categories/<int:category_id>/update/', views.category_update, name='category_update'),
    path('categories/<int:category_id>/delete/', views.category_delete, name='category_delete'),
    
    # Control URLs
    path('controls/<int:control_id>/', views.control_detail, name='control_detail'),
    path('categories/<int:category_id>/controls/create/', views.control_create, name='control_create'),
    path('controls/<int:control_id>/update/', views.control_update, name='control_update'),
    path('controls/<int:control_id>/delete/', views.control_delete, name='control_delete'),
    path('controls/<int:control_id>/verify/', views.control_verify, name='control_verify'),
    path('controls/<int:control_id>/assign/', views.control_assign, name='control_assign'),
    path('controls/<int:control_id>/set-responsible/', views.control_set_responsible, name='control_set_responsible'),
    path('assignments/<int:assignment_id>/delete/', views.assignment_delete, name='assignment_delete'),
    
    # Evidence URLs
    path('controls/<int:control_id>/evidences/', views.evidence_list, name='evidence_list'),
    path('controls/<int:control_id>/evidences/create/', views.evidence_create, name='evidence_create'),
    path('evidences/<int:evidence_id>/edit/', views.evidence_edit, name='evidence_edit'),
    path('evidences/<int:evidence_id>/update/', views.evidence_update, name='evidence_update'),
    path('evidences/<int:evidence_id>/delete/', views.evidence_delete, name='evidence_delete'),
    path('evidences/<int:evidence_id>/approve/', views.evidence_approve, name='evidence_approve'),
    path('evidences/<int:evidence_id>/reject/', views.evidence_reject, name='evidence_reject'),
    
    # Control Notes URLs
    path('controls/<int:control_id>/notes/create/', views.note_create, name='note_create'),
    path('notes/<int:note_id>/delete/', views.note_delete, name='note_delete'),
    path('notes/<int:note_id>/update/', views.note_update, name='note_update'),
    path('note-attachments/<int:attachment_id>/delete/', views.control_note_attachment_delete, name='control_note_attachment_delete'),
    
    # Control Mapping
    path('control-mapping/', views.control_mapping_view, name='control_mapping'),
    path('control-mapping/create/', views.control_mapping_create, name='control_mapping_create'),
    path('control-mapping/<int:mapping_id>/delete/', views.control_mapping_delete, name='control_mapping_delete'),
    
    # AJAX endpoints
    path('api/frameworks/<int:framework_id>/stats/', views.get_framework_stats, name='get_framework_stats'),
    path('api/controls/<int:control_id>/evidences/', views.get_control_evidences, name='get_control_evidences'),
    path('api/controls/search/', views.search_controls, name='search_controls'),
    path('api/country/<int:country_id>/companies/', views.get_country_companies, name='get_country_companies'),
    path('api/translate/', views.translate_to_country_language, name='translate_to_country_language'),
    path('api/internal/company-documents/', views.get_internal_company_documents, name='get_internal_company_documents'),
    
    # Export/Import endpoints
    path('frameworks/<int:framework_id>/export/excel/', views.framework_export_excel, name='framework_export_excel'),
    path('frameworks/import/excel/', views.framework_import_excel, name='framework_import_excel'),
    path('frameworks/excel-template/', views.framework_excel_template, name='framework_excel_template'),
    path('frameworks/<int:framework_id>/export/pdf/', views.export_framework_pdf, name='export_framework_pdf'),
    path('controls/<int:control_id>/export/pdf/', views.export_control_pdf, name='export_control_pdf'),
    
    # Framework Notes (company instances)
    path('frameworks/<int:framework_id>/notes/create/', views.framework_note_create, name='framework_note_create'),
    path('framework-notes/<int:note_id>/update/', views.framework_note_update, name='framework_note_update'),
    path('framework-notes/<int:note_id>/delete/', views.framework_note_delete, name='framework_note_delete'),
    path('framework-note-attachments/<int:attachment_id>/delete/', views.framework_note_attachment_delete, name='framework_note_attachment_delete'),
    
    # Bulk Operations endpoints (Templates)
    path('frameworks/bulk/apply/', views.bulk_apply_frameworks, name='bulk_apply_frameworks'),
    path('frameworks/bulk/change-status/', views.bulk_change_status, name='bulk_change_status'),
    path('frameworks/bulk/export/', views.bulk_export_frameworks, name='bulk_export_frameworks'),
    path('frameworks/bulk/duplicate/', views.bulk_duplicate_frameworks, name='bulk_duplicate_frameworks'),
    path('frameworks/bulk/delete/', views.bulk_delete_frameworks, name='bulk_delete_frameworks'),
    
    # Bulk Operations endpoints (Instances)
    path('instances/bulk/change-status/', views.bulk_change_instance_status, name='bulk_change_instance_status'),
    path('instances/bulk/toggle-mandatory/', views.bulk_toggle_mandatory, name='bulk_toggle_mandatory'),
    path('instances/bulk/export/', views.bulk_export_instances, name='bulk_export_instances'),
    path('instances/bulk/delete/', views.bulk_delete_instances, name='bulk_delete_instances'),
    
    # Framework Lifecycle endpoints
    path('frameworks/<int:framework_id>/schedule-review/', views.schedule_review, name='schedule_review'),
    path('frameworks/<int:framework_id>/mark-reviewed/', views.mark_reviewed, name='mark_reviewed'),
    path('frameworks/<int:framework_id>/archive/', views.archive_framework, name='archive_framework'),
    
    # Framework Translation endpoints
    path('frameworks/translation/start/', views.start_framework_translation, name='start_framework_translation'),
    path('frameworks/translation/progress/', views.get_framework_translation_progress, name='get_framework_translation_progress'),
    path('frameworks/translation/stop/', views.stop_framework_translation, name='stop_framework_translation'),
    
    # Local Requirements Templates endpoints
    path('local/templates/', views.local_requirements_library, name='local_requirements_library'),
    path('local/requirements/instances/', views.local_requirement_instances_list, name='local_requirement_instances_list'),
    path('local/requirements/instances/<int:requirement_id>/', views.local_requirement_instance_detail, name='local_requirement_instance_detail'),

    # Local Requirement Notes (for instances)
    path('local/requirements/instances/<int:requirement_id>/notes/create/', views.local_requirement_note_create, name='local_requirement_note_create'),
    path('local/requirement-notes/<int:note_id>/update/', views.local_requirement_note_update, name='local_requirement_note_update'),
    path('local/requirement-notes/<int:note_id>/delete/', views.local_requirement_note_delete, name='local_requirement_note_delete'),
    path('local/requirement-note-attachments/<int:attachment_id>/delete/', views.local_requirement_note_attachment_delete, name='local_requirement_note_attachment_delete'),

    path('local/templates/create/', views.local_requirement_template_create, name='local_requirement_template_create'),
    path('local/templates/<int:requirement_id>/', views.local_requirement_template_detail, name='local_requirement_template_detail'),
    path('local/templates/<int:requirement_id>/edit/', views.local_requirement_template_edit, name='local_requirement_template_edit'),
    path('local/templates/<int:requirement_id>/export/excel/', views.local_requirement_template_export_excel, name='local_requirement_template_export_excel'),
    path('local/templates/<int:requirement_id>/delete/', views.local_requirement_template_delete, name='local_requirement_template_delete'),
    path('local/templates/<int:requirement_id>/apply/', views.local_requirement_template_apply, name='local_requirement_template_apply'),
    path('local/templates/export/excel/', views.local_requirements_export_excel, name='local_requirements_export_excel'),
    path('local/templates/import/excel/', views.local_requirements_import_excel, name='local_requirements_import_excel'),
    path('local/templates/excel-template/', views.local_requirements_excel_template, name='local_requirements_excel_template'),
    path('local/templates/<int:requirement_id>/categories/create/', views.local_requirement_category_create, name='local_requirement_category_create'),
    path('local/templates/categories/<int:category_id>/update/', views.local_requirement_category_update, name='local_requirement_category_update'),
    path('local/templates/categories/<int:category_id>/delete/', views.local_requirement_category_delete, name='local_requirement_category_delete'),
    path('local/templates/<int:requirement_id>/controls/create/', views.local_requirement_control_create, name='local_requirement_control_create'),
    path('local/controls/<int:control_id>/update/', views.local_requirement_control_update, name='local_requirement_control_update'),
    path('local/controls/<int:control_id>/delete/', views.local_requirement_control_delete, name='local_requirement_control_delete'),

    # Redirects: keep old /local/requirements/ URLs working
    path('local/requirements/', RedirectView.as_view(pattern_name='compliance:local_requirements_library', permanent=True)),
    path('local/requirements/create/', RedirectView.as_view(pattern_name='compliance:local_requirement_template_create', permanent=True)),
    path('local/requirements/export/excel/', RedirectView.as_view(pattern_name='compliance:local_requirements_export_excel', permanent=True)),
    path('local/requirements/import/excel/', RedirectView.as_view(pattern_name='compliance:local_requirements_import_excel', permanent=True)),
    path('local/requirements/excel-template/', RedirectView.as_view(pattern_name='compliance:local_requirements_excel_template', permanent=True)),

    # Local Control Instance Detail & Operations
    path('local/instance-controls/<int:control_id>/', views.local_control_detail, name='local_control_detail'),
    path('local/instance-controls/<int:control_id>/update/', views.local_control_update, name='local_control_update'),
    path('local/instance-controls/<int:control_id>/assign/', views.local_control_assign, name='local_control_assign'),
    path('local/instance-controls/<int:control_id>/set-responsible/', views.local_control_set_responsible, name='local_control_set_responsible'),
    path('local/instance-assignments/<int:assignment_id>/delete/', views.local_control_assignment_delete, name='local_control_assignment_delete'),
    path('local/instance-controls/<int:control_id>/evidences/create/', views.local_control_evidence_create, name='local_control_evidence_create'),
    path('local/instance-evidences/<int:evidence_id>/edit/', views.local_control_evidence_edit, name='local_control_evidence_edit'),
    path('local/instance-evidences/<int:evidence_id>/update/', views.local_control_evidence_update, name='local_control_evidence_update'),
    path('local/instance-evidences/<int:evidence_id>/delete/', views.local_control_evidence_delete, name='local_control_evidence_delete'),
    path('local/instance-evidences/<int:evidence_id>/approve/', views.local_control_evidence_approve, name='local_control_evidence_approve'),
    path('local/instance-evidences/<int:evidence_id>/reject/', views.local_control_evidence_reject, name='local_control_evidence_reject'),
    path('local/instance-controls/<int:control_id>/notes/create/', views.local_control_note_create, name='local_control_note_create'),
    path('local/instance-notes/<int:note_id>/delete/', views.local_control_note_delete, name='local_control_note_delete'),
    path('local/instance-notes/<int:note_id>/update/', views.local_control_note_update, name='local_control_note_update'),
    path('local/instance-note-attachments/<int:attachment_id>/delete/', views.local_control_note_attachment_delete, name='local_control_note_attachment_delete'),
    path('local/instance-mapping/create/', views.local_control_mapping_create, name='local_control_mapping_create'),
    path('local/instance-mapping/<int:mapping_id>/delete/', views.local_control_mapping_delete, name='local_control_mapping_delete'),
    
    # Mandatory Processes URLs
    path('mandatory-processes/', process_views.mandatory_processes, name='mandatory_processes'),
    path('mandatory-processes/guide/', process_views.mandatory_processes_guide, name='mandatory_processes_guide'),
    path('mandatory-processes/api/guide/translate/', process_views.mandatory_processes_guide_translate, name='mandatory_processes_guide_translate'),
    path('mandatory-processes/add/', process_views.add_mandatory_process, name='add_mandatory_process'),
    path('mandatory-processes/<int:process_id>/', process_views.get_mandatory_process, name='get_mandatory_process'),
    path('mandatory-processes/<int:process_id>/edit/', process_views.edit_mandatory_process, name='edit_mandatory_process'),
    path('mandatory-processes/<int:process_id>/delete/', process_views.delete_mandatory_process, name='delete_mandatory_process'),
    path('mandatory-processes/<int:process_id>/complete/', process_views.mark_process_completed, name='mark_process_completed'),
    path('mandatory-processes/<int:process_id>/last-execution/', process_views.get_process_last_execution, name='get_process_last_execution'),
    path('mandatory-processes/<int:process_id>/history/', process_views.process_execution_history, name='process_execution_history'),
    path('mandatory-processes/executions/<int:execution_id>/evidence/update/', process_views.update_execution_evidence, name='update_execution_evidence'),
    path('mandatory-processes/<int:process_id>/reminder-recipients/', process_views.get_process_reminder_recipients, name='get_process_reminder_recipients'),
    path('mandatory-processes/send-reminder/', process_views.send_process_reminder, name='send_process_reminder'),
    path('mandatory-processes/export/', process_views.export_mandatory_processes, name='export_mandatory_processes'),
    path('process-attachments/<int:attachment_id>/delete/', process_views.delete_process_attachment, name='delete_process_attachment'),
]

