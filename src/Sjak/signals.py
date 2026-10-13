"""Discord-notifikationer for SjakBooking; sendes asynkront via Celery."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from organization.tasks import notify_booking_change
from Sjak.models import SjakBooking

logger = logging.getLogger(__name__)


@receiver(post_save, sender=SjakBooking)
def notify_discord_on_sjakbooking_change(sender, instance, created, **kwargs):
    """Planlæg Discord-notifikation når en SjakBooking oprettes eller opdateres."""
    try:
        assigned = instance.assigned_sjak.get_full_name() if instance.assigned_sjak else "Ikke tildelt"
        notify_booking_change(
            instance, created, "SJAK", "⚙️ Sjak Notifikationer",
            "sjak/Sjak/SjakBooking/detail",
            [
                ("Antal", str(instance.quantity)),
                ("Dato", f"{instance.start_date.strftime('%d/%m')} {instance.start_time.strftime('%H:%M')}"),
                ("Tildelt", assigned),
            ],
        )
    except Exception:
        logger.exception("Discord-notifikation fejlede for SjakBooking %s", instance.pk)
