from datetime import time

from django import forms
from django.forms import TextInput
from django.utils import timezone

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
    
    class Meta:
        model = models.VolunteerAppointment
        fields = [
            'receiver', 
            'start_date', 'start_time', 
            'end_date', 'end_time', 
            'description'
        ]
        

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Setup Querysets
        # We order by first_name to make the dropdown readable
        self.fields["receiver"].queryset = models.Volunteer.objects.all().order_by("first_name")
        
        # Customize the receiver field display to show team short_name
        self.fields["receiver"].label_from_instance = self._label_from_instance

        # 2. Intelligent Initial Values (Don't override if instance exists)
        instance = kwargs.get('instance')
        
        if instance and instance.pk:
            # When updating, values come from the database
            pass 
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
    
    def _label_from_instance(self, obj):
        """Customize how each volunteer is displayed in the dropdown."""
        team = obj.teams.first()
        if team:
            return f"{obj.get_full_name()} ({team.short_name})"
        return obj.get_full_name()

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set default status for new appointments
        if not instance.pk:
            instance.status = "pending"
        
        if commit:
            instance.save()
        return instance

