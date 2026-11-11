"""Tests for Discord integration, Celery tasks and model signals in organization."""
from datetime import date
from types import SimpleNamespace
from unittest import mock

from allauth.account.models import EmailAddress
from django.test import SimpleTestCase, TestCase

from . import models
from .discord_services import (
    DEFAULT_COLOR,
    DEFAULT_RETRY_AFTER,
    STATUS_COLORS,
    DiscordRateLimited,
    DiscordTransientError,
    _create_thread,
    _post,
    build_embed,
    send_team_embed,
)
from .tasks import (
    BACKOFF_BASE_SECONDS,
    enqueue_discord_embed,
    notify_booking_change,
    send_discord_embed_task,
)


class RetryRequested(Exception):
    """Raised by the fake task used to capture ``self.retry`` calls."""


class FakeTaskSelf:
    def __init__(self, retries=0):
        self.request = SimpleNamespace(retries=retries)
        self.retried = (None, None)

    def retry(self, exc=None, countdown=None):
        self.retried = (exc, countdown)
        raise RetryRequested


class BuildEmbedTests(SimpleTestCase):
    def test_uses_status_colour_and_includes_fields(self):
        embed = build_embed(
            "Title",
            description="Desc",
            status="Approved",
            url="https://example.test/x",
            fields=[("Team", "A")],
            changed_by="Bob",
        )

        self.assertEqual(embed["color"], STATUS_COLORS["Approved"])
        self.assertEqual(embed["url"], "https://example.test/x")
        names = [field["name"] for field in embed["fields"]]
        self.assertEqual(names[0], "Status")
        self.assertIn("Team", names)
        self.assertEqual(names[-1], "Ændret af")

    def test_defaults_to_grey_without_status(self):
        self.assertEqual(build_embed("Title")["color"], DEFAULT_COLOR)

    def test_truncates_long_values_and_limits_field_count(self):
        embed = build_embed(
            "T" * 300,
            description="D" * 5000,
            fields=[(f"F{i}", "v" * 2000) for i in range(30)],
        )

        self.assertEqual(len(embed["title"]), 256)
        self.assertEqual(len(embed["description"]), 4000)
        self.assertEqual(len(embed["fields"]), 25)
        self.assertEqual(len(embed["fields"][0]["value"]), 1024)


class PostTests(SimpleTestCase):
    @mock.patch("organization.discord_services.requests.post")
    def test_rate_limit_is_translated(self, post):
        post.return_value = mock.Mock(status_code=429)
        post.return_value.json.return_value = {"retry_after": 2.5}

        with self.assertRaises(DiscordRateLimited) as ctx:
            _post("https://discord.test/hook", {}, {})

        self.assertEqual(ctx.exception.retry_after, 2.5)

    @mock.patch("organization.discord_services.requests.post")
    def test_rate_limit_without_retry_after_uses_default(self, post):
        post.return_value = mock.Mock(status_code=429)
        post.return_value.json.side_effect = ValueError

        with self.assertRaises(DiscordRateLimited) as ctx:
            _post("https://discord.test/hook", {}, {})

        self.assertEqual(ctx.exception.retry_after, DEFAULT_RETRY_AFTER)

    @mock.patch("organization.discord_services.requests.post")
    def test_server_error_is_transient(self, post):
        post.return_value = mock.Mock(status_code=503)

        with self.assertRaises(DiscordTransientError):
            _post("https://discord.test/hook", {}, {})

    @mock.patch("organization.discord_services.requests.post")
    def test_success_returns_response(self, post):
        response = mock.Mock(status_code=204)
        post.return_value = response

        self.assertIs(_post("https://discord.test/hook", {}, {}), response)


