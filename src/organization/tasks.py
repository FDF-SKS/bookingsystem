import logging
from datetime import timedelta
from smtplib import SMTPException

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db.models import Q
from django.utils import timezone

from django_comments.models import Comment

from AktivitetsTeam.models import AktivitetsTeamBooking
from Butikken.models import ButikkenBooking
from Depot.models import DepotBooking
from Foto.models import FotoBooking
from SOS.models import SOSBooking
from Sjak.models import SjakBooking
from Teknik.models import TeknikBooking

from .models import EmailLog, TeamMembership, Volunteer

logger = logging.getLogger(__name__)

BOOKING_MODELS = (
    AktivitetsTeamBooking,
    ButikkenBooking,
    DepotBooking,
    FotoBooking,
    SOSBooking,
    SjakBooking,
    TeknikBooking,
)


def _get_recent_booking_updates(since):
    updates = []
    per_team = {}
    for model in BOOKING_MODELS:
        queryset = (
            model.objects.select_related("team")
            .filter(last_updated__gte=since)
            .order_by("-last_updated")
        )
        count = queryset.count()
        if count:
            updates.append(
                {
                    "model_name": model._meta.verbose_name_plural.title(),
                    "count": count,
                }
            )

        for booking in queryset:
            team_id = booking.team_id
            if team_id not in per_team:
                per_team[team_id] = []
            per_team[team_id].append(
                f"{model._meta.verbose_name.title()} #{booking.pk} ({booking.status})"
            )
    return updates, per_team


def _get_recent_comments_count(since):
    content_types = ContentType.objects.get_for_models(*BOOKING_MODELS).values()
    return Comment.objects.filter(
        submit_date__gte=since,
        content_type__in=content_types,
    ).count()


@shared_task(bind=True, autoretry_for=(SMTPException,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 3})
def send_email_logs(self, email_log_ids):
    logs = list(
        EmailLog.objects.filter(id__in=email_log_ids, status__in=[EmailLog.STATUS_PENDING, EmailLog.STATUS_FAILED]).order_by("id")
    )
    if not logs:
        return 0

    connection = get_connection(fail_silently=False)
    sent_count = 0
    transient_failures = []

    try:
        connection.open()
        for log in logs:
            email_message = EmailMultiAlternatives(
                subject=log.subject,
                body=log.body,
                from_email=log.from_email,
                to=[log.recipient],
                connection=connection,
            )
            if log.html_body:
                email_message.attach_alternative(log.html_body, "text/html")
            for attachment in log.attachments or []:
                email_message.attach(
                    attachment.get("filename", "attachment.txt"),
                    attachment.get("content", ""),
                    attachment.get("mimetype", "application/octet-stream"),
                )

            try:
                sent = connection.send_messages([email_message])
                if sent != 1:
                    raise SMTPException("Email backend did not report successful delivery.")
                log.status = EmailLog.STATUS_SENT
                log.error_message = ""
                log.sent_at = timezone.now()
                sent_count += 1
            except SMTPException as exc:
                log.error_message = str(exc)
                if self.request.retries >= self.max_retries:
                    log.status = EmailLog.STATUS_FAILED
                    logger.exception("Email permanently failed for log %s", log.id)
                else:
                    log.status = EmailLog.STATUS_PENDING
                    transient_failures.append(log.id)
            except Exception as exc:
                log.error_message = str(exc)
                log.status = EmailLog.STATUS_FAILED
                logger.exception("Unexpected email failure for log %s", log.id)
            finally:
                log.attempts += 1
                log.save(update_fields=["status", "attempts", "error_message", "sent_at", "last_updated"])
    finally:
        connection.close()

    if transient_failures and self.request.retries < self.max_retries:
        raise SMTPException(f"Temporary SMTP failure for email logs: {transient_failures}")

    return sent_count


@shared_task
def send_daily_role_updates():
    from .email_service import queue_bulk_emails

    since = timezone.now() - timedelta(days=1)
    booking_updates, booking_updates_per_team = _get_recent_booking_updates(since)
    if not booking_updates:
        return 0

    comments_count = _get_recent_comments_count(since)
    messages = []

    admin_sjak_recipients = Volunteer.objects.filter(
        is_active=True,
    ).filter(
        Q(is_superuser=True)
        | Q(teams__name__icontains="sjak")
        | Q(teams__short_name__icontains="sjak")
    ).distinct()

    updates_text = "\n".join([f"- {item['model_name']}: {item['count']}" for item in booking_updates])
    for volunteer in admin_sjak_recipients:
        body = (
            "Daglig booking-opdatering (seneste døgn)\n\n"
            f"Bookinger:\n{updates_text}\n\n"
            f"Nye kommentarer på bookinger: {comments_count}"
        )
        messages.append(
            {
                "recipient": volunteer.email,
                "subject": "Daglig opdatering: Bookinger og kommentarer",
                "body": body,
            }
        )

    instructor_memberships = TeamMembership.objects.select_related("member", "team").filter(
        member__is_active=True
    ).filter(
        Q(role__icontains="instrukt") | Q(role__icontains="instructor")
    )

    for membership in instructor_memberships:
        team_updates = booking_updates_per_team.get(membership.team_id, [])
        if not team_updates:
            continue
        body = (
            f"Daglig statusopdatering for {membership.team.name}\n\n"
            "Opdaterede bookinger:\n"
            + "\n".join([f"- {entry}" for entry in team_updates[:50]])
        )
        messages.append(
            {
                "recipient": membership.member.email,
                "subject": f"Daglig opdatering: {membership.team.name}",
                "body": body,
            }
        )

    return queue_bulk_emails(messages)
