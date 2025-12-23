from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def divide(value, arg):
    """Divide the value by the argument."""
    try:
        if value and arg:
            return Decimal(value) / Decimal(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        pass
    return Decimal('0.00')