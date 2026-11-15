"""Demo data for the Teknik app."""

from datetime import time, timedelta
from decimal import Decimal

from Teknik.models import TeknikBooking, TeknikItem, TeknikType
from utils.demo import DEMO_TAG, DemoContext, DemoFactory


class TeknikDemoFactory(DemoFactory):
    label = 'Teknik'

    def create_items(self, ctx: DemoContext) -> None:
        TeknikType.objects.get_or_create(name=f'{DEMO_TAG} Teknik')
        for index in ctx.indexes:
            TeknikItem.objects.get_or_create(
                name=f'{DEMO_TAG} Teknik-ting {index + 1}',
                defaults={'description': 'Teknisk udstyr oprettet til test.'},
            )

    def create_bookings(self, ctx: DemoContext) -> None:
        if self.has_demo_rows(TeknikBooking, minimum=ctx.per_model):
            return
        items = list(TeknikItem.objects.filter(name__startswith=DEMO_TAG).order_by('pk'))
        if not items:
            return
        for index in ctx.indexes:
            TeknikBooking.objects.create(
                team=ctx.team(index),
                item=items[index % len(items)],
                team_contact=ctx.contact(index),
                quantity=Decimal(str(index + 1)),
                start_date=ctx.today + timedelta(days=index % 3),
                start_time=time(9, 0),
                end_date=ctx.today + timedelta(days=(index % 3) + 1),
                end_time=time(16, 0),
                status=ctx.status(index),
                remarks=f'{DEMO_TAG} Testbooking',
                delivery_needed=index % 2 == 0,
                assistance_needed=index % 3 == 0,
            )

    def reset(self) -> None:
        TeknikBooking.objects.filter(remarks__startswith=DEMO_TAG).delete()
        TeknikItem.objects.filter(name__startswith=DEMO_TAG).delete()
        TeknikType.objects.filter(name__startswith=DEMO_TAG).delete()

    def report(self, ctx: DemoContext) -> str:
        items = self.count(TeknikItem, field='name')
        bookings = self.count(TeknikBooking)
        return f'{items} varer, {bookings} bookinger'


FACTORY = TeknikDemoFactory
