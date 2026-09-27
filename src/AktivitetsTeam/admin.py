"""
AktivitetsTeam Django Admin Configuration.

Udnytter Django Unfold package til avancerede admin features:
- Fuld bredde lister med horizontale filtreringer
- Automatisk billede forhåndsvisninger
- Farvede status badges
- Datohierarkier for intuitiv navigation
- Import/Export med django-import-export
"""

import csv
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib.admin import SimpleListFilter

from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action, display
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm

from organization.models import Volunteer
from . import models
from utils.ical_utils import export_selected_to_ical, send_ical_via_email


# ============================================================================
# IMPORT/EXPORT RESSOURCER
# ============================================================================

class AktivitetsTeamItemResource(resources.ModelResource):
    """Import/Export ressource for AktivitetsTeamItem."""
    
    class Meta:
        model = models.AktivitetsTeamItem
        fields = (
            "name", "description", "short_description", "youtube_link", 
            "description_aktiverede", "description_eksempel", "description_flow"
        )
        import_id_fields = ()
        export_order = fields

    def before_import_row(self, row, **kwargs):
        """Rens op i ledende/efterfølgende mellemrum."""
        for field in self.get_export_fields():
            column_name = field.column_name
            if column_name in row and row[column_name]:
                row[column_name] = str(row[column_name]).strip()


class AktivitetsTeamBookingResource(resources.ModelResource):
    """Import/Export ressource for AktivitetsTeamBooking."""
    
    class Meta:
        model = models.AktivitetsTeamBooking
        fields = (
            "item__name", "team__name", "team_contact__first_name", 
            "status", "start_date", "start_time", "end_date", "end_time", 
            "location", "remarks", "remarks_internal"
        )
        export_order = fields


# ============================================================================
# BASE ADMIN
# ============================================================================

class AktivitetsTeamBaseAdmin(ModelAdmin, ImportExportModelAdmin):
    """Basiskonfiguration for alle AktivitetsTeam admin klasser."""
    
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    actions = ["approve_selected", "reject_selected", "export_selected_raw"]

    @admin.action(description="Godkend valgte")
    def approve_selected(self, request, queryset):
        """Godkend valgte bookinger."""
        updated = queryset.update(status="Approved")
        self.message_user(request, f"{updated} bookinger er nu godkendt.", messages.SUCCESS)

    @admin.action(description="Afvis valgte")
    def reject_selected(self, request, queryset):
        """Afvis valgte bookinger."""
        updated = queryset.update(status="Rejected")
        self.message_user(request, f"{updated} bookinger er blevet afvist.", messages.WARNING)

    @admin.action(description="Eksporter valgte (CSV)")
    def export_selected_raw(self, request, queryset):
        """Eksporter valgte elementer som CSV."""
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename={meta.model_name}_export.csv'
        
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])
        
        return response


# ============================================================================
# ADMIN FORMULARER
# ============================================================================

class AktivitetsTeamItemAdminForm(forms.ModelForm):
    """Formular for AktivitetsTeamItem."""
    
    class Meta:
        model = models.AktivitetsTeamItem
        fields = [
            "name", "category", "description", "short_description",
            "is_active", "youtube_link", "description_flow",
            "description_eksempel", "description_aktiverede",
            "location", "image",
        ]


