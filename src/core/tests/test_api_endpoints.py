"""
Integration tests for the DRF API endpoints.

The endpoints were previously only "covered" because the modules are imported
when the URLconf loads. These tests actually exercise the list endpoints, the
permission class, and a full CRUD round-trip.
"""
import json

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
        client.force_authenticate(self.user)

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
