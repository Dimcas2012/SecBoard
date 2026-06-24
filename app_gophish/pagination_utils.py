"""Shared server-side table pagination for app_gophish list pages."""

from django.core.paginator import Paginator

GOPHISH_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
GOPHISH_TABLE_DEFAULT_PAGE_SIZE = 25


def get_gophish_table_page_size(request):
    try:
        page_size = int(request.GET.get('per_page', GOPHISH_TABLE_DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = GOPHISH_TABLE_DEFAULT_PAGE_SIZE
    if page_size not in GOPHISH_TABLE_PAGE_SIZE_OPTIONS:
        page_size = GOPHISH_TABLE_DEFAULT_PAGE_SIZE
    return page_size


def paginate_gophish_queryset(request, queryset):
    per_page = get_gophish_table_page_size(request)
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': paginator.count > 0,
        'current_page_size': per_page,
        'page_size_options': GOPHISH_TABLE_PAGE_SIZE_OPTIONS,
        'per_page': per_page,
    }
    return page_obj, context
