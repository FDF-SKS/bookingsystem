from multiprocessing import context
from django.views import generic
from django.shortcuts import render
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import F
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
import logging
logger = logging.getLogger(__name__)


# views.py
class AktivitetsTeamItemListView(LoginRequiredMixin, generic.ListView):
    model = models.AktivitetsTeamItem
    context_object_name = 'object_list'

    def get_queryset(self):
        # Use select_related to join the category table efficiently
        queryset = models.AktivitetsTeamItem.objects.filter(is_active=True).select_related('category').order_by('name')
        
        # Filter by the slug of the category
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pull all types from the DB for the filter buttons
        context['categories'] = models.AktivitetsTeamItemType.objects.all()
        context['current_category'] = self.request.GET.get('category', '')
        return context


class AktivitetsTeamItemCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.AktivitetsTeamItem
    form_class = forms.AktivitetsTeamItemForm


class AktivitetsTeamItemDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.AktivitetsTeamItem
    form_class = forms.AktivitetsTeamItemForm


class AktivitetsTeamItemUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.AktivitetsTeamItem
    form_class = forms.AktivitetsTeamItemForm
    pk_url_kwarg = "pk"


class AktivitetsTeamItemDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.AktivitetsTeamItem
    success_url = reverse_lazy("AktivitetsTeam_AktivitetsTeamItem_list")


@login_required
@user_passes_test(lambda u: u.is_staff)
def approve_booking(request, pk):
    booking = get_object_or_404(models.AktivitetsTeamBooking, pk=pk)
    booking.status = 'Approved'
    booking.save()
    next_url = request.GET.get('next', 'AktivitetsTeam_AktivitetsTeamBooking_list')
    return redirect(next_url)

@login_required
@user_passes_test(lambda u: u.is_staff)
def reject_booking(request, pk):
    booking = get_object_or_404(models.AktivitetsTeamBooking, pk=pk)
    booking.status = 'Rejected'
    booking.save()
    next_url = request.GET.get('next', 'AktivitetsTeam_AktivitetsTeamBooking_list')
    return redirect(next_url)


def gantt_chart_view(request):
    bookings = models.AktivitetsTeamBooking.objects.all()
    tasks = [
        {
            'id': booking.id,
            'label': booking.item.name,
            'from': booking.start_date.isoformat(),
            'to': booking.end_date.isoformat()
        }
        for booking in bookings
    ]
    time_ranges = []  # Add your time ranges if needed
    return render(request, 'gantt_chart.html', {'tasks': tasks, 'time_ranges': time_ranges})

import json
import logging
from datetime import datetime, timedelta, time
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic

import json
from django.core.serializers.json import DjangoJSONEncoder

class TimelinePreviewMixin:
    """Provides timeline data for booking forms."""
    def get_timeline_context(self):
        active_event = Event.objects.filter(is_active=True).first()
        if not active_event:
            return {}

        # 1. Base timeline config
        t_start = datetime.combine(active_event.start_date, time.min)
        
        # 2. Get all bookings for the event to check for conflicts
        # We exclude the current object if we are in UpdateView
        existing_qs = models.AktivitetsTeamBooking.objects.filter(
            start_date__gte=active_event.start_date,
            end_date__lte=active_event.end_date
        )
        
        if hasattr(self, 'object') and self.object:
            existing_qs = existing_qs.exclude(pk=self.object.pk)

        # Prepare a list of simple dicts for JS
        bookings_data = []
        for b in existing_qs.select_related('item'):
            bookings_data.append({
                'item_id': b.item_id,
                'start': datetime.combine(b.start_date, b.start_time).isoformat(),
                'end': datetime.combine(b.end_date, b.end_time).isoformat(),
                'team': b.team.name if b.team else "Booking",
                'status': b.status.lower(),  # ADD THIS LINE
            })

        return {
            'timeline_start_iso': t_start.isoformat(),
            'existing_bookings_json': json.dumps(bookings_data, cls=DjangoJSONEncoder),
            'hour_width': 30,
        }
    
