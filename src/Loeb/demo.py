"""Demo data for the Loeb app (løb, poster og hold)."""

from Loeb.models import Hold, Loeb, Task
from utils.demo import DEMO_TAG, DemoContext, DemoFactory


class LoebDemoFactory(DemoFactory):
    label = 'Løb'

    def create_items(self, ctx: DemoContext) -> None:
        for index in ctx.indexes:
            loeb, created = Loeb.objects.get_or_create(
                name=f'{DEMO_TAG} Løb {index + 1}',
                defaults={
                    'team': ctx.team(index),
                    'event': ctx.event,
                    'description': 'Demoløb med to poster og to hold.',
                    'is_active': True,
                    'show_map': True,
                    'show_points': True,
                },
            )
            if not created:
                continue
            for number in (1, 2):
                Task.objects.create(
                    loeb=loeb,
                    title=f'Demo-post {number}',
                    task_type='physical' if number % 2 else 'qr',
                    points=10 * number,
                    is_published=True,
                    order=number,
                )
            for number in (1, 2):
                Hold.objects.create(
                    loeb=loeb,
                    name=f'Demo-hold {number}',
                    pin_code=f'{1000 + index * 10 + number}',
                )

    def reset(self) -> None:
        Loeb.objects.filter(name__startswith=DEMO_TAG).delete()

    def report(self, ctx: DemoContext) -> str:
        loebs = self.count(Loeb, field='name')
        tasks = Task.objects.filter(loeb__name__startswith=DEMO_TAG).count()
        holds = Hold.objects.filter(loeb__name__startswith=DEMO_TAG).count()
        return f'{loebs} løb, {tasks} poster, {holds} hold'


FACTORY = LoebDemoFactory
