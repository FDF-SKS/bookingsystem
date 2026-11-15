"""Demo data for the Foto app."""

from datetime import time, timedelta

from Foto.models import FotoBooking, FotoItem
from utils.demo import DEMO_TAG, DemoContext, DemoFactory


class FotoDemoFactory(DemoFactory):
    label = 'Foto'

    def create_items(self, ctx: DemoContext) -> None:
        for index in ctx.indexes:
            FotoItem.objects.get_or_create(
                name=f'{DEMO_TAG} Foto-udstyr {index + 1}',
                defaults={'description': 'Foto- og videoudstyr oprettet til test.'},
            )

    def create_bookings(self, ctx: DemoContext) -> None:
        if self.has_demo_rows(FotoBooking, minimum=ctx.per_model):
            return
        items = list(FotoItem.objects.filter(name__startswith=DEMO_TAG).order_by('pk'))
        if not items:
            return
        for index in ctx.indexes:
            FotoBooking.objects.create(
                team=ctx.team(index),
                item=items[index % len(items)],
                team_contact=ctx.contact(index),
                remarks=f'{DEMO_TAG} Testbooking',
                start_date=ctx.today + timedelta(days=index % 3),
                start_time=time(9, 0),
                end_date=ctx.today + timedelta(days=(index % 3) + 1),
                end_time=time(16, 0),
                status=ctx.status(index),
            )

    def reset(self) -> None:
        FotoBooking.objects.filter(remarks__startswith=DEMO_TAG).delete()
        FotoItem.objects.filter(name__startswith=DEMO_TAG).delete()

    def report(self, ctx: DemoContext) -> str:
        items = self.count(FotoItem, field='name')
        bookings = self.count(FotoBooking)
        return f'{items} varer, {bookings} bookinger'


FACTORY = FotoDemoFactory
