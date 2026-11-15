from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import generic

from organization.models import Event  # Import the Event model
from organization.permissions import StaffRequiredMixin, TeamQuerysetMixin
from utils.ui import (
    BookingDetailContextMixin,
    BookingListContextMixin,
    ItemDetailContextMixin,
    ItemListContextMixin,
)

from . import forms, models


@login_required
@user_passes_test(lambda u: u.is_staff)
def approve_booking(request, pk):
    """Approve an SOS booking."""
    booking = get_object_or_404(models.SOSBooking, pk=pk)
    booking.status = 'Approved'
    booking.save()
    return redirect(request.GET.get('next', 'SOS_SOSBooking_list'))


@login_required
@user_passes_test(lambda u: u.is_staff)
def reject_booking(request, pk):
    """Reject an SOS booking."""
    booking = get_object_or_404(models.SOSBooking, pk=pk)
    booking.status = 'Rejected'
    booking.save()
    return redirect(request.GET.get('next', 'SOS_SOSBooking_list'))


class SOSBookingListView(BookingListContextMixin, TeamQuerysetMixin, generic.ListView):
    model = models.SOSBooking
    form_class = forms.SOSBookingForm

    booking_list_title = "SOS bookinger"
    booking_list_create_url_name = "SOS_SOSBooking_create"
    booking_list_create_label = "Ny booking"
    booking_list_mobile_create_label = "Ny SOS bestilling"
    booking_list_approve_url_name = "SOS_SOSBooking_approve"
    booking_list_reject_url_name = "SOS_SOSBooking_reject"
    booking_list_update_url_name = "SOS_SOSBooking_update"
    booking_list_delete_url_name = "SOS_SOSBooking_delete"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().select_related('team', 'team_contact', 'item')

    def get_booking_list_subtitle(self) -> str:
        membership = self.request.user.teammembership_set.select_related('team').first()
        return f"Team: {membership.team.name}" if membership else ""

    def get_booking_list_deadline(self) -> str:
        event = Event.objects.filter(is_active=True).first()
        return str(event.deadline_sos) if event and event.deadline_sos else ""


class SOSBookingCreateView(generic.CreateView):
    model = models.SOSBooking
    form_class = forms.SOSBookingForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        if event and event.deadline_sos < timezone.now().date():
            messages.error(request, 'Booking is closed.')
            return redirect('SOS_SOSBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class SOSBookingDetailView(BookingDetailContextMixin, TeamQuerysetMixin, generic.DetailView):
    model = models.SOSBooking
    form_class = forms.SOSBookingForm

    booking_detail_kicker = "SOS booking"
    booking_detail_list_url_name = "SOS_SOSBooking_list"
    booking_detail_list_label = "SOS bookinger"
    booking_detail_approve_url_name = "SOS_SOSBooking_approve"
    booking_detail_reject_url_name = "SOS_SOSBooking_reject"
    booking_detail_show_comments = False

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().select_related('item', 'team', 'team_contact')


class SOSBookingUpdateView(TeamQuerysetMixin, generic.UpdateView):
    model = models.SOSBooking
    form_class = forms.SOSBookingForm
    pk_url_kwarg = "pk"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        if event and event.deadline_sos < timezone.now().date():
            messages.error(request, 'Booking is closed.')
            return redirect('SOS_SOSBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        return obj

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.instance = self.get_object()  # Pre-populate the form with object's values
        return form


class SOSBookingDeleteView(TeamQuerysetMixin, generic.DeleteView):
    model = models.SOSBooking
    success_url = reverse_lazy("SOS_SOSBooking_list")

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class SOSItemListView(ItemListContextMixin, LoginRequiredMixin, generic.ListView):
    model = models.SOSItem
    form_class = forms.SOSItemForm
    context_object_name = 'object_list'

    item_list_title = "SOS katalog"
    item_list_subtitle = "Oversigt over udstyr og materialer i SOS-kataloget."
    item_list_create_url_name = "SOS_SOSItem_create"
    item_list_create_label = "Tilføj genstand"
    item_list_detail_url_name = "SOS_SOSItem_detail"
    item_list_update_url_name = "SOS_SOSItem_update"
    item_list_delete_url_name = "SOS_SOSItem_delete"
    item_list_icon = "bi-life-preserver"
    item_list_show_location = False
    item_list_show_quantity = False
    item_list_empty_title = "Ingen SOS-varer fundet"
    item_list_empty_message = "Der er endnu ingen varer i SOS-kataloget."

    def get_queryset(self):
        queryset = models.SOSItem.objects.all().order_by('name')  # Order by the 'name' field
        return queryset


class SOSItemCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.SOSItem
    form_class = forms.SOSItemForm


class SOSItemDetailView(ItemDetailContextMixin, LoginRequiredMixin, generic.DetailView):
    model = models.SOSItem
    form_class = forms.SOSItemForm

    item_detail_catalog_label = "SOS katalog"
    item_detail_list_url_name = "SOS_SOSItem_list"
    item_detail_badge_label = "Genstand nr."
    item_detail_icon = "bi-life-preserver"
    item_detail_footer_text = "Information fra SOS-kataloget"


class SOSItemUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.SOSItem
    form_class = forms.SOSItemForm
    pk_url_kwarg = "pk"


class SOSItemDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.SOSItem
    success_url = reverse_lazy("SOS_SOSItem_list")


class SOSTypeListView(LoginRequiredMixin, generic.ListView):
    model = models.SOSType
    form_class = forms.SOSTypeForm


class SOSTypeCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.SOSType
    form_class = forms.SOSTypeForm


class SOSTypeDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.SOSType
    form_class = forms.SOSTypeForm


class SOSTypeUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.SOSType
    form_class = forms.SOSTypeForm
    pk_url_kwarg = "pk"


class SOSTypeDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.SOSType
    success_url = reverse_lazy("SOS_SOSType_list")
