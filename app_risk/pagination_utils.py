"""Shared DataTables page-length validation for app_risk AJAX list endpoints."""

RISK_TABLE_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)
RISK_TABLE_DEFAULT_PAGE_SIZE = 25


def normalize_risk_table_length(length):
    try:
        length = int(length)
    except (TypeError, ValueError):
        return RISK_TABLE_DEFAULT_PAGE_SIZE
    if length not in RISK_TABLE_PAGE_SIZE_OPTIONS:
        return RISK_TABLE_DEFAULT_PAGE_SIZE
    return length
