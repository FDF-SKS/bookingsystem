import csv
import time
from collections import defaultdict
from datetime import date, timedelta
from typing import List

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.template.loader import render_to_string
from django.urls import path
from django.urls.resolvers import URLPattern
from django.utils.html import strip_tags
from django.utils.translation import ngettext

from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ManyToManyWidget
from django_tiptap_editor.admin.mixin import TipTapModelAdminMixin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.import_export.forms import ExportForm, ImportForm, SelectableFieldsExportForm
from unfold.decorators import action

from . import models
from .models import (
    Event,
    EventMembership,
    Key,
    Team,
    TeamEventMembership,
    TeamMembership,
    Tjanse,
    TjanseOwnership,
    TjanseSwapRequest,
    Volunteer,
    VolunteerAppointment,
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
        MAX_EMAILS = 50  # Safety cap for Gmail
        count = queryset.count()

        if count > MAX_EMAILS:
            self.message_user(
                request, 
                f"FEJL: Du har valgt {count} personer. Max grænsen er {MAX_EMAILS} for at undgå at blive blokeret af Gmail.", 
                level=messages.ERROR
            )
            return

        sent_count = 0
        last_volunteer = None

        try:
            for volunteer in queryset:
                subject = "Velkommen til Seniorkursus Slettens booking system"
                email_template = "organization/reset_password_guide_email.html"
                context = {'volunteer': volunteer, 'first_team': volunteer.teams.first()}
                message = render_to_string(email_template, context)

                # send_mail returns 1 on success
                success = send_mail(
                    subject, 
                    strip_tags(message), 
                    'slettenbooking@gmail.com', 
                    [volunteer.email], 
                    html_message=message
                )
                
                if success:
                    sent_count += 1
                    last_volunteer = volunteer
                    time.sleep(1) # 1 second pause between emails (Safe for Gmail)

            self.message_user(request, f"Succes: {sent_count} emails blev sendt.")

        except Exception as e:
            # If Google blocks us halfway, we tell the user exactly where we stopped
            self.message_user(
                request, 
                f"PROCES AFBRUDT: Kun {sent_count} blev sendt. Sidste succesfulde var {last_volunteer}. Fejl: {str(e)}", 
                level=messages.ERROR
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


@admin.register(VolunteerAppointment)
class VolunteerAppointmentAdmin(ModelAdmin):
    list_display = [
        "__str__",
        "requester",
        "get_requester_teams",
        "receiver",
        "get_receiver_teams",
        "start_date",
        "start_time",
        "status",
        "created",
    ]
    
    list_filter = [
        "status",
        "start_date",
        "requester__teams",
        "receiver__teams",
    ]
    
    search_fields = [
        "requester__first_name",
        "requester__last_name",
        "receiver__first_name",
        "receiver__last_name",
        "description",
    ]
    
    # Pre-select relational objects for fast database queries
    raw_id_fields = ["requester", "receiver"]
    
    # Group fields nicely in the detail form
    fieldsets = (
        ("Deltagere", {
            "fields": ("requester", "receiver")
        }),
        ("Tid og Sted", {
            "fields": (("start_date", "end_date"), ("start_time", "end_time"))
        }),
        ("Detaljer", {
            "fields": ("description", "status")
        }),
        ("Systeminfo", {
            "classes": ("collapse",),
            "fields": ("created", "last_updated"),
        }),
    )
    
    readonly_fields = ["created", "last_updated"]

    def get_queryset(self, request):
        """Optimize queries by prefetching related teams to avoid N+1 queries."""
        qs = super().get_queryset(request)
        return qs.select_related("requester", "receiver").prefetch_related(
            "requester__teams", 
            "receiver__teams"
        )

    @admin.display(description="Afsender Team")
    def get_requester_teams(self, obj):
        """Returns all teams for the requester as a comma-separated string."""
        teams = obj.requester.teams.all()
        if teams:
            return ", ".join([getattr(t, "name", str(t)) for t in teams])
        return "-"

    @admin.display(description="Modtager Team")
    def get_receiver_teams(self, obj):
        """Returns all teams for the receiver as a comma-separated string."""
        teams = obj.receiver.teams.all()
        if teams:
            return ", ".join([getattr(t, "name", str(t)) for t in teams])
        return "-"


@admin.register(Tjanse)
class TjanseAdmin(TipTapModelAdminMixin, ModelAdmin):
    tiptap_fields = ["description"]
    list_display = ["title", "created", "last_updated"]
    search_fields = ["title", "description"]
    readonly_fields = ["created", "last_updated"]


@admin.register(TjanseOwnership)
class TjanseOwnershipAdmin(SimpleHistoryAdmin, ModelAdmin):
    change_list_template = "admin/organization/tjanseownership/change_list.html"
    change_form_template = "admin/organization/tjanseownership/change_form.html"
    list_display = ["tjanse", "event", "team", "status", "due_date", "completed_at"]
    list_display_links = ["tjanse"]
    list_editable = ["team", "status", "due_date"]
    list_filter = ["status", "event", "team"]
    search_fields = ["tjanse__title", "team__name"]
    fields = [
        "tjanse",
        "event",
        "team",
        "due_date",
        "status",
        "completed_at",
        "assigned_at",
        "created",
        "last_updated",
    ]
    readonly_fields = ["assigned_at", "created", "last_updated"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("tjanse", "event", "team")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "overview/",
                self.admin_site.admin_view(self.overview_view),
                name="organization_tjanseownership_overview",
            ),
            path(
                "status-overview/",
                self.admin_site.admin_view(self.status_overview_view),
                name="organization_tjanseownership_status_overview",
            ),
        ]
        return custom_urls + urls

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            ownership = self.get_object(request, object_id)
            if ownership:
                extra_context["ownership_history"] = ownership.history.select_related(
                    "history_user", "team", "tjanse"
                ).all()
        return super().changeform_view(request, object_id, form_url, extra_context)

    def overview_view(self, request):
        events = Event.objects.order_by("-start_date", "name")
        event_id = request.POST.get("event") or request.GET.get("event")
        selected_event = events.filter(pk=event_id).first() if event_id else events.first()
        default_start = selected_event.start_date if selected_event else date.today()

        try:
            week_start = date.fromisoformat(
                request.POST.get("week_start") or request.GET.get("week_start") or default_start.isoformat()
            )
        except ValueError:
            week_start = default_start

        if selected_event:
            week_start = max(selected_event.start_date, min(week_start, selected_event.end_date))

        days = [
            week_start + timedelta(days=index)
            for index in range((selected_event.end_date - week_start).days + 1)
        ] if selected_event else []

        if request.method == "POST" and selected_event:
            self._save_overview_grid(request, selected_event, days)
            return redirect(
                f"{request.path}?event={selected_event.pk}&week_start={week_start.isoformat()}"
            )

        tjanser = Tjanse.objects.order_by("title")
        ownerships = self.get_queryset(request).filter(
            event=selected_event,
            due_date__gte=days[0],
            due_date__lte=days[-1],
        ) if selected_event else TjanseOwnership.objects.none()
        ownership_map = defaultdict(list)
        for ownership in ownerships:
            ownership_map[(ownership.tjanse_id, ownership.due_date)].append(ownership)
        teams = list(Team.objects.order_by("name"))
        event_team_ids = {team.pk for team in teams}
        rows = [
            {
                "tjanse": tjanse,
                "cells": [
                    {
                        "day": day,
                        "ownerships": cell_ownerships,
                        "team_ids": {ownership.team_id for ownership in cell_ownerships},
                        "all_teams": bool(event_team_ids) and {
                            ownership.team_id for ownership in cell_ownerships
                        } == event_team_ids,
                        "assignment_label": (
                            "Alle teams"
                            if event_team_ids and {
                                ownership.team_id for ownership in cell_ownerships
                            } == event_team_ids
                            else ", ".join(
                                ownership.team.short_name or ownership.team.name
                                for ownership in cell_ownerships
                            )
                        ),
                    }
                    for day in days
                    for cell_ownerships in [ownership_map.get((tjanse.pk, day), [])]
                ],
            }
            for tjanse in tjanser
        ]
        team_assignment_counts = Team.objects.annotate(
            tjanse_assignment_count=Count(
                "tjanse_ownerships",
                filter=Q(tjanse_ownerships__event=selected_event),
            )
        ).order_by("name") if selected_event else Team.objects.none()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Tjanseoversigt",
            "events": events,
            "selected_event": selected_event,
            "days": days,
            "rows": rows,
            "team_assignment_counts": team_assignment_counts,
            "teams": teams,
            "week_start": week_start.isoformat(),
        }
        return render(request, "admin/organization/tjanseownership/overview.html", context)

    def status_overview_view(self, request):
        events = Event.objects.order_by("-start_date", "name")
        event_id = request.GET.get("event")
        selected_event = events.filter(pk=event_id).first() if event_id else events.first()
        if selected_event:
            days = [
                selected_event.start_date + timedelta(days=index)
                for index in range((selected_event.end_date - selected_event.start_date).days + 1)
            ]
            ownerships = self.get_queryset(request).filter(
                event=selected_event,
                due_date__gte=selected_event.start_date,
                due_date__lte=selected_event.end_date,
            )
        else:
            days = []
            ownerships = TjanseOwnership.objects.none()

        ownership_map = defaultdict(list)
        for ownership in ownerships:
            ownership_map[(ownership.tjanse_id, ownership.due_date)].append(ownership)

        rows = [
            {
                "tjanse": tjanse,
                "cells": [
                    {"day": day, "ownerships": ownership_map.get((tjanse.pk, day), [])}
                    for day in days
                ],
            }
            for tjanse in Tjanse.objects.order_by("title")
        ]
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Tjanse-statusoversigt",
            "events": events,
            "selected_event": selected_event,
            "days": days,
            "rows": rows,
        }
        return render(
            request,
            "admin/organization/tjanseownership/status_overview.html",
            context,
        )

    def _save_overview_grid(self, request, event, days):
        event_team_ids = set(Team.objects.values_list("pk", flat=True))
        for tjanse in Tjanse.objects.all():
            for day in days:
                field_key = f"{tjanse.pk}_{day.isoformat()}"
                submitted_team_ids = request.POST.getlist(f"team_{field_key}")
                if "all" in submitted_team_ids:
                    selected_team_ids = event_team_ids
                else:
                    selected_team_ids = set()
                    for team_id in submitted_team_ids:
                        try:
                            parsed_team_id = int(team_id)
                        except (TypeError, ValueError):
                            continue
                        if parsed_team_id in event_team_ids:
                            selected_team_ids.add(parsed_team_id)

                ownership_qs = TjanseOwnership.objects.filter(
                    tjanse=tjanse,
                    event=event,
                    due_date=day,
                )
                existing_by_team = {}
                for ownership in ownership_qs.order_by("pk"):
                    if ownership.team_id in existing_by_team:
                        ownership.delete()
                    else:
                        existing_by_team[ownership.team_id] = ownership

                for team_id, ownership in existing_by_team.items():
                    if team_id not in selected_team_ids:
                        ownership.delete()

                for team_id in selected_team_ids - existing_by_team.keys():
                    TjanseOwnership.objects.create(
                        tjanse=tjanse,
                        event=event,
                        due_date=day,
                        team_id=team_id,
                    )


@admin.register(TjanseSwapRequest)
class TjanseSwapRequestAdmin(ModelAdmin):
    list_display = ["task_ownership", "requesting_team", "receiving_team", "status", "created"]
    list_filter = ["status"]
    search_fields = ["task_ownership__tjanse__title", "requesting_team__name", "receiving_team__name"]
    readonly_fields = ["created", "last_updated", "resolved_by"]
    actions = ["accept_swap_action", "reject_swap_action"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("task_ownership__tjanse", "requesting_team", "receiving_team")

    @action(description="Godkend valgte bytter")
    def accept_swap_action(self, request, queryset):
        from .signals import send_tjanse_assigned_email
        count = 0
        for swap in queryset.filter(status="pending"):
            swap.accept(resolved_by=request.user)
            send_tjanse_assigned_email(swap.task_ownership)
            count += 1
        self.message_user(request, f"{count} tjanse-bytter blev godkendt.", messages.SUCCESS)

    @action(description="Afvis valgte bytter")
    def reject_swap_action(self, request, queryset):
        count = 0
        for swap in queryset.filter(status="pending"):
            swap.reject(resolved_by=request.user)
            count += 1
        self.message_user(request, f"{count} tjanse-bytter blev afvist.", messages.SUCCESS)

