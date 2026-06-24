from django import template
from django.utils.safestring import mark_safe
from ..models import GoogleTagSettings

register = template.Library()


@register.simple_tag
def google_analytics_script():
    """
    Renders Google Analytics tracking script for HTML head section
    """
    try:
        settings = GoogleTagSettings.get_settings()
        if settings and settings.is_active and settings.enable_google_analytics and settings.google_analytics_id:
            ga_id = settings.google_analytics_id.strip()
            
            # Check if it's GA4 (G-) or Universal Analytics (UA-)
            if ga_id.startswith('G-'):
                # GA4 script
                script = f"""
<!-- Google Analytics (GA4) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga_id}');
</script>
"""
            elif ga_id.startswith('UA-'):
                # Universal Analytics script
                script = f"""
<!-- Google Analytics (Universal Analytics) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga_id}');
</script>
"""
            else:
                # Default GA4 format
                script = f"""
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga_id}');
</script>
"""
            return mark_safe(script)
    except Exception:
        pass
    return ""


@register.simple_tag
def google_tag_manager_head():
    """
    Renders Google Tag Manager script for HTML head section
    """
    try:
        settings = GoogleTagSettings.get_settings()
        if settings and settings.is_active and settings.enable_google_tag_manager and settings.google_tag_manager_id:
            gtm_id = settings.google_tag_manager_id.strip()
            script = f"""
<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{gtm_id}');</script>
<!-- End Google Tag Manager -->
"""
            return mark_safe(script)
    except Exception:
        pass
    return ""


@register.simple_tag
def google_tag_manager_body():
    """
    Renders Google Tag Manager noscript for HTML body section
    """
    try:
        settings = GoogleTagSettings.get_settings()
        if settings and settings.is_active and settings.enable_google_tag_manager and settings.google_tag_manager_id:
            gtm_id = settings.google_tag_manager_id.strip()
            script = f"""
<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gtm_id}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->
"""
            return mark_safe(script)
    except Exception:
        pass
    return ""


@register.simple_tag
def facebook_pixel_script():
    """
    Renders Facebook Pixel tracking script for HTML head section
    """
    try:
        settings = GoogleTagSettings.get_settings()
        if settings and settings.is_active and settings.enable_facebook_pixel and settings.facebook_pixel_id:
            pixel_id = settings.facebook_pixel_id.strip()
            script = f"""
<!-- Facebook Pixel Code -->
<script>
!function(f,b,e,v,n,t,s)
{{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '{pixel_id}');
fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none"
src="https://www.facebook.com/tr?id={pixel_id}&ev=PageView&noscript=1"
/></noscript>
<!-- End Facebook Pixel Code -->
"""
            return mark_safe(script)
    except Exception:
        pass
    return ""


@register.simple_tag
def custom_head_scripts():
    """
    Renders custom head scripts
    """
    try:
        settings = GoogleTagSettings.get_settings()
        if settings and settings.is_active and settings.custom_head_scripts:
            return mark_safe(settings.custom_head_scripts)
    except Exception:
        pass
    return ""


@register.simple_tag
def custom_body_scripts():
    """
    Renders custom body scripts
    """
    try:
        settings = GoogleTagSettings.get_settings()
        if settings and settings.is_active and settings.custom_body_scripts:
            return mark_safe(settings.custom_body_scripts)
    except Exception:
        pass
    return ""


@register.simple_tag
def all_tracking_head_scripts():
    """
    Renders all tracking scripts for HTML head section
    """
    scripts = []
    
    # Google Analytics
    ga_script = google_analytics_script()
    if ga_script:
        scripts.append(ga_script)
    
    # Google Tag Manager Head
    gtm_head_script = google_tag_manager_head()
    if gtm_head_script:
        scripts.append(gtm_head_script)
    
    # Facebook Pixel
    fb_script = facebook_pixel_script()
    if fb_script:
        scripts.append(fb_script)
    
    # Custom Head Scripts
    custom_head = custom_head_scripts()
    if custom_head:
        scripts.append(custom_head)
    
    return mark_safe('\n'.join(scripts))


@register.simple_tag
def all_tracking_body_scripts():
    """
    Renders all tracking scripts for HTML body section
    """
    scripts = []
    
    # Google Tag Manager Body
    gtm_body_script = google_tag_manager_body()
    if gtm_body_script:
        scripts.append(gtm_body_script)
    
    # Custom Body Scripts
    custom_body = custom_body_scripts()
    if custom_body:
        scripts.append(custom_body)
    
    return mark_safe('\n'.join(scripts)) 