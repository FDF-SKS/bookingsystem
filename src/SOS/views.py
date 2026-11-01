from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import generic

from organization.models import Event  # Import the Event model

from . import forms, models


class SOSBookingListView(generic.ListView):
    model = models.SOSBooking
    form_class = forms.SOSBookingForm

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


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


class SOSBookingDetailView(generic.DetailView):
    model = models.SOSBooking
    form_class = forms.SOSBookingForm

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class SOSBookingUpdateView(generic.UpdateView):
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

class SOSBookingDeleteView(generic.DeleteView):
    model = models.SOSBooking
    success_url = reverse_lazy("SOS_SOSBooking_list")

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class SOSItemListView(generic.ListView):
    model = models.SOSItem
    form_class = forms.SOSItemForm
    context_object_name = 'object_list'

    def get_queryset(self):
        queryset = models.SOSItem.objects.all().order_by('name')  # Order by the 'name' field
        return queryset


class SOSItemCreateView(generic.CreateView):
    model = models.SOSItem
    form_class = forms.SOSItemForm


class SOSItemDetailView(generic.DetailView):
    model = models.SOSItem
    form_class = forms.SOSItemForm


class SOSItemUpdateView(generic.UpdateView):
    model = models.SOSItem
    form_class = forms.SOSItemForm
    pk_url_kwarg = "pk"


class SOSItemDeleteView(generic.DeleteView):
    model = models.SOSItem
    success_url = reverse_lazy("SOS_SOSItem_list")


class SOSTypeListView(generic.ListView):
    model = models.SOSType
    form_class = forms.SOSTypeForm


class SOSTypeCreateView(generic.CreateView):
    model = models.SOSType
    form_class = forms.SOSTypeForm


class SOSTypeDetailView(generic.DetailView):
    model = models.SOSType
    form_class = forms.SOSTypeForm


class SOSTypeUpdateView(generic.UpdateView):
    model = models.SOSType
    form_class = forms.SOSTypeForm
    pk_url_kwarg = "pk"


class SOSTypeDeleteView(generic.DeleteView):
    model = models.SOSType
    success_url = reverse_lazy("SOS_SOSType_list")


