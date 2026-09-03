from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from datetime import datetime, time
from django.db.models import Q

def get_status_color(status):
    """Map booking status to Bootstrap color."""
    status_colors = {
        'Pending': 'warning',
        'Approved': 'success',
        'Rejected': 'danger',
        'Udleveret': 'info',
        # Danish equivalents
        'Afventer': 'warning',
        'Godkendt': 'success',
        'Afvist': 'danger',
        'Pakket': 'info',
    }
    return status_colors.get(status, 'secondary')

@login_required
def index(request):
    """Dashboard view showing combined timeline of all user bookings."""
    user = request.user
    now = timezone.now()
    
    # Fetch bookings from all modules for current user/team
    bookings = []
    
    # Get teams the user is a member of
    from organization.models import TeamMembership
    user_teams = TeamMembership.objects.filter(member=user).values_list('team_id', flat=True)
    
    # Sjak bookings
    from Sjak.models import SjakBooking
    sjak_bookings = SjakBooking.objects.filter(
        team_id__in=user_teams
    ).select_related('team', 'team_contact', 'assigned_sjak').exclude(
        start_date__lt=now.date()
    )
    for booking in sjak_bookings:
        bookings.append({
            'obj': booking,
            'type': 'Sjak',
            'icon': 'tools',
            'color': 'warning',
            'status_color': get_status_color(booking.status),
            'start': datetime.combine(booking.start_date, booking.start_time),
            'end': datetime.combine(booking.end_date, booking.end_time),
            'title': f"{booking.quantity} x {booking.item.name if booking.item else 'Ukendt'}",
            'url': f"/sjak/Sjak/SjakBooking/detail/{booking.pk}/",
        })
    
    # Teknik bookings
    from Teknik.models import TeknikBooking
    teknik_bookings = TeknikBooking.objects.filter(
        team_id__in=user_teams
    ).select_related('team', 'team_contact', 'item').exclude(
        start_date__lt=now.date()
    )
    for booking in teknik_bookings:
        bookings.append({
            'obj': booking,
            'type': 'Teknik',
            'icon': 'cpu',
            'color': 'tertiary',
            'status_color': get_status_color(booking.status),
            'start': datetime.combine(booking.start_date, booking.start_time),
            'end': datetime.combine(booking.end_date, booking.end_time),
            'title': f"{booking.quantity} x {booking.item.name if booking.item else 'Ukendt'}",
            'url': f"/teknik/Teknik/TeknikBooking/detail/{booking.pk}/",
        })
    
    # AktivitetsTeam bookings
    from AktivitetsTeam.models import AktivitetsTeamBooking
    aktivitet_bookings = AktivitetsTeamBooking.objects.filter(
        team_id__in=user_teams
    ).select_related('team', 'team_contact', 'item').exclude(
        start_date__lt=now.date()
    )
    for booking in aktivitet_bookings:
        bookings.append({
            'obj': booking,
            'type': 'AktivitetsTeam',
            'icon': 'universal-access',
            'color': 'success',
            'status_color': get_status_color(booking.status),
            'start': datetime.combine(booking.start_date, booking.start_time),
            'end': datetime.combine(booking.end_date, booking.end_time),
            'title': booking.item.name if booking.item else 'Aktivitet',
            'url': f"/aktivitetsteam/AktivitetsTeam/AktivitetsTeamBooking/detail/{booking.pk}/",
        })
    
    # Foto bookings
    from Foto.models import FotoBooking
    foto_bookings = FotoBooking.objects.filter(
        team_id__in=user_teams
    ).select_related('team', 'team_contact', 'item').exclude(
        start_date__lt=now.date()
    )
    for booking in foto_bookings:
        bookings.append({
            'obj': booking,
            'type': 'Foto',
            'icon': 'camera',
            'color': 'grey',
            'status_color': get_status_color(booking.status),
            'start': datetime.combine(booking.start_date, booking.start_time),
            'end': datetime.combine(booking.end_date, booking.end_time),
            'title': booking.item.name if booking.item else 'Foto',
            'url': f"/foto/Foto/FotoBooking/detail/{booking.pk}/",
        })
    
    # SOS bookings
    from SOS.models import SOSBooking
    sos_bookings = SOSBooking.objects.filter(
        team_id__in=user_teams
    ).select_related('team', 'team_contact', 'item').exclude(
        start_date__lt=now.date()
    )
    for booking in sos_bookings:
        bookings.append({
            'obj': booking,
            'type': 'SOS',
            'icon': 'heart-pulse',
            'color': 'danger',
            'status_color': get_status_color(booking.status),
            'start': datetime.combine(booking.start_date, booking.start_time),
            'end': datetime.combine(booking.end_date, booking.end_time),
            'title': booking.item.name if booking.item else 'SOS',
            'url': f"/sos/SOS/SOSBooking/detail/{booking.pk}/",
        })
    
    # Butikken: show Orders (parent objects) on the dashboard instead of per-item bookings
    from Butikken.models import ButikkenOrder
    butikken_orders = ButikkenOrder.objects.filter(
        team_id__in=user_teams,
    ).filter(
        Q(pickup_date__isnull=True) | Q(pickup_date__gte=now.date())
    ).select_related('team', 'team_contact')
    for order in butikken_orders:
        pickup_date = order.pickup_date or now.date()
        start_dt = datetime.combine(pickup_date, time(8, 0))
        bookings.append({
            'obj': order,
            'type': 'Butikken',
            'icon': 'shop',
            'color': 'secondary',
            'status_color': get_status_color(order.status),
            'start': start_dt,
            'end': None,
            'title': f"Bestilling {order.id} - {order.name or ''}",
            'url': f"/butikken/Butikken/ButikkenOrder/detail/{order.pk}/",
        })
    
    # VolunteerAppointments
    from organization.models import VolunteerAppointment
    appointments = VolunteerAppointment.objects.filter(
        requester=user
    ) | VolunteerAppointment.objects.filter(
        receiver=user
    )
    appointments = appointments.select_related('requester', 'receiver').exclude(
        start_date__lt=now.date()
    )
    for appointment in appointments:
        bookings.append({
            'obj': appointment,
            'type': 'Legeaftale',
            'icon': 'balloon-heart',
            'color': 'danger',
            'status_color': get_status_color(appointment.status),
            'start': datetime.combine(appointment.start_date, appointment.start_time),
            'end': datetime.combine(appointment.end_date, appointment.end_time),
            'title': f"{appointment.requester.get_full_name()} → {appointment.receiver.get_full_name()}",
            'url': f"/organization/appointment/{appointment.pk}/",
        })
    
    # Depot bookings
    from Depot.models import DepotBooking
    depot_bookings = DepotBooking.objects.filter(
        team_id__in=user_teams
    ).select_related('team', 'team_contact', 'item').exclude(
        start_date__lt=now.date()
    )
    for booking in depot_bookings:
        bookings.append({
            'obj': booking,
            'type': 'Depot',
            'icon': 'box-seam',
            'color': 'info',    
            'status_color': get_status_color(booking.status),
            'start': datetime.combine(booking.start_date, booking.start_time),
            'end': datetime.combine(booking.end_date, booking.end_time),
            'title': f"{booking.quantity} x {booking.item.name if booking.item else 'Depot'}",
            'url': f"/depot/bookings/{booking.pk}/",
        })
    
    # Sort by start time
    bookings.sort(key=lambda x: x['start'])
    
    # Group by date
    from itertools import groupby
    
    grouped_bookings = {}
    for date_key, items in groupby(bookings, key=lambda x: x['start'].date()):
        grouped_bookings[date_key] = list(items)
    
    # Sort grouped_bookings by date
    sorted_grouped_bookings = dict(sorted(grouped_bookings.items()))
    
    context = {
        'bookings': bookings,
        'grouped_bookings': sorted_grouped_bookings,
        'now': now.date(),
        'tomorrow': (now + timezone.timedelta(days=1)).date(),
    }
    
    return render(request, 'index.html', context)


