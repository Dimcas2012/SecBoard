# SecBoard/app_risk/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import Threat


# Guide model names used to group them in admin app_list (see apps.py)
RISK_GUIDE_MODEL_NAMES = {
    'RiskAssessmentConfigGuide',
    'RiskAssessmentGuide',
    'RiskReportGuide',
}


@staff_member_required
def risk_guides_settings_view(request):
    """Single settings page for all Risk Guides (replaces 3 separate menu items in admin)."""
    guides = [
        (_('Risk Assessment Config Guides'), 'admin:app_risk_riskassessmentconfigguide_changelist'),
        (_('Risk Assessment Guides'), 'admin:app_risk_riskassessmentguide_changelist'),
        (_('Risk Report Guides'), 'admin:app_risk_riskreportguide_changelist'),
    ]
    context = {
        'title': _('Risk Guides – Settings'),
        'guides': [(label, reverse(url_name)) for label, url_name in guides],
        'opts': Threat._meta,  # for breadcrumbs app_label
    }
    return render(request, 'admin/app_risk/risk_guides_settings.html', context)
