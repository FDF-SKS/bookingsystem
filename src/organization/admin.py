import csv
from datetime import date
from typing import List

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import path
from django.urls.resolvers import URLPattern
from django.utils.html import strip_tags
from django.utils.translation import ngettext

from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ManyToManyWidget
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.import_export.forms import ExportForm, ImportForm, SelectableFieldsExportForm
from unfold.decorators import action

from . import models
from .email_service import queue_bulk_emails
from .tasks import send_email_logs
from .models import (
    EmailLog,
    Event,
    EventMembership,
    Key,
    Team,
    TeamEventMembership,
    TeamMembership,
    Volunteer,
)

# 1. Widget specifically for creating Teams on the fly
class CreateTeamIfNotFoundWidget(ManyToManyWidget):
    def clean(self, value, row=None, **kwargs):
        if not value:
            return self.model.objects.none()
        
        names = [n.strip() for n in str(value).split(",") if n.strip()]
        ids = []
        
        for name in names:
            # We only create if it's a Team model
            obj, created = self.model.objects.get_or_create(
                **{self.field: name}, 
                defaults={'is_active': True}
            )
            ids.append(obj.pk)
            
        return self.model.objects.filter(pk__in=ids)
class AppendOrCreateWidget(ManyToManyWidget):
    def clean(self, value, row=None, **kwargs):
        if not value:
            return self.model.objects.none()
        
        names = [n.strip() for n in str(value).split(",") if n.strip()]
        incoming_ids = []
        
        for name in names:
            if self.model == Team:
                # Create Team with short_name = name if it doesn't exist
                obj, created = self.model.objects.get_or_create(
                    name=name,
                    defaults={'short_name': name[:30]} 
                )
            elif self.model == Event:
                # Create Event with dummy dates to satisfy model constraints
                today = date.today()
                obj, created = self.model.objects.get_or_create(
                    name=name,
                    defaults={
                        'start_date': today,
                        'end_date': today,
                        'deadline_sjak': today,
                        'deadline_teknik': today,
                        'deadline_mad': today,
                        'deadline_aktivitetsteam': today,
                        'deadline_foto': today,
                        'deadline_lokaler': today,
                        'deadline_sos': today,
                    }
                )
            else:
                obj, created = self.model.objects.get_or_create(**{self.field: name})
            
            incoming_ids.append(obj.pk)
        
        # APPEND LOGIC: Fetch current memberships from the Volunteer instance
        username = row.get('username')
        existing_ids = []
        if username:
            try:
                volunteer = Volunteer.objects.get(username=username)
                # Look up the attribute name we stored in the resource init
                attr_name = getattr(self, 'volunteer_attr_name', None)
                if attr_name:
                    existing_ids = list(getattr(volunteer, attr_name).values_list('pk', flat=True))
            except Volunteer.DoesNotExist:
                pass
        
        final_ids = set(incoming_ids + existing_ids)
        return self.model.objects.filter(pk__in=final_ids)
    

class VolunteerResource(resources.ModelResource):
    events = fields.Field(
        column_name='events',
        attribute='events',
        widget=AppendOrCreateWidget(Event, field='name')
    )
    
    teams = fields.Field(
        column_name='teams',
        attribute='teams',
        widget=AppendOrCreateWidget(Team, field='name')
    )

    def __init__(self, *args, **kwargs):
        # Pass all arguments (like 'form') up to the base Resource class
        super().__init__(*args, **kwargs)
        
        # Now set your custom widget properties
        if 'events' in self.fields:
            self.fields['events'].widget.volunteer_attr_name = 'events'
        if 'teams' in self.fields:
            self.fields['teams'].widget.volunteer_attr_name = 'teams'

    class Meta:
        model = Volunteer
        import_id_fields = ('username',)
        fields = (
            'first_name', 'last_name', 'username', 'email', 
            'phone', 'is_active', 'events', 'teams'
        )
        skip_unchanged = True    


class TeamEventMembershipInline(TabularInline):
    model = TeamEventMembership
    extra = 1

class EventMembershipInline(TabularInline):
    model = EventMembership
    extra = 1

class TeamMembershipInline(TabularInline):
    model = TeamMembership
    extra = 1

# --- Admin Classes ---


from Butikken.models import MealPlan, TeamMealPlan

@admin.register(Team)
class TeamAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ["name", "short_name", "last_updated", "created"]
    readonly_fields = ["id", "last_updated", "created"]
    
    # 1. Reference the method name as a string
    actions = ["create_team_meal_plans_action"]

    # 2. Define the action inside the class
    @action(description="Create TeamMealPlan for each MealPlan")
    def create_team_meal_plans_action(self, request, queryset):
        meal_plans = MealPlan.objects.all()
        created_count = 0
        for team in queryset:
            for meal_plan in meal_plans:
                # get_or_create is cleaner here than a manual check
                obj, created = TeamMealPlan.objects.get_or_create(
                    team=team, 
                    meal_plan=meal_plan
                )
                if created:
                    created_count += 1
        
        self.message_user(request, f"{created_count} TeamMealPlan objects created successfully.")


