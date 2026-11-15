from datetime import time

from django import forms
from django.conf import settings
from django.db.models import Q
from django.forms import TextInput
from django.utils import timezone
from django_tiptap_editor.forms.json_field import TipTapJSONFormField
from django_tiptap_editor.widgets.tiptap_widget import TipTapWidget

from . import models


class AllauthSignupForm(forms.Form):
    first_name = forms.CharField(max_length=30, label='Fornavn')
    last_name = forms.CharField(max_length=30, label='Efternavn')
    field_order = ['first_name', 'last_name', 'email', 'password1', 'password2']

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()



class TeamForm(forms.ModelForm):
    class Meta:
        model = models.Team
        fields = [
            "name",
            "short_name",
           # "events",
        ]


class TeamMembershipForm(forms.ModelForm):
    class Meta:
        model = models.TeamMembership
        fields = [
            "member",
            "team",
            "role",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = models.Team.objects.all()
        self.fields["member"].queryset = models.Volunteer.objects.all()



class EventForm(forms.ModelForm):
    class Meta:
        model = models.Event
        fields = [
            "name",
            "is_active",
            "start_date",
            "end_date",
            "deadline_sjak",
            "deadline_teknik",
            "deadline_mad",
            "deadline_aktivitetsteam",
            "deadline_foto",
            "deadline_lokaler",
            "deadline_sos",
        ]


class ProgramBlockForm(forms.ModelForm):
    """Create/edit form for a single framework or team programme block.

    ``event`` and ``team`` come from the view, which also enforces the
    permission to write in that scope. ``team`` is ``None`` for blocks in the
    shared framework, so the responsible dropdown then offers every volunteer;
    for a team block it offers that team's members.
    """

    content = TipTapJSONFormField(
        label='Indhold',
        required=False,
        widget=TipTapWidget(
            storage='json',
            config={
                **dict(getattr(settings, 'TIPTAP_DEFAULT_CONFIG', {})),
                'height': '240px',
            },
        ),
    )

    class Meta:
        model = models.ProgramBlock
        fields = [
            'title',
            'category',
            'day',
            'start_time',
            'end_time',
            'content',
            'responsible',
        ]
        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'F.eks. Morgenmad og briefing',
                }
            ),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'day': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d',
            ),
            'start_time': forms.TimeInput(
                attrs={'class': 'form-control', 'type': 'time'},
                format='%H:%M',
            ),
            'end_time': forms.TimeInput(
                attrs={'class': 'form-control', 'type': 'time'},
                format='%H:%M',
            ),
            'responsible': forms.SelectMultiple(
                attrs={'class': 'form-select', 'size': 6}
            ),
        }
        labels = {
            'title': 'Titel',
            'category': 'Type',
            'day': 'Dag',
            'start_time': 'Starttid',
            'end_time': 'Sluttid',
            'content': 'Indhold',
            'responsible': 'Ansvarlige',
        }

    def __init__(self, *args, event=None, team=None, **kwargs):
        self.event = event
        self.team = team
        super().__init__(*args, **kwargs)

        volunteers = models.Volunteer.objects.order_by('first_name', 'last_name')
        if team is not None:
            # Keep volunteers that are already responsible on the block even if
            # they have since left the team, so editing does not lose them.
            current_ids = []
            if self.instance.pk:
                current_ids = list(
                    self.instance.responsible.values_list('pk', flat=True)
                )
            volunteers = volunteers.filter(
                Q(teammembership__team=team) | Q(pk__in=current_ids)
            ).distinct()
        self.fields['responsible'].queryset = volunteers
        self.fields['responsible'].help_text = (
            'Vælg en eller flere medarbejdere. Hold Ctrl/Cmd nede for at vælge flere.'
        )

        if event is not None:
            self.fields['day'].initial = event.start_date
            self.fields['start_time'].initial = time(9, 0)
            self.fields['end_time'].initial = time(10, 0)

    def clean(self):
        cleaned_data = super().clean()
        day = cleaned_data.get('day')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and end_time and start_time >= end_time:
            self.add_error('end_time', 'Sluttiden skal være efter starttiden.')

        if (
            day
            and self.event is not None
            and not (self.event.start_date <= day <= self.event.end_date)
        ):
            self.add_error(
                'day', 'Dagen skal ligge inden for eventets periode.'
            )

        return cleaned_data


