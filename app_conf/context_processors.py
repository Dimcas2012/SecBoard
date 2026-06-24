from .models import GoogleTagSettings, ContactSettings, SiteSettings


def site_settings(request):
    """
    Context processor to make site settings available in all templates
    """
    import os
    
    # Get build name from environment variable or directory name
    build_name = os.environ.get('BUILD_NAME')
    if not build_name:
        # Try to detect build name from current working directory
        cwd = os.getcwd()
        if 'builds/' in cwd or 'builds\\' in cwd:
            # Extract build name from path like /srv/SecBoard_customer/builds/secboard_v1.4
            parts = cwd.replace('\\', '/').split('/builds/')
            if len(parts) > 1:
                build_name = parts[1].split('/')[0]
    
    try:
        settings = SiteSettings.get_settings()
        return {
            'site_settings': settings,
            'project_display_name': settings.get_project_display_name(),
            'navbar_color': settings.get_navbar_color(),
            'project_type': settings.project_type,
            'build_name': build_name,
        }
    except Exception:
        # Return default settings if there's any error
        return {
            'site_settings': None,
            'project_display_name': 'SecBoard',
            'navbar_color': '#2c3e50',
            'project_type': 'prod',
            'build_name': build_name,
        }


def google_tags(request):
    """
    Context processor to make Google tag settings available in all templates
    """
    try:
        settings = GoogleTagSettings.get_settings()
        return {
            'google_tag_settings': settings
        }
    except Exception:
        # Return empty settings if there's any error
        return {
            'google_tag_settings': None
        }


def contact_settings(request):
    """
    Context processor to make contact settings available in all templates
    """
    try:
        settings = ContactSettings.get_settings()
        return {
            'contact_settings': settings
        }
    except Exception:
        # Return empty settings if there's any error
        return {
            'contact_settings': None
        } 