"""Tests for the iCalendar export helpers in ``utils.ical_utils``."""
from datetime import date, time
from unittest import mock

from django.test import TestCase

from utils.ical_utils import (
    convert_to_ical,
    export_selected_to_ical,
    send_ical_via_email,
)


class FakeContact:
    def __init__(self, name="Kontakt Person", phone="12345678"):
        self._name = name
        self.phone = phone

    def __str__(self):
        return self._name


class FakeAssignedTeam:
    def __init__(self, volunteers):
        self._volunteers = volunteers

    def exists(self):
        return bool(self._volunteers)

    def all(self):
        return self._volunteers


class FakeVolunteer:
    def __init__(self, email="volunteer@example.com", first_name="Vol", last_name="Unteer"):
        self.email = email
        self.first_name = first_name
        self.last_name = last_name


class FakeBooking:
    def __init__(self, **overrides):
        self.id = overrides.get("id", 1)
        self.item = overrides.get("item", "Test Item")
        self.team = overrides.get("team", "Test Team")
        self.team_contact = overrides.get("team_contact", FakeContact())
        self.start_date = overrides.get("start_date", date(2026, 1, 1))
        self.start_time = overrides.get("start_time", time(10, 0))
        self.end_date = overrides.get("end_date", date(2026, 1, 1))
        self.end_time = overrides.get("end_time", time(12, 0))
        self.quantity = overrides.get("quantity", 3)
        self.remarks = overrides.get("remarks", "Husk trailer")
        if "assigned_aktivitetsteam" in overrides:
            self.assigned_aktivitetsteam = overrides["assigned_aktivitetsteam"]

    def __str__(self):
        return self.item


class ConvertToICalTests(TestCase):
    def test_event_contains_summary_times_and_details(self):
        ics = convert_to_ical(FakeBooking()).to_ical().decode()

        self.assertIn("SUMMARY:", ics)
        self.assertIn("Test Item", ics)
        self.assertIn("20260101T100000", ics)
        self.assertIn("20260101T120000", ics)
        self.assertIn("Kontaktperson: Kontakt Person", ics)
        self.assertIn("Telefon: 12345678", ics)
        self.assertIn("Antal: 3", ics)
        self.assertIn("Husk trailer", ics)

    def test_event_has_one_hour_display_alarm(self):
        ics = convert_to_ical(FakeBooking()).to_ical().decode()

        self.assertIn("BEGIN:VALARM", ics)
        self.assertIn("ACTION:DISPLAY", ics)
        self.assertIn("TRIGGER:-PT1H", ics)

    def test_attendees_are_added_from_assigned_team(self):
        booking = FakeBooking(
            assigned_aktivitetsteam=FakeAssignedTeam([FakeVolunteer()])
        )
        ics = convert_to_ical(booking).to_ical().decode()

        self.assertIn("ATTENDEE", ics)
        self.assertIn("mailto:volunteer@example.com", ics.lower())


class ExportTests(TestCase):
    def test_export_selected_returns_valid_calendar(self):
        content = export_selected_to_ical([FakeBooking(id=1), FakeBooking(id=2)])

        self.assertIsInstance(content, bytes)
        ics = content.decode()
        self.assertIn("BEGIN:VCALENDAR", ics)
        self.assertEqual(ics.count("BEGIN:VEVENT"), 2)


class SendViaEmailTests(TestCase):
    @mock.patch("utils.ical_utils.send_email")
    def test_sends_one_email_per_assigned_volunteer_with_ics_attachment(self, send_email):
        volunteer = FakeVolunteer()
        booking = FakeBooking(assigned_aktivitetsteam=FakeAssignedTeam([volunteer]))

        send_ical_via_email([booking], "AktivitetsTeam/ical_email_template.html", "from@example.com")

        send_email.assert_called_once()
        args, kwargs = send_email.call_args
        self.assertEqual(args[3], [volunteer.email])
        attachment = kwargs["attachments"][0]
        self.assertEqual(attachment["filename"], f"booking_{booking.id}.ics")
        self.assertEqual(attachment["mimetype"], "text/calendar")
        self.assertIn(b"BEGIN:VCALENDAR", attachment["content"])
