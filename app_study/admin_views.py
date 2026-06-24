# SecBoard/app_study/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import Quiz


# Guide model names used to group them in admin app_list (see apps.py)
STUDY_GUIDE_MODEL_NAMES = {
    'PageManagerGuide',
    'QuizManagerGuide',
}


@staff_member_required
def study_guides_settings_view(request):
    """Single settings page for all Study Guides (replaces 2 separate menu items in admin)."""
    guides = [
        (_('Page Manager Guides'), 'admin:app_study_pagemanagerguide_changelist'),
        (_('Quiz Manager Guides'), 'admin:app_study_quizmanagerguide_changelist'),
    ]
    context = {
        'title': _('Study Guides – Settings'),
        'guides': [(label, reverse(url_name)) for label, url_name in guides],
        'opts': Quiz._meta,  # for breadcrumbs app_label
    }
    return render(request, 'admin/app_study/study_guides_settings.html', context)
