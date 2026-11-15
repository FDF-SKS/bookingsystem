from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordResetView
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.db.models.functions import Cast
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views import generic
from django.views.decorators.http import require_POST

from emailing.forms import BrandedPasswordResetForm
from utils.ui import BookingDetailContextMixin, BookingListContextMixin

from . import forms, models
from .models import Team, TeamMembership
from .permissions import StaffRequiredMixin, TeamQuerysetMixin

User = get_user_model()

# Hard cap on the width of the tjanse overview grid. Events with a longer
# range are truncated to this many days to bound per-request work.
MAX_OVERVIEW_DAYS = 60

# Used when ordering the Slutrengøring pool: Required -> High -> Medium -> Low.
SLUTRENGOERING_PRIORITY_ORDER = Case(
    When(tjanse__priority='required', then=Value(0)),
    When(tjanse__priority='high', then=Value(1)),
    When(tjanse__priority='medium', then=Value(2)),
    When(tjanse__priority='low', then=Value(3)),
    default=Value(99),
    output_field=IntegerField(),
)



@login_required
def home(request):
    return render(request, 'index.html')

def logout_user(request):
	logout(request)
	messages.success(request, ("You Were Logged Out!"))
	return redirect('home')


class ResetPasswordView(SuccessMessageMixin, PasswordResetView):
    template_name = 'organization/password_reset.html'
    form_class = BrandedPasswordResetForm
    email_template_name = 'emailing/password_reset.html'
    subject_template_name = 'organization/password_reset_subject.txt'
    success_message = "We've emailed you instructions for setting your password, " \
                      "if an account exists with the email you entered. You should receive them shortly." \
                      " If you don't receive an email, " \
                      "please make sure you've entered the address you registered with, and check your spam folder."
    success_url = reverse_lazy('home')





class EventMembershipListView(LoginRequiredMixin, generic.ListView):
    model = models.EventMembership
    form_class = forms.EventMembershipForm


class EventMembershipCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.EventMembership
    form_class = forms.EventMembershipForm


class EventMembershipDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.EventMembership
    form_class = forms.EventMembershipForm


class EventMembershipUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.EventMembership
    form_class = forms.EventMembershipForm
    pk_url_kwarg = "pk"


class EventMembershipDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.EventMembership
    success_url = reverse_lazy("organization_EventMembership_list")


class EventListView(LoginRequiredMixin, generic.ListView):
    model = models.Event
    form_class = forms.EventForm


class EventCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.Event
    form_class = forms.EventForm


class EventDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Event
    form_class = forms.EventForm


class EventUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.Event
    form_class = forms.EventForm
    pk_url_kwarg = "pk"


class EventDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.Event
    success_url = reverse_lazy("organization_Event_list")


class TeamListView(LoginRequiredMixin, generic.ListView):
    model = models.Team
    form_class = forms.TeamForm


class TeamCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.Team
    form_class = forms.TeamForm


class TeamDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Team
    form_class = forms.TeamForm


class TeamUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.Team
    form_class = forms.TeamForm
    pk_url_kwarg = "pk"


class TeamDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.Team
    success_url = reverse_lazy("organization_Team_list")


class TeamMembershipListView(LoginRequiredMixin, generic.ListView):
    model = models.TeamMembership
    form_class = forms.TeamMembershipForm


class TeamMembershipCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.TeamMembership
    form_class = forms.TeamMembershipForm


class TeamMembershipDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.TeamMembership
    form_class = forms.TeamMembershipForm


class TeamMembershipUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.TeamMembership
    form_class = forms.TeamMembershipForm
    pk_url_kwarg = "pk"


class TeamMembershipDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.TeamMembership
    success_url = reverse_lazy("organization_TeamMembership_list")


class VolunteerListView(LoginRequiredMixin, generic.ListView):
    model = models.Volunteer
    context_object_name = 'volunteer_list'

    def get_queryset(self):
        return models.Volunteer.objects.filter(
            is_active=True
        ).prefetch_related(
            'teammembership_set__team'
        ).only(
            'first_name', 'last_name', 'phone', 'email', 'id', 'is_active'
        ).order_by('first_name')


class VolunteerCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.Volunteer
    form_class = forms.VolunteerForm


class VolunteerDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Volunteer
    form_class = forms.VolunteerForm
    success_url = reverse_lazy("organization_Volunteer_detail")



class VolunteerUpdateView(UserPassesTestMixin, generic.UpdateView):
    model = models.Volunteer
    form_class = forms.VolunteerProfileUpdateForm
    template_name = 'organization/volunteer_form.html'

    def test_func(self):
        # Only allow the user to edit their own profile
        obj = self.get_object()
        return self.request.user == obj

    def handle_no_permission(self):
        # Redirect them back to their own profile if they try to edit someone else's
        return redirect('volunteer_detail', pk=self.request.user.pk)
    
    def form_valid(self, form):
        # Add success message
        messages.success(self.request, 'Din profil blev opdateret succesfuldt!')
        return super().form_valid(form)


class VolunteerDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.Volunteer
    success_url = reverse_lazy("organization_Volunteer_list")

class KeyListView(LoginRequiredMixin, generic.ListView):
    model = models.Key
    form_class = forms.KeyForm
    context_object_name = "key_list"

    def get_queryset(self):
        return models.Key.objects.annotate(
            number_int=Cast('number', IntegerField())
        ).order_by('number_int')


class KeyCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.Key
    form_class = forms.KeyForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "Du har ikke tilladelse til at oprette en nøgle.")
            return redirect(reverse_lazy('organization_Key_list'))

class KeyDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Key
    form_class = forms.KeyForm


class KeyUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.Key
    form_class = forms.KeyForm
    pk_url_kwarg = "pk"

    def dispatch(self, request, *args, **kwargs):
        # Only allow admins
        if not request.user.is_staff:  # or use is_superuser if you prefer
            messages.error(request, "Du har ikke tilladelse til at ændre denne nøgle.")
            # Redirect back to the previous page, or fallback to a safe URL
            return redirect(request.META.get('HTTP_REFERER', reverse_lazy('organization_Key_list')))
        return super().dispatch(request, *args, **kwargs)

class KeyDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.Key
    success_url = reverse_lazy("organization_Key_list")



class AppointmentQuerysetMixin:
    """Restrict appointments to the ones the user may see.

    Participants, members of the receiving team, and (for shared appointments)
    the requester's teammates all get access. Staff see everything.
    """

    def get_queryset(self):
        return super().get_queryset().visible_to(self.request.user)


class AppointmentOwnerMixin:
    """Restrict editing and deleting to the requester (or staff)."""

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        return qs.filter(requester=user)


