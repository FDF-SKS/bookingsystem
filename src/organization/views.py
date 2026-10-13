from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import now
from django.http import Http404
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, PasswordResetView
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views import generic
from django.urls import reverse_lazy
from .forms import RegisterUserForm
from emailing.forms import BrandedPasswordResetForm
from . import models
from . import forms
from django.db.models import F, Q
from .models import Team, TeamMembership
from django.db.models import IntegerField
from django.db.models.functions import Cast

User = get_user_model()



@login_required
def home(request):
    return render(request, 'index.html')

def login_user(request):
    if request.method == "POST":
        username = request.POST['username'].lower()  # Convert to lowercase
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            messages.error(request, "There was an error logging in. Please try again.")
            return redirect('login_user')
    else:
        return render(request, 'organization/login.html', {})

def logout_user(request):
	logout(request)
	messages.success(request, ("You Were Logged Out!"))
	return redirect('home')


def register_user(request):
    if request.method == "POST":
        form = RegisterUserForm(request.POST)
        if form.is_valid():
            new_username = form.cleaned_data['username'].lower()  # Convert to lowercase
            password = form.cleaned_data['password1']

            User = get_user_model()  # Get the custom user model
            
            # Create a new user instance and set is_active to False
            new_user = User.objects.create_user(username=new_username, password=password, is_active=False)

            # Check if the team "Unassigned users" exists
            try:
                new_users_team = Team.objects.get(name="Unassigned users")
            except Team.DoesNotExist:
                # Handle the case when the team doesn't exist
                pass
            else:
                # Create a TeamMembership for the new user
                TeamMembership.objects.create(team=new_users_team, member=new_user)

            messages.success(request, "Registration Successful!")
            return redirect('home')
    else:
        form = RegisterUserForm()

    return render(request, 'organization/register_user.html', {
        'form': form,
    })



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


class EventMembershipCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.EventMembership
    form_class = forms.EventMembershipForm


class EventMembershipDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.EventMembership
    form_class = forms.EventMembershipForm


class EventMembershipUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.EventMembership
    form_class = forms.EventMembershipForm
    pk_url_kwarg = "pk"


class EventMembershipDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.EventMembership
    success_url = reverse_lazy("organization_EventMembership_list")


class EventListView(LoginRequiredMixin, generic.ListView):
    model = models.Event
    form_class = forms.EventForm


class EventCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.Event
    form_class = forms.EventForm


class EventDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Event
    form_class = forms.EventForm


class EventUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.Event
    form_class = forms.EventForm
    pk_url_kwarg = "pk"


class EventDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.Event
    success_url = reverse_lazy("organization_Event_list")


class TeamListView(LoginRequiredMixin, generic.ListView):
    model = models.Team
    form_class = forms.TeamForm


class TeamCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.Team
    form_class = forms.TeamForm


class TeamDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Team
    form_class = forms.TeamForm


class TeamUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.Team
    form_class = forms.TeamForm
    pk_url_kwarg = "pk"


class TeamDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.Team
    success_url = reverse_lazy("organization_Team_list")


class TeamMembershipListView(LoginRequiredMixin, generic.ListView):
    model = models.TeamMembership
    form_class = forms.TeamMembershipForm


class TeamMembershipCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.TeamMembership
    form_class = forms.TeamMembershipForm


class TeamMembershipDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.TeamMembership
    form_class = forms.TeamMembershipForm


class TeamMembershipUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.TeamMembership
    form_class = forms.TeamMembershipForm
    pk_url_kwarg = "pk"


class TeamMembershipDeleteView(LoginRequiredMixin, generic.DeleteView):
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


class VolunteerCreateView(LoginRequiredMixin, generic.CreateView):
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


class VolunteerDeleteView(generic.DeleteView):
    model = models.Volunteer
    success_url = reverse_lazy("organization_Volunteer_list")

class KeyListView(generic.ListView):
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

class KeyDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.Key
    success_url = reverse_lazy("organization_Key_list")



