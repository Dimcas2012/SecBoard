#  SecBoard\SecBoard\app_study\templatetags\quiz_filters.py
from django import template

register = template.Library()

@register.filter
def sub(value, arg):
    return value - arg