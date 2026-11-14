"""Title and content search for the wiki, including query-aware previews."""
import html
import re

from django.db.models import Q
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import WikiPage

_TAG_RE = re.compile(r'<[^>]+>')
_TERM_SPLIT_RE = re.compile(r'\s+')


def query_terms(query: str) -> list[str]:
    return [term for term in _TERM_SPLIT_RE.split((query or '').strip()) if term]


def plain_text(value: str) -> str:
    """Convert stored TipTap HTML into searchable, human-readable text."""
    if not value:
        return ''
    without_tags = _TAG_RE.sub(' ', value)
    return re.sub(r'\s+', ' ', html.unescape(without_tags)).strip()


def _term_pattern(terms: list[str]) -> re.Pattern | None:
    if not terms:
        return None
    # Longest first so overlapping terms highlight as a whole.
    ordered = sorted(terms, key=len, reverse=True)
    return re.compile('|'.join(re.escape(term) for term in ordered), re.IGNORECASE)


def _highlight(segment: str, pattern: re.Pattern) -> tuple[str, bool]:
    parts = []
    last = 0
    found = False
    for match in pattern.finditer(segment):
        found = True
        parts.append(escape(segment[last:match.start()]))
        parts.append(f'<mark>{escape(match.group(0))}</mark>')
        last = match.end()
    parts.append(escape(segment[last:]))
    return ''.join(parts), found


def highlight_text(value: str, query: str):
    """Escape ``value`` and wrap query matches in ``<mark>``."""
    text = value or ''
    pattern = _term_pattern(query_terms(query))
    if pattern is None:
        return escape(text)
    highlighted, _ = _highlight(text, pattern)
    return mark_safe(highlighted)


def make_snippet(text: str, query: str, radius: int = 150):
    """Return a safe HTML preview centred on the first query match."""
    text = text or ''
    pattern = _term_pattern(query_terms(query))
    if not text:
        return mark_safe('')
    if pattern is None:
        excerpt = text[: radius * 2]
        suffix = '…' if len(text) > len(excerpt) else ''
        return mark_safe(escape(excerpt) + suffix)

    match = pattern.search(text)
    if match is None:
        excerpt = text[: radius * 2]
        suffix = '…' if len(text) > len(excerpt) else ''
        return mark_safe(escape(excerpt) + suffix)

    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    fragment = text[start:end]
    highlighted, _ = _highlight(fragment, pattern)
    prefix = '…' if start > 0 else ''
    suffix = '…' if end < len(text) else ''
    return mark_safe(prefix + highlighted + suffix)


def build_filter(query: str) -> Q | None:
    """Build an AND-of-terms query, each term matching title or content."""
    terms = query_terms(query)
    if not terms:
        return None
    condition = Q()
    for term in terms:
        condition &= Q(title__icontains=term) | Q(content__icontains=term)
    return condition


def page_matches(page, terms: list[str]) -> bool:
    """Whether every term occurs in the page title or its visible text.

    The database filter also looks at raw HTML, so this second pass drops pages
    that only matched a tag name, a class or an href.
    """
    if not terms:
        return False
    haystack = f'{page.title}\n{plain_text(page.content)}'.lower()
    return all(term.lower() in haystack for term in terms)


def build_search_results(query: str, limit: int = 50):
    condition = build_filter(query)
    if condition is None:
        return []

    terms = query_terms(query)
    pages = (
        WikiPage.objects.filter(condition)
        .select_related('parent')
        .order_by('title')[:200]
    )
    results = []
    for page in pages:
        if not page_matches(page, terms):
            continue
        body = plain_text(page.content)
        results.append(
            {
                'page': page,
                'title_html': highlight_text(page.title, query),
                'snippet': make_snippet(body, query),
                'title_match': all(term.lower() in page.title.lower() for term in terms),
            }
        )
        if len(results) >= limit:
            break

    # Title matches are the strongest signal, then alphabetical within each group.
    results.sort(key=lambda result: (not result['title_match'], result['page'].title.lower()))
    return results
