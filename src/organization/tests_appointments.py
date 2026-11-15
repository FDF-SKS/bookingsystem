"""Tests for personal, shared and team-level legeaftaler."""

from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django_comments_xtd.models import XtdComment

from organization.forms import AppointmentForm
from organization.models import Team, TeamMembership, Volunteer, VolunteerAppointment


class AppointmentTestBase(TestCase):
    def setUp(self):
        self.team_a = Team.objects.create(name="Team A", short_name="A")
        self.team_b = Team.objects.create(name="Team B", short_name="B")
        self.team_c = Team.objects.create(name="Team C", short_name="C")

        self.alice = self._user("alice", self.team_a)
        self.eve = self._user("eve", self.team_a)
        self.bob = self._user("bob", self.team_b)
        self.carol = self._user("carol", self.team_b)
        self.dave = self._user("dave", self.team_c)
        self.staff = self._user("staff", None, is_staff=True)

        today = timezone.localdate()
        self.personal = VolunteerAppointment.objects.create(
            requester=self.alice,
            receiver=self.bob,
            description="Personlig aftale",
            start_date=today + timedelta(days=1),
            start_time=time(12, 0),
            end_date=today + timedelta(days=1),
            end_time=time(13, 0),
        )
        self.shared = VolunteerAppointment.objects.create(
            requester=self.alice,
            receiver=self.bob,
            shared_with_team=True,
            description="Delt aftale",
            start_date=today + timedelta(days=2),
            start_time=time(12, 0),
            end_date=today + timedelta(days=2),
            end_time=time(13, 0),
        )
        self.team_appointment = VolunteerAppointment.objects.create(
            requester=self.alice,
            receiver=None,
            receiver_team=self.team_b,
            description="Aftale med hele team B",
            start_date=today + timedelta(days=3),
            start_time=time(12, 0),
            end_date=today + timedelta(days=3),
            end_time=time(13, 0),
        )

    def _user(self, username, team, **kwargs):
        user = Volunteer.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="test-password",
            first_name=username.title(),
            last_name="Test",
            **kwargs,
        )
        if team is not None:
            TeamMembership.objects.create(team=team, member=user)
        return user

    def detail_url(self, appointment):
        return reverse(
            "organization_VolunteerAppointment_detail", args=[appointment.pk]
        )


class AppointmentModelTests(AppointmentTestBase):
    def test_requires_exactly_one_receiver(self):
        neither = VolunteerAppointment(requester=self.alice, description="Ingen")
        with self.assertRaises(ValidationError):
            neither.full_clean()

        both = VolunteerAppointment(
            requester=self.alice,
            receiver=self.bob,
            receiver_team=self.team_b,
            description="Begge",
        )
        with self.assertRaises(ValidationError):
            both.full_clean()

    def test_receiver_display_covers_person_and_team(self):
        self.assertEqual(self.personal.receiver_display, "Bob Test")
        self.assertEqual(self.team_appointment.receiver_display, "Team B (team)")

    def test_visibility_rules(self):
        self.assertTrue(self.personal.can_view(self.alice))
        self.assertTrue(self.personal.can_view(self.bob))
        self.assertFalse(self.personal.can_view(self.eve))
        self.assertFalse(self.personal.can_view(self.dave))
        self.assertTrue(self.personal.can_view(self.staff))

        self.assertTrue(self.shared.can_view(self.eve))
        self.assertFalse(self.shared.can_view(self.dave))

        self.assertTrue(self.team_appointment.can_view(self.bob))
        self.assertTrue(self.team_appointment.can_view(self.carol))
        self.assertFalse(self.team_appointment.can_view(self.dave))
        self.assertFalse(self.team_appointment.can_view(self.eve))

    def test_response_permissions(self):
        self.assertTrue(self.personal.can_respond(self.bob))
        self.assertFalse(self.personal.can_respond(self.carol))
        self.assertTrue(self.team_appointment.can_respond(self.carol))
        self.assertFalse(self.team_appointment.can_respond(self.dave))
        self.assertFalse(self.team_appointment.can_respond(self.eve))

    def test_only_requester_can_edit(self):
        self.assertTrue(self.personal.can_edit(self.alice))
        self.assertFalse(self.personal.can_edit(self.bob))
        self.assertTrue(self.personal.can_edit(self.staff))

    def test_role_labels(self):
        self.assertEqual(self.personal.role_for(self.alice), "requester")
        self.assertEqual(self.personal.role_for(self.bob), "receiver")
        self.assertEqual(self.team_appointment.role_for(self.carol), "team")
        self.assertEqual(self.shared.role_for(self.eve), "shared")
        self.assertEqual(self.team_appointment.role_for(self.staff), "staff")


