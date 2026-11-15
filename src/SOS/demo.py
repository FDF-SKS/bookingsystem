"""Demo data for the SOS app."""

from datetime import time, timedelta
from decimal import Decimal

from SOS.models import SOSBooking, SOSItem
from utils.demo import DEMO_TAG, DemoContext, DemoFactory


class SOSDemoFactory(DemoFactory):
    label = 'SOS'

    def create_items(self, ctx: DemoContext) -> None:
        for index in ctx.indexes:
            SOSItem.objects.get_or_create(
                name=f'{DEMO_TAG} SOS-ting {index + 1}',
                defaults={'description': 'SOS-udstyr oprettet til test.'},
            )

    def create_bookings(self, ctx: DemoContext) -> None:
        if self.has_demo_rows(SOSBooking, minimum=ctx.per_model):
            return
        items = list(SOSItem.objects.filter(name__startswith=DEMO_TAG).order_by('pk'))
        if not items:
            return
        for index in ctx.indexes:
            SOSBooking.objects.create(
                team=ctx.team(index),
                item=items[index % len(items)],
                team_contact=ctx.contact(index),
                quantity=Decimal(str(index + 1)),
                start_date=ctx.today + timedelta(days=index % 3),
                start_time=time(8, 0),
                end_date=ctx.today + timedelta(days=(index % 3) + 1),
                end_time=time(18, 0),
                status=ctx.status(index),
                remarks=f'{DEMO_TAG} Testbooking',
                assistance_needed=index % 2 == 0,
                delivery_needed=index % 3 == 0,
            )

    def reset(self) -> None:
        SOSBooking.objects.filter(remarks__startswith=DEMO_TAG).delete()
        SOSItem.objects.filter(name__startswith=DEMO_TAG).delete()

    def report(self, ctx: DemoContext) -> str:
        items = self.count(SOSItem, field='name')
        bookings = self.count(SOSBooking)
        return f'{items} varer, {bookings} bookinger'


FACTORY = SOSDemoFactory
