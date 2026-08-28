from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views import generic
from django.urls import reverse, reverse_lazy

from organization.models import TeamMembership

from . import forms, models


@login_required
def move_task_up(request, pk):
    task = get_object_or_404(models.Task, pk=pk)
    previous = models.Task.objects.filter(loeb=task.loeb, order__lt=task.order).order_by('-order').first()
    if previous:
        task.order, previous.order = previous.order, task.order
        task.save(update_fields=['order'])
        previous.save(update_fields=['order'])
        messages.success(request, f'"{task.title}" flyttet op.')
    return HttpResponseRedirect(reverse('Loeb_Task_list'))


@login_required
def move_task_down(request, pk):
    task = get_object_or_404(models.Task, pk=pk)
    next_task = models.Task.objects.filter(loeb=task.loeb, order__gt=task.order).order_by('order').first()
    if next_task:
        task.order, next_task.order = next_task.order, task.order
        task.save(update_fields=['order'])
        next_task.save(update_fields=['order'])
        messages.success(request, f'"{task.title}" flyttet ned.')
    return HttpResponseRedirect(reverse('Loeb_Task_list'))


class LoebListView(LoginRequiredMixin, generic.ListView):
    model = models.Loeb
    context_object_name = 'loeb_list'
    template_name = 'Loeb/loeb_list.html'

    def get_queryset(self):
        queryset = super().get_queryset()
        memberships = TeamMembership.objects.filter(member=self.request.user).values_list('team_id', flat=True)
        return queryset.filter(team_id__in=memberships).order_by('-created') if memberships else queryset.none()


class LoebCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.Loeb
    form_class = forms.LoebForm
    template_name = 'Loeb/loeb_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy('Loeb_Loeb_list')


class LoebDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Loeb
    form_class = forms.LoebForm
    template_name = 'Loeb/loeb_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loeb = self.object
        holds = list(loeb.holds.all().order_by('name'))
        tasks = list(loeb.tasks.all().order_by('order', 'title'))

        task_progress = []
        for task in tasks:
            submissions = models.TaskSubmission.objects.filter(task=task)
            total_holds = len(holds)
            completed = submissions.filter(state='GRADED').count()
            submitted = submissions.filter(state='SUBMITTED').count()
            unlocked = submissions.filter(state='UNLOCKED').count()
            percentage = 0 if total_holds == 0 else round((completed / total_holds) * 100)
            task_progress.append({
                'task': task,
                'total_holds': total_holds,
                'completed': completed,
                'submitted': submitted,
                'unlocked': unlocked,
                'percentage': percentage,
            })

        hold_progress = []
        for hold in holds:
            completed_tasks = models.TaskSubmission.objects.filter(hold=hold, state='GRADED').count()
            total_tasks = len(tasks)
            hold_progress.append({
                'hold': hold,
                'completed_tasks': completed_tasks,
                'total_tasks': total_tasks,
                'percentage': 0 if total_tasks == 0 else round((completed_tasks / total_tasks) * 100),
            })

        context['holds'] = holds
        context['tasks'] = tasks
        context['task_progress'] = task_progress
        context['hold_progress'] = hold_progress
        return context


class LoebUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.Loeb
    form_class = forms.LoebForm
    pk_url_kwarg = 'pk'
    template_name = 'Loeb/loeb_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy('Loeb_Loeb_list')


class LoebDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.Loeb
    success_url = reverse_lazy('Loeb_Loeb_list')


class PhysicalStationListView(LoginRequiredMixin, generic.ListView):
    model = models.PhysicalStation
    context_object_name = 'physical_station_list'


class PhysicalStationCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.PhysicalStation
    form_class = forms.PhysicalStationForm


class PhysicalStationDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.PhysicalStation
    form_class = forms.PhysicalStationForm


class PhysicalStationUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.PhysicalStation
    form_class = forms.PhysicalStationForm
    pk_url_kwarg = 'pk'


class PhysicalStationDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.PhysicalStation
    success_url = reverse_lazy('Loeb_PhysicalStation_list')


class TaskListView(LoginRequiredMixin, generic.ListView):
    model = models.Task
    context_object_name = 'task_list'
    template_name = 'Loeb/task_list.html'

    def get_queryset(self):
        queryset = super().get_queryset()
        team_ids = TeamMembership.objects.filter(member=self.request.user).values_list('team_id', flat=True)
        return queryset.filter(loeb__team_id__in=team_ids).order_by('order', 'title') if team_ids else queryset.none()


class TaskCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.Task
    form_class = forms.TaskForm
    template_name = 'Loeb/task_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not form.instance.order:
            form.instance.order = models.Task.next_order_for_loeb(form.instance.loeb)
        return super().form_valid(form)

    def get_success_url(self):
        if self.object and self.object.loeb_id:
            return reverse_lazy('Loeb_Loeb_detail', kwargs={'pk': self.object.loeb_id})
        return reverse_lazy('Loeb_Task_list')


class TaskDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Task
    form_class = forms.TaskForm
    template_name = 'Loeb/task_detail.html'


class TaskUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.Task
    form_class = forms.TaskForm
    pk_url_kwarg = 'pk'
    template_name = 'Loeb/task_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        if self.object and self.object.loeb_id:
            return reverse_lazy('Loeb_Loeb_detail', kwargs={'pk': self.object.loeb_id})
        return reverse_lazy('Loeb_Task_list')


class TaskDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.Task
    success_url = reverse_lazy('Loeb_Task_list')


class HoldListView(LoginRequiredMixin, generic.ListView):
    model = models.Hold
    context_object_name = 'hold_list'


class HoldListView(LoginRequiredMixin, generic.ListView):
    model = models.Hold
    context_object_name = 'hold_list'
    template_name = 'Loeb/hold_list.html'

    def get_queryset(self):
        queryset = super().get_queryset()
        team_ids = TeamMembership.objects.filter(member=self.request.user).values_list('team_id', flat=True)
        return queryset.filter(loeb__team_id__in=team_ids).order_by('name') if team_ids else queryset.none()


class HoldCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.Hold
    form_class = forms.HoldForm
    template_name = 'Loeb/hold_form.html'

    def get_initial(self):
        initial = super().get_initial().copy()
        loeb_id = self.request.GET.get('loeb')
        if loeb_id:
            initial['loeb'] = loeb_id
        return initial

    def get_success_url(self):
        if self.object and self.object.loeb_id:
            return reverse_lazy('Loeb_Loeb_detail', kwargs={'pk': self.object.loeb_id})
        return reverse_lazy('Loeb_Hold_list')


class HoldDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Hold
    form_class = forms.HoldForm
    template_name = 'Loeb/hold_detail.html'


class HoldUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.Hold
    form_class = forms.HoldForm
    pk_url_kwarg = 'pk'
    template_name = 'Loeb/hold_form.html'

    def get_success_url(self):
        if self.object and self.object.loeb_id:
            return reverse_lazy('Loeb_Loeb_detail', kwargs={'pk': self.object.loeb_id})
        return reverse_lazy('Loeb_Hold_list')


class HoldDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.Hold
    template_name = 'Loeb/hold_confirm_delete.html'

    def get_success_url(self):
        if self.object and self.object.loeb_id:
            return reverse_lazy('Loeb_Loeb_detail', kwargs={'pk': self.object.loeb_id})
        return reverse_lazy('Loeb_Hold_list')


