from django import template

register = template.Library()


@register.filter
def get_item(container, key):
    """Works for dicts and Django Form instances — both support bracket access."""
    if container is None:
        return None
    try:
        return container[key]
    except KeyError:
        return None


@register.filter
def percent(value, total):
    try:
        value = float(value)
        total = float(total)
        if total == 0:
            return 0
        return round(value / total * 100)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def mul(value, factor):
    try:
        return float(value) * float(factor)
    except (TypeError, ValueError):
        return 0
