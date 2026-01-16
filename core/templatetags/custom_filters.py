from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Template filter to access dictionary items by key"""
    if dictionary and key:
        return dictionary.get(key)
    return None
