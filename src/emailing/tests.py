import json
from unittest import mock

from botocore.exceptions import ClientError
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import EmailMessageLog, EmailSuppression
from .services import html_to_text, send_email

Status = EmailMessageLog.Status
TEMPLATE = 'emailing/password_reset.html'
CTX = {'user': mock.Mock(email='a@example.com'), 'reset_url': 'https://x.test/reset/'}


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SITE_URL='https://booking.test',
)
class SendEmailTests(TestCase):
    def test_sends_branded_html_and_logs(self):
        with self.captureOnCommitCallbacks(execute=True):
            send_email('Hej', TEMPLATE, CTX, ['a@example.com'])
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('#003255', html)
        self.assertIn('https://x.test/reset/', mail.outbox[0].body)
        log = EmailMessageLog.objects.get()
        self.assertEqual(log.status, Status.SENT)
        self.assertEqual(log.attempts, 1)
        self.assertEqual((log.body_html, log.body_text, log.attachments), ('', '', []))

    def test_suppressed_recipient_is_not_sent(self):
        EmailSuppression.objects.create(email='a@example.com', reason='bounce')
        with self.captureOnCommitCallbacks(execute=True):
            send_email('Hej', TEMPLATE, CTX, ['A@Example.com'])
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(EmailMessageLog.objects.get().status, Status.SUPPRESSED)
        self.assertEqual(EmailMessageLog.objects.get().body_html, '')

    def test_attachment_survives_queue(self):
        with self.captureOnCommitCallbacks(execute=True):
            send_email('Hej', TEMPLATE, CTX, ['a@example.com'], attachments=[
                {'filename': 'e.ics', 'mimetype': 'text/calendar', 'content': b'BEGIN:VCALENDAR'},
            ])
        name, content, mimetype = mail.outbox[0].attachments[0]
        self.assertEqual((name, mimetype), ('e.ics', 'text/calendar'))
        self.assertIn(b'BEGIN:VCALENDAR', content if isinstance(content, bytes) else content.encode())

    def test_permanent_error_marks_failed_without_retry(self):
        err = ClientError({'Error': {'Code': 'MessageRejected', 'Message': 'no'}}, 'SendRawEmail')
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=err):
            with self.captureOnCommitCallbacks(execute=True):
                send_email('Hej', TEMPLATE, CTX, ['a@example.com'])
        log = EmailMessageLog.objects.get()
        self.assertEqual(log.status, Status.FAILED)
        self.assertEqual(log.attempts, 1)
        self.assertIn('https://x.test/reset/', log.body_text)

    def test_cleanup_wipes_old_failed_bodies_and_deletes_old_rows(self):
        from datetime import timedelta
        from django.core.management import call_command
        from django.utils import timezone

        def make(days):
            log = EmailMessageLog.objects.create(
                recipient='a@example.com', subject='s', body_html='h', body_text='t',
                status=Status.FAILED,
            )
            EmailMessageLog.objects.filter(pk=log.pk).update(
                created_at=timezone.now() - timedelta(days=days)
            )
            return log.pk

        fresh, old, ancient = make(1), make(8), make(100)
        call_command('cleanup_email_logs')
        self.assertEqual(EmailMessageLog.objects.get(pk=fresh).body_html, 'h')
        self.assertEqual(EmailMessageLog.objects.get(pk=old).body_html, '')
        self.assertFalse(EmailMessageLog.objects.filter(pk=ancient).exists())
    def test_transient_error_is_retried(self):
        err = ClientError({'Error': {'Code': 'Throttling', 'Message': 'slow'}}, 'SendRawEmail')
        calls = {'n': 0}

        def flaky(self_, fail_silently=False):
            calls['n'] += 1
            if calls['n'] == 1:
                raise err
            self_.extra_headers['message_id'] = 'ses-123'
            return 1

        with mock.patch('django.core.mail.EmailMultiAlternatives.send', flaky):
            with self.captureOnCommitCallbacks(execute=True):
                send_email('Hej', TEMPLATE, CTX, ['a@example.com'])
        log = EmailMessageLog.objects.get()
        self.assertEqual(calls['n'], 2)
        self.assertEqual(log.status, Status.SENT)
        self.assertEqual(log.ses_message_id, 'ses-123')

    def test_html_to_text_keeps_links_and_drops_style(self):
        text = html_to_text('<head><style>a{}</style></head><p>Hej <a href="https://x.test">her</a></p>')
        self.assertEqual(text, 'Hej her (https://x.test)')


@override_settings(AWS_SES_VERIFY_EVENT_SIGNATURES=False)
class WebhookTests(TestCase):
    def setUp(self):
        self.log = EmailMessageLog.objects.create(
            recipient='a@example.com', subject='s', body_html='h', body_text='t',
            status=Status.SENT, ses_message_id='m1',
        )

    def post(self, message):
        body = {'Type': 'Notification', 'Message': json.dumps(message)}
        return self.client.post(
            reverse('ses_notifications'), json.dumps(body), content_type='text/plain',
        )

    def test_delivery_updates_log_once(self):
        event = {'eventType': 'Delivery', 'mail': {'messageId': 'm1'},
                 'delivery': {'recipients': ['a@example.com']}}
        self.assertEqual(self.post(event).status_code, 200)
        self.assertEqual(self.post(event).status_code, 200)
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, Status.DELIVERED)

    def test_permanent_bounce_suppresses_and_is_not_overwritten_by_delivery(self):
        bounce = {'eventType': 'Bounce', 'mail': {'messageId': 'm1'}, 'bounce': {
            'bounceType': 'Permanent',
            'bouncedRecipients': [{'emailAddress': 'A@example.com', 'diagnosticCode': 'no such user'}],
        }}
        self.post(bounce)
        self.post({'eventType': 'Delivery', 'mail': {'messageId': 'm1'},
                   'delivery': {'recipients': ['a@example.com']}})
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, Status.BOUNCED)
        self.assertTrue(EmailSuppression.is_suppressed('a@example.com'))

    def test_transient_bounce_does_not_suppress(self):
        self.post({'eventType': 'Bounce', 'mail': {'messageId': 'm1'}, 'bounce': {
            'bounceType': 'Transient', 'bouncedRecipients': [{'emailAddress': 'a@example.com'}],
        }})
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, Status.SENT)
        self.assertFalse(EmailSuppression.is_suppressed('a@example.com'))

    def test_complaint_suppresses(self):
        self.post({'eventType': 'Complaint', 'mail': {'messageId': 'm1'}, 'complaint': {
            'complainedRecipients': [{'emailAddress': 'a@example.com'}],
        }})
        self.log.refresh_from_db()
        self.assertEqual(self.log.status, Status.COMPLAINED)
        self.assertTrue(EmailSuppression.is_suppressed('a@example.com'))

    def test_unverified_signature_is_rejected(self):
        with override_settings(AWS_SES_VERIFY_EVENT_SIGNATURES=True):
            response = self.client.post(
                reverse('ses_notifications'),
                json.dumps({'Type': 'Notification', 'Message': '{}'}),
                content_type='text/plain',
            )
        self.assertEqual(response.status_code, 400)
