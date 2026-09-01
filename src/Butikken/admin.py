import csv
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.http import HttpResponse

# Unfold & Import/Export
from unfold.admin import ModelAdmin, TabularInline 
from unfold.decorators import action, display
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

# Unfold Contrib for styled Import/Export forms
from unfold.contrib.import_export.forms import ExportForm, ImportForm, SelectableFieldsExportForm

# Models & Forms
from .models import (
    ButikkenItem, ButikkenBooking, ButikkenItemType, 
    Day, Recipe, Meal, Option, MealBooking, 
    MealPlan, MealOption, TeamMealPlan, Team
)
from .models import ButikkenOrder
from .forms import ButikkenBookingForm, MealPlanForm

# --- Resources ---

class ButikkenBookingResource(resources.ModelResource):
    item = fields.Field(attribute='item__name', column_name='Vare')
    team = fields.Field(attribute='team__name', column_name='Team')
    
    class Meta:
        model = ButikkenBooking
        fields = ('item', 'team', 'quantity', 'status', 'for_meal')

class TeamMealPlanResource(resources.ModelResource):
    # Explicitly map the ForeignKey fields to use the 'name' attribute instead of 'id'
    team = fields.Field(
        column_name='Team',
        attribute='team',
        widget=ForeignKeyWidget(Team, 'name')
    )
    meal_plan = fields.Field(
        column_name='Måltidsplan',
        attribute='meal_plan',
        widget=ForeignKeyWidget(MealPlan, 'name')
    )
    meal_option = fields.Field(
        column_name='Valgt Menu',
        attribute='meal_option',
        widget=ForeignKeyWidget(MealOption, 'id') # Or another identifying field
    )

    class Meta:
        model = TeamMealPlan
        fields = ('id', 'team', 'meal_plan', 'meal_option', 'status')
        export_order = ('id', 'team', 'meal_plan', 'meal_option', 'status')

class ButikkenItemResource(resources.ModelResource):
    class Meta:
        model = ButikkenItem
        # 1. Define the fields exactly as they appear in your CSV
        fields = ('name', 'type', 'content_normal', 'content_unit', 'description')
        
        # 2. IMPORTANT: Leave this empty to disable the "check if exists" logic.
        # This ensures every row becomes a NEW item.
        import_id_fields = () 
        
        # 3. Matches your preferred export order
        export_order = ('name', 'type', 'content_normal', 'content_unit', 'description')

    def before_import_row(self, row, **kwargs):
        """
        Since you want to allow spaces, we do NOT strip the middle of the string.
        We only strip 'accidental' leading/trailing spaces from the CSV cells.
        """
        if 'name' in row and row['name']:
            # This turns " Karse " into "Karse", 
            # but keeps "Salt karamel" as "Salt karamel"
            row['name'] = str(row['name']).strip()

class TeamMealPlanResource(resources.ModelResource):
    class Meta:
        model = TeamMealPlan
        fields = ('team__name', 'meal_plan__name', 'meal_option__recipe__name', 'status')

# --- Base Admin with Universal Features ---

class BaseAdmin(ModelAdmin, ImportExportModelAdmin):
    """
    Inherit from this to get selectable export/import 
    and bulk approve/reject/export actions automatically.
    """
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm
    
    # Raw Django Actions (Selection via Checkboxes)
    actions = ["approve_selected", "reject_selected", "export_selected_raw"]

    @admin.action(description="Godkend valgte")
    def approve_selected(self, request, queryset):
        updated = queryset.update(status="Approved")
        self.message_user(request, f"{updated} elementer er nu godkendt.", messages.SUCCESS)

    @admin.action(description="Afvis valgte")
    def reject_selected(self, request, queryset):
        updated = queryset.update(status="Rejected")
        self.message_user(request, f"{updated} elementer er blevet afvist.", messages.WARNING)

    @admin.action(description="Eksporter valgte (CSV)")
    def export_selected_raw(self, request, queryset):
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename={meta.model_name}_export.csv'
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])
        return response

# --- Inlines ---

class MealOptionInline(TabularInline):
    model = MealOption
    extra = 1
    tab = True 


