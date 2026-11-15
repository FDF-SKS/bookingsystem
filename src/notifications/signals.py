"""Signal receivers that announce booking decisions.

The approved/rejected decision is the only booking change that pushes a
notification; the calendar feed updates itself on every request, so no other
booking writes need extra work.
"""
from __future__ import annotations

import logging

from django.apps import apps
from django.db.models.signals import post_save, pre_save

from .bookings import BOOKING_SOURCES, source_for
from .services import notify_booking_decisions

logger = logging.getLogger(__name__)

DECIDED_STATUSES = ('Approved', 'Rejected')


def _capture_previous_status(sender, instance, **kwargs) -> None:
    """Remember the stored status so ``post_save`` can detect a transition."""
    if not instance.pk:
        instance._notifications_previous_status = None
        return
    instance._notifications_previous_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list('status', flat=True)
        .first()
    )


def _notify_decision(sender, instance, created, **kwargs) -> None:
    previous = getattr(instance, '_notifications_previous_status', None)
    if instance.status not in DECIDED_STATUSES or instance.status == previous:
        return
    if source_for(instance) is None:
        return
    try:
        notify_booking_decisions([instance], instance.status)
    except Exception:
        logger.exception(
            'Push-notifikation for booking %s.%s %s fejlede',
            sender._meta.app_label,
            sender._meta.model_name,
            instance.pk,
        )


def connect_booking_signals() -> None:
    for source in BOOKING_SOURCES:
        try:
            model = apps.get_model(source.app_label, source.model_name)
        except LookupError:
            logger.warning(
                'Booking-modellen %s blev ikke fundet; springer push over.',
                source.label,
            )
            continue
        pre_save.connect(
            _capture_previous_status,
            sender=model,
            dispatch_uid=f'notifications.status.{source.label}',
        )
        post_save.connect(
            _notify_decision,
            sender=model,
            dispatch_uid=f'notifications.decision.{source.label}',
        )


connect_booking_signals()
