"""Views for the PWA manifest, service worker, push API and calendar feeds."""
from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from . import calendar as calendar_feeds
from .forms import NotificationPreferenceForm
from .models import CalendarFeedToken, PushSubscription
from .push import push_is_configured
from .services import get_preference, send_test_notification

MANIFEST_ICONS = (
    ('icons/icon-192.png', '192x192', 'any'),
    ('icons/icon-512.png', '512x512', 'any'),
    ('icons/maskable-512.png', '512x512', 'maskable'),
)


# ---------------------------------------------------------------------------
# PWA plumbing
# ---------------------------------------------------------------------------
@require_GET
def manifest(request):
    """Serve the web app manifest from the root so the scope covers the site."""
    data = {
        'name': 'SKS Booking',
        'short_name': 'SKS Booking',
        'description': 'Bookingsystem og rammeprogram for FDF SKS.',
        'lang': 'da',
        'dir': 'ltr',
        'id': '/',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'display_override': ['standalone', 'minimal-ui'],
        'orientation': 'any',
        'background_color': '#ffffff',
        'theme_color': '#FF733C',
        'categories': ['productivity', 'utilities'],
        'prefer_related_applications': False,
        'icons': [
            {
                'src': f'{settings.STATIC_URL}{src}',
                'sizes': sizes,
                'type': 'image/png',
                'purpose': purpose,
            }
            for src, sizes, purpose in MANIFEST_ICONS
        ],
        'shortcuts': [
            {
                'name': 'Mine opgaver',
                'short_name': 'Opgaver',
                'url': reverse('organization_TjanseOwnership_list'),
            },
            {
                'name': 'Rammeprogram',
                'short_name': 'Program',
                'url': reverse('organization_Program_event_list'),
            },
            {
                'name': 'Notifikationer og kalender',
                'short_name': 'Indstillinger',
                'url': reverse('notifications_settings'),
            },
        ],
    }
    return HttpResponse(
        json.dumps(data, ensure_ascii=False),
        content_type='application/manifest+json',
    )


@require_GET
def service_worker(request):
    """Serve the service worker from the site root so it controls every page."""
    response = render(
        request,
        'notifications/sw.js',
        content_type='application/javascript; charset=utf-8',
    )
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


class OfflineView(TemplateView):
    """Fallback page shown by the service worker when the network is gone."""

    template_name = 'notifications/offline.html'


# ---------------------------------------------------------------------------
# Notification settings
# ---------------------------------------------------------------------------
class NotificationSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'notifications/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        preference = get_preference(user)
        token, _ = CalendarFeedToken.objects.get_or_create(user=user)

        feeds = []
        for feed, label in calendar_feeds.FEED_CHOICES.items():
            path = calendar_feeds.feed_url_path(token.token, feed)
            # Use the canonical public URL: the settings page may have been
            # opened via an internal host name that a phone cannot reach.
            url = f"{settings.SITE_URL}/{path.lstrip('/')}"
            feeds.append(
                {
                    'key': feed,
                    'label': label,
                    'url': url,
                    'webcal': calendar_feeds.webcal_url(url),
                }
            )

        context.update(
            {
                'preference': preference,
                'form': NotificationPreferenceForm(instance=preference),
                'vapid_public_key': settings.WEBPUSH_VAPID_PUBLIC_KEY,
                'push_configured': push_is_configured(),
                'subscription_count': user.push_subscriptions.count(),
                'calendar_feeds': feeds,
                'upcoming_minutes': settings.NOTIFICATIONS_UPCOMING_MINUTES,
            }
        )
        return context


@login_required
@require_POST
def update_preferences(request):
    preference = get_preference(request.user)
    form = NotificationPreferenceForm(request.POST, instance=preference)
    if form.is_valid():
        form.save()
        messages.success(request, 'Dine notifikationsindstillinger blev gemt.')
    else:
        messages.error(request, 'Indstillingerne kunne ikke gemmes.')
    return redirect('notifications_settings')


