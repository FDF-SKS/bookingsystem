"""Tests for push notifications, reminder scheduling and calendar feeds."""
import json
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pywebpush import WebPushException

from organization.models import (
    Event,
    ProgramBlock,
    Team,
    TeamMembership,
    Tjanse,
    TjanseOwnership,
)
from Sjak.models import SjakBooking, SjakItem

from .models import (
    CalendarFeedToken,
    NotificationPreference,
    PushSubscription,
    SentReminder,
)
from .push import send_to_users
from .services import set_booking_status
from .tasks import send_upcoming_reminders

User = get_user_model()

VAPID_SETTINGS = {
    'WEBPUSH_VAPID_PUBLIC_KEY': 'test-public-key',
    'WEBPUSH_VAPID_PRIVATE_KEY': 'test-private-key',
    'WEBPUSH_VAPID_SUBJECT': 'mailto:test@example.com',
    'SITE_URL': 'https://booking.example.test',
}


def tiptap_document(text='Hej'):
    return {
        'doc': {
            'type': 'doc',
            'content': [
                {
                    'type': 'paragraph',
                    'content': [{'type': 'text', 'text': text}],
                }
            ],
        },
        'html': f'<p>{text}</p>',
    }


class NotificationTestBase(TestCase):
    def setUp(self):
        self.day = timezone.localdate()
        self.event = Event.objects.create(
            name='SKS E26',
            start_date=self.day,
            end_date=self.day + timedelta(days=2),
            deadline_sjak=self.day,
            deadline_teknik=self.day,
            deadline_mad=self.day,
            deadline_aktivitetsteam=self.day,
            deadline_foto=self.day,
            deadline_lokaler=self.day,
            deadline_sos=self.day,
        )
        self.alice = User.objects.create_user(
            username='alice', email='alice@example.com', password='test-password'
        )
        self.bob = User.objects.create_user(
            username='bob', email='bob@example.com', password='test-password'
        )
        self.team = Team.objects.create(name='Sjak', short_name='Sjak')
        self.other_team = Team.objects.create(name='Teknik', short_name='Tek')
        TeamMembership.objects.create(team=self.team, member=self.alice)
        TeamMembership.objects.create(team=self.other_team, member=self.bob)

    def create_block(self, **overrides):
        data = {
            'event': self.event,
            'team': None,
            'category': ProgramBlock.CATEGORY_FIXED,
            'title': 'Morgenmad',
            'day': self.day,
            'start_time': time(8, 0),
            'end_time': time(9, 0),
        }
        data.update(overrides)
        return ProgramBlock.objects.create(**data)

    def create_tjanse(self, **overrides):
        title = overrides.pop('title', 'Opvask')
        tjanse = Tjanse.objects.create(title=title)
        data = {
            'tjanse': tjanse,
            'event': self.event,
            'team': self.team,
            'due_date': self.day,
        }
        data.update(overrides)
        return TjanseOwnership.objects.create(**data)


class CalendarFeedTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.token = CalendarFeedToken.objects.create(user=self.alice)

    def feed_url(self, **params):
        url = reverse('notifications_calendar_feed', args=[self.token.token])
        if params:
            query = '&'.join(f'{key}={value}' for key, value in params.items())
            url = f'{url}?{query}'
        return url

    def read_feed(self, **params):
        """Return the feed with RFC 5545 line folding removed."""
        response = self.client.get(self.feed_url(**params))
        return response, response.content.decode().replace('\r\n ', '')

    def test_feed_contains_shared_and_team_blocks(self):
        shared = self.create_block(title='Fælles start', content=tiptap_document('Alle møder op'))
        team_block = self.create_block(title='Sjak-møde', team=self.team)
        foreign = self.create_block(title='Teknik-møde', team=self.other_team)

        response, body = self.read_feed()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/calendar'))
        self.assertIn(shared.title, body)
        self.assertIn(team_block.title, body)
        self.assertNotIn(foreign.title, body)
        self.assertIn(f'UID:program-block-{shared.pk}@', body)
        self.assertIn('Alle møder op', body)
        self.assertIn('REFRESH-INTERVAL', body)

    def test_task_feed_contains_only_team_tasks(self):
        own = self.create_tjanse()
        foreign = self.create_tjanse(team=self.other_team, title='Anden opgave')
        self.create_block(title='Morgenmad')

        _, body = self.read_feed(feed='tasks')

        self.assertIn(f'UID:tjanse-ownership-{own.pk}@', body)
        self.assertIn('Opgave: Opvask', body)
        self.assertNotIn(foreign.tjanse.title, body)
        self.assertNotIn('Morgenmad', body)

    def test_changes_to_a_block_are_reflected_immediately(self):
        block = self.create_block(title='Gammel titel')

        _, first = self.read_feed()
        block.title = 'Ny titel'
        block.save()
        _, second = self.read_feed()

        self.assertIn('Gammel titel', first)
        self.assertNotIn('Gammel titel', second)
        self.assertIn('Ny titel', second)

    def test_unknown_token_returns_404(self):
        url = reverse(
            'notifications_calendar_feed',
            args=['00000000-0000-0000-0000-000000000000'],
        )
        self.assertEqual(self.client.get(url).status_code, 404)


