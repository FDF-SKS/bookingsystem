from django import forms
from Butikken.models import ButikkenItemType, ButikkenItem, Day, Meal, Option, Recipe
from organization.models import Team, TeamMembership, Volunteer, Event
from django.shortcuts import render, redirect
from django.urls import reverse
from django.forms import BaseFormSet, TextInput, formset_factory
from . import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.utils import timezone
from datetime import time



from django import forms
from .models import MealPlan, MealOption, TeamMealPlan, MealBooking
from django.contrib.auth.models import User

class MealBookingForm(forms.ModelForm):
    class Meta:
        model = MealBooking
        fields = [
            'team',
            'team_contact',
            'status',
            ]  # Add other fields as necessary
        widgets = {
            "team": forms.Select(attrs={"class": "form-control", "data-error": "Please select a team."}),
            "team_contact": forms.Select(attrs={"class": "form-control", "data-error": "Please select a team contact"}),
            "status": forms.Select(attrs={"class": "form-control", "data-error": "Please select a status."}),
        }
    def __init__(self, *args, user=None, **kwargs):
        super(MealBookingForm, self).__init__(*args, **kwargs)
        self.fields["team_contact"].queryset = Volunteer.objects.all().order_by("first_name")
        self.fields["team"].queryset = Team.objects.all().order_by("name")
        
        self.fields["team_contact"].initial = user
        if user:
            team_membership = TeamMembership.objects.filter(member=user).first()
            
            if team_membership:
                self.fields["team"].initial = team_membership.team
                self.fields["team_contact"].queryset = Volunteer.objects.filter(
                    teammembership__team=team_membership.team
                )
                self.fields["team_contact"].initial = user
            else:
                print(f"Warning: User {user} has no team membership.")

class MealForm(forms.ModelForm):
    class Meta:
        model = models.Meal
        fields = [
            "type",
            "day",
        ]

    def __init__(self, *args, **kwargs):
        super(MealForm, self).__init__(*args, **kwargs)
        self.fields["day"].queryset = Day.objects.all()

class OptionForm(forms.ModelForm):
    class Meta:
        model = models.Option
        fields = [
            "meal",
            "recipe",
        ]

    def __init__(self, *args, **kwargs):
        super(OptionForm, self).__init__(*args, **kwargs)
        self.fields["meal"].queryset = Meal.objects.all()
        self.fields["recipe"].queryset = Recipe.objects.all()



class DayForm(forms.ModelForm):
    class Meta:
        model = models.Day
        fields = [
            "name",
            "date",
        ]


class RecipeForm(forms.ModelForm):
    class Meta:
        model = models.Recipe
        fields = [
            "name",
            "description",
        ]

class ButikkenItemForm(forms.ModelForm):
    class Meta:
        model = models.ButikkenItem
        fields = [
            "description",
            "name",
            "type",
            "content_normal",
            "content_unit",
        ]

    def __init__(self, *args, **kwargs):
        super(ButikkenItemForm, self).__init__(*args, **kwargs)
        self.fields["type"].queryset = ButikkenItemType.objects.all()

class ButikkenBookingForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=TextInput(attrs={"type": "date"}),
        label="Afhentning Dato:"
    )
    start_time = forms.TimeField(
        widget=TextInput(attrs={"type": "time"}),
        label="Afhentning Tidspunkt:"
    )
    date_used = forms.DateField(
        widget=TextInput(attrs={"type": "date"}),
        label="Anvendelsesdato:"
    )
    class Meta:
        model = models.ButikkenBooking
        fields =[
            "item",
            "team",
            "team_contact",
            "start_date",
            "start_time",
            "quantity",
            "unit",
            "for_meal",
            "remarks",
            "date_used",
        ]

        labels = {
            "item": "Vare",
            "team": "Team",
            "team_contact": "Kontaktperson",
            "quantity": "Antal",
            "unit": "Enhed",
            "for_meal": "Måltid",
            "remarks": "Bemærkninger",
            "start_date": "Afhentning Dato",
            "start_time": "Afhentning Tidspunkt",
            "date_used": "Anvendelsesdato",

        }
        widgets = {
            # Added tom-select class and placeholder
            "item": forms.Select(attrs={"class": "tom-select", "placeholder": "Søg efter vare..."}),
            "team": forms.Select(attrs={"class": "form-select"}),
            "team_contact": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "1"}),
            "unit": forms.TextInput(attrs={"class": "form-control"}),            
            "for_meal": forms.Select(attrs={"class": "form-select"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "start_date": forms.TextInput(attrs={"class": "form-control", "type": "date"}),
            "start_time": forms.TextInput(attrs={"class": "form-control", "type": "time"}),
            "date_used": forms.TextInput(attrs={"class": "form-control", "type": "date"}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.status = "Pending"
        if commit:
            instance.save()
        return instance
    
    def __init__(self, *args, user=None, **kwargs):
        super(ButikkenBookingForm, self).__init__(*args, **kwargs)
        self.fields["item"].queryset = ButikkenItem.objects.all()
        self.fields["team"].queryset = Team.objects.all()
        self.fields["team_contact"].queryset = Volunteer.objects.all()
        self.fields["item"].empty_label = "Begynd at skrive for at finde en vare..."
        
        if user:
            # CHANGE: Use filter().first() instead of .get()
            team_membership = TeamMembership.objects.filter(member=user).first()
            
            if team_membership:
                self.fields["team"].initial = team_membership.team
                self.fields["team_contact"].queryset = Volunteer.objects.filter(
                    teammembership__team=team_membership.team
                )
                self.fields["team_contact"].initial = user
            else:
                print(f"Warning: User {user} has no team membership.")
        # 4. Handle Event Dates / Initials
        instance = kwargs.get('instance')
        if instance:
            self.fields["start_date"].initial = instance.start_date
            self.fields["start_time"].initial = instance.start_time    
            self.fields["date_used"].initial = instance.date_used       
        else:
            # Safe lookup for active/next event
            active_event = Event.objects.filter(is_active=True).first()
            if not active_event:
                active_event = Event.objects.filter(start_date__gt=timezone.now()).order_by('start_date').first()

            if active_event:
                self.fields["start_date"].initial = active_event.start_date
                self.fields["start_time"].initial = time(8, 0)
                self.fields["date_used"].initial = active_event.start_date
        
# Function to get the next event
        def get_next_event():
            now = timezone.now()
            next_event = Event.objects.filter(start_date__gt=now).order_by('start_date').first()
            return next_event
        
        # Check if the form is being initialized with an instance
        if self.instance and self.instance.pk:
            # Use the existing value from the instance
            self.fields["start_date"].initial = self.instance.start_date.strftime('%Y-%m-%d')
            print(self.instance.start_date.strftime('%Y-%m-%d'))
        else:
            # Use the next event's start date if no instance or new instance
            next_event = get_next_event()
            if next_event:
                self.fields["start_date"].initial = next_event.start_date.strftime('%Y-%m-%d')
                self.fields["start_time"].initial = time(8, 0)  # Set default time to 08:00 AM


class ButikkenOrderForm(forms.ModelForm):
    class Meta:
        model = models.ButikkenOrder
        fields = [
            "team",
            "team_contact",
            "name",
            "pickup_date",
            "remarks",
        ]
        widgets = {
            "team": forms.Select(attrs={"class": "form-select"}),
            "team_contact": forms.Select(attrs={"class": "form-select"}),
            "pickup_date": forms.TextInput(attrs={"class": "form-control", "type": "date"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super(ButikkenOrderForm, self).__init__(*args, **kwargs)
        self.fields["team"].queryset = Team.objects.all()
        self.fields["team_contact"].queryset = Volunteer.objects.all()
        if user:
            team_membership = TeamMembership.objects.filter(member=user).first()
            if team_membership:
                self.fields["team"].initial = team_membership.team
                self.fields["team_contact"].initial = user
        # Only allow staff/admin users to edit status. For regular users we omit the status field.
        try:
            is_staff = bool(user and user.is_staff)
        except Exception:
            is_staff = False
        if is_staff:
            # Add status field dynamically for staff users
            self.fields['status'] = forms.ChoiceField(
                choices=models.ButikkenOrder.STATUS_CHOICES,
                initial=(self.instance.status if getattr(self.instance, 'pk', None) else 'Afventer'),
                widget=forms.Select(attrs={"class": "form-select"}),
                required=True,
            )
        # Default pickup_date from the active event (or next upcoming event)
        try:
            active_event = Event.objects.filter(is_active=True).first()
            if not active_event:
                active_event = (
                    Event.objects.filter(start_date__gt=timezone.now().date()).order_by("start_date").first()
                )
            if active_event:
                self.fields["pickup_date"].initial = active_event.start_date
        except Exception:
            # Be defensive: if Event lookup fails, leave the field empty
            pass


class ButikkenAddItemForm(forms.Form):
    item = forms.ModelChoiceField(queryset=ButikkenItem.objects.all(), widget=forms.Select(attrs={"class": "form-select"}))
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, initial=1, widget=forms.NumberInput(attrs={"class": "form-control", "step": "1"}))
    # Make unit readonly so it is shown but not editable; JS will prefill this from the item
    unit = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"}))
    start_date = forms.DateField(widget=TextInput(attrs={"type": "date", "class": "form-control"}))
    start_time = forms.TimeField(widget=TextInput(attrs={"type": "time", "class": "form-control"}))
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}))



class ButikkenItemTypeForm(forms.ModelForm):
    class Meta:
        model = models.ButikkenItemType
        fields = [
            "name",
            "description",
        ]


class MealPlanForm(forms.ModelForm):
    class Meta:
        model = MealPlan
        fields = [
            "name",
            "meal_date",
            "open_date",
            "close_date",
        ]

    def __init__(self, *args, **kwargs):
        super(MealPlanForm, self).__init__(*args, **kwargs)

class MealOptionForm(forms.ModelForm):
    class Meta:
        model = MealOption
        fields = [
            "meal_plan",
            "recipe",
        ]

    def __init__(self, *args, **kwargs):
        super(MealOptionForm, self).__init__(*args, **kwargs)
        self.fields["meal_plan"].queryset = MealPlan.objects.all()
        self.fields["recipe"].queryset = Recipe.objects.all()


class TeamMealPlanForm(forms.ModelForm):
    class Meta:
        model = models.TeamMealPlan
        fields = [
            "meal_plan",
            "meal_option",
            "team",
            "team_contact",
        ]
        labels = {
            "meal_plan": "Måltid",
            "meal_option": "Måltidspakke",
            "team": "Team",
            "team_contact": "Kontaktperson",
        }

    def __init__(self, *args, **kwargs):
        meal_plan = kwargs.pop('meal_plan', None)
        user = kwargs.pop('user', None)
        super(TeamMealPlanForm, self).__init__(*args, **kwargs)
        self.fields["meal_plan"].queryset = MealPlan.objects.all()
        self.fields["team"].queryset = Team.objects.all()
        
        if meal_plan:
            self.fields['meal_option'].queryset = MealOption.objects.filter(meal_plan=meal_plan)
        else:
            self.fields['meal_option'].queryset = MealOption.objects.none()
        
        if user:
            # Get the team of the current user
            user_team = models.Team.objects.filter(teammembership__member=user).first()
            if user_team:
                # Filter team_contact to only include volunteers related to the same team
                self.fields['team_contact'].queryset = models.Volunteer.objects.filter(teammembership__team=user_team)
                # Set the default value of team_contact to the current user
                self.fields['team_contact'].initial = user

class BulkMealForm(forms.ModelForm):
    class Meta:
        model = TeamMealPlan
        fields = ['meal_option', 'team_contact']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Safeguard against missing instance or meal_plan
        if self.instance and hasattr(self.instance, 'meal_plan') and self.instance.meal_plan:
            self.fields['meal_option'].queryset = MealOption.objects.filter(
                meal_plan=self.instance.meal_plan
            )
            self.fields['meal_option'].empty_label = "Vælg et måltid..."
        else:
            # Fallback: if no meal_plan is linked, don't show any options
            self.fields['meal_option'].queryset = MealOption.objects.none()
            self.fields['meal_option'].help_text = "Ingen måltidsplan fundet."

        # 2. Safeguard team_contact (Limit to the specific team)
        if self.instance and hasattr(self.instance, 'team') and self.instance.team:
            self.fields['team_contact'].queryset = models.Volunteer.objects.filter(
                teammembership__team=self.instance.team
            )

