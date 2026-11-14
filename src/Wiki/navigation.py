"""Helpers for the nested wiki page menu."""
from collections import defaultdict

from .models import WikiPage


def build_page_tree():
    """Return the wiki's page hierarchy as nested ``{'page', 'children'}`` nodes."""
    pages = list(WikiPage.objects.all().order_by('order', 'title'))
    by_parent = defaultdict(list)
    for page in pages:
        by_parent[page.parent_id].append(page)

    def make_node(page, ancestors):
        # The model forbids cycles, but a malformed row should not hang a page.
        if page.pk in ancestors:
            return {'page': page, 'children': []}
        seen = ancestors | {page.pk}
        return {
            'page': page,
            'children': [make_node(child, seen) for child in by_parent.get(page.pk, [])],
        }

    return [make_node(page, frozenset()) for page in by_parent.get(None, [])]
