"""iCalendar feed generation for device calendar subscriptions.

A feed contains the requesting user's team duties (tjanser) and the programme
blocks for their teams plus the shared framework ("fælles rammeprogram"). The
calendar client polls the URL, so edits made in the app show up without any
extra push from the server.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from datetime import time as datetime_time
from datetime import timezone as dt_timezone
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from icalendar import Alarm, Calendar, Event

from .services import absolute_url

FEED_ALL = 'all'
FEED_TASKS = 'tasks'
FEED_PROGRAM = 'program'

FEED_CHOICES = {
    FEED_ALL: 'Opgaver og rammeprogram',
    FEED_TASKS: 'Opgaver (tjanser)',
    FEED_PROGRAM: 'Rammeprogram',
}

CATEGORY_PREFIX = {
    'fixed': 'Fast program',
    'recommended': 'Anbefaling',
    'placeholder': 'Plads til eget program',
    'preparation': 'Forberedelse',
}

PROGRAM_ALARM_MINUTES = 30
TASK_ALARM_HOURS = 8
FEED_REFRESH_MINUTES = 15


def _uid_domain() -> str:
    hostname = urlparse(settings.SITE_URL).hostname
    return hostname or 'bookingsystem.local'


def _utc(day: date, value: datetime_time) -> datetime:
    naive = datetime.combine(day, value)
    aware = timezone.make_aware(naive, timezone.get_current_timezone())
    return aware.astimezone(dt_timezone.utc)


def _tiptap_text(value) -> str:
    """Extract readable text from a TipTap document.

    The field returns a ``TipTapValue`` (with ``.doc``/``.html``); older rows or
    plain dicts can also reach this function.
    """
    if hasattr(value, 'doc'):
        return _tiptap_text(value.doc)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return ' '.join(filter(None, (_tiptap_text(item) for item in value))).strip()
    if not isinstance(value, dict):
        return ''

    # TipTapJSONField stores ``{'doc': {...}, 'html': ...}``; the content
    # itself is the inner document.
    if 'doc' in value:
        return _tiptap_text(value.get('doc'))

    node_type = value.get('type')
    if node_type == 'text':
        return str(value.get('text', '')).strip()
    if node_type == 'hardBreak':
        return '\n'

    children = [
        _tiptap_text(child)
        for child in value.get('content', [])
        if isinstance(child, dict)
    ]
    text = ' '.join(filter(None, children)).strip()
    if node_type in ('paragraph', 'heading', 'listItem', 'blockquote', 'codeBlock'):
        return f'{text}\n'
    return text


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    return '\n'.join(line for line in lines if line)


def _team_ids_for(user) -> list[int]:
    from organization.models import TeamMembership

    return list(
        TeamMembership.objects.filter(member=user).values_list('team_id', flat=True)
    )


def _program_queryset(user):
    """Blocks belonging to the user's teams plus relevant shared framework."""
    from organization.models import ProgramBlock

    team_ids = _team_ids_for(user)
    cutoff = timezone.localdate() - timedelta(days=30)

    team_blocks = Q(team_id__in=team_ids)
    shared_blocks = Q(team__isnull=True, event__is_active=True)
    return (
        ProgramBlock.objects.filter(team_blocks | shared_blocks)
        .filter(day__gte=cutoff)
        .select_related('event', 'team')
        .prefetch_related('responsible')
        .order_by('day', 'start_time', 'pk')
    )


def _tasks_queryset(user):
    from organization.models import TjanseOwnership

    team_ids = _team_ids_for(user)
    cutoff = timezone.localdate() - timedelta(days=30)
    return (
        TjanseOwnership.objects.filter(team_id__in=team_ids, due_date__gte=cutoff)
        .select_related('tjanse', 'team', 'event')
        .order_by('due_date', 'pk')
    )


def _category_label(block) -> str:
    return CATEGORY_PREFIX.get(block.category, block.category)


