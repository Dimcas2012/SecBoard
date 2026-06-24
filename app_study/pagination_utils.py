"""Shared server-side table pagination for app_study list pages."""

STUDY_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
STUDY_TABLE_DEFAULT_PAGE_SIZE = 25


def get_study_table_page_size(request):
    try:
        page_size = int(request.GET.get('per_page', STUDY_TABLE_DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = STUDY_TABLE_DEFAULT_PAGE_SIZE
    if page_size not in STUDY_TABLE_PAGE_SIZE_OPTIONS:
        page_size = STUDY_TABLE_DEFAULT_PAGE_SIZE
    return page_size
