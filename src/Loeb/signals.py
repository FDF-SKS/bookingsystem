from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Hold, TaskSubmission


@receiver(post_save, sender=Hold)
def hold_created_handler(sender, instance, created, **kwargs):
    if created:
        return


@receiver(post_save, sender=TaskSubmission)
def submission_updated_handler(sender, instance, **kwargs):
    return
