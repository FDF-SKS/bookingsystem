from django import template

from ..navigation import build_page_tree
from ..search import plain_text

register = template.Library()


@register.inclusion_tag('Wiki/_sidebar.html', takes_context=True)
def wiki_sidebar(context, current_page=None):
    active_ids = set()
    if current_page is not None and hasattr(current_page, 'get_ancestors'):
        active_ids = {page.pk for page in current_page.get_ancestors()}
        active_ids.add(current_page.pk)
    return {
        'nodes': build_page_tree(),
        'active_ids': active_ids,
        'current_page': current_page,
        'request': context.get('request'),
    }


@register.filter
def wiki_preview(value, length=160):
    """Plain-text preview of stored TipTap HTML."""
    text = plain_text(value)
    try:
        max_length = int(length)
    except (TypeError, ValueError):
        max_length = 160
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + '…'
