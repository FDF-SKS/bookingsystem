"""Send a reminder email to teams whose tjanse is due today but not yet done.

Intended to be run once daily at 18:00 via host crontab, e.g.:
    0 18 * * * <path-to-venv>/bin/python manage.py send_tjanse_reminders
"""
from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from organization.models import TjanseOwnership


class Command(BaseCommand):
    help = "Send reminder emails for tjanser due today that are not yet marked done."

    def handle(self, *args, **kwargs):
        due_ownerships = TjanseOwnership.objects.filter(
            due_date=date.today(),
        ).exclude(status='done').select_related('tjanse', 'event', 'team')

        sent_count = 0
        for ownership in due_ownerships:
            team_emails = list(
                ownership.team.volunteer_set.exclude(email='').values_list('email', flat=True)
            )
            if not team_emails:
                continue

            subject = f"Påmindelse: {ownership.tjanse.title} er ikke udført"
            context = {
                'team': ownership.team,
                'tjanse': ownership.tjanse,
                'due_date': ownership.due_date,
            }
            message = render_to_string('organization/task_reminder_email.html', context)
            send_mail(
                subject,
                strip_tags(message),
                settings.DEFAULT_FROM_EMAIL,
                team_emails,
                html_message=message,
            )
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Sendt {sent_count} tjanse-påmindelser."))
