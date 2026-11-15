"""Create demo data for every app that ships a ``demo.py`` factory.

The command is meant for local development and staging only - it never runs
automatically. It creates a demo event, demo teams and users, and then lets each
app's factory fill in items and bookings.

Usage:
    python manage.py generate_dummy_data
    python manage.py generate_dummy_data --per-model 3
    python manage.py generate_dummy_data --reset
"""

from importlib import import_module
from pathlib import Path

from django.apps import apps as django_apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from organization.demo import OrganizationDemoFactory


class Command(BaseCommand):
    help = (
        'Opretter demo-event, brugere, varer og bookinger til alle apps med en '
        'demo.py-factory. Kun til udvikling og staging.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--per-model',
            type=int,
            default=5,
            help='Antal varer og bookinger pr. model (standard: 5).',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Slet tidligere demo-data (markeret med [demo]) før der oprettes nyt.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Tillad kørsel i produktion (frarådes).',
        )

    def handle(self, *args, **options):
        if getattr(settings, 'ENVIRONMENT', 'dev') == 'production' and not options['force']:
            raise CommandError(
                'generate_dummy_data opretter testbrugere og demo-data og må ikke køre '
                'i produktion. Brug --force hvis du er helt sikker.'
            )

        per_model = options['per_model']
        verbosity = options['verbosity']
        factories = self._factories()

        with transaction.atomic():
            if options['reset']:
                for factory in factories:
                    factory.reset()
                if verbosity:
                    self.stdout.write('  Eksisterende demo-data slettet.')

            context = factories[0].bootstrap(per_model, verbosity, stdout=self.stdout)
            for factory in factories:
                factory.run(context)

        if verbosity:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Demo-data klar ({per_model} pr. model). '
                    'Kør igen for at fylde op, eller brug --reset for at starte forfra.'
                )
            )

    def _factories(self):
        """Return the organization factory followed by every discovered one."""
        factories = [OrganizationDemoFactory()]
        base_dir = Path(settings.BASE_DIR).resolve()

        for config in django_apps.get_app_configs():
            if config.name == 'organization':
                continue
            if not Path(config.path).resolve().is_relative_to(base_dir):
                continue
            try:
                module = import_module(f'{config.name}.demo')
            except ModuleNotFoundError as exc:
                if exc.name != f'{config.name}.demo':
                    raise
                continue
            factory_class = getattr(module, 'FACTORY', None)
            if factory_class is not None:
                factories.append(factory_class())

        return factories
