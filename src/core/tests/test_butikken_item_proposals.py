"""Tests for proposing new Butikken items from the order form."""
import json
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from Butikken.models import (
    ButikkenBooking,
    ButikkenItem,
    ButikkenOrder,
    MealPlan,
    TeamMealPlan,
)
from organization.models import Team, TeamMembership, Volunteer


class ButikkenItemProposalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Team.objects.create(name="Team A", short_name="TA")
        cls.user = Volunteer.objects.create_user(
            username="vol",
            email="vol@example.com",
            first_name="Vol",
            last_name="Unteer",
        )
        TeamMembership.objects.create(team=cls.team, member=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        data = {
            "team": self.team.pk,
            "team_contact": self.user.pk,
            "name": "Testordre",
            "pickup_date": "2026-01-01",
            "remarks": "",
            "cart_items_json": "[]",
            "new_items_json": "[]",
        }
        data.update(overrides)
        return data

    def _create_order_with_proposal(self, proposal, **overrides):
        response = self.client.post(
            reverse("Butikken_ButikkenOrder_create"),
            self._payload(new_items_json=json.dumps([proposal]), **overrides),
        )
        self.assertEqual(response.status_code, 302)
        return ButikkenOrder.objects.get(name=overrides.get("name", "Testordre"))

    def test_proposal_creates_pending_item_and_booking(self):
        order = self._create_order_with_proposal(
            {
                "name": "Hakkede tomater",
                "qty": 3,
                "unit": "dåse",
                "description": "Til sovs",
            }
        )

        item = ButikkenItem.objects.get(name="Hakkede tomater")
        self.assertEqual(item.status, ButikkenItem.STATUS_PENDING)
        self.assertEqual(item.type, ButikkenItem.PROPOSAL_TYPE)
        self.assertEqual(item.proposed_by, self.user)
        self.assertEqual(item.source_order, order)
        self.assertEqual(item.content_normal, "3")
        self.assertEqual(item.content_unit, "dåse")

        booking = order.bookings.get(item=item)
        self.assertEqual(booking.quantity, Decimal("3"))
        self.assertEqual(booking.unit, "dåse")

    def test_proposal_reuses_existing_active_item(self):
        existing = ButikkenItem.objects.create(
            name="Kaffe", type="Tørvarer", status=ButikkenItem.STATUS_ACTIVE
        )

        order = self._create_order_with_proposal(
            {"name": "kaffe", "qty": 2, "unit": "pose"}
        )

        self.assertEqual(ButikkenItem.objects.filter(name__iexact="Kaffe").count(), 1)
        booking = order.bookings.get()
        self.assertEqual(booking.item, existing)
        self.assertEqual(booking.quantity, Decimal("2"))

    def test_update_keeps_existing_proposal_booking(self):
        order = self._create_order_with_proposal(
            {"name": "Rugbrød", "qty": 1, "unit": "stk"}
        )
        item = ButikkenItem.objects.get(name="Rugbrød")

        # The update page should render the proposal as part of the cart.
        response = self.client.get(
            reverse("Butikken_ButikkenOrder_update", args=[order.pk])
        )
        self.assertEqual(response.status_code, 200)
        cart = {row["id"]: row for row in response.context["initial_cart"]}
        self.assertIn(str(item.pk), cart)
        self.assertTrue(cart[str(item.pk)]["proposal"])

        # Saving the order with the proposal still in the cart updates the
        # existing booking instead of creating a new item.
        response = self.client.post(
            reverse("Butikken_ButikkenOrder_update", args=[order.pk]),
            self._payload(
                name="Testordre",
                cart_items_json=json.dumps(
                    [{"id": str(item.pk), "qty": 4, "unit": "stk"}]
                ),
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ButikkenItem.objects.filter(name="Rugbrød").count(), 1)
        self.assertEqual(
            ButikkenBooking.objects.get(order=order, item=item).quantity,
            Decimal("4"),
        )

    def test_pending_proposal_is_reused_across_orders(self):
        first_order = self._create_order_with_proposal(
            {"name": "Frisk basilikum", "qty": 1, "unit": "pot"}
        )
        second_order = self._create_order_with_proposal(
            {"name": "frisk basilikum", "qty": 2, "unit": "pot"},
            name="Anden ordre",
        )

        self.assertEqual(
            ButikkenItem.objects.filter(name__iexact="Frisk basilikum").count(), 1
        )
        item = ButikkenItem.objects.get(name__iexact="Frisk basilikum")
        self.assertEqual(first_order.bookings.get(item=item).quantity, Decimal("1"))
        self.assertEqual(second_order.bookings.get(item=item).quantity, Decimal("2"))

    def test_rejecting_proposal_removes_booking_and_notifies_team(self):
        second_member = Volunteer.objects.create_user(
            username="vol2",
            email="vol2@example.com",
            first_name="Second",
            last_name="Member",
        )
        TeamMembership.objects.create(team=self.team, member=second_member)

        order = self._create_order_with_proposal(
            {"name": "Sennep", "qty": 1, "unit": "glas"}
        )
        item = ButikkenItem.objects.get(name="Sennep")

        # Add the webhook after the order (and its booking) exists, so only the
        # rejection notification is queued.
        self.team.discord_webhook_url = "https://discord.com/api/webhooks/123/token"
        self.team.save(update_fields=["discord_webhook_url"])

        with (
            mock.patch("Butikken.services.send_email") as send_email,
            mock.patch("Butikken.services.enqueue_discord_embed") as discord,
            self.captureOnCommitCallbacks(execute=True),
        ):
            item.reject()

        item.refresh_from_db()
        self.assertEqual(item.status, ButikkenItem.STATUS_REJECTED)
        self.assertFalse(ButikkenBooking.objects.filter(item=item).exists())
        self.assertFalse(ButikkenBooking.objects.filter(order=order).exists())

        send_email.assert_called_once()
        subject, template, context, recipients = send_email.call_args.args
        self.assertIn("Sennep", subject)
        self.assertEqual(template, "Butikken/item_proposal_rejected_email.html")
        self.assertEqual(set(recipients), {"vol@example.com", "vol2@example.com"})
        self.assertEqual(context["team"], self.team)
        self.assertEqual(context["quantity"], Decimal("1"))
        self.assertEqual(context["orders"], [order])

        discord.assert_called_once()
        self.assertEqual(discord.call_args.args[0], self.team.pk)

    def test_special_approved_item_is_not_selectable(self):
        special = ButikkenItem.objects.create(
            name="Kun til én ordre",
            type="Specialbestilling",
            status=ButikkenItem.STATUS_SPECIAL,
        )

        list_response = self.client.get(reverse("Butikken_ButikkenItem_list"))
        self.assertNotIn(
            special.pk,
            {item.pk for item in list_response.context["object_list"]},
        )

        form_response = self.client.get(reverse("Butikken_ButikkenOrder_create"))
        available_ids = {
            item["id"] for item in form_response.context["available_items"]
        }
        self.assertNotIn(special.pk, available_ids)

    def test_order_create_page_renders_proposal_controls(self):
        response = self.client.get(reverse("Butikken_ButikkenOrder_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="proposal-panel"')
        self.assertContains(response, 'name="new_items_json"')

    def test_catalog_list_hides_pending_items(self):
        active = ButikkenItem.objects.create(
            name="Mel", type="Tørvarer", status=ButikkenItem.STATUS_ACTIVE
        )
        pending = ButikkenItem.objects.create(
            name="Ukendt vare", type="Specialbestilling", status=ButikkenItem.STATUS_PENDING
        )

        response = self.client.get(reverse("Butikken_ButikkenItem_list"))
        self.assertEqual(response.status_code, 200)
        item_ids = {item.pk for item in response.context["object_list"]}
        self.assertIn(active.pk, item_ids)
        self.assertNotIn(pending.pk, item_ids)


class ButikkenItemProposalAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = Volunteer.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pw-12345-xyz",
            first_name="Ad",
            last_name="Min",
        )
        cls.pending = ButikkenItem.objects.create(
            name="Foreslået vare", type="Specialbestilling", status=ButikkenItem.STATUS_PENDING
        )

    def test_approve_action_promotes_proposal(self):
        from django.contrib.admin.sites import AdminSite

        from Butikken.admin import ButikkenItemAdmin

        admin = ButikkenItemAdmin(ButikkenItem, AdminSite())
        request = type("Request", (), {"_messages": []})()
        # message_user() needs a real request; bypass it for this unit test.
        admin.message_user = lambda *args, **kwargs: None

        admin.approve_proposals(request, ButikkenItem.objects.filter(pk=self.pending.pk))

        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, ButikkenItem.STATUS_ACTIVE)

    def test_approve_as_special_keeps_item_out_of_catalog(self):
        from django.contrib.admin.sites import AdminSite

        from Butikken.admin import ButikkenItemAdmin

        admin = ButikkenItemAdmin(ButikkenItem, AdminSite())
        request = type("Request", (), {"_messages": []})()
        admin.message_user = lambda *args, **kwargs: None

        admin.approve_as_special(
            request, ButikkenItem.objects.filter(pk=self.pending.pk)
        )

        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, ButikkenItem.STATUS_SPECIAL)


class ButikkenDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = Volunteer.objects.create_superuser(
            username="dash-admin",
            email="dash-admin@example.com",
            password="pw-12345-xyz",
            first_name="Dash",
            last_name="Admin",
        )
        cls.team_a = Team.objects.create(name="Team A", short_name="TA")
        cls.team_b = Team.objects.create(name="Team B", short_name="TB")
        cls.user = Volunteer.objects.create_user(
            username="team-a-user",
            email="team-a@example.com",
            first_name="Team",
            last_name="A",
        )
        TeamMembership.objects.create(team=cls.team_a, member=cls.user)

        cls.meal_plan = MealPlan.objects.create(
            name="Morgenmad", meal_date=date(2026, 1, 2)
        )
        TeamMealPlan.objects.create(
            team=cls.team_a, meal_plan=cls.meal_plan, status="Approved"
        )

        cls.order_a = ButikkenOrder.objects.create(
            team=cls.team_a, team_contact=cls.user, name="A-ordre"
        )
        cls.order_b = ButikkenOrder.objects.create(
            team=cls.team_b, name="B-ordre"
        )
        cls.pending_item = ButikkenItem.objects.create(
            name="Foreslået vare",
            type="Specialbestilling",
            status=ButikkenItem.STATUS_PENDING,
            source_order=cls.order_a,
            proposed_by=cls.user,
        )

    def test_dashboard_shows_team_rows_and_pending_count_for_staff(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("Butikken_dashboard"))

        self.assertEqual(response.status_code, 200)
        rows = {row["team"]: row for row in response.context["rows"]}
        self.assertEqual(set(rows), {self.team_a, self.team_b})
        self.assertEqual(rows[self.team_a]["missing_days"], 0)
        self.assertTrue(rows[self.team_a]["meals_complete"])
        self.assertEqual(rows[self.team_b]["missing_days"], 1)
        self.assertEqual(response.context["pending_count"], 1)
        self.assertEqual(response.context["teams_without_orders"], 0)
        self.assertContains(response, "Foreslået vare")

    def test_dashboard_scopes_rows_for_non_staff(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("Butikken_dashboard"))

        self.assertEqual(response.status_code, 200)
        rows = [row["team"] for row in response.context["rows"]]
        self.assertEqual(rows, [self.team_a])
        self.assertEqual(response.context["pending_count"], 0)
        self.assertNotContains(response, "Foreslået vare")

    def test_review_endpoint_approves_as_catalog_item(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("Butikken_ButikkenItem_review", args=[self.pending_item.pk]),
            {"decision": "catalog"},
        )

        self.assertRedirects(response, reverse("Butikken_dashboard"))
        self.pending_item.refresh_from_db()
        self.assertEqual(self.pending_item.status, ButikkenItem.STATUS_ACTIVE)

    def test_review_endpoint_approves_as_special(self):
        self.client.force_login(self.staff)

        self.client.post(
            reverse("Butikken_ButikkenItem_review", args=[self.pending_item.pk]),
            {"decision": "special"},
        )

        self.pending_item.refresh_from_db()
        self.assertEqual(self.pending_item.status, ButikkenItem.STATUS_SPECIAL)

    def test_review_endpoint_requires_staff(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("Butikken_ButikkenItem_review", args=[self.pending_item.pk]),
            {"decision": "catalog"},
        )

        self.assertEqual(response.status_code, 302)
        self.pending_item.refresh_from_db()
        self.assertEqual(self.pending_item.status, ButikkenItem.STATUS_PENDING)
