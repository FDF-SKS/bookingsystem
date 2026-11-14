import re
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import (
	Event,
	SlutrengoringAssignment,
	Team,
	TeamMembership,
	Tjanse,
	TjanseOwnership,
	Volunteer,
)
from .slutrengoring_services import (
	assign_highest_priority_to_teams,
	notify_assignment_discord,
)


class TjanseOverviewAssignmentTests(TestCase):
	def setUp(self):
		user = get_user_model().objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="test-password",
		)
		self.client.force_login(user)
		self.day = date(2026, 10, 10)
		self.event = Event.objects.create(
			name="Test event",
			start_date=self.day,
			end_date=self.day,
			deadline_sjak=self.day,
			deadline_teknik=self.day,
			deadline_mad=self.day,
			deadline_aktivitetsteam=self.day,
			deadline_foto=self.day,
			deadline_lokaler=self.day,
			deadline_sos=self.day,
		)
		self.teams = [self.create_team("Team A"), self.create_team("Team B")]
		self.task = Tjanse.objects.create(title="Rengøring")
		self.url = reverse("admin:organization_tjanseownership_overview")

	def create_team(self, name, event=True):
		team = Team.objects.create(name=name, short_name=name)
		if event:
			team.events.add(self.event)
		return team

	def post_assignments(self, selection):
		return self.client.post(
			self.url,
			{
				"event": str(self.event.pk),
				"week_start": self.day.isoformat(),
				f"team_{self.task.pk}_{self.day.isoformat()}": selection,
			},
			follow=True,
		)

	def test_saves_multiple_selected_teams(self):
		response = self.post_assignments([str(team.pk) for team in self.teams])

		self.assertEqual(response.status_code, 200)
		self.assertSetEqual(
			set(self.event.tjanse_ownerships.values_list("team_id", flat=True)),
			{team.pk for team in self.teams},
		)

	def test_all_teams_shortcut_includes_unlinked_teams_and_displays_all(self):
		other_team = self.create_team("Unlinked team", event=False)

		response = self.post_assignments("all")

		self.assertEqual(response.status_code, 200)
		self.assertSetEqual(
			set(self.event.tjanse_ownerships.values_list("team_id", flat=True)),
			{team.pk for team in [*self.teams, other_team]},
		)
		self.assertContains(response, "Alle teams")

	def test_individual_team_options_include_teams_not_linked_to_event(self):
		unlinked_team = self.create_team("Unlinked team", event=False)

		response = self.client.get(
			self.url,
			{"event": self.event.pk, "week_start": self.day.isoformat()},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f'value="{unlinked_team.pk}"')

	def test_retained_assignment_keeps_its_status(self):
		existing = TjanseOwnership.objects.create(
			tjanse=self.task,
			event=self.event,
			team=self.teams[0],
			due_date=self.day,
			status="done",
		)

		self.post_assignments([str(team.pk) for team in self.teams])

		existing.refresh_from_db()
		self.assertEqual(existing.status, "done")
		self.assertEqual(self.event.tjanse_ownerships.count(), 2)

	def test_status_overview_links_team_and_status_to_ownership_detail(self):
		ownership = TjanseOwnership.objects.create(
			tjanse=self.task,
			event=self.event,
			team=self.teams[0],
			due_date=self.day,
			status="done",
		)

		response = self.client.get(
			reverse("admin:organization_tjanseownership_status_overview"),
			{"event": self.event.pk},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.teams[0].short_name)
		self.assertContains(response, "Udført")
		self.assertContains(
			response,
			reverse("admin:organization_tjanseownership_change", args=[ownership.pk]),
		)

	def test_ownership_detail_displays_fields_and_change_history(self):
		ownership = TjanseOwnership.objects.create(
			tjanse=self.task,
			event=self.event,
			team=self.teams[0],
			due_date=self.day,
		)
		ownership.status = "done"
		ownership.save()

		response = self.client.get(
			reverse("admin:organization_tjanseownership_change", args=[ownership.pk])
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.task.title)
		self.assertContains(response, self.teams[0].name)
		self.assertContains(response, "Udført")
		self.assertContains(response, "Ændringshistorik")
		self.assertContains(response, "Oprettet")
		self.assertContains(response, "Ændret")


