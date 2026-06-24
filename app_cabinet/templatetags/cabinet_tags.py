# app_cabinet/templatetags/cabinet_tags.py
from django import template
from urllib.parse import urlencode

register = template.Library()

@register.filter
def multiply(value, arg):
    """Множить значення на аргумент"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return ''


@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Повертає закодований URL з оновленими параметрами
    """
    request = context['request']
    params = request.GET.copy()

    for key, value in kwargs.items():
        params[key] = value

    # Видаляємо порожні параметри
    for key in list(params.keys()):
        if not params[key]:
            del params[key]

    return urlencode(params)