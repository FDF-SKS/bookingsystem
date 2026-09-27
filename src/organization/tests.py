from unittest.mock import MagicMock, patch
from smtplib import SMTPException
from datetime import date, time

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from AktivitetsTeam.admin import AktivitetsTeamBookingAdmin
from AktivitetsTeam.models import AktivitetsTeamBooking, AktivitetsTeamItem
from organization.admin import EmailLogAdmin, VolunteerAdmin
from organization.email_service import queue_bulk_emails
from organization.models import EmailLog, Team, TeamMembership, Volunteer
from organization.tasks import MAX_EMAIL_RETRIES, send_email_logs


class EmailQueueTests(TestCase):
    @patch("organization.email_service.send_email_logs.delay")
    def test_queue_bulk_emails_creates_logs_and_enqueues_task(self, mock_delay):
        queued = queue_bulk_emails(
            [
                {
                    "recipient": "volunteer@example.com",
                    "subject": "Test subject",
                    "body": "Plain text",
                    "html_body": "<p>HTML</p>",
                }
            ]
        )

        self.assertEqual(queued, 1)
        email_log = EmailLog.objects.get()
        self.assertEqual(email_log.status, EmailLog.STATUS_PENDING)
        mock_delay.assert_called_once_with([email_log.id])

    @patch("organization.tasks.get_connection")
    def test_send_email_logs_marks_log_sent_with_single_connection(self, mock_get_connection):
        email_log = EmailLog.objects.create(
            recipient="volunteer@example.com",
            subject="Test subject",
            body="Body",
            from_email="noreply@example.com",
        )

        connection = MagicMock()
        connection.send_messages.return_value = 1
        mock_get_connection.return_value = connection

        result = send_email_logs._orig_run([email_log.id])
        email_log.refresh_from_db()

        self.assertEqual(result, 1)
        self.assertEqual(email_log.status, EmailLog.STATUS_SENT)
        self.assertEqual(email_log.attempts, 1)
        connection.open.assert_called_once()
        connection.close.assert_called_once()
        self.assertEqual(connection.send_messages.call_count, 1)

    @patch("organization.tasks.get_connection")
    def test_send_email_logs_marks_pending_then_failed_on_retry_limit(self, mock_get_connection):
        email_log = EmailLog.objects.create(
            recipient="volunteer@example.com",
            subject="Test subject",
            body="Body",
            from_email="noreply@example.com",
        )

        connection = MagicMock()
        connection.send_messages.side_effect = SMTPException("Temporary SMTP error")
        mock_get_connection.return_value = connection

        with self.assertRaises(SMTPException):
            send_email_logs._orig_run([email_log.id])
        email_log.refresh_from_db()
        self.assertEqual(email_log.status, EmailLog.STATUS_PENDING)

        email_log.attempts = MAX_EMAIL_RETRIES - 1
        email_log.save(update_fields=["attempts"])
        send_email_logs._orig_run([email_log.id])
        email_log.refresh_from_db()
        self.assertEqual(email_log.status, EmailLog.STATUS_FAILED)

    @patch("organization.tasks.send_email_logs.retry")
    @patch("organization.tasks.get_connection")
    def test_send_email_logs_handles_partial_delivery(self, mock_get_connection, mock_retry):
        first = EmailLog.objects.create(
            recipient="first@example.com",
            subject="First",
            body="Body",
            from_email="noreply@example.com",
        )
        second = EmailLog.objects.create(
            recipient="second@example.com",
            subject="Second",
            body="Body",
            from_email="noreply@example.com",
        )

        connection = MagicMock()
        connection.send_messages.side_effect = [1, 0]
        mock_get_connection.return_value = connection
        mock_retry.side_effect = SMTPException("retry scheduled")

        with self.assertRaises(SMTPException):
            send_email_logs.run([first.id, second.id])

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, EmailLog.STATUS_SENT)
        self.assertEqual(second.status, EmailLog.STATUS_PENDING)


class VolunteerAdminActionTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = VolunteerAdmin(Volunteer, self.site)
        self.factory = RequestFactory()
        self.user = Volunteer.objects.create_user(
            username="testvolunteer",
            email="test@example.com",
            first_name="Test",
            last_name="Volunteer",
        )

    def _build_request(self):
        request = self.factory.post("/admin/organization/volunteer/")
        request.user = self.user
        setattr(request, "session", self.client.session)
        setattr(request, "_messages", FallbackStorage(request))
        return request

    @patch("organization.admin.queue_bulk_emails")
    def test_send_email_action_queues_messages(self, mock_queue_bulk_emails):
        mock_queue_bulk_emails.return_value = 1

        request = self._build_request()
        queryset = Volunteer.objects.filter(pk=self.user.pk)
        self.admin.send_email_action(request, queryset)

        mock_queue_bulk_emails.assert_called_once()

    @patch("organization.admin.send_email_logs.delay")
    def test_email_log_resend_action_only_requeues_failed_logs(self, mock_delay):
        failed_log = EmailLog.objects.create(
            recipient="failed@example.com",
            subject="Failed",
            status=EmailLog.STATUS_FAILED,
            attempts=2,
            error_message="smtp",
        )
        sent_log = EmailLog.objects.create(
            recipient="sent@example.com",
            subject="Sent",
            status=EmailLog.STATUS_SENT,
            attempts=1,
        )

        email_log_admin = EmailLogAdmin(EmailLog, self.site)
        request = self._build_request()
        email_log_admin.resend_failed_emails(request, EmailLog.objects.filter(id__in=[failed_log.id, sent_log.id]))

        failed_log.refresh_from_db()
        sent_log.refresh_from_db()
        self.assertEqual(failed_log.status, EmailLog.STATUS_PENDING)
        self.assertEqual(failed_log.attempts, 0)
        self.assertEqual(sent_log.status, EmailLog.STATUS_SENT)
        mock_delay.assert_called_once_with([failed_log.id])