class SlutrengoringFlowTests(TestCase):
	def setUp(self):
		self.event = Event.objects.create(
			name="Slut event",
			start_date=date(2026, 10, 10),
			end_date=date(2026, 10, 11),
			deadline_sjak=date(2026, 10, 10),
			deadline_teknik=date(2026, 10, 10),
			deadline_mad=date(2026, 10, 10),
			deadline_aktivitetsteam=date(2026, 10, 10),
			deadline_foto=date(2026, 10, 10),
			deadline_lokaler=date(2026, 10, 10),
			deadline_sos=date(2026, 10, 10),
		)
		self.team_a = Team.objects.create(name="Team A", short_name="TA")
		self.team_b = Team.objects.create(name="Team B", short_name="TB")
		self.user_a = Volunteer.objects.create_user(
			username="member-a", email="a@example.com", password="test-password",
			first_name="A", last_name="Member",
		)
		self.user_b = Volunteer.objects.create_user(
			username="member-b", email="b@example.com", password="test-password",
			first_name="B", last_name="Member",
		)
		TeamMembership.objects.create(team=self.team_a, member=self.user_a)
		TeamMembership.objects.create(team=self.team_b, member=self.user_b)
		self.task = Tjanse.objects.create(
			title="Rengør køkkenet",
			kind="slutrengoring",
			priority="required",
		)
		self.assignment = SlutrengoringAssignment.objects.create(
			tjanse=self.task, event=self.event,
		)

	def claim(self, user, assignment=None):
		self.client.force_login(user)
		return self.client.post(
			reverse("slutrengoring_claim", args=[(assignment or self.assignment).pk]),
			{"team": user.teams.first().pk, "event": self.event.pk},
		)

	def test_claim_is_exclusive(self):
		first = self.claim(self.user_a)
		second = self.claim(self.user_b)

		self.assertEqual(first.status_code, 302)
		self.assertEqual(second.status_code, 302)
		self.assignment.refresh_from_db()
		self.assertEqual(self.assignment.team, self.team_a)
		self.assertEqual(self.assignment.status, "assigned")
		self.assertFalse(
			SlutrengoringAssignment.objects.filter(pk=self.assignment.pk, team=self.team_b).exists()
		)

	def test_team_with_active_task_cannot_claim_another(self):
		other_task = Tjanse.objects.create(
			title="Rengør toilettet", kind="slutrengoring", priority="high",
		)
		other = SlutrengoringAssignment.objects.create(
			tjanse=other_task, event=self.event, team=self.team_a, status="in_progress",
		)

		response = self.claim(self.user_a)

		self.assertEqual(response.status_code, 302)
		self.assignment.refresh_from_db()
		self.assertIsNone(self.assignment.team)
		self.assertEqual(self.assignment.status, "available")
		self.assertEqual(other.team, self.team_a)

	def test_start_done_redirects_to_claim_page_when_last_task_finishes(self):
		self.claim(self.user_a)
		self.client.post(reverse("slutrengoring_start", args=[self.assignment.pk]))
		response = self.client.post(reverse("slutrengoring_done", args=[self.assignment.pk]))

		self.assignment.refresh_from_db()
		self.assertEqual(self.assignment.status, "done")
		self.assertIsNotNone(self.assignment.completed_at)
		self.assertIn(reverse("organization_Slutrengoring_claim_list"), response.url)

	def test_not_finished_returns_task_to_pool(self):
		self.claim(self.user_a)
		self.client.post(reverse("slutrengoring_start", args=[self.assignment.pk]))
		response = self.client.post(
			reverse("slutrengoring_not_finished", args=[self.assignment.pk]),
			{"reason": "Mangler udstyr"},
		)

		self.assignment.refresh_from_db()
		self.assertEqual(response.status_code, 302)
		self.assertEqual(self.assignment.status, "not_finished")
		self.assertIsNone(self.assignment.team)
		self.assertEqual(self.assignment.last_team, self.team_a)
		self.assertEqual(self.assignment.attempt_count, 1)
		self.assertEqual(self.assignment.not_finished_reason, "Mangler udstyr")

		# The team that returned the task cannot immediately re-claim it.
		self.claim(self.user_a)
		self.assignment.refresh_from_db()
		self.assertEqual(self.assignment.status, "not_finished")
		self.assertIsNone(self.assignment.team)

	def test_claim_list_orders_required_first(self):
		low = Tjanse.objects.create(title="Lav opgave", kind="slutrengoring", priority="low")
		medium = Tjanse.objects.create(title="Mellem opgave", kind="slutrengoring", priority="medium")
		SlutrengoringAssignment.objects.create(tjanse=low, event=self.event)
		SlutrengoringAssignment.objects.create(tjanse=medium, event=self.event)

		self.client.force_login(self.user_a)
		response = self.client.get(
			reverse("organization_Slutrengoring_claim_list"),
			{"event": self.event.pk},
		)
		content = response.content.decode()

		self.assertEqual(response.status_code, 200)
		self.assertLess(content.index("Rengør køkkenet"), content.index("Mellem opgave"))
		self.assertLess(content.index("Mellem opgave"), content.index("Lav opgave"))

	def test_regular_and_slutrengoring_lists_are_separated(self):
		regular = Tjanse.objects.create(title="Almindelig tjanse", kind="regular")
		TjanseOwnership.objects.create(
			tjanse=regular, event=self.event, team=self.team_a, due_date=date(2026, 10, 10),
		)

		self.client.force_login(self.user_a)
		regular_response = self.client.get(reverse("organization_TjanseOwnership_list"))
		claim_response = self.client.get(
			reverse("organization_Slutrengoring_claim_list"),
			{"event": self.event.pk},
		)

		self.assertContains(regular_response, "Almindelig tjanse")
		self.assertNotContains(regular_response, "Rengør køkkenet")
		self.assertContains(claim_response, "Rengør køkkenet")
		self.assertNotContains(claim_response, "Almindelig tjanse")

	def test_admin_board_renders(self):
		admin = Volunteer.objects.create_superuser(
			username="admin", email="admin@example.com", password="test-password",
		)
		self.client.force_login(admin)
		response = self.client.get(
			reverse("admin:organization_slutrengoringassignment_board"),
			{"event": self.event.pk},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Slutrengøringsstatus")
		self.assertContains(response, "Rengør køkkenet")

	def test_home_page_renders_active_assignment(self):
		self.claim(self.user_a)
		response = self.client.get(
			reverse("organization_Slutrengoring_home"),
			{"event": self.event.pk},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Rengør køkkenet")
		self.assertContains(response, "Start opgave")

	def test_claim_detail_page_renders(self):
		self.client.force_login(self.user_a)
		response = self.client.get(
			reverse("organization_Slutrengoring_detail", args=[self.assignment.pk])
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Rengør køkkenet")
		self.assertContains(response, "Tag opgaven")

	def test_admin_assignment_changelist_renders(self):
		admin = Volunteer.objects.create_superuser(
			username="admin", email="admin@example.com", password="test-password",
		)
		self.client.force_login(admin)
		response = self.client.get(
			reverse("admin:organization_slutrengoringassignment_changelist")
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Rengør køkkenet")

	def test_admin_tools_page_renders(self):
		admin = Volunteer.objects.create_superuser(
			username="admin", email="admin@example.com", password="test-password",
		)
		self.client.force_login(admin)
		response = self.client.get(
			reverse("admin:organization_slutrengoringassignment_tools"),
			{"event": self.event.pk},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Opret tildelinger")
		self.assertContains(response, "Tildel én opgave til hvert ledigt team")

	def test_admin_create_action_creates_assignments(self):
		Tjanse.objects.create(
			title="Støvsug gangen", kind="slutrengoring", priority="low",
		)
		admin = Volunteer.objects.create_superuser(
			username="admin", email="admin@example.com", password="test-password",
		)
		self.client.force_login(admin)
		response = self.client.post(
			reverse("admin:organization_slutrengoringassignment_tools"),
			{"event": self.event.pk, "action": "create"},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(
			SlutrengoringAssignment.objects.filter(event=self.event).count(), 2,
		)

	def test_admin_assign_action_uses_highest_priority(self):
		admin = Volunteer.objects.create_superuser(
			username="admin", email="admin@example.com", password="test-password",
		)
		self.client.force_login(admin)
		response = self.client.post(
			reverse("admin:organization_slutrengoringassignment_tools"),
			{"event": self.event.pk, "action": "assign"},
		)

		self.assertEqual(response.status_code, 302)
		self.assignment.refresh_from_db()
		self.assertEqual(self.assignment.team, self.team_a)
		self.assertEqual(self.assignment.status, "assigned")

	def test_assign_highest_priority_returns_assigned_and_skipped_teams(self):
		assigned, skipped = assign_highest_priority_to_teams(self.event)

		self.assertEqual(len(assigned), 1)
		self.assertEqual(assigned[0].team, self.team_a)
		self.assertEqual(skipped, [self.team_b])

	@mock.patch("organization.slutrengoring_services.enqueue_discord_embed")
	def test_admin_assignment_triggers_discord_signal(self, enqueue):
		self.team_a.discord_webhook_url = "https://discord.test/webhook"
		self.team_a.save(update_fields=["discord_webhook_url"])
		admin = Volunteer.objects.create_superuser(
			username="admin", email="admin@example.com", password="test-password",
		)
		task = Tjanse.objects.create(
			title="Rengør toilettet", kind="slutrengoring", priority="high",
		)

		SlutrengoringAssignment.objects.create(
			tjanse=task,
			event=self.event,
			team=self.team_a,
			status="assigned",
			assigned_by=admin,
		)

		enqueue.assert_called_once()

	@mock.patch("organization.slutrengoring_services.enqueue_discord_embed")
	def test_assignment_discord_notification(self, enqueue):
		self.team_a.discord_webhook_url = "https://discord.test/webhook"
		self.team_a.save(update_fields=["discord_webhook_url"])
		self.assignment.team = self.team_a
		self.assignment.status = "assigned"
		self.assignment.save()

		sent = notify_assignment_discord(self.assignment, changed_by=self.user_a)

		self.assertTrue(sent)
		enqueue.assert_called_once()

	def test_management_command_creates_missing_assignments(self):
		task = Tjanse.objects.create(
			title="Støvsug gangen", kind="slutrengoring", priority="low",
		)

		call_command("create_slutrengoring_assignments", event=self.event.pk)

		self.assertTrue(
			SlutrengoringAssignment.objects.filter(
				tjanse=task, event=self.event, status="available",
			).exists()
		)
		self.assertEqual(
			SlutrengoringAssignment.objects.filter(event=self.event).count(), 2,
		)

	def test_tjanse_ownership_rejects_slutrengoring_task(self):
		ownership = TjanseOwnership(
			tjanse=self.task,
			event=self.event,
			team=self.team_a,
			due_date=date(2026, 10, 10),
		)

		with self.assertRaises(ValidationError):
			ownership.full_clean()

	def test_event_selector_lists_the_event_inside_the_select(self):
		"""Guard against a stray closing tag that empties the dropdown."""
		self.event.is_active = True
		self.event.save(update_fields=["is_active"])
		self.client.force_login(self.user_a)

		for url_name in (
			"organization_Slutrengoring_home",
			"organization_Slutrengoring_claim_list",
		):
			response = self.client.get(reverse(url_name))
			html = response.content.decode()
			match = re.search(
				r'<select[^>]*id="id_event"[^>]*>(.*?)</select>', html, re.DOTALL
			)
			self.assertIsNotNone(match, url_name)
			self.assertIn(self.event.name, match.group(1), url_name)


