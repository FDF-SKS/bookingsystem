from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from organization.admin import VolunteerAdmin
from organization.email_service import queue_bulk_emails
from organization.models import EmailLog, Volunteer
from organization.tasks import send_email_logs


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

        result = send_email_logs.run([email_log.id])
        email_log.refresh_from_db()

        self.assertEqual(result, 1)
        self.assertEqual(email_log.status, EmailLog.STATUS_SENT)
        self.assertEqual(email_log.attempts, 1)
        connection.open.assert_called_once()
        connection.close.assert_called_once()
        self.assertEqual(connection.send_messages.call_count, 1)


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
