"""Discord-notifikationer for AktivitetsTeamBooking; sendes asynkront via Celery."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from AktivitetsTeam.models import AktivitetsTeamBooking
from organization.tasks import notify_booking_change

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AktivitetsTeamBooking)
def notify_discord_on_aktivitetsteambooking_change(sender, instance, created, **kwargs):
    """Planlæg Discord-notifikation når en AktivitetsTeamBooking oprettes eller opdateres."""
    try:
        assigned = ", ".join(v.get_full_name() for v in instance.assigned_aktivitetsteam.all()) or "Ikke tildelt"
        notify_booking_change(
            instance, created, "AktivitetsTeam", "👥 AktivitetsTeam Notifikationer",
            "aktivitetsteam/AktivitetsTeam/AktivitetsTeamBooking/detail",
            [
                ("Dato", f"{instance.start_date.strftime('%d/%m')} {instance.start_time.strftime('%H:%M')}"),
                ("Tildelt AT", assigned),
            ],
        )
    except Exception:
        logger.exception("Discord-notifikation fejlede for AktivitetsTeamBooking %s", instance.pk)