def station_qr(request, qr_code):
    station = get_object_or_404(models.PhysicalStation, qr_code=qr_code)
    hold_id = request.session.get('loeb_hold_id')

    if not hold_id:
        return render(request, 'Loeb/station_qr.html', {
            'station': station,
            'hold': None,
            'task': None,
            'message': 'Bare ærgeligt - ingen post her',
        })

    hold = get_object_or_404(models.Hold, pk=hold_id)
    task = models.Task.objects.filter(station=station, loeb=hold.loeb).order_by('order', 'title').first()

    if not task:
        return render(request, 'Loeb/station_qr.html', {
            'station': station,
            'hold': hold,
            'task': None,
            'message': 'Bare ærgeligt - ingen post her',
        })

    submission, _ = models.TaskSubmission.objects.get_or_create(hold=hold, task=task)

    if request.method == 'POST':
        answer = (request.POST.get('submitted_answer') or '').strip()
        submission.submitted_answer = answer
        submission.state = 'SUBMITTED'
        submission.save(update_fields=['submitted_answer', 'state', 'last_updated'])
        return render(request, 'Loeb/station_qr.html', {
            'station': station,
            'hold': hold,
            'task': task,
            'submission': submission,
            'message': 'Svar gemt.',
            'show_form': task.input_mode and task.input_mode.lower() != 'none',
        })

    return render(request, 'Loeb/station_qr.html', {
        'station': station,
        'hold': hold,
        'task': task,
        'submission': submission,
        'message': '',
        'show_form': task.input_mode and task.input_mode.lower() != 'none',
    })


def hold_login(request, loeb_pk):
    loeb = get_object_or_404(models.Loeb, pk=loeb_pk)
    error = None

    if request.method == 'POST':
        pin_code = (request.POST.get('pin_code') or '').strip()
        hold = models.Hold.objects.filter(loeb=loeb, pin_code=pin_code).first()

        if hold:
            request.session['loeb_hold_id'] = hold.pk
            request.session['loeb_id'] = loeb.pk
            return HttpResponseRedirect(reverse('Loeb_Hold_dashboard', args=[loeb.pk]))

        error = 'Ugyldig pin-kode. Prøv igen.'

    preview_hold = loeb.holds.order_by('name').first()
    return render(request, 'Loeb/hold_login.html', {
        'loeb': loeb,
        'error': error,
        'preview_hold': preview_hold,
    })


def hold_dashboard(request, loeb_pk):
    loeb = get_object_or_404(models.Loeb, pk=loeb_pk)
    hold_id = request.session.get('loeb_hold_id')

    if not hold_id:
        return HttpResponseRedirect(reverse('Loeb_Hold_login', args=[loeb.pk]))

    hold = get_object_or_404(models.Hold, pk=hold_id, loeb=loeb)
    tasks = list(loeb.tasks.all().order_by('order', 'title'))
    task_rows = []

    for task in tasks:
        submission = models.TaskSubmission.objects.filter(hold=hold, task=task).first()
        if submission:
            state = submission.state
            labels = {
                'UNLOCKED': 'Låst op',
                'SUBMITTED': 'Indsendt',
                'GRADED': 'Godkendt',
            }
        else:
            state = 'LOCKED'
            labels = {'LOCKED': 'Låst'}

        task_rows.append({
            'task': task,
            'submission': submission,
            'state': state,
            'status_label': labels.get(state, 'Låst'),
        })

    return render(request, 'Loeb/hold_dashboard.html', {
        'loeb': loeb,
        'hold': hold,
        'task_rows': task_rows,
    })


def hold_logout(request, loeb_pk):
    request.session.pop('loeb_hold_id', None)
    request.session.pop('loeb_id', None)
    return HttpResponseRedirect(reverse('Loeb_Hold_login', args=[loeb_pk]))


class TaskSubmissionListView(LoginRequiredMixin, generic.ListView):
    model = models.TaskSubmission
    context_object_name = 'task_submission_list'


class TaskSubmissionCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.TaskSubmission
    form_class = forms.TaskSubmissionForm


class TaskSubmissionDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.TaskSubmission
    form_class = forms.TaskSubmissionForm


class TaskSubmissionUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = models.TaskSubmission
    form_class = forms.TaskSubmissionForm
    pk_url_kwarg = 'pk'


class TaskSubmissionDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = models.TaskSubmission
    success_url = reverse_lazy('Loeb_TaskSubmission_list')