class VolunteerAppointmentListView(BookingListContextMixin, LoginRequiredMixin, generic.ListView):
    model = models.VolunteerAppointment
    context_object_name = 'appointments'

    booking_list_title = "Mine legeaftaler"
    booking_list_create_url_name = "organization_VolunteerAppointment_create"
    booking_list_create_label = "Ny legeaftale"
    booking_list_mobile_create_label = "Ny legeaftale"
    booking_list_show_comments = False
    booking_list_show_quantity = False
    booking_list_show_team_contact = False
    booking_list_empty_message = "Du har ingen legeaftaler endnu."

    def get_queryset(self):
        return (
            models.VolunteerAppointment.objects.visible_to(self.request.user)
            .select_related('requester', 'receiver', 'receiver_team')
            .order_by(
                F('start_date').desc(nulls_last=True),
                F('start_time').desc(nulls_last=True),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointments = context.get('object_list')
        if appointments is None:
            appointments = context.get(self.context_object_name, [])
        user = self.request.user
        for appointment in appointments:
            appointment.role = appointment.role_for(user)
        context['object_list'] = appointments
        return context
    
    
class VolunteerAppointmentCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.VolunteerAppointment
    form_class = forms.AppointmentForm
    success_url = reverse_lazy("organization_VolunteerAppointment_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.requester = self.request.user
        form.instance.status = 'pending'
        return super().form_valid(form)

class VolunteerAppointmentDetailView(BookingDetailContextMixin, AppointmentQuerysetMixin, LoginRequiredMixin, generic.DetailView):
    model = models.VolunteerAppointment

    booking_detail_kicker = "Legeaftale"
    booking_detail_list_url_name = "organization_VolunteerAppointment_list"
    booking_detail_list_label = "Legeaftaler"
    booking_detail_show_comments = False

    def get_queryset(self):
        return super().get_queryset().select_related(
            'requester', 'receiver', 'receiver_team', 'resolved_by'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.urls import reverse
        from django_comments_xtd.models import XtdComment

        # Get all comments for this appointment
        content_type = ContentType.objects.get_for_model(models.VolunteerAppointment)
        context['comments'] = XtdComment.objects.filter(
            content_type=content_type,
            object_pk=str(self.object.pk),
            is_public=True
        ).select_related('user').order_by('-submit_date')

        # Everyone who can see the appointment can join the conversation.
        context['user_can_comment'] = self.object.can_view(self.request.user)
        context['user_can_respond'] = self.object.can_respond(self.request.user)
        context['user_can_edit'] = self.object.can_edit(self.request.user)

        # Add URL for comment form submission
        context['comment_form_url'] = reverse('appointment_comment_add', kwargs={'pk': self.object.pk})

        return context

class VolunteerAppointmentUpdateView(AppointmentOwnerMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.VolunteerAppointment
    form_class = forms.AppointmentForm
    # Fallback redirect if get_absolute_url isn't used
    success_url = reverse_lazy("organization_VolunteerAppointment_list") 

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class VolunteerAppointmentDeleteView(AppointmentOwnerMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.VolunteerAppointment
    success_url = reverse_lazy("organization_VolunteerAppointment_list")




@login_required
@require_POST
def appointment_status_update(request, pk, new_status):
    """Let the receiver (or a member of the receiving team) answer."""
    appointment = get_object_or_404(models.VolunteerAppointment, pk=pk)
    if not appointment.can_respond(request.user):
        raise Http404()

    if new_status in ['accepted', 'rejected', 'pending']:
        appointment.status = new_status
        if new_status in ('accepted', 'rejected'):
            appointment.resolved_by = request.user
        else:
            appointment.resolved_by = None
        appointment.save(update_fields=['status', 'resolved_by', 'last_updated'])
    return redirect('organization_VolunteerAppointment_detail', pk=pk)


@login_required
@require_POST
def appointment_comment_add(request, pk):
    """Add a comment to a VolunteerAppointment."""
    from django.conf import settings
    from django_comments_xtd.models import XtdComment

    appointment = get_object_or_404(models.VolunteerAppointment, pk=pk)

    # Everyone who can see the appointment can comment on it.
    if not appointment.can_view(request.user):
        raise Http404()
    
    comment_text = request.POST.get('comment', '').strip()
    if not comment_text:
        messages.warning(request, "Kommentaren kan ikke være tom.")
        return redirect('organization_VolunteerAppointment_detail', pk=pk)
    
    content_type = ContentType.objects.get_for_model(models.VolunteerAppointment)
    
    XtdComment.objects.create(
        content_type=content_type,
        object_pk=str(appointment.pk),
        user=request.user,
        user_name=request.user.get_full_name() or request.user.username,
        user_email=request.user.email,
        comment=comment_text,
        is_public=True,
        site_id=getattr(settings, 'SITE_ID', 1),
    )
    
    messages.success(request, "Kommentar tilføjet!")
    return redirect('organization_VolunteerAppointment_detail', pk=pk)


class TjanseOwnershipDetailView(TeamQuerysetMixin, LoginRequiredMixin, generic.DetailView):
    """Single tjanse assignment: description, swap request and reassignment history."""
    model = models.TjanseOwnership
    context_object_name = 'ownership'

    def get_queryset(self):
        return super().get_queryset().filter(tjanse__kind='regular')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_team_ids = set(TeamMembership.objects.filter(member=self.request.user).values_list('team_id', flat=True))
        pending_swaps = models.TjanseSwapRequest.objects.filter(
            task_ownership=self.object, status='pending'
        ).select_related('requesting_team', 'receiving_team')

        context['pending_swaps'] = pending_swaps
        context['can_request_swap'] = self.object.team_id in user_team_ids and not pending_swaps.exists()
        context['teams'] = Team.objects.exclude(pk=self.object.team_id).order_by('name')
        context['history'] = self.object.history.all().select_related('team', 'event').order_by('-history_date')
        return context


@login_required
@require_POST
def tjanse_request_swap(request, pk):
    """Lets a member of the owning team request handing their tjanse to another team."""
    ownership = get_object_or_404(models.TjanseOwnership, pk=pk)
    user_team_ids = TeamMembership.objects.filter(member=request.user).values_list('team_id', flat=True)
    if ownership.team_id not in user_team_ids:
        raise Http404()

    receiving_team = models.Team.objects.filter(pk=request.POST.get('receiving_team')).exclude(pk=ownership.team_id).first()
    if receiving_team:
        models.TjanseSwapRequest.objects.create(
            task_ownership=ownership,
            requesting_team_id=ownership.team_id,
            receiving_team=receiving_team,
            status='pending',
        )
        messages.success(request, "Byt-anmodning sendt.")
    else:
        messages.error(request, "Vælg et gyldigt team at anmode.")
    return redirect('organization_TjanseOwnership_detail', pk=ownership.pk)


class TjanseOwnershipListView(LoginRequiredMixin, generic.ListView):
    """Lists tjanser owned by any team the requesting user belongs to."""
    model = models.TjanseOwnership
    context_object_name = 'ownerships'

    def get_queryset(self):
        user_team_ids = TeamMembership.objects.filter(member=self.request.user).values_list('team_id', flat=True)
        return models.TjanseOwnership.objects.filter(
            team_id__in=user_team_ids,
            tjanse__kind='regular',
        ).select_related('tjanse', 'event', 'team').order_by('due_date', 'status')


class TjanseOverviewView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'organization/tjanse_overview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        events = models.Event.objects.filter(is_active=True).order_by('start_date', 'name')
        event_id = self.request.GET.get('event')
        selected_event = None
        if event_id:
            try:
                selected_event = events.filter(pk=int(event_id)).first()
            except (TypeError, ValueError):
                selected_event = None
        else:
            selected_event = events.first()

        days = []
        rows = []
        if selected_event:
            total_days = (selected_event.end_date - selected_event.start_date).days + 1
            day_count = max(0, min(total_days, MAX_OVERVIEW_DAYS))
            days = [
                selected_event.start_date + timedelta(days=offset)
                for offset in range(day_count)
            ]
            ownerships = models.TjanseOwnership.objects.filter(
                event=selected_event,
                tjanse__kind='regular',
                due_date__gte=days[0],
                due_date__lte=days[-1],
            ).select_related('team', 'tjanse').order_by('team__name') if days else models.TjanseOwnership.objects.none()
            ownership_map = {}
            for ownership in ownerships:
                ownership_map.setdefault((ownership.tjanse_id, ownership.due_date), []).append(ownership)

            rows = [
                {
                    'tjanse': tjanse,
                    'cells': [
                        {
                            'day': day,
                            'ownerships': ownership_map.get((tjanse.pk, day), []),
                        }
                        for day in days
                    ],
                }
                for tjanse in models.Tjanse.objects.filter(kind='regular').order_by('title')
            ]

        context.update({
            'events': events,
            'selected_event': selected_event,
            'days': days,
            'rows': rows,
        })
        return context


@login_required
@require_POST
def tjanse_ownership_status_update(request, pk, new_status):
    """Lets a member of the owning team update the status of their tjanse."""
    ownership = get_object_or_404(models.TjanseOwnership, pk=pk)
    user_team_ids = TeamMembership.objects.filter(member=request.user).values_list('team_id', flat=True)
    if ownership.team_id not in user_team_ids:
        raise Http404()
    if new_status in dict(models.TjanseOwnership.STATUS_CHOICES):
        ownership.status = new_status
        if new_status == 'done':
            ownership.completed_at = now()
        ownership.save()
        messages.success(request, "Status opdateret.")
    return redirect('organization_TjanseOwnership_list')


class TjanseSwapRequestCreateView(LoginRequiredMixin, generic.CreateView):
    """Lets a team member request handing a tjanse over to another team."""
    model = models.TjanseSwapRequest
    fields = ['task_ownership', 'receiving_team']
    success_url = reverse_lazy('organization_TjanseSwapRequest_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user_team_ids = TeamMembership.objects.filter(member=self.request.user).values_list('team_id', flat=True)
        form.fields['task_ownership'].queryset = models.TjanseOwnership.objects.filter(
            team_id__in=user_team_ids,
            tjanse__kind='regular',
        )
        form.fields['receiving_team'].queryset = Team.objects.exclude(id__in=user_team_ids)
        return form

    def form_valid(self, form):
        form.instance.requesting_team = form.instance.task_ownership.team
        form.instance.status = 'pending'
        return super().form_valid(form)


class TjanseSwapRequestListView(LoginRequiredMixin, generic.ListView):
    """Lists swap requests where the user's team is either party."""
    model = models.TjanseSwapRequest
    context_object_name = 'swap_requests'

    def get_queryset(self):
        user_team_ids = TeamMembership.objects.filter(member=self.request.user).values_list('team_id', flat=True)
        return models.TjanseSwapRequest.objects.filter(
            Q(requesting_team_id__in=user_team_ids) | Q(receiving_team_id__in=user_team_ids)
        ).select_related('task_ownership__tjanse', 'requesting_team', 'receiving_team').order_by('-created')


@login_required
@require_POST
def tjanse_swap_request_update(request, pk, new_status):
    """Lets a member of the receiving team accept or reject a swap request."""
    swap = get_object_or_404(models.TjanseSwapRequest, pk=pk, status='pending')
    user_team_ids = TeamMembership.objects.filter(member=request.user).values_list('team_id', flat=True)
    if swap.receiving_team_id not in user_team_ids:
        raise Http404()
    if new_status == 'accepted':
        from .signals import send_tjanse_assigned_email
        swap.accept(resolved_by=request.user)
        send_tjanse_assigned_email(swap.task_ownership)
        messages.success(request, "Tjanse-byttet blev accepteret.")
    elif new_status == 'rejected':
        swap.reject(resolved_by=request.user)
        messages.success(request, "Tjanse-byttet blev afvist.")
    return redirect('organization_TjanseSwapRequest_list')


# ---------------------------------------------------------------------------
# Slutrengøring
# ---------------------------------------------------------------------------

def _slutrengoring_team_ids(user):
    if user is None or not user.is_authenticated:
        return set()
    return set(
        TeamMembership.objects.filter(member=user).values_list('team_id', flat=True)
    )


def _resolve_slutrengoring_event(request):
    """Return the event to show, preferring the user's current active task."""
    events = models.Event.objects.filter(is_active=True).order_by('-end_date', 'name')
    event_id = request.POST.get('event') or request.GET.get('event')
    if event_id:
        try:
            selected = events.filter(pk=int(event_id)).first()
        except (TypeError, ValueError):
            selected = None
        if selected:
            return selected, events

    team_ids = _slutrengoring_team_ids(request.user)
    if team_ids:
        current = (
            models.SlutrengoringAssignment.objects
            .filter(
                event__is_active=True,
                team_id__in=team_ids,
                status__in=models.SlutrengoringAssignment.ACTIVE_STATUSES,
            )
            .select_related('event')
            .order_by('-event__end_date')
            .first()
        )
        if current:
            return current.event, events
    return events.first(), events


def _slutrengoring_team_for_action(request, event, team_id=None):
    """Validate that the acting user may represent ``team_id``.

    Staff may pick any team; everyone else may only pick one of their own.
    """
    team_ids = _slutrengoring_team_ids(request.user)
    if team_id:
        try:
            team_id = int(team_id)
        except (TypeError, ValueError):
            return None
        if request.user.is_staff:
            return Team.objects.filter(pk=team_id).first()
        return Team.objects.filter(pk=team_id, id__in=team_ids).first()

    if len(team_ids) == 1:
        return Team.objects.filter(pk=next(iter(team_ids))).first()
    return None


def _slutrengoring_can_act(request, assignment):
    if request.user.is_staff:
        return True
    return assignment.team_id in _slutrengoring_team_ids(request.user)


def _slutrengoring_redirect_after_finish(request, assignment, team):
    """Send a team to the claim page once its last active task is finished."""
    event_id = assignment.event_id
    remaining = models.SlutrengoringAssignment.objects.filter(
        event_id=event_id,
        team=team,
        status__in=models.SlutrengoringAssignment.ACTIVE_STATUSES,
    ).exists() if team else False

    if remaining:
        return redirect(f"{reverse('organization_Slutrengoring_home')}?event={event_id}")

    messages.info(request, "I har ingen aktive opgaver. Vælg den næste opgave.")
    team_param = f"&team={team.pk}" if team else ""
    return redirect(
        f"{reverse('organization_Slutrengoring_claim_list')}?event={event_id}{team_param}"
    )


class SlutrengoringHomeView(LoginRequiredMixin, generic.TemplateView):
    """A team's current and recently completed Slutrengøring tasks."""
    template_name = 'organization/slutrengoring_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_event, events = _resolve_slutrengoring_event(self.request)
        team_ids = _slutrengoring_team_ids(self.request.user)

        assignments = models.SlutrengoringAssignment.objects.none()
        active = models.SlutrengoringAssignment.objects.none()
        completed = models.SlutrengoringAssignment.objects.none()
        claimable_count = 0

        if selected_event:
            claimable_qs = models.SlutrengoringAssignment.objects.filter(
                event=selected_event,
                team__isnull=True,
                status__in=models.SlutrengoringAssignment.CLAIMABLE_STATUSES,
            )
            if team_ids and not self.request.user.is_staff:
                claimable_qs = claimable_qs.exclude(
                    status='not_finished', last_team_id__in=team_ids
                )
            claimable_count = claimable_qs.count()

        if selected_event and team_ids:
            assignments = (
                models.SlutrengoringAssignment.objects
                .filter(event=selected_event, team_id__in=team_ids)
                .select_related('tjanse', 'team', 'event')
            )
            active = assignments.filter(
                status__in=models.SlutrengoringAssignment.ACTIVE_STATUSES
            ).annotate(priority_rank=SLUTRENGOERING_PRIORITY_ORDER).order_by(
                'priority_rank', 'tjanse__order', 'tjanse__title'
            )
            completed = assignments.filter(status='done').order_by('-completed_at')[:10]

        context.update({
            'events': events,
            'selected_event': selected_event,
            'active_assignments': active,
            'completed_assignments': completed,
            'claimable_count': claimable_count,
            'team_ids': team_ids,
        })
        return context


class SlutrengoringClaimListView(LoginRequiredMixin, generic.TemplateView):
    """The pool of unclaimed tasks, ordered by priority."""
    template_name = 'organization/slutrengoring_claim_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_event, events = _resolve_slutrengoring_event(self.request)
        team_ids = _slutrengoring_team_ids(self.request.user)
        teams = Team.objects.filter(id__in=team_ids).order_by('name')
        if self.request.user.is_staff:
            teams = Team.objects.order_by('name')

        assignments = models.SlutrengoringAssignment.objects.none()
        areas = []
        if selected_event:
            assignments = (
                models.SlutrengoringAssignment.objects
                .filter(
                    event=selected_event,
                    team__isnull=True,
                    status__in=models.SlutrengoringAssignment.CLAIMABLE_STATUSES,
                )
                .select_related('tjanse', 'last_team')
            )
            if team_ids and not self.request.user.is_staff:
                # A team that returned a task should let another team take it.
                assignments = assignments.exclude(
                    status='not_finished', last_team_id__in=team_ids
                )

            priority = self.request.GET.get('priority')
            if priority in dict(models.Tjanse.PRIORITY_CHOICES):
                assignments = assignments.filter(tjanse__priority=priority)
            area = self.request.GET.get('area')
            if area:
                assignments = assignments.filter(tjanse__area=area)

            assignments = assignments.annotate(
                priority_rank=SLUTRENGOERING_PRIORITY_ORDER
            ).order_by('priority_rank', 'tjanse__order', 'tjanse__title')
            areas = (
                models.Tjanse.objects
                .filter(
                    kind='slutrengoring',
                    slutrengoring_assignments__event=selected_event,
                )
                .exclude(area='')
                .values_list('area', flat=True)
                .distinct()
                .order_by('area')
            )

        selected_team_id = self.request.GET.get('team') or ''
        context.update({
            'events': events,
            'selected_event': selected_event,
            'assignments': assignments,
            'teams': teams,
            'selected_team_id': selected_team_id,
            'areas': areas,
            'priority_choices': models.Tjanse.PRIORITY_CHOICES,
            'selected_priority': self.request.GET.get('priority', ''),
            'selected_area': self.request.GET.get('area', ''),
        })
        return context


class SlutrengoringAssignmentDetailView(LoginRequiredMixin, generic.DetailView):
    """A single Slutrengøring task with start/finish actions and history."""
    model = models.SlutrengoringAssignment
    context_object_name = 'assignment'
    template_name = 'organization/slutrengoring_detail.html'

    def get_queryset(self):
        qs = super().get_queryset().select_related('tjanse', 'event', 'team', 'last_team')
        if self.request.user.is_staff:
            return qs
        team_ids = _slutrengoring_team_ids(self.request.user)
        return qs.filter(
            Q(team_id__in=team_ids)
            | Q(
                team__isnull=True,
                status__in=models.SlutrengoringAssignment.CLAIMABLE_STATUSES,
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.object
        team_ids = _slutrengoring_team_ids(self.request.user)
        teams = Team.objects.filter(id__in=team_ids).order_by('name')
        if self.request.user.is_staff:
            teams = Team.objects.order_by('name')

        context.update({
            'teams': teams,
            'can_act': _slutrengoring_can_act(self.request, assignment),
            'can_claim': assignment.is_claimable and assignment.last_team_id not in team_ids,
            'history': assignment.history.select_related('history_user', 'team').all(),
        })
        return context


@login_required
@require_POST
def slutrengoring_claim(request, pk):
    """Atomically claim a task from the pool for a team."""
    assignment = get_object_or_404(
        models.SlutrengoringAssignment.objects.select_related('event', 'tjanse'),
        pk=pk,
    )
    if not assignment.is_claimable or not assignment.event.is_active:
        messages.error(request, "Opgaven er ikke længere ledig.")
        return redirect(
            f"{reverse('organization_Slutrengoring_claim_list')}?event={assignment.event_id}"
        )

    team = _slutrengoring_team_for_action(
        request, assignment.event, request.POST.get('team')
    )
    if team is None:
        messages.error(request, "Vælg hvilket team der tager opgaven.")
        return redirect(
            f"{reverse('organization_Slutrengoring_detail', args=(assignment.pk,))}"
        )

    if (
        not request.user.is_staff
        and assignment.status == 'not_finished'
        and assignment.last_team_id == team.pk
    ):
        messages.error(
            request,
            "Opgaven er returneret af jeres team. Lad et andet team tage den.",
        )
        return redirect(
            f"{reverse('organization_Slutrengoring_claim_list')}?event={assignment.event_id}"
        )

    with transaction.atomic():
        # Serialize claims from the same team so it cannot grab two tasks.
        Team.objects.select_for_update().get(pk=team.pk)
        has_active = models.SlutrengoringAssignment.objects.filter(
            event=assignment.event,
            team=team,
            status__in=models.SlutrengoringAssignment.ACTIVE_STATUSES,
        ).exists()
        if has_active:
            messages.error(request, "I har allerede en aktiv opgave. Afslut den først.")
            return redirect(
                f"{reverse('organization_Slutrengoring_home')}?event={assignment.event_id}"
            )

        claimed = (
            models.SlutrengoringAssignment.objects
            .filter(
                pk=assignment.pk,
                team__isnull=True,
                status__in=models.SlutrengoringAssignment.CLAIMABLE_STATUSES,
            )
            .update(
                team=team,
                status='assigned',
                assigned_at=now(),
                assigned_by=request.user,
                last_updated=now(),
            )
        )
        if claimed:
            # ``update()`` bypasses simple-history; re-save the claimed row so
            # the assignment history and audit trail stay complete.
            assignment.refresh_from_db()
            assignment.save()

    if not claimed:
        messages.error(
            request,
            "Opgaven blev desværre taget af et andet team. Vælg en anden.",
        )
        return redirect(
            f"{reverse('organization_Slutrengoring_claim_list')}?event={assignment.event_id}"
        )

    messages.success(request, f"Opgaven er nu tildelt {team.name}.")
    return redirect('organization_Slutrengoring_detail', pk=assignment.pk)


@login_required
@require_POST
def slutrengoring_start(request, pk):
    with transaction.atomic():
        assignment = get_object_or_404(
            models.SlutrengoringAssignment.objects.select_for_update(), pk=pk
        )
        if not _slutrengoring_can_act(request, assignment):
            raise Http404()
        if assignment.status != 'assigned':
            messages.error(request, "Opgaven kan ikke startes i sin nuværende status.")
        else:
            assignment.status = 'in_progress'
            assignment.started_at = now()
            assignment.save(update_fields=['status', 'started_at', 'last_updated'])
            messages.success(request, "Opgaven er markeret som i gang.")
    return redirect('organization_Slutrengoring_detail', pk=assignment.pk)


@login_required
@require_POST
def slutrengoring_done(request, pk):
    with transaction.atomic():
        assignment = get_object_or_404(
            models.SlutrengoringAssignment.objects.select_for_update(), pk=pk
        )
        if not _slutrengoring_can_act(request, assignment):
            raise Http404()
        if assignment.status not in models.SlutrengoringAssignment.ACTIVE_STATUSES:
            messages.error(request, "Opgaven er allerede afsluttet.")
            return redirect('organization_Slutrengoring_detail', pk=assignment.pk)

        team = assignment.team
        assignment.status = 'done'
        assignment.completed_at = now()
        assignment.completed_by = request.user
        assignment.save(
            update_fields=['status', 'completed_at', 'completed_by', 'last_updated']
        )
        messages.success(request, "Opgaven er markeret som udført.")

    return _slutrengoring_redirect_after_finish(request, assignment, team)


@login_required
@require_POST
def slutrengoring_not_finished(request, pk):
    reason = request.POST.get('reason', '').strip()
    with transaction.atomic():
        assignment = get_object_or_404(
            models.SlutrengoringAssignment.objects.select_for_update(), pk=pk
        )
        if not _slutrengoring_can_act(request, assignment):
            raise Http404()
        if assignment.status not in models.SlutrengoringAssignment.ACTIVE_STATUSES:
            messages.error(request, "Opgaven er allerede afsluttet.")
            return redirect('organization_Slutrengoring_detail', pk=assignment.pk)
        if not reason:
            messages.error(request, "Skriv hvorfor opgaven ikke kunne færdiggøres.")
            return redirect('organization_Slutrengoring_detail', pk=assignment.pk)

        team = assignment.team
        assignment.last_team = team
        assignment.team = None
        assignment.status = 'not_finished'
        assignment.assigned_at = None
        assignment.assigned_by = None
        assignment.started_at = None
        assignment.not_finished_at = now()
        assignment.not_finished_reason = reason
        assignment.attempt_count += 1
        assignment.completed_at = None
        assignment.completed_by = None
        assignment.save(
            update_fields=[
                'last_team', 'team', 'status', 'assigned_at', 'assigned_by',
                'started_at', 'not_finished_at', 'not_finished_reason',
                'attempt_count', 'completed_at', 'completed_by', 'last_updated',
            ]
        )
        messages.success(request, "Opgaven er returneret til puljen.")

    return _slutrengoring_redirect_after_finish(request, assignment, team)

