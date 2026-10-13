from django.db import models


class EmailMessageLog(models.Model):
    class Status(models.TextChoices):
        QUEUED = 'queued', 'I kø'
        SENDING = 'sending', 'Sender'
        SENT = 'sent', 'Sendt til SES'
        DELIVERED = 'delivered', 'Leveret'
        BOUNCED = 'bounced', 'Afvist (bounce)'
        COMPLAINED = 'complained', 'Spam-klage'
        FAILED = 'failed', 'Fejlet'
        SUPPRESSED = 'suppressed', 'Blokeret (suppression)'

    # Forward-only progression; webhook events never move a log backwards.
    RANK = {
        Status.QUEUED: 0,
        Status.SENDING: 1,
        Status.SENT: 2,
        Status.DELIVERED: 3,
        Status.BOUNCED: 4,
        Status.COMPLAINED: 4,
    }

    recipient = models.EmailField(db_index=True)
    subject = models.CharField(max_length=255)
    template = models.CharField(max_length=255, blank=True)
    body_html = models.TextField()
    body_text = models.TextField()
    # [{"filename", "mimetype", "content" (base64)}]
    attachments = models.JSONField(default=list, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    ses_message_id = models.CharField(max_length=128, blank=True, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    bounce_type = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email-log'
        verbose_name_plural = 'Email-log'

    def __str__(self):
        return f'{self.recipient}: {self.subject}'

    @classmethod
    def advance(cls, ses_message_id, recipient, new_status, **extra):
        """Move matching logs forward to new_status; duplicate or stale events do nothing."""
        lower = [s for s, r in cls.RANK.items() if r < cls.RANK[new_status]]
        return cls.objects.filter(
            ses_message_id=ses_message_id,
            recipient__iexact=recipient,
            status__in=lower,
        ).update(status=new_status, **extra)


class EmailSuppression(models.Model):
    class Reason(models.TextChoices):
        BOUNCE = 'bounce', 'Permanent bounce'
        COMPLAINT = 'complaint', 'Spam-klage'
        MANUAL = 'manual', 'Manuel'

    email = models.EmailField(unique=True)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email-suppression'
        verbose_name_plural = 'Email-suppression'

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

    @classmethod
    def is_suppressed(cls, email):
        return cls.objects.filter(email=email.strip().lower()).exists()
