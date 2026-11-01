from django.urls import include, path
from rest_framework import routers

from . import api, views

router = routers.DefaultRouter()
router.register("SjakItem", api.SjakItemViewSet)
router.register("SjakBooking", api.SjakBookingViewSet)
router.register("SjakItemType", api.SjakItemTypeViewSet)

urlpatterns = [
    path("api/v1/", include(router.urls)),
    path("Sjak/SjakItem/", views.SjakItemListView.as_view(), name="Sjak_SjakItem_list"),
    path("Sjak/SjakItem/create/", views.SjakItemCreateView.as_view(), name="Sjak_SjakItem_create"),
    path("Sjak/SjakItem/detail/<int:pk>/", views.SjakItemDetailView.as_view(), name="Sjak_SjakItem_detail"),
    path("Sjak/SjakItem/update/<int:pk>/", views.SjakItemUpdateView.as_view(), name="Sjak_SjakItem_update"),
    path("Sjak/SjakItem/delete/<int:pk>/", views.SjakItemDeleteView.as_view(), name="Sjak_SjakItem_delete"),

    path("Sjak/SjakBooking/", views.SjakBookingListView.as_view(), name="Sjak_SjakBooking_list"),
    path("Sjak/SjakBooking/kanban/", views.SjakKanbanView.as_view(), name="Sjak_SjakBooking_kanban"),
    path("Sjak/SjakBooking/create/", views.SjakBookingCreateView.as_view(), name="Sjak_SjakBooking_create"),
    path("Sjak/SjakBooking/create/<int:item_id>/", views.SjakBookingCreateView.as_view(), name="Sjak_SjakBooking_create_with_item"),
    path("Sjak/SjakBooking/detail/<int:pk>/", views.SjakBookingDetailView.as_view(), name="Sjak_SjakBooking_detail"),
    path("Sjak/SjakBooking/update/<int:pk>/", views.SjakBookingUpdateView.as_view(), name="Sjak_SjakBooking_update"),
    path("Sjak/SjakBooking/delete/<int:pk>/", views.SjakBookingDeleteView.as_view(), name="Sjak_SjakBooking_delete"),
    path("Sjak/SjakBooking/approve/<int:pk>/", views.approve_booking, name="Sjak_SjakBooking_approve"),
    path("Sjak/SjakBooking/reject/<int:pk>/", views.reject_booking, name="Sjak_SjakBooking_reject"),
    path("Sjak/SjakBooking/status/<int:pk>/", views.update_booking_status, name="Sjak_SjakBooking_update_status"),
    path("Sjak/SjakBooking/field/<int:pk>/", views.update_booking_field, name="Sjak_SjakBooking_update_field"),
  
    path("Sjak/SjakItemType/", views.SjakItemTypeListView.as_view(), name="Sjak_SjakItemType_list"),
    path("Sjak/SjakItemType/create/", views.SjakItemTypeCreateView.as_view(), name="Sjak_SjakItemType_create"),
    path("Sjak/SjakItemType/detail/<int:pk>/", views.SjakItemTypeDetailView.as_view(), name="Sjak_SjakItemType_detail"),
    path("Sjak/SjakItemType/update/<int:pk>/", views.SjakItemTypeUpdateView.as_view(), name="Sjak_SjakItemType_update"),
    path("Sjak/SjakItemType/delete/<int:pk>/", views.SjakItemTypeDeleteView.as_view(), name="Sjak_SjakItemType_delete"),
]



