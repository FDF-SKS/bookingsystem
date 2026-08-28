from django import forms

from organization.models import Team, TeamMembership

from .models import Hold, Loeb, PhysicalStation, Task, TaskSubmission


class LoebForm(forms.ModelForm):
    class Meta:
        model = Loeb
        fields = ['name', 'team', 'event', 'description', 'is_active', 'show_map', 'show_points']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'team': forms.Select(attrs={'class': 'form-select'}),
            'event': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_map': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_points': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user and user.is_authenticated:
            memberships = TeamMembership.objects.filter(member=user).select_related('team')
            team_ids = list(memberships.values_list('team_id', flat=True))

            if team_ids:
                self.fields['team'].queryset = Team.objects.filter(id__in=team_ids).order_by('name')
                first_membership = memberships.order_by('team__name').first()
                if first_membership:
                    self.fields['team'].initial = first_membership.team
            else:
                self.fields['team'].queryset = Team.objects.none()
                self.fields['team'].empty_label = 'Du er ikke tilknyttet et team'
        else:
            self.fields['team'].queryset = Team.objects.all().order_by('name')


class PhysicalStationForm(forms.ModelForm):
    class Meta:
        model = PhysicalStation
        fields = ['name', 'qr_code', 'description', 'location', 'is_active']
        labels = {
            'name': 'Stationsnavn',
            'qr_code': 'QR-kode',
            'description': 'Beskrivelse',
            'location': 'Kortplacering',
            'is_active': 'Aktiv',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'qr_code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'loeb', 'title', 'description', 'task_type', 'station', 'location',
            'gps_radius_meters', 'qr_code', 'points', 'input_mode', 'is_published'
        ]
        labels = {
            'loeb': 'Løb',
            'title': 'Titel',
            'description': 'Beskrivelse',
            'task_type': 'Type',
            'station': 'Station',
            'location': 'Kortplacering',
            'gps_radius_meters': 'GPS-radius (meter)',
            'qr_code': 'QR-kode',
            'points': 'Point',
            'input_mode': 'Inputtype',
            'is_published': 'Offentliggjort',
        }
        widgets = {
            'loeb': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'task_type': forms.Select(attrs={'class': 'form-select'}),
            'station': forms.Select(attrs={'class': 'form-select'}),
            'gps_radius_meters': forms.NumberInput(attrs={'class': 'form-control'}),
            'qr_code': forms.TextInput(attrs={'class': 'form-control'}),
            'points': forms.NumberInput(attrs={'class': 'form-control'}),
            'input_mode': forms.TextInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            from organization.models import TeamMembership
            team_ids = list(TeamMembership.objects.filter(member=user).values_list('team_id', flat=True))
            if team_ids:
                self.fields['loeb'].queryset = self.fields['loeb'].queryset.filter(team_id__in=team_ids).order_by('name')
            else:
                self.fields['loeb'].queryset = self.fields['loeb'].queryset.none()
                self.fields['loeb'].empty_label = 'Du har ikke adgang til et løb'

        self.fields['station'].queryset = PhysicalStation.objects.filter(is_active=True).order_by('name')


class HoldForm(forms.ModelForm):
    class Meta:
        model = Hold
        fields = ['loeb', 'name', 'pin_code', 'is_active']
        widgets = {
            'loeb': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'pin_code': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TaskSubmissionForm(forms.ModelForm):
    class Meta:
        model = TaskSubmission
        fields = ['hold', 'task', 'state', 'submitted_answer', 'points_awarded']
        widgets = {
            'hold': forms.Select(attrs={'class': 'form-select'}),
            'task': forms.Select(attrs={'class': 'form-select'}),
            'state': forms.Select(attrs={'class': 'form-select'}),
            'submitted_answer': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'points_awarded': forms.NumberInput(attrs={'class': 'form-control'}),
        }
