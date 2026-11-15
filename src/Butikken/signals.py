"""Signals for Butikken: booking-notifikationer og oprydning efter afviste forslag."""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from Butikken.models import ButikkenBooking, ButikkenItem
from organization.tasks import notify_booking_change
from utils.formatting import short_date, short_time

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ButikkenItem)
def remember_butikkenitem_status(sender, instance, **kwargs):
    """Remember the previous status so the post_save handler can detect changes."""
    instance._previous_status = None
    if instance.pk:
        instance._previous_status = (
            ButikkenItem.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=ButikkenItem)
def remove_rejected_proposal_from_orders(sender, instance, created, **kwargs):
    """Remove order lines when a pending/special proposal is rejected.

    Covers every code path that saves the item, including inline edits in the
    admin. Catalog items (``Active``) are never removed this way.
    """
    if created or instance.status != ButikkenItem.STATUS_REJECTED:
        return
    previous = getattr(instance, "_previous_status", None)
    if previous not in (ButikkenItem.STATUS_PENDING, ButikkenItem.STATUS_SPECIAL):
        return

    from Butikken.services import remove_bookings_for_rejected_proposal

    remove_bookings_for_rejected_proposal(instance)


@receiver(post_save, sender=ButikkenBooking)
def notify_discord_on_butikkenbooking_change(sender, instance, created, **kwargs):
    """Planlæg Discord-notifikation når en ButikkenBooking oprettes eller opdateres."""
    try:
        notify_booking_change(
            instance, created, "Butikken", "🛒 Butikken Notifikationer",
            "butikken/Butikken/ButikkenBooking/detail",
            [
                ("Dato", f"{short_date(instance.start_date)} {short_time(instance.start_time)}".strip()),
                ("Antal", f"{instance.quantity} {instance.unit}"),
            ],
        )
    except Exception:
        logger.exception("Discord-notifikation fejlede for ButikkenBooking %s", instance.pk)
