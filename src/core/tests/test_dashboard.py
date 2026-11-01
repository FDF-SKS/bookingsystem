"""Tests for the dashboard aggregation view (``core.views.index``)."""
from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class DashboardViewTests(TestCase):
    def test_dashboard_renders_for_authenticated_user(self):
        user = User.objects.create_user(
            username="dash-user",
            email="dash@example.com",
            password="pw-12345-xyz",
            first_name="Dash",
            last_name="Board",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("bookings", response.context)
        self.assertEqual(list(response.context["bookings"]), [])

    def test_dashboard_only_includes_user_team_bookings(self):
        user = User.objects.create_user(
            username="dash-user2",
            email="dash2@example.com",
            password="pw-12345-xyz",
            first_name="Dash",
            last_name="Two",
        )
        self.client.force_login(user)

        # A booking belonging to a team the user is not a member of must not leak
        # into the dashboard.
        from organization.models import Team
        from Sjak.models import SjakBooking, SjakItem

        team = Team.objects.create(name="Other team", short_name="OT")
        item = SjakItem.objects.create(name="Item")
        SjakBooking.objects.create(
            team=team,
            item=item,
            team_contact=user,
            quantity=1,
            start_date=date(2026, 1, 1),
            start_time=time(10, 0),
            end_date=date(2026, 1, 1),
            end_time=time(12, 0),
            status="Pending",
        )

        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["bookings"]), [])
