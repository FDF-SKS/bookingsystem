from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.template.loader import render_to_string
from django.urls import reverse

from .services import send_email


class BrandedPasswordResetForm(PasswordResetForm):
    """Sends the reset mail through the shared pipeline so it is branded, queued and logged."""

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        subject = ''.join(render_to_string(subject_template_name, context).splitlines())
        reset_path = reverse(
            'password_reset_confirm', kwargs={'uidb64': context['uid'], 'token': context['token']}
        )
        send_email(
            subject,
            email_template_name,
            {'user': context['user'], 'reset_url': f'{settings.SITE_URL}{reset_path}'},
            [to_email],
        )
