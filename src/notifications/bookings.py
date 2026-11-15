"""Registry of the booking models that can trigger push notifications.

Each booking module keeps its own model, but they all share the same decision
workflow: ``status`` moves from ``Pending`` to ``Approved``/``Rejected`` and the
booking belongs to a team. Listing the models here lets one receiver handle all
of them instead of copying a signal into every app.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BookingSource:
    app_label: str
    model_name: str
    module_label: str
    detail_url_name: str
    item_attr: str = 'item'

    @property
    def label(self) -> str:
        return f'{self.app_label}.{self.model_name}'


BOOKING_SOURCES: tuple[BookingSource, ...] = (
    BookingSource(
        app_label='Sjak',
        model_name='SjakBooking',
        module_label='Sjak',
        detail_url_name='Sjak_SjakBooking_detail',
    ),
    BookingSource(
        app_label='Teknik',
        model_name='TeknikBooking',
        module_label='Teknik',
        detail_url_name='Teknik_TeknikBooking_detail',
    ),
    BookingSource(
        app_label='Foto',
        model_name='FotoBooking',
        module_label='Foto',
        detail_url_name='Foto_FotoBooking_detail',
    ),
    BookingSource(
        app_label='SOS',
        model_name='SOSBooking',
        module_label='SOS',
        detail_url_name='SOS_SOSBooking_detail',
    ),
    BookingSource(
        app_label='AktivitetsTeam',
        model_name='AktivitetsTeamBooking',
        module_label='AktivitetsTeam',
        detail_url_name='AktivitetsTeam_AktivitetsTeamBooking_detail',
    ),
    BookingSource(
        app_label='Depot',
        model_name='DepotBooking',
        module_label='Depot',
        detail_url_name='Depot_DepotBooking_detail',
    ),
    BookingSource(
        app_label='Butikken',
        model_name='ButikkenBooking',
        module_label='Butikken',
        detail_url_name='Butikken_ButikkenBooking_detail',
    ),
)

_BY_LABEL = {source.label: source for source in BOOKING_SOURCES}


def source_for(instance) -> BookingSource | None:
    """Return the registry entry for a model instance, if it is a booking."""
    return _BY_LABEL.get(instance._meta.label)
