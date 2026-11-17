"""Dashboard data: the date-ordered feed and the app sidebar.

The dashboard is intentionally read-only: it aggregates the next relevant
items from the modules a volunteer uses and links into the existing pages.
Keeping the queries here keeps ``core.views.index`` thin.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from constance import config
from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from organization.models import (
    Event,
    EventMembership,
    ProgramBlock,
    TeamEventMembership,
    TeamMembership,
    TjanseOwnership,
    VolunteerAppointment,
)

STATUS_LABELS = {
    'Pending': 'Afventer',
    'Approved': 'Godkendt',
    'Rejected': 'Afvist',
    'Udleveret': 'Udleveret',
    'Afventer': 'Afventer',
    'Godkendt': 'Godkendt',
    'Afvist': 'Afvist',
    'Pakket': 'Pakket',
    'pending': 'Afventer',
    'accepted': 'Accepteret',
    'rejected': 'Afvist',
    'cancelled': 'Annulleret',
    'assigned': 'Tildelt',
    'in_progress': 'I gang',
    'done': 'Udført',
    'not_done': 'Ikke udført',
}

STATUS_COLORS = {
    'Pending': 'warning',
    'Approved': 'success',
    'Rejected': 'danger',
    'Udleveret': 'info',
    'Afventer': 'warning',
    'Godkendt': 'success',
    'Afvist': 'danger',
    'Pakket': 'info',
    'pending': 'warning',
    'accepted': 'success',
    'rejected': 'danger',
    'cancelled': 'secondary',
    'assigned': 'warning',
    'in_progress': 'info',
    'done': 'success',
    'not_done': 'danger',
}

PROGRAM_COLORS = {
    ProgramBlock.CATEGORY_FIXED: 'warning',
    ProgramBlock.CATEGORY_RECOMMENDED: 'primary',
    ProgramBlock.CATEGORY_PLACEHOLDER: 'danger',
    ProgramBlock.CATEGORY_PREPARATION: 'success',
}

# Colour coding from the previous dashboard, kept in one place so the icon and
# the timeline dot for every source stay consistent.
APP_COLORS = {
    'sjak': 'warning',
    'teknik': 'tertiary',
    'aktiviteter': 'success',
    'foto': 'grey',
    'sos': 'danger',
    'depot': 'info',
    'butikken': 'secondary',
    'legeaftale': 'danger',
    'opgave': 'secondary',
}

SECTION_ICONS = {
    'Overblik': 'bi-grid-1x2',
    'Sjak': 'bi-tools',
    'Teknik': 'bi-cpu',
    'Aktiviteter': 'bi-universal-access',
    'Foto': 'bi-camera',
    'SOS': 'bi-heart-pulse',
    'Depot': 'bi-box-seam',
    'Butikken': 'bi-shop',
    'Legeaftaler': 'bi-balloon-heart',
    'Organisation': 'bi-people',
    'Løb': 'bi-flag',
}

EVENT_DEADLINES = (
    ('deadline_sjak', 'Sjak', 'bi-tools', 'APP_ENABLE_SJAK', APP_COLORS['sjak']),
    ('deadline_teknik', 'Teknik', 'bi-cpu', 'APP_ENABLE_TEKNIK', APP_COLORS['teknik']),
    (
        'deadline_mad',
        'Mad',
        'bi-egg-fried',
        'APP_ENABLE_BUTIKKEN',
        APP_COLORS['butikken'],
    ),
    (
        'deadline_aktivitetsteam',
        'Aktiviteter',
        'bi-universal-access',
        'APP_ENABLE_AKTIVITETSTEAM',
        APP_COLORS['aktiviteter'],
    ),
    ('deadline_foto', 'Foto', 'bi-camera', 'APP_ENABLE_FOTO', APP_COLORS['foto']),
    ('deadline_lokaler', 'Lokaler', 'bi-door-open', None, 'secondary'),
    ('deadline_sos', 'SOS', 'bi-heart-pulse', 'APP_ENABLE_SOS', APP_COLORS['sos']),
)

MAX_FEED_ITEMS = 80


@dataclass
class FeedItem:
    starts_at: datetime
    title: str
    url: str
    icon: str = 'bi-calendar-event'
    color: str = 'secondary'
    responsible: str = ''
    kind_label: str = ''
    origin: str = ''
    is_preparation: bool = False
    ends_at: datetime | None = None
    status: str = ''
    status_color: str = ''
    all_day: bool = False
    all_day_label: str = 'Hele dagen'
    linkable: bool = True
    is_next: bool = False
    is_ongoing: bool = False
    is_overdue: bool = False
    # Program blocks open their content in a modal on the dashboard instead of
    # navigating away; ``url`` stays the fallback link to the programme page.
    modal_id: str = ''
    content: Any = None


@dataclass
class FeedDay:
    date: date
    is_today: bool
    is_tomorrow: bool
    items: list[FeedItem] = field(default_factory=list)


@dataclass
class NavItem:
    label: str
    icon: str
    url: str
    create_url: str | None = None
    active: bool = False


@dataclass
class NavSection:
    title: str
    items: list[NavItem]
    icon: str = 'bi-folder'
    default_open: bool = False
    # A section with a single entry is rendered as that entry, without the
    # collapsible group header.
    flat: bool = False

    @property
    def only_item(self) -> NavItem | None:
        return self.items[0] if len(self.items) == 1 else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _aware(day: date, value: time | None = None) -> datetime:
    return timezone.make_aware(
        datetime.combine(day, value or time(0, 0)),
        timezone.get_current_timezone(),
    )


def _status(value: str) -> tuple[str, str]:
    return STATUS_LABELS.get(value, value or ''), STATUS_COLORS.get(value, 'secondary')


def _qty(value) -> str:
    from decimal import Decimal

    if isinstance(value, Decimal):
        return format(value.normalize(), 'f')
    try:
        return f'{value:g}'
    except (TypeError, ValueError):
        return str(value)


def _team_ids(user) -> set[int]:
    return set(
        TeamMembership.objects.filter(member=user).values_list('team_id', flat=True)
    )


def _person(volunteer) -> str:
    if volunteer is None:
        return ''
    return volunteer.get_full_name().strip() or volunteer.username


def _tiptap_has_content(content: Any) -> bool:
    """Whether a stored TipTap value has anything worth showing.

    An empty document still renders as ``<p></p>``, so look at the canonical
    ``doc`` instead of the HTML mirror.
    """
    doc = getattr(content, 'doc', None)
    if not isinstance(doc, dict):
        return bool(str(getattr(content, 'html', '') or '').strip())

    def walk(node: Any) -> bool:
        if not isinstance(node, dict):
            return False
        kind = node.get('type')
        if kind == 'text':
            return bool((node.get('text') or '').strip())
        if kind in ('image', 'hardBreak', 'horizontalRule'):
            return True
        return any(walk(child) for child in node.get('content') or [])

    return walk(doc)


def _user_event_ids(user, team_ids: set[int]) -> set[int]:
    """Events the volunteer takes part in, directly or through a team."""
    event_ids = set(
        EventMembership.objects.filter(volunteer=user).values_list(
            'event_id', flat=True
        )
    )
    if team_ids:
        event_ids |= set(
            TeamEventMembership.objects.filter(team_id__in=team_ids).values_list(
                'event_id', flat=True
            )
        )
    return event_ids


def _feed_event(user, team_ids: set[int], today: date) -> Event | None:
    """Return the single active event the dashboard is scoped to.

    An event the volunteer takes part in wins when several are active. The
    lookup deliberately falls back to the active event the rest of the app
    works against, because deadlines and the shared programme are event-wide
    information that must not disappear just because memberships have not been
    configured (or because the event has ended but is still marked active).
    """
    active = Event.objects.filter(is_active=True)
    event_ids = _user_event_ids(user, team_ids)
    if event_ids:
        event = (
            active.filter(pk__in=event_ids, end_date__gte=today)
            .order_by('start_date', 'pk')
            .first()
        )
        if event is not None:
            return event
    upcoming = (
        active.filter(end_date__gte=today).order_by('start_date', 'pk').first()
    )
    if upcoming is not None:
        return upcoming
    # Nothing upcoming: keep the most recent active event so its deadlines stay
    # visible (marked as overdue) instead of the dashboard going empty.
    return active.order_by('-end_date', '-pk').first()


# ---------------------------------------------------------------------------
# Feed sources
# ---------------------------------------------------------------------------
def _booking_items(user, team_ids: set[int], today: date) -> list[FeedItem]:
    items: list[FeedItem] = []
    if not team_ids:
        return items

    from AktivitetsTeam.models import AktivitetsTeamBooking
    from Butikken.models import ButikkenOrder
    from Depot.models import DepotBooking
    from Foto.models import FotoBooking
    from Sjak.models import SjakBooking
    from SOS.models import SOSBooking
    from Teknik.models import TeknikBooking

    sources = []
    if _enabled('APP_ENABLE_SJAK'):
        sources.append(
            (SjakBooking, 'Sjak_SjakBooking_detail', 'Sjak', 'bi-tools',
             APP_COLORS['sjak'], lambda b: f'{_qty(b.quantity)} x {b.item.name}',
             ('assigned_sjak', 'team_contact'))
        )
    if _enabled('APP_ENABLE_TEKNIK'):
        sources.append(
            (TeknikBooking, 'Teknik_TeknikBooking_detail', 'Teknik', 'bi-cpu',
             APP_COLORS['teknik'], lambda b: f'{_qty(b.quantity)} x {b.item.name}',
             ('team_contact',))
        )
    if _enabled('APP_ENABLE_AKTIVITETSTEAM'):
        sources.append(
            (AktivitetsTeamBooking, 'AktivitetsTeam_AktivitetsTeamBooking_detail',
             'Aktiviteter', 'bi-universal-access', APP_COLORS['aktiviteter'],
             lambda b: b.item.name, ('team_contact',))
        )
    if _enabled('APP_ENABLE_FOTO'):
        sources.append(
            (FotoBooking, 'Foto_FotoBooking_detail', 'Foto', 'bi-camera',
             APP_COLORS['foto'], lambda b: b.item.name, ('team_contact',))
        )
    if _enabled('APP_ENABLE_SOS'):
        sources.append(
            (SOSBooking, 'SOS_SOSBooking_detail', 'SOS', 'bi-heart-pulse',
             APP_COLORS['sos'], lambda b: b.item.name, ('team_contact',))
        )
    if _enabled('APP_ENABLE_DEPOT'):
        sources.append(
            (DepotBooking, 'Depot_DepotBooking_detail', 'Depot', 'bi-box-seam',
             APP_COLORS['depot'], lambda b: f'{_qty(b.quantity)} x {b.item.name}',
             ('team_contact',))
        )

    for model, url_name, module, icon, color, title, related in sources:
        queryset = (
            model.objects.filter(team_id__in=team_ids, end_date__gte=today)
            .select_related('team', 'item', *related)
            .order_by('start_date', 'start_time')
        )
        for booking in queryset:
            status, status_color = _status(booking.status)
            items.append(
                FeedItem(
                    starts_at=_aware(booking.start_date, booking.start_time),
                    ends_at=_aware(booking.end_date, booking.end_time),
                    title=title(booking),
                    kind_label=module,
                    icon=icon,
                    color=color,
                    url=reverse(url_name, args=[booking.pk]),
                    responsible=_person(
                        getattr(booking, 'assigned_sjak', None)
                        or booking.team_contact
                    ),
                    status=status,
                    status_color=status_color,
                )
            )

    if not _enabled('APP_ENABLE_BUTIKKEN'):
        return items

    for order in (
        ButikkenOrder.objects.filter(team_id__in=team_ids, pickup_date__gte=today)
        .select_related('team', 'team_contact')
        .order_by('pickup_date', 'pk')
    ):
        status, status_color = _status(order.status)
        title = f'Bestilling #{order.pk}'
        if order.name:
            title = f'{title} · {order.name}'
        items.append(
            FeedItem(
                starts_at=_aware(order.pickup_date),
                title=title,
                kind_label='Butikken',
                icon='bi-shop',
                color=APP_COLORS['butikken'],
                url=reverse('Butikken_ButikkenOrder_detail', args=[order.pk]),
                responsible=_person(order.team_contact),
                status=status,
                status_color=status_color,
                all_day=True,
                all_day_label='Afhentning',
            )
        )

    return items


def _appointment_items(user, today: date) -> list[FeedItem]:
    if not _enabled('APP_ENABLE_LEGEAFTALER'):
        return []
    items: list[FeedItem] = []
    queryset = (
        VolunteerAppointment.objects.visible_to(user)
        .filter(Q(start_date__gte=today) | Q(end_date__gte=today))
        .exclude(status__in=('rejected', 'cancelled'))
        .select_related('requester', 'receiver', 'receiver_team')
        .order_by('start_date', 'start_time')
    )
    for appointment in queryset:
        if appointment.start_date is None:
            continue
        all_day = appointment.start_time is None
        starts_at = _aware(appointment.start_date, appointment.start_time)
        ends_at = (
            _aware(appointment.end_date, appointment.end_time)
            if appointment.end_date
            else None
        )
        status, status_color = _status(appointment.status)
        title = (appointment.description or 'Legeaftale').strip()
        requester = _person(appointment.requester)
        if appointment.receiver_id:
            receiver = _person(appointment.receiver)
        elif appointment.receiver_team_id:
            receiver = appointment.receiver_team.name
        else:
            receiver = ''
        items.append(
            FeedItem(
                starts_at=starts_at,
                ends_at=ends_at,
                title=title,
                kind_label='Legeaftale',
                icon='bi-balloon-heart',
                color=APP_COLORS['legeaftale'],
                url=appointment.get_absolute_url(),
                responsible=f'{requester} til {receiver}' if receiver else requester,
                status=status,
                status_color=status_color,
                all_day=all_day,
                all_day_label='Hele dagen',
            )
        )
    return items


def _program_items(
    team_ids: set[int], event: Event | None, today: date
) -> list[FeedItem]:
    if event is None:
        return []
    queryset = (
        ProgramBlock.objects.filter(event=event, day__gte=today)
        .filter(Q(team__isnull=True) | Q(team_id__in=team_ids))
        .select_related('event', 'team')
        .prefetch_related('responsible')
        .order_by('day', 'start_time', 'pk')
    )
    items = []
    for block in queryset:
        responsible = ', '.join(
            name for name in (_person(v) for v in block.responsible.all()) if name
        )
        content = block.content
        # ``TipTapJSONField`` returns a safe ``TipTapValue``; only offer the
        # modal when the block actually has something to read.
        has_content = _tiptap_has_content(content)
        items.append(
            FeedItem(
                starts_at=_aware(block.day, block.start_time),
                ends_at=_aware(block.day, block.end_time),
                title=block.title,
                kind_label='Rammeprogram',
                icon='bi-calendar3',
                color=PROGRAM_COLORS.get(block.category, 'secondary'),
                url=block.get_absolute_url(),
                responsible=responsible,
                origin=block.team.name if block.team_id else 'Fælles',
                is_preparation=(
                    block.category == ProgramBlock.CATEGORY_PREPARATION
                ),
                modal_id=f'program-block-{block.pk}',
                content=content if has_content else None,
            )
        )
    return items


def _deadline_items(event: Event | None, today: date) -> list[FeedItem]:
    if event is None:
        return []
    items = []
    for field_name, label, icon, toggle, color in EVENT_DEADLINES:
        if toggle and not _enabled(toggle):
            continue
        deadline = getattr(event, field_name)
        if deadline is None:
            continue
        overdue = deadline < today
        items.append(
            FeedItem(
                starts_at=_aware(deadline),
                title=f'{label}-frist',
                kind_label='Frist',
                icon=icon,
                color=color,
                url=event.get_absolute_url(),
                all_day=True,
                all_day_label='Frist',
                linkable=False,
                status='Overskredet' if overdue else '',
                status_color='secondary' if overdue else '',
                is_overdue=overdue,
            )
        )
    return items


def _tjanse_items(team_ids: set[int], today: date) -> list[FeedItem]:
    if not team_ids:
        return []
    items = []
    queryset = (
        TjanseOwnership.objects.filter(
            team_id__in=team_ids, due_date__gte=today
        )
        .exclude(status__in=('done', 'not_done'))
        .select_related('tjanse', 'team', 'event')
        .order_by('due_date', 'pk')
    )
    for ownership in queryset:
        status, status_color = _status(ownership.status)
        items.append(
            FeedItem(
                starts_at=_aware(ownership.due_date),
                title=ownership.tjanse.title,
                kind_label='Opgave',
                icon='bi-check2-square',
                color=APP_COLORS['opgave'],
                url=ownership.get_absolute_url(),
                responsible=ownership.team.name,
                status=status,
                status_color=status_color,
                all_day=True,
                all_day_label='Opgave',
            )
        )
    return items


def build_feed(user) -> list[FeedItem]:
    """Return upcoming/ongoing feed items, soonest first."""
    now = timezone.localtime()
    today = now.date()
    team_ids = _team_ids(user)
    event = _feed_event(user, team_ids, today)

    items = [
        *_booking_items(user, team_ids, today),
        *_appointment_items(user, today),
        *_program_items(team_ids, event, today),
        *_deadline_items(event, today),
        *_tjanse_items(team_ids, today),
    ]

    # Drop items that already ended; all-day items count for the whole day.
    items = [
        item
        for item in items
        if item.all_day or (item.ends_at or item.starts_at) >= now
    ]
    items.sort(key=lambda item: (item.starts_at, not item.all_day, item.title.lower()))
    items = items[:MAX_FEED_ITEMS]

    next_set = False
    for item in items:
        item.is_ongoing = bool(
            not item.all_day
            and item.starts_at <= now
            and (item.ends_at or item.starts_at) >= now
        )
        # Overdue deadlines are informational leftovers from the event that
        # just ended; they should never be labelled as the next thing to do.
        if not next_set and not item.is_overdue:
            item.is_next = True
            next_set = True

    return items


def group_feed(items: list[FeedItem]) -> list[FeedDay]:
    today = timezone.localdate()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    grouped: OrderedDict[date, FeedDay] = OrderedDict()
    for item in items:
        day = item.starts_at.date()
        if day not in grouped:
            grouped[day] = FeedDay(
                date=day,
                is_today=day == today,
                is_tomorrow=day == tomorrow,
            )
        grouped[day].items.append(item)
    return list(grouped.values())


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def _reverse(name: str) -> str | None:
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def _nav_item(
    user,
    path: str,
    label: str,
    icon: str,
    list_name: str,
    create_name: str | None = None,
) -> NavItem | None:
    url = _reverse(list_name)
    if not url:
        return None
    create_url = _reverse(create_name) if create_name else None
    active = path == url if url == '/' else path.startswith(url)
    return NavItem(label=label, icon=icon, url=url, create_url=create_url, active=active)


def _enabled(name: str) -> bool:
    return bool(getattr(config, name, True))


def build_sidebar(user, path: str) -> list[NavSection]:
    sections: list[NavSection] = []

    def add(title: str, items, icon: str | None = None) -> None:
        entries = [item for item in items if item]
        if entries:
            sections.append(
                NavSection(
                    title,
                    entries,
                    icon=icon or SECTION_ICONS.get(title, 'bi-folder'),
                    flat=len(entries) == 1,
                )
            )

    add(
        'Overblik',
        [
            _nav_item(user, path, 'Feed', 'bi-house-door', 'index'),
            _nav_item(
                user, path, 'Program', 'bi-calendar3-week',
                'organization_Program_event_list',
            ),
            _nav_item(
                user, path, 'Telefonbog', 'bi-telephone',
                'organization_Volunteer_list',
            )
            if _enabled('APP_ENABLE_CONTACTS')
            else None,
            _nav_item(
                user, path, 'Wiki', 'bi-book', 'Wiki_WikiPage_list'
            )
            if _enabled('APP_ENABLE_WIKI')
            else None,
            _nav_item(
                user, path, 'Tjanser', 'bi-check2-square',
                'organization_TjanseOwnership_list',
            ),
            _nav_item(
                user, path, 'Slutrengøring', 'bi-stars',
                'organization_Slutrengoring_home',
            ),
        ],
    )

    if _enabled('APP_ENABLE_SJAK'):
        add(
            'Sjak',
            [
                _nav_item(
                    user, path, 'Bookinger', 'bi-calendar-check',
                    'Sjak_SjakBooking_list', 'Sjak_SjakBooking_create',
                ),
                _nav_item(user, path, 'Sager', 'bi-box-seam', 'Sjak_SjakItem_list'),
            ],
        )

    if _enabled('APP_ENABLE_TEKNIK'):
        add(
            'Teknik',
            [
                _nav_item(
                    user, path, 'Bookinger', 'bi-calendar-check',
                    'Teknik_TeknikBooking_list', 'Teknik_TeknikBooking_create',
                ),
                _nav_item(user, path, 'Ting', 'bi-cpu', 'Teknik_TeknikItem_list'),
            ],
        )

    if _enabled('APP_ENABLE_AKTIVITETSTEAM'):
        add(
            'Aktiviteter',
            [
                _nav_item(
                    user, path, 'Bookinger', 'bi-calendar-check',
                    'AktivitetsTeam_AktivitetsTeamBooking_mine',
                    'AktivitetsTeam_AktivitetsTeamBooking_create',
                ),
                _nav_item(
                    user, path, 'Katalog', 'bi-universal-access',
                    'AktivitetsTeam_AktivitetsTeamItem_list',
                ),
            ],
        )

    if _enabled('APP_ENABLE_FOTO'):
        add(
            'Foto',
            [
                _nav_item(
                    user, path, 'Bookinger', 'bi-calendar-check',
                    'Foto_FotoBooking_list', 'Foto_FotoBooking_create',
                ),
                _nav_item(user, path, 'Katalog', 'bi-camera', 'Foto_FotoItem_list'),
            ],
        )

    if _enabled('APP_ENABLE_SOS'):
        add(
            'SOS',
            [
                _nav_item(
                    user, path, 'Bookinger', 'bi-calendar-check',
                    'SOS_SOSBooking_list', 'SOS_SOSBooking_create',
                ),
                _nav_item(
                    user, path, 'Katalog', 'bi-heart-pulse', 'SOS_SOSItem_list',
                ),
            ],
        )

    if _enabled('APP_ENABLE_DEPOT'):
        add(
            'Depot',
            [
                _nav_item(
                    user, path, 'Bookinger', 'bi-calendar-check',
                    'Depot_DepotBooking_list', 'Depot_DepotBooking_create',
                ),
                _nav_item(
                    user, path, 'Katalog', 'bi-box-seam', 'Depot_DepotItem_list',
                ),
            ],
        )

    if _enabled('APP_ENABLE_BUTIKKEN'):
        add(
            'Butikken',
            [
                _nav_item(
                    user, path, 'Admin overblik', 'bi-speedometer2',
                    'Butikken_dashboard',
                ),
                _nav_item(
                    user, path, 'Varebestillinger', 'bi-bag-check',
                    'Butikken_ButikkenOrder_list',
                    'Butikken_ButikkenOrder_create',
                ),
                _nav_item(
                    user, path, 'Måltidsbestillinger', 'bi-egg-fried',
                    'Butikken_TeamMealPlan_list',
                    'Butikken_TeamMealPlan_create',
                ),
                _nav_item(
                    user, path, 'Varekatalog', 'bi-shop',
                    'Butikken_ButikkenItem_list',
                ),
            ],
        )

    if _enabled('APP_ENABLE_LEGEAFTALER'):
        add(
            'Legeaftaler',
            [
                _nav_item(
                    user, path, 'Legeaftaler', 'bi-balloon-heart',
                    'organization_VolunteerAppointment_list',
                    'organization_VolunteerAppointment_create',
                ),
            ],
        )

    if _enabled('APP_ENABLE_CONTACTS'):
        add(
            'Organisation',
            [
                _nav_item(
                    user, path, 'Nøgler', 'bi-key', 'organization_Key_list'
                ),
            ],
        )

    if _enabled('APP_ENABLE_LOEB') and user.is_staff:
        add(
            'Løb',
            [
                _nav_item(user, path, 'Løb', 'bi-flag', 'Loeb_Loeb_list'),
            ],
        )

    if sections:
        sections[0].default_open = True
        # Keep the section that contains the current page expanded so the
        # highlighted item is visible without an extra click.
        for section in sections:
            if any(item.active for item in section.items):
                section.default_open = True
    return sections
