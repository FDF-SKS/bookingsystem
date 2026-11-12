from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from organization.permissions import (
    StaffRequiredMixin,
    TeamQuerysetMixin,
    restrict_team_field,
)

from .forms import DepotBookingForm, DepotItemForm
from .models import DepotBooking, DepotItem


class DepotItemListView(LoginRequiredMixin, ListView):
    """List all depot items."""
    model = DepotItem
    template_name = 'Depot/depot_item_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        # Single database query: select_related loads location data in one query
        # Client-side search handles filtering in JavaScript (no server round-trips)
        return DepotItem.objects.select_related('location').order_by('name')


class DepotItemDetailView(LoginRequiredMixin, DetailView):
    """View details of a specific depot item and its bookings."""
    model = DepotItem
    template_name = 'Depot/depot_item_detail.html'
    context_object_name = 'item'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        
        # Get all bookings for this item
        context['bookings'] = DepotBooking.objects.filter(item=item).select_related('team', 'team_contact')
        
        # Get upcoming bookings (approved only)
        context['upcoming_bookings'] = DepotBooking.objects.filter(
            item=item,
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


class DepotBookingListView(TeamQuerysetMixin, LoginRequiredMixin, ListView):
    """List all depot bookings with filtering."""
    model = DepotBooking
    template_name = 'Depot/depot_booking_list.html'
    context_object_name = 'bookings'
    paginate_by = 20

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = DepotBooking.STATUS_CHOICES
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_team'] = self.request.GET.get('team', '')
        context['selected_item'] = self.request.GET.get('item', '')
        return context


class DepotBookingDetailView(TeamQuerysetMixin, LoginRequiredMixin, DetailView):
    """View details of a specific booking."""
    model = DepotBooking
    template_name = 'Depot/depot_booking_detail.html'
    context_object_name = 'booking'


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


