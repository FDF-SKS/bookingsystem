"""
Management command to test Discord notifications for SjakBooking.

Usage:
    python manage.py test_discord_notification [team_id] [--webhook URL]

Examples:
    # Test with first team that has a webhook
    python manage.py test_discord_notification
    
    # Test with specific team
    python manage.py test_discord_notification 5
    
    # Test with custom webhook URL
    python manage.py test_discord_notification --webhook https://discord.com/api/webhooks/...
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from organization.models import Team
from Sjak.models import SjakBooking, SjakItem, SjakItemType


class Command(BaseCommand):
    help = 'Test Discord notifications by creating a temporary SjakBooking'

    def add_arguments(self, parser):
        parser.add_argument(
            'team_id',
            nargs='?',
            type=int,
            help='Team ID to test with (optional - uses first team if not provided)'
        )
        parser.add_argument(
            '--webhook',
            type=str,
            help='Discord webhook URL to test with'
        )

    def handle(self, *args, **options):
        # Get or find team
        team_id = options.get('team_id')
        webhook_url = options.get('webhook')
        
        if team_id:
            try:
                team = Team.objects.get(id=team_id)
            except Team.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Team with ID {team_id} not found'))
                return
        else:
            team = Team.objects.first()
            if not team:
                self.stdout.write(self.style.ERROR('No teams found in database'))
                return
        
        # Set webhook URL if provided
        if webhook_url:
            team.discord_webhook_url = webhook_url
            team.save()
            self.stdout.write(self.style.SUCCESS(f'Set webhook URL for team: {team.name}'))
        elif not team.discord_webhook_url:
            self.stdout.write(self.style.WARNING(f'Team "{team.name}" has no webhook URL configured'))
            return
        
        # Create test item type if needed
        item_type, _ = SjakItemType.objects.get_or_create(name='Test Type')
        
        # Create or get test item
        test_item, _ = SjakItem.objects.get_or_create(
            name='Test Item for Discord Notification',
            defaults={'item_type': item_type, 'quantity_lager': 1}
        )
        
        # Get first volunteer as contact
        contact = team.teammembership_set.first()
        if not contact:
            self.stdout.write(self.style.WARNING(f'No team members found for team "{team.name}"'))
            return
        
        # Create test booking (this will trigger the signal)
        try:
            booking = SjakBooking.objects.create(
                item=test_item,
                quantity=1,
                team=team,
                team_contact=contact.member,
                start=timezone.now().date(),
                end=timezone.now().date() + timedelta(days=1),
                start_time=timezone.now().time(),
                end_time=timezone.now().time(),
                status='Pending',
                status_internal='Afventer',
                remarks='Test booking - Discord notification test'
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Test booking created: ID {booking.id}'))
            self.stdout.write(self.style.SUCCESS(f'✓ Discord notification should be sent to: {team.discord_webhook_url}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error creating test booking: {e!s}'))


