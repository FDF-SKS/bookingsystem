import contextlib
import json
import logging
from collections import defaultdict
from datetime import time
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import generic
from django.views.decorators.http import require_POST

from organization.models import Event, Team
from organization.permissions import StaffRequiredMixin, TeamQuerysetMixin
from utils.ui import (
    BookingDetailContextMixin,
    BookingListContextMixin,
    ItemDetailContextMixin,
    ItemListContextMixin,
)

from . import forms, models
from .forms import BulkMealForm, TeamMealPlanForm
from .models import MealBooking, TeamMealPlan

logger = logging.getLogger(__name__)

# Safety cap for the JSON payload accepted from the order form.
MAX_ITEM_PROPOSALS_PER_ORDER = 50


@login_required
@user_passes_test(lambda u: u.is_staff)
def approve_booking(request, pk):
    """Approve a Butikken booking."""
    booking = get_object_or_404(models.ButikkenBooking, pk=pk)
    booking.status = 'Approved'
    booking.save()
    return redirect(request.GET.get('next', 'Butikken_ButikkenBooking_list'))


@login_required
@user_passes_test(lambda u: u.is_staff)
def reject_booking(request, pk):
    """Reject a Butikken booking."""
    booking = get_object_or_404(models.ButikkenBooking, pk=pk)
    booking.status = 'Rejected'
    booking.save()
    return redirect(request.GET.get('next', 'Butikken_ButikkenBooking_list'))


def _active_items():
    """Catalog items that may be picked in an order."""
    return models.ButikkenItem.objects.filter(status=models.ButikkenItem.STATUS_ACTIVE)


def _parse_cart_qty(raw) -> Decimal:
    """Parse a posted quantity, tolerating commas and invalid input."""
    try:
        value = Decimal(str(raw)) if raw not in (None, "") else Decimal("1")
    except (InvalidOperation, TypeError, ValueError):
        try:
            value = Decimal(str(raw).replace(",", "."))
        except Exception:
            value = Decimal("1")
    return value if value > 0 else Decimal("1")


def _format_qty(quantity: Decimal) -> str:
    return format(quantity.normalize(), "f")


def _upsert_order_booking(order, item, quantity, unit, user):
    """Create or update the single booking for ``item`` on ``order``."""
    booking = (
        models.ButikkenBooking.objects.filter(order=order, item=item)
        .order_by("pk")
        .first()
    )
    if booking is None:
        return models.ButikkenBooking.objects.create(
            order=order,
            item=item,
            team=order.team,
            team_contact=(order.team_contact or user),
            start_date=(order.pickup_date or timezone.now().date()),
            start_time=time(8, 0),
            quantity=quantity,
            unit=(unit or item.content_unit or ""),
        )
    booking.quantity = quantity
    booking.unit = unit or booking.unit
    booking.start_date = booking.start_date or order.pickup_date or timezone.now().date()
    booking.start_time = booking.start_time or time(8, 0)
    booking.save(
        update_fields=["quantity", "unit", "start_date", "start_time", "last_updated"]
    )
    return booking


