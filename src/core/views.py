import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.views.csrf import csrf_failure as default_csrf_failure

from .dashboard import build_feed, build_sidebar, group_feed

logger = logging.getLogger(__name__)


def csrf_failure(request, reason=""):
    """Log why the CSRF check failed, then render Django's standard 403 page.

    Django's default page hides the reason, which makes "403 on login" hard to
    debug behind a proxy. The details (origin, host, referer, cookie presence)
    are written to the server log only - never to the response - so nothing is
    exposed to the client, regardless of how ENVIRONMENT is configured.
    """
    try:
        host = request.get_host()
    except Exception:  # DisallowedHost and friends
        host = "<ukendt host>"

    # %r escapes the header values, so a crafted Origin cannot inject log lines.
    logger.warning(
        "CSRF-afvisning: path=%s reason=%r origin=%r host=%r secure=%s "
        "referer=%r csrf_cookie=%s",
        request.path,
        reason,
        request.META.get("HTTP_ORIGIN"),
        host,
        request.is_secure(),
        request.META.get("HTTP_REFERER"),
        "csrftoken" in request.COOKIES,
    )
    return default_csrf_failure(request, reason)


@login_required
def index(request):
    """Dashboard: a date-ordered feed of the user's next relevant items."""
    now = timezone.localtime()
    feed_items = build_feed(request.user)
    return render(
        request,
        'index.html',
        {
            'feed_days': group_feed(feed_items),
            'feed_items': feed_items,
            'sidebar_sections': build_sidebar(request.user, request.path),
            'today': now.date(),
        },
    )
