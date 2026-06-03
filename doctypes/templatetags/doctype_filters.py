from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Template filter to get item from dictionary by key
    Usage: {{ mydict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter(name='workflow_state')
def workflow_state_filter(document):
    """Safely get workflow state for a document, returns None if not set."""
    try:
        return document.workflow_state
    except Exception:
        return None
