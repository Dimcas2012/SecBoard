"""Shared server-side table pagination for app_soc list pages."""

SOC_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
SOC_TABLE_DEFAULT_PAGE_SIZE = 25


def get_soc_table_page_size(request):
    try:
        page_size = int(request.GET.get('per_page', SOC_TABLE_DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = SOC_TABLE_DEFAULT_PAGE_SIZE
    if page_size not in SOC_TABLE_PAGE_SIZE_OPTIONS:
        page_size = SOC_TABLE_DEFAULT_PAGE_SIZE
    return page_size
