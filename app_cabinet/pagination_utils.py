"""Shared server-side table pagination for app_cabinet list pages."""

CABINET_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
CABINET_TABLE_DEFAULT_PAGE_SIZE = 25


def get_cabinet_table_page_size(request):
    try:
        page_size = int(request.GET.get('per_page', CABINET_TABLE_DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = CABINET_TABLE_DEFAULT_PAGE_SIZE
    if page_size not in CABINET_TABLE_PAGE_SIZE_OPTIONS:
        page_size = CABINET_TABLE_DEFAULT_PAGE_SIZE
    return page_size
