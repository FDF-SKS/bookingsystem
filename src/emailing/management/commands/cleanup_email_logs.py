"""Daily cleanup of email logs; run from host crontab, e.g.:
    30 3 * * * docker compose exec -T web python manage.py cleanup_email_logs
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from emailing.models import EmailMessageLog


class Command(BaseCommand):
    help = "Wipe bodies of old failed emails and delete old email log rows."

    def add_arguments(self, parser):
        parser.add_argument('--body-days', type=int, default=7)
        parser.add_argument('--row-days', type=int, default=90)

    def handle(self, *args, body_days, row_days, **kwargs):
        now = timezone.now()
        wiped = EmailMessageLog.objects.filter(
            created_at__lt=now - timedelta(days=body_days),
        ).exclude(body_html='', body_text='', attachments=[]).update(
            body_html='', body_text='', attachments=[],
        )
        deleted, _ = EmailMessageLog.objects.filter(
            created_at__lt=now - timedelta(days=row_days),
        ).delete()
        self.stdout.write(self.style.SUCCESS(
            f"Ryddet bodies på {wiped} emails og slettede {deleted} log-rækker."
        ))
