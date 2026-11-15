"""
Django signals for organization models - handles Discord notifications and comments.
"""
import logging

import requests
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django_comments_xtd.models import XtdComment

from emailing.services import send_email
from notifications.services import (
    notify_new_tjanse,
    notify_slutrengoring_assignment,
)

from .discord_services import build_embed
from .models import (
    SlutrengoringAssignment,
    TjanseOwnership,
    TjanseSwapRequest,
    VolunteerAppointment,
)
from .slutrengoring_services import notify_assignment_discord
from .tasks import enqueue_discord_embed

logger = logging.getLogger(__name__)

TJANSE_STATUS_COLORS = {
    'assigned': 0x5865F2,
    'in_progress': 0xF1C40F,
    'done': 0x2ECC71,
    'not_done': 0xE74C3C,
}
SWAP_STATUS_COLORS = {
    'pending': 0xF1C40F,
    'accepted': 0x2ECC71,
    'rejected': 0xE74C3C,
    'cancelled': 0x95A5A6,
}



@receiver(post_save, sender=XtdComment)
def notify_appointment_comment(sender, instance, created, **kwargs):
    """
    Send Discord notification when a comment is added to a VolunteerAppointment.
    """
    if not created:
        return
    
    # Check if this comment is on a VolunteerAppointment
    volunteer_appointment_ct = ContentType.objects.get_for_model(VolunteerAppointment)
    if instance.content_type != volunteer_appointment_ct:
        return
    
    try:
        appointment = VolunteerAppointment.objects.get(pk=instance.object_pk)
    except VolunteerAppointment.DoesNotExist:
        return
    
    # Get Discord webhook from settings if it exists
    discord_webhook = getattr(settings, 'VOLUNTEER_APPOINTMENT_DISCORD_WEBHOOK', None)
    if not discord_webhook:
        return
    
    # Build notification message
    commenter = instance.user.get_full_name() or instance.user.username
    appointment_link = f"{settings.SITE_URL}/organization/appointment/{appointment.pk}/"

    message_text = (
        f"💬 **Ny kommentar på legeaftale**\n"
        f"**Kommentator:** {commenter}\n"
        f"**Aftale:** {appointment.requester.get_full_name()} → {appointment.receiver_display}\n"
        f"**Dato:** {appointment.start_date}\n"
        f"**Kommentar:** {instance.comment}\n"
        f"[Vis aftale]({appointment_link})"
    )
    
    payload = {
        "content": message_text,
        "username": "📝 Legeaftale Kommentarer",
        "thread_name": f"Aftale #{appointment.pk}",
    }
    
    try:
        response = requests.post(discord_webhook, json=payload, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        # Log the error but don't raise - comments should still be saved
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send Discord notification for appointment comment: {e}")


def send_tjanse_assigned_email(ownership):
    """Email every member of the owning team that a tjanse has been assigned to them."""
    team_emails = list(
        ownership.team.volunteer_set.exclude(email='').values_list('email', flat=True)
    )
    if not team_emails:
        return

    subject = f"Ny tjanse tildelt: {ownership.tjanse.title}"
    context = {
        'team': ownership.team,
        'event': ownership.event,
        'tjanse': ownership.tjanse,
        'due_date': ownership.due_date,
    }
    send_email(subject, 'organization/task_assigned_email.html', context, team_emails)


@receiver(post_save, sender=TjanseOwnership)
def notify_tjanse_assigned(sender, instance, created, **kwargs):
    """Email the owning team when a tjanse is first assigned to them."""
    if not created:
        return
    send_tjanse_assigned_email(instance)
    try:
        notify_new_tjanse(instance)
    except Exception:
        logger.exception(
            'Push-notifikation for ny tjanse %s fejlede', instance.pk
        )


@receiver(post_save, sender=TjanseOwnership)
def notify_tjanse_discord(sender, instance, created, **kwargs):
    """Queue a Discord embed for the owning team when a tjanse is assigned or updated."""
    team = instance.team
    if not team.discord_webhook_url:
        return
    embed = build_embed(
        title=f"{'Ny tjanse' if created else 'Tjanse opdateret'}: {instance.tjanse.title}",
        status=instance.get_status_display(),
        color=TJANSE_STATUS_COLORS.get(instance.status),
        fields=[
            ("Team", team.name),
            ("Event", str(instance.event)),
            ("Deadline", str(instance.due_date) if instance.due_date else "-"),
        ],
    )
    enqueue_discord_embed(team.pk, embed, "Tjanse Notifikationer")


@receiver(post_save, sender=TjanseSwapRequest)
def notify_tjanse_swap_discord(sender, instance, created, **kwargs):
    """Queue a Discord embed for both teams when a swap request is created or changed."""
    requesting, receiving = instance.requesting_team, instance.receiving_team
    tjanse = instance.task_ownership.tjanse
    embed = build_embed(
        title=f"{'Ny bytte-anmodning' if created else 'Bytte-anmodning opdateret'}: {tjanse.title}",
        status=instance.get_status_display(),
        color=SWAP_STATUS_COLORS.get(instance.status),
        changed_by=instance.resolved_by.get_full_name() if instance.resolved_by else None,
        fields=[
            ("Fra team", requesting.name),
            ("Til team", receiving.name),
            ("Event", str(instance.task_ownership.event)),
        ],
    )
    for team in {requesting.pk: requesting, receiving.pk: receiving}.values():
        if team.discord_webhook_url:
            enqueue_discord_embed(team.pk, embed, "Tjanse Notifikationer")


def send_slutrengoring_assigned_email(assignment):
    """Email the team when a Slutrengøring task is pre-assigned from the admin.

    Self-claims use ``QuerySet.update()`` and therefore do not emit ``post_save``;
    the team is already on the page and does not need another email.
    """
    if not assignment.team_id:
        return
    team_emails = list(
        assignment.team.volunteer_set.exclude(email='').values_list('email', flat=True)
    )
    if not team_emails:
        return

    subject = f"Ny slutrengøringopgave: {assignment.tjanse.title}"
    context = {
        'team': assignment.team,
        'event': assignment.event,
        'tjanse': assignment.tjanse,
        'assignment': assignment,
    }
    send_email(
        subject,
        'organization/slutrengoring_assigned_email.html',
        context,
        team_emails,
    )


@receiver(pre_save, sender=SlutrengoringAssignment)
def capture_slutrengoring_previous_team(sender, instance, **kwargs):
    """Remember the old owner so post_save can detect a real team change."""
    if not instance.pk:
        instance._previous_team_id = None
        return
    instance._previous_team_id = (
        sender.objects.filter(pk=instance.pk).values_list('team_id', flat=True).first()
    )


def _is_staff_assignment(instance):
    return bool(
        instance.team_id
        and instance.assigned_by_id
        and instance.assigned_by
        and instance.assigned_by.is_staff
    )


def _assignment_team_changed(instance, created):
    if created:
        return True
    return getattr(instance, '_previous_team_id', instance.team_id) != instance.team_id


@receiver(post_save, sender=SlutrengoringAssignment)
def notify_slutrengoring_assigned(sender, instance, created, **kwargs):
    # Only notify for a deliberate assignment by a staff member.
    if not created or not _is_staff_assignment(instance):
        return
    send_slutrengoring_assigned_email(instance)
    try:
        notify_slutrengoring_assignment(instance)
    except Exception:
        logger.exception(
            'Push-notifikation for slutrengøring %s fejlede', instance.pk
        )


@receiver(post_save, sender=SlutrengoringAssignment)
def notify_slutrengoring_discord(sender, instance, created, **kwargs):
    """Post assignments (and reassignments) to the receiving team's Discord."""
    if not _is_staff_assignment(instance):
        return
    if not _assignment_team_changed(instance, created):
        return
    notify_assignment_discord(instance, changed_by=instance.assigned_by)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def sync_allauth_email_address(sender, instance, created, **kwargs):
    from allauth.account.models import EmailAddress

    # allauth's own signup creates the row itself
    if getattr(instance, '_skip_email_sync', False) or not instance.email:
        return
    email = instance.email.lower()

    # Drop every alias that no longer matches the account's current email. An
    # old, verified alias left behind would remain a usable login identity
    # after the user changes their email address.
    EmailAddress.objects.filter(user=instance).exclude(email__iexact=email).delete()

    address = EmailAddress.objects.filter(user=instance, email__iexact=email).first()
    if address is None:
        EmailAddress.objects.create(
            user=instance, email=email, verified=True, primary=True
        )
        return

    update_fields = []
    if address.email != email:
        address.email = email
        update_fields.append('email')
    if not address.verified:
        address.verified = True
        update_fields.append('verified')
    if not address.primary:
        address.primary = True
        update_fields.append('primary')
    if update_fields:
        address.save(update_fields=update_fields)
