"""Shared DataTables page-length validation for app_keycert AJAX lists."""

KEYCERT_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
KEYCERT_TABLE_DEFAULT_PAGE_SIZE = 25


def normalize_keycert_table_length(length):
    try:
        length = int(length)
    except (TypeError, ValueError):
        return KEYCERT_TABLE_DEFAULT_PAGE_SIZE
    if length not in KEYCERT_TABLE_PAGE_SIZE_OPTIONS:
        return KEYCERT_TABLE_DEFAULT_PAGE_SIZE
    return length
