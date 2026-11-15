"""Demo data for the Butikken app."""

from datetime import time, timedelta
from decimal import Decimal

from django.utils import timezone

from Butikken.models import ButikkenBooking, ButikkenItem, ButikkenOrder
from utils.demo import DEMO_TAG, DemoContext, DemoFactory

ORDER_STATUSES = ('Afventer', 'Godkendt', 'Pakket', 'Udleveret', 'Afvist')


class ButikkenDemoFactory(DemoFactory):
    label = 'Butikken'

    def create_items(self, ctx: DemoContext) -> None:
        for index in ctx.indexes:
            ButikkenItem.objects.get_or_create(
                name=f'{DEMO_TAG} Butiksvare {index + 1}',
                defaults={
                    'type': 'Demo',
                    'description': 'Vare oprettet til test af bookingsystemet.',
                    'content_normal': '1 stk.',
                    'content_unit': 'stk.',
                },
            )

    def create_bookings(self, ctx: DemoContext) -> None:
        if self.has_demo_rows(ButikkenOrder, field='name', minimum=ctx.per_model):
            return
        items = list(ButikkenItem.objects.filter(name__startswith=DEMO_TAG).order_by('pk'))
        if not items:
            return
        for index in ctx.indexes:
            team = ctx.team(index)
            order = ButikkenOrder.objects.create(
                team=team,
                team_contact=ctx.contact(index),
                status=ORDER_STATUSES[index % len(ORDER_STATUSES)],
                name=f'{DEMO_TAG} Butiksordre {index + 1}',
                order_date=timezone.now(),
                pickup_date=ctx.today + timedelta(days=index % 3),
                remarks='Testordre oprettet af generate_dummy_data.',
            )
            ButikkenBooking.objects.create(
                order=order,
                team=team,
                item=items[index % len(items)],
                team_contact=ctx.contact(index),
                status=ctx.status(index),
                start_date=ctx.today + timedelta(days=index % 3),
                start_time=time(9 + index % 8, 0),
                quantity=Decimal(str(index + 1)),
                unit='stk.',
                for_meal='Aktivitet',
                remarks=DEMO_TAG,
            )

    def reset(self) -> None:
        ButikkenBooking.objects.filter(remarks__startswith=DEMO_TAG).delete()
        ButikkenOrder.objects.filter(name__startswith=DEMO_TAG).delete()
        ButikkenItem.objects.filter(name__startswith=DEMO_TAG).delete()

    def report(self, ctx: DemoContext) -> str:
        items = self.count(ButikkenItem, field='name')
        bookings = self.count(ButikkenBooking)
        return f'{items} varer, {bookings} bookinger'


FACTORY = ButikkenDemoFactory
