from allauth.account.adapter import DefaultAccountAdapter
from django.template.loader import render_to_string

from emailing.services import send_email


class AccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        user.is_active = False  # an admin must approve new volunteers
        user._skip_email_sync = True  # allauth creates the EmailAddress itself
        if commit:
            user.save()
            self._add_to_unassigned_team(user)
        return user

    def _add_to_unassigned_team(self, user):
        from .models import Team, TeamMembership

        team = Team.objects.filter(name="Unassigned users").first()
        if team:
            TeamMembership.objects.create(team=team, member=user)

    def send_mail(self, template_prefix, email, context):
        subject = ''.join(
            render_to_string(f'{template_prefix}_subject.txt', context, self.request).splitlines()
        )
        body = render_to_string(f'{template_prefix}_message.txt', context, self.request)
        send_email(
            self.format_email_subject(subject),
            'emailing/account_message.html',
            {'body': body, 'user': context.get('user')},
            [email],
        )
