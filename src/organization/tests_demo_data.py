"""Tests for the ``generate_dummy_data`` command and its per-app factories."""

import shutil
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from AktivitetsTeam.models import AktivitetsTeamBooking, AktivitetsTeamItem
from Butikken.models import ButikkenBooking, ButikkenItem, ButikkenOrder
from Depot.models import DepotBooking, DepotItem
from Foto.models import FotoBooking, FotoItem
from Loeb.models import Hold, Loeb, Task
from organization.models import (
    Event,
    SlutrengoringAssignment,
    Team,
    Tjanse,
    TjanseOwnership,
    Volunteer,
    VolunteerAppointment,
)
from Sjak.models import SjakBooking, SjakItem
from SOS.models import SOSBooking, SOSItem
from Teknik.models import TeknikBooking, TeknikItem

DEMO = '[demo]'

ITEM_MODELS = (
    ButikkenItem,
    AktivitetsTeamItem,
    SOSItem,
    FotoItem,
    SjakItem,
    TeknikItem,
    DepotItem,
)

BOOKING_MODELS = (
    ButikkenBooking,
    AktivitetsTeamBooking,
    SOSBooking,
    FotoBooking,
    SjakBooking,
    TeknikBooking,
    DepotBooking,
)


class GenerateDummyDataTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_creates_an_event_users_items_and_bookings_for_every_app(self):
        call_command('generate_dummy_data', per_model=2, verbosity=0)

        self.assertEqual(Event.objects.filter(is_active=True).count(), 1)
        self.assertEqual(Team.objects.filter(name__startswith=DEMO).count(), 2)
        self.assertEqual(
            Volunteer.objects.filter(username__startswith='demo').count(), 2
        )

        for model in ITEM_MODELS:
            self.assertEqual(
                model.objects.filter(name__startswith=DEMO).count(),
                2,
                model.__name__,
            )
        for model in BOOKING_MODELS:
            self.assertEqual(
                model.objects.filter(remarks__startswith=DEMO).count(),
                2,
                model.__name__,
            )

        self.assertEqual(ButikkenOrder.objects.filter(name__startswith=DEMO).count(), 2)
        self.assertEqual(Loeb.objects.filter(name__startswith=DEMO).count(), 2)
        self.assertEqual(Task.objects.filter(loeb__name__startswith=DEMO).count(), 4)
        self.assertEqual(Hold.objects.filter(loeb__name__startswith=DEMO).count(), 4)

        # Tjanser: one regular and one Slutrengøring per "model".
        self.assertEqual(
            Tjanse.objects.filter(kind='regular', title__startswith=DEMO).count(), 2
        )
        self.assertEqual(
            Tjanse.objects.filter(kind='slutrengoring', title__startswith=DEMO).count(),
            2,
        )
        self.assertTrue(TjanseOwnership.objects.filter(tjanse__title__startswith=DEMO).exists())
        self.assertTrue(
            SlutrengoringAssignment.objects.filter(
                tjanse__title__startswith=DEMO
            ).exists()
        )
        self.assertEqual(
            VolunteerAppointment.objects.filter(
                description__startswith=DEMO
            ).count(),
            2,
        )

    def test_running_twice_does_not_duplicate_rows(self):
        call_command('generate_dummy_data', per_model=2, verbosity=0)
        first_run = [model.objects.count() for model in ITEM_MODELS + BOOKING_MODELS]
        first_tjanser = Tjanse.objects.count()
        first_assignments = SlutrengoringAssignment.objects.count()

        call_command('generate_dummy_data', per_model=2, verbosity=0)

        self.assertEqual(
            [model.objects.count() for model in ITEM_MODELS + BOOKING_MODELS],
            first_run,
        )
        self.assertEqual(Tjanse.objects.count(), first_tjanser)
        self.assertEqual(SlutrengoringAssignment.objects.count(), first_assignments)

    def test_refuses_to_run_in_production(self):
        from django.core.management.base import CommandError

        with override_settings(ENVIRONMENT='production'), self.assertRaises(CommandError):
            call_command('generate_dummy_data', verbosity=0)

    def test_reset_recreates_demo_rows_and_keeps_other_data(self):
        real_team = Team.objects.create(name='Rigtigt hold')
        real_tjanse = Tjanse.objects.create(title='Rigtig tjense', kind='regular')

        call_command('generate_dummy_data', per_model=2, verbosity=0)
        old_item_ids = set(
            ButikkenItem.objects.filter(name__startswith=DEMO).values_list('pk', flat=True)
        )

        call_command('generate_dummy_data', '--reset', per_model=2, verbosity=0)

        new_item_ids = set(
            ButikkenItem.objects.filter(name__startswith=DEMO).values_list('pk', flat=True)
        )
        self.assertEqual(len(new_item_ids), 2)
        self.assertFalse(old_item_ids & new_item_ids, 'Demo items should be recreated')

        # Non-demo rows must survive a reset.
        self.assertTrue(Team.objects.filter(pk=real_team.pk).exists())
        self.assertTrue(Tjanse.objects.filter(pk=real_tjanse.pk).exists())
