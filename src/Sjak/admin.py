from django.conf import settings
from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericTabularInline
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_comments_xtd.models import XtdComment
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.decorators import action, display

from utils.ical_utils import export_selected_to_ical

from .forms import SjakBookingForm
from .models import SjakBooking, SjakItem, SjakItemLocation, SjakItemType, SjakTag

# ============================================================================
# IMPORT/EXPORT RESSOURCER
# ============================================================================

class CreateIfNotFoundWidget(ForeignKeyWidget):
    """Automatisk opret relaterede objekter hvis de ikke findes ved import."""
    
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        obj, _ = self.model.objects.get_or_create(**{self.field: value})
        return obj


class SjakBookingResource(resources.ModelResource):
    """Import/Export ressource for SjakBooking."""
    
    item = fields.Field(column_name='Item', attribute='item', widget=ForeignKeyWidget(SjakItem, 'name'))
    team = fields.Field(column_name='Team', attribute='team', widget=ForeignKeyWidget(SjakItem, 'name'))
    team_contact = fields.Field(column_name='Kontakt', attribute='team_contact', widget=ForeignKeyWidget(SjakItem, 'first_name'))

    class Meta:
        model = SjakBooking
        fields = (
            'id', 'item', 'quantity', 'team', 'team_contact', 
            'start_date', 'start_time', 'end_date', 'end_time', 
            'status', 'status_internal'
        )


class SjakItemResource(resources.ModelResource):
    """Import/Export ressource for SjakItem med auto-oprettelse af relaterede objekter."""
    
    item_type = fields.Field(
        column_name='item_type',
        attribute='item_type',
        widget=CreateIfNotFoundWidget(SjakItemType, 'name')
    )
    location = fields.Field(
        column_name='location',
        attribute='location',
        widget=CreateIfNotFoundWidget(SjakItemLocation, 'name')
    )

    class Meta:
        model = SjakItem
        import_id_fields = ('name',)
        fields = ('name', 'item_type', 'location', 'quantity_lager', 'description')
        export_order = fields


# ============================================================================
# BASE ADMIN
# ============================================================================

class SjakBaseAdmin(ModelAdmin, ImportExportModelAdmin):
    """Basiskonfiguration for alle Sjak admin klasser."""
    
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    actions = ["approve_selected", "reject_selected", "export_selected_to_ical_action"]

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

    @action(description="Exporter valgte bookinger til iCal fil")
    def export_selected_to_ical_action(self, request, queryset):
        """
        Eksporter valgte bookinger som iCal fil.
        Oprettter én .ics fil med alle valgte bookinger som separate eventos.
        """
        if not queryset.exists():
            self.message_user(request, "Vælg mindst én booking for at eksportere.", messages.WARNING)
            return
        
        ical_content = export_selected_to_ical(queryset)
        count = queryset.count()
        first_booking = queryset.first()
        start_date = first_booking.start_date.strftime("%d-%m-%Y")
        filename = f"sjak_{count}_bookinger_{start_date}.ics"
        
        response = HttpResponse(ical_content, content_type='text/calendar')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        self.message_user(
            request,
            f"✅ Eksporteret {count} booking(er) til iCal fil.",
            messages.SUCCESS
        )
        return response


# ============================================================================
# KOMMENTAR INLINE
# ============================================================================

