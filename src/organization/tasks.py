"""Celery-tasks for organization."""
from __future__ import annotations

import logging
from typing import Any

import requests
from celery import shared_task
from django.conf import settings
from django.db import transaction

from .discord_services import (
    build_embed,
    DiscordRateLimited,
    DiscordTransientError,
    send_team_embed,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 5


@shared_task(bind=True, max_retries=MAX_RETRIES, ignore_result=True)
def send_discord_embed_task(
    self, team_id: int, embed: dict[str, Any], username: str | None = None
) -> None:
    """
    Send en Discord embed til et teams forumtråd.

    429 genforsøges efter Discords `retry_after`; netværksfejl og 5xx genforsøges
    med eksponentiel backoff (max 3 gange).
    """
    try:
        send_team_embed(team_id, embed, username)
    except DiscordRateLimited as exc:
        logger.warning("Discord rate limit for team %s; genforsøger om %ss", team_id, exc.retry_after)
        raise self.retry(exc=exc, countdown=exc.retry_after)
    except (requests.RequestException, DiscordTransientError) as exc:
        countdown = BACKOFF_BASE_SECONDS * 2 ** self.request.retries
        logger.warning(
            "Discord fejl for team %s (%s); forsøg %s/%s om %ss",
            team_id, exc, self.request.retries + 1, MAX_RETRIES, countdown,
        )
        raise self.retry(exc=exc, countdown=countdown)


def enqueue_discord_embed(
    team_id: int | None, embed: dict[str, Any], username: str | None = None
) -> None:
    """Planlæg afsendelse efter transaktionen er committet; fejl må aldrig vælte et save()."""
    if not team_id:
        return

    def _dispatch() -> None:
        try:
            send_discord_embed_task.delay(team_id, embed, username)
        except Exception:
            logger.exception("Kunne ikke sende Discord-task for team %s i kø", team_id)

    transaction.on_commit(_dispatch)


def notify_booking_change(
    booking: Any,
    created: bool,
    module: str,
    username: str,
    url_path: str,
    fields: list[tuple[str, str]] | None = None,
) -> None:
    """Byg en embed for en booking og send den asynkront til bookingens team."""
    team = getattr(booking, "team", None)
    if team is None or not team.discord_webhook_url:
        return

    contact = getattr(booking, "team_contact", None)
    item = getattr(booking, "item", None)
    all_fields = [
        ("Team", team.name),
        ("Kontakt", contact.get_full_name() if contact else "Ikke angivet"),
        *(fields or []),
    ]
    remarks = getattr(booking, "remarks", "") or ""
    embed = build_embed(
        title=f"{'Ny booking' if created else 'Booking opdateret'} | {module}: {item.name if item else 'Ikke valgt'}",
        description=remarks,
        status=getattr(booking, "status", None) or ("Created" if created else None),
        url=f"{settings.SITE_URL}/{url_path}/{booking.pk}/",
        fields=all_fields,
    )
    enqueue_discord_embed(team.pk, embed, username)
