"""Shared server-side table pagination for app_gdpr list pages."""

GDPR_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
GDPR_TABLE_DEFAULT_PAGE_SIZE = 25


def get_gdpr_table_page_size(request):
    try:
        page_size = int(request.GET.get('per_page', GDPR_TABLE_DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = GDPR_TABLE_DEFAULT_PAGE_SIZE
    if page_size not in GDPR_TABLE_PAGE_SIZE_OPTIONS:
        page_size = GDPR_TABLE_DEFAULT_PAGE_SIZE
    return page_size
