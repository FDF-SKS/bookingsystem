"""Framework behind the ``generate_dummy_data`` management command.

Every app takes part by adding a ``demo.py`` module with ``FACTORY`` set to a
``DemoFactory`` subclass. The command discovers those modules, so a new booking
type only needs its own factory - the command itself does not change.

A factory may create both "items" (the things that can be booked) and
"bookings" (the records pointing at them). Everything is matched by the
``[demo]`` marker, which makes the command safe to run twice: existing demo rows
are left alone, and ``--reset`` removes exactly the rows the command created.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO

from django.core.files.base import ContentFile

DEMO_TAG = '[demo]'
BOOKING_STATUSES = ('Pending', 'Approved', 'Pending', 'Rejected', 'Pending')
INTERNAL_STATUSES = ('Afventer', 'Igang', 'Klar', 'Afsluttet', 'Afventer')
DEMO_COLORS = ('#0d6efd', '#198754', '#fd7e14', '#6f42c1', '#20c997')


def demo_image(label: str, index: int) -> ContentFile:
    """Return a placeholder photo so galleries have something to show."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new('RGB', (800, 500), DEMO_COLORS[index % len(DEMO_COLORS)])
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=42)
    text = label.replace(DEMO_TAG, '').strip()[:26]
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(
        ((800 - (right - left)) / 2, (500 - (bottom - top)) / 2),
        text,
        fill='white',
        font=font,
    )
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return ContentFile(buffer.getvalue(), name='demo.png')


def attach_demo_image(instance, index: int) -> None:
    """Attach a placeholder image to ``instance`` if the model has one."""
    if getattr(instance, 'image', None):
        return
    instance.image.save(f'demo-{index + 1}.png', demo_image(instance.name, index), save=True)


def delete_demo_images(queryset) -> None:
    """Delete image files before their rows are removed.

    Django leaves the files on disk when a row is deleted; without this a
    repeated ``--reset`` would collect a new set of suffixed copies every time.
    """
    for instance in queryset:
        if getattr(instance, 'image', None):
            instance.image.delete(save=False)


@dataclass
class DemoContext:
    """Everything a factory needs to create consistent demo rows."""

    event: object
    teams: list
    volunteers: list
    per_model: int
    today: date
    verbosity: int = 1
    stdout: object | None = None

    @property
    def indexes(self):
        return range(self.per_model)

    def team(self, index: int):
        return self.teams[index % len(self.teams)]

    def contact(self, index: int):
        from organization.models import Volunteer

        team = self.team(index)
        return (
            Volunteer.objects.filter(teammembership__team=team, is_staff=True).first()
            or Volunteer.objects.filter(teammembership__team=team).first()
            or self.volunteers[index % len(self.volunteers)]
        )

    def status(self, index: int) -> str:
        return BOOKING_STATUSES[index % len(BOOKING_STATUSES)]

    def internal_status(self, index: int) -> str:
        return INTERNAL_STATUSES[index % len(INTERNAL_STATUSES)]

    def write(self, message: str) -> None:
        if not self.verbosity:
            return
        if self.stdout is not None:
            self.stdout.write(message)
        else:
            print(message)


class DemoFactory:
    """Base class for the per-app demo data factories."""

    label = '?'

    def create_items(self, ctx: DemoContext) -> None:
        """Create the things that can be booked."""

    def create_bookings(self, ctx: DemoContext) -> None:
        """Create bookings pointing at the items."""

    def reset(self) -> None:
        """Delete every row this factory created."""

    def report(self, ctx: DemoContext) -> str:
        """Return a one-line summary for the command output."""
        return ''

    def run(self, ctx: DemoContext) -> None:
        self.create_items(ctx)
        self.create_bookings(ctx)
        summary = self.report(ctx)
        if summary:
            ctx.write(f'  {self.label}: {summary}')

    @staticmethod
    def has_demo_rows(model, field: str = 'remarks', minimum: int = 1) -> bool:
        return model.objects.filter(**{f'{field}__startswith': DEMO_TAG}).count() >= minimum

    @staticmethod
    def count(model, field: str = 'remarks') -> int:
        return model.objects.filter(**{f'{field}__startswith': DEMO_TAG}).count()
