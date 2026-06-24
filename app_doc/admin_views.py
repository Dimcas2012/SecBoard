# SecBoard/app_doc/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import RegisterDocs


# Guide model names used to group them in admin app_list (see apps.py)
DOC_GUIDE_MODEL_NAMES = {
    'RegDocsGuide',
    'LegislativeDocsGuide',
}


@staff_member_required
def doc_guides_settings_view(request):
    """Single settings page for all Doc Guides (replaces 2 separate menu items in admin)."""
    guides = [
        (_('Reg Docs Guides'), 'admin:app_doc_regdocsguide_changelist'),
        (_('Legislative Docs Guides'), 'admin:app_doc_legislativedocsguide_changelist'),
    ]
    context = {
        'title': _('Doc Guides – Settings'),
        'guides': [(label, reverse(url_name)) for label, url_name in guides],
        'opts': RegisterDocs._meta,  # for breadcrumbs app_label
    }
    return render(request, 'admin/app_doc/doc_guides_settings.html', context)
