from django import template

register = template.Library()

@register.filter
def split(value, delimiter=','):
    if value:
        return value.split(delimiter)
    return []

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, '')

@register.filter
def split_query(query_dict, key=None):
    if not query_dict:
        return []
    if key:
        # Handle multi-select query parameters (e.g., spec_1=8&spec_1=16)
        return query_dict.getlist(key)
    # Handle product_name or other multi-select fields
    return query_dict.getlist('product_name') if 'product_name' in query_dict else []