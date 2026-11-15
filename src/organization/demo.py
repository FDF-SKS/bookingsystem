"""Demo data for the organization app: event, teams, users, tjanser."""

from datetime import time, timedelta

from django.conf import settings
from django.utils import timezone

from organization.models import (
    Event,
    EventMembership,
    SlutrengoringAssignment,
    Team,
    TeamMembership,
    Tjanse,
    TjanseOwnership,
    TjanseSwapRequest,
    Volunteer,
    VolunteerAppointment,
)
from organization.slutrengoring_services import create_assignments_for_event
from utils.demo import DEMO_TAG, DemoContext, DemoFactory

DEMO_PASSWORD = 'demo12345'
PRIORITIES = ('required', 'high', 'medium', 'low')
OWNERSHIP_STATUSES = ('assigned', 'in_progress', 'done')


def _tiptap(text: str) -> dict:
    return {
        'type': 'doc',
        'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': text}]}],
    }


class OrganizationDemoFactory(DemoFactory):
    label = 'Organization'

    # -- bootstrap ---------------------------------------------------------
    def bootstrap(self, per_model: int, verbosity: int, stdout=None) -> DemoContext:
        """Create the event, teams and users every other factory builds on."""
        today = timezone.localdate()
        event, _ = Event.objects.update_or_create(
            name=f'{DEMO_TAG} Event',
            defaults={
                'start_date': today,
                'end_date': today + timedelta(days=3),
                'is_active': True,
                'deadline_sjak': today + timedelta(days=2),
                'deadline_teknik': today + timedelta(days=2),
                'deadline_mad': today + timedelta(days=2),
                'deadline_aktivitetsteam': today + timedelta(days=2),
                'deadline_foto': today + timedelta(days=2),
                'deadline_lokaler': today + timedelta(days=2),
                'deadline_sos': today + timedelta(days=2),
            },
        )
        # The demo event is only useful if the pages work against it.
        Event.objects.exclude(pk=event.pk).filter(is_active=True).update(is_active=False)

        demo_teams = []
        volunteers = []
        for index in range(1, per_model + 1):
            team, _ = Team.objects.get_or_create(
                name=f'{DEMO_TAG} Hold {index}',
                defaults={'short_name': f'D{index}'},
            )
            volunteer, created = Volunteer.objects.get_or_create(
                username=f'demo{index}',
                defaults={
                    'email': f'demo{index}@example.com',
                    'first_name': 'Demo',
                    'last_name': f'Bruger {index}',
                },
            )
            if created:
                volunteer.set_unusable_password()
                volunteer.save(update_fields=['password'])
            if settings.DEBUG and not volunteer.has_usable_password():
                # Keep the documented demo login working on re-runs too.
                volunteer.set_password(DEMO_PASSWORD)
                volunteer.save(update_fields=['password'])
            TeamMembership.objects.get_or_create(team=team, member=volunteer)
            EventMembership.objects.get_or_create(event=event, volunteer=volunteer)
            demo_teams.append(team)
            volunteers.append(volunteer)

        self._attach_staff(demo_teams[0], verbosity, stdout)

        # Test the team-scoped pages with the developer's own team as well.
        pool = list(
            Team.objects.filter(teammembership__member__is_staff=True)
            .distinct()
            .order_by('pk')
        )
        for team in demo_teams:
            if team not in pool:
                pool.append(team)

        if verbosity and stdout is not None:
            stdout.write(f'  Event: {event.name} ({event.start_date} - {event.end_date})')
            if settings.DEBUG:
                stdout.write(f'  Demo-brugere: demo1..demo{per_model} / {DEMO_PASSWORD}')

        return DemoContext(
            event=event,
            teams=pool,
            volunteers=volunteers,
            per_model=per_model,
            today=today,
            verbosity=verbosity,
            stdout=stdout,
        )

    def _attach_staff(self, team, verbosity: int, stdout) -> None:
        attached = 0
        for volunteer in Volunteer.objects.filter(is_staff=True, teammembership__isnull=True):
            TeamMembership.objects.get_or_create(team=team, member=volunteer)
            attached += 1
        if attached and verbosity and stdout is not None:
            stdout.write(
                f'  Tilknyttede {attached} administrator(er) til {team.name} '
                '(så teamafgrænsede lister viser demo-data)'
            )

    # -- items and bookings -------------------------------------------------
    def create_items(self, ctx: DemoContext) -> None:
        for index in ctx.indexes:
            Tjanse.objects.get_or_create(
                title=f'{DEMO_TAG} Tjense {index + 1}',
                defaults={
                    'kind': 'regular',
                    'priority': PRIORITIES[index % len(PRIORITIES)],
                    'description': _tiptap(
                        'Demo-tjense. Beskriv opgaven, så teamet ved hvad der skal gøres.'
                    ),
                },
            )
            Tjanse.objects.get_or_create(
                title=f'{DEMO_TAG} Slutrengøring {index + 1}',
                defaults={
                    'kind': 'slutrengoring',
                    'priority': PRIORITIES[index % len(PRIORITIES)],
                    'area': f'Område {index + 1}',
                    'estimated_minutes': 15 * (index + 1),
                    'order': index,
                    'description': _tiptap('Demo-opgave til slutrengøring.'),
                },
            )

    def create_bookings(self, ctx: DemoContext) -> None:
        regular = list(
            Tjanse.objects.filter(kind='regular', title__startswith=DEMO_TAG).order_by('pk')
        )
        for index in ctx.indexes:
            ownership, created = TjanseOwnership.objects.get_or_create(
                tjanse=regular[index % len(regular)],
                event=ctx.event,
                team=ctx.team(index),
                defaults={
                    'due_date': ctx.today + timedelta(days=index % 3),
                    'status': OWNERSHIP_STATUSES[index % len(OWNERSHIP_STATUSES)],
                },
            )
            if created and ownership.status == 'done':
                ownership.completed_at = timezone.now()
                ownership.save(update_fields=['completed_at'])

        self._create_pending_swap()
        self._assign_slutrengoring(ctx)
        self._create_appointments(ctx)

    def _create_pending_swap(self) -> None:
        if TjanseSwapRequest.objects.filter(
            status='pending', task_ownership__tjanse__title__startswith=DEMO_TAG
        ).exists():
            return
        ownership = (
            TjanseOwnership.objects.filter(tjanse__title__startswith=DEMO_TAG)
            .select_related('team')
            .first()
        )
        if ownership is None:
            return
        receiving = Team.objects.exclude(pk=ownership.team_id).order_by('pk').first()
        if receiving is None:
            return
        TjanseSwapRequest.objects.create(
            task_ownership=ownership,
            requesting_team=ownership.team,
            receiving_team=receiving,
            status='pending',
        )

    def _assign_slutrengoring(self, ctx: DemoContext) -> None:
        create_assignments_for_event(ctx.event)
        assignments = list(
            SlutrengoringAssignment.objects.filter(
                event=ctx.event, tjanse__title__startswith=DEMO_TAG
            ).order_by('tjanse__order')
        )
        now = timezone.now()
        # Leave the rest in the pool so claiming can be tested on the web page.
        for index, assignment in enumerate(assignments):
            if assignment.team_id is not None:
                continue
            if index == 0:
                SlutrengoringAssignment.objects.filter(pk=assignment.pk).update(
                    team=ctx.team(0), status='assigned', assigned_at=now
                )
            elif index == 1 and len(assignments) > 2:
                SlutrengoringAssignment.objects.filter(pk=assignment.pk).update(
                    team=ctx.team(1), status='in_progress', assigned_at=now, started_at=now
                )
            elif index == 2 and len(assignments) > 3:
                SlutrengoringAssignment.objects.filter(pk=assignment.pk).update(
                    team=ctx.team(2),
                    status='done',
                    assigned_at=now,
                    started_at=now,
                    completed_at=now,
                )

    def _create_appointments(self, ctx: DemoContext) -> None:
        if self.has_demo_rows(VolunteerAppointment, field='description', minimum=ctx.per_model):
            return
        for index in ctx.indexes:
            requester = ctx.volunteers[index % len(ctx.volunteers)]
            receiver = ctx.volunteers[(index + 1) % len(ctx.volunteers)]
            kind = index % 3
            defaults = {
                'requester': requester,
                'description': f'{DEMO_TAG} Legeaftale {index + 1}',
                'start_date': ctx.today + timedelta(days=index % 3),
                'end_date': ctx.today + timedelta(days=index % 3),
                'start_time': time(12 + index % 4, 0),
                'end_time': time(13 + index % 4, 0),
            }
            if kind == 0:
                defaults['receiver'] = receiver
            elif kind == 1:
                defaults['receiver'] = receiver
                defaults['shared_with_team'] = True
            else:
                defaults['receiver_team'] = receiver.teams.first() or ctx.teams[
                    (index + 1) % len(ctx.teams)
                ]
            VolunteerAppointment.objects.create(**defaults)

    # -- housekeeping -------------------------------------------------------
    def reset(self) -> None:
        VolunteerAppointment.objects.filter(description__startswith=DEMO_TAG).delete()
        SlutrengoringAssignment.objects.filter(
            tjanse__title__startswith=DEMO_TAG
        ).delete()
        TjanseOwnership.objects.filter(tjanse__title__startswith=DEMO_TAG).delete()
        Tjanse.objects.filter(title__startswith=DEMO_TAG).delete()

    def report(self, ctx: DemoContext) -> str:
        tjanser = Tjanse.objects.filter(kind='regular', title__startswith=DEMO_TAG).count()
        slut = Tjanse.objects.filter(
            kind='slutrengoring', title__startswith=DEMO_TAG
        ).count()
        ownerships = TjanseOwnership.objects.filter(
            tjanse__title__startswith=DEMO_TAG
        ).count()
        appointments = VolunteerAppointment.objects.filter(
            description__startswith=DEMO_TAG
        ).count()
        return (
            f'{tjanser} tjanser, {slut} slutrengøring, '
            f'{ownerships} tildelinger, {appointments} legeaftaler'
        )


FACTORY = OrganizationDemoFactory
