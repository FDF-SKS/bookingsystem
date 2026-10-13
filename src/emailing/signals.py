from django.dispatch import receiver
from django_ses.signals import bounce_received, complaint_received, delivery_received

from .models import EmailMessageLog, EmailSuppression

Status = EmailMessageLog.Status


@receiver(delivery_received)
def on_delivery(sender, mail_obj, delivery_obj, **kwargs):
    message_id = (mail_obj or {}).get('messageId', '')
    for address in delivery_obj.get('recipients', []):
        EmailMessageLog.advance(message_id, address, Status.DELIVERED)


@receiver(bounce_received)
def on_bounce(sender, mail_obj, bounce_obj, **kwargs):
    message_id = (mail_obj or {}).get('messageId', '')
    permanent = bounce_obj.get('bounceType') == 'Permanent'
    for rcpt in bounce_obj.get('bouncedRecipients', []):
        address = rcpt.get('emailAddress', '')
        if not address:
            continue
        detail = rcpt.get('diagnosticCode', '') or bounce_obj.get('bounceSubType', '')
        # Suppression doesn't depend on finding the log row.
        if permanent:
            EmailSuppression.objects.get_or_create(
                email=address.lower(),
                defaults={'reason': EmailSuppression.Reason.BOUNCE, 'detail': detail},
            )
            EmailMessageLog.advance(
                message_id, address, Status.BOUNCED,
                bounce_type='Permanent', last_error=detail,
            )
        else:
            EmailMessageLog.objects.filter(
                ses_message_id=message_id, recipient__iexact=address,
            ).update(bounce_type='Transient', last_error=detail)


@receiver(complaint_received)
def on_complaint(sender, mail_obj, complaint_obj, **kwargs):
    message_id = (mail_obj or {}).get('messageId', '')
    for rcpt in complaint_obj.get('complainedRecipients', []):
        address = rcpt.get('emailAddress', '')
        if not address:
            continue
        EmailSuppression.objects.get_or_create(
            email=address.lower(),
            defaults={
                'reason': EmailSuppression.Reason.COMPLAINT,
                'detail': complaint_obj.get('complaintFeedbackType', ''),
            },
        )
        EmailMessageLog.advance(message_id, address, Status.COMPLAINED)
