from django.views import generic
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from . import models
from . import forms

from django.contrib import messages
from organization.models import EventMembership, Event
from django.utils import timezone
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from geopy.geocoders import Nominatim

@login_required
@user_passes_test(lambda u: u.is_staff)
def approve_booking(request, pk):
    booking = get_object_or_404(models.TeknikBooking, pk=pk)
    booking.status = 'Approved'
    booking.save()
    next_url = request.GET.get('next', 'Teknik_TeknikBooking_list')
    return redirect(next_url)

@login_required
@user_passes_test(lambda u: u.is_staff)
def reject_booking(request, pk):
    booking = get_object_or_404(models.TeknikBooking, pk=pk)
    booking.status = 'Rejected'
    booking.save()
    next_url = request.GET.get('next', 'Teknik_TeknikBooking_list')
    return redirect(next_url)


class TeknikBookingListView(LoginRequiredMixin, generic.ListView):
    model = models.TeknikBooking
    form_class = forms.TeknikBookingForm
    context_object_name = 'object_list'
    template_name = 'Teknik/teknikbooking_list.html'
    paginate_by = 16

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        """Return bookings but defer the `location` field to avoid map_location
        conversion errors when stored values are malformed in the DB.
        """
        return models.TeknikBooking.objects.select_related(
            'team', 'team_contact', 'item'
        ).defer('location').order_by('item', 'start_date')

    def get_context_data(self, **kwargs):
        """Provide context variables matching the Sjak list view so the
        template can be reused 1:1.
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Fetch the user's team membership
        user_team_membership = user.teammembership_set.select_related('team').first()
        is_staff = user.is_staff

        # Filter the object list based on the user's team membership and staff status
        object_list = context.get('object_list', [])
        if is_staff:
            filtered_object_list = object_list
        else:
            filtered_object_list = [
                obj for obj in object_list
                if user_team_membership and obj.team == user_team_membership.team
            ]

        # Fetch user events (deadline_teknik)
        user_events = list(user.events.filter(is_active=True).values('name', 'deadline_teknik'))

        # Fetch volunteer team memberships
        volunteer_team_memberships = list(user.teammembership_set.select_related('team').values('team__name'))

        context.update({
            'filtered_object_list': filtered_object_list,
            'is_staff': is_staff,
            'user_team_membership': user_team_membership,
            'user_events': user_events,
            'volunteer_team_memberships': volunteer_team_memberships,
            'current_sort': self.request.GET.get('sort', 'item'),
        })

        return context



class TeknikBookingCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.TeknikBooking
    form_class = forms.TeknikBookingForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        self.item_id = kwargs.get('item_id')
        
        if not self.request.user.is_staff and event and event.deadline_teknik < timezone.now().date():
            messages.error(request, 'booking deadline overskredet')
            return redirect('Teknik_TeknikBooking_list')  # replace with the name of your list view url
        
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        if self.item_id:
            item = get_object_or_404(models.TeknikItem, id=self.item_id)
            kwargs['initial'] = {'item': item}
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = models.TeknikItem.objects.all()
            # Check if self.object exists
        if hasattr(self, 'object') and self.object is not None:
            context['object_dict'] = self.object.to_dict()
        else:
            context['items'] = items
        return context

class TeknikBookingDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.TeknikBooking
    form_class = forms.TeknikBookingForm

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django_comments_xtd.models import XtdComment
        from django.contrib.contenttypes.models import ContentType
        
        context['object_dict'] = self.object.to_dict()
        
        content_type = ContentType.objects.get_for_model(models.TeknikBooking)
        context['comments'] = XtdComment.objects.filter(
            content_type=content_type,
            object_pk=str(self.object.pk),
            is_public=True
        ).select_related('user').order_by('-submit_date')
        context['content_type_id'] = content_type.id
        
        return context


class TeknikBookingUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.TeknikBooking
    form_class = forms.TeknikBookingForm
    pk_url_kwarg = "pk"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        if not self.request.user.is_staff and event and event.deadline_teknik < timezone.now().date():
            messages.error(request, 'booking deadline overskredet')
            return redirect('Teknik_TeknikBooking_list')  # replace with the name of your list view url
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
        
        # Add the following lines to ensure related fields are initialized
        form.fields["team"].initial = form.instance.team
        form.fields["item"].initial = form.instance.item
        form.fields["team_contact"].initial = form.instance.team_contact
        return form
        
        self.object.save()
        messages.success(self.request, 'Booking updated successfully')
        return redirect('Teknik_TeknikBooking_detail', pk=self.object.pk)
    
    def form_invalid(self, form):
        messages.error(self.request, 'There was an error updating the booking')
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = self.get_object()
        context['object_dict'] = instance.to_dict()  # Ensure your model has a to_dict method
        return context

class TeknikBookingDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.TeknikBooking
    success_url = reverse_lazy("Teknik_TeknikBooking_list")

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class TeknikItemListView(LoginRequiredMixin, generic.ListView):
    model = models.TeknikItem
    form_class = forms.TeknikItemForm
    context_object_name = 'object_list'

    def get_queryset(self):
        queryset = models.TeknikItem.objects.all().order_by('name')  # Order by the 'name' field
        return queryset


class TeknikItemCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.TeknikItem
    form_class = forms.TeknikItemForm


class TeknikItemDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.TeknikItem
    form_class = forms.TeknikItemForm


class TeknikItemUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.TeknikItem
    form_class = forms.TeknikItemForm
    pk_url_kwarg = "pk"


class TeknikItemDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.TeknikItem
    success_url = reverse_lazy("Teknik_TeknikItem_list")


class TeknikTypeListView(LoginRequiredMixin, generic.ListView):
    model = models.TeknikType
    form_class = forms.TeknikTypeForm


class TeknikTypeCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.TeknikType
    form_class = forms.TeknikTypeForm


class TeknikTypeDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.TeknikType
    form_class = forms.TeknikTypeForm


class TeknikTypeUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.TeknikType
    form_class = forms.TeknikTypeForm
    pk_url_kwarg = "pk"


class TeknikTypeDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.TeknikType
    success_url = reverse_lazy("Teknik_TeknikType_list")


