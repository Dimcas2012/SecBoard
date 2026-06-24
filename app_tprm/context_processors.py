#  SecBoard\SecBoard\app_tprm\context_processors.py

from .permissions import check_tprm_access


def tprm_permissions(request):
    """
    Context processor to add TPRM permissions to all templates
    """
    if not request.user.is_authenticated:
        return {
            'tprm_perms': {
                # Vendor permissions
                'has_access_vendors': False,
                'can_edit_vendors': False,
                'can_delete_vendors': False,
                
                # Assessment permissions
                'has_access_assessments': False,
                'can_conduct_assessments': False,
                'can_approve_assessments': False,
                
                # Document permissions
                'has_access_documents': False,
                'can_upload_documents': False,
                'can_delete_documents': False,
                
                # Template permissions
                'has_access_templates': False,
                'can_edit_templates': False,
                'can_manage_questions': False,
                
                # Questionnaire permissions
                'has_access_questionnaires': False,
                'can_complete_questionnaires': False,
                'can_review_questionnaires': False,
                
                # Dashboard and reporting permissions
                'has_access_dashboard': False,
                'can_generate_reports': False,
                'can_export_data': False,
                
                # Risk management permissions
                'can_change_risk_level': False,
                'can_change_vendor_status': False,
            }
        }
    
    return {
        'tprm_perms': {
            # Vendor permissions
            'has_access_vendors': check_tprm_access(request.user, 'has_access_vendors'),
            'can_edit_vendors': check_tprm_access(request.user, 'can_edit_vendors'),
            'can_delete_vendors': check_tprm_access(request.user, 'can_delete_vendors'),
            
            # Assessment permissions
            'has_access_assessments': check_tprm_access(request.user, 'has_access_assessments'),
            'can_conduct_assessments': check_tprm_access(request.user, 'can_conduct_assessments'),
            'can_approve_assessments': check_tprm_access(request.user, 'can_approve_assessments'),
            
            # Document permissions
            'has_access_documents': check_tprm_access(request.user, 'has_access_documents'),
            'can_upload_documents': check_tprm_access(request.user, 'can_upload_documents'),
            'can_delete_documents': check_tprm_access(request.user, 'can_delete_documents'),
            
            # Template permissions
            'has_access_templates': check_tprm_access(request.user, 'has_access_templates'),
            'can_edit_templates': check_tprm_access(request.user, 'can_edit_templates'),
            'can_manage_questions': check_tprm_access(request.user, 'can_manage_questions'),
            
            # Questionnaire permissions
            'has_access_questionnaires': check_tprm_access(request.user, 'has_access_questionnaires'),
            'can_complete_questionnaires': check_tprm_access(request.user, 'can_complete_questionnaires'),
            'can_review_questionnaires': check_tprm_access(request.user, 'can_review_questionnaires'),
            
            # Dashboard and reporting permissions
            'has_access_dashboard': check_tprm_access(request.user, 'has_access_dashboard'),
            'can_generate_reports': check_tprm_access(request.user, 'can_generate_reports'),
            'can_export_data': check_tprm_access(request.user, 'can_export_data'),
            
            # Risk management permissions
            'can_change_risk_level': check_tprm_access(request.user, 'can_change_risk_level'),
            'can_change_vendor_status': check_tprm_access(request.user, 'can_change_vendor_status'),
        }
    }