class AktivitetsTeamBookingAdminForm(forms.ModelForm):
    """Formular for AktivitetsTeamBooking."""
    
    class Meta:
        model = models.AktivitetsTeamBooking
        fields = [
            "item", "team", "team_contact", "status", "start_date",
            "start_time", "end_date", "end_time", "location",
            "remarks", "remarks_internal",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# ============================================================================
# INLINES
# ============================================================================

class AssignedInline(TabularInline):
    """Inline for tilføjelse/redigering af tilknyttede frivillige."""
    
    model = models.AktivitetsTeamBooking.assigned_aktivitetsteam.through
    verbose_name = "Tilknyttet frivillig"
    verbose_name_plural = "Tilknyttede frivillige"
    extra = 1
    can_delete = True
    min_num = 0

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtrer frivillige til kun dem med AktivitetsTeamBookingTildeling gruppe."""
        if db_field.name in ["volunteer", "user"]:
            kwargs["queryset"] = Volunteer.objects.filter(
                groups__name="AktivitetsTeamBookingTildeling",
                is_active=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ============================================================================
# FILTRER
# ============================================================================

class AssignedAktivitetsteamFilter(SimpleListFilter):
    """Tilpasset filter for tilknyttede frivillige."""
    
    title = "Tilknyttet frivillig"
    parameter_name = "assigned_aktivitetsteam"

    def lookups(self, request, model_admin):
        """Returnér liste af frivillige."""
        volunteers = Volunteer.objects.filter(
            groups__name="AktivitetsTeamBookingTildeling",
            is_active=True
        )
        return [(volunteer.id, volunteer.get_full_name()) for volunteer in volunteers]

    def queryset(self, request, queryset):
        """Filtrer bookinger baseret på valgt frivillig."""
        if self.value():
            return queryset.filter(assigned_aktivitetsteam__id=self.value())
        return queryset


# ============================================================================
# ADMIN REGISTRATIONS
# ============================================================================




@admin.register(models.AktivitetsTeamItem)
class AktivitetsTeamItemAdmin(AktivitetsTeamBaseAdmin):
    """Admin for håndtering af AktivitetsTeam ting/aktiviteter."""
    
    resource_class = AktivitetsTeamItemResource
    form = AktivitetsTeamItemAdminForm
    list_display = [
        "name", "display_image", "display_category", "is_active", "last_updated"
    ]
    list_filter = ["category", "is_active", "created"]
    search_fields = ["name", "description", "short_description"]
    list_fullwidth = True
    date_hierarchy = "created"
    ordering = ["-last_updated"]
    list_per_page = 25
    readonly_fields = ["created", "last_updated", "image_preview"]
    
    fieldsets = (
        (None, {
            "fields": (
                "name", "category", "is_active",
                "description", "short_description",
                "image", "image_preview",
                "youtube_link",
                "description_flow", "description_eksempel", "description_aktiverede",
                "location",
            ),
        }),
        ("Metadata", {
            "fields": ("created", "last_updated"),
        }),
    )

    @display(description="Billede")
    def display_image(self, obj):
        """Vis miniaturebillede af aktiviteten."""
        if obj.image:
            return format_html(
                '<img src="{}" width="40" height="40" class="rounded" />', 
                obj.image.url
            )
        return "-"

    @display(description="Kategori", label=True)
    def display_category(self, obj):
        """Vis kategori eller 'Ingen kategori'."""
        return obj.category.name if obj.category else "Ingen kategori"

    def image_preview(self, obj):
        """Vis forhåndsvisning af billede."""
        if obj.image:
            return mark_safe(
                f'<img src="{obj.image.url}" style="max-height: 200px; border-radius: 8px;" />'
            )
        return "Intet billede"

    image_preview.short_description = "Forhåndsvisning"


@admin.register(models.AktivitetsTeamBooking)
class AktivitetsTeamBookingAdmin(AktivitetsTeamBaseAdmin):
    """Admin for håndtering af AktivitetsTeam bookinger."""
    
    resource_class = AktivitetsTeamBookingResource
    form = AktivitetsTeamBookingAdminForm
    inlines = [AssignedInline]
    list_fullwidth = True
    date_hierarchy = "start_date"
    ordering = ["-start_date"]
    actions = AktivitetsTeamBaseAdmin.actions + ["export_selected_to_ical_action", "send_ical_via_email_action"]
    
    list_display = [
        "item", "team",
        "display_contact",
        "display_status",
        "formatted_times",
        "display_assigned_count",
        "last_updated"
    ]
    
    list_filter = [
        "status",
        "team",
        "item",
        ("start_date", admin.DateFieldListFilter),
        AssignedAktivitetsteamFilter,
    ]
    
    search_fields = ["item__name", "team__name", "team_contact__first_name", "team_contact__last_name"]
    readonly_fields = ["created", "last_updated", "display_assigned"]
    
    fieldsets = (
        (None, {
            "fields": (
                "item", "team", "team_contact",
                ("start_date", "start_time"),
                ("end_date", "end_time"),
                "location", "status",
                "remarks", "remarks_internal",
                "display_assigned",
            ),
        }),
        ("Metadata", {
            "fields": ("created", "last_updated"),
        }),
    )

    @display(description="Status", label={
        "Approved": "success",
        "Pending": "warning",
        "Rejected": "danger",
    })
    def display_status(self, obj):
        """Vis bookingstatus med farve."""
        status_da = {
            "Approved": "Godkendt ✅",
            "Pending": "Afventer ⏳",
            "Rejected": "Afvist ❌",
        }
        return status_da.get(obj.status, obj.status)

    @display(description="Kontakt", ordering="team_contact__first_name")
    def display_contact(self, obj):
        """Vis teamkontakt navn."""
        if obj.team_contact:
            return obj.team_contact.get_full_name()
        return "-"

    @display(description="Tidsramme", ordering="start_date")
    def formatted_times(self, obj):
        """Vis datointervallet i kompakt format."""
        return f"{obj.start_date.strftime('%d/%m')} - {obj.end_date.strftime('%d/%m')}"

    @display(description="Tilknyttede", ordering="assigned_aktivitetsteam")
    def display_assigned_count(self, obj):
        """Vis antal tilknyttede frivillige."""
        count = obj.assigned_aktivitetsteam.count()
        if count == 0:
            return format_html('<span style="color: #dc3545;">Ingen</span>')
        elif count == 1:
            return format_html('<span style="color: #fd7e14;">{}</span>', count)
        else:
            return format_html('<span style="color: #28a745;">{}</span>', count)

    def display_assigned(self, obj):
        """Vis liste af tilknyttede frivillige."""
        assigned = obj.assigned_aktivitetsteam.all()
        if not assigned.exists():
            return "Ingen frivillige tilknyttet endnu"
        
        html = "<ul style='margin: 10px 0;'>"
        for volunteer in assigned:
            html += f"<li>{volunteer.get_full_name()}</li>"
        html += "</ul>"
        return mark_safe(html)

    display_assigned.short_description = "Tilknyttede Frivillige"

    @admin.action(description="Exporter valgte bookinger til iCal fil")
    def export_selected_to_ical_action(self, request, queryset):
        """
        Eksporter valgte bookinger til iCal format.
        
        Opretter én .ics fil med alle valgte bookinger som separate eventos.
        Brugeren kan vælge flere bookinger ved at klikke checkboksene.
        """
        if not queryset.exists():
            self.message_user(request, "Vælg mindst én booking for at eksportere.", messages.WARNING)
            return
        
        ical_content = export_selected_to_ical(queryset)
        
        # Opret en beskrivende filnavn baseret på datointervallet
        first_booking = queryset.first()
        last_booking = queryset.last()
        start_date = first_booking.start_date.strftime("%d-%m-%Y")
        count = queryset.count()
        filename = f"aktiviteter_{count}_bookinger_{start_date}.ics"
        
        response = HttpResponse(ical_content, content_type='text/calendar')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        self.message_user(
            request, 
            f"✅ Eksporteret {count} booking(er) til iCal fil.",
            messages.SUCCESS
        )
        return response

    @admin.action(description="Send iCal via email (til tilknyttede frivillige)")
    def send_ical_via_email_action(self, request, queryset):
        """
        Send iCal for valgte bookinger via email til tilknyttede frivillige.
        
        Hver frivillig får sin egen .ics fil for hver booking de er tilknyttet.
        """
        if not queryset.exists():
            self.message_user(request, "Vælg mindst én booking for at sende.", messages.WARNING)
            return

        queryset = queryset.filter(assigned_aktivitetsteam__isnull=False).distinct()
        if not queryset.exists():
            self.message_user(
                request,
                f"⚠️ Ingen frivillige tilknyttet de valgte bookinger.",
                messages.WARNING
            )
            return

        email_template = "AktivitetsTeam/ical_email_template.html"
        queued_email_count = send_ical_via_email(queryset, email_template, settings.DEFAULT_FROM_EMAIL)

        if queued_email_count > 0:
            self.message_user(
                request, 
                f"✅ {queued_email_count} email(s) sat i kø til afsendelse i baggrunden.",
                messages.SUCCESS
            )
        else:
            self.message_user(request, "⚠️ Ingen emails blev sat i kø.", messages.WARNING)


# ============================================================================
# ADMIN FORMULARER
# ============================================================================

class AktivitetsTeamItemAdminForm(forms.ModelForm):
    """Formular for AktivitetsTeamItem."""
    
    class Meta:
        model = models.AktivitetsTeamItem
        fields = [
            "name", "category", "description", "short_description",
            "is_active", "youtube_link", "description_flow",
            "description_eksempel", "description_aktiverede",
            "location", "image",
        ]


class AktivitetsTeamBookingAdminForm(forms.ModelForm):
    """Formular for AktivitetsTeamBooking."""
    
    class Meta:
        model = models.AktivitetsTeamBooking
        fields = [
            "item", "team", "team_contact", "status", "start_date",
            "start_time", "end_date", "end_time", "location",
            "remarks", "remarks_internal",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
