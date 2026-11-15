"""Models for device push subscriptions and calendar feeds.

The app stores the browser/OS push endpoints a volunteer has registered, their
per-category notification preferences, and the secret token used by calendar
apps to fetch an iCalendar feed without an interactive login.
"""
import uuid

from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """A single Web Push endpoint for one user's browser or installed PWA."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    failure_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Push-abonnement'
        verbose_name_plural = 'Push-abonnementer'
        ordering = ['-created']

    def __str__(self):
        return f'{self.user} · {self.endpoint[:60]}'

    @property
    def subscription_info(self) -> dict:
        """Return the dict shape expected by ``pywebpush``."""
        return {
            'endpoint': self.endpoint,
            'keys': {'p256dh': self.p256dh, 'auth': self.auth},
        }


class NotificationPreference(models.Model):
    """Which push notification categories a user wants to receive."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference',
    )
    notify_bookings = models.BooleanField(
        default=True,
        verbose_name='Bookinger godkendt eller afvist',
    )
    notify_tasks = models.BooleanField(
        default=True,
        verbose_name='Nye opgaver',
    )
    notify_upcoming = models.BooleanField(
        default=True,
        verbose_name='Opgaver og programpunkter der starter snart',
    )
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Notifikationsindstilling'
        verbose_name_plural = 'Notifikationsindstillinger'

    def __str__(self):
        return f'Notifikationer for {self.user}'


class CalendarFeedToken(models.Model):
    """Secret token that lets a device calendar subscribe to a user's feed.

    Calendar apps cannot log in interactively, so the feed URL carries this
    unguessable token instead. Rotating the token invalidates old URLs.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calendar_feed_token',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Kalenderabonnement'
        verbose_name_plural = 'Kalenderabonnementer'

    def __str__(self):
        return f'Kalenderfeed for {self.user}'

    def rotate(self) -> None:
        """Issue a new token, which invalidates every previously shared URL."""
        self.token = uuid.uuid4()
        self.save(update_fields=['token', 'last_updated'])


class SentReminder(models.Model):
    """Deduplication key for scheduled reminders.

    Celery beat runs the reminder task repeatedly; this table guarantees that a
    given program block or task is only announced once.
    """

    key = models.CharField(max_length=200, unique=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Afsendt påmindelse'
        verbose_name_plural = 'Afsendte påmindelser'
        ordering = ['-created']

    def __str__(self):
        return self.key
