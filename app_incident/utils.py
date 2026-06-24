from app_conf.models import Company

def get_user_accessible_companies(user):
    """
    Returns a queryset of companies that the user has access to.
    If user is superuser, returns all companies.
    """
    if user.is_superuser:
        return Company.objects.all()
    
    # Get user groups
    user_groups = user.groups.all()
    
    # Get companies user has access to through AccessIncidents
    company_ids = set()
    for group in user_groups:
        try:
            from app_incident.models import AccessIncidents
            access = AccessIncidents.objects.get(group=group, has_access=True)
            for company in access.companies.all():
                company_ids.add(company.id)
        except AccessIncidents.DoesNotExist:
            continue
    
    # Return a QuerySet of accessible companies
    return Company.objects.filter(id__in=company_ids) 