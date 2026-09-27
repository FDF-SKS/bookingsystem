from collections.abc import Iterable

from django.conf import settings

from .models import EmailLog
from .tasks import send_email_logs


def _normalize_attachments(attachments):
    normalized = []
    for attachment in attachments or []:
        content = attachment.get("content", "")
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        normalized.append(
            {
                "filename": attachment.get("filename", "attachment.txt"),
                "content": content,
                "mimetype": attachment.get("mimetype", "application/octet-stream"),
            }
        )
    return normalized


def queue_bulk_emails(messages: Iterable[dict]) -> int:
    logs = []
    for message in messages:
        recipient = message.get("recipient")
        if not recipient:
            continue
        logs.append(
            EmailLog(
                recipient=recipient,
                subject=message.get("subject", ""),
                body=message.get("body", ""),
                html_body=message.get("html_body", ""),
                from_email=message.get("from_email", settings.DEFAULT_FROM_EMAIL),
                attachments=_normalize_attachments(message.get("attachments")),
            )
        )

    if not logs:
        return 0

    created_logs = EmailLog.objects.bulk_create(logs)
    send_email_logs.delay([email_log.id for email_log in created_logs])
    return len(created_logs)