class SendTeamEmbedTests(TestCase):
    def test_skips_unknown_team_and_team_without_webhook(self):
        team = models.Team.objects.create(name="No hook", short_name="NH")
        self.assertFalse(send_team_embed(team.pk, {"title": "x"}))
        self.assertFalse(send_team_embed(999999, {"title": "x"}))

    @mock.patch("organization.discord_services._post")
    def test_posts_to_existing_thread(self, post):
        team = models.Team.objects.create(
            name="Hooked",
            short_name="H",
            discord_webhook_url="https://discord.com/api/webhooks/hook",
            discord_topic_thread_id="42",
        )
        post.return_value = mock.Mock(status_code=204)

        self.assertTrue(send_team_embed(team.pk, {"title": "x"}, username="Bot"))

        args, _ = post.call_args
        self.assertEqual(args[2], {"thread_id": "42"})
        self.assertEqual(args[1]["username"], "Bot")

    @mock.patch("organization.discord_services._create_thread", return_value=True)
    @mock.patch("organization.discord_services._post")
    def test_recreates_thread_when_missing(self, post, create_thread):
        team = models.Team.objects.create(
            name="Stale",
            short_name="ST",
            discord_webhook_url="https://discord.com/api/webhooks/hook",
            discord_topic_thread_id="42",
        )
        post.return_value = mock.Mock(status_code=404, text="gone")

        self.assertTrue(send_team_embed(team.pk, {"title": "x"}))

        create_thread.assert_called_once()
        team.refresh_from_db()
        self.assertIsNone(team.discord_topic_thread_id)

    @mock.patch("organization.discord_services._post")
    def test_create_thread_stores_channel_id(self, post):
        team = models.Team.objects.create(
            name="New thread",
            short_name="NT",
            discord_webhook_url="https://discord.test/hook",
        )
        response = mock.Mock(status_code=200)
        response.json.return_value = {"channel_id": 987}
        post.return_value = response

        self.assertTrue(
            _create_thread(team.pk, team.discord_webhook_url, {"embeds": []})
        )

        team.refresh_from_db()
        self.assertEqual(team.discord_topic_thread_id, "987")


