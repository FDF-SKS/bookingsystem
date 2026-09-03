from django.views import generic
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.contrib.auth.decorators import user_passes_test
import logging
from . import models
from . import forms
from organization.models import EventMembership, Event, Volunteer


# HTMX
from django.views.decorators.http import require_POST, require_http_methods
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404

from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.views.generic import FormView
from django.contrib.messages.views import SuccessMessageMixin
from organization.models import Event  # Import the Event model
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from itertools import groupby
from operator import itemgetter
logger = logging.getLogger(__name__)

class SjakKanbanView(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):
    """
    Advanced Kanban dashboard with dynamic grouping and filtering.
    Only accessible to staff/admins.
    """
    model = models.SjakBooking
    template_name = 'Sjak/sjak_kanban.html'
    context_object_name = 'bookings'
    paginate_by = None

    # Supported grouping fields
    GROUPING_OPTIONS = {
        'status': ('Status', models.SjakBooking.STATUS_CHOICES),
        'status_internal': ('Internal Status', models.SjakBooking.INTERNAL_STATUS_CHOICES),
        'assigned_sjak': ('Assigned Staff', None),  # Dynamic
        'item': ('Item', None),  # Dynamic
        'tag': ('Tag', None),  # Dynamic - now SjakTag objects
    }

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = models.SjakBooking.objects.select_related(
            'team', 'item', 'team_contact', 'assigned_sjak'
        ).order_by('-created')
        
        # Apply filters from query parameters
        team_id = self.request.GET.get('team')
        if team_id:
            queryset = queryset.filter(team_id=team_id)
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        status_internal = self.request.GET.get('status_internal')
        if status_internal:
            queryset = queryset.filter(status_internal=status_internal)
        
        item_id = self.request.GET.get('item')
        if item_id:
            queryset = queryset.filter(item_id=item_id)
        
        assigned_id = self.request.GET.get('assigned_sjak')
        if assigned_id:
            queryset = queryset.filter(assigned_sjak_id=assigned_id)
        
        tag = self.request.GET.get('tag')
        if tag:
            queryset = queryset.filter(tag=tag)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bookings = self.get_queryset()
        group_by = self.request.GET.get('group_by', 'status')
        
        # Validate group_by parameter
        if group_by not in self.GROUPING_OPTIONS:
            group_by = 'status'
        
        # Group bookings dynamically
        grouped_data = self._group_bookings(bookings, group_by)
        
        # Get filter options
        teams = models.SjakBooking.objects.values_list('team_id', 'team__name').distinct().order_by('team__name')
        items = models.SjakItem.objects.values_list('id', 'name').order_by('name')
        staff = Volunteer.objects.filter(
            groups__name='Sjak'
        ).values_list('id', 'first_name', 'last_name').order_by('first_name')
        
        context.update({
            'grouped_bookings': grouped_data,
            'group_by': group_by,
            'grouping_options': self.GROUPING_OPTIONS,
            'teams': teams,
            'items': items,
            'staff_members': staff,
            'status_choices': models.SjakBooking.STATUS_CHOICES,
            'status_internal_choices': models.SjakBooking.INTERNAL_STATUS_CHOICES,
            'tag_choices': models.SjakTag.objects.all().order_by('name'),
            'current_filters': {
                'team': self.request.GET.get('team', ''),
                'status': self.request.GET.get('status', ''),
                'status_internal': self.request.GET.get('status_internal', ''),
                'item': self.request.GET.get('item', ''),
                'assigned_sjak': self.request.GET.get('assigned_sjak', ''),
                'tag': self.request.GET.get('tag', ''),
            }
        })
        return context

    def _group_bookings(self, bookings, group_by):
        """
        Group bookings by the specified field.
        Returns a dictionary with group keys and booking lists.
        """
        from organization.models import Volunteer
        from django.db.models import Q
        
        grouped = {}
        
        if group_by == 'status':
            choices = models.SjakBooking.STATUS_CHOICES
            for choice_value, choice_label in choices:
                grouped[choice_value] = {
                    'label': choice_label,
                    'bookings': bookings.filter(status=choice_value),
                    'count': bookings.filter(status=choice_value).count()
                }
        
        elif group_by == 'status_internal':
            choices = models.SjakBooking.INTERNAL_STATUS_CHOICES
            for choice_value, choice_label in choices:
                grouped[choice_value] = {
                    'label': choice_label,
                    'bookings': bookings.filter(status_internal=choice_value),
                    'count': bookings.filter(status_internal=choice_value).count()
                }
        
        elif group_by == 'tag':
            # Include "Untagged"
            grouped['None'] = {
                'label': 'Untagged',
                'bookings': bookings.filter(tag__isnull=True),
                'count': bookings.filter(tag__isnull=True).count()
            }
            # Group by SjakTag objects - use values() instead of distinct()
            tag_ids = bookings.filter(tag__isnull=False).values_list('tag', flat=True).distinct()
            for tag_id in tag_ids:
                try:
                    tag = models.SjakTag.objects.get(id=tag_id)
                    key = f"tag_{tag.id}"
                    grouped[key] = {
                        'label': tag.name,
                        'bookings': bookings.filter(tag=tag),
                        'count': bookings.filter(tag=tag).count(),
                        'tag_id': tag.id,
                        'tag_color': tag.color
                    }
                except:
                    pass
        
        elif group_by == 'assigned_sjak':
            # Include "Unassigned"
            grouped['None'] = {
                'label': 'Unassigned',
                'bookings': bookings.filter(assigned_sjak__isnull=True),
                'count': bookings.filter(assigned_sjak__isnull=True).count()
            }
            # Group by assigned staff - use values() instead of distinct()
            staff_ids = bookings.filter(assigned_sjak__isnull=False).values_list('assigned_sjak', flat=True).distinct()
            for staff_id in staff_ids:
                try:
                    from organization.models import Volunteer
                    staff = Volunteer.objects.get(id=staff_id)
                    key = f"staff_{staff.id}"
                    grouped[key] = {
                        'label': f"{staff.first_name} {staff.last_name}",
                        'bookings': bookings.filter(assigned_sjak=staff),
                        'count': bookings.filter(assigned_sjak=staff).count(),
                        'staff_id': staff.id
                    }
                except:
                    pass
        
        elif group_by == 'item':
            # Group by item - use values() instead of distinct()
            item_ids = bookings.values_list('item', flat=True).distinct()
            for item_id in item_ids:
                try:
                    item = models.SjakItem.objects.get(id=item_id)
                    key = f"item_{item.id}"
                    grouped[key] = {
                        'label': item.name,
                        'bookings': bookings.filter(item=item),
                        'count': bookings.filter(item=item).count(),
                        'item_id': item.id
                    }
                except:
                    pass
        
        return grouped