class EventMembershipForm(forms.ModelForm):
    class Meta:
        model = models.EventMembership
        fields = [
            "event",
            "volunteer",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["event"].queryset = models.Event.objects.all()
        self.fields["volunteer"].queryset = models.Volunteer.objects.all()

class TeamEventMembershipForm(forms.ModelForm):
    class Meta:
        model = models.TeamEventMembership
        fields = [
            "event",
            "team",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["event"].queryset = models.Event.objects.all()
        self.fields["team"].queryset = models.Team.objects.all()



class VolunteerForm(forms.ModelForm):
    class Meta:
        model = models.Volunteer
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
        ]


class VolunteerProfileUpdateForm(forms.ModelForm):
    """Form for volunteers to update their own profile including email and picture"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control bg-light border-0 py-2',
            'placeholder': 'Din e-mail adresse'
        })
    )
    
    class Meta:
        model = models.Volunteer
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "image",
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control bg-light border-0 py-2',
                'placeholder': 'Dit fornavn'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control bg-light border-0 py-2',
                'placeholder': 'Dit efternavn'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control bg-light border-0 py-2',
                'placeholder': 'Dit telefonnummer'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control bg-light border-0 py-2',
                'accept': 'image/*'
            }),
        }
        labels = {
            'first_name': 'Fornavn',
            'last_name': 'Efternavn',
            'email': 'E-mail',
            'phone': 'Telefon',
            'image': 'Profilbillede',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Check if email is unique, excluding the current user
        if models.Volunteer.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Denne e-mail adresse er allerede i brug. Væg venligst en anden.')
        return email


class KeyForm(forms.ModelForm):
    class Meta:
        model = models.Key
        fields = [
            "number",
            "name", 
            "description", 
            "current_user"] 
        widgets = {
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly'
                }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'readonly': 'readonly' 
                }),
            'description': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control',
                'readonly': 'readonly' 
                }),
            'current_user': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'number': 'Nøgle nummer',
            'name': 'Nøgle navn',
            'description': 'Beskrivelse',
            'current_user': 'Udleveret til',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["current_user"].queryset = models.Volunteer.objects.all().order_by('first_name')



class AppointmentForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=TextInput(attrs={"type": "date", "class": "form-control"}),
        label="Start Dato"
    )
    start_time = forms.TimeField(
        widget=TextInput(attrs={"type": "time", "class": "form-control"}),
        label="Start tidspunkt"
    )
    end_date = forms.DateField(
        widget=TextInput(attrs={"type": "date", "class": "form-control"}),
        label="Slut Dato"
    )
    end_time = forms.TimeField(
        widget=TextInput(attrs={"type": "time", "class": "form-control"}),
        label="Slut tidspunkt"
    )
    # One dropdown for both choices: a single person or a whole team. The value
    # is ``person:<pk>`` or ``team:<pk>``; groups keep the list readable.
    recipient = forms.ChoiceField(
        label="Modtager",
        required=True,
        help_text="Vælg en person eller et helt team - ikke begge.",
    )

    class Meta:
        model = models.VolunteerAppointment
        fields = [
            'shared_with_team',
            'start_date', 'start_time',
            'end_date', 'end_time',
            'description'
        ]
        labels = {
            'shared_with_team': 'Del aftalen med dit team',
            'description': 'Aftalens indhold',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        self.fields["recipient"].choices = self._recipient_choices(user)

        instance = kwargs.get('instance')

        if instance and instance.pk:
            # Show who the appointment currently points at.
            if instance.receiver_id:
                self.fields["recipient"].initial = f"person:{instance.receiver_id}"
            elif instance.receiver_team_id:
                self.fields["recipient"].initial = f"team:{instance.receiver_team_id}"
        else:
            # For NEW appointments, find the active or next event
            active_event = models.Event.objects.filter(is_active=True).first()
            if not active_event:
                active_event = models.Event.objects.filter(
                    start_date__gt=timezone.now()
                ).order_by('start_date').first()

            if active_event:
                self.fields["start_date"].initial = active_event.start_date
                self.fields["end_date"].initial = active_event.start_date # Default to same day
                self.fields["start_time"].initial = time(12, 0)
                self.fields["end_time"].initial = time(13, 0)

    def _recipient_choices(self, user):
        """Return grouped choices: a person or a whole team."""
        receivers = models.Volunteer.objects.prefetch_related('teams').order_by(
            "first_name", "last_name"
        )
        if user and user.is_authenticated:
            receivers = receivers.exclude(pk=user.pk)

        person_choices = []
        for person in receivers:
            team = next(iter(person.teams.all()), None)
            label = person.get_full_name() or person.username
            if team:
                label = f"{label} ({team.short_name})"
            person_choices.append((f"person:{person.pk}", label))

        # The requester's own teams are left out: a legeaftale is meant to
        # reach another group.
        teams = models.Team.objects.order_by("name")
        if user and user.is_authenticated and not user.is_staff:
            teams = teams.exclude(pk__in=user.teams.values('pk'))
        team_choices = [(f"team:{team.pk}", f"{team.name} (team)") for team in teams]

        return [
            ("", "Vælg person eller team"),
            ("Personer", person_choices),
            ("Teams", team_choices),
        ]

    def clean(self):
        cleaned_data = super().clean()
        value = cleaned_data.get('recipient')
        if not value:
            return cleaned_data

        kind, _, raw_pk = value.partition(':')
        try:
            pk = int(raw_pk)
        except (TypeError, ValueError):
            raise forms.ValidationError("Vælg en gyldig modtager.") from None

        if kind == 'person':
            receiver = models.Volunteer.objects.filter(pk=pk).first()
            if receiver is None:
                raise forms.ValidationError("Den valgte person findes ikke længere.")
            if self.user and receiver.pk == self.user.pk:
                self.add_error('recipient', "Du kan ikke lave en aftale med dig selv.")
            self.instance.receiver = receiver
            self.instance.receiver_team = None
        elif kind == 'team':
            team = models.Team.objects.filter(pk=pk).first()
            if team is None:
                raise forms.ValidationError("Det valgte team findes ikke længere.")
            self.instance.receiver_team = team
            self.instance.receiver = None
        else:
            raise forms.ValidationError("Vælg en gyldig modtager.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set default status for new appointments
        if not instance.pk:
            instance.status = "pending"
        
        if commit:
            instance.save()
        return instance

