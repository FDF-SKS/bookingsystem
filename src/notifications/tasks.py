"""Celery tasks for push delivery and scheduled reminders."""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import SentReminder
from .push import push_is_configured

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def send_push_to_users_task(user_ids, payload: dict) -> int:
    from .push import send_to_users

    return send_to_users(user_ids, payload)


def _claim_reminder(key: str) -> bool:
    """Return True only the first time this reminder key is seen."""
    _, created = SentReminder.objects.get_or_create(key=key)
    return created


@shared_task(ignore_result=True)
def send_upcoming_reminders() -> int:
    """Announce program blocks and tasks that are about to start.

    Scheduled through ``CELERY_BEAT_SCHEDULE`` (every five minutes). Each item
    is announced once, tracked by ``SentReminder``.
    """
    from organization.models import ProgramBlock, TjanseOwnership

    from .services import (
        local_now,
        notify_program_block_upcoming,
        notify_tjanse_due,
    )

    if not push_is_configured():
        # Do not claim reminders that cannot be delivered yet; they will be
        # picked up on the next run once the VAPID keys are configured.
        return 0

    # Keep the deduplication table bounded.
    SentReminder.objects.filter(
        created__lt=timezone.now() - timedelta(days=90)
    ).delete()

    now = local_now()
    lead_minutes = int(getattr(settings, 'NOTIFICATIONS_UPCOMING_MINUTES', 30))
    window_end = now + timedelta(minutes=lead_minutes)
    sent = 0

    # Program blocks on today's date whose start time falls inside the window.
    blocks = (
        ProgramBlock.objects.filter(
            day=now.date(),
            start_time__gt=now.time(),
            start_time__lte=window_end.time(),
        )
        .exclude(category=ProgramBlock.CATEGORY_PLACEHOLDER)
        .select_related('event', 'team')
    )
    for block in blocks:
        key = f'program-block:{block.pk}:{block.day}:{block.start_time}'
        if not _claim_reminder(key):
            continue
        notify_program_block_upcoming(block, lead_minutes)
        sent += 1

    # Tjanser have a due date but no start time, so they are announced once on
    # the morning of the due date.
    reminder_hour = int(getattr(settings, 'NOTIFICATIONS_TASK_REMINDER_HOUR', 8))
    if now.hour >= reminder_hour:
        ownerships = (
            TjanseOwnership.objects.filter(due_date=now.date())
            .exclude(status__in=('done', 'not_done'))
            .select_related('tjanse', 'team', 'event')
        )
        for ownership in ownerships:
            key = f'tjanse-due:{ownership.pk}:{ownership.due_date}'
            if not _claim_reminder(key):
                continue
            notify_tjanse_due(ownership)
            sent += 1

    if sent:
        logger.info('Sendte %s påmindelser.', sent)
    return sent