def _program_event(block) -> Event:
    domain = _uid_domain()
    event = Event()
    event.add('uid', f'program-block-{block.pk}@{domain}')
    event.add('summary', block.title)
    event.add('dtstart', _utc(block.day, block.start_time))
    event.add('dtend', _utc(block.day, block.end_time))
    event.add('dtstamp', timezone.now())
    event.add('created', block.created)
    event.add('last-modified', block.last_updated)
    event.add(
        'sequence',
        min(int(block.last_updated.timestamp()), 2_147_483_647),
    )
    event.add('categories', [_category_label(block), 'Rammeprogram'])
    event.add('url', absolute_url(block.get_absolute_url()))
    event.add('transp', 'OPAQUE')

    description_lines = [
        block.event.name,
        f'Team: {block.team.name}' if block.team_id else 'Fælles rammeprogram',
        f'Kategori: {_category_label(block)}',
    ]
    responsible = ', '.join(
        str(volunteer) for volunteer in block.responsible.all()
    )
    if responsible:
        description_lines.append(f'Ansvarlig: {responsible}')
    content = _clean_text(_tiptap_text(block.content))
    if content:
        description_lines.append('')
        description_lines.append(content)
    event.add('description', '\n'.join(description_lines))

    if block.category != 'placeholder':
        alarm = Alarm()
        alarm.add('action', 'DISPLAY')
        alarm.add('trigger', timedelta(minutes=-PROGRAM_ALARM_MINUTES))
        alarm.add(
            'description',
            f'{block.title} starter om {PROGRAM_ALARM_MINUTES} minutter',
        )
        event.add_component(alarm)

    return event


def _task_event(ownership) -> Event:
    domain = _uid_domain()
    event = Event()
    event.add('uid', f'tjanse-ownership-{ownership.pk}@{domain}')
    event.add('summary', f'Opgave: {ownership.tjanse.title}')
    event.add('dtstart', ownership.due_date)
    event.add('dtend', ownership.due_date + timedelta(days=1))
    event.add('dtstamp', timezone.now())
    event.add('created', ownership.created)
    event.add('last-modified', ownership.last_updated)
    event.add(
        'sequence',
        min(int(ownership.last_updated.timestamp()), 2_147_483_647),
    )
    event.add('categories', ['Tjanse'])
    event.add('url', absolute_url(ownership.get_absolute_url()))
    event.add('transp', 'TRANSPARENT')

    description_lines = [
        ownership.event.name,
        f'Team: {ownership.team.name}',
        f'Status: {ownership.get_status_display()}',
        f'Prioritet: {ownership.tjanse.get_priority_display()}',
    ]
    if ownership.tjanse.area:
        description_lines.append(f'Område: {ownership.tjanse.area}')
    if ownership.tjanse.estimated_minutes:
        description_lines.append(
            f'Anslået tid: {ownership.tjanse.estimated_minutes} min.'
        )
    content = _clean_text(_tiptap_text(ownership.tjanse.description))
    if content:
        description_lines.append('')
        description_lines.append(content)
    event.add('description', '\n'.join(description_lines))

    alarm = Alarm()
    alarm.add('action', 'DISPLAY')
    alarm.add('trigger', timedelta(hours=TASK_ALARM_HOURS))
    alarm.add(
        'description',
        f'Opgaven "{ownership.tjanse.title}" skal løses i dag',
    )
    event.add_component(alarm)

    return event


def build_calendar(user, feed: str = FEED_ALL) -> bytes:
    """Render an iCalendar document for ``user`` and the requested feed."""
    calendar = Calendar()
    calendar.add('prodid', f'-//FDF SKS Bookingsystem//{_uid_domain()}//DA')
    calendar.add('version', '2.0')
    calendar.add('calscale', 'GREGORIAN')
    calendar.add('method', 'PUBLISH')
    calendar.add('x-wr-calname', f'SKS Booking - {FEED_CHOICES[feed]}')
    calendar.add('x-wr-timezone', settings.TIME_ZONE)
    calendar.add(
        'refresh-interval',
        timedelta(minutes=FEED_REFRESH_MINUTES),
        parameters={'VALUE': 'DURATION'},
    )
    calendar.add('x-published-ttl', f'PT{FEED_REFRESH_MINUTES}M')

    if feed in (FEED_ALL, FEED_TASKS):
        for ownership in _tasks_queryset(user):
            calendar.add_component(_task_event(ownership))

    if feed in (FEED_ALL, FEED_PROGRAM):
        for block in _program_queryset(user):
            calendar.add_component(_program_event(block))

    return calendar.to_ical()


def feed_url_path(token, feed: str) -> str:
    from django.urls import reverse

    url = reverse('notifications_calendar_feed', args=[token])
    if feed == FEED_ALL:
        return url
    return f'{url}?feed={feed}'


def webcal_url(url: str) -> str:
    """Convert an https URL to webcal, which device calendars understand."""
    for prefix in ('https://', 'http://'):
        if url.startswith(prefix):
            return 'webcal://' + url[len(prefix):]
    return url
