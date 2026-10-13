"""Discord webhook-integration: embed-bygning og afsendelse til et teams forumtråd."""
from __future__ import annotations

import logging
from datetime import datetime, timezone as dt_timezone
from typing import Any

import requests
from django.db import transaction

from .models import Team

logger = logging.getLogger(__name__)

THREAD_NAME = "Bookingsystem & Tjanser"
REQUEST_TIMEOUT = 10
DEFAULT_RETRY_AFTER = 5.0

STATUS_COLORS: dict[str, int] = {
    "Approved": 0x2ECC71,
    "Pending": 0xF1C40F,
    "Rejected": 0xE74C3C,
    "Udleveret": 0x3498DB,
    "Created": 0x5865F2,
}
DEFAULT_COLOR = 0x95A5A6


class DiscordRateLimited(Exception):
    """Discord svarede 429; `retry_after` er antal sekunder der skal ventes."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


class DiscordTransientError(Exception):
    """Midlertidig fejl (5xx) som kan genforsøges."""


def build_embed(
    title: str,
    description: str = "",
    status: str | None = None,
    changed_by: str | None = None,
    url: str | None = None,
    fields: list[tuple[str, str]] | None = None,
    color: int | None = None,
) -> dict[str, Any]:
    """Byg en Discord embed-dict med farve ud fra status."""
    embed: dict[str, Any] = {
        "title": title[:256],
        "description": description[:4000],
        "color": color if color is not None else STATUS_COLORS.get(status or "", DEFAULT_COLOR),
        "timestamp": datetime.now(dt_timezone.utc).isoformat(),
    }
    if url:
        embed["url"] = url
    embed_fields = [
        {"name": name[:256], "value": (value or "-")[:1024], "inline": True}
        for name, value in (fields or [])
    ]
    if status:
        embed_fields.insert(0, {"name": "Status", "value": status[:1024], "inline": True})
    if changed_by:
        embed_fields.append({"name": "Ændret af", "value": changed_by[:1024], "inline": True})
    if embed_fields:
        embed["fields"] = embed_fields[:25]
    return embed


def _post(url: str, payload: dict[str, Any], params: dict[str, str]) -> requests.Response:
    """Send til webhook og oversæt rate-limits og 5xx til exceptions."""
    response = requests.post(url, json=payload, params=params, timeout=REQUEST_TIMEOUT)
    if response.status_code == 429:
        try:
            retry_after = float(response.json().get("retry_after", DEFAULT_RETRY_AFTER))
        except (ValueError, TypeError):
            retry_after = DEFAULT_RETRY_AFTER
        raise DiscordRateLimited(retry_after)
    if response.status_code >= 500:
        raise DiscordTransientError(f"Discord HTTP {response.status_code}")
    return response


def _create_thread(team_id: int, webhook_url: str, payload: dict[str, Any]) -> bool:
    """Opret tråd og gem ID på teamet. Låser rækken så parallelle tasks ikke opretter dubletter."""
    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team_id)
        if team.discord_topic_thread_id:
            # En anden task nåede først; brug dens tråd.
            response = _post(
                webhook_url, payload, {"thread_id": team.discord_topic_thread_id}
            )
            if response.status_code < 400:
                return True
            team.discord_topic_thread_id = None

        response = _post(
            webhook_url, {**payload, "thread_name": THREAD_NAME}, {"wait": "true"}
        )
        if response.status_code >= 400:
            logger.error(
                "Discord tråd-oprettelse fejlede for team %s: HTTP %s - %s",
                team_id, response.status_code, response.text[:200],
            )
            return False

        thread_id = response.json().get("channel_id")
        if not thread_id:
            logger.error("Discord-svar manglede channel_id for team %s", team_id)
            return False

        team.discord_topic_thread_id = str(thread_id)
        team.save(update_fields=["discord_topic_thread_id"])
        logger.info("Oprettede Discord-tråd %s for team %s", thread_id, team_id)
        return True


def send_team_embed(team_id: int, embed: dict[str, Any], username: str | None = None) -> bool:
    """
    Send en embed til teamets Discord-forumtråd.

    Bruger eksisterende tråd hvis den findes; opretter en ny hvis ingen findes
    eller tråden er slettet (HTTP 400/404). Returnerer True ved succes.
    Rejser DiscordRateLimited / DiscordTransientError / requests.RequestException
    så kalderen (Celery-task) kan genforsøge.
    """
    team = Team.objects.filter(pk=team_id).only(
        "id", "discord_webhook_url", "discord_topic_thread_id"
    ).first()
    if team is None or not team.discord_webhook_url:
        logger.info("Team %s har ingen Discord webhook; springer over", team_id)
        return False

    payload: dict[str, Any] = {"embeds": [embed]}
    if username:
        payload["username"] = username

    if team.discord_topic_thread_id:
        response = _post(
            team.discord_webhook_url, payload, {"thread_id": team.discord_topic_thread_id}
        )
        if response.status_code < 400:
            return True
        if response.status_code not in (400, 404):
            logger.error(
                "Discord webhook fejl for team %s: HTTP %s - %s",
                team_id, response.status_code, response.text[:200],
            )
            return False
        logger.warning(
            "Discord-tråd %s for team %s findes ikke længere (HTTP %s); opretter ny",
            team.discord_topic_thread_id, team_id, response.status_code,
        )
        Team.objects.filter(pk=team_id).update(discord_topic_thread_id=None)

    return _create_thread(team_id, team.discord_webhook_url, payload)
