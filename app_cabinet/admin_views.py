# SecBoard/app_cabinet/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import CabinetUser


# Guide model names used to group them in admin app_list (see apps.py)
CABINET_GUIDE_MODEL_NAMES = {
    'OrgStructureGuide',
    'CabinetUsersGuide',
    'CabinetGroupsGuide',
}


@staff_member_required
def cabinet_guides_settings_view(request):
    """Single settings page for all Cabinet Guides (replaces 3 separate menu items in admin)."""
    guides = [
        (_('Organization Structure Guides'), 'admin:app_cabinet_orgstructureguide_changelist'),
        (_('Cabinet Users Guides'), 'admin:app_cabinet_cabinetusersguide_changelist'),
        (_('Cabinet Groups Guides'), 'admin:app_cabinet_cabinetgroupsguide_changelist'),
    ]
    context = {
        'title': _('Cabinet Guides – Settings'),
        'guides': [(label, reverse(url_name)) for label, url_name in guides],
        'opts': CabinetUser._meta,  # for breadcrumbs app_label
    }
    return render(request, 'admin/app_cabinet/cabinet_guides_settings.html', context)
