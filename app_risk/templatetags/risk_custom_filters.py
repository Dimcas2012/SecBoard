#  SecBoard\SecBoard\app_suib\templatetags\asset_custom_filters.py

from django import template
from django.template.defaultfilters import stringfilter
from django.utils import timezone

register = template.Library()

@register.filter
def multiply(value, arg):
    return float(value) * arg

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_criticality_name(criticality_level, language):
    if criticality_level:
        return criticality_level.get_name(language)
    return ''

@register.filter
def call_method(obj, method_name):
    method = getattr(obj, method_name)
    if callable(method):
        return method()
    return method

@register.filter
def call_method_with_arg(obj, method_and_arg):
    method_name, arg = method_and_arg.split(':')
    method = getattr(obj, method_name)
    if callable(method):
        return method(arg)
    return method

@register.filter
@stringfilter
def getattribute(value, arg):
    """Gets an attribute of an object dynamically from a string name"""
    if hasattr(value, str(arg)):
        return getattr(value, arg)
    elif hasattr(value, 'get'):
        return value.get(arg)
    else:
        return ''

@register.filter
@stringfilter
def split(value, arg):
    """
    Splits the string into a list.
    """
    return value.split(arg)

@register.filter
def local_datetime(value, format_string='%Y-%m-%d %H:%M'):
    """
    Convert timezone-aware datetime to local timezone and format it.
    """
    if value:
        try:
            local_time = value.astimezone()
            return local_time.strftime(format_string)
        except:
            return value.strftime(format_string) if value else ''
    return ''

@register.filter
def local_date(value, format_string='%Y-%m-%d'):
    """
    Convert timezone-aware datetime to local timezone and format as date.
    """
    if value:
        try:
            local_time = value.astimezone()
            return local_time.strftime(format_string)
        except:
            return value.strftime(format_string) if value else ''
    return ''

@register.filter
def local_time(value, format_string='%H:%M'):
    """
    Convert timezone-aware datetime to local timezone and format as time.
    """
    if value:
        try:
            local_time = value.astimezone()
            return local_time.strftime(format_string)
        except:
            return value.strftime(format_string) if value else ''
    return ''