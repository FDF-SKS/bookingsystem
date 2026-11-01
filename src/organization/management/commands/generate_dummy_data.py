import random

from django.core.management.base import BaseCommand

from organization.models import Team, TeamMembership, Volunteer


class Command(BaseCommand):
    help = 'Generate dummy data for Team, Volunteer, and TeamMembership models'

    def handle(self, *args, **kwargs):
        # Create dummy teams
        for i in range(5):
            team = Team.objects.create(name=f'Team {i+1}')
            self.stdout.write(self.style.SUCCESS(f'Successfully created team {team.name}'))

        # Create dummy volunteers
        for i in range(10):
            volunteer = Volunteer.objects.create(
                username=f'user{i+1}',
                first_name=f'First{i+1}',
                last_name=f'Last{i+1}'
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created volunteer {volunteer.username}'))

        # Create dummy team memberships
        teams = Team.objects.all()
        volunteers = Volunteer.objects.all()
        for volunteer in volunteers:
            team = random.choice(teams)
            TeamMembership.objects.create(
                team=team,
                member=volunteer,
                role='Member'
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created membership for {volunteer.username} in {team.name}'))

