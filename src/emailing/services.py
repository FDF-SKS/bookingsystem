import base64
import re

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import EmailMessageLog, EmailSuppression


def html_to_text(html):
    """Plain-text fallback: drops head/style and keeps link targets."""
    html = re.sub(r'(?is)<(head|style|script).*?</\1>', '', html)
    html = re.sub(r'(?is)<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r'\2 (\1)', html)
    html = re.sub(r'(?i)<br\s*/?>|</(p|div|tr|h\d|li)>', '\n', html)
    text = strip_tags(html)
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def send_email(subject, template, context, recipients, attachments=None, *, sensitive=False):
    """Render template once, log one row per recipient, and queue delivery.

    attachments: iterable of {"filename", "mimetype", "content"} with raw bytes/str content.
    sensitive: when True the rendered body (which may contain a reset link or
        one-time code) is handed to the delivery task but never persisted on
        the log row, so secrets do not sit in the database in plaintext.
    Returns the created EmailMessageLog rows.
    """
    from .tasks import deliver_email

    ctx = {
        'site_url': settings.SITE_URL,
        'logo_url': f'{settings.SITE_URL}/static/favicon.png',
        'subject': subject,
        **(context or {}),
    }
    html = render_to_string(template, ctx)
    text = html_to_text(html)

    encoded = []
    for att in attachments or []:
        content = att['content']
        if isinstance(content, str):
            content = content.encode('utf-8')
        encoded.append({
            'filename': att['filename'],
            'mimetype': att['mimetype'],
            'content': base64.b64encode(content).decode('ascii'),
        })

    store_body = not sensitive
    logs = []
    seen = set()
    for address in recipients:
        address = (address or '').strip()
        if not address or address.lower() in seen:
            continue
        seen.add(address.lower())

        suppressed = EmailSuppression.is_suppressed(address)
        log = EmailMessageLog.objects.create(
            recipient=address,
            subject=subject,
            template=template,
            body_html='' if suppressed or not store_body else html,
            body_text='' if suppressed or not store_body else text,
            attachments=[] if suppressed or not store_body else encoded,
            status=EmailMessageLog.Status.SUPPRESSED if suppressed else EmailMessageLog.Status.QUEUED,
        )
        logs.append(log)
        if not suppressed:
            # The body is passed explicitly so sensitive mails can be delivered
            # (and retried) without ever being written to the log row.
            transaction.on_commit(
                lambda pk=log.pk, h=html, t=text, a=encoded: deliver_email.delay(pk, h, t, a)
            )
    return logs
