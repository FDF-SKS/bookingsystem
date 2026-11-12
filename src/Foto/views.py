from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import generic

from organization.models import Event
from organization.permissions import StaffRequiredMixin, TeamQuerysetMixin

from . import forms, models


class FotoItemListView(LoginRequiredMixin,generic.ListView):
    model = models.FotoItem
    form_class = forms.FotoItemForm
    context_object_name = 'object_list'

    def get_queryset(self):
        queryset = models.FotoItem.objects.all().order_by('name')  # Order by the 'name' field
        return queryset



class FotoItemCreateView(LoginRequiredMixin, StaffRequiredMixin, generic.CreateView):
    model = models.FotoItem
    form_class = forms.FotoItemForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        self.item_id = kwargs.get('item_id')

        if event and event.deadline_foto < timezone.now().date():
            messages.error(request, 'Deadline for booking overskredet')
            return redirect('Foto_FotoBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)


    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        print(self.request.user)
        return kwargs




class FotoItemDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.FotoItem
    form_class = forms.FotoItemForm


class FotoItemUpdateView(StaffRequiredMixin, generic.UpdateView):
    model = models.FotoItem
    form_class = forms.FotoItemForm
    pk_url_kwarg = "pk"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        if event and event.deadline_foto < timezone.now().date():
            messages.error(request, 'Deadline for booking overskredet')
            return redirect('Foto_FotoBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)


class FotoItemDeleteView(LoginRequiredMixin, StaffRequiredMixin, generic.DeleteView):
    model = models.FotoItem
    success_url = reverse_lazy("Foto_FotoItem_list")

@login_required
@user_passes_test(lambda u: u.is_staff)
def approve_booking(request, pk):
    booking = get_object_or_404(models.FotoBooking, pk=pk)
    booking.status = 'Approved'
    booking.save()
    next_url = request.GET.get('next', 'Foto_FotoBooking_list')
    return redirect(next_url)

@login_required
@user_passes_test(lambda u: u.is_staff)
def reject_booking(request, pk):
    booking = get_object_or_404(models.FotoBooking, pk=pk)
    booking.status = 'Rejected'
    booking.save()
    next_url = request.GET.get('next', 'Foto_FotoBooking_list')
    return redirect(next_url)


class FotoBookingListView(LoginRequiredMixin, TeamQuerysetMixin, generic.ListView):
    model = models.FotoBooking
    form_class = forms.FotoBookingForm


class FotoBookingCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.FotoBooking
    form_class = forms.FotoBookingForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        self.item_id = kwargs.get('item_id')

        # Fixed: Changed from deadline_aktivitetsteam to deadline_foto
        if event and event.deadline_foto < timezone.now().date():
            messages.error(request, 'Deadline for booking overskredet')
            return redirect('Foto_FotoBooking_list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # ADD THIS: This pre-selects the camera/item in the dropdown
        if self.item_id:
            item = get_object_or_404(models.FotoItem, id=self.item_id)
            kwargs.setdefault('initial', {})['item'] = item
            
        return kwargs

    def form_valid(self, form):
        # Save and redirect to detail view
        self.object = form.save()
        messages.success(self.request, 'Booking oprettet!')
        return redirect('Foto_FotoBooking_detail', pk=self.object.pk)


class FotoBookingDetailView(LoginRequiredMixin, TeamQuerysetMixin, generic.DetailView):
    model = models.FotoBooking
    form_class = forms.FotoBookingForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.contrib.contenttypes.models import ContentType
        from django_comments_xtd.models import XtdComment
        
        content_type = ContentType.objects.get_for_model(models.FotoBooking)
        context['comments'] = XtdComment.objects.filter(
            content_type=content_type,
            object_pk=str(self.object.pk),
            is_public=True
        ).select_related('user').order_by('-submit_date')
        context['content_type_id'] = content_type.id
        
        return context


class FotoBookingUpdateView(LoginRequiredMixin, TeamQuerysetMixin, generic.UpdateView):
    model = models.FotoBooking
    form_class = forms.FotoBookingForm
    pk_url_kwarg = "pk"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        if event and event.deadline_foto < timezone.now().date():
            messages.error(request, 'Deadline for booking overskredet')
            return redirect('Foto_FotoBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, 'Booking opdateret!')
        return redirect('Foto_FotoBooking_detail', pk=self.object.pk)


class FotoBookingDeleteView(LoginRequiredMixin, TeamQuerysetMixin, generic.DeleteView):
    model = models.FotoBooking
    success_url = reverse_lazy("Foto_FotoBooking_list")