class SjakBookingListView(LoginRequiredMixin, generic.ListView):
    model = models.SjakBooking
    form_class = forms.SjakBookingForm
    context_object_name = 'object_list'
    template_name = 'Sjak/SjakBooking_list.html'
    paginate_by = 16  # Display 15 items per page

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            queryset = models.SjakBooking.objects.all()
        else:
            queryset = models.SjakBooking.objects.filter(
                team__in=user.teammembership_set.values('team')
            )
        
        queryset = queryset.select_related(
            'team', 'team_contact', 'event', 'item__item_type'
        ).only(
            'id', 'team_id', 'team_contact_id', 'event_id', 'start_date', 'start_time', 'end_date', 'end_time', 'item_id', 'quantity', 'status'
        ).order_by('id')
        
        logger.info(f"Fetched {queryset.count()} bookings for user {user.id}")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Fetch the user's team membership
        user_team_membership = user.teammembership_set.select_related('team').first()
        is_staff = user.is_staff

        # Filter the object list based on the user's team membership and staff status
        if is_staff:
            filtered_object_list = context['object_list']
        else:
            filtered_object_list = [
            obj for obj in context['object_list']
            if user_team_membership and obj.team == user_team_membership.team
            ]

        # Fetch user events
        user_events = list(user.events.filter(is_active=True).values('name', 'deadline_sjak'))

        # Fetch volunteer team memberships
        volunteer_team_memberships = list(user.teammembership_set.select_related('team').values('team__name'))

        context.update({
            'filtered_object_list': filtered_object_list,
            'is_staff': is_staff,
            'user_team_membership': user_team_membership,
            'user_events': user_events,
            'volunteer_team_memberships': volunteer_team_memberships,
        })

        return context

    def get(self, request, *args, **kwargs):
        logger.info(f"Handling GET request for user {request.user.id} on page {self.request.GET.get('page', 1)}")
        return super().get(request, *args, **kwargs)

class SjakBookingCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.SjakBooking
    form_class = forms.SjakBookingForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        self.item_id = kwargs.get('item_id')
        if event and event.deadline_sjak < timezone.now().date():
            messages.error(request, 'Booking is closed.')
            return redirect('Sjak_SjakBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        if self.item_id:
            item = get_object_or_404(models.SjakItem, id=self.item_id)
            kwargs['initial'] = {'item': item}
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sjak_items = models.SjakItem.objects.all()
        context['sjak_items'] = sjak_items
        return context
    
    def get_success_url(self):
        return reverse('Sjak_SjakBooking_detail', args=[self.object.pk])

    def form_invalid(self, form):
        # Log form errors and submitted POST data to aid debugging when the
        # view re-renders with a 200 status (form invalid).
        try:
            post_data = dict(self.request.POST)
        except Exception:
            post_data = str(self.request.POST)
        logger.warning(
            "SjakBookingCreateView.form_invalid: user=%s errors=%s post=%s",
            getattr(self.request.user, 'id', 'anonymous'),
            form.errors.as_json() if hasattr(form.errors, 'as_json') else str(form.errors),
            post_data,
        )
        return super().form_invalid(form)




class SjakBookingDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.SjakBooking
    form_class = forms.SjakBookingForm

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django_comments_xtd.models import XtdComment
        from django.contrib.contenttypes.models import ContentType
        
        content_type = ContentType.objects.get_for_model(models.SjakBooking)
        context['comments'] = XtdComment.objects.filter(
            content_type=content_type,
            object_pk=str(self.object.pk),
            is_public=True
        ).select_related('user').order_by('-submit_date')
        context['content_type_id'] = content_type.id
        
        return context
    
@login_required
@user_passes_test(lambda u: u.is_staff)
def approve_booking(request, pk):
    booking = get_object_or_404(models.SjakBooking, pk=pk)
    booking.status = 'Approved'
    booking.save()
    next_url = request.GET.get('next', 'Sjak_SjakBooking_list')
    return redirect(next_url)

@login_required
@user_passes_test(lambda u: u.is_staff)
def reject_booking(request, pk):
    booking = get_object_or_404(models.SjakBooking, pk=pk)
    booking.status = 'Rejected'
    booking.save()
    next_url = request.GET.get('next', 'Sjak_SjakBooking_list')
    return redirect(next_url)

class SjakBookingUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.SjakBooking
    form_class = forms.SjakBookingForm
    pk_url_kwarg = "pk"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        if event and event.deadline_sjak < timezone.now().date():
            messages.error(request, 'Booking is closed.')
            return redirect('Sjak_SjakBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sjak_items = models.SjakItem.objects.all()
        context['sjak_items'] = sjak_items
        return context
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        form.instance = self.get_object()  # Pre-populate the form with object's values
        
        # Add the following lines to ensure related fields are initialized
        form.fields["team"].initial = form.instance.team
        form.fields["item"].initial = form.instance.item
        form.fields["team_contact"].initial = form.instance.team_contact
        
        return form


class SjakBookingDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.SjakBooking
    success_url = reverse_lazy("Sjak_SjakBooking_list")

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    


class SjakItemListView(generic.ListView):
    model = models.SjakItem
    form_class = forms.SjakItemForm
    context_object_name = 'object_list'
    ordering = ['name']

    def get_queryset(self):
        queryset = models.SjakItem.objects.all().order_by('name')  # Order by the 'name' field
        return queryset
    


class SjakItemCreateView(generic.CreateView):
    model = models.SjakItem
    form_class = forms.SjakItemForm

    def form_valid(self, form):
        # Handle the form submission and file upload
        return super().form_valid(form)


class SjakItemDetailView(generic.DetailView):
    model = models.SjakItem
    form_class = forms.SjakItemForm




class SjakItemUpdateView(generic.UpdateView):
    model = models.SjakItem
    form_class = forms.SjakItemForm
    pk_url_kwarg = "pk"

    def form_valid(self, form):
        # Handle the form submission and file upload
        return super().form_valid(form)


class SjakItemDeleteView(generic.DeleteView):
    model = models.SjakItem
    success_url = reverse_lazy("Sjak_SjakItem_list")





class SjakItemTypeListView(generic.ListView):
    model = models.SjakItemType
    form_class = forms.SjakItemTypeForm


class SjakItemTypeCreateView(generic.CreateView):
    model = models.SjakItemType
    form_class = forms.SjakItemTypeForm


class SjakItemTypeDetailView(generic.DetailView):
    model = models.SjakItemType
    form_class = forms.SjakItemTypeForm


class SjakItemTypeUpdateView(generic.UpdateView):
    model = models.SjakItemType
    form_class = forms.SjakItemTypeForm
    pk_url_kwarg = "pk"


class SjakItemTypeDeleteView(generic.DeleteView):
    model = models.SjakItemType
    success_url = reverse_lazy("Sjak_SjakItemType_list")


@login_required
def search_item(request):
    search_text = request.POST.get('search')
    results = models.SjakItem.objects.filter(name__icontains=search_text)
    context = {"results": results}
    return render(request, 'Sjak/partials/search-results.html', context)

def clear(request):
    return HttpResponse("")

@login_required
@user_passes_test(lambda u: u.is_staff)
@require_POST
def update_booking_field(request, pk):
    """
    Generic AJAX endpoint to update any field on a booking.
    Accepts: field_name and field_value via POST.
    """
    import json
    
    try:
        booking = get_object_or_404(models.SjakBooking, pk=pk)
        
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        field_name = data.get('field_name')
        field_value = data.get('field_value')
        
        # Whitelist allowed fields for security
        allowed_fields = ['status', 'status_internal', 'assigned_sjak', 'item', 'tag']
        if field_name not in allowed_fields:
            return JsonResponse({'error': 'Invalid field'}, status=400)
        
        # Validate and update field
        if field_name == 'assigned_sjak':
            # Handle Volunteer foreign key
            if field_value and field_value != 'None':
                from organization.models import Volunteer
                try:
                    staff = Volunteer.objects.get(id=int(field_value))
                    setattr(booking, field_name, staff)
                except (Volunteer.DoesNotExist, ValueError):
                    return JsonResponse({'error': 'Invalid staff member'}, status=400)
            else:
                setattr(booking, field_name, None)
        
        elif field_name == 'item':
            # Handle SjakItem foreign key
            if field_value and field_value != 'None':
                try:
                    item = models.SjakItem.objects.get(id=int(field_value))
                    setattr(booking, field_name, item)
                except (models.SjakItem.DoesNotExist, ValueError):
                    return JsonResponse({'error': 'Invalid item'}, status=400)
            else:
                return JsonResponse({'error': 'Item cannot be empty'}, status=400)
        
        else:
            # Handle CharField fields (status, status_internal)
            # Validate the value against choices
            if field_name == 'status':
                valid_values = [choice[0] for choice in models.SjakBooking.STATUS_CHOICES]
            elif field_name == 'status_internal':
                valid_values = [choice[0] for choice in models.SjakBooking.INTERNAL_STATUS_CHOICES]
            elif field_name == 'tag':
                # Validate against SjakTag IDs
                valid_tag_ids = models.SjakTag.objects.values_list('id', flat=True)
                valid_values = list(valid_tag_ids)
                valid_values.append(None)  # Allow null for tags
                # Convert field_value to int if it's a number string, or None if it's 'None'
                if field_value != 'None':
                    try:
                        field_value = int(field_value) if field_value else None
                    except (ValueError, TypeError):
                        return JsonResponse({'error': 'Invalid tag ID'}, status=400)
            
            if field_value not in valid_values:
                return JsonResponse({'error': f'Invalid {field_name}'}, status=400)
            
            # Handle ForeignKey fields
            if field_name == 'tag':
                if field_value:
                    tag_obj = models.SjakTag.objects.get(id=field_value)
                    setattr(booking, field_name, tag_obj)
                else:
                    setattr(booking, field_name, None)
            elif field_name == 'assigned_sjak':
                if field_value:
                    staff_obj = Volunteer.objects.get(id=field_value)
                    setattr(booking, field_name, staff_obj)
                else:
                    setattr(booking, field_name, None)
            elif field_name == 'item':
                if field_value:
                    item_obj = models.SjakItem.objects.get(id=field_value)
                    setattr(booking, field_name, item_obj)
                else:
                    setattr(booking, field_name, None)
            else:
                setattr(booking, field_name, field_value if field_value != 'None' else None)
        
        booking.save()
        
        return JsonResponse({
            'success': True,
            'id': booking.id,
            'field': field_name,
            'value': field_value,
            'message': f'Booking updated'
        })
    
    except Exception as e:
        logger.error(f"Error updating booking field: {str(e)}")
        return JsonResponse({'error': 'Failed to update booking'}, status=500)

@login_required
@user_passes_test(lambda u: u.is_staff)
@require_POST
def update_booking_status(request, pk):
    """
    Legacy endpoint for backward compatibility.
    """
    try:
        booking = get_object_or_404(models.SjakBooking, pk=pk)
        new_status = request.POST.get('status')
        
        # Validate the new status
        valid_statuses = [choice[0] for choice in models.SjakBooking.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        booking.status = new_status
        booking.save()
        
        return JsonResponse({
            'success': True,
            'id': booking.id,
            'status': booking.get_status_display(),
            'message': f'Booking updated to {booking.get_status_display()}'
        })
    except Exception as e:
        logger.error(f"Error updating booking status: {str(e)}")
        return JsonResponse({'error': 'Failed to update booking'}, status=500)



