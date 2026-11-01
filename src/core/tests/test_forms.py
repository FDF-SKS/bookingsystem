"""Validation tests for representative forms across the booking apps."""
from datetime import date

from django.test import TestCase

from Butikken.forms import ButikkenItemTypeForm
from Depot.forms import DepotBookingForm, DepotItemForm
from Depot.models import DepotItem
from organization.forms import TeamForm, VolunteerForm
from organization.models import Team, Volunteer
from Sjak.forms import SjakItemTypeForm
from SOS.forms import SOSTypeForm
from Teknik.forms import TeknikTypeForm


class SimpleModelFormTests(TestCase):
    """The per-app "type" ModelForms only require a ``name``."""

    def test_sjak_item_type_form(self):
        self.assertTrue(SjakItemTypeForm({"name": "Værktøj"}).is_valid())
        invalid = SjakItemTypeForm({})
        self.assertFalse(invalid.is_valid())
        self.assertIn("name", invalid.errors)

    def test_teknik_type_form(self):
        self.assertTrue(TeknikTypeForm({"name": "Lyd"}).is_valid())
        invalid = TeknikTypeForm({})
        self.assertFalse(invalid.is_valid())
        self.assertIn("name", invalid.errors)

    def test_sos_type_form(self):
        self.assertTrue(SOSTypeForm({"name": "Sikkerhed"}).is_valid())
        invalid = SOSTypeForm({})
        self.assertFalse(invalid.is_valid())
        self.assertIn("name", invalid.errors)

    def test_butikken_item_type_form(self):
        self.assertTrue(ButikkenItemTypeForm({"name": "Mad", "description": ""}).is_valid())
        invalid = ButikkenItemTypeForm({})
        self.assertFalse(invalid.is_valid())
        self.assertIn("name", invalid.errors)


class OrganizationFormTests(TestCase):
    def test_team_form_requires_short_name(self):
        self.assertTrue(TeamForm({"name": "Team A", "short_name": "TA"}).is_valid())

        invalid = TeamForm({"name": "Team A"})
        self.assertFalse(invalid.is_valid())
        self.assertIn("short_name", invalid.errors)

    def test_volunteer_form_requires_unique_email(self):
        Volunteer.objects.create_user(
            username="existing",
            email="taken@example.com",
            first_name="E",
            last_name="X",
        )

        invalid = VolunteerForm(
            {"first_name": "A", "last_name": "B", "email": "taken@example.com", "phone": ""}
        )
        self.assertFalse(invalid.is_valid())
        self.assertIn("email", invalid.errors)


class DepotFormTests(TestCase):
    def setUp(self):
        self.item = DepotItem.objects.create(name="Telt", quantity=5)
        self.team = Team.objects.create(name="Team", short_name="T")
        self.volunteer = Volunteer.objects.create_user(
            username="depot-vol", email="depot@example.com", first_name="D", last_name="V"
        )

    def test_depot_item_form_valid_and_requires_name(self):
        valid = DepotItemForm({"name": "Telt", "quantity": 5, "unit": "stk"})
        self.assertTrue(valid.is_valid(), valid.errors)

        invalid = DepotItemForm({"quantity": 1, "unit": "stk"})
        self.assertFalse(invalid.is_valid())
        self.assertIn("name", invalid.errors)

    def _booking_data(self, **overrides):
        data = {
            "item": self.item.pk,
            "team": self.team.pk,
            "team_contact": self.volunteer.pk,
            "quantity": 2,
            "remarks": "",
            "start_date": date(2026, 1, 1),
            "start_time": "08:00",
            "end_date": date(2026, 1, 2),
            "end_time": "17:00",
        }
        data.update(overrides)
        return data

    def test_depot_booking_form_accepts_valid_window(self):
        form = DepotBookingForm(self._booking_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_depot_booking_form_rejects_end_before_start(self):
        form = DepotBookingForm(
            self._booking_data(end_date=date(2025, 12, 31), end_time="08:00")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Sluttidspunkt skal være efter starttidspunkt", str(form.errors))

    def test_depot_booking_form_rejects_more_than_stock(self):
        form = DepotBookingForm(self._booking_data(quantity=10))
        self.assertFalse(form.is_valid())
        self.assertIn("overstiger", str(form.errors))
