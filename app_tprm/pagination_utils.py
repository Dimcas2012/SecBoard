"""Shared server-side table pagination for app_tprm list pages."""

from django.core.paginator import Paginator

TPRM_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
TPRM_TABLE_DEFAULT_PAGE_SIZE = 25


def get_tprm_table_page_size(request):
    try:
        page_size = int(request.GET.get('per_page', TPRM_TABLE_DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = TPRM_TABLE_DEFAULT_PAGE_SIZE
    if page_size not in TPRM_TABLE_PAGE_SIZE_OPTIONS:
        page_size = TPRM_TABLE_DEFAULT_PAGE_SIZE
    return page_size


def paginate_tprm_queryset(request, queryset):
    per_page = get_tprm_table_page_size(request)
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': paginator.count > 0,
        'current_page_size': per_page,
        'page_size_options': TPRM_TABLE_PAGE_SIZE_OPTIONS,
        'per_page': per_page,
    }
    return page_obj, context