class AppointmentFormTests(AppointmentTestBase):
    def form_data(self, **overrides):
        data = {
            "start_date": "2026-01-01",
            "start_time": "12:00",
            "end_date": "2026-01-01",
            "end_time": "13:00",
            "description": "Testaftale",
        }
        data.update(overrides)
        return data

    def group_values(self, form, group_label):
        return {
            value
            for value, _label in dict(form.fields["recipient"].choices)[group_label]
        }

    def test_recipient_is_required(self):
        form = AppointmentForm(data=self.form_data(), user=self.alice)
        self.assertFalse(form.is_valid())
        self.assertIn("recipient", form.errors)

    def test_accepts_a_person(self):
        form = AppointmentForm(
            data=self.form_data(recipient=f"person:{self.bob.pk}"), user=self.alice
        )
        self.assertTrue(form.is_valid(), form.errors)
        appointment = form.save(commit=False)
        appointment.requester = self.alice
        appointment.save()
        self.assertEqual(appointment.receiver, self.bob)
        self.assertIsNone(appointment.receiver_team)

    def test_accepts_a_team_instead_of_a_person(self):
        form = AppointmentForm(
            data=self.form_data(recipient=f"team:{self.team_b.pk}"), user=self.alice
        )
        self.assertTrue(form.is_valid(), form.errors)
        appointment = form.save(commit=False)
        appointment.requester = self.alice
        appointment.save()
        self.assertIsNone(appointment.receiver)
        self.assertEqual(appointment.receiver_team, self.team_b)

    def test_cannot_book_yourself(self):
        form = AppointmentForm(
            data=self.form_data(recipient=f"person:{self.alice.pk}"), user=self.alice
        )
        self.assertFalse(form.is_valid())
        self.assertIn("recipient", form.errors)

    def test_rejects_an_unknown_recipient(self):
        form = AppointmentForm(
            data=self.form_data(recipient="team:999999"), user=self.alice
        )
        self.assertFalse(form.is_valid())
        self.assertIn("recipient", form.errors)

    def test_choices_are_grouped_and_exclude_requester_and_own_teams(self):
        form = AppointmentForm(user=self.alice)
        group_labels = [label for label, _choices in form.fields["recipient"].choices]
        self.assertIn("Personer", group_labels)
        self.assertIn("Teams", group_labels)

        people = self.group_values(form, "Personer")
        self.assertIn(f"person:{self.bob.pk}", people)
        self.assertNotIn(f"person:{self.alice.pk}", people)

        teams = self.group_values(form, "Teams")
        self.assertIn(f"team:{self.team_b.pk}", teams)
        self.assertNotIn(f"team:{self.team_a.pk}", teams)

        staff_form = AppointmentForm(user=self.staff)
        self.assertIn(f"team:{self.team_a.pk}", self.group_values(staff_form, "Teams"))

    def test_update_shows_the_current_recipient(self):
        person_form = AppointmentForm(user=self.alice, instance=self.personal)
        self.assertEqual(person_form.fields["recipient"].initial, f"person:{self.bob.pk}")

        team_form = AppointmentForm(user=self.alice, instance=self.team_appointment)
        self.assertEqual(
            team_form.fields["recipient"].initial,
            f"team:{self.team_b.pk}",
        )


