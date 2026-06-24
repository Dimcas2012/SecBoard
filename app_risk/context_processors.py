# SecBoard/app_risk/context_processors.py


def vulnerability_form_languages(request):
    """Make vulnerability form languages available in templates (dynamic from settings)."""
    from .vulnerability_utils import get_vulnerability_form_languages
    return {
        'vulnerability_form_languages': get_vulnerability_form_languages(),
    }
