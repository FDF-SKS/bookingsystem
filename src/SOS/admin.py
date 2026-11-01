from datetime import datetime

from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline
from django.http import HttpResponse
from django_comments_xtd.models import XtdComment
from icalendar import Calendar, Event
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.decorators import display

from organization.models import Team, Volunteer

from .models import SOSBooking, SOSItem, SOSType

# --- Resources ---

class SOSBookingResource(resources.ModelResource):
    item = fields.Field(column_name='Item', attribute='item', widget=ForeignKeyWidget(SOSItem, 'name'))
    team = fields.Field(column_name='Team', attribute='team', widget=ForeignKeyWidget(Team, 'name'))
    team_contact = fields.Field(column_name='Kontakt', attribute='team_contact', widget=ForeignKeyWidget(Volunteer, 'first_name'))

    class Meta:
        model = SOSBooking
        fields = (
            'id', 'item', 'quantity', 'team', 'team_contact', 
            'start_date', 'start_time', 'end_date', 'end_time', 
            'status', 'assistance_needed', 'delivery_needed',
            'remarks', 'remarks_internal', 'dispatched', 'received'
        )

# --- Inlines ---

class SOSCommentInline(GenericTabularInline):
    model = XtdComment
    ct_field = "content_type"
    ct_fk_field = "object_pk"
    extra = 0
    classes = ["tab"]
    fields = ('user', 'comment', 'submit_date', 'is_public')
    readonly_fields = ('submit_date', 'user')

# --- Base Admin ---

class SOSBaseAdmin(ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    
    @admin.action(description="Godkend valgte")
    def approve_selected(self, request, queryset):
        queryset.update(status="Approved")
        self.message_user(request, f"{queryset.count()} bookinger godkendt.", messages.SUCCESS)

    @admin.action(description="Afvis valgte")
    def reject_selected(self, request, queryset):
        queryset.update(status="Rejected")
        self.message_user(request, f"{queryset.count()} bookinger afvist.", messages.WARNING)

# --- Admin Classes ---

@admin.register(SOSBooking)
class SOSBookingAdmin(SOSBaseAdmin):
    resource_class = SOSBookingResource
    inlines = [SOSCommentInline]
    actions = ["approve_selected", "reject_selected", "export_selected_to_ical"]
    
    list_display = [
        "item", "display_status", "quantity", "team", 
        "formatted_start", "assistance_badge", "delivery_badge",
        "dispatch_status"
    ]
    
    list_filter = ["status", "item", "team", "dispatched", "received"]
    search_fields = ["item__name", "team__name", "remarks"]
    readonly_fields = ["created", "last_updated"]

    @display(description="Status", label={
        "Approved": "success", "Pending": "warning", "Rejected": "danger",
    })
    def display_status(self, obj):
        return obj.status

    @display(description="Start")
    def formatted_start(self, obj):
        return f"{obj.start_date.strftime('%d/%m')} {obj.start_time.strftime('%H:%M')}"

    @display(description="Assistance", label={"True": "info", "False": "neutral"})
    def assistance_badge(self, obj):
        return "Ja" if obj.assistance_needed else "Nej"

    @display(description="Levering", label={"True": "info", "False": "neutral"})
    def delivery_badge(self, obj):
        return "Ja" if obj.delivery_needed else "Nej"

    @display(description="Logistik", label={
        "Modtaget": "success", "Sendt": "info", "Afventer": "neutral"
    })
    def dispatch_status(self, obj):
        if obj.received:
            return "Modtaget"
        if obj.dispatched:
            return "Sendt"
        return "Afventer"

    @admin.action(description="Exporter valgte bookinger til iCal fil")
    def export_selected_to_ical(self, request, queryset):
        """
        Eksporter valgte bookinger som iCal fil.
        Opretter én .ics fil med alle valgte bookinger som separate eventos.
        """
        if not queryset.exists():
            self.message_user(request, "Vælg mindst én booking for at eksportere.", messages.WARNING)
            return
        
        calendar = Calendar()
        for booking in queryset:
            event = Event()
            event.add('summary', f"SOS: {booking.item} ({booking.team})")
            start = datetime.combine(booking.start_date, booking.start_time)
            end = datetime.combine(booking.end_date, booking.end_time)
            event.add('dtstart', start)
            event.add('dtend', end)
            event.add('description', f"Kontakt: {booking.team_contact}\nBemærkning: {booking.remarks}")
            calendar.add_component(event)
        
        count = queryset.count()
        first_booking = queryset.first()
        start_date = first_booking.start_date.strftime("%d-%m-%Y")
        filename = f"sos_{count}_bookinger_{start_date}.ics"
        
        response = HttpResponse(calendar.to_ical(), content_type='text/calendar')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        self.message_user(
            request,
            f"✅ Eksporteret {count} booking(er) til iCal fil.",
            messages.SUCCESS
        )
        return response

@admin.register(SOSItem)
class SOSItemAdmin(SOSBaseAdmin):
    list_display = ["name", "description", "last_updated"]
    search_fields = ["name", "description"]

@admin.register(SOSType)
class SOSTypeAdmin(SOSBaseAdmin):
    list_display = ["name", "created"]

