"""Demo data for the Sjak app."""

from datetime import time, timedelta
from decimal import Decimal

from Sjak.models import SjakBooking, SjakItem, SjakItemLocation, SjakItemType
from utils.demo import (
    DEMO_TAG,
    DemoContext,
    DemoFactory,
    attach_demo_image,
    delete_demo_images,
)


class SjakDemoFactory(DemoFactory):
    label = 'Sjak'

    def create_items(self, ctx: DemoContext) -> None:
        item_type, _ = SjakItemType.objects.get_or_create(name=f'{DEMO_TAG} Værktøj')
        location, _ = SjakItemLocation.objects.get_or_create(name=f'{DEMO_TAG} Lager')
        for index in ctx.indexes:
            item, created = SjakItem.objects.get_or_create(
                name=f'{DEMO_TAG} Sjak-ting {index + 1}',
                defaults={
                    'item_type': item_type,
                    'location': location,
                    'description': 'Værktøj oprettet til test af bookingsystemet.',
                    'quantity_lager': str(index + 3),
                },
            )
            if created:
                attach_demo_image(item, index)

    def create_bookings(self, ctx: DemoContext) -> None:
        if self.has_demo_rows(SjakBooking, minimum=ctx.per_model):
            return
        items = list(SjakItem.objects.filter(name__startswith=DEMO_TAG).order_by('pk'))
        if not items:
            return
        for index in ctx.indexes:
            SjakBooking.objects.create(
                team=ctx.team(index),
                item=items[index % len(items)],
                team_contact=ctx.contact(index),
                event=ctx.event,
                start_date=ctx.today + timedelta(days=index % 3),
                start_time=time(9, 0),
                end_date=ctx.today + timedelta(days=(index % 3) + 1),
                end_time=time(16, 0),
                quantity=Decimal(str(index + 1)),
                status=ctx.status(index),
                status_internal=ctx.internal_status(index),
                remarks=f'{DEMO_TAG} Testbooking',
            )

    def reset(self) -> None:
        SjakBooking.objects.filter(remarks__startswith=DEMO_TAG).delete()
        items = SjakItem.objects.filter(name__startswith=DEMO_TAG)
        delete_demo_images(items)
        items.delete()
        SjakItemType.objects.filter(name__startswith=DEMO_TAG).delete()
        SjakItemLocation.objects.filter(name__startswith=DEMO_TAG).delete()

    def report(self, ctx: DemoContext) -> str:
        items = self.count(SjakItem, field='name')
        bookings = self.count(SjakBooking)
        return f'{items} varer, {bookings} bookinger'


FACTORY = SjakDemoFactory
