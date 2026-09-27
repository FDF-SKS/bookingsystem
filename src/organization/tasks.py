import logging
from datetime import timedelta
from smtplib import SMTPException
import base64

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
MAX_EMAIL_RETRIES = 3

BOOKING_MODELS = (
    AktivitetsTeamBooking,
    ButikkenBooking,
    DepotBooking,
    FotoBooking,
    SOSBooking,
    SjakBooking,
    TeknikBooking,
)


def _get_recent_booking_updates(since, until=None):
    updates = []
    per_team = {}
    for model in BOOKING_MODELS:
        queryset = (
            model.objects.select_related("team")
            .filter(last_updated__gte=since)
            .order_by("-last_updated")
        )
        if until:
            queryset = queryset.filter(last_updated__lt=until)
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


def _get_recent_comments_count(since, until=None):
    content_types = ContentType.objects.get_for_models(*BOOKING_MODELS).values()
    queryset = Comment.objects.filter(
        submit_date__gte=since,
        content_type__in=content_types,
    )
    if until:
        queryset = queryset.filter(submit_date__lt=until)
    return queryset.count()


@shared_task(bind=True, autoretry_for=(SMTPException,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": MAX_EMAIL_RETRIES})
def send_email_logs(self, email_log_ids):
    logs = list(
        EmailLog.objects.filter(id__in=email_log_ids, status__in=[EmailLog.STATUS_PENDING, EmailLog.STATUS_FAILED]).order_by("id")
    )
    if not logs:
        return 0

    connection = get_connection(fail_silently=False)
    sent_count = 0
    transient_failures = []

    email_messages = []
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
            content = attachment.get("content", "")
            if attachment.get("is_base64"):
                content = base64.b64decode(content)
            email_message.attach(
                attachment.get("filename", "attachment.txt"),
                content,
                attachment.get("mimetype", "application/octet-stream"),
            )
        email_messages.append(email_message)

    try:
        connection.open()
        now = timezone.now()
        for log, email_message in zip(logs, email_messages):
            try:
                delivered = connection.send_messages([email_message]) or 0
                log.attempts += 1
                if delivered == 1:
                    log.status = EmailLog.STATUS_SENT
                    log.error_message = ""
                    log.sent_at = now
                    sent_count += 1
                else:
                    log.error_message = "Email backend did not report successful delivery."
                    if log.attempts >= MAX_EMAIL_RETRIES:
                        log.status = EmailLog.STATUS_FAILED
                    else:
                        log.status = EmailLog.STATUS_PENDING
                        transient_failures.append(log.id)
                log.save(update_fields=["status", "attempts", "error_message", "sent_at", "last_updated"])
            except SMTPException as single_exc:
                log.attempts += 1
                log.error_message = str(single_exc)
                if log.attempts >= MAX_EMAIL_RETRIES:
                    log.status = EmailLog.STATUS_FAILED
                    logger.exception("Email permanently failed for log %s", log.id)
                else:
                    log.status = EmailLog.STATUS_PENDING
                    transient_failures.append(log.id)
                log.save(update_fields=["status", "attempts", "error_message", "sent_at", "last_updated"])
            except Exception as exc:
                log.attempts += 1
                log.error_message = str(exc)
                log.status = EmailLog.STATUS_FAILED
                log.save(update_fields=["status", "attempts", "error_message", "sent_at", "last_updated"])
                logger.exception("Unexpected email failure for log %s", log.id)
    finally:
        connection.close()

    if transient_failures:
        raise SMTPException(f"Temporary SMTP failure for email logs: {transient_failures}")

    return sent_count


@shared_task
def send_daily_role_updates():
    from .email_service import queue_bulk_emails

    now = timezone.localtime()
    window_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(days=1)

    booking_updates, booking_updates_per_team = _get_recent_booking_updates(window_start, until=window_end)
    comments_count = _get_recent_comments_count(window_start, until=window_end)
    if not booking_updates and comments_count == 0:
        return 0
    messages = []

    admin_sjak_recipients = Volunteer.objects.filter(
        is_active=True,
        email__isnull=False,
        is_superuser=True,
    ).exclude(
        email="",
    )
    sjak_assignees = Volunteer.objects.filter(
        is_active=True,
        email__isnull=False,
        assigned_sjak_bookings__last_updated__gte=window_start,
        assigned_sjak_bookings__last_updated__lt=window_end,
    ).exclude(email="")
    admin_sjak_recipients = (admin_sjak_recipients | sjak_assignees).distinct()

    updates_text = "\n".join([f"- {item['model_name']}: {item['count']}" for item in booking_updates]) or "- Ingen booking-opdateringer"
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
        member__is_active=True,
        member__email__isnull=False,
    ).exclude(
        member__email="",
    ).filter(
        Q(role__icontains="instrukt") | Q(role__icontains="instructor")
    )
    seen_memberships = set()

    for membership in instructor_memberships:
        dedupe_key = (membership.member_id, membership.team_id)
        if dedupe_key in seen_memberships:
            continue
        seen_memberships.add(dedupe_key)

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
