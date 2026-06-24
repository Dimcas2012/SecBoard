"""Shared server-side table pagination for app_access list pages."""

ACCESS_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
ACCESS_TABLE_DEFAULT_PAGE_SIZE = 25


def get_access_table_page_size(request):
    try:
        page_size = int(request.GET.get('page_size', ACCESS_TABLE_DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = ACCESS_TABLE_DEFAULT_PAGE_SIZE
    if page_size not in ACCESS_TABLE_PAGE_SIZE_OPTIONS:
        page_size = ACCESS_TABLE_DEFAULT_PAGE_SIZE
    return page_size
