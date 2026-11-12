"""
Integration tests for the DRF API endpoints.

The endpoints were previously only "covered" because the modules are imported
when the URLconf loads. These tests actually exercise the list endpoints, the
permission class, and a full CRUD round-trip.
"""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from AktivitetsTeam.models import AktivitetsTeamBooking, AktivitetsTeamItem
from Butikken.models import (
    ButikkenBooking,
    ButikkenItem,
    ButikkenItemType,
    ButikkenOrder,
    Day,
    Meal,
    MealBooking,
    MealPlan,
    Option,
    Recipe,
    TeamMealPlan,
)
from Foto.models import FotoBooking, FotoItem
from Loeb.models import Hold, Loeb, PhysicalStation, Task, TaskSubmission
from organization.models import (
    Event,
    EventMembership,
    Key,
    Team,
    TeamMembership,
    Tjanse,
    TjanseOwnership,
    TjanseSwapRequest,
    Volunteer,
)
from Sjak.models import SjakBooking, SjakItem, SjakItemType
from SOS.models import SOSBooking, SOSItem, SOSType
from Teknik.models import TeknikBooking, TeknikItem, TeknikType

User = get_user_model()

API_MODELS = [
    # organization
    Event, EventMembership, Team, TeamMembership, Volunteer, Key,
    Tjanse, TjanseOwnership, TjanseSwapRequest,
    # AktivitetsTeam
    AktivitetsTeamItem, AktivitetsTeamBooking,
    # Butikken
    Day, Recipe, ButikkenItemType, Meal, Option, ButikkenItem,
    ButikkenBooking, ButikkenOrder, MealBooking, TeamMealPlan,
    # Foto
    FotoItem, FotoBooking,
    # Loeb
    Loeb, PhysicalStation, Task, Hold, TaskSubmission,
    # Sjak
    SjakItem, SjakBooking, SjakItemType,
    # SOS
    SOSBooking, SOSItem, SOSType,
    # Teknik
    TeknikBooking, TeknikItem, TeknikType,
]

BASENAMES = sorted({model._meta.model_name for model in API_MODELS})

SERIALIZER_APPS = [
    "organization",
    "AktivitetsTeam",
    "Butikken",
    "Depot",
    "Foto",
    "Loeb",
    "SOS",
    "Sjak",
    "Teknik",
]


class ApiEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="api-user",
            email="api@example.com",
            password="pw-12345-xyz",
            first_name="Api",
            last_name="User",
        )
        cls.staff = User.objects.create_user(
            username="api-staff",
            email="apistaff@example.com",
            password="pw-12345-xyz",
            first_name="Api",
            last_name="Staff",
            is_staff=True,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_every_list_endpoint_returns_json(self):
        for basename in BASENAMES:
            with self.subTest(basename=basename):
                response = self.client.get(reverse(f"{basename}-list"))
                self.assertEqual(response.status_code, 200)
                self.assertIsInstance(response.json(), list)

    def test_list_endpoints_require_authentication(self):
        self.client.logout()
        for basename in BASENAMES:
            with self.subTest(basename=basename):
                response = self.client.get(reverse(f"{basename}-list"))
                self.assertIn(response.status_code, (401, 403))

    def test_team_crud_roundtrip(self):
        client = APIClient()
        client.force_authenticate(self.staff)

        list_url = reverse("team-list")

        created = client.post(
            list_url,
            json.dumps({"name": "API Team", "short_name": "AT"}),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)

        team = Team.objects.get(name="API Team")
        detail_url = reverse("team-detail", args=[team.pk])

        retrieved = client.get(detail_url)
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(retrieved.json()["short_name"], "AT")

        updated = client.patch(
            detail_url,
            json.dumps({"short_name": "AT2"}),
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        team.refresh_from_db()
        self.assertEqual(team.short_name, "AT2")

        deleted = client.delete(detail_url)
        self.assertEqual(deleted.status_code, 204, deleted.content)
        self.assertFalse(Team.objects.filter(pk=team.pk).exists())

    def test_non_staff_cannot_create_team(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(
            reverse("team-list"),
            json.dumps({"name": "Nope", "short_name": "N"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_all_serializers_have_valid_fields(self):
        """Guards against serializers listing fields that do not exist."""
        import importlib

        from rest_framework.serializers import BaseSerializer

        for app in SERIALIZER_APPS:
            module = importlib.import_module(f"{app}.serializers")
            for name in dir(module):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseSerializer)
                    and obj is not BaseSerializer
                ):
                    with self.subTest(serializer=f"{app}.{name}"):
                        list(obj().fields)


class ApiCrossTenantTests(TestCase):
    """Team-scoped API viewsets must hide other teams' records (404)."""

    @classmethod
    def setUpTestData(cls):
        cls.team_a = Team.objects.create(name="API Team A", short_name="AA")
        cls.team_b = Team.objects.create(name="API Team B", short_name="BB")

        cls.user = User.objects.create_user(
            username="tenant-a",
            email="tenant-a@example.com",
            password="pw-12345-xyz",
        )
        cls.staff = User.objects.create_user(
            username="tenant-staff",
            email="tenant-staff@example.com",
            password="pw-12345-xyz",
            is_staff=True,
        )
        TeamMembership.objects.create(team=cls.team_a, member=cls.user)

        # Butikken
        cls.butikken_item = ButikkenItem.objects.create(name="Vare")
        cls.team_b_order = ButikkenOrder.objects.create(
            team=cls.team_b,
            team_contact=cls.staff,
            name="Team B order",
            pickup_date=date(2026, 1, 1),
        )
        cls.team_b_butikken_booking = ButikkenBooking.objects.create(
            team=cls.team_b,
            item=cls.butikken_item,
            team_contact=cls.staff,
            order=cls.team_b_order,
            start_date=date(2026, 1, 1),
            start_time="08:00",
            quantity=Decimal("1"),
            unit="stk",
        )
        cls.team_b_meal_booking = MealBooking.objects.create(
            team=cls.team_b,
            team_contact=cls.staff,
        )
        meal_plan = MealPlan.objects.create(name="Plan")
        cls.team_b_meal_plan = TeamMealPlan.objects.create(
            team=cls.team_b,
            meal_plan=meal_plan,
        )

        # SOS
        cls.sos_item = SOSItem.objects.create(name="SOS ting", description="x")
        cls.team_b_sos_booking = SOSBooking.objects.create(
            team=cls.team_b,
            item=cls.sos_item,
            team_contact=cls.staff,
            quantity=Decimal("1"),
        )

        # Loeb
        cls.team_b_loeb = Loeb.objects.create(name="Team B løb", team=cls.team_b)
        cls.team_b_task = Task.objects.create(loeb=cls.team_b_loeb, title="Team B opgave")
        cls.team_b_task_2 = Task.objects.create(
            loeb=cls.team_b_loeb, title="Team B opgave 2"
        )
        cls.team_b_hold = Hold.objects.create(
            loeb=cls.team_b_loeb, name="Team B hold", pin_code="8888"
        )
        cls.team_b_submission = TaskSubmission.objects.create(
            hold=cls.team_b_hold, task=cls.team_b_task
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _assert_blocked(self, basename, pk, methods=("get",)):
        url = reverse(f"{basename}-detail", args=[pk])
        for method in methods:
            with self.subTest(viewset=basename, method=method):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 404, response.content)

    def test_butikken_booking_is_team_scoped(self):
        self._assert_blocked(
            "butikkenbooking",
            self.team_b_butikken_booking.pk,
            ("get", "patch", "delete"),
        )

    def test_meal_booking_is_team_scoped(self):
        self._assert_blocked(
            "mealbooking", self.team_b_meal_booking.pk, ("get", "patch", "delete")
        )

    def test_team_meal_plan_is_team_scoped(self):
        self._assert_blocked("teammealplan", self.team_b_meal_plan.pk, ("get", "patch"))

    def test_butikken_order_is_team_scoped(self):
        self._assert_blocked("butikkenorder", self.team_b_order.pk, ("get", "patch"))

    def test_sos_booking_is_team_scoped(self):
        self._assert_blocked(
            "sosbooking", self.team_b_sos_booking.pk, ("get", "patch", "delete")
        )

    def test_loeb_is_team_scoped(self):
        self._assert_blocked("loeb", self.team_b_loeb.pk, ("get", "patch", "delete"))

    def test_task_is_team_scoped(self):
        self._assert_blocked("task", self.team_b_task.pk, ("get", "patch", "delete"))

    def test_hold_is_team_scoped(self):
        self._assert_blocked("hold", self.team_b_hold.pk, ("get", "patch", "delete"))

    def test_task_submission_is_team_scoped(self):
        self._assert_blocked(
            "tasksubmission", self.team_b_submission.pk, ("get", "patch", "delete")
        )

    def test_cannot_create_task_for_other_team_loeb(self):
        response = self.client.post(
            reverse("task-list"),
            {"loeb": self.team_b_loeb.pk, "title": "Injected"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Task.objects.filter(title="Injected").exists())

    def test_cannot_create_task_submission_for_other_team(self):
        response = self.client.post(
            reverse("tasksubmission-list"),
            {"hold": self.team_b_hold.pk, "task": self.team_b_task_2.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_can_create_loeb_for_own_team(self):
        response = self.client.post(
            reverse("loeb-list"),
            {"name": "Mit løb", "team": self.team_a.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_staff_can_access_other_team_objects(self):
        client = APIClient()
        client.force_authenticate(self.staff)
        response = client.get(reverse("loeb-detail", args=[self.team_b_loeb.pk]))
        self.assertEqual(response.status_code, 200)