logger = logging.getLogger(__name__)
class AktivitetsTeamBookingListView(LoginRequiredMixin, generic.ListView):
    model = models.AktivitetsTeamBooking
    context_object_name = 'object_list'
    template_name = 'AktivitetsTeam/AktivitetsTeamBooking_list.html'
    paginate_by = 16

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            queryset = models.AktivitetsTeamBooking.objects.all()
        else:
            queryset = models.AktivitetsTeamBooking.objects.filter(
                team__in=user.teammembership_set.values('team')
            )
        
        queryset = queryset.select_related(
            'team', 'team_contact', 'item'
        ).only(
            'id', 'team_id', 'team_contact_id', 'start_date', 'start_time', 
            'end_date', 'end_time', 'item_id', 'status', 'remarks'
        ).order_by('start_date', 'start_time')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_event = Event.objects.filter(is_active=True).first()
        if not active_event: return context

        timeline_start = datetime.combine(active_event.start_date, time.min)
        timeline_end = datetime.combine(active_event.end_date, time.max)
        total_duration = timeline_end - timeline_start
        total_hours = int(total_duration.total_seconds() / 3600) + 1

        # 2. Get resources and bookings
        items = models.AktivitetsTeamItem.objects.filter(is_active=True)
        item_rows = []
        all_bookings = list(self.get_queryset().filter(
            start_date__gte=active_event.start_date,
            end_date__lte=active_event.end_date
        ).select_related('item', 'team'))

        for item in items:
            row_bookings = []
            item_bookings = [b for b in all_bookings if b.item_id == item.id]
            item_bookings.sort(key=lambda x: datetime.combine(x.start_date, x.start_time))
            
            levels_end_times = []
            
            for b in item_bookings:
                b_start = datetime.combine(b.start_date, b.start_time)
                b_end = datetime.combine(b.end_date, b.end_time)

                # Collision detection for stacking lanes
                level = 0
                assigned = False
                for idx, last_end_time in enumerate(levels_end_times):
                    if b_start >= last_end_time:
                        level = idx
                        levels_end_times[idx] = b_end
                        assigned = True
                        break
                
                if not assigned:
                    level = len(levels_end_times)
                    levels_end_times.append(b_end)

                offset_hours = (b_start - timeline_start).total_seconds() / 3600
                duration_hours = (b_end - b_start).total_seconds() / 3600

                row_bookings.append({
                    'id': b.id,
                    'team_name': b.team.name if b.team else "Booking",
                    'left_val': "{:.2f}".format(offset_hours),
                    'width_val': "{:.2f}".format(duration_hours),
                    'level': level,
                    'status': b.status.lower() if b.status else 'pending',
                    'hover_content': (
                        f"<strong>{item.name}</strong><br>"
                        f"<strong>Fra:</strong> {b.start_date.strftime('%d. %b')} kl {b.start_time.strftime('%H:%M')}<br>"
                        f"<strong>Til:</strong> {b.end_date.strftime('%d. %b')} kl {b.end_time.strftime('%H:%M')}<br>"
                        f"<strong>Team:</strong> {b.team.name if b.team else 'N/A'}<br>"
                        f"<strong>Status:</strong> {b.status.capitalize()}<br>"
                        f"<hr class='my-1'>"
                        f"<em>{b.remarks or 'Ingen beskrivelse'}</em>"
                    )
                })
            
            item_rows.append({
                'id': item.id,  # CRITICAL for JS currentItemId
                'name': item.name,
                'bookings': row_bookings,
                'num_levels': len(levels_end_times) or 1
            })

        # 3. Header data
        hours_list = []
        for h in range(total_hours):
            current_dt = timeline_start + timedelta(hours=h)
            hours_list.append({
                'label': current_dt.strftime('%H'),
                'is_new_day': current_dt.hour == 0,
                'day_label': current_dt, # Passed as object for |date:"D. j" filter
            })

        context.update({
            'item_rows': item_rows,
            'hours_list': hours_list,
            'hour_width': 40,
            'timeline_start_iso': timeline_start.strftime('%Y-%m-%dT%H:%M:%S'),
        })
        return context

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    


