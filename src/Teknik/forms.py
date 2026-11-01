from datetime import time

from django import forms
from django.forms.widgets import TextInput
from django.utils import timezone

from organization.models import Event, Team, TeamMembership, Volunteer

from . import models


class TeknikBookingForm(forms.ModelForm):
    # Manual date/time fields to force HTML5 inputs
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
        model = models.TeknikBooking
        fields = [
            "quantity",
            "team",
            "item",
            "start_date",
            "start_time",
            "end_date",
            "end_time",
            "team_contact",
            "location",    # Single location field from map_location
            "remarks",
            "delivery_needed",
            "assistance_needed",
        ]
        widgets = {
            "item": forms.Select(attrs={"class": "form-select"}),
            "team": forms.Select(attrs={"class": "form-select"}),
            "team_contact": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "address": forms.TextInput(attrs={"class": "form-control", "placeholder": "F.eks. Område G, bag scenen"}),
            "delivery_needed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "assistance_needed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            # 'location' is omitted here; the model's LocationField 
            # provides its own widget automatically.
        }
        labels = {
            "quantity": "Antal",
            "team": "Team",
            "item": "Teknik ting",
            "team_contact": "Kontaktperson",
            "location": "Vælg placering på kort",
            "remarks": "Bemærkninger",
            "delivery_needed": "Levering nødvendig",
            "assistance_needed": "Vi ønsker assistance",
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.status = "Pending"
        if commit:
            instance.save()
        return instance

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Queryset filtering and ordering
        self.fields["team"].queryset = Team.objects.all().order_by("name")
        self.fields["item"].queryset = models.TeknikItem.objects.all().order_by("name")
        
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

class TeknikItemForm(forms.ModelForm):
    class Meta:
        model = models.TeknikItem
        fields = [
            "name",
            "description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)



class TeknikTypeForm(forms.ModelForm):
    class Meta:
        model = models.TeknikType
        fields = [
            "name",
        ]


