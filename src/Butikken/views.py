import contextlib
import json
import logging
from datetime import time
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.forms import modelformset_factory
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import generic

from organization.models import Event
from organization.permissions import StaffRequiredMixin, TeamQuerysetMixin

from . import forms, models
from .forms import BulkMealForm, TeamMealPlanForm
from .models import MealBooking, TeamMealPlan

logger = logging.getLogger(__name__)


class ButikkenItemListView(LoginRequiredMixin, generic.ListView):
    model = models.ButikkenItem
    context_object_name = 'object_list'
    ordering = ['name']

    def get_queryset(self):
        queryset = models.ButikkenItem.objects.all().order_by('name')  # Order by the 'name' field
        return queryset


class ButikkenItemCreateView(StaffRequiredMixin, LoginRequiredMixin, generic.CreateView):
    model = models.ButikkenItem
    form_class = forms.ButikkenItemForm


class ButikkenItemDetailView(LoginRequiredMixin, generic.DetailView):
    model = models.ButikkenItem
    form_class = forms.ButikkenItemForm


class ButikkenItemUpdateView(StaffRequiredMixin, LoginRequiredMixin, generic.UpdateView):
    model = models.ButikkenItem
    form_class = forms.ButikkenItemForm
    pk_url_kwarg = "pk"


class ButikkenItemDeleteView(StaffRequiredMixin, LoginRequiredMixin, generic.DeleteView):
    model = models.ButikkenItem
    success_url = reverse_lazy("Butikken_ButikkenItem_list")


class ButikkenBookingListView(LoginRequiredMixin, generic.ListView):
    model = models.ButikkenBooking
    form_class = forms.ButikkenBookingForm
    context_object_name = 'object_list'
    template_name = 'Butikken/butikkenbooking_list.html'

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


class ButikkenBookingDetailView(TeamQuerysetMixin, LoginRequiredMixin, generic.DetailView):
    model = models.ButikkenBooking
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

        # Persist cart items from client JSON
        cart_json = self.request.POST.get('cart_items_json', '[]')
        try:
            cart_items = json.loads(cart_json)
        except Exception:
            cart_items = []

        from .models import ButikkenBooking, ButikkenItem
        for ci in cart_items:
            try:
                item_id = int(ci.get('id'))
            except Exception:
                continue
            # Parse quantity as Decimal, tolerant to commas and invalid input
            qty_raw = ci.get('qty')
            try:
                qty = Decimal(str(qty_raw)) if qty_raw is not None else Decimal('1')
            except (InvalidOperation, TypeError, ValueError):
                try:
                    qty = Decimal(str(qty_raw).replace(',', '.'))
                except Exception:
                    qty = Decimal('1')
            unit = ci.get('unit') or ''
            item_obj = ButikkenItem.objects.filter(pk=item_id).first()
            if not item_obj:
                continue
            start_date = order.pickup_date or timezone.now().date()
            start_time = time(8, 0)
            ButikkenBooking.objects.create(
                order=order,
                item=item_obj,
                team=order.team,
                team_contact=(order.team_contact or self.request.user),
                start_date=start_date,
                start_time=start_time,
                quantity=qty,
                unit=(unit or item_obj.content_unit or ''),
            )

        return redirect('Butikken_ButikkenOrder_update', pk=order.pk)

    def get_context_data(self, **kwargs):
        # Provide the same context the update view expects so the single template works
        context = super().get_context_data(**kwargs)
        from .models import ButikkenItem
        context['items'] = ButikkenItem.objects.all()
        context['bookings'] = []
        items_qs = ButikkenItem.objects.all().values('id', 'content_unit', 'content_normal')
        items_data = {str(i['id']): {'unit': i['content_unit'] or '', 'normal': i['content_normal'] or ''} for i in items_qs}
        context['items_data'] = items_data
        context['available_items'] = [
            {'id': it.pk, 'name': it.name, 'unit': it.content_unit or ''}
            for it in ButikkenItem.objects.all()
        ]
        context['unit_map'] = {str(it.pk): (it.content_unit or '') for it in ButikkenItem.objects.all()}
        context['initial_cart'] = []
        return context


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
        from .models import ButikkenItem
        context['items'] = ButikkenItem.objects.all()
        context['bookings'] = self.object.bookings.select_related('item', 'team_contact')
        # Provide items metadata (unit and normal quantity) as JSON-friendly dict
        items_qs = ButikkenItem.objects.all().values('id', 'content_unit', 'content_normal')
        items_data = {str(i['id']): {'unit': i['content_unit'] or '', 'normal': i['content_normal'] or ''} for i in items_qs}
        context['items_data'] = items_data
        # Provide available_items for the template (id, name, unit)
        context['available_items'] = [
            {'id': it.pk, 'name': it.name, 'unit': it.content_unit or ''}
            for it in ButikkenItem.objects.all()
        ]
        # unit_map for older templates that expect it
        context['unit_map'] = {str(it.pk): (it.content_unit or '') for it in ButikkenItem.objects.all()}
        # Initial cart items based on existing bookings (id=item.id)
        initial_cart = []
        for b in context['bookings']:
            initial_cart.append({'id': str(b.item.pk), 'name': b.item.name, 'qty': int(b.quantity), 'unit': b.unit})
        context['initial_cart'] = initial_cart
        return context

    def form_valid(self, form):
        # Save the order fields first (enforce Pending for non-staff)
        self.object = form.save(commit=False)
        if not self.request.user.is_staff:
            self.object.status = 'Afventer'
        self.object.save()

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
            qty_raw = ci.get('qty')
            try:
                qty = Decimal(str(qty_raw)) if qty_raw is not None else Decimal('1')
            except (InvalidOperation, TypeError, ValueError):
                try:
                    qty = Decimal(str(qty_raw).replace(',', '.'))
                except Exception:
                    qty = Decimal('1')
            unit = ci.get('unit') or ''
            desired[item_id] = {'qty': qty, 'unit': unit}

        # Existing bookings mapped by item id
        existing = {b.item_id: b for b in self.object.bookings.all()}

        # Create or update bookings from desired
        from .models import ButikkenBooking, ButikkenItem
        for item_id, data in desired.items():
            item_obj = ButikkenItem.objects.filter(pk=item_id).first()
            if not item_obj:
                continue
            if item_id in existing:
                b = existing[item_id]
                b.quantity = data['qty']
                b.unit = data['unit'] or b.unit
                # ensure start_date/time exist
                if not b.start_date:
                    b.start_date = self.object.pickup_date or timezone.now().date()
                if not b.start_time:
                    b.start_time = time(8, 0)
                b.save()
                del existing[item_id]
            else:
                ButikkenBooking.objects.create(
                    order=self.object,
                    item=item_obj,
                    team=self.object.team,
                    team_contact=(self.object.team_contact or self.request.user),
                    start_date=(self.object.pickup_date or timezone.now().date()),
                    start_time=time(8, 0),
                    quantity=data['qty'],
                    unit=(data['unit'] or item_obj.content_unit or ''),
                )

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


