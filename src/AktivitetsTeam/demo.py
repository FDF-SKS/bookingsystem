"""Demo data for the AktivitetsTeam app."""

from datetime import time, timedelta

from AktivitetsTeam.models import (
    AktivitetsTeamBooking,
    AktivitetsTeamItem,
    AktivitetsTeamItemType,
)
from utils.demo import (
    DEMO_TAG,
    DemoContext,
    DemoFactory,
    attach_demo_image,
    delete_demo_images,
)


class AktivitetsTeamDemoFactory(DemoFactory):
    label = 'AktivitetsTeam'

    def create_items(self, ctx: DemoContext) -> None:
        category, _ = AktivitetsTeamItemType.objects.get_or_create(
            name=f'{DEMO_TAG} Aktiviteter',
            defaults={'bs_icon': 'bi-activity', 'slug': 'demo-aktiviteter'},
        )
        for index in ctx.indexes:
            item, created = AktivitetsTeamItem.objects.get_or_create(
                name=f'{DEMO_TAG} Aktivitet {index + 1}',
                defaults={
                    'category': category,
                    'short_description': 'Kort demo-beskrivelse af aktiviteten.',
                    'description': 'Aktivitet oprettet til test af bookingsystemet.',
                    'is_active': True,
                },
            )
            if created:
                attach_demo_image(item, index)

    def create_bookings(self, ctx: DemoContext) -> None:
        if self.has_demo_rows(AktivitetsTeamBooking, minimum=ctx.per_model):
            return
        items = list(AktivitetsTeamItem.objects.filter(name__startswith=DEMO_TAG).order_by('pk'))
        if not items:
            return
        for index in ctx.indexes:
            AktivitetsTeamBooking.objects.create(
                team=ctx.team(index),
                item=items[index % len(items)],
                team_contact=ctx.contact(index),
                status=ctx.status(index),
                remarks=f'{DEMO_TAG} Testbooking',
                start_date=ctx.today + timedelta(days=index % 3),
                start_time=time(10 + index % 8, 0),
                end_date=ctx.today + timedelta(days=index % 3),
                end_time=time(12 + index % 8, 0),
            )

    def reset(self) -> None:
        AktivitetsTeamBooking.objects.filter(remarks__startswith=DEMO_TAG).delete()
        items = AktivitetsTeamItem.objects.filter(name__startswith=DEMO_TAG)
        delete_demo_images(items)
        items.delete()
        AktivitetsTeamItemType.objects.filter(name__startswith=DEMO_TAG).delete()

    def report(self, ctx: DemoContext) -> str:
        items = self.count(AktivitetsTeamItem, field='name')
        bookings = self.count(AktivitetsTeamBooking)
        return f'{items} varer, {bookings} bookinger'


FACTORY = AktivitetsTeamDemoFactory