@override_settings(**VAPID_SETTINGS)
class PushApiTests(NotificationTestBase):
    def test_subscribe_requires_login(self):
        response = self.client.post(reverse('notifications_push_subscribe'), {})
        self.assertEqual(response.status_code, 302)

    def test_subscribe_creates_and_updates_subscription(self):
        self.client.force_login(self.alice)
        payload = {
            'endpoint': 'https://push.example.test/abc',
            'keys': {'p256dh': 'p256dh-value', 'auth': 'auth-value'},
        }

        response = self.client.post(
            reverse('notifications_push_subscribe'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PushSubscription.objects.count(), 1)

        payload['keys']['auth'] = 'rotated-auth'
        self.client.post(
            reverse('notifications_push_subscribe'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(PushSubscription.objects.count(), 1)
        self.assertEqual(
            PushSubscription.objects.get().auth,
            'rotated-auth',
        )

    def test_private_or_non_https_endpoints_are_rejected(self):
        self.client.force_login(self.alice)
        for endpoint in (
            'http://push.example.test/abc',
            'https://127.0.0.1/internal',
            'https://localhost/internal',
        ):
            response = self.client.post(
                reverse('notifications_push_subscribe'),
                data=json.dumps(
                    {
                        'endpoint': endpoint,
                        'keys': {'p256dh': 'p256dh-value', 'auth': 'auth-value'},
                    }
                ),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 400, endpoint)
        self.assertFalse(PushSubscription.objects.exists())

    def test_unsubscribe_removes_subscription(self):
        self.client.force_login(self.alice)
        PushSubscription.objects.create(
            user=self.alice,
            endpoint='https://push.example.test/abc',
            p256dh='p256dh-value',
            auth='auth-value',
        )

        response = self.client.post(
            reverse('notifications_push_unsubscribe'),
            data=json.dumps({'endpoint': 'https://push.example.test/abc'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PushSubscription.objects.exists())

    def test_settings_page_shows_personal_feed(self):
        self.client.force_login(self.alice)

        response = self.client.get(reverse('notifications_settings'))

        self.assertEqual(response.status_code, 200)
        token = CalendarFeedToken.objects.get(user=self.alice)
        self.assertContains(response, str(token.token))
        self.assertContains(response, 'Push-notifikationer')

    def test_base_template_exposes_offline_banner_and_user_id(self):
        self.client.force_login(self.alice)

        response = self.client.get(reverse('notifications_settings'))

        self.assertContains(response, 'id="offline-banner"')
        self.assertContains(
            response, f'name="user-id" content="{self.alice.pk}"'
        )
        self.assertContains(response, 'viewport-fit=cover')
        # Bootstrap, icons and Leaflet are self-hosted so Safari can use them
        # from the service-worker cache without CORS/SRI edge cases.
        self.assertContains(response, 'vendor/bootstrap/css/bootstrap.min.css')
        self.assertContains(response, 'vendor/bootstrap-icons/bootstrap-icons.min.css')
        self.assertContains(response, 'vendor/leaflet/leaflet.js')
        self.assertNotContains(response, 'cdn.jsdelivr.net/npm/bootstrap@')

    def test_offline_page_has_last_updated_placeholder(self):
        response = self.client.get(reverse('notifications_offline'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-offline-last-updated')

    def test_service_worker_is_served_from_the_root(self):
        response = self.client.get(reverse('pwa_service_worker'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('application/javascript'))
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        self.assertIn(b'X-Cached-At', response.content)


class NotificationPreferenceTests(NotificationTestBase):
    def test_settings_page_creates_defaults(self):
        self.client.force_login(self.alice)

        response = self.client.get(reverse('notifications_settings'))

        self.assertEqual(response.status_code, 200)
        preference = NotificationPreference.objects.get(user=self.alice)
        self.assertTrue(preference.notify_bookings)
        self.assertTrue(preference.notify_tasks)
        self.assertTrue(preference.notify_upcoming)

    def test_preferences_can_be_turned_off(self):
        self.client.force_login(self.alice)

        response = self.client.post(
            reverse('notifications_update_preferences'),
            {'notify_bookings': '', 'notify_tasks': 'on'},
        )

        self.assertEqual(response.status_code, 302)
        preference = NotificationPreference.objects.get(user=self.alice)
        self.assertFalse(preference.notify_bookings)
        self.assertTrue(preference.notify_tasks)
        self.assertFalse(preference.notify_upcoming)


@override_settings(**VAPID_SETTINGS)
class BookingNotificationTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        self.item = SjakItem.objects.create(name='Telt')
        self.booking = SjakBooking.objects.create(
            team=self.team,
            item=self.item,
            team_contact=self.alice,
            event=self.event,
            start_date=self.day,
            start_time=time(12, 0),
            end_date=self.day,
            end_time=time(14, 0),
            quantity=2,
        )

    def test_approval_pushes_to_team_members(self):
        self.booking.status = 'Approved'

        with (
            patch('notifications.tasks.send_push_to_users_task.delay') as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.booking.save(update_fields=['status'])

        delay.assert_called_once()
        recipients, payload = delay.call_args.args
        self.assertEqual(recipients, [self.alice.pk])
        self.assertIn('godkendt', payload['title'])
        self.assertIn('Telt', payload['body'])
        self.assertEqual(payload['kind'], 'booking')

    def test_rejection_pushes(self):
        self.booking.status = 'Rejected'

        with (
            patch('notifications.tasks.send_push_to_users_task.delay') as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.booking.save(update_fields=['status'])

        self.assertIn('afvist', delay.call_args.args[1]['title'])

    def test_unchanged_status_does_not_push(self):
        self.booking.status = 'Approved'
        with self.captureOnCommitCallbacks(execute=True):
            self.booking.save()

        with (
            patch('notifications.tasks.send_push_to_users_task.delay') as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.booking.remarks = 'Ny bemærkning'
            self.booking.save()

        delay.assert_not_called()

    def test_disabled_preference_suppresses_push(self):
        NotificationPreference.objects.create(
            user=self.alice, notify_bookings=False
        )
        self.booking.status = 'Approved'

        with (
            patch('notifications.tasks.send_push_to_users_task.delay') as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.booking.save(update_fields=['status'])

        delay.assert_not_called()

    def test_bulk_approval_sends_one_grouped_notification(self):
        SjakBooking.objects.create(
            team=self.team,
            item=self.item,
            team_contact=self.alice,
            event=self.event,
            start_date=self.day,
            start_time=time(15, 0),
            end_date=self.day,
            end_time=time(16, 0),
            quantity=1,
        )

        with (
            patch('notifications.tasks.send_push_to_users_task.delay') as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            updated = set_booking_status(
                SjakBooking.objects.filter(team=self.team), 'Approved'
            )

        self.assertEqual(updated, 2)
        delay.assert_called_once()
        recipients, payload = delay.call_args.args
        self.assertEqual(recipients, [self.alice.pk])
        self.assertIn('2 bookinger', payload['title'])


@override_settings(**VAPID_SETTINGS)
class ReminderTests(NotificationTestBase):
    def fixed_now(self, hour=9, minute=0):
        return datetime(
            self.day.year, self.day.month, self.day.day, hour, minute,
            tzinfo=ZoneInfo('Europe/Copenhagen'),
        )

    def test_program_block_reminder_is_sent_once(self):
        now = self.fixed_now()
        block = self.create_block(
            start_time=(now + timedelta(minutes=10)).time(),
            end_time=(now + timedelta(minutes=70)).time(),
            team=self.team,
        )

        with (
            patch('notifications.services.local_now', return_value=now),
            patch('notifications.tasks.send_push_to_users_task.delay') as delay,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                first = send_upcoming_reminders()

            self.assertEqual(first, 1)
            delay.assert_called_once()
            recipients, payload = delay.call_args.args
            self.assertEqual(recipients, [self.alice.pk])
            self.assertIn('Om 30 min', payload['title'])

            with self.captureOnCommitCallbacks(execute=True):
                second = send_upcoming_reminders()

        self.assertEqual(second, 0)
        self.assertEqual(SentReminder.objects.count(), 1)
        self.assertEqual(block.day, self.day)

    def test_placeholder_blocks_are_not_announced(self):
        now = self.fixed_now()
        self.create_block(
            category=ProgramBlock.CATEGORY_PLACEHOLDER,
            start_time=(now + timedelta(minutes=10)).time(),
            end_time=(now + timedelta(minutes=70)).time(),
            team=self.team,
        )

        with (
            patch('notifications.services.local_now', return_value=now),
            patch('notifications.tasks.send_push_to_users_task.delay') as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            sent = send_upcoming_reminders()

        self.assertEqual(sent, 0)
        delay.assert_not_called()

    def test_due_task_is_announced_after_reminder_hour(self):
        ownership = self.create_tjanse()
        now = self.fixed_now(hour=9)

        with (
            patch('notifications.services.local_now', return_value=now),
            patch('notifications.tasks.send_push_to_users_task.delay') as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            sent = send_upcoming_reminders()

        self.assertEqual(sent, 1)
        recipients, payload = delay.call_args.args
        self.assertEqual(recipients, [self.alice.pk])
        self.assertIn('Opgave i dag', payload['title'])
        self.assertIn(ownership.tjanse.title, payload['title'])

    def test_due_task_is_not_announced_before_reminder_hour(self):
        self.create_tjanse()
        now = self.fixed_now(hour=6)

        with (
            patch('notifications.services.local_now', return_value=now),
            patch('notifications.tasks.send_push_to_users_task.delay') as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            sent = send_upcoming_reminders()

        self.assertEqual(sent, 0)
        delay.assert_not_called()


@override_settings(**VAPID_SETTINGS)
class PushTransportTests(NotificationTestBase):
    def make_subscription(self, endpoint='https://push.example.test/abc'):
        return PushSubscription.objects.create(
            user=self.alice,
            endpoint=endpoint,
            p256dh='public-key',
            auth='auth-secret',
        )

    def test_delivery_uses_configured_vapid_claims(self):
        self.make_subscription()

        with patch('notifications.push.webpush') as webpush:
            delivered = send_to_users([self.alice.pk], {'title': 'Hej'})

        self.assertEqual(delivered, 1)
        webpush.assert_called_once()
        kwargs = webpush.call_args.kwargs
        self.assertEqual(kwargs['vapid_private_key'], 'test-private-key')
        self.assertEqual(kwargs['vapid_claims'], {'sub': 'mailto:test@example.com'})
        self.assertEqual(
            kwargs['subscription_info']['endpoint'],
            'https://push.example.test/abc',
        )

    def test_gone_subscription_is_deleted(self):
        subscription = self.make_subscription()
        response = MagicMock(status_code=410)

        with patch(
            'notifications.push.webpush',
            side_effect=WebPushException('gone', response=response),
        ):
            delivered = send_to_users([self.alice.pk], {'title': 'Hej'})

        self.assertEqual(delivered, 0)
        self.assertFalse(
            PushSubscription.objects.filter(pk=subscription.pk).exists()
        )

    def test_transient_failure_keeps_subscription_and_counts_it(self):
        subscription = self.make_subscription()
        response = MagicMock(status_code=500)

        with patch(
            'notifications.push.webpush',
            side_effect=WebPushException('boom', response=response),
        ):
            delivered = send_to_users([self.alice.pk], {'title': 'Hej'})

        self.assertEqual(delivered, 0)
        subscription.refresh_from_db()
        self.assertEqual(subscription.failure_count, 1)

    def test_nothing_is_sent_without_vapid_keys(self):
        self.make_subscription()

        with (
            override_settings(
                WEBPUSH_VAPID_PUBLIC_KEY='', WEBPUSH_VAPID_PRIVATE_KEY=''
            ),
            patch('notifications.push.webpush') as webpush,
        ):
            delivered = send_to_users([self.alice.pk], {'title': 'Hej'})

        self.assertEqual(delivered, 0)
        webpush.assert_not_called()