# Inline for bookings inside an order
class ButikkenBookingInline(TabularInline):
    model = ButikkenBooking
    extra = 1
    fields = ('item', 'quantity', 'unit', 'start_date', 'start_time', 'team_contact')
    tab = True


class ButikkenOrderResource(resources.ModelResource):
    team = fields.Field(attribute='team__name', column_name='Team')
    team_contact = fields.Field(attribute='team_contact__first_name', column_name='Kontakt')

    class Meta:
        model = ButikkenOrder
        fields = ('id', 'team', 'team_contact', 'pickup_date', 'status', 'remarks')
        export_order = ('id', 'team', 'team_contact', 'pickup_date', 'status', 'remarks')

# --- Admin Classes ---

@admin.register(ButikkenItem)
class ButikkenItemAdmin(BaseAdmin):
    resource_class = ButikkenItemResource
    list_display = ["name", "display_type", "display_content", "last_updated"]
    list_filter = ["type"]
    search_fields = ["name", "description"]

    @display(description="Type", label=True)
    def display_type(self, obj):
        return obj.type

    @display(description="Indhold")
    def display_content(self, obj):
        return f"{obj.content_normal} {obj.content_unit}" if obj.content_normal else "-"

@admin.register(ButikkenBooking)
class ButikkenBookingAdmin(BaseAdmin):
    list_fullwidth = True
    # FIXED: 'for_meal' used directly as it's a field in your model
    list_display = ["order", "item", "display_status", "team", "for_meal", "formatted_start", "quantity_with_unit"]
    list_filter = ["status", "for_meal", "team", "item", "start_date", "order"]
    
    @display(description="Status", label={
        "Approved": "success", "Pending": "warning", "Rejected": "danger", "Udleveret": "info",
    })
    def display_status(self, obj):
        return obj.status

    @display(description="Mængde")
    def quantity_with_unit(self, obj):
        return f"{obj.quantity} {obj.unit}"

    @display(description="Afhentning")
    def formatted_start(self, obj):
        return f"{obj.start_date.strftime('%d/%m')} kl. {obj.start_time.strftime('%H:%M')}"

@admin.register(TeamMealPlan)
class TeamMealPlanAdmin(BaseAdmin):
    resource_class = TeamMealPlanResource
    list_display = ["team", "meal_plan", "meal_option", "display_status", "last_updated"]
    list_filter = ["status", "team"]

    @display(description="Status", label={"Approved": "success", "Pending": "warning", "Rejected": "danger"})
    def display_status(self, obj):
        return obj.status

@admin.register(MealPlan)
class MealPlanAdmin(BaseAdmin):
    list_display = ["name", "day_of_week", "meal_date", "open_date", "close_date"]
    inlines = [MealOptionInline]

    @display(description="Ugedag")
    def day_of_week(self, obj):
        return obj.meal_date.strftime("%A")

# Registration for remaining models using the new BaseAdmin features
@admin.register(Recipe)
class RecipeAdmin(BaseAdmin):
    list_display = ["name", "description", "last_updated"]


@admin.register(ButikkenOrder)
class ButikkenOrderAdmin(BaseAdmin):
    resource_class = ButikkenOrderResource
    list_display = ["id", "team", "team_contact", "pickup_date", "status", "last_updated"]
    list_filter = ["status", "team", "pickup_date"]
    inlines = [ButikkenBookingInline]

    @admin.action(description="Eksporter ordre inkl. varer (CSV)")
    def export_order_with_bookings(self, request, queryset):
        # Export orders and their child bookings as CSV (simple implementation)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=butikken_orders_export.csv'
        writer = csv.writer(response)
        writer.writerow(['order_id', 'team', 'team_contact', 'pickup_date', 'order_status', 'item', 'quantity', 'unit', 'start_date', 'start_time'])
        for order in queryset:
            for b in order.bookings.all():
                writer.writerow([
                    order.id,
                    getattr(order.team, 'name', ''),
                    getattr(order.team_contact, 'first_name', ''),
                    order.pickup_date,
                    order.status,
                    getattr(b.item, 'name', ''),
                    b.quantity,
                    b.unit,
                    b.start_date,
                    b.start_time,
                ])
        return response


