from collections import defaultdict
from datetime import date, timedelta

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.timezone import localtime, now
from django_tiptap_editor.admin.mixin import TipTapModelAdminMixin
from django_tiptap_editor.widgets.tiptap_widget import TipTapWidget
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.import_export.forms import ExportForm, ImportForm
from unfold.decorators import action

from Butikken.models import MealPlan, TeamMealPlan
from emailing.services import send_email

from .models import (
    Event,
    EventMembership,
    Key,
    ProgramBlock,
    SlutrengoringAssignment,
    Team,
    TeamEventMembership,
    TeamMembership,
    Tjanse,
    TjanseOwnership,
    TjanseSwapRequest,
    Volunteer,
    VolunteerAppointment,
)
from .slutrengoring_services import (
    assign_highest_priority_to_teams,
    create_assignments_for_event,
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

class ProgramBlockInlineForm(forms.ModelForm):
    class Meta:
        model = ProgramBlock
        fields = ['title', 'category', 'day', 'start_time', 'end_time', 'content', 'responsible']
        widgets = {
            'content': TipTapWidget(
                storage='json',
                config={
                    **dict(getattr(settings, 'TIPTAP_DEFAULT_CONFIG', {})),
                    'height': '180px',
                },
            ),
        }


class ProgramBlockInline(TabularInline):
    """The shared framework blocks, edited directly from the event."""

    model = ProgramBlock
    form = ProgramBlockInlineForm
    fk_name = 'event'
    extra = 0
    fields = ['title', 'category', 'day', 'start_time', 'end_time', 'content', 'responsible']
    autocomplete_fields = ['responsible']
    show_change_link = True
    verbose_name = 'Rammeprogram-blok'
    verbose_name_plural = 'Rammeprogram (fælles blokke)'

    def get_queryset(self, request):
        return super().get_queryset(request).filter(team__isnull=True)

# --- Admin Classes ---


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
    readonly_fields = ["id", "last_updated", "created", "program_link"]
    inlines = [ProgramBlockInline]

    @admin.display(description='Rammeprogram')
    def program_link(self, obj):
        if not obj.pk:
            return 'Gem eventet først'
        url = reverse('organization_Event_program', args=(obj.pk,))
        history_url = reverse('organization_Event_program_history', args=(obj.pk,))
        export_url = reverse('organization_Event_program_export', args=(obj.pk,))
        return format_html(
            '<a href="{}">Åbn rammeprogram</a> &middot; '
            '<a href="{}?team=base">Eksportér</a> &middot; '
            '<a href="{}">Historik</a>',
            url,
            export_url,
            history_url,
        )


@admin.register(ProgramBlock)
class ProgramBlockAdmin(TipTapModelAdminMixin, SimpleHistoryAdmin, ModelAdmin):
    tiptap_fields = ['content']
    list_display = [
        'title', 'event', 'team', 'category', 'day',
        'start_time', 'end_time', 'last_updated',
    ]
    list_filter = ['event', 'team', 'category', 'day']
    search_fields = ['title', 'event__name', 'team__name']
    autocomplete_fields = ['responsible']
    readonly_fields = ['id', 'last_updated', 'created']
    ordering = ['event', 'day', 'start_time']

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
        subject = "Velkommen til Seniorkursus Slettens booking system"
        email_template = "organization/reset_password_guide_email.html"
        queued_count = 0

        for volunteer in queryset:
            if not volunteer.email:
                continue
            context = {'volunteer': volunteer, 'first_team': volunteer.teams.first()}
            queued_count += len(send_email(subject, email_template, context, [volunteer.email]))

        self.message_user(
            request,
            f"{queued_count} emails er sat i kø. Status kan følges under Emails > Email-log.",
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
        "shared_with_team",
        "start_date",
        "start_time",
        "status",
        "resolved_by",
        "created",
    ]

    list_filter = [
        "status",
        "shared_with_team",
        "start_date",
        "requester__teams",
        "receiver__teams",
        "receiver_team",
    ]

    search_fields = [
        "requester__first_name",
        "requester__last_name",
        "receiver__first_name",
        "receiver__last_name",
        "receiver_team__name",
        "resolved_by__first_name",
        "resolved_by__last_name",
        "description",
    ]

    # Pre-select relational objects for fast database queries
    raw_id_fields = ["requester", "receiver", "resolved_by"]

    # Group fields nicely in the detail form
    fieldsets = (
        ("Deltagere", {
            "fields": (
                "requester",
                ("receiver", "receiver_team"),
                "shared_with_team",
            ),
            "description": (
                "Vælg enten en person eller et team som modtager. "
                "Delt betyder, at afsenderens team også kan se aftalen."
            ),
        }),
        ("Tid og Sted", {
            "fields": (("start_date", "end_date"), ("start_time", "end_time"))
        }),
        ("Detaljer", {
            "fields": ("description", "status", "resolved_by")
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
        return qs.select_related(
            "requester", "receiver", "receiver_team", "resolved_by"
        ).prefetch_related(
            "requester__teams",
            "receiver__teams",
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
        """Return the receiving team, or the receiver's teams."""
        if obj.receiver_team_id:
            return obj.receiver_team.name
        if not obj.receiver_id:
            return "-"
        teams = obj.receiver.teams.all()
        if teams:
            return ", ".join([getattr(t, "name", str(t)) for t in teams])
        return "-"


@admin.register(Tjanse)
class TjanseAdmin(TipTapModelAdminMixin, ModelAdmin):
    tiptap_fields = ["description"]
    list_display = ["title", "kind", "priority", "area", "created", "last_updated"]
    list_filter = ["kind", "priority"]
    search_fields = ["title", "description", "area"]
    ordering = ["kind", "order", "title"]
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
        return qs.filter(tjanse__kind="regular").select_related("tjanse", "event", "team")

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
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        if request.method == "POST" and not self.has_change_permission(request):
            raise PermissionDenied

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

        tjanser = Tjanse.objects.filter(kind="regular").order_by("title")
        ownerships = self.get_queryset(request).filter(
            event=selected_event,
            due_date__gte=days[0],
            due_date__lte=days[-1],
        ) if selected_event and days else TjanseOwnership.objects.none()
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
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

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
            for tjanse in Tjanse.objects.filter(kind="regular").order_by("title")
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
        for tjanse in Tjanse.objects.filter(kind="regular"):
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


class SlutrengoringAssignmentResource(resources.ModelResource):
    tjanse = fields.Field(
        column_name="tjanse",
        attribute="tjanse",
        widget=ForeignKeyWidget(Tjanse, "title"),
    )
    event = fields.Field(
        column_name="event",
        attribute="event",
        widget=ForeignKeyWidget(Event, "name"),
    )
    team = fields.Field(
        column_name="team",
        attribute="team",
        widget=ForeignKeyWidget(Team, "name"),
    )

    class Meta:
        model = SlutrengoringAssignment
        fields = ("id", "tjanse", "event", "team", "status")
        import_id_fields = ("tjanse", "event")


SLUTRENGOERING_PRIORITY_ORDER = Case(
    When(tjanse__priority='required', then=Value(0)),
    When(tjanse__priority='high', then=Value(1)),
    When(tjanse__priority='medium', then=Value(2)),
    When(tjanse__priority='low', then=Value(3)),
    default=Value(99),
    output_field=IntegerField(),
)


@admin.register(SlutrengoringAssignment)
class SlutrengoringAssignmentAdmin(SimpleHistoryAdmin, ModelAdmin, ImportExportModelAdmin):
    resource_classes = [SlutrengoringAssignmentResource]
    import_form_class = ImportForm
    export_form_class = ExportForm
    change_list_template = "admin/organization/slutrengoringassignment/change_list.html"
    list_display = [
        "tjanse",
        "event",
        "priority_display",
        "team",
        "status",
        "attempt_count",
        "assigned_at",
        "started_at",
        "completed_at",
    ]
    list_display_links = ["tjanse"]
    list_editable = ["team", "status"]
    list_filter = ["status", "event", "team", "tjanse__priority"]
    search_fields = ["tjanse__title", "tjanse__area", "team__name"]
    list_select_related = ("tjanse", "event", "team")
    readonly_fields = [
        "assigned_at",
        "started_at",
        "completed_at",
        "not_finished_at",
        "attempt_count",
        "last_team",
        "created",
        "last_updated",
    ]
    fields = [
        "tjanse",
        "event",
        "team",
        "status",
        "assigned_by",
        "assigned_at",
        "started_at",
        "completed_at",
        "completed_by",
        "not_finished_at",
        "not_finished_reason",
        "attempt_count",
        "last_team",
        "created",
        "last_updated",
    ]
    actions = ["return_to_pool_action", "reopen_action", "mark_done_action"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            tjanse__kind="slutrengoring"
        ).select_related("tjanse", "event", "team", "last_team")

    def save_model(self, request, obj, form, change):
        previous_team_id = None
        if change and obj.pk:
            previous_team_id = (
                SlutrengoringAssignment.objects
                .filter(pk=obj.pk)
                .values_list("team_id", flat=True)
                .first()
            )

        # Keep team/status coherent when staff use the editable changelist.
        if obj.team_id and obj.status in ("available", "not_finished"):
            obj.status = "assigned"
        elif not obj.team_id and obj.status in SlutrengoringAssignment.ACTIVE_STATUSES:
            obj.status = "available"

        if obj.team_id and (not change or previous_team_id != obj.team_id):
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(ordering="tjanse__priority", description="Prioritet")
    def priority_display(self, obj):
        return obj.tjanse.get_priority_display()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "board/",
                self.admin_site.admin_view(self.board_view),
                name="organization_slutrengoringassignment_board",
            ),
            path(
                "tools/",
                self.admin_site.admin_view(self.tools_view),
                name="organization_slutrengoringassignment_tools",
            ),
        ]
        return custom_urls + urls

    @action(description="Returnér valgte opgaver til puljen")
    def return_to_pool_action(self, request, queryset):
        count = 0
        for assignment in queryset.filter(status__in=SlutrengoringAssignment.ACTIVE_STATUSES):
            assignment.last_team = assignment.team
            assignment.team = None
            assignment.status = "not_finished"
            assignment.assigned_at = None
            assignment.assigned_by = None
            assignment.started_at = None
            assignment.not_finished_at = now()
            assignment.not_finished_reason = "Returneret af administrator."
            assignment.attempt_count += 1
            assignment.save()
            count += 1
        self.message_user(request, f"{count} opgaver blev returneret til puljen.", messages.SUCCESS)

    @action(description="Genåbn valgte opgaver")
    def reopen_action(self, request, queryset):
        count = queryset.update(
            status="available",
            team=None,
            assigned_at=None,
            assigned_by=None,
            started_at=None,
            completed_at=None,
            completed_by=None,
        )
        self.message_user(request, f"{count} opgaver blev genåbnet.", messages.SUCCESS)

    @action(description="Markér valgte opgaver som udført")
    def mark_done_action(self, request, queryset):
        count = 0
        for assignment in queryset.exclude(status="done"):
            assignment.status = "done"
            assignment.completed_at = now()
            assignment.completed_by = request.user
            assignment.save()
            count += 1
        self.message_user(request, f"{count} opgaver blev markeret som udført.", messages.SUCCESS)

    def tools_view(self, request):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        if request.method == "POST" and not self.has_change_permission(request):
            raise PermissionDenied

        events = Event.objects.order_by("-end_date", "name")
        event_id = request.POST.get("event") or request.GET.get("event")
        selected_event = events.filter(pk=event_id).first() if event_id else events.first()

        if request.method == "POST" and selected_event:
            action = request.POST.get("action")
            if action == "create":
                created = create_assignments_for_event(selected_event)
                self.message_user(
                    request,
                    f"Oprettede {created} nye slutrengøringstildelinger til {selected_event.name}.",
                    messages.SUCCESS,
                )
            elif action == "assign":
                assigned, skipped = assign_highest_priority_to_teams(
                    selected_event, actor=request.user
                )
                self.message_user(
                    request,
                    (
                        f"Tildelte {len(assigned)} opgaver til teams. "
                        f"{len(skipped)} teams blev sprunget over "
                        "(allerede aktiv opgave eller ingen ledige opgaver tilbage)."
                    ),
                    messages.SUCCESS if assigned else messages.WARNING,
                )
            return redirect(f"{request.path}?event={selected_event.pk}")

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Opret og tildel slutrengøring",
            "events": events,
            "selected_event": selected_event,
            "selected_event_id": selected_event.pk if selected_event else "",
        }
        if selected_event:
            event_assignments = SlutrengoringAssignment.objects.filter(event=selected_event)
            active_team_ids = (
                event_assignments
                .filter(status__in=SlutrengoringAssignment.ACTIVE_STATUSES)
                .values_list("team_id", flat=True)
                .distinct()
            )
            context.update({
                "assignment_count": event_assignments.count(),
                "available_count": event_assignments.filter(
                    team__isnull=True,
                    status__in=SlutrengoringAssignment.CLAIMABLE_STATUSES,
                ).count(),
                "team_count": Team.objects.count(),
                "busy_team_count": len(set(active_team_ids)),
            })
        return render(
            request,
            "admin/organization/slutrengoringassignment/tools.html",
            context,
        )

    def board_view(self, request):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied

        events = Event.objects.order_by("-end_date", "name")
        event_id = request.GET.get("event")
        selected_event = events.filter(pk=event_id).first() if event_id else events.first()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Slutrengøringsstatus",
            "events": events,
            "selected_event": selected_event,
            "auto_refresh": request.GET.get("auto") != "0",
        }

        if not selected_event:
            return render(
                request,
                "admin/organization/slutrengoringassignment/board.html",
                context,
            )

        assignments = (
            SlutrengoringAssignment.objects
            .filter(event=selected_event)
            .select_related("tjanse", "team", "last_team")
        )
        done_assignments = list(
            assignments.filter(status="done", completed_at__isnull=False).order_by("completed_at")
        )
        active_assignments = list(
            assignments.filter(status__in=SlutrengoringAssignment.ACTIVE_STATUSES)
            .select_related("team", "tjanse")
            .order_by("team__name", "tjanse__priority", "tjanse__title")
        )
        missing_assignments = list(
            assignments.filter(
                team__isnull=True,
                status__in=SlutrengoringAssignment.CLAIMABLE_STATUSES,
            )
            .annotate(priority_rank=SLUTRENGOERING_PRIORITY_ORDER)
            .order_by("priority_rank", "tjanse__order", "tjanse__title")
        )

        active_by_team = defaultdict(list)
        for assignment in active_assignments:
            active_by_team[assignment.team_id].append(assignment)

        team_rows = [
            {"team": team, "assignments": active_by_team.get(team.pk, [])}
            for team in Team.objects.order_by("name")
        ]

        priority_rows = []
        for value, label in Tjanse.PRIORITY_CHOICES:
            priority_qs = assignments.filter(tjanse__priority=value)
            priority_rows.append({
                "value": value,
                "label": label,
                "total": priority_qs.count(),
                "done": priority_qs.filter(status="done").count(),
                "missing": priority_qs.filter(
                    team__isnull=True,
                    status__in=SlutrengoringAssignment.CLAIMABLE_STATUSES,
                ).count(),
            })

        bucket_counts = defaultdict(int)
        for assignment in done_assignments:
            completed = localtime(assignment.completed_at)
            bucket = completed.replace(
                minute=(completed.minute // 15) * 15,
                second=0,
                microsecond=0,
            )
            bucket_counts[bucket] += 1
        max_bucket = max(bucket_counts.values(), default=1)
        completion_buckets = [
            {
                "label": bucket.strftime("%H:%M"),
                "count": count,
                "width": round(count / max_bucket * 100),
            }
            for bucket, count in sorted(bucket_counts.items())
        ]

        total = assignments.count()
        done = len(done_assignments)
        context.update({
            "assignments": assignments,
            "total": total,
            "done_count": done,
            "active_count": len(active_assignments),
            "available_count": assignments.filter(
                team__isnull=True,
                status__in=SlutrengoringAssignment.CLAIMABLE_STATUSES,
            ).count(),
            "not_finished_count": assignments.filter(status="not_finished").count(),
            "required_missing_count": assignments.filter(
                tjanse__priority="required",
            ).exclude(status="done").count(),
            "progress_percent": round(done / total * 100) if total else 0,
            "missing_assignments": missing_assignments,
            "active_assignments": active_assignments,
            "team_rows": team_rows,
            "priority_rows": priority_rows,
            "completion_buckets": completion_buckets,
            "recent_done": done_assignments[-10:][::-1],
            "active_team_count": len(active_by_team),
        })
        return render(
            request,
            "admin/organization/slutrengoringassignment/board.html",
            context,
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

