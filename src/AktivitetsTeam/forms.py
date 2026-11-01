from datetime import time

from django import forms
from django.forms import TextInput
from django.utils import timezone

from AktivitetsTeam.models import AktivitetsTeamItem
from organization.models import Event, Team, TeamMembership, Volunteer

from . import models


class AktivitetsTeamItemForm(forms.ModelForm):
    class Meta:
        model = models.AktivitetsTeamItem
        fields = [
            "name",
            "description",
            "youtube_link",
            "short_description",
            "image",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class AktivitetsTeamBookingForm(forms.ModelForm):
    # Define fields without initial/queryset values at the class level
    start_date = forms.DateField(
        widget=TextInput(attrs={"type": "date"}),
        label="Start Dato:"
    )
    start_time = forms.TimeField(
        widget=TextInput(attrs={"type": "time"}),
        label="Start tidspunkt:"
    )
    end_date = forms.DateField(
        widget=TextInput(attrs={"type": "date"}),
        label="Slut dato:"
    )
    end_time = forms.TimeField(
        widget=TextInput(attrs={"type": "time"}),
        label="Slut tidspunkt:"
    )
    assigned_aktivitetsteam = forms.ModelMultipleChoiceField(
        queryset=Volunteer.objects.none(), # Start empty, populate in __init__
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = models.AktivitetsTeamBooking
        fields = [
            "item", "team", "team_contact", "remarks", 
            "start_date", "start_time", 
            "end_date", "end_time","location", 
        ]
        widgets = {
            "item": forms.Select(attrs={"class": "form-select"}),
            "team": forms.Select(attrs={"class": "form-select"}),
            "team_contact": forms.Select(attrs={"class": "form-select"}),
            "remarks": forms.Textarea(attrs={
                "class": "form-control",
                "placeholder": "Hvad er jeres formål... (forkortet for læsbarhed)"
            }),         
        }
        labels = {
            "item": "Aktivitet",
            "team": "Team",
            "team_contact": "Kontaktperson",
            "remarks": "Bemærkninger",
            "location": "Lokation",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Populate Dynamic Querysets Safely
        self.fields["item"].queryset = AktivitetsTeamItem.objects.filter(is_active=True).order_by("name")
        self.fields["team_contact"].queryset = Volunteer.objects.all().order_by("first_name")
        self.fields["team"].queryset = Team.objects.all().order_by("name")

        # 2. Handle the "Specific Team" (ID 8) logic safely
        try:
            my_specific_team = Team.objects.get(id=8)
            self.fields["assigned_aktivitetsteam"].queryset = Volunteer.objects.filter(
                teammembership__team=my_specific_team
            )
        except Team.DoesNotExist:
            self.fields["assigned_aktivitetsteam"].queryset = Volunteer.objects.none()

        # 3. Handle User-Specific Defaults
        if user:
            try:
                team_membership = TeamMembership.objects.get(member=user)
                self.fields["team"].initial = team_membership.team
                self.fields["team_contact"].queryset = Volunteer.objects.filter(
                    teammembership__team=team_membership.team
                )
            except TeamMembership.DoesNotExist:
                pass
            self.fields["team_contact"].initial = user

        # 4. Handle Event Dates / Initials
        instance = kwargs.get('instance')
        if instance:
            self.fields["start_date"].initial = instance.start_date
            self.fields["end_date"].initial = instance.end_date
            self.fields["start_time"].initial = instance.start_time
            self.fields["end_time"].initial = instance.end_time            
        else:
            # Safe lookup for active/next event
            active_event = Event.objects.filter(is_active=True).first()
            if not active_event:
                active_event = Event.objects.filter(start_date__gt=timezone.now()).order_by('start_date').first()

            if active_event:
                self.fields["start_date"].initial = active_event.start_date
                self.fields["end_date"].initial = active_event.end_date
                self.fields["start_time"].initial = time(8, 0)
                self.fields["end_time"].initial = time(8, 0)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.status = "Pending"
        if commit:
            instance.save()
        return instance


