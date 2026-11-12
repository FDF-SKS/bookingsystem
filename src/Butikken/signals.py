"""Discord-notifikationer for ButikkenBooking; sendes asynkront via Celery."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from Butikken.models import ButikkenBooking
from organization.tasks import notify_booking_change
from utils.formatting import short_date, short_time

logger = logging.getLogger(__name__)


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