class EnqueueTests(TestCase):
    def test_none_team_is_noop(self):
        with mock.patch("organization.tasks.send_discord_embed_task.delay") as delay:
            enqueue_discord_embed(None, {"x": 1})
        delay.assert_not_called()

    def test_schedules_after_commit(self):
        with (
            mock.patch("organization.tasks.send_discord_embed_task.delay") as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            enqueue_discord_embed(5, {"x": 1}, "Bot")

        delay.assert_called_once_with(5, {"x": 1}, "Bot")


class NotifyBookingChangeTests(TestCase):
    def make_booking(self, team):
        return SimpleNamespace(
            team=team,
            team_contact=None,
            item=SimpleNamespace(name="Item"),
            remarks="",
            status="Pending",
            pk=1,
        )

    def test_skips_when_team_has_no_webhook(self):
        team = models.Team.objects.create(name="T", short_name="T")
        with mock.patch("organization.tasks.enqueue_discord_embed") as enqueue:
            notify_booking_change(self.make_booking(team), True, "Sjak", "Bot", "sjak")
        enqueue.assert_not_called()

    def test_enqueues_when_webhook_is_configured(self):
        team = models.Team.objects.create(
            name="T", short_name="T", discord_webhook_url="https://discord.test/hook"
        )
        with mock.patch("organization.tasks.enqueue_discord_embed") as enqueue:
            notify_booking_change(self.make_booking(team), True, "Sjak", "Bot", "sjak")

        enqueue.assert_called_once()
        team_id, embed, username = enqueue.call_args.args
        self.assertEqual(team_id, team.pk)
        self.assertEqual(username, "Bot")
        self.assertIn("Ny booking", embed["title"])


class DiscordTaskTests(TestCase):
    @mock.patch("organization.tasks.send_team_embed")
    def test_successful_send(self, send_team_embed):
        result = send_discord_embed_task.apply(args=[1, {"title": "x"}, "Bot"])

        self.assertEqual(result.state, "SUCCESS")
        send_team_embed.assert_called_once_with(1, {"title": "x"}, "Bot")

    @mock.patch("organization.tasks.send_team_embed", side_effect=DiscordRateLimited(7))
    def test_rate_limit_requests_retry(self, send_team_embed):
        fake = FakeTaskSelf()

        with self.assertRaises(RetryRequested):
            send_discord_embed_task.run.__func__(fake, 1, {})

        self.assertIsInstance(fake.retried[0], DiscordRateLimited)
        self.assertEqual(fake.retried[1], 7)

    @mock.patch(
        "organization.tasks.send_team_embed",
        side_effect=DiscordTransientError("boom"),
    )
    def test_transient_error_uses_exponential_backoff(self, send_team_embed):
        fake = FakeTaskSelf(retries=0)

        with self.assertRaises(RetryRequested):
            send_discord_embed_task.run.__func__(fake, 1, {})

        self.assertIsInstance(fake.retried[0], DiscordTransientError)
        self.assertEqual(fake.retried[1], BACKOFF_BASE_SECONDS)


class EmailSyncSignalTests(TestCase):
    def test_creates_verified_primary_address(self):
        user = models.Volunteer.objects.create_user(
            username="sync-user",
            email="Sync@Example.com",
            first_name="S",
            last_name="Y",
        )

        address = EmailAddress.objects.get(user=user)
        self.assertEqual(address.email, "sync@example.com")
        self.assertTrue(address.primary)
        self.assertTrue(address.verified)

    def test_skip_flag_prevents_email_address_creation(self):
        user = models.Volunteer(
            username="skip-user", email="skip@example.com", first_name="S", last_name="K"
        )
        user._skip_email_sync = True
        user.save()

        self.assertFalse(EmailAddress.objects.filter(user=user).exists())


class TjanseSignalTests(TestCase):
    def setUp(self):
        day = date(2026, 1, 1)
        self.event = models.Event.objects.create(
            name="Event",
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
        self.team = models.Team.objects.create(name="Team", short_name="T")
        self.volunteer = models.Volunteer.objects.create_user(
            username="team-member",
            email="member@example.com",
            first_name="Team",
            last_name="Member",
        )
        models.TeamMembership.objects.create(team=self.team, member=self.volunteer)
        self.tjanse = models.Tjanse.objects.create(title="Opvask")

    def make_ownership(self, team=None):
        return models.TjanseOwnership.objects.create(
            tjanse=self.tjanse,
            event=self.event,
            team=team or self.team,
            due_date=date(2026, 1, 1),
        )

    @mock.patch("organization.signals.send_email")
    def test_assignment_emails_team_members(self, send_email):
        self.make_ownership()

        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.args[3], ["member@example.com"])

    @mock.patch("organization.signals.send_email")
    @mock.patch("organization.signals.enqueue_discord_embed")
    def test_discord_enqueued_when_webhook_configured(self, enqueue, send_email):
        self.team.discord_webhook_url = "https://discord.test/hook"
        self.team.save()

        self.make_ownership()

        enqueue.assert_called_once()

    @mock.patch("organization.signals.send_email")
    @mock.patch("organization.signals.enqueue_discord_embed")
    def test_discord_skipped_without_webhook(self, enqueue, send_email):
        self.make_ownership()

        enqueue.assert_not_called()

    @mock.patch("organization.signals.send_email")
    @mock.patch("organization.signals.enqueue_discord_embed")
    def test_swap_request_notifies_both_teams(self, enqueue, send_email):
        ownership = self.make_ownership()
        other_team = models.Team.objects.create(name="Other", short_name="O")
        self.team.discord_webhook_url = "https://discord.test/a"
        self.team.save()
        other_team.discord_webhook_url = "https://discord.test/b"
        other_team.save()
        enqueue.reset_mock()

        models.TjanseSwapRequest.objects.create(
            task_ownership=ownership,
            requesting_team=self.team,
            receiving_team=other_team,
        )

        self.assertEqual(enqueue.call_count, 2)

    def test_swap_accept_transfers_ownership(self):
        ownership = self.make_ownership()
        receiving_team = models.Team.objects.create(name="Receiver", short_name="R")
        swap = models.TjanseSwapRequest.objects.create(
            task_ownership=ownership,
            requesting_team=self.team,
            receiving_team=receiving_team,
        )

        swap.accept()

        ownership.refresh_from_db()
        swap.refresh_from_db()
        self.assertEqual(ownership.team_id, receiving_team.pk)
        self.assertEqual(swap.status, "accepted")

    def test_swap_reject_keeps_ownership(self):
        ownership = self.make_ownership()
        receiving_team = models.Team.objects.create(name="Receiver", short_name="R")
        swap = models.TjanseSwapRequest.objects.create(
            task_ownership=ownership,
            requesting_team=self.team,
            receiving_team=receiving_team,
        )

        swap.reject()

        ownership.refresh_from_db()
        swap.refresh_from_db()
        self.assertEqual(ownership.team_id, self.team.pk)
        self.assertEqual(swap.status, "rejected")
