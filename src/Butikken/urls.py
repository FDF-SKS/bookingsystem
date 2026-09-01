from django.urls import path, include
from rest_framework import routers

from . import api
from . import views


router = routers.DefaultRouter()
router.register("Day", api.DayViewSet)
router.register("Recipe", api.RecipeViewSet)
router.register("ButikkenItemType", api.ButikkenItemTypeViewSet)
router.register("Meal", api.MealViewSet)
router.register("Option", api.OptionViewSet)
router.register("ButikkenItem", api.ButikkenItemViewSet)
router.register("ButikkenBooking", api.ButikkenBookingViewSet)
router.register("ButikkenOrder", api.ButikkenOrderViewSet)
router.register("MealBooking", api.MealBookingViewSet)
router.register("TeamMealPlan", api.TeamMealPlanViewSet)

urlpatterns = (
    path("api/v1/", include(router.urls)),
    path("Butikken/ButikkenItem/", views.ButikkenItemListView.as_view(), name="Butikken_ButikkenItem_list"),
    path("Butikken/ButikkenItem/create/", views.ButikkenItemCreateView.as_view(), name="Butikken_ButikkenItem_create"),
    path("Butikken/ButikkenItem/detail/<int:pk>/", views.ButikkenItemDetailView.as_view(), name="Butikken_ButikkenItem_detail"),
    path("Butikken/ButikkenItem/update/<int:pk>/", views.ButikkenItemUpdateView.as_view(), name="Butikken_ButikkenItem_update"),
    path("Butikken/ButikkenItem/delete/<int:pk>/", views.ButikkenItemDeleteView.as_view(), name="Butikken_ButikkenItem_delete"),

    path("Butikken/ButikkenBooking/", views.ButikkenBookingListView.as_view(), name="Butikken_ButikkenBooking_list"),
    #path("Butikken/ButikkenBooking/createNew/", views.create_butikken_booking, name="Butikken_ButikkenBooking_create_new"),
    path("Butikken/ButikkenBooking/create/", views.ButikkenBookingCreateView.as_view(), name="Butikken_ButikkenBooking_create"),
    path("Butikken/ButikkenBooking/detail/<int:pk>/", views.ButikkenBookingDetailView.as_view(), name="Butikken_ButikkenBooking_detail"),
    path("Butikken/ButikkenBooking/update/<int:pk>/", views.ButikkenBookingUpdateView.as_view(), name="Butikken_ButikkenBooking_update"),
    path("Butikken/ButikkenBooking/delete/<int:pk>/", views.ButikkenBookingDeleteView.as_view(), name="Butikken_ButikkenBooking_delete"),

    # Butikken Order (cart) URLs
    path("Butikken/ButikkenOrder/", views.ButikkenOrderListView.as_view(), name="Butikken_ButikkenOrder_list"),
    path("Butikken/ButikkenOrder/create/", views.ButikkenOrderCreateView.as_view(), name="Butikken_ButikkenOrder_create"),
    path("Butikken/ButikkenOrder/detail/<int:pk>/", views.ButikkenOrderDetailView.as_view(), name="Butikken_ButikkenOrder_detail"),
    path("Butikken/ButikkenOrder/update/<int:pk>/", views.ButikkenOrderUpdateView.as_view(), name="Butikken_ButikkenOrder_update"),
    path("Butikken/ButikkenOrder/delete/<int:pk>/", views.ButikkenOrderDeleteView.as_view(), name="Butikken_ButikkenOrder_delete"),
    path("Butikken/ButikkenOrder/<int:pk>/add-item/", views.butikken_order_add_item, name="Butikken_ButikkenOrder_add_item"),
    path("Butikken/ButikkenOrder/<int:order_pk>/remove-item/<int:pk>/", views.butikken_order_remove_item, name="Butikken_ButikkenOrder_remove_item"),

    path("Butikken/ButikkenItemType/", views.ButikkenItemTypeListView.as_view(), name="Butikken_ButikkenItemType_list"),
    path("Butikken/ButikkenItemType/create/", views.ButikkenItemTypeCreateView.as_view(), name="Butikken_ButikkenItemType_create"),
    path("Butikken/ButikkenItemType/detail/<int:pk>/", views.ButikkenItemTypeDetailView.as_view(), name="Butikken_ButikkenItemType_detail"),
    path("Butikken/ButikkenItemType/update/<int:pk>/", views.ButikkenItemTypeUpdateView.as_view(), name="Butikken_ButikkenItemType_update"),
    path("Butikken/ButikkenItemType/delete/<int:pk>/", views.ButikkenItemTypeDeleteView.as_view(), name="Butikken_ButikkenItemType_delete"),

    path("Butikken/Day/", views.DayListView.as_view(), name="Butikken_Day_list"),
    path("Butikken/Day/create/", views.DayCreateView.as_view(), name="Butikken_Day_create"),
    path("Butikken/Day/detail/<int:pk>/", views.DayDetailView.as_view(), name="Butikken_Day_detail"),
    path("Butikken/Day/update/<int:pk>/", views.DayUpdateView.as_view(), name="Butikken_Day_update"),
    path("Butikken/Day/delete/<int:pk>/", views.DayDeleteView.as_view(), name="Butikken_Day_delete"),

    path("Butikken/Recipe/", views.RecipeListView.as_view(), name="Butikken_Recipe_list"),
    path("Butikken/Recipe/create/", views.RecipeCreateView.as_view(), name="Butikken_Recipe_create"),
    path("Butikken/Recipe/detail/<int:pk>/", views.RecipeDetailView.as_view(), name="Butikken_Recipe_detail"),
    path("Butikken/Recipe/update/<int:pk>/", views.RecipeUpdateView.as_view(), name="Butikken_Recipe_update"),
    path("Butikken/Recipe/delete/<int:pk>/", views.RecipeDeleteView.as_view(), name="Butikken_Recipe_delete"),

    path("Butikken/Meal/", views.MealListView.as_view(), name="Butikken_Meal_list"),
    path("Butikken/Meal/create/", views.MealCreateView.as_view(), name="Butikken_Meal_create"),
    path("Butikken/Meal/detail/<int:pk>/", views.MealDetailView.as_view(), name="Butikken_Meal_detail"),
    path("Butikken/Meal/update/<int:pk>/", views.MealUpdateView.as_view(), name="Butikken_Meal_update"),
    path("Butikken/Meal/delete/<int:pk>/", views.MealDeleteView.as_view(), name="Butikken_Meal_delete"),

    path("Butikken/Option/", views.OptionListView.as_view(), name="Butikken_Option_list"),
    path("Butikken/Option/create/", views.OptionCreateView.as_view(), name="Butikken_Option_create"),
    path("Butikken/Option/detail/<int:pk>/", views.OptionDetailView.as_view(), name="Butikken_Option_detail"),
    path("Butikken/Option/update/<int:pk>/", views.OptionUpdateView.as_view(), name="Butikken_Option_update"),
    path("Butikken/Option/delete/<int:pk>/", views.OptionDeleteView.as_view(), name="Butikken_Option_delete"),


    path("Butikken/MealBooking/", views.MealBookingListView.as_view(), name="Butikken_MealBooking_list"),
    path("Butikken/MealBooking/create/", views.MealBookingCreateView.as_view(), name="Butikken_MealBooking_create"),
    path("Butikken/MealBooking/detail/<int:pk>/", views.MealBookingDetailView.as_view(), name="Butikken_MealBooking_detail"),
    path("Butikken/MealBooking/update/<int:pk>/", views.MealBookingUpdateView.as_view(), name="Butikken_MealBooking_update"),
    path("Butikken/MealBooking/delete/<int:pk>/", views.MealBookingDeleteView.as_view(), name="Butikken_MealBooking_delete"),

    path("Butikken/TeamMealPlan/", views.TeamMealPlanListView.as_view(), name="Butikken_TeamMealPlan_list"),
    path("Butikken/TeamMealPlan/bulk-update/", views.bulk_meal_update, name="Butikken_TeamMealPlan_bulk_update"), # NEW
    path("Butikken/TeamMealPlan/create/", views.TeamMealPlanCreateView.as_view(), name="Butikken_TeamMealPlan_create"),
    path("Butikken/TeamMealPlan/detail/<int:pk>/", views.TeamMealPlanDetailView.as_view(), name="Butikken_TeamMealPlan_detail"),
    path("Butikken/TeamMealPlan/update/<int:pk>/", views.TeamMealPlanUpdateView.as_view(), name="Butikken_TeamMealPlan_update"),
    path("Butikken/TeamMealPlan/delete/<int:pk>/", views.TeamMealPlanDeleteView.as_view(), name="Butikken_TeamMealPlan_delete"),

)


