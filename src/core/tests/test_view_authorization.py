"""Regression tests for the authorization hardening of the Django views.

These complement ``test_api_endpoints.py`` by asserting that:

- global catalogs are staff-only for mutations (``StaffRequiredMixin``),
- team-scoped records are hidden from users outside the owning team
  (``TeamQuerysetMixin`` / nested Loeb scoping), and
- team dropdowns on booking forms are limited to the user's own teams.
"""
from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from AktivitetsTeam.models import AktivitetsTeamBooking, AktivitetsTeamItem
from Butikken.forms import ButikkenOrderForm, MealBookingForm, TeamMealPlanForm
from Butikken.models import ButikkenOrder, MealBooking
from Depot.models import DepotBooking, DepotItem
from Loeb.forms import HoldForm, TaskForm
from Loeb.models import Hold, Loeb, PhysicalStation, Task, TaskSubmission
from organization.models import (
    Event,
    Key,
    Team,
    TeamMembership,
    Volunteer,
)
from Sjak.models import SjakBooking, SjakItem, SjakItemType
from SOS.forms import SOSBookingForm
from SOS.models import SOSBooking, SOSItem
from Teknik.forms import TeknikBookingForm
from Teknik.models import TeknikBooking, TeknikItem


class ViewAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team_a = Team.objects.create(name="Team A", short_name="TA")
        cls.team_b = Team.objects.create(name="Team B", short_name="TB")

        cls.user = Volunteer.objects.create_user(
            username="volunteer",
            email="volunteer@example.com",
            password="pw-12345-xyz",
        )
        cls.staff = Volunteer.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="pw-12345-xyz",
            is_staff=True,
        )
        TeamMembership.objects.create(team=cls.team_a, member=cls.user)

        # Depot
        cls.depot_item = DepotItem.objects.create(name="Telt", quantity=5)
        cls.team_b_depot_booking = DepotBooking.objects.create(
            item=cls.depot_item,
            team=cls.team_b,
            team_contact=cls.staff,
            quantity=1,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )

        # Butikken
        cls.team_b_meal_booking = MealBooking.objects.create(
            team=cls.team_b,
            team_contact=cls.staff,
        )
        cls.team_b_order = ButikkenOrder.objects.create(
            team=cls.team_b,
            team_contact=cls.staff,
            name="Team B order",
            pickup_date=date(2026, 1, 1),
        )

        # organization
        cls.key = Key.objects.create(name="Nøgle", number="1")

        # SOS
        cls.sos_item = SOSItem.objects.create(name="SOS ting", description="x")
        cls.team_b_sos_booking = SOSBooking.objects.create(
            team=cls.team_b,
            item=cls.sos_item,
            team_contact=cls.staff,
            quantity=Decimal("1"),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )

        # Teknik
        cls.teknik_item = TeknikItem.objects.create(name="Teknik ting", description="x")
        cls.team_b_teknik_booking = TeknikBooking.objects.create(
            team=cls.team_b,
            item=cls.teknik_item,
            team_contact=cls.staff,
            quantity=Decimal("1"),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )

        # Sjak
        cls.sjak_item = SjakItem.objects.create(name="Sjak ting")
        cls.sjak_item_type = SjakItemType.objects.create(name="Sjak type")
        cls.team_b_sjak_booking = SjakBooking.objects.create(
            team=cls.team_b,
            item=cls.sjak_item,
            team_contact=cls.staff,
            quantity=Decimal("1"),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
        )

        # AktivitetsTeam
        cls.aktivitet_item = AktivitetsTeamItem.objects.create(
            name="AT ting",
            description="x",
            short_description="x",
        )
        cls.team_b_aktivitet_booking = AktivitetsTeamBooking.objects.create(
            team=cls.team_b,
            item=cls.aktivitet_item,
            team_contact=cls.staff,
            start_date=date(2026, 1, 1),
            start_time=time(8, 0),
            end_date=date(2026, 1, 2),
            end_time=time(17, 0),
        )

        # Loeb / Task / Hold / TaskSubmission (all owned by team B)
        cls.team_b_loeb = Loeb.objects.create(name="Team B løb", team=cls.team_b)
        cls.team_b_task = Task.objects.create(loeb=cls.team_b_loeb, title="Team B opgave")
        cls.team_b_hold = Hold.objects.create(
            loeb=cls.team_b_loeb, name="Team B hold", pin_code="9999"
        )
        cls.team_b_submission = TaskSubmission.objects.create(
            hold=cls.team_b_hold, task=cls.team_b_task
        )

    def setUp(self):
        self.client.force_login(self.user)

    # -- Global catalogs: staff-only mutations -----------------------------

    def test_non_staff_cannot_create_depot_item(self):
        response = self.client.post(
            reverse("Depot_DepotItem_create"),
            {"name": "Ny", "quantity": 1, "unit": "stk"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(DepotItem.objects.filter(name="Ny").exists())

    def test_non_staff_cannot_delete_depot_item(self):
        response = self.client.post(
            reverse("Depot_DepotItem_delete", args=[self.depot_item.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(DepotItem.objects.filter(pk=self.depot_item.pk).exists())

    def test_non_staff_cannot_create_event(self):
        response = self.client.post(
            reverse("organization_Event_create"),
            {
                "name": "Nyt event",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "deadline_sjak": "2025-12-01",
                "deadline_teknik": "2025-12-01",
                "deadline_mad": "2025-12-01",
                "deadline_aktivitetsteam": "2025-12-01",
                "deadline_foto": "2025-12-01",
                "deadline_lokaler": "2025-12-01",
                "deadline_sos": "2025-12-01",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Event.objects.filter(name="Nyt event").exists())

    def test_non_staff_cannot_delete_key(self):
        response = self.client.post(
            reverse("organization_Key_delete", args=[self.key.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Key.objects.filter(pk=self.key.pk).exists())

    def test_non_staff_cannot_create_sos_item(self):
        response = self.client.post(
            reverse("SOS_SOSItem_create"), {"name": "Ny", "description": "x"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SOSItem.objects.filter(name="Ny").exists())

    def test_non_staff_cannot_delete_sos_item(self):
        response = self.client.post(
            reverse("SOS_SOSItem_delete", args=[self.sos_item.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(SOSItem.objects.filter(pk=self.sos_item.pk).exists())

    def test_non_staff_cannot_create_teknik_item(self):
        response = self.client.post(
            reverse("Teknik_TeknikItem_create"), {"name": "Ny", "description": "x"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TeknikItem.objects.filter(name="Ny").exists())

    def test_non_staff_cannot_create_sjak_item(self):
        response = self.client.post(
            reverse("Sjak_SjakItem_create"), {"name": "Ny"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SjakItem.objects.filter(name="Ny").exists())

    def test_non_staff_cannot_create_aktivitet_item(self):
        response = self.client.post(
            reverse("AktivitetsTeam_AktivitetsTeamItem_create"),
            {"name": "Ny", "description": "x", "short_description": "x"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AktivitetsTeamItem.objects.filter(name="Ny").exists())

    def test_non_staff_cannot_create_physical_station(self):
        response = self.client.post(
            reverse("Loeb_PhysicalStation_create"), {"name": "Ny", "qr_code": "ny-1"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PhysicalStation.objects.filter(name="Ny").exists())

    # -- Team-scoped records: hidden from other teams ----------------------

    def test_non_staff_cannot_read_other_team_depot_booking(self):
        response = self.client.get(
            reverse("Depot_DepotBooking_detail", args=[self.team_b_depot_booking.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_update_other_team_depot_booking(self):
        response = self.client.get(
            reverse("Depot_DepotBooking_update", args=[self.team_b_depot_booking.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_other_team_depot_booking(self):
        response = self.client.post(
            reverse("Depot_DepotBooking_delete", args=[self.team_b_depot_booking.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            DepotBooking.objects.filter(pk=self.team_b_depot_booking.pk).exists()
        )

    def test_non_staff_cannot_update_other_team_meal_booking(self):
        response = self.client.get(
            reverse("Butikken_MealBooking_update", args=[self.team_b_meal_booking.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_other_team_meal_booking(self):
        response = self.client.post(
            reverse("Butikken_MealBooking_delete", args=[self.team_b_meal_booking.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            MealBooking.objects.filter(pk=self.team_b_meal_booking.pk).exists()
        )

    def test_non_staff_cannot_update_other_team_order(self):
        response = self.client.get(
            reverse("Butikken_ButikkenOrder_update", args=[self.team_b_order.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_other_team_order(self):
        response = self.client.post(
            reverse("Butikken_ButikkenOrder_delete", args=[self.team_b_order.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ButikkenOrder.objects.filter(pk=self.team_b_order.pk).exists())

    def test_non_staff_cannot_update_other_team_sos_booking(self):
        response = self.client.get(
            reverse("SOS_SOSBooking_update", args=[self.team_b_sos_booking.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_other_team_sos_booking(self):
        response = self.client.post(
            reverse("SOS_SOSBooking_delete", args=[self.team_b_sos_booking.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            SOSBooking.objects.filter(pk=self.team_b_sos_booking.pk).exists()
        )

    def test_non_staff_cannot_update_other_team_teknik_booking(self):
        response = self.client.get(
            reverse("Teknik_TeknikBooking_update", args=[self.team_b_teknik_booking.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_other_team_teknik_booking(self):
        response = self.client.post(
            reverse("Teknik_TeknikBooking_delete", args=[self.team_b_teknik_booking.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            TeknikBooking.objects.filter(pk=self.team_b_teknik_booking.pk).exists()
        )

    def test_non_staff_cannot_update_other_team_sjak_booking(self):
        response = self.client.get(
            reverse("Sjak_SjakBooking_update", args=[self.team_b_sjak_booking.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_sjak_signal_formats_string_and_time_values(self):
        """The Discord signal must not crash on string defaults or values."""
        from utils.formatting import short_date, short_time

        self.assertEqual(short_time("12:01"), "12:01")
        self.assertEqual(short_time("12:01:30"), "12:01")
        self.assertEqual(short_time(time(8, 5)), "08:05")
        self.assertEqual(short_time(None), "")
        self.assertEqual(short_date(date(2026, 1, 2)), "02/01")
        self.assertEqual(short_date("2026-01-02"), "2026-01-02")
        self.assertEqual(short_date(None), "")

    def test_non_staff_cannot_delete_other_team_sjak_booking(self):
        response = self.client.post(
            reverse("Sjak_SjakBooking_delete", args=[self.team_b_sjak_booking.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            SjakBooking.objects.filter(pk=self.team_b_sjak_booking.pk).exists()
        )

    def test_non_staff_cannot_update_other_team_aktivitet_booking(self):
        response = self.client.get(
            reverse(
                "AktivitetsTeam_AktivitetsTeamBooking_update",
                args=[self.team_b_aktivitet_booking.pk],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_other_team_aktivitet_booking(self):
        response = self.client.post(
            reverse(
                "AktivitetsTeam_AktivitetsTeamBooking_delete",
                args=[self.team_b_aktivitet_booking.pk],
            )
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            AktivitetsTeamBooking.objects.filter(
                pk=self.team_b_aktivitet_booking.pk
            ).exists()
        )

    def test_non_staff_cannot_read_other_team_loeb(self):
        response = self.client.get(
            reverse("Loeb_Loeb_detail", args=[self.team_b_loeb.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_update_other_team_loeb(self):
        response = self.client.get(
            reverse("Loeb_Loeb_update", args=[self.team_b_loeb.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_other_team_loeb(self):
        response = self.client.post(
            reverse("Loeb_Loeb_delete", args=[self.team_b_loeb.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Loeb.objects.filter(pk=self.team_b_loeb.pk).exists())

    def test_non_staff_cannot_read_other_team_task(self):
        response = self.client.get(
            reverse("Loeb_Task_detail", args=[self.team_b_task.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_read_other_team_hold(self):
        response = self.client.get(
            reverse("Loeb_Hold_detail", args=[self.team_b_hold.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_read_other_team_task_submission(self):
        response = self.client.get(
            reverse("Loeb_TaskSubmission_detail", args=[self.team_b_submission.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_staff_cannot_delete_other_team_task_submission(self):
        response = self.client.post(
            reverse("Loeb_TaskSubmission_delete", args=[self.team_b_submission.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            TaskSubmission.objects.filter(pk=self.team_b_submission.pk).exists()
        )

    # -- Booking forms: team dropdown limited to the user's teams ----------

    def test_meal_booking_form_limits_team_choices(self):
        form = MealBookingForm(user=self.user)
        self.assertIn(self.team_a, form.fields["team"].queryset)
        self.assertNotIn(self.team_b, form.fields["team"].queryset)

    def test_meal_booking_form_staff_keeps_full_team_choices(self):
        form = MealBookingForm(user=self.staff)
        self.assertIn(self.team_a, form.fields["team"].queryset)
        self.assertIn(self.team_b, form.fields["team"].queryset)

    def test_butikken_order_form_limits_team_choices(self):
        form = ButikkenOrderForm(user=self.user)
        self.assertIn(self.team_a, form.fields["team"].queryset)
        self.assertNotIn(self.team_b, form.fields["team"].queryset)

    def test_team_meal_plan_form_limits_team_choices(self):
        form = TeamMealPlanForm(user=self.user)
        self.assertIn(self.team_a, form.fields["team"].queryset)
        self.assertNotIn(self.team_b, form.fields["team"].queryset)

    def test_sos_booking_form_limits_team_choices(self):
        form = SOSBookingForm(user=self.user)
        self.assertIn(self.team_a, form.fields["team"].queryset)
        self.assertNotIn(self.team_b, form.fields["team"].queryset)

    def test_teknik_booking_form_limits_team_choices(self):
        form = TeknikBookingForm(user=self.user)
        self.assertIn(self.team_a, form.fields["team"].queryset)
        self.assertNotIn(self.team_b, form.fields["team"].queryset)

    def test_task_form_limits_loeb_choices(self):
        form = TaskForm(user=self.user)
        self.assertNotIn(self.team_b_loeb, form.fields["loeb"].queryset)

    def test_hold_form_limits_loeb_choices(self):
        form = HoldForm(user=self.user)
        self.assertNotIn(self.team_b_loeb, form.fields["loeb"].queryset)

    # -- Anonymous access: sensitive views require a session --------------

    def test_anonymous_cannot_view_key_list(self):
        self.client.logout()
        response = self.client.get(reverse("organization_Key_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url.lower())

    def test_anonymous_cannot_delete_volunteer(self):
        self.client.logout()
        response = self.client.post(
            reverse("organization_Volunteer_delete", args=[self.user.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Volunteer.objects.filter(pk=self.user.pk).exists())

    def test_anonymous_cannot_delete_sjak_item(self):
        self.client.logout()
        response = self.client.post(
            reverse("Sjak_SjakItem_delete", args=[self.sjak_item.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SjakItem.objects.filter(pk=self.sjak_item.pk).exists())

    def test_anonymous_cannot_delete_sjak_item_type(self):
        self.client.logout()
        response = self.client.post(
            reverse("Sjak_SjakItemType_delete", args=[self.sjak_item_type.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            SjakItemType.objects.filter(pk=self.sjak_item_type.pk).exists()
        )

    def test_anonymous_cannot_bulk_update_meal_plans(self):
        self.client.logout()
        response = self.client.post(reverse("Butikken_TeamMealPlan_bulk_update"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url.lower())

    def test_hold_login_does_not_disclose_pin(self):
        self.client.logout()
        response = self.client.get(
            reverse("Loeb_Hold_login", args=[self.team_b_loeb.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "9999")
