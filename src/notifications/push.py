"""Web Push transport.

Notifications are delivered through the browser push service (APNs on iOS,
FCM on Android/Chrome). ``pywebpush`` performs the VAPID signing and payload
encryption; this module only deals with our own subscription rows and with
pruning endpoints the push service has permanently rejected.
"""
from __future__ import annotations

import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

from .models import PushSubscription

logger = logging.getLogger(__name__)


def push_is_configured() -> bool:
    """Whether the server has a VAPID key pair to sign push messages with."""
    return bool(
        getattr(settings, 'WEBPUSH_VAPID_PUBLIC_KEY', '')
        and getattr(settings, 'WEBPUSH_VAPID_PRIVATE_KEY', '')
    )


def _send(subscription: PushSubscription, payload: dict) -> bool:
    """Send one payload to one subscription and prune dead endpoints.

    Returns ``False`` when the push service reports that the subscription no
    longer exists, so it is not counted as delivered.
    """
    try:
        webpush(
            subscription_info=subscription.subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
            vapid_claims={'sub': settings.WEBPUSH_VAPID_SUBJECT},
            ttl=int(getattr(settings, 'WEBPUSH_TTL_SECONDS', 86400)),
        )
    except WebPushException as exc:
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        if status in (404, 410):
            # The browser dropped the subscription (uninstalled, permission reset).
            subscription.delete()
            logger.info('Fjernede udløbet push-abonnement %s', subscription.pk)
            return False
        _record_failure(subscription, exc)
        raise
    except Exception as exc:  # network errors, malformed keys, ...
        _record_failure(subscription, exc)
        raise

    if subscription.failure_count:
        PushSubscription.objects.filter(pk=subscription.pk).update(failure_count=0)
    return True


def _record_failure(subscription: PushSubscription, exc: Exception) -> None:
    PushSubscription.objects.filter(pk=subscription.pk).update(
        failure_count=subscription.failure_count + 1
    )
    logger.warning(
        'Push til abonnement %s (bruger %s) fejlede: %s',
        subscription.pk,
        subscription.user_id,
        exc,
    )


def send_to_users(user_ids, payload: dict) -> int:
    """Send ``payload`` to every push endpoint of the given users.

    Returns the number of endpoints the push service accepted.
    """
    if not push_is_configured():
        logger.info('Push er ikke konfigureret; springer afsendelse over.')
        return 0

    user_ids = list(user_ids)
    if not user_ids:
        return 0

    delivered = 0
    for subscription in PushSubscription.objects.filter(user_id__in=user_ids).iterator():
        try:
            if _send(subscription, payload):
                delivered += 1
        except Exception:
            # One broken endpoint must not stop the remaining deliveries.
            continue
    return delivered


def send_to_user(user_id, payload: dict) -> int:
    return send_to_users([user_id], payload)
