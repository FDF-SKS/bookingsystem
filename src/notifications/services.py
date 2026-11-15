"""Business logic for deciding who to notify and what the message says."""
from __future__ import annotations

import logging
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from .bookings import source_for
from .models import NotificationPreference
from .push import push_is_configured, send_to_users

logger = logging.getLogger(__name__)

KIND_BOOKING = 'booking'
KIND_TASK = 'task'
KIND_UPCOMING = 'upcoming'

PREFERENCE_FIELDS = {
    KIND_BOOKING: 'notify_bookings',
    KIND_TASK: 'notify_tasks',
    KIND_UPCOMING: 'notify_upcoming',
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def static_url(path: str) -> str:
    """Absolute URL for a static file, as push services expect."""
    from django.templatetags.static import static

    return urljoin(f'{settings.SITE_URL}/', static(path))


def absolute_url(path: str) -> str:
    return urljoin(f'{settings.SITE_URL}/', path.lstrip('/'))


def get_preference(user) -> NotificationPreference:
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    return preference


def users_with_kind_enabled(user_ids, kind: str) -> list[int]:
    """Drop users who turned this category off (missing rows mean enabled)."""
    field = PREFERENCE_FIELDS.get(kind)
    user_ids = list({uid for uid in user_ids if uid})
    if not field or not user_ids:
        return user_ids
    disabled = set(
        NotificationPreference.objects.filter(
            user_id__in=user_ids, **{field: False}
        ).values_list('user_id', flat=True)
    )
    return [uid for uid in user_ids if uid not in disabled]


def team_member_ids(team_id) -> list[int]:
    from organization.models import TeamMembership

    if not team_id:
        return []
    return list(
        TeamMembership.objects.filter(team_id=team_id).values_list(
            'member_id', flat=True
        )
    )


def program_block_recipient_ids(block) -> list[int]:
    """Team members for a team block; event participants for a shared block.

    Volunteers explicitly marked as responsible are always included, even if
    they are not on the block's team.
    """
    responsible_ids = [volunteer.pk for volunteer in block.responsible.all()]
    if block.team_id:
        return team_member_ids(block.team_id) + responsible_ids

    from organization.models import EventMembership, TeamEventMembership

    volunteer_ids = list(
        EventMembership.objects.filter(event_id=block.event_id).values_list(
            'volunteer_id', flat=True
        )
    )
    team_ids = list(
        TeamEventMembership.objects.filter(
            event_id=block.event_id
        ).values_list('team_id', flat=True)
    )
    team_member_ids_for_event = [
        member_id
        for team_id in team_ids
        for member_id in team_member_ids(team_id)
    ]
    return volunteer_ids + team_member_ids_for_event + responsible_ids


def notification_payload(
    *,
    title: str,
    body: str,
    url: str,
    tag: str,
    kind: str,
) -> dict:
    return {
        'title': title,
        'body': body,
        'url': absolute_url(url),
        'tag': tag,
        'kind': kind,
        'icon': static_url('icons/icon-192.png'),
        'badge': static_url('icons/badge-72.png'),
    }


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
def enqueue_push(user_ids, payload: dict, kind: str) -> None:
    """Filter by preferences and deliver after the current transaction.

    Signal handlers run inside the caller's transaction. Dispatching on
    ``on_commit`` avoids telling users about a booking that was rolled back, and
    keeps any push/network failure away from the request that saved the row.
    """
    if not push_is_configured():
        return
    recipients = users_with_kind_enabled(user_ids, kind)
    if not recipients:
        return

    def _dispatch() -> None:
        from .tasks import send_push_to_users_task

        try:
            send_push_to_users_task.delay(recipients, payload)
        except Exception:
            # The broker may be unavailable (e.g. a standalone management
            # command). Fall back to sending inline rather than losing the
            # notification entirely.
            logger.warning(
                'Kunne ikke lægge push-besked i kø; sender inline.', exc_info=True
            )
            _send_inline(recipients, payload)

    transaction.on_commit(_dispatch)


def _send_inline(user_ids, payload) -> None:
    try:
        send_to_users(user_ids, payload)
    except Exception:
        logger.exception('Inline push-afsendelse fejlede.')


def send_test_notification(user) -> bool:
    """Send a single test push to the user's own devices."""
    if not push_is_configured():
        return False
    payload = notification_payload(
        title='Testnotifikation',
        body='Push-notifikationer virker på denne enhed.',
        url=reverse('notifications_settings'),
        tag='test',
        kind=KIND_UPCOMING,
    )
    return send_to_users([user.pk], payload) > 0


# ---------------------------------------------------------------------------
# Booking decisions
# ---------------------------------------------------------------------------
_STATUS_WORDS = {
    'Approved': 'godkendt',
    'Rejected': 'afvist',
}


def _booking_label(booking, source) -> str:
    item = getattr(booking, source.item_attr, None)
    item_name = getattr(item, 'name', None)
    if item_name:
        return item_name
    return source.module_label


def _booking_when(booking) -> str:
    start_date = getattr(booking, 'start_date', None)
    start_time = getattr(booking, 'start_time', None)
    if not start_date:
        return ''
    parts = [date_format(start_date, 'j. F')]
    if start_time:
        parts.append(time_format(start_time))
    return ' '.join(parts)


def time_format(value) -> str:
    try:
        return value.strftime('%H:%M')
    except AttributeError:
        return str(value)


def set_booking_status(queryset, status: str) -> int:
    """Set ``status`` on each row, avoiding an accidental signal storm.

    Admin bulk actions used ``queryset.update()``, which bypasses ``post_save``
    and therefore every notification channel (Discord, push). For booking models
    we keep the bulk update (so a 50-row approval does not send 50 Discord
    messages), then send one grouped push notification per team. Other models
    keep their original behaviour.
    """
    if source_for(queryset.model) is None:
        return queryset.update(status=status)

    bookings = [booking for booking in queryset if booking.status != status]
    if not bookings:
        return 0

    update_fields = {'status': status}
    if any(field.name == 'last_updated' for field in queryset.model._meta.fields):
        update_fields['last_updated'] = timezone.now()
    queryset.model._default_manager.filter(
        pk__in=[booking.pk for booking in bookings]
    ).update(**update_fields)
    for booking in bookings:
        booking.status = status

    notify_booking_decisions(bookings, status)
    return len(bookings)


def _booking_recipient_ids(team_id, bookings) -> list[int]:
    """Team members plus the booking's contact person."""
    recipient_ids = team_member_ids(team_id)
    for booking in bookings:
        contact_id = getattr(booking, 'team_contact_id', None)
        if contact_id:
            recipient_ids.append(contact_id)
    return recipient_ids


def notify_booking_decisions(bookings, new_status: str) -> None:
    """Announce approved/rejected bookings to the owning teams.

    Bookings are grouped per team so a bulk admin action produces one
    notification per team instead of one per row.
    """
    word = _STATUS_WORDS.get(new_status)
    if not word:
        return

    grouped: dict[int, list] = {}
    for booking in bookings:
        if booking.team_id:
            grouped.setdefault(booking.team_id, []).append(booking)

    for team_id, team_bookings in grouped.items():
        source = source_for(team_bookings[0])
        if source is None:
            continue

        labels = [_booking_label(booking, source) for booking in team_bookings]
        if len(team_bookings) == 1:
            booking = team_bookings[0]
            title = f'Booking {word}: {source.module_label}'
            when = _booking_when(booking)
            body = ' · '.join(part for part in (labels[0], when) if part)
            url = reverse(source.detail_url_name, args=[booking.pk])
            tag = f'booking-{source.app_label}-{booking.pk}'
        else:
            title = f'{len(team_bookings)} bookinger {word}'
            body = ', '.join(labels)[:180]
            url = reverse(source.detail_url_name, args=[team_bookings[0].pk])
            tag = f'booking-bulk-{source.app_label}-{team_id}'

        enqueue_push(
            _booking_recipient_ids(team_id, team_bookings),
            notification_payload(
                title=title,
                body=body,
                url=url,
                tag=tag,
                kind=KIND_BOOKING,
            ),
            KIND_BOOKING,
        )


# ---------------------------------------------------------------------------
# New tasks
# ---------------------------------------------------------------------------
def notify_new_tjanse(ownership) -> None:
    """Tell a team that a new tjanse (duty) has been assigned to them."""
    due = (
        f' · frist {date_format(ownership.due_date, "j. F")}'
        if ownership.due_date
        else ''
    )
    enqueue_push(
        team_member_ids(ownership.team_id),
        notification_payload(
            title=f'Ny opgave: {ownership.tjanse.title}',
            body=f'{ownership.event.name}{due}',
            url=reverse('organization_TjanseOwnership_detail', args=[ownership.pk]),
            tag=f'tjanse-{ownership.pk}',
            kind=KIND_TASK,
        ),
        KIND_TASK,
    )


def notify_slutrengoring_assignment(assignment) -> None:
    """Tell a team that a slutrengøring task has been assigned to them."""
    enqueue_push(
        team_member_ids(assignment.team_id),
        notification_payload(
            title=f'Ny slutrengøring: {assignment.tjanse.title}',
            body=assignment.event.name,
            url=reverse('organization_Slutrengoring_detail', args=[assignment.pk]),
            tag=f'slutrengoring-{assignment.pk}',
            kind=KIND_TASK,
        ),
        KIND_TASK,
    )


# ---------------------------------------------------------------------------
# Reminders ("about to start")
# ---------------------------------------------------------------------------
def notify_program_block_upcoming(block, minutes: int) -> None:
    team = block.team.name if block.team_id else 'Fælles program'
    enqueue_push(
        program_block_recipient_ids(block),
        notification_payload(
            title=f'Om {minutes} min: {block.title}',
            body=(
                f'{block.event.name} · {team} · '
                f'{time_format(block.start_time)}-{time_format(block.end_time)}'
            ),
            url=block.get_absolute_url(),
            tag=f'program-block-{block.pk}',
            kind=KIND_UPCOMING,
        ),
        KIND_UPCOMING,
    )


def notify_tjanse_due(ownership) -> None:
    enqueue_push(
        team_member_ids(ownership.team_id),
        notification_payload(
            title=f'Opgave i dag: {ownership.tjanse.title}',
            body=f'{ownership.team.name} · {ownership.event.name}',
            url=reverse('organization_TjanseOwnership_detail', args=[ownership.pk]),
            tag=f'tjanse-due-{ownership.pk}',
            kind=KIND_UPCOMING,
        ),
        KIND_UPCOMING,
    )


def local_now():
    return timezone.localtime()
