import base64
import logging
import random

from botocore.exceptions import BotoCoreError, ClientError
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

from .models import EmailMessageLog, EmailSuppression

logger = logging.getLogger(__name__)

# Bodies can hold reset links or booking details; they live only until the mail is sent.
WIPED = {'body_html': '', 'body_text': '', 'attachments': []}

MAX_RETRIES = 6

# SES error codes worth retrying; anything else (rejected, unverified identity...) is permanent.
TRANSIENT_CODES = {
    'Throttling', 'ThrottlingException', 'TooManyRequestsException', 'Throttled',
    'ServiceUnavailable', 'InternalFailure', 'InternalServerError', 'RequestTimeout',
    'RequestExpired', 'SlowDown',
}


def _is_transient(exc):
    if isinstance(exc, ClientError):
        return exc.response.get('Error', {}).get('Code') in TRANSIENT_CODES
    return isinstance(exc, (BotoCoreError, OSError))


@shared_task(bind=True, max_retries=MAX_RETRIES, acks_late=True)
def deliver_email(self, log_id):
    Status = EmailMessageLog.Status
    try:
        log = EmailMessageLog.objects.get(pk=log_id)
    except EmailMessageLog.DoesNotExist:
        return

    # Only queued/sending rows are claimable; a redelivered task for a sent row is a no-op.
    claimed = EmailMessageLog.objects.filter(
        pk=log_id, status__in=[Status.QUEUED, Status.SENDING],
    ).update(status=Status.SENDING, attempts=log.attempts + 1)
    if not claimed:
        return

    if EmailSuppression.is_suppressed(log.recipient):
        EmailMessageLog.objects.filter(pk=log_id).update(status=Status.SUPPRESSED, **WIPED)
        return

    message = EmailMultiAlternatives(
        subject=log.subject,
        body=log.body_text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[log.recipient],
        connection=get_connection(),
    )
    message.attach_alternative(log.body_html, 'text/html')
    for att in log.attachments:
        message.attach(att['filename'], base64.b64decode(att['content']), att['mimetype'])

    try:
        message.send(fail_silently=False)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        if _is_transient(exc) and self.request.retries < MAX_RETRIES:
            EmailMessageLog.objects.filter(pk=log_id).update(last_error=error)
            countdown = min(30 * 2 ** self.request.retries, 3600) + random.randint(0, 15)
            raise self.retry(exc=exc, countdown=countdown)
        logger.error('Email %s to %s failed: %s', log_id, log.recipient, error)
        EmailMessageLog.objects.filter(pk=log_id).update(status=Status.FAILED, last_error=error)
        return

    # Saved in the same update as the status so webhook events can match immediately.
    EmailMessageLog.objects.filter(pk=log_id, status=Status.SENDING).update(
        status=Status.SENT,
        ses_message_id=message.extra_headers.get('message_id', ''),
        sent_at=timezone.now(),
        last_error='',
        **WIPED,
    )
