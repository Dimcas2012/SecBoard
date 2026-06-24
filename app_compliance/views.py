"""
Compliance views module - re-exports all views from specialized modules
This file maintains backward compatibility by importing all views from:
- framework_compliance: Framework-related views
- local_compliance: Local compliance views  
- internal_compliance: Internal compliance views
"""

# Import all views from specialized modules
from .framework_compliance import *
from .local_compliance import *
from .internal_compliance import *

# Also export utility functions and decorators for convenience
from .utils import (
    get_language_preferences,
    parse_local_requirement_date,
    build_localized_options,
    get_dictionary_options,
    compliance_access_required,
    local_compliance_access_required,
    internal_compliance_access_required,
    control_mapping_access_required,
    get_user_company,
    get_user_accessible_companies,
    get_user_accessible_companies_local,
    get_user_accessible_companies_internal,
    get_user_accessible_companies_for_control_mapping,
    check_user_compliance_permission,
    check_user_local_compliance_permission,
    check_user_internal_compliance_permission,
    check_user_control_mapping_access,
    get_user_compliance_permissions,
    get_user_local_compliance_permissions,
    get_user_internal_compliance_permissions,
    log_compliance_action,
    excel_get_required,
    excel_normalize_choice,
    excel_is_empty_value,
    excel_parse_date,
    excel_parse_required_count,
    excel_parse_periodicity,
)
