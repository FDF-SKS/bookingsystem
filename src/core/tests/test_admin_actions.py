"""Integration tests for admin actions on the Volunteer changelist."""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organization.models import Event, EventMembership

User = get_user_model()


class VolunteerAdminActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="admin-user",
            email="admin@example.com",
            password="pw-12345-xyz",
            first_name="Admin",
            last_name="User",
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.url = reverse("admin:organization_volunteer_changelist")

    def run_action(self, action, volunteers):
        return self.client.post(
            self.url,
            {
                "action": action,
                "_selected_action": [str(v.pk) for v in volunteers],
            },
            follow=True,
        )

    def make_volunteer(self, username, email=None):
        return User.objects.create_user(
            username=username,
            email=email or f"{username}@example.com",
            first_name="Vol",
            last_name="Unteer",
            is_active=True,
        )

    def test_deactivate_and_activate(self):
        volunteer = self.make_volunteer("toggle-me")

        self.run_action("deactivate_volunteers", [volunteer])
        volunteer.refresh_from_db()
        self.assertFalse(volunteer.is_active)

        self.run_action("activate_volunteers", [volunteer])
        volunteer.refresh_from_db()
        self.assertTrue(volunteer.is_active)

    def test_assign_to_aktivitetsteam_group(self):
        volunteer = self.make_volunteer("group-me")

        self.run_action("assign_to_aktivitetsteam_group", [volunteer])

        self.assertTrue(
            volunteer.groups.filter(name="AktivitetsTeamBookingTildeling").exists()
        )

    @mock.patch("organization.admin.send_email")
    def test_send_welcome_email_action(self, send_email):
        send_email.return_value = [object()]
        volunteer = self.make_volunteer("mail-me")

        self.run_action("send_email_action", [volunteer])

        send_email.assert_called_once()
        recipients = send_email.call_args.args[3]
        self.assertEqual(recipients, [volunteer.email])

    def test_create_event_membership_action(self):
        volunteer = self.make_volunteer("event-me")
        day = date.today() + timedelta(days=7)
        event = Event.objects.create(
            name="Upcoming",
            start_date=day,
            end_date=day,
            deadline_sjak=day,
            deadline_teknik=day,
            deadline_mad=day,
            deadline_aktivitetsteam=day,
            deadline_foto=day,
            deadline_lokaler=day,
            deadline_sos=day,
        )

        self.run_action("create_event_membership", [volunteer])

        self.assertTrue(
            EventMembership.objects.filter(volunteer=volunteer, event=event).exists()
        )
