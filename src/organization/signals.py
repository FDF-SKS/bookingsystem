"""
Django signals for organization models - handles Discord notifications and comments.
"""
import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django_comments_xtd.models import XtdComment
from django.contrib.contenttypes.models import ContentType
from .models import TjanseOwnership, VolunteerAppointment


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
    appointment_link = f"https://{settings.ALLOWED_HOSTS[0]}/organization/appointment/{appointment.pk}/"
    
    message_text = (
        f"💬 **Ny kommentar på legeaftale**\n"
        f"**Kommentator:** {commenter}\n"
        f"**Aftale:** {appointment.requester.get_full_name()} → {appointment.receiver.get_full_name()}\n"
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
    message = render_to_string('organization/task_assigned_email.html', context)
    send_mail(
        subject,
        strip_tags(message),
        settings.DEFAULT_FROM_EMAIL,
        team_emails,
        html_message=message,
    )


@receiver(post_save, sender=TjanseOwnership)
def notify_tjanse_assigned(sender, instance, created, **kwargs):
    """Email the owning team when a tjanse is first assigned to them."""
    if not created:
        return
    send_tjanse_assigned_email(instance)
