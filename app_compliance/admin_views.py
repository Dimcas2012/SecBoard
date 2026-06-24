# SecBoard/app_compliance/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import ComplianceFramework


# Guide model names used to group them in admin app_list (see apps.py)
COMPLIANCE_GUIDE_MODEL_NAMES = {
    'MandatoryProcessesGuide',
    'InternalComplianceGuide',
    'LocalComplianceGuide',
    'FrameworkComplianceGuide',
}


@staff_member_required
def compliance_guides_settings_view(request):
    """Single settings page for all Compliance Guides (replaces 4 separate menu items in admin)."""
    guides = [
        (_('Mandatory Processes Guides'), 'admin:app_compliance_mandatoryprocessesguide_changelist'),
        (_('Internal Compliance Guides'), 'admin:app_compliance_internalcomplianceguide_changelist'),
        (_('Local Compliance Guides'), 'admin:app_compliance_localcomplianceguide_changelist'),
        (_('Framework Compliance Guides'), 'admin:app_compliance_frameworkcomplianceguide_changelist'),
    ]
    context = {
        'title': _('Compliance Guides – Settings'),
        'guides': [(label, reverse(url_name)) for label, url_name in guides],
        'opts': ComplianceFramework._meta,  # for breadcrumbs app_label
    }
    return render(request, 'admin/app_compliance/compliance_guides_settings.html', context)