class AppointmentViewTests(AppointmentTestBase):
    def test_team_member_can_read_team_appointment(self):
        self.client.force_login(self.carol)
        response = self.client.get(self.detail_url(self.team_appointment))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Team B")
        self.assertContains(response, "Besvar aftale")

    def test_outsider_cannot_read_team_appointment(self):
        self.client.force_login(self.dave)
        response = self.client.get(self.detail_url(self.team_appointment))
        self.assertEqual(response.status_code, 404)

    def test_teammate_can_read_shared_but_not_personal(self):
        self.client.force_login(self.eve)
        self.assertEqual(
            self.client.get(self.detail_url(self.shared)).status_code, 200
        )
        self.assertEqual(
            self.client.get(self.detail_url(self.personal)).status_code, 404
        )

    def test_any_team_member_can_answer_and_is_recorded(self):
        self.client.force_login(self.carol)
        response = self.client.post(
            reverse(
                "appointment_status_update",
                args=[self.team_appointment.pk, "accepted"],
            )
        )
        self.assertEqual(response.status_code, 302)

        self.team_appointment.refresh_from_db()
        self.assertEqual(self.team_appointment.status, "accepted")
        self.assertEqual(self.team_appointment.resolved_by, self.carol)

    def test_unrelated_user_cannot_answer(self):
        self.client.force_login(self.dave)
        response = self.client.post(
            reverse(
                "appointment_status_update",
                args=[self.team_appointment.pk, "accepted"],
            )
        )
        self.assertEqual(response.status_code, 404)
        self.team_appointment.refresh_from_db()
        self.assertEqual(self.team_appointment.status, "pending")

    def test_list_shows_personal_shared_and_team_appointments(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("organization_VolunteerAppointment_list"))
        appointment_ids = {a.pk for a in response.context["object_list"]}
        self.assertEqual(
            appointment_ids,
            {self.personal.pk, self.shared.pk, self.team_appointment.pk},
        )

        self.client.force_login(self.carol)
        response = self.client.get(reverse("organization_VolunteerAppointment_list"))
        appointment_ids = {a.pk for a in response.context["object_list"]}
        self.assertEqual(appointment_ids, {self.team_appointment.pk})

        self.client.force_login(self.eve)
        response = self.client.get(reverse("organization_VolunteerAppointment_list"))
        appointment_ids = {a.pk for a in response.context["object_list"]}
        self.assertEqual(appointment_ids, {self.shared.pk})

        self.client.force_login(self.dave)
        response = self.client.get(reverse("organization_VolunteerAppointment_list"))
        self.assertEqual(list(response.context["object_list"]), [])

    def test_receiver_cannot_edit_or_delete(self):
        self.client.force_login(self.bob)
        self.assertEqual(
            self.client.get(
                reverse(
                    "organization_VolunteerAppointment_update",
                    args=[self.personal.pk],
                )
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "organization_VolunteerAppointment_delete",
                    args=[self.personal.pk],
                )
            ).status_code,
            404,
        )
        self.assertTrue(
            VolunteerAppointment.objects.filter(pk=self.personal.pk).exists()
        )

    def test_requester_can_edit(self):
        self.client.force_login(self.alice)
        response = self.client.get(
            reverse(
                "organization_VolunteerAppointment_update", args=[self.personal.pk]
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_shared_teammate_can_comment(self):
        self.client.force_login(self.eve)
        response = self.client.post(
            reverse("appointment_comment_add", args=[self.shared.pk]),
            {"comment": "Skal vi mødes i hallen?"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            XtdComment.objects.filter(
                object_pk=str(self.shared.pk), comment__contains="hallen"
            ).exists()
        )

    def test_outsider_cannot_comment(self):
        self.client.force_login(self.dave)
        response = self.client.post(
            reverse("appointment_comment_add", args=[self.team_appointment.pk]),
            {"comment": "Jeg vil gerne med"},
        )
        self.assertEqual(response.status_code, 404)

    def test_dashboard_shows_team_appointment_for_team_member(self):
        self.client.force_login(self.carol)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        titles = [
            booking["title"]
            for booking in response.context["bookings"]
            if booking["type"] == "Legeaftale"
        ]
        self.assertIn("Alice Test → Team B (team)", titles)

        self.client.force_login(self.dave)
        response = self.client.get(reverse("index"))
        self.assertEqual(
            [
                booking
                for booking in response.context["bookings"]
                if booking["type"] == "Legeaftale"
            ],
            [],
        )
