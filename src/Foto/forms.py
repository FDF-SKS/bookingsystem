from datetime import time

from django import forms
from django.forms.widgets import TextInput
from django.utils import timezone

from organization.models import Event, Team, TeamMembership, Volunteer
from organization.permissions import restrict_team_field

from . import models


class FotoItemForm(forms.ModelForm):
    class Meta:
        model = models.FotoItem
        fields = ["name", "description"]

class FotoBookingForm(forms.ModelForm):

    start_date = forms.DateField(
        widget=TextInput(attrs={"type": "date"}),
        label="Afhentning Dato:"
    )
    start_time = forms.TimeField(
        widget=TextInput(attrs={"type": "time"}),
        label="Afhentning tidspunkt:"
    )
    end_date = forms.DateField(
        widget=TextInput(attrs={"type": "date"}),
        label="Retur dato:"
    )
    end_time = forms.TimeField(
        widget=TextInput(attrs={"type": "time"}),
        label="Retur tidspunkt:"
    )

    class Meta:
        model = models.FotoBooking
        fields = [
            "item",
            "team",
            "team_contact",
            "remarks",
            "location",
            "start_date",
            "start_time",
            "end_date",
            "end_time",
        ]
        widgets = {
            "item": forms.Select(attrs={"class": "form-select"}),
            "team": forms.Select(attrs={"class": "form-select"}),
            "team_contact": forms.Select(attrs={"class": "form-select"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3}),    
        }
        labels = {
            "team": "Team",
            "item": "Foto udstyr/service",
            "start_date": "Start Dato",
            "start_time": "Start tidspunkt",
            "end_date": "Slut dato",
            "end_time": "Slut tidspunkt",
            "team_contact": "Kontaktperson",
            "remarks": "Bemærkninger",
            "location": "Placering",
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Ensure status is set if not already present
        if not instance.status:
            instance.status = "Pending"
        if commit:
            instance.save()
        return instance

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Queryset filtering and ordering
        self.fields["team"].queryset = Team.objects.all().order_by("name")
        self.fields["item"].queryset = models.FotoItem.objects.all().order_by("name")
        restrict_team_field(user, self.fields["team"])
        
        # 2. User-specific defaults and contact filtering
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

        # 3. Handle Event Dates / Initials
        instance = kwargs.get('instance')
        if instance:
            self.fields["start_date"].initial = instance.start_date
            self.fields["end_date"].initial = instance.end_date
            self.fields["start_time"].initial = instance.start_time
            self.fields["end_time"].initial = instance.end_time            
        else:
            # Safe lookup for active or upcoming event
            active_event = Event.objects.filter(is_active=True).first()
            if not active_event:
                active_event = Event.objects.filter(start_date__gt=timezone.now()).order_by('start_date').first()

            if active_event:
                self.fields["start_date"].initial = active_event.start_date
                self.fields["end_date"].initial = active_event.end_date
                self.fields["start_time"].initial = time(8, 0)
                self.fields["end_time"].initial = time(8, 0)

