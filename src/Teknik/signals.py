"""
Teknik signal handlers.

Discord/webhook integration for TeknikBooking has been removed. This module
keeps a registered receiver that is a no-op to avoid import-time side effects
or missing-module errors in environments that expect the signal to exist.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

from Teknik.models import TeknikBooking


@receiver(post_save, sender=TeknikBooking)
def notify_discord_on_teknikbooking_change(sender, instance, created, **kwargs):
	"""No-op receiver: Discord integration for TeknikBooking intentionally disabled."""
	return


