"""Service helpers for Butikken item proposals."""
from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from emailing.services import send_email
from organization.models import Team
from organization.tasks import build_embed, enqueue_discord_embed

from .models import ButikkenBooking, ButikkenItem, ButikkenOrder

logger = logging.getLogger(__name__)

BUTIKKEN_DISCORD_USERNAME = "🛒 Butikken Notifikationer"


def remove_bookings_for_rejected_proposal(item: ButikkenItem) -> int:
    """Remove a rejected proposal from all orders and notify the affected teams.

    Returns the number of removed booking lines. Notifications are queued after
    the current transaction commits so a rollback never sends a false message.
    """
    bookings = list(
        ButikkenBooking.objects.filter(item=item).select_related("order__team", "team")
    )
    if not bookings:
        return 0

    team_ids: set[int] = set()
    order_ids: set[int] = set()
    quantities: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for booking in bookings:
        team_id = booking.team_id or (booking.order.team_id if booking.order else None)
        if team_id:
            team_ids.add(team_id)
            quantities[team_id] += booking.quantity
        if booking.order_id:
            order_ids.add(booking.order_id)

    ButikkenBooking.objects.filter(pk__in=[booking.pk for booking in bookings]).delete()

    if team_ids:
        transaction.on_commit(
            lambda: _notify_teams_about_rejection(
                item.pk,
                sorted(team_ids),
                sorted(order_ids),
                dict(quantities),
            )
        )

    return len(bookings)


def _notify_teams_about_rejection(
    item_id: int,
    team_ids: list[int],
    order_ids: list[int],
    quantities: dict[int, Decimal],
) -> None:
    item = ButikkenItem.objects.filter(pk=item_id).first()
    if item is None:
        return

    orders = list(
        ButikkenOrder.objects.filter(pk__in=order_ids).select_related(
            "team", "team_contact"
        )
    )
    orders_by_team: dict[int, list[ButikkenOrder]] = defaultdict(list)
    for order in orders:
        orders_by_team[order.team_id].append(order)

    orders_url = f"{settings.SITE_URL}{reverse('Butikken_ButikkenOrder_list')}"

    for team in Team.objects.filter(pk__in=team_ids).only(
        "id", "name", "discord_webhook_url"
    ):
        team_orders = orders_by_team.get(team.pk, [])
        quantity = quantities.get(team.pk, Decimal("0"))

        recipients = set(
            team.volunteer_set.exclude(email="").values_list("email", flat=True)
        )
        recipients.update(
            order.team_contact.email
            for order in team_orders
            if order.team_contact and order.team_contact.email
        )
        recipients = sorted(email for email in recipients if email)

        if recipients:
            try:
                send_email(
                    f"Vareforslag afvist: {item.name}",
                    "Butikken/item_proposal_rejected_email.html",
                    {
                        "item": item,
                        "team": team,
                        "orders": team_orders,
                        "quantity": quantity,
                        "orders_url": orders_url,
                    },
                    recipients,
                )
            except Exception:
                logger.exception(
                    "Kunne ikke sende afvisnings-email for vareforslag %s", item_id
                )

        if team.discord_webhook_url:
            embed = build_embed(
                title=f"Vareforslag afvist | Butikken: {item.name}",
                description=(
                    "Vareforslaget er afvist og fjernet fra bestillingen."
                ),
                status="Rejected",
                url=orders_url,
                fields=[
                    ("Team", team.name),
                    (
                        "Bestillinger",
                        ", ".join(f"#{order.pk}" for order in team_orders) or "-",
                    ),
                    ("Antal", f"{quantity} {item.content_unit}".strip()),
                ],
            )
            enqueue_discord_embed(team.pk, embed, BUTIKKEN_DISCORD_USERNAME)