class DailyRoleUpdateTests(TestCase):
    @patch("organization.email_service.queue_bulk_emails")
    @patch("organization.tasks._get_recent_booking_updates")
    def test_send_daily_role_updates_skips_when_no_updates(self, mock_updates, mock_queue):
        from organization.tasks import send_daily_role_updates

        mock_updates.return_value = ([], {})
        result = send_daily_role_updates.run()

        self.assertEqual(result, 0)
        mock_queue.assert_not_called()

    @patch("organization.tasks._get_recent_comments_count", return_value=3)
    @patch("organization.email_service.queue_bulk_emails")
    @patch("organization.tasks._get_recent_booking_updates", return_value=([], {}))
    def test_send_daily_role_updates_queues_when_only_comments_exist(
        self, _mock_updates, mock_queue, _mock_comments
    ):
        from organization.tasks import send_daily_role_updates

        admin = Volunteer.objects.create_user(
            username="admin-only-comments",
            email="admin-comments@example.com",
            first_name="Admin",
            last_name="Comments",
            is_superuser=True,
            is_staff=True,
        )
        mock_queue.return_value = 1

        result = send_daily_role_updates.run()
        self.assertEqual(result, 1)
        queued_messages = mock_queue.call_args[0][0]
        self.assertEqual(queued_messages[0]["recipient"], admin.email)

    @patch("organization.tasks._get_recent_comments_count", return_value=2)
    @patch("organization.email_service.queue_bulk_emails")
    @patch("organization.tasks._get_recent_booking_updates")
    def test_send_daily_role_updates_queues_admin_and_instructor_messages(
        self, mock_updates, mock_queue, _mock_comments
    ):
        from organization.tasks import send_daily_role_updates

        admin = Volunteer.objects.create_user(
            username="admin-user",
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
            is_staff=True,
        )
        instructor = Volunteer.objects.create_user(
            username="instruktor",
            email="instruktor@example.com",
            first_name="Instruktor",
            last_name="User",
        )
        team = Team.objects.create(name="Teknik", short_name="TEK")
        TeamMembership.objects.create(team=team, member=instructor, role="Instruktør")

        mock_updates.return_value = (
            [{"model_name": "Teknikbookings", "count": 1}],
            {team.id: ["Teknikbooking #1 (Approved)"]},
        )
        mock_queue.return_value = 2

        result = send_daily_role_updates.run()
        self.assertEqual(result, 2)

        queued_messages = mock_queue.call_args[0][0]
        recipients = {message["recipient"] for message in queued_messages}
        self.assertIn(admin.email, recipients)
        self.assertIn(instructor.email, recipients)


class AktivitetsTeamAdminActionTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = AktivitetsTeamBookingAdmin(AktivitetsTeamBooking, self.site)
        self.factory = RequestFactory()
        self.request_user = Volunteer.objects.create_user(
            username="admin-akt",
            email="admin-akt@example.com",
            first_name="Admin",
            last_name="Akt",
            is_superuser=True,
            is_staff=True,
        )
        self.team = Team.objects.create(name="AktTeam", short_name="AKT")
        self.contact = Volunteer.objects.create_user(
            username="contact-akt",
            email="contact-akt@example.com",
            first_name="Contact",
            last_name="Akt",
        )
        self.assignee = Volunteer.objects.create_user(
            username="assignee-akt",
            email="assignee-akt@example.com",
            first_name="Assignee",
            last_name="Akt",
        )
        self.item = AktivitetsTeamItem.objects.create(
            name="Aktivitet",
            description="Desc",
            short_description="Short",
        )

    def _build_request(self):
        request = self.factory.post("/admin/AktivitetsTeam/aktivitetsteambooking/")
        request.user = self.request_user
        setattr(request, "session", self.client.session)
        setattr(request, "_messages", FallbackStorage(request))
        return request

    @patch("AktivitetsTeam.admin.send_ical_via_email")
    def test_send_ical_action_filters_to_bookings_with_assignees(self, mock_send_ical):
        booking_with_assignee = AktivitetsTeamBooking.objects.create(
            team=self.team,
            item=self.item,
            team_contact=self.contact,
            start_date=date(2026, 1, 1),
            start_time=time(10, 0),
            end_date=date(2026, 1, 1),
            end_time=time(12, 0),
        )
        booking_with_assignee.assigned_aktivitetsteam.add(self.assignee)
        booking_without_assignee = AktivitetsTeamBooking.objects.create(
            team=self.team,
            item=self.item,
            team_contact=self.contact,
            start_date=date(2026, 1, 2),
            start_time=time(10, 0),
            end_date=date(2026, 1, 2),
            end_time=time(12, 0),
        )
        mock_send_ical.return_value = 1

        request = self._build_request()
        queryset = AktivitetsTeamBooking.objects.filter(id__in=[booking_with_assignee.id, booking_without_assignee.id])
        self.admin.send_ical_via_email_action(request, queryset)

        filtered_queryset = mock_send_ical.call_args[0][0]
        self.assertEqual(list(filtered_queryset.values_list("id", flat=True)), [booking_with_assignee.id])
        self.assertTrue(any("1 email(s) sat i kø" in str(message) for message in request._messages))
