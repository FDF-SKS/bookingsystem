"""Demo data for the Depot app."""

from datetime import time, timedelta

from Depot.models import DepotBooking, DepotItem, DepotLocation
from utils.demo import (
    DEMO_TAG,
    DemoContext,
    DemoFactory,
    attach_demo_image,
    delete_demo_images,
)


class DepotDemoFactory(DemoFactory):
    label = 'Depot'

    def create_items(self, ctx: DemoContext) -> None:
        location, _ = DepotLocation.objects.get_or_create(name=f'{DEMO_TAG} Lager')
        for index in ctx.indexes:
            item, created = DepotItem.objects.get_or_create(
                name=f'{DEMO_TAG} Depot-ting {index + 1}',
                defaults={
                    'location': location,
                    'description': 'Inventar oprettet til test af bookingsystemet.',
                    'quantity': 10 + index,
                    'unit': 'stk.',
                },
            )
            if created:
                attach_demo_image(item, index)

    def create_bookings(self, ctx: DemoContext) -> None:
        if self.has_demo_rows(DepotBooking, minimum=ctx.per_model):
            return
        items = list(DepotItem.objects.filter(name__startswith=DEMO_TAG).order_by('pk'))
        if not items:
            return
        for index in ctx.indexes:
            DepotBooking.objects.create(
                item=items[index % len(items)],
                team=ctx.team(index),
                team_contact=ctx.contact(index),
                quantity=index + 1,
                start_date=ctx.today + timedelta(days=index % 3),
                start_time=time(8, 0),
                end_date=ctx.today + timedelta(days=(index % 3) + 1),
                end_time=time(17, 0),
                status=ctx.status(index),
                remarks=f'{DEMO_TAG} Testbooking',
            )

    def reset(self) -> None:
        DepotBooking.objects.filter(remarks__startswith=DEMO_TAG).delete()
        items = DepotItem.objects.filter(name__startswith=DEMO_TAG)
        delete_demo_images(items)
        items.delete()
        DepotLocation.objects.filter(name__startswith=DEMO_TAG).delete()

    def report(self, ctx: DemoContext) -> str:
        items = self.count(DepotItem, field='name')
        bookings = self.count(DepotBooking)
        return f'{items} varer, {bookings} bookinger'


FACTORY = DepotDemoFactory