class CommentInline(GenericTabularInline):
    """Inline for tilføjelse/redigering af kommentarer på bookinger."""
    
    model = XtdComment
    ct_field = "content_type"
    ct_fk_field = "object_pk"
    extra = 1
    fields = ("user", "comment", "submit_date", "is_public")
    readonly_fields = ("submit_date", "user")
    tab = False

    def has_change_permission(self, request, obj=None):
        """Tillad kun forfatter eller superuser at redigere kommentarer."""
        if obj and isinstance(obj, XtdComment):
            return obj.user == request.user or request.user.is_superuser
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Tillad kun forfatter eller superuser at slette kommentarer."""
        if obj and isinstance(obj, XtdComment):
            return obj.user == request.user or request.user.is_superuser
        return super().has_delete_permission(request, obj)


# ============================================================================
# SJAK TING ADMIN
# ============================================================================

@admin.register(SjakItem)
class SjakItemAdmin(SjakBaseAdmin):
    """Admin for håndtering af Sjak ting/udstyr."""
    
    resource_class = SjakItemResource
    list_display = ["name", "display_item_type", "display_location", "display_image", "quantity_lager", "last_updated"]
    list_filter = ["item_type", "location", "created"]
    search_fields = ["name", "description"]
    list_fullwidth = True
    date_hierarchy = "created"
    ordering = ["-last_updated"]
    list_per_page = 25
    
    # Unfold styling
    unfold_fieldset_summary = {
        "Grundlæggende": ("name", "item_type"),
        "Lokation og Lager": ("location", "quantity_lager"),
    }
    unfold_hide_empty_change_form_tabs = True

    @display(description="Billede")
    def display_image(self, obj):
        """Vis miniaturebillede af ting."""
        if obj.image:
            return format_html(
                '<img src="{}" width="40" height="40" class="rounded" />', 
                obj.image.url
            )
        return "-"

    @display(description="Type", label=True)
    def display_item_type(self, obj):
        """Vis tingtype eller 'Ingen type'."""
        return obj.item_type.name if obj.item_type else "Ingen type"

    @display(description="Lokation", label=True)
    def display_location(self, obj):
        """Vis lokation eller 'Lager'."""
        return obj.location.name if obj.location else "Lager"


# ============================================================================
# SJAK BOOKING ADMIN
# ============================================================================

@admin.register(SjakBooking)
class SjakBookingAdmin(SjakBaseAdmin):
    """Admin for håndtering af Sjak udstyrsbookinger."""
    
    resource_class = SjakItemResource
    list_fullwidth = True
    
    inlines = [CommentInline]
    form = SjakBookingForm
    
    list_display = [
        "item", "quantity", "team", "display_status",
        "formatted_times", "display_internal_status"
    ]
    list_filter = ["status", "status_internal", "team", "item", "start_date"]
    search_fields = ["item__name", "team__name", "team_contact__first_name"]
    readonly_fields = ["image_preview"]

    fields = [
        ("item", "status"),
        ("team", "quantity"),
        ("start_date", "start_time"),
        ("end_date", "end_time"),
        "team_contact",
        "assigned_sjak",
        ("remarks", "status_internal"),
        "image",
        "image_preview",
    ]

    # ---- Visningsmetoder ----

    @display(description="Status", label={
        "Approved": "success",
        "Pending": "warning",
        "Rejected": "danger"
    })
    def display_status(self, obj):
        """Vis bookingstatus med farve."""
        return obj.status

    @display(description="Intern Status", label={
        "Afventer": "info",
        "Igang": "warning",
        "Klar": "success",
        "Afsluttet": "neutral"
    })
    def display_internal_status(self, obj):
        """Vis internt status med farve."""
        return obj.status_internal

    @display(description="Tidsramme")
    def formatted_times(self, obj):
        """Vis datointervallet i kompakt format."""
        return f"{obj.start_date.strftime('%d/%m')} {obj.start_time.strftime('%H:%M')} - {obj.end_date.strftime('%d/%m')} {obj.end_time.strftime('%H:%M')}"

    def image_preview(self, obj):
        """Vis forhåndsvisning af bookingbillede hvis tilgængeligt."""
        if obj.image:
            return mark_safe(
                f'<img src="{obj.image.url}" style="max-height: 200px; border-radius: 8px;" />'
            )
        return "Intet billede"

    image_preview.short_description = "Forhåndsvisning"

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
                    instance.site_id = getattr(settings, "SITE_ID", 1)
                
                # 2. Inject Current User if none is set
                if not instance.user:
                    instance.user = request.user
                
                # 3. Force the user's name/email into the required fields
                if not instance.user_name:
                    instance.user_name = request.user.get_full_name() or request.user.username
                if not instance.user_email:
                    instance.user_email = request.user.email

            instance.save()
        formset.save_m2m()


# ============================================================================
# SIMPLE ADMIN KLASSER
# ============================================================================

@admin.register(SjakItemType)
class SjakItemTypeAdmin(SjakBaseAdmin):
    """Admin for tingtyper/kategorier."""
    list_display = ["name", "created"]
    list_fullwidth = True
    ordering = ["name"]
    unfold_hide_empty_change_form_tabs = True


@admin.register(SjakItemLocation)
class SjakItemLocationAdmin(SjakBaseAdmin):
    """Admin for lagerlokaliteter."""
    list_display = ["name", "created"]
    list_fullwidth = True
    ordering = ["name"]
    unfold_hide_empty_change_form_tabs = True


@admin.register(SjakTag)
class SjakTagAdmin(SjakBaseAdmin):
    """Admin for booking-mærker."""
    list_display = ["name", "color", "created"]
    fields = ["name", "color"]
    list_fullwidth = True
    ordering = ["name"]
    unfold_hide_empty_change_form_tabs = True

