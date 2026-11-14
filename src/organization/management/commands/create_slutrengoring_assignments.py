"""Create the per-event Slutrengøring assignment rows from the task catalogue.

Usage:
    python manage.py create_slutrengoring_assignments --event 4
    python manage.py create_slutrengoring_assignments --event 4 --team 12
"""
from django.core.management.base import BaseCommand, CommandError

from organization.models import Event, Team
from organization.slutrengoring_services import create_assignments_for_event


class Command(BaseCommand):
    help = "Create Slutrengøring assignment rows for every Slutrengøring task."

    def add_arguments(self, parser):
        parser.add_argument("--event", type=int, required=True, help="Event ID")
        parser.add_argument(
            "--team",
            type=int,
            default=None,
            help="Optional team ID to pre-assign all created tasks to.",
        )

    def handle(self, *args, **options):
        try:
            event = Event.objects.get(pk=options["event"])
        except Event.DoesNotExist as exc:
            raise CommandError("Event not found.") from exc

        team = None
        if options["team"]:
            try:
                team = Team.objects.get(pk=options["team"])
            except Team.DoesNotExist as exc:
                raise CommandError("Team not found.") from exc

        created_count = create_assignments_for_event(event, team=team)

        self.stdout.write(
            self.style.SUCCESS(
                f"Oprettede {created_count} slutrengøringstildelinger til {event.name}."
            )
        )
