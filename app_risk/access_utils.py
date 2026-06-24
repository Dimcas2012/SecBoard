# SecBoard/app_risk/access_utils.py

from .models import AccessRisk

def has_risk_assessment_access(user):
    """Check if user has access to risk assessment functionality"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        has_access_assessment=True
    ).exists()

def can_edit_risk_assessment(user):
    """Check if user can edit risk assessment records"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        can_edit_assessment=True
    ).exists()

def can_config_risk_assessment(user):
    """Check if user can configure risk assessment settings"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        can_config_assessment=True
    ).exists()

def has_risk_report_access(user):
    """Check if user has access to risk report functionality"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        has_access_report=True
    ).exists()

def can_add_risk_report(user):
    """Check if user can add risk report records"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        can_add_report=True
    ).exists()

def can_edit_risk_report(user):
    """Check if user can edit risk report records"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        can_edit_report=True
    ).exists()

def can_delete_risk_report(user):
    """Check if user can delete risk report records"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        can_delete_report=True
    ).exists()

def has_risk_config_access(user):
    """Check if user has access to risk configuration functionality"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        has_access_config=True
    ).exists()

def can_add_risk_config(user):
    """Check if user can add risk configuration records"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        can_add_config=True
    ).exists()

def can_edit_risk_config(user):
    """Check if user can edit risk configuration records"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        can_edit_config=True
    ).exists()

def can_delete_risk_config(user):
    """Check if user can delete risk configuration records"""
    if user.is_superuser:
        return True
    return AccessRisk.objects.filter(
        group__in=user.groups.all(), 
        can_delete_config=True
    ).exists()

def get_user_risk_companies(user):
    """Get companies that user can access through AccessRisk"""
    if user.is_superuser:
        from app_conf.models import Company
        return Company.objects.all()
    
    access_records = AccessRisk.objects.filter(
        group__in=user.groups.all(),
        has_access_assessment=True
    ).prefetch_related('companies')
    
    # Collect all company IDs from AccessRisk records
    from app_conf.models import Company
    company_ids = set()
    for access_record in access_records:
        company_ids.update(access_record.companies.values_list('id', flat=True))
    
    # Return companies filtered by collected IDs
    return Company.objects.filter(id__in=company_ids).order_by('name')

def get_user_risk_permissions(user):
    """Get comprehensive risk permissions for user"""
    if user.is_superuser:
        return {
            'has_access_assessment': True,
            'can_edit_assessment': True,
            'can_config_assessment': True,
            'has_access_report': True,
            'can_add_report': True,
            'can_edit_report': True,
            'can_delete_report': True,
            'has_access_config': True,
            'can_add_config': True,
            'can_edit_config': True,
            'can_delete_config': True,
            'companies': get_user_risk_companies(user),
        }
    
    access_records = AccessRisk.objects.filter(
        group__in=user.groups.all()
    ).prefetch_related('companies')
    
    # Aggregate permissions from all matching records
    permissions = {
        'has_access_assessment': False,
        'can_edit_assessment': False,
        'can_config_assessment': False,
        'has_access_report': False,
        'can_add_report': False,
        'can_edit_report': False,
        'can_delete_report': False,
        'has_access_config': False,
        'can_add_config': False,
        'can_edit_config': False,
        'can_delete_config': False,
        'companies': set(),
    }
    
    for access_record in access_records:
        if access_record.has_access_assessment:
            permissions['has_access_assessment'] = True
        if access_record.can_edit_assessment:
            permissions['can_edit_assessment'] = True
        if access_record.can_config_assessment:
            permissions['can_config_assessment'] = True
        if access_record.has_access_report:
            permissions['has_access_report'] = True
        if access_record.can_add_report:
            permissions['can_add_report'] = True
        if access_record.can_edit_report:
            permissions['can_edit_report'] = True
        if access_record.can_delete_report:
            permissions['can_delete_report'] = True
        if access_record.has_access_config:
            permissions['has_access_config'] = True
        if access_record.can_add_config:
            permissions['can_add_config'] = True
        if access_record.can_edit_config:
            permissions['can_edit_config'] = True
        if access_record.can_delete_config:
            permissions['can_delete_config'] = True
        
        # Collect companies
        for company in access_record.companies.all():
            permissions['companies'].add(company)
    
    # Convert companies set to queryset
    from app_conf.models import Company
    if permissions['companies']:
        company_ids = [company.id for company in permissions['companies']]
        permissions['companies'] = Company.objects.filter(id__in=company_ids)
    else:
        permissions['companies'] = Company.objects.none()
    
    return permissions 