"""Discord-notifikationer for SOSBooking; sendes asynkront via Celery."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from organization.tasks import notify_booking_change
from SOS.models import SOSBooking

logger = logging.getLogger(__name__)


@receiver(post_save, sender=SOSBooking)
def notify_discord_on_sosbooking_change(sender, instance, created, **kwargs):
    """Planlæg Discord-notifikation når en SOSBooking oprettes eller opdateres."""
    try:
        flags = []
        if instance.assistance_needed:
            flags.append("🆘 Assistance nødvendig")
        if instance.delivery_needed:
            flags.append("🚚 Levering nødvendig")
        fields = [
            ("Antal", str(instance.quantity)),
            ("Dato", f"{instance.start_date.strftime('%d/%m')} {instance.start_time.strftime('%H:%M')}"),
        ]
        if flags:
            fields.append(("Behov", "\n".join(flags)))
        notify_booking_change(
            instance, created, "SOS", "🆘 SOS Notifikationer", "sos/SOS/SOSBooking/detail", fields
        )
    except Exception:
        logger.exception("Discord-notifikation fejlede for SOSBooking %s", instance.pk)
