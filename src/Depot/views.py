from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from organization.models import Team
from organization.permissions import (
    StaffRequiredMixin,
    TeamQuerysetMixin,
    restrict_team_field,
    scope_to_user_teams,
)
from utils.ui import (
    BookingDetailContextMixin,
    BookingListContextMixin,
    ItemDetailContextMixin,
    ItemListContextMixin,
)

from .forms import DepotBookingForm, DepotItemForm
from .models import DepotBooking, DepotItem


@login_required
@user_passes_test(lambda u: u.is_staff)
def approve_booking(request, pk):
    """Approve a depot booking."""
    booking = get_object_or_404(DepotBooking, pk=pk)
    booking.status = 'Approved'
    booking.save()
    return redirect(request.GET.get('next', 'Depot_DepotBooking_list'))


@login_required
@user_passes_test(lambda u: u.is_staff)
def reject_booking(request, pk):
    """Reject a depot booking."""
    booking = get_object_or_404(DepotBooking, pk=pk)
    booking.status = 'Rejected'
    booking.save()
    return redirect(request.GET.get('next', 'Depot_DepotBooking_list'))


class DepotItemListView(ItemListContextMixin, LoginRequiredMixin, ListView):
    """List all depot items."""
    model = DepotItem
    template_name = 'Depot/depot_item_list.html'
    context_object_name = 'object_list'

    item_list_title = "Depot katalog"
    item_list_subtitle = "Oversigt over alle lagervarer."
    item_list_create_url_name = "Depot_DepotItem_create"
    item_list_create_label = "Tilføj genstand"
    item_list_detail_url_name = "Depot_DepotItem_detail"
    item_list_update_url_name = "Depot_DepotItem_update"
    item_list_delete_url_name = "Depot_DepotItem_delete"
    item_list_icon = "bi-box-seam"
    item_list_empty_title = "Ingen varer fundet"
    item_list_empty_message = "Der er endnu ingen depot varer i kataloget."

    def get_queryset(self):
        # Single database query: select_related loads location data in one query
        # Client-side search handles filtering in JavaScript (no server round-trips)
        return DepotItem.objects.select_related('location').order_by('name')


class DepotItemDetailView(ItemDetailContextMixin, LoginRequiredMixin, DetailView):
    """View details of a specific depot item and its bookings."""
    model = DepotItem
    template_name = 'Depot/depot_item_detail.html'

    item_detail_catalog_label = "Depot Katalog"
    item_detail_list_url_name = "Depot_DepotItem_list"
    item_detail_badge_label = "Vare nr."
    item_detail_icon = "bi-box-seam"
    item_detail_quantity_label = "Lagerbeholdning"
    item_detail_footer_text = "Information fra Depot Katalog"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Kun bookinger for brugerens egne teams; staff ser alt. Ellers kan en
        # almindelig bruger se andre holds bookinger via vare-detaljesiden.
        bookings = scope_to_user_teams(
            DepotBooking.objects.filter(item=self.object).select_related(
                'team', 'team_contact'
            ),
            self.request.user,
        )
        context['bookings'] = bookings

        # Get upcoming bookings (approved only)
        context['upcoming_bookings'] = bookings.filter(
            status='Approved'
        ).order_by('start_date')

        return context


class DepotItemCreateView(StaffRequiredMixin, LoginRequiredMixin, CreateView):
    """Create a new depot item."""
    model = DepotItem
    form_class = DepotItemForm
    template_name = 'Depot/depot_item_form.html'
    success_url = reverse_lazy('Depot_DepotItem_list')


class DepotItemUpdateView(StaffRequiredMixin, LoginRequiredMixin, UpdateView):
    """Update a depot item."""
    model = DepotItem
    form_class = DepotItemForm
    template_name = 'Depot/depot_item_form.html'
    success_url = reverse_lazy('Depot_DepotItem_list')


