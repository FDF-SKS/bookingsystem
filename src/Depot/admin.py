
from django.contrib import admin
from django.utils.html import format_html
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from unfold.decorators import display

from .models import DepotBooking, DepotItem, DepotLocation

# --- Custom Widgets & Fields ---

class DepotLocationWidget:
    """Custom widget to handle location name → DepotLocation conversion."""
    def clean(self, value, row=None, *args, **kwargs):
        """Convert location name string to DepotLocation instance."""
        if not value:
            return None
        
        # Exact name match (case-sensitive)
        location, created = DepotLocation.objects.get_or_create(
            name=value,
            defaults={'description': ''}
        )
        return location
    
    def render(self, value, obj=None):
        """Render location name instead of ID."""
        if value:
            return value.name if hasattr(value, 'name') else str(value)
        return ''


# --- Custom Resources ---

class DepotLocationResource(resources.ModelResource):
    """Import/Export resource for DepotLocation with strict matching."""
    
    class Meta:
        model = DepotLocation
        fields = ('name', 'description', 'created', 'last_updated')
        import_id_fields = ('name',)  # Use name as unique identifier
    
    def get_or_init_instance(self, row):
        """Create or get instance using name-based matching."""
        instance, created = self.Meta.model.objects.get_or_create(
            name=row.get('name', ''),
            defaults={'description': row.get('description', '')}
        )
        return instance, created


class DepotItemResource(resources.ModelResource):
    """Import/Export resource for DepotItem."""
    
    location_name = fields.Field(
        column_name='location_name',
        attribute='location',
        widget=DepotLocationWidget()
    )
    
    class Meta:
        model = DepotItem
        fields = ('name', 'location_name', 'description', 'quantity', 'unit')
        import_id_fields = ()  # Create new items, don't update existing ones
        export_order = ('name', 'location_name', 'description', 'quantity', 'unit')
    
    def before_import_row(self, row, **kwargs):
        """Process row before import - handle location name resolution and defaults."""
        # Strip whitespace from name
        if 'name' in row and row['name']:
            row['name'] = str(row['name']).strip()
        
        # Handle location name resolution
        location_name = row.get('location_name', '')
        if location_name:
            location_name = str(location_name).strip()
            location, _ = DepotLocation.objects.get_or_create(
                name=location_name,
                defaults={'description': ''}
            )
            row['location'] = location.pk
        else:
            row['location'] = None
        
        # Set default unit if not provided
        if not row.get('unit'):
            row['unit'] = 'stk'
        
        return row


class DepotBookingResource(resources.ModelResource):
    """Import/Export resource for DepotBooking."""
    
    class Meta:
        model = DepotBooking
        fields = ('item__name', 'team__name', 'team_contact__first_name', 'quantity', 'start_date', 'start_time', 'end_date', 'end_time', 'status', 'created_at')


# --- Base Admin ---

class DepotBaseAdmin(ModelAdmin, ImportExportModelAdmin):
    """Base admin configuration for Depot models with Unfold support."""
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    list_fullwidth = True
    list_filter_submit = True


# --- Inlines ---

class DepotItemInline(TabularInline):
    """Inline admin for DepotItem within DepotLocation."""
    model = DepotItem
    extra = 0
    fields = ['name', 'description', 'quantity', 'image']
    readonly_fields = ['created', 'last_updated']


# --- Admin Classes ---

@admin.register(DepotLocation)
class DepotLocationAdmin(DepotBaseAdmin):
    """Admin interface for Depot storage locations."""
    
    resource_class = DepotLocationResource
    list_display = ['name', 'item_count_display', 'created']
    search_fields = ['name', 'description']
    list_filter = ['created', 'last_updated']
    readonly_fields = ['created', 'last_updated', 'item_count_display']
    inlines = [DepotItemInline]
    
    fieldsets = (
        ('Grundinformation', {
            'fields': ('name', 'description')
        }),
        ('Statistik', {
            'fields': ('item_count_display',),
            'classes': ('collapse',)
        }),
        ('Systeminfo', {
            'fields': ('created', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    @display(description="Antal varer", ordering='name')
    def item_count_display(self, obj):
        """Display number of items in this location."""
        count = obj.items.count()
        return format_html('<span style="font-weight: bold;">{}</span>', count)


@admin.register(DepotItem)
class DepotItemAdmin(DepotBaseAdmin):
    """Admin interface for Depot inventory items with strict import/export."""
    
    resource_class = DepotItemResource
    
    list_display = ['name', 'location', 'quantity', 'unit', 'image_preview', 'created']
    search_fields = ['name', 'description', 'location__name']
    list_filter = ['created', 'last_updated', 'location']
    readonly_fields = ['created', 'last_updated', 'image_preview']
    
    fieldsets = (
        ('Grundinformation', {
            'fields': ('name', 'location', 'description', 'image')
        }),
        ('Lagerbeholdning', {
            'fields': ('quantity', 'unit')
        }),
        ('Billede', {
            'fields': ('image_preview',),
            'classes': ('collapse',)
        }),
        ('Systeminfo', {
            'fields': ('created', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    @display(description="Billede")
    def image_preview(self, obj):
        """Display image preview in admin."""
        if obj.image:
            return format_html(
                '<img src="{}" width="100" height="100" style="border-radius: 4px;" />',
                obj.image.url
            )
        return '-'
    
    def get_import_data_dict(self, *args, **kwargs):
        """Override to ensure location name is properly handled during import."""
        return super().get_import_data_dict(*args, **kwargs)


@admin.register(DepotBooking)
class DepotBookingAdmin(DepotBaseAdmin):
    """Admin interface for Depot item reservations."""
    
    resource_class = DepotBookingResource
    
    list_display = ['item', 'team', 'team_contact', 'quantity', 'start_date', 'start_time', 'status', 'created_at']
    list_filter = ['status', 'created_at', 'start_date', 'team']
    search_fields = ['item__name', 'team__name', 'team_contact__first_name']
    readonly_fields = ['created_at', 'last_updated', 'available_quantity_display']
    
    fieldsets = (
        ('Booking Information', {
            'fields': ('item', 'team', 'team_contact', 'quantity')
        }),
        ('Tid', {
            'fields': (('start_date', 'start_time'), ('end_date', 'end_time'), 'status')
        }),
        ('Yderligere Info', {
            'fields': ('remarks', 'admin_comment', 'available_quantity_display')
        }),
        ('Systeminfo', {
            'fields': ('created_at', 'last_updated'),
            'classes': ('collapse',)
        }),
    )
    
    @display(description="Available / Total", ordering='item')
    def available_quantity_display(self, obj):
        """Display available quantity for the booking period."""
        available = obj.item.available_quantity(obj.start_date, obj.end_date)
        return f"{available} / {obj.item.quantity}"