class AktivitetsTeamBookingCreateView(LoginRequiredMixin, TimelinePreviewMixin, generic.CreateView):

    model = models.AktivitetsTeamBooking
    form_class = forms.AktivitetsTeamBookingForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        self.item_id = kwargs.get('item_id')

        if event and event.deadline_aktivitetsteam < timezone.now().date():
            messages.error(request, 'Deadline for booking overskredet')
            return redirect('AktivitetsTeam_AktivitetsTeamBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        if self.item_id:
            item = get_object_or_404(models.AktivitetsTeamItem, id=self.item_id)
            kwargs['initial'] = {'item': item}
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        
        # 1. Handle drag-and-drop parameters from the timeline
        if 'item' in self.request.GET:
            initial['item'] = self.request.GET.get('item')
            initial['start_date'] = self.request.GET.get('start_date')
            initial['start_time'] = self.request.GET.get('start_time')
            initial['end_date'] = self.request.GET.get('end_date')
            initial['end_time'] = self.request.GET.get('end_time')
        
        # 2. Support for item_id passed via URL path (kwargs)
        elif self.item_id:
            initial['item'] = self.item_id
            
        return initial

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add timeline data
        context.update(self.get_timeline_context())
        aktivitetsteam_items = models.AktivitetsTeamItem.objects.all()
        return context



class AktivitetsTeamBookingUpdateView(LoginRequiredMixin, TimelinePreviewMixin, generic.UpdateView):
    model = models.AktivitetsTeamBooking
    form_class = forms.AktivitetsTeamBookingForm
    pk_url_kwarg = "pk"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        if event and event.deadline_aktivitetsteam < timezone.now().date():
            messages.error(request, 'Deadline for booking overskredet')
            return redirect('AktivitetsTeam_AktivitetsTeamBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.instance = self.get_object()  # Pre-populate the form with object's values
        
        # Add the following lines to ensure related fields are initialized
        form.fields["team"].initial = form.instance.team
        form.fields["item"].initial = form.instance.item
        form.fields["team_contact"].initial = form.instance.team_contact
        
        return form

    def form_invalid(self, form):
        messages.error(self.request, 'There was an error updating the booking')
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add timeline data
        context.update(self.get_timeline_context())
        instance = self.get_object()
        context['object_dict'] = instance.to_dict()
        return context



class AktivitetsTeamBookingDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.AktivitetsTeamBooking
    form_class = forms.AktivitetsTeamBookingForm

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django_comments_xtd.models import XtdComment
        from django.contrib.contenttypes.models import ContentType
        
        context['object_dict'] = self.object.to_dict()
        
        content_type = ContentType.objects.get_for_model(models.AktivitetsTeamBooking)
        context['comments'] = XtdComment.objects.filter(
            content_type=content_type,
            object_pk=str(self.object.pk),
            is_public=True
        ).select_related('user').order_by('-submit_date')
        context['content_type_id'] = content_type.id
        
        return context



class AktivitetsTeamBookingDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.AktivitetsTeamBooking
    success_url = reverse_lazy("AktivitetsTeam_AktivitetsTeamBooking_list")

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class AktivitetsTeamBookingTeamListView(LoginRequiredMixin, generic.ListView):
    """List view showing bookings for the user's team only ("Mine bookinger").
    This is an additional view; the existing list view remains unchanged.
    """
    model = models.AktivitetsTeamBooking
    context_object_name = 'object_list'
    template_name = 'AktivitetsTeam/AktivitetsTeamBooking_mine_list.html'
    paginate_by = 16

    def get_queryset(self):
        user = self.request.user
        # Filter to bookings that belong to any team the user is a member of
        team_ids = user.teammembership_set.values_list('team', flat=True)
        queryset = models.AktivitetsTeamBooking.objects.filter(team__in=team_ids)
        queryset = queryset.select_related('team', 'team_contact', 'item').only(
            'id', 'team_id', 'team_contact_id', 'start_date', 'start_time',
            'end_date', 'end_time', 'item_id', 'status', 'remarks'
        ).order_by('start_date', 'start_time')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Team membership and staff flag
        user_team_membership = user.teammembership_set.select_related('team').first()
        is_staff = user.is_staff

        # The queryset is already filtered to the user's teams, but keep the
        # same context structure as other list views
        filtered_object_list = context.get('object_list', [])

        # Fetch user events (deadline field for aktivitetsteam)
        user_events = list(user.events.filter(is_active=True).values('name', 'deadline_aktivitetsteam'))

        # Volunteer team memberships for display
        volunteer_team_memberships = list(user.teammembership_set.select_related('team').values('team__name'))

        context.update({
            'filtered_object_list': filtered_object_list,
            'is_staff': is_staff,
            'user_team_membership': user_team_membership,
            'user_events': user_events,
            'volunteer_team_memberships': volunteer_team_memberships,
        })
        return context
    


