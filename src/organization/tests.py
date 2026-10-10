from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Event, Team, Tjanse, TjanseOwnership


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