# ---------------------------------------------------------------------------
# Push subscription API (JSON, called by the service-worker client script)
# ---------------------------------------------------------------------------
def _json_body(request) -> dict:
    try:
        return json.loads(request.body or b'{}')
    except (TypeError, ValueError):
        return {}


def _is_valid_push_endpoint(endpoint: str) -> bool:
    """Accept only public HTTPS endpoints, never an internal address.

    ``pywebpush`` makes the server send a request to this URL, so an endpoint
    pointing at an internal host would be a server-side request forgery vector.
    """
    parsed = urlparse(endpoint)
    if parsed.scheme != 'https' or not parsed.hostname:
        return False
    hostname = parsed.hostname
    if hostname == 'localhost' or hostname.endswith('.local'):
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
    )


@login_required
@require_POST
def push_subscribe(request):
    if not push_is_configured():
        return JsonResponse(
            {'ok': False, 'error': 'Push er ikke konfigureret på serveren.'},
            status=503,
        )

    data = _json_body(request)
    endpoint = str(data.get('endpoint') or '').strip()
    keys = data.get('keys') or {}
    p256dh = str(keys.get('p256dh') or '').strip()
    auth = str(keys.get('auth') or '').strip()
    if not endpoint or not p256dh or not auth:
        return JsonResponse(
            {'ok': False, 'error': 'Ufuldstændigt abonnement.'}, status=400
        )
    if not _is_valid_push_endpoint(endpoint):
        return JsonResponse(
            {'ok': False, 'error': 'Ugyldig push-adresse.'}, status=400
        )

    subscription, created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:300],
            'failure_count': 0,
        },
    )
    return JsonResponse(
        {
            'ok': True,
            'created': created,
            'subscription_id': subscription.pk,
            'count': request.user.push_subscriptions.count(),
        }
    )


@login_required
@require_POST
def push_unsubscribe(request):
    data = _json_body(request)
    endpoint = str(data.get('endpoint') or '').strip()
    deleted, _ = PushSubscription.objects.filter(
        user=request.user, endpoint=endpoint
    ).delete()
    return JsonResponse(
        {
            'ok': True,
            'deleted': deleted,
            'count': request.user.push_subscriptions.count(),
        }
    )


@login_required
@require_POST
def push_test(request):
    if not push_is_configured():
        return JsonResponse(
            {'ok': False, 'error': 'Push er ikke konfigureret på serveren.'},
            status=503,
        )
    if not request.user.push_subscriptions.exists():
        return JsonResponse(
            {'ok': False, 'error': 'Slå notifikationer til på denne enhed først.'},
            status=409,
        )
    sent = send_test_notification(request.user)
    if not sent:
        return JsonResponse(
            {'ok': False, 'error': 'Testnotifikationen kunne ikke sendes.'},
            status=502,
        )
    return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
# Calendar feeds
# ---------------------------------------------------------------------------
@login_required
@require_POST
def rotate_calendar_token(request):
    token, _ = CalendarFeedToken.objects.get_or_create(user=request.user)
    token.rotate()
    messages.success(
        request,
        'Kalenderlinket er fornyet. Gamle links virker ikke længere.',
    )
    return redirect('notifications_settings')


@require_GET
def calendar_feed(request, token):
    """Public, token-authenticated iCalendar feed for a device calendar."""
    feed = request.GET.get('feed') or calendar_feeds.FEED_ALL
    if feed not in calendar_feeds.FEED_CHOICES:
        feed = calendar_feeds.FEED_ALL

    try:
        token_obj = CalendarFeedToken.objects.select_related('user').get(token=token)
    except (CalendarFeedToken.DoesNotExist, ValidationError, ValueError):
        raise Http404('Kalenderfeed findes ikke.')

    if not token_obj.user.is_active:
        raise Http404('Kalenderfeed findes ikke.')

    payload = calendar_feeds.build_calendar(token_obj.user, feed)
    response = HttpResponse(payload, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'inline; filename="sks-{feed}.ics"'
    response['Cache-Control'] = 'private, max-age=300'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
