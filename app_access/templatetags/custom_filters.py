from django import template

register = template.Library()

@register.filter
def startswith(text, starts):
    """
    Returns True if 'text' starts with the 'starts' string.
    """
    if text is None:
        return False
    return str(text).startswith(starts)

@register.filter
def dict_length(dict_obj):
    """
    Returns the length of a dictionary or 0 if not a dictionary
    """
    if isinstance(dict_obj, dict):
        return len(dict_obj)
    return 0

@register.filter
def abs_value(value):
    """
    Returns the absolute value of a number
    """
    try:
        return abs(value)
    except (TypeError, ValueError):
        return value


@register.simple_tag(takes_context=True)
def filters_expanded(context, *names):
    """
    True if any named query param (request.GET) or context variable is non-empty.
    Use: {% filters_expanded 'search' 'company' as filters_expanded %}
    """
    request = context.get('request')
    for name in names:
        if request is not None:
            value = request.GET.get(name)
            if value not in (None, ''):
                return True
        value = context.get(name)
        if value not in (None, ''):
            return True
    return False