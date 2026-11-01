from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline
from django.http import HttpResponse

# Comments
from django_comments_xtd.models import XtdComment
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget

# Unfold & Import/Export
from unfold.admin import ModelAdmin

# Unfold Contrib for styled Import/Export forms
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.decorators import action, display

from organization.models import Team, Volunteer

# iCal utilities
from utils.ical_utils import export_selected_to_ical

from .models import TeknikBooking, TeknikItem, TeknikType

# --- Resources ---

class TeknikBookingResource(resources.ModelResource):
    item = fields.Field(column_name='Item', attribute='item', widget=ForeignKeyWidget(TeknikItem, 'name'))
    team = fields.Field(column_name='Team', attribute='team', widget=ForeignKeyWidget(Team, 'name'))
    team_contact = fields.Field(column_name='Kontakt', attribute='team_contact', widget=ForeignKeyWidget(Volunteer, 'first_name'))

    class Meta:
        model = TeknikBooking
        fields = (
            'id', 'item', 'quantity', 'team', 'team_contact', 
            'start_date', 'start_time', 'end_date', 'end_time', 
            'status', 'assistance_needed', 'delivery_needed'
        )

# --- Inlines ---
class CommentInline(GenericTabularInline):
    model = XtdComment
    ct_field = "content_type"
    ct_fk_field = "object_pk"
    extra = 1
    fields = ("user", "comment", "submit_date", "is_public")
    readonly_fields = ("submit_date", "user") # Keep user read-only to prevent spoofing
    tab = False

    def has_change_permission(self, request, obj=None):
        # If we are looking at a specific comment
        if obj and isinstance(obj, XtdComment):
            # Only allow editing if the user is the author OR a superuser
            return obj.user == request.user or request.user.is_superuser
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Only allow deleting if the user is the author OR a superuser
        if obj and isinstance(obj, XtdComment):
            return obj.user == request.user or request.user.is_superuser
        return super().has_delete_permission(request, obj)



# --- Base Admin ---

class TeknikBaseAdmin(ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    
    actions = ["approve_selected", "reject_selected", "export_selected_to_ical_action"]

    @admin.action(description="Godkend valgte")
    def approve_selected(self, request, queryset):
        queryset.update(status="Approved")
        self.message_user(request, "Valgte bookinger er godkendt.", messages.SUCCESS)

    @admin.action(description="Afvis valgte")
    def reject_selected(self, request, queryset):
        queryset.update(status="Rejected")
        self.message_user(request, "Valgte bookinger er afvist.", messages.WARNING)

    @action(description="Exporter valgte bookinger til iCal fil")
    def export_selected_to_ical_action(self, request, queryset):
        """
        Export selected bookings to iCal format.
        Creates one .ics file with all selected bookings as separate events.
        """
        if not queryset.exists():
            self.message_user(request, "Select at least one booking to export.", messages.WARNING)
            return
        
        ical_content = export_selected_to_ical(queryset)
        count = queryset.count()
        first_booking = queryset.first()
        start_date = first_booking.start_date.strftime("%d-%m-%Y")
        filename = f"teknik_{count}_bookings_{start_date}.ics"
        
        response = HttpResponse(ical_content, content_type='text/calendar')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        self.message_user(
            request,
            f"✅ Exported {count} booking(s) to iCal file.",
            messages.SUCCESS
        )
        return response

# --- Admin Classes ---
@admin.register(TeknikBooking)
class TeknikBookingAdmin(TeknikBaseAdmin):
    resource_class = TeknikBookingResource
    list_fullwidth = True
    
    inlines = [CommentInline]
    
    list_display = [
        "item", "quantity", "team", "display_status",
        "formatted_start", "assistance_badge", "delivery_badge"
    ]

    fields = [
        ("item", "status"),
        ("team", "quantity"),
        ("start_date", "start_time"),
        ("end_date", "end_time"),
        "team_contact", 
        ("assistance_needed", "delivery_needed"),
        "remarks",
        "remarks_internal",
        "location",
    ]

    # REMOVE the 'fields = [...]' line entirely. 
    # It was causing the unhashable type error and conflict.

    list_filter = ["status", "item", "team", "start_date"]
    search_fields = ["item__name", "team__name", "team_contact__first_name"]

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
    
    def save_formset(self, request, form, formset, change):
        """
        Catches the inline formset and injects the SITE_ID and 
        the current user into any new comments.
        """
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, XtdComment):
                # 1. Inject Site ID
                if not instance.site_id:
                    from django.conf import settings
                    instance.site_id = getattr(settings, "SITE_ID", 1)
                
                # 2. Inject Current User if none is set
                if not instance.user:
                    instance.user = request.user
                
                # Optional: Force the user's name/email into the required fields 
                # if the model uses them for guest tracking
                if not instance.user_name:
                    instance.user_name = request.user.get_full_name() or request.user.username
                if not instance.user_email:
                    instance.user_email = request.user.email

            instance.save()
        formset.save_m2m()

@admin.register(TeknikItem)
class TeknikItemAdmin(TeknikBaseAdmin):
    list_display = ["name", "description", "last_updated"]
    search_fields = ["name", "description"]

@admin.register(TeknikType)
class TeknikTypeAdmin(TeknikBaseAdmin):
    list_display = ["name", "created"]