class DepotItemDeleteView(StaffRequiredMixin, LoginRequiredMixin, DeleteView):
    """Delete a depot item."""
    model = DepotItem
    template_name = 'Depot/depot_item_confirm_delete.html'
    success_url = reverse_lazy('Depot_DepotItem_list')


class DepotBookingListView(BookingListContextMixin, TeamQuerysetMixin, LoginRequiredMixin, ListView):
    """List all depot bookings with filtering."""
    model = DepotBooking
    template_name = 'Depot/depot_booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 20

    booking_list_title = "Depot bookinger"
    booking_list_create_url_name = "Depot_DepotBooking_create"
    booking_list_create_label = "Ny booking"
    booking_list_mobile_create_label = "Ny Depot booking"
    booking_list_approve_url_name = "Depot_DepotBooking_approve"
    booking_list_reject_url_name = "Depot_DepotBooking_reject"
    booking_list_update_url_name = "Depot_DepotBooking_update"
    booking_list_delete_url_name = "Depot_DepotBooking_delete"

    def get_queryset(self):
        queryset = super().get_queryset().select_related('item', 'team', 'team_contact')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by team
        team = self.request.GET.get('team')
        if team:
            queryset = queryset.filter(team__id=team)
        
        # Filter by item
        item = self.request.GET.get('item')
        if item:
            queryset = queryset.filter(item__id=item)
        
        return queryset.order_by('-created_at')

    def get_booking_list_subtitle(self) -> str:
        membership = self.request.user.teammembership_set.select_related('team').first()
        return f"Team: {membership.team.name}" if membership else ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = DepotBooking.STATUS_CHOICES
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_team'] = self.request.GET.get('team', '')
        context['selected_item'] = self.request.GET.get('item', '')
        context['filter_items'] = DepotItem.objects.all().order_by('name')
        if self.request.user.is_staff:
            context['filter_teams'] = Team.objects.all().order_by('name')
        else:
            context['filter_teams'] = Team.objects.filter(
                teammembership__member=self.request.user
            ).order_by('name')
        return context


class DepotBookingDetailView(BookingDetailContextMixin, TeamQuerysetMixin, LoginRequiredMixin, DetailView):
    """View details of a specific booking."""
    model = DepotBooking
    template_name = 'Depot/depot_booking_detail.html'

    booking_detail_kicker = "Depot booking"
    booking_detail_list_url_name = "Depot_DepotBooking_list"
    booking_detail_list_label = "Depot bookinger"
    booking_detail_approve_url_name = "Depot_DepotBooking_approve"
    booking_detail_reject_url_name = "Depot_DepotBooking_reject"
    booking_detail_delete_url_name = "Depot_DepotBooking_delete"
    booking_detail_show_comments = False

    def get_queryset(self):
        return super().get_queryset().select_related('item', 'team', 'team_contact')


class DepotBookingCreateView(LoginRequiredMixin, CreateView):
    """Create a new depot booking."""
    model = DepotBooking
    form_class = DepotBookingForm
    template_name = 'Depot/depot_booking_form.html'
    success_url = reverse_lazy('Depot_DepotBooking_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        restrict_team_field(self.request.user, form.fields['team'], form.fields['team_contact'])
        return form


class DepotBookingUpdateView(TeamQuerysetMixin, LoginRequiredMixin, UpdateView):
    """Update a depot booking."""
    model = DepotBooking
    form_class = DepotBookingForm
    template_name = 'Depot/depot_booking_form.html'
    success_url = reverse_lazy('Depot_DepotBooking_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        restrict_team_field(self.request.user, form.fields['team'], form.fields['team_contact'])
        return form


class DepotBookingDeleteView(TeamQuerysetMixin, LoginRequiredMixin, DeleteView):
    """Delete a depot booking."""
    model = DepotBooking
    template_name = 'Depot/depot_booking_confirm_delete.html'
    success_url = reverse_lazy('Depot_DepotBooking_list')