def _create_item_proposals(order, raw_json, user) -> list[int]:
    """Turn submitted item proposals into pending catalog items + bookings.

    A proposal whose name matches an existing active item reuses that item, so
    users cannot accidentally create duplicates of catalog entries. Otherwise
    an existing *pending* item with the same name is reused across orders, which
    aggregates demand for the same proposed item. Anything else becomes a new
    ``Pending`` :class:`ButikkenItem` that staff can approve or reject in the
    admin.

    Returns the item ids that now have a booking on ``order`` so callers can
    keep them when syncing the rest of the cart.
    """
    try:
        raw_proposals = json.loads(raw_json or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(raw_proposals, list):
        return []

    item_ids: list[int] = []
    for raw in raw_proposals[:MAX_ITEM_PROPOSALS_PER_ORDER]:
        if not isinstance(raw, dict):
            continue
        form = forms.ButikkenItemProposalForm(
            data={
                "name": raw.get("name"),
                "quantity": raw.get("qty", raw.get("quantity")),
                "unit": raw.get("unit"),
                "description": raw.get("description"),
            }
        )
        if not form.is_valid():
            logger.info("Ignoring invalid item proposal: %s", form.errors.as_json())
            continue

        name = form.cleaned_data["name"]
        quantity = form.cleaned_data["quantity"] or Decimal("1")
        unit = form.cleaned_data["unit"]
        description = form.cleaned_data["description"]

        item = models.ButikkenItem.objects.filter(
            status=models.ButikkenItem.STATUS_ACTIVE, name__iexact=name
        ).first()
        if item is None:
            # Reuse an existing proposal for the same item (possibly from another
            # order) instead of creating near-duplicates in the review queue.
            item = models.ButikkenItem.objects.filter(
                status=models.ButikkenItem.STATUS_PENDING, name__iexact=name
            ).first()
        if item is None:
            item = models.ButikkenItem.objects.create(
                name=name,
                type=models.ButikkenItem.PROPOSAL_TYPE,
                status=models.ButikkenItem.STATUS_PENDING,
                content_normal=_format_qty(quantity),
                content_unit=unit,
                description=description,
                proposed_by=user if getattr(user, "pk", None) else None,
                source_order=order,
            )
        elif item.status == models.ButikkenItem.STATUS_PENDING:
            # Enrich an existing proposal with details the first reporter omitted.
            changed = []
            if description and not item.description:
                item.description = description
                changed.append("description")
            if unit and not item.content_unit:
                item.content_unit = unit
                changed.append("content_unit")
            if changed:
                item.save(update_fields=[*changed, "last_updated"])

        _upsert_order_booking(order, item, quantity, unit, user)
        item_ids.append(item.pk)

    return item_ids


def _order_form_context(context, order=None):
    """Shared context for the create/update order form."""
    active_items = list(_active_items().order_by("name"))
    context["items"] = active_items
    context["available_items"] = [
        {"id": it.pk, "name": it.name, "unit": it.content_unit or ""}
        for it in active_items
    ]
    context["items_data"] = {
        str(it.pk): {
            "unit": it.content_unit or "",
            "normal": it.content_normal or "",
        }
        for it in active_items
    }
    context["unit_map"] = {str(it.pk): (it.content_unit or "") for it in active_items}
    context["initial_cart"] = []
    context["bookings"] = []

    if order is not None and order.pk:
        bookings = list(order.bookings.select_related("item", "team_contact"))
        context["bookings"] = bookings
        context["initial_cart"] = [
            {
                "id": str(b.item_id),
                "name": b.item.name,
                "qty": float(b.quantity),
                "unit": b.unit,
                "description": b.item.description,
                "proposal": b.item.status != models.ButikkenItem.STATUS_ACTIVE,
                "status": b.item.status,
            }
            for b in bookings
        ]
    return context


class ButikkenDashboardView(LoginRequiredMixin, generic.TemplateView):
    """Overview of meal bookings, orders and pending item proposals per team."""

    template_name = 'Butikken/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()

        active_event = Event.objects.filter(is_active=True).first()
        if active_event is None:
            active_event = (
                Event.objects.filter(start_date__gte=today)
                .order_by('start_date')
                .first()
            )

        # "Relevante dage" are the meal plans for the active event. Without an
        # event we fall back to all meal plans.
        meal_plans = models.MealPlan.objects.all()
        if active_event:
            meal_plans = meal_plans.filter(
                meal_date__range=(active_event.start_date, active_event.end_date)
            )
        meal_plans = list(meal_plans.order_by('meal_date'))

        teams = Team.objects.all().order_by('name')
        if not user.is_staff:
            teams = teams.filter(teammembership__member=user).distinct()
        teams = list(teams)
        team_ids = [team.pk for team in teams]

        meal_bookings = models.TeamMealPlan.objects.filter(
            team_id__in=team_ids,
            meal_plan_id__in=[plan.pk for plan in meal_plans],
        )
        meal_map = {
            (booking.team_id, booking.meal_plan_id): booking
            for booking in meal_bookings
        }

        orders_by_team = defaultdict(list)
        for order in models.ButikkenOrder.objects.filter(
            team_id__in=team_ids
        ).order_by('-created'):
            orders_by_team[order.team_id].append(order)

        rows = []
        for team in teams:
            meal_days = []
            missing_days = 0
            for plan in meal_plans:
                booking = meal_map.get((team.pk, plan.pk))
                if booking is None or booking.status == 'Rejected':
                    missing_days += 1
                meal_days.append({'plan': plan, 'booking': booking})

            team_orders = orders_by_team.get(team.pk, [])
            rows.append({
                'team': team,
                'meal_days': meal_days,
                'missing_days': missing_days,
                'meals_complete': bool(meal_plans) and missing_days == 0,
                'orders': team_orders,
                'order_count': len(team_orders),
                'latest_order': team_orders[0] if team_orders else None,
            })

        pending_items = []
        if user.is_staff:
            pending_items = list(
                models.ButikkenItem.objects.filter(
                    status=models.ButikkenItem.STATUS_PENDING
                ).select_related('proposed_by', 'source_order').order_by('created')
            )

        context.update({
            'rows': rows,
            'meal_plans': meal_plans,
            'active_event': active_event,
            'pending_items': pending_items,
            'pending_count': len(pending_items),
            'team_count': len(rows),
            'order_count': sum(row['order_count'] for row in rows),
            'teams_missing_meals': sum(1 for row in rows if row['missing_days']),
            'teams_without_orders': sum(1 for row in rows if not row['order_count']),
            'today': today,
        })
        return context


@login_required
@user_passes_test(lambda u: u.is_staff)
@require_POST
def review_item_proposal(request, pk):
    """Approve or reject a pending item proposal from the dashboard."""
    item = get_object_or_404(models.ButikkenItem, pk=pk)
    decision = request.POST.get('decision')

    if item.status != models.ButikkenItem.STATUS_PENDING:
        messages.warning(request, f"'{item.name}' er allerede behandlet.")
    elif decision == 'catalog':
        item.approve()
        messages.success(
            request, f"'{item.name}' er godkendt som butiksvare."
        )
    elif decision == 'special':
        item.approve_as_special()
        messages.info(
            request, f"'{item.name}' er godkendt som specialbestilling."
        )
    elif decision == 'reject':
        removed = models.ButikkenBooking.objects.filter(item=item).count()
        item.reject()
        if removed:
            messages.warning(
                request,
                f"'{item.name}' er afvist og fjernet fra "
                f"{removed} bestillingslinje(r). Teamet er underrettet.",
            )
        else:
            messages.warning(request, f"'{item.name}' er afvist.")
    else:
        messages.error(request, 'Ukendt handling.')

    return redirect('Butikken_dashboard')


class ButikkenItemListView(ItemListContextMixin, LoginRequiredMixin, generic.ListView):
    model = models.ButikkenItem
    context_object_name = 'object_list'
    ordering = ['name']

    item_list_title = "Vareoversigt"
    item_list_subtitle = "Gennemse sortimentet i butikken."
    item_list_create_url_name = "Butikken_ButikkenItem_create"
    item_list_create_label = "Tilføj vare"
    item_list_detail_url_name = "Butikken_ButikkenItem_detail"
    item_list_update_url_name = "Butikken_ButikkenItem_update"
    item_list_delete_url_name = "Butikken_ButikkenItem_delete"
    item_list_icon = "bi-shop"
    item_list_show_location = False
    item_list_empty_title = "Ingen varer fundet"
    item_list_empty_message = "Der er endnu ingen varer i butikken."

    def get_queryset(self):
        # The catalog only shows approved items; pending proposals are reviewed
        # in the admin.
        return _active_items().order_by('name')


class ButikkenItemCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.ButikkenItem
    form_class = forms.ButikkenItemForm


class ButikkenItemDetailView(ItemDetailContextMixin, LoginRequiredMixin, generic.DetailView):
    model = models.ButikkenItem
    form_class = forms.ButikkenItemForm

    item_detail_catalog_label = "Butikken"
    item_detail_list_url_name = "Butikken_ButikkenItem_list"
    item_detail_badge_label = "Vare nr."
    item_detail_icon = "bi-shop"
    item_detail_quantity_label = "Indhold"
    item_detail_footer_text = "Information fra Butikken"


class ButikkenItemUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.ButikkenItem
    form_class = forms.ButikkenItemForm
    pk_url_kwarg = "pk"


class ButikkenItemDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.ButikkenItem
    success_url = reverse_lazy("Butikken_ButikkenItem_list")


class ButikkenBookingListView(BookingListContextMixin, LoginRequiredMixin, generic.ListView):
    model = models.ButikkenBooking
    form_class = forms.ButikkenBookingForm
    context_object_name = 'object_list'
    template_name = 'Butikken/butikkenbooking_list.html'

    booking_list_title = "Butikken bookinger"
    booking_list_create_url_name = "Butikken_ButikkenBooking_create"
    booking_list_create_label = "Ny booking"
    booking_list_mobile_create_label = "Ny butiksbestilling"
    booking_list_approve_url_name = "Butikken_ButikkenBooking_approve"
    booking_list_reject_url_name = "Butikken_ButikkenBooking_reject"
    booking_list_update_url_name = "Butikken_ButikkenBooking_update"
    booking_list_delete_url_name = "Butikken_ButikkenBooking_delete"

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        queryset = models.ButikkenBooking.objects.select_related(
            'team', 'team_contact', 'item'
        )
        
        user = self.request.user
        # Filter by user's team if not staff
        if not user.is_staff:
            # Get user's team efficiently with single query
            try:
                team = user.teammembership_set.select_related('team').values_list('team', flat=True).first()
                queryset = queryset.filter(team_id=team) if team else queryset.none()
            except Exception:
                queryset = queryset.none()
        
        # Get sort parameter from GET request
        sort_by = self.request.GET.get('sort', 'item')
        
        # Validate sort parameter to prevent injection
        allowed_sorts = {
            'item': 'item__name',
            '-item': '-item__name',
            'start_date': 'start_date',
            '-start_date': '-start_date',
        }
        
        order_by = allowed_sorts.get(sort_by, 'item__name')
        return queryset.order_by(order_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Only fetch team membership once - already filtered in get_queryset
        if not user.is_staff:
            user_team_membership = user.teammembership_set.select_related('team').first()
            context['user_team_membership'] = user_team_membership
        else:
            context['user_team_membership'] = None
        
        # Add current sort parameter to context
        context['current_sort'] = self.request.GET.get('sort', 'item')
        
        return context

    def get_booking_list_subtitle(self) -> str:
        membership = self.request.user.teammembership_set.select_related('team').first()
        return f"Team: {membership.team.name}" if membership else ""

    def get_booking_list_deadline(self) -> str:
        event = Event.objects.filter(is_active=True).first()
        return str(event.deadline_mad) if event and event.deadline_mad else ""


class ButikkenBookingCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.ButikkenBooking
    form_class = forms.ButikkenBookingForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        if event and event.deadline_mad < timezone.now().date():
            messages.error(request, 'Deadline for booking overskredet')
            return redirect('Butikken_ButikkenBooking_list')  # replace with the name of your list view url
        # Enforce order-based workflow: creating a booking requires creating an order first.
        messages.info(request, 'Bookings must be created as part of an order (kurv). Opret venligst en ordre først.')
        return redirect('Butikken_ButikkenOrder_create')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        butikken_items = models.ButikkenItem.objects.all()
        
        # Use 'content_unit' instead of 'unit'
        items_data = butikken_items.values_list('id', 'content_unit')
        unit_map = {str(item_id): (u or "") for item_id, u in items_data}
        
        context['unit_map'] = unit_map
        return context


class ButikkenBookingUpdateView(TeamQuerysetMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.ButikkenBooking
    form_class = forms.ButikkenBookingForm
    pk_url_kwarg = "pk"
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        event = Event.objects.filter(is_active=True).first()
        if event and event.deadline_mad < timezone.now().date():
            messages.error(request, 'Deadline for booking overskredet')
            return redirect('Butikken_ButikkenBooking_list')  # replace with the name of your list view url
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        butikken_items = models.ButikkenItem.objects.all()
        
        # Use 'content_unit' instead of 'unit'
        items_data = butikken_items.values_list('id', 'content_unit')
        unit_map = {str(item_id): (u or "") for item_id, u in items_data}
        
        context['unit_map'] = unit_map
        return context


class ButikkenBookingDetailView(BookingDetailContextMixin, TeamQuerysetMixin, LoginRequiredMixin, generic.DetailView):
    model = models.ButikkenBooking

    booking_detail_kicker = "Butikken bestilling"
    booking_detail_list_url_name = "Butikken_ButikkenBooking_list"
    booking_detail_list_label = "Butikken bookinger"
    booking_detail_approve_url_name = "Butikken_ButikkenBooking_approve"
    booking_detail_reject_url_name = "Butikken_ButikkenBooking_reject"
    booking_detail_show_comments = False

    def get_queryset(self):
        return super().get_queryset().select_related('item', 'team', 'team_contact', 'order')

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            
            # Get the "Type" of this model so we can filter logs
            obj_type = ContentType.objects.get_for_model(self.object)
            
            # Fetch logs related to this specific object ID
            context['logs'] = LogEntry.objects.filter(
                content_type=obj_type,
                object_id=self.object.pk
            ).order_by('-action_time')
            
            return context



class ButikkenBookingDeleteView(TeamQuerysetMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.ButikkenBooking
    success_url = reverse_lazy("Butikken_ButikkenBooking_list")
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class ButikkenItemTypeListView(LoginRequiredMixin, generic.ListView):
    model = models.ButikkenItemType
    form_class = forms.ButikkenItemTypeForm


class ButikkenItemTypeCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.ButikkenItemType
    form_class = forms.ButikkenItemTypeForm


class ButikkenItemTypeDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.ButikkenItemType
    form_class = forms.ButikkenItemTypeForm


class ButikkenItemTypeUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.ButikkenItemType
    form_class = forms.ButikkenItemTypeForm
    pk_url_kwarg = "pk"


class ButikkenItemTypeDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.ButikkenItemType
    success_url = reverse_lazy("Butikken_ButikkenItemType_list")



####### Options

class OptionListView(LoginRequiredMixin, generic.ListView):
    model = models.Option
    form_class = forms.OptionForm


class OptionCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.Option
    form_class = forms.OptionForm


class OptionDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Option
    form_class = forms.OptionForm


class OptionUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.Option
    form_class = forms.OptionForm
    pk_url_kwarg = "pk"


class OptionDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.Option
    success_url = reverse_lazy("Butikken_Option_list")


###### Meal 



class MealListView(LoginRequiredMixin, generic.ListView):
    model = models.Meal
    form_class = forms.MealForm


class MealCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.Meal
    form_class = forms.MealForm


class MealDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Meal
    form_class = forms.MealForm


class MealUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.Meal
    form_class = forms.MealForm
    pk_url_kwarg = "pk"


class MealDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.Meal
    success_url = reverse_lazy("Butikken_Meal_list")


###### MealBooking


class MealBookingListView(TeamQuerysetMixin, LoginRequiredMixin, generic.ListView):
    model = models.MealBooking
    form_class = forms.MealBookingForm

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meal_plans'] = models.MealPlan.objects.all()
        return context


class MealBookingCreateView(LoginRequiredMixin, generic.CreateView):
    model = MealBooking
    form_class = forms.MealBookingForm
    template_name = 'Butikken/mealbooking_form.html'
    success_url = reverse_lazy('Butikken_MealBooking_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    

class MealBookingUpdateView(TeamQuerysetMixin, LoginRequiredMixin, generic.UpdateView):
    model = MealBooking
    form_class = forms.MealBookingForm
    template_name = 'Butikken/mealbooking_form.html'
    success_url = reverse_lazy('Butikken_MealBooking_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    

class MealBookingDetailView(TeamQuerysetMixin, LoginRequiredMixin, generic.DetailView):
    model = models.MealBooking
    form_class = forms.MealBookingForm
   
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['team_meal_plans'] = TeamMealPlan.objects.filter(meal_booking=self.object)
        return context
        

class TeamMealPlanListView(TeamQuerysetMixin, LoginRequiredMixin, generic.ListView):
    model = TeamMealPlan
    form_class = TeamMealPlanForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        print(user)
        if user.is_staff:
            context['TeamMealPlans'] = TeamMealPlan.objects.all().order_by('meal_plan__name')
        else:
            context['TeamMealPlans'] = TeamMealPlan.objects.filter(team__teammembership__member=user).order_by('meal_plan__name')
        return context
        


class TeamMealPlanCreateView(LoginRequiredMixin, generic.CreateView):
    model = TeamMealPlan
    form_class = TeamMealPlanForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['TeamMealPlans'] = TeamMealPlan.objects.all()
        return context

class TeamMealPlanDetailView(TeamQuerysetMixin, LoginRequiredMixin, generic.DetailView):
    model = TeamMealPlan
    form_class = TeamMealPlanForm


class ButikkenOrderListView(LoginRequiredMixin, generic.ListView):
    model = models.ButikkenOrder
    context_object_name = 'object_list'
    template_name = 'Butikken/butikkenorder_list.html'

    def get_queryset(self):
        qs = models.ButikkenOrder.objects.select_related('team', 'team_contact').order_by('-created')
        user = self.request.user
        if not user.is_staff:
            # limit to user's team if available
            team = user.teammembership_set.select_related('team').values_list('team', flat=True).first()
            qs = qs.filter(team_id=team) if team else qs.none()
        return qs


class ButikkenOrderCreateView(LoginRequiredMixin, generic.CreateView):
    model = models.ButikkenOrder
    form_class = forms.ButikkenOrderForm
    template_name = 'Butikken/butikkenorder_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # For create view, persist the new order and attach bookings sent in cart_items_json
        order = form.save(commit=False)
        if not self.request.user.is_staff:
            order.status = 'Afventer'
        order.save()

        # Item proposals are created first so their bookings can be kept below.
        _create_item_proposals(
            order,
            self.request.POST.get('new_items_json', '[]'),
            self.request.user,
        )

        # Persist cart items from client JSON
        cart_json = self.request.POST.get('cart_items_json', '[]')
        try:
            cart_items = json.loads(cart_json)
        except Exception:
            cart_items = []

        for ci in cart_items:
            try:
                item_id = int(ci.get('id'))
            except Exception:
                continue
            item_obj = models.ButikkenItem.objects.filter(pk=item_id).first()
            if not item_obj:
                continue
            _upsert_order_booking(
                order,
                item_obj,
                _parse_cart_qty(ci.get('qty')),
                ci.get('unit') or '',
                self.request.user,
            )

        return redirect('Butikken_ButikkenOrder_update', pk=order.pk)

    def get_context_data(self, **kwargs):
        # Provide the same context the update view expects so the single template works
        context = super().get_context_data(**kwargs)
        return _order_form_context(context)


class ButikkenOrderDetailView(TeamQuerysetMixin, LoginRequiredMixin, generic.DetailView):
    model = models.ButikkenOrder
    template_name = 'Butikken/butikkenorder_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bookings'] = self.object.bookings.select_related('item', 'team_contact')
        # Determine whether current user may edit/delete this order
        user = self.request.user
        can_edit = False
        try:
            if user.is_staff:
                can_edit = True
            else:
                # check team membership
                can_edit = user.teammembership_set.filter(team=self.object.team).exists()
        except Exception:
            can_edit = False
        context['can_edit'] = can_edit
        return context


class ButikkenOrderUpdateView(TeamQuerysetMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.ButikkenOrder
    form_class = forms.ButikkenOrderForm
    template_name = 'Butikken/butikkenorder_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure the template always has a proper form instance available
        # so template tags like `bootstrap_field` receive a valid BoundField.
        with contextlib.suppress(Exception):
            # Fallback: keep the existing form if construction fails.
            context['form'] = self.get_form()
        return _order_form_context(context, self.object)

    def form_valid(self, form):
        # Save the order fields first (enforce Pending for non-staff)
        self.object = form.save(commit=False)
        if not self.request.user.is_staff:
            self.object.status = 'Afventer'
        self.object.save()

        # Proposals are created before syncing the cart, and their bookings are
        # excluded from the "removed from cart" cleanup below.
        proposal_item_ids = _create_item_proposals(
            self.object,
            self.request.POST.get('new_items_json', '[]'),
            self.request.user,
        )

        # Process posted cart JSON (list of {id, name, qty, unit})
        cart_json = self.request.POST.get('cart_items_json', '[]')
        try:
            cart_items = json.loads(cart_json)
        except Exception:
            cart_items = []

        # Build map of item_id -> desired data (qty as Decimal)
        desired = {}
        for ci in cart_items:
            try:
                item_id = int(ci.get('id'))
            except Exception:
                continue
            desired[item_id] = {
                'qty': _parse_cart_qty(ci.get('qty')),
                'unit': ci.get('unit') or '',
            }

        # Existing bookings mapped by item id
        existing = {b.item_id: b for b in self.object.bookings.all()}

        # Create or update bookings from desired
        for item_id, data in desired.items():
            item_obj = models.ButikkenItem.objects.filter(pk=item_id).first()
            if not item_obj:
                continue
            _upsert_order_booking(
                self.object,
                item_obj,
                data['qty'],
                data['unit'],
                self.request.user,
            )
            existing.pop(item_id, None)

        # Keep bookings created for proposals in this request.
        for item_id in proposal_item_ids:
            existing.pop(item_id, None)

        # Any remaining in existing were removed from cart -> delete them
        for rem in existing.values():
            rem.delete()

        return redirect(self.get_success_url())


class ButikkenOrderDeleteView(TeamQuerysetMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.ButikkenOrder
    success_url = reverse_lazy("Butikken_ButikkenOrder_list")


class TeamMealPlanUpdateView(TeamQuerysetMixin, LoginRequiredMixin, generic.UpdateView):
    model = TeamMealPlan
    form_class = TeamMealPlanForm
    pk_url_kwarg = "pk"
    success_url = reverse_lazy("Butikken_TeamMealPlan_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['meal_plan'] = self.object.meal_plan
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meal_plan'] = self.object.meal_plan
        return context


class TeamMealPlanDeleteView(TeamQuerysetMixin, LoginRequiredMixin, generic.DeleteView):
    model = TeamMealPlan
    success_url = reverse_lazy("Butikken_TeamMealPlan_list")



#class MealBookingUpdateView(LoginRequiredMixin, generic.UpdateView):
#    model = models.MealBooking
#    form_class = forms.MealBookingForm
#    pk_url_kwarg = "pk"
#    @method_decorator(login_required)
#    def dispatch(self, request, *args, **kwargs):
#        event = Event.objects.filter(is_active=True).first()
#        if event and event.deadline_mad < timezone.now().date():
#            messages.error(request, 'Deadline for booking overskredet')
#            return redirect('Butikken_MealBooking_list')  # replace with the name of your list view url
#        return super().dispatch(request, *args, **kwargs)
#
#    def get_form_kwargs(self):
#        kwargs = super().get_form_kwargs()
#        kwargs['user'] = self.request.user
#        return kwargs


class MealBookingDeleteView(TeamQuerysetMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.MealBooking
    success_url = reverse_lazy("Butikken_MealBooking_list")




class DayListView(LoginRequiredMixin, generic.ListView):
    model = models.Day
    form_class = forms.DayForm


class DayCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.Day
    form_class = forms.DayForm


class DayDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Day
    form_class = forms.DayForm


class DayUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.Day
    form_class = forms.DayForm
    pk_url_kwarg = "pk"


class DayDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.Day
    success_url = reverse_lazy("Butikken_Day_list")


class RecipeListView(LoginRequiredMixin, generic.ListView):
    model = models.Recipe
    form_class = forms.RecipeForm


class RecipeCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.Recipe
    form_class = forms.RecipeForm


class RecipeDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.Recipe
    form_class = forms.RecipeForm


class RecipeUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.Recipe
    form_class = forms.RecipeForm
    pk_url_kwarg = "pk"


class RecipeDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.Recipe
    success_url = reverse_lazy("Butikken_Recipe_list")



@login_required
def bulk_meal_update(request):
    user = request.user
    
    # 1. Use the same filtering logic as your list
    if user.is_staff:
        queryset = TeamMealPlan.objects.all()
    else:
        queryset = TeamMealPlan.objects.filter(team__teammembership__member=user)
    
    # 2. Add select_related to prevent 'NoneType' errors and optimize DB hits
    queryset = queryset.select_related('meal_plan', 'meal_option', 'team').order_by('meal_plan__meal_date')

    MealFormSet = modelformset_factory(
        TeamMealPlan, 
        form=BulkMealForm, 
        extra=0
    )

    if request.method == 'POST':
        # Pass the EXACT same queryset to the POST handler
        formset = MealFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            formset.save()
            return redirect('Butikken_TeamMealPlan_list')
        else:
            # Print errors to terminal so you can see them in 'docker logs'
            print(formset.errors)
    else:
        formset = MealFormSet(queryset=queryset)

    return render(request, 'Butikken/meal_bulk_edit.html', {'formset': formset})


