#  SecBoard\SecBoard\app_study\templatetags\quiz_custom_filters.py
from django import template
import html
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def div(value, arg):
    try:
        return int(value) / int(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    return value * arg

@register.filter
def successful_attempts(attempts):
    return sum(1 for attempt in attempts if attempt['attempt'].score >= attempt['attempt'].quiz.passing_score)

@register.filter
def failed_attempts(attempts):
    return sum(1 for attempt in attempts if attempt['attempt'].score < attempt['attempt'].quiz.passing_score)

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using its key.
    Usage: {{ my_dict|get_item:key_var }}
    """
    if dictionary is None:
        return None
    
    try:
        return dictionary.get(key)
    except (KeyError, AttributeError):
        return None

@register.filter
def decode_html_entities(value):
    """
    Decode HTML entities in text while preserving formatting.
    Usage: {{ text|decode_html_entities }}
    """
    if not value:
        return value
    
    # First strip HTML tags
    clean_text = strip_tags(value)
    # Then decode HTML entities
    decoded_text = html.unescape(clean_text)
    return mark_safe(decoded_text)

