from datetime import datetime

from django.contrib import admin, messages
from django.http import HttpResponse
from icalendar import Calendar
from icalendar import Event as ICalEvent
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.decorators import display

from .models import FotoBooking, FotoItem

# --- Resources ---

class FotoBookingResource(resources.ModelResource):
    class Meta:
        model = FotoBooking
        fields = ('id', 'item__name', 'team__name', 'team_contact__first_name', 'location', 'start_date', 'status', 'remarks')

# --- Admin Classes ---

@admin.register(FotoBooking)
class FotoBookingAdmin(ModelAdmin, ImportExportModelAdmin):
    resource_class = FotoBookingResource
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    
    list_fullwidth = True
    list_filter_submit = True  # Adds a 'Filter' button for better performance
    
    list_display = [
        "item", "team", "display_status", "location", "formatted_start", "formatted_end", "last_updated"
    ]
    list_filter = ["status", "item", "team", "start_date"]
    search_fields = ["item__name", "team__name", "location", "remarks"]
    readonly_fields = ["created", "last_updated"]
    actions = ["approve_selected", "reject_selected", "export_selected_to_ical"]

    # --- Detail View Layout ---
    fieldsets = (
        ("Information", {
            "fields": ("item", "status", "team", "team_contact")
        }),
        ("Tid og Sted", {
            "fields": (("start_date", "start_time"), ("end_date", "end_time"), "location"),
        }),
        ("Yderligere", {
            "fields": ("remarks", "created", "last_updated"),
        }),
    )

    @display(description="Status", label={
        "Approved": "success", "Pending": "warning", "Rejected": "danger",
    })
    def display_status(self, obj):
        return obj.status

    @display(description="Start")
    def formatted_start(self, obj):
        return f"{obj.start_date.strftime('%d/%m')} {obj.start_time.strftime('%H:%M')}"

    @display(description="Slut")
    def formatted_end(self, obj):
        return f"{obj.end_date.strftime('%d/%m')} {obj.end_time.strftime('%H:%M')}"

    # --- Actions ---
    @admin.action(description="Godkend valgte")
    def approve_selected(self, request, queryset):
        queryset.update(status="Approved")
        self.message_user(request, "Foto bookinger godkendt.", messages.SUCCESS)

    @admin.action(description="Afvis valgte")
    def reject_selected(self, request, queryset):
        queryset.update(status="Rejected")
        self.message_user(request, "Foto bookinger afvist.", messages.WARNING)

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
            event = ICalEvent()
            event.add('summary', f"Foto: {booking.item.name} ({booking.team.name})")
            event.add('description', booking.remarks or "Ingen bemærkninger")
            event.add('location', booking.location)
            
            start = datetime.combine(booking.start_date, booking.start_time)
            end = datetime.combine(booking.end_date, booking.end_time)
            
            event.add('dtstart', start)
            event.add('dtend', end)
            calendar.add_component(event)
        
        count = queryset.count()
        first_booking = queryset.first()
        start_date = first_booking.start_date.strftime("%d-%m-%Y")
        filename = f"foto_{count}_bookinger_{start_date}.ics"
        
        response = HttpResponse(calendar.to_ical(), content_type='text/calendar')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        self.message_user(
            request,
            f"✅ Eksporteret {count} booking(er) til iCal fil.",
            messages.SUCCESS
        )
        return response

@admin.register(FotoItem)
class FotoItemAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ["name", "description", "last_updated"]
    search_fields = ["name"]

