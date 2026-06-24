#  SecBoard/app_std/templatetags/std_custom_filters.py

from django import template
from django.template.defaultfilters import stringfilter

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

@register.filter(name='split')
def split(value, delimiter=','):
    """
    Returns a list of strings, breaking the given string by the specified delimiter.
    Example usage: {{ "a,b,c"|split:"," }}
    """
    return value.split(delimiter)