class VolunteerAppointmentListView(LoginRequiredMixin, generic.ListView):
    model = models.VolunteerAppointment
    context_object_name = 'appointments'

    def get_queryset(self):
        user = self.request.user
        # Filter where user is EITHER the requester OR the receiver
        return models.VolunteerAppointment.objects.filter(
            Q(requester=user) | Q(receiver=user)
        ).select_related(
            'requester', 'receiver'
        ).order_by('-start_date', '-start_time')
    
    
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

class VolunteerAppointmentDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.VolunteerAppointment
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django_comments_xtd.models import XtdComment
        from django.contrib.contenttypes.models import ContentType
        from django.urls import reverse
        
        # Get all comments for this appointment
        content_type = ContentType.objects.get_for_model(models.VolunteerAppointment)
        context['comments'] = XtdComment.objects.filter(
            content_type=content_type,
            object_pk=str(self.object.pk),
            is_public=True
        ).select_related('user').order_by('-submit_date')
        
        # Add flag for whether user can comment
        context['user_can_comment'] = (
            self.request.user == self.object.requester or 
            self.request.user == self.object.receiver
        )
        
        # Add URL for comment form submission
        context['comment_form_url'] = reverse('appointment_comment_add', kwargs={'pk': self.object.pk})
        
        return context

class VolunteerAppointmentUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.VolunteerAppointment
    form_class = forms.AppointmentForm
    # Fallback redirect if get_absolute_url isn't used
    success_url = reverse_lazy("organization_VolunteerAppointment_list") 

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class VolunteerAppointmentDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.VolunteerAppointment
    success_url = reverse_lazy("organization_VolunteerAppointment_list")




@login_required
@require_POST
def appointment_status_update(request, pk, new_status):
    # Only the receiver should be able to trigger this
    appointment = get_object_or_404(models.VolunteerAppointment, pk=pk, receiver=request.user)
    if new_status in ['accepted', 'rejected', 'pending']:
        appointment.status = new_status
        appointment.save()
    return redirect('organization_VolunteerAppointment_detail', pk=pk)


@login_required
@require_POST
def appointment_comment_add(request, pk):
    """Add a comment to a VolunteerAppointment."""
    from django_comments_xtd.models import XtdComment
    from django.contrib.contenttypes.models import ContentType
    from django.conf import settings
    
    appointment = get_object_or_404(models.VolunteerAppointment, pk=pk)
    
    # Only requester and receiver can comment
    if request.user != appointment.requester and request.user != appointment.receiver:
        return redirect('organization_VolunteerAppointment_detail', pk=pk)
    
    comment_text = request.POST.get('comment', '').strip()
    if not comment_text:
        messages.warning(request, "Kommentaren kan ikke være tom.")
        return redirect('organization_VolunteerAppointment_detail', pk=pk)
    
    content_type = ContentType.objects.get_for_model(models.VolunteerAppointment)
    
    comment = XtdComment.objects.create(
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


class TjanseOwnershipDetailView(LoginRequiredMixin, generic.DetailView):
    """Single tjanse assignment: description, swap request and reassignment history."""
    model = models.TjanseOwnership
    context_object_name = 'ownership'

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
            team_id__in=user_team_ids
        ).select_related('tjanse', 'event', 'team').order_by('due_date', 'status')


class TjanseOverviewView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'organization/tjanse_overview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        events = models.Event.objects.filter(is_active=True).order_by('start_date', 'name')
        event_id = self.request.GET.get('event')
        selected_event = events.filter(pk=event_id).first() if event_id else events.first()

        days = []
        rows = []
        if selected_event:
            days = [
                selected_event.start_date + timedelta(days=offset)
                for offset in range((selected_event.end_date - selected_event.start_date).days + 1)
            ]
            ownerships = models.TjanseOwnership.objects.filter(
                event=selected_event,
                due_date__gte=selected_event.start_date,
                due_date__lte=selected_event.end_date,
            ).select_related('team', 'tjanse').order_by('team__name')
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
                for tjanse in models.Tjanse.objects.order_by('title')
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
        form.fields['task_ownership'].queryset = models.TjanseOwnership.objects.filter(team_id__in=user_team_ids)
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

