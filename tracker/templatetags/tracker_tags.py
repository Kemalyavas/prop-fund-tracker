from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """İki değeri çarpar"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """İlk değeri ikinci değere böler"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def add(value, arg):
    """İki değeri toplar"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """İlk değerden ikinci değeri çıkarır"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def abs(value):
    """Mutlak değer alır"""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return 0

@register.filter
def maximum(value, arg):
    """İki değerden büyük olanı döndürür"""
    try:
        return max(float(value), float(arg))
    except (ValueError, TypeError):
        return 0

@register.filter
def minimum(value, arg):
    """İki değerden küçük olanı döndürür"""
    try:
        return min(float(value), float(arg))
    except (ValueError, TypeError):
        return 0

@register.filter
def negative(value):
    """Değerin negatifini alır"""
    try:
        return -float(value)
    except (ValueError, TypeError):
        return 0
    
@register.filter
def get_item(dictionary, key):
    """Bir sözlükten anahtar ile değer alır"""
    try:
        return dictionary.get(key)
    except (AttributeError, KeyError, TypeError):
        return None