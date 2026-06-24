"""Shared server-side table pagination for app_incident list pages."""

INCIDENT_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
INCIDENT_TABLE_DEFAULT_PAGE_SIZE = 25


def get_incident_table_page_size(request):
    try:
        page_size = int(request.GET.get('page_size', INCIDENT_TABLE_DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = INCIDENT_TABLE_DEFAULT_PAGE_SIZE
    if page_size not in INCIDENT_TABLE_PAGE_SIZE_OPTIONS:
        page_size = INCIDENT_TABLE_DEFAULT_PAGE_SIZE
    return page_size
