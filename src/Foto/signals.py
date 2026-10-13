"""Discord-notifikationer for FotoBooking; sendes asynkront via Celery."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from Foto.models import FotoBooking
from organization.tasks import notify_booking_change

logger = logging.getLogger(__name__)


@receiver(post_save, sender=FotoBooking)
def notify_discord_on_fotobooking_change(sender, instance, created, **kwargs):
    """Planlæg Discord-notifikation når en FotoBooking oprettes eller opdateres."""
    try:
        notify_booking_change(
            instance, created, "Foto", "📷 Foto Notifikationer",
            "foto/Foto/FotoBooking/detail",
            [("Dato", f"{instance.start_date.strftime('%d/%m')} {instance.start_time.strftime('%H:%M')}")],
        )
    except Exception:
        logger.exception("Discord-notifikation fejlede for FotoBooking %s", instance.pk)