@admin.register(TeamMembership)
class TeamMembershipAdmin(ModelAdmin):
    list_display = ["member", "team", "role", "last_updated", "created"]
    readonly_fields = ["last_updated", "created"]

@admin.register(Event)
class EventAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ["name", "start_date", "end_date", "is_active", "last_updated", "created"]
    readonly_fields = ["id", "last_updated", "created"]

@admin.register(EventMembership)
class EventMembershipAdmin(ModelAdmin):
    list_display = ["volunteer", "event", "last_updated", "created"]
    readonly_fields = ["last_updated", "created"]

@admin.register(TeamEventMembership)
class TeamEventMembershipAdmin(ModelAdmin):
    list_display = ["team", "last_updated", "created"]
    readonly_fields = ["last_updated", "created"]

@admin.register(Key)
class KeyAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ["number", "name", "current_user", "description"]
    readonly_fields = ["last_updated"]

# --- Volunteer Admin (Unfold + Import/Export + Simple History) ---
@admin.register(Volunteer)
class VolunteerAdmin(SimpleHistoryAdmin, ModelAdmin, ImportExportModelAdmin):
    # Resource for django-import-export
    resource_classes = [VolunteerResource]
    
    # Unfold specific Import/Export forms
    import_form_class = ImportForm
    export_form_class = ExportForm
    
    inlines = [EventMembershipInline, TeamMembershipInline]
    
    list_display = [
        "first_name",
        "last_name",
        "username",
        "email",
        "display_events",
        "display_teams",
        "is_active",
        "created",
    ]
    
    search_fields = ['first_name', 'last_name', 'email', 'username']
    list_filter = ['is_active',
                    'events',
                    'teams',
                    'last_updated']
    readonly_fields = ["created", "last_updated"]
    ordering = ['first_name', 'last_name', 'username', 'events', 'teams']

    actions = [
        "send_email_action",
        "deactivate_volunteers",
        "activate_volunteers",
        "create_event_membership",
        "assign_to_aktivitetsteam_group"
    ]

    def display_events(self, obj):
        return ", ".join([event.name for event in obj.events.all()])
    display_events.short_description = "Events"

    def display_teams(self, obj):
        return ", ".join([team.name for team in obj.teams.all()])
    display_teams.short_description = "Teams"

    # --- Unfold Decorated Actions ---

    @action(description="Assign to AktivitetsTeamBookingTildeling group")
    def assign_to_aktivitetsteam_group(self, request, queryset):
        group, _ = Group.objects.get_or_create(name="AktivitetsTeamBookingTildeling")
        for volunteer in queryset:
            volunteer.groups.add(group)
        self.message_user(request, "Group assignment complete.")

    



    @admin.action(description="Send 'Hjælp til at komme igang' email")
    def send_email_action(self, request, queryset):
        messages_payload = []
        for volunteer in queryset:
            subject = "Velkommen til Seniorkursus Slettens booking system"
            email_template = "organization/reset_password_guide_email.html"
            context = {'volunteer': volunteer, 'first_team': volunteer.teams.first()}
            message = render_to_string(email_template, context)
            messages_payload.append(
                {
                    "recipient": volunteer.email,
                    "subject": subject,
                    "body": strip_tags(message),
                    "html_body": message,
                    "from_email": settings.DEFAULT_FROM_EMAIL,
                }
            )

        queued_count = queue_bulk_emails(messages_payload)
        self.message_user(
            request,
            f"Succes: {queued_count} emails blev sat i kø til baggrundsafsendelse.",
            messages.SUCCESS,
        )

    @action(description="Deactivate selected volunteers")
    def deactivate_volunteers(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Volunteers deactivated.", messages.SUCCESS)

    @action(description="Activate selected volunteers")
    def activate_volunteers(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Volunteers activated.", messages.SUCCESS)

    @action(description="Add selected to the next upcoming event")
    def create_event_membership(self, request, queryset):
        next_event = Event.objects.filter(start_date__gte=date.today()).order_by('start_date').first()
        if next_event:
            for volunteer in queryset:
                EventMembership.objects.get_or_create(volunteer=volunteer, event=next_event)
            self.message_user(request, f'Added to event: {next_event}', messages.SUCCESS)
        else:
            self.message_user(request, "No upcoming events found.", messages.ERROR)


@admin.register(EmailLog)
class EmailLogAdmin(ModelAdmin):
    list_display = ["recipient", "subject", "status", "attempts", "sent_at", "created"]
    search_fields = ["recipient", "subject", "error_message"]
    list_filter = ["status", "sent_at", "created"]
    readonly_fields = ["recipient", "subject", "body", "html_body", "from_email", "attachments", "attempts", "error_message", "sent_at", "created", "last_updated"]
    actions = ["resend_failed_emails"]

    @action(description="Genafsend fejlede mails")
    def resend_failed_emails(self, request, queryset):
        failed_logs = queryset.filter(status=EmailLog.STATUS_FAILED)
        updated = failed_logs.update(status=EmailLog.STATUS_PENDING, error_message="", sent_at=None, attempts=0)
        send_email_logs.delay(list(failed_logs.values_list("id", flat=True)))
        self.message_user(request, f"{updated} fejlede mails sat i kø til genafsendelse.", messages.SUCCESS)
