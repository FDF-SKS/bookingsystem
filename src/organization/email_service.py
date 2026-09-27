from collections.abc import Iterable
import base64

from django.conf import settings

from .models import EmailLog
from .tasks import send_email_logs


def _normalize_attachments(attachments):
    normalized = []
    for attachment in attachments or []:
        content = attachment.get("content", "")
        if isinstance(content, bytes):
            content = base64.b64encode(content).decode("ascii")
        normalized.append(
            {
                "filename": attachment.get("filename", "attachment.txt"),
                "content": content,
                "mimetype": attachment.get("mimetype", "application/octet-stream"),
                "is_base64": isinstance(attachment.get("content", ""), bytes),
            }
        )
    return normalized


def queue_bulk_emails(messages: Iterable[dict]) -> int:
    created_logs = []
    for message in messages:
        recipient = message.get("recipient")
        if not recipient:
            continue
        created_logs.append(
            EmailLog.objects.create(
                recipient=recipient,
                subject=message.get("subject", ""),
                body=message.get("body", ""),
                html_body=message.get("html_body", ""),
                from_email=message.get("from_email", settings.DEFAULT_FROM_EMAIL),
                attachments=_normalize_attachments(message.get("attachments")),
            )
        )

    if not created_logs:
        return 0

    send_email_logs.delay([email_log.id for email_log in created_logs])
    return len(created_logs)
