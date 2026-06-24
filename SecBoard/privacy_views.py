from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _


@require_http_methods(["GET"])
def privacy_policy(request):
    """Privacy Policy page for GDPR compliance"""
    context = {
        'page_title': _('Privacy Policy'),
        'last_updated': '2025-06-24',
    }
    return render(request, 'privacy/privacy_policy.html', context)


@require_http_methods(["GET"])  
def cookie_policy(request):
    """Cookie Policy page with detailed information"""
    context = {
        'page_title': _('Cookie Policy'),
        'last_updated': '2025-06-24',
    }
    return render(request, 'privacy/cookie_policy.html', context)


@require_http_methods(["GET"])
def terms_of_service(request):
    """Terms of Service page"""
    context = {
        'page_title': _('Terms of Service'),
        'last_updated': '2025-06-24',
    }
    return render(request, 'privacy/terms_of_service.html', context) 