"""Service helpers for the Slutrengøring pool and admin dispatch buttons."""
from django.db.models import Case, IntegerField, Value, When
from django.utils.timezone import now

from .discord_services import build_embed
from .models import SlutrengoringAssignment, Team, Tjanse
from .tasks import enqueue_discord_embed

PRIORITY_ORDER = Case(
    When(tjanse__priority='required', then=Value(0)),
    When(tjanse__priority='high', then=Value(1)),
    When(tjanse__priority='medium', then=Value(2)),
    When(tjanse__priority='low', then=Value(3)),
    default=Value(99),
    output_field=IntegerField(),
)


def create_assignments_for_event(event, team=None, assigned_by=None):
    """Create one assignment row per Slutrengøring task for ``event``.

    Returns the number of rows actually created. Existing rows are left
    untouched, so the operation is idempotent.
    """
    created_count = 0
    for tjanse in Tjanse.objects.filter(kind='slutrengoring'):
        defaults = {'status': 'assigned' if team else 'available'}
        if team is not None:
            defaults['team'] = team
        if assigned_by is not None:
            defaults['assigned_by'] = assigned_by
        _, created = SlutrengoringAssignment.objects.get_or_create(
            tjanse=tjanse,
            event=event,
            defaults=defaults,
        )
        if created:
            created_count += 1
    return created_count


def notify_assignment_discord(assignment, changed_by=None):
    """Send a Discord embed to the team that received ``assignment``."""
    team = assignment.team
    if team is None or not team.discord_webhook_url:
        return False

    embed = build_embed(
        title=f"Slutrengøringopgave tildelt: {assignment.tjanse.title}",
        status=assignment.get_status_display(),
        color=0x5865F2,
        changed_by=changed_by.get_full_name() if changed_by else None,
        fields=[
            ("Team", team.name),
            ("Event", str(assignment.event)),
            ("Prioritet", assignment.tjanse.get_priority_display()),
            ("Område", assignment.tjanse.area or "-"),
        ],
    )
    enqueue_discord_embed(team.pk, embed, "Slutrengøring")
    return True


def assign_highest_priority_to_teams(event, actor=None):
    """Assign one claimable task to each team that has no active task.

    Tasks are consumed highest-priority first. The conditional ``update``
    makes the operation safe if a team claims a task from the web page at the
    same time. Returns ``(assigned, skipped_teams)``.
    """
    pool = list(
        SlutrengoringAssignment.objects
        .filter(
            event=event,
            team__isnull=True,
            status__in=SlutrengoringAssignment.CLAIMABLE_STATUSES,
        )
        .select_related('tjanse', 'event')
        .annotate(priority_rank=PRIORITY_ORDER)
        .order_by('priority_rank', 'tjanse__order', 'tjanse__title')
    )
    pool_index = 0
    assigned = []
    skipped = []

    for team in Team.objects.order_by('name'):
        if SlutrengoringAssignment.objects.filter(
            event=event,
            team=team,
            status__in=SlutrengoringAssignment.ACTIVE_STATUSES,
        ).exists():
            skipped.append(team)
            continue

        assigned_this_team = False
        while pool_index < len(pool):
            candidate = pool[pool_index]
            pool_index += 1
            updated = (
                SlutrengoringAssignment.objects
                .filter(
                    pk=candidate.pk,
                    team__isnull=True,
                    status__in=SlutrengoringAssignment.CLAIMABLE_STATUSES,
                )
                .update(
                    team=team,
                    status='assigned',
                    assigned_at=now(),
                    assigned_by=actor,
                    last_updated=now(),
                )
            )
            if not updated:
                # A web claim won the row; try the next-highest task.
                continue

            candidate.refresh_from_db()
            # update() bypasses simple-history; re-save for the audit trail.
            candidate.save()
            notify_assignment_discord(candidate, changed_by=actor)
            assigned.append(candidate)
            assigned_this_team = True
            break

        if not assigned_this_team:
            skipped.append(team)

    return assigned, skipped
