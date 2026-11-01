from django.urls import include, path
from rest_framework import routers

from . import api, views

router = routers.DefaultRouter()
router.register("TeknikBooking", api.TeknikBookingViewSet)
router.register("TeknikItem", api.TeknikItemViewSet)
router.register("TeknikType", api.TeknikTypeViewSet)

urlpatterns = (
    path("api/v1/", include(router.urls)),
    path("Teknik/TeknikBooking/", views.TeknikBookingListView.as_view(), name="Teknik_TeknikBooking_list"),
    path("Teknik/TeknikBooking/create/", views.TeknikBookingCreateView.as_view(), name="Teknik_TeknikBooking_create"),
    path("Teknik/TeknikBooking/create/<int:item_id>/", views.TeknikBookingCreateView.as_view(), name="Teknik_TeknikBooking_create_with_item"),
    path("Teknik/TeknikBooking/detail/<int:pk>/", views.TeknikBookingDetailView.as_view(), name="Teknik_TeknikBooking_detail"),
    path("Teknik/TeknikBooking/update/<int:pk>/", views.TeknikBookingUpdateView.as_view(), name="Teknik_TeknikBooking_update"),
    path("Teknik/TeknikBooking/delete/<int:pk>/", views.TeknikBookingDeleteView.as_view(), name="Teknik_TeknikBooking_delete"),

    path("Teknik/TeknikBooking/approve/<int:pk>/", views.approve_booking, name="Teknik_TeknikBooking_approve"),
    path("Teknik/TeknikBooking/reject/<int:pk>/", views.reject_booking, name="Teknik_TeknikBooking_reject"),


    path("Teknik/TeknikItem/", views.TeknikItemListView.as_view(), name="Teknik_TeknikItem_list"),
    path("Teknik/TeknikItem/create/", views.TeknikItemCreateView.as_view(), name="Teknik_TeknikItem_create"),
    path("Teknik/TeknikItem/detail/<int:pk>/", views.TeknikItemDetailView.as_view(), name="Teknik_TeknikItem_detail"),
    path("Teknik/TeknikItem/update/<int:pk>/", views.TeknikItemUpdateView.as_view(), name="Teknik_TeknikItem_update"),
    path("Teknik/TeknikItem/delete/<int:pk>/", views.TeknikItemDeleteView.as_view(), name="Teknik_TeknikItem_delete"),

    path("Teknik/TeknikType/", views.TeknikTypeListView.as_view(), name="Teknik_TeknikType_list"),
    path("Teknik/TeknikType/create/", views.TeknikTypeCreateView.as_view(), name="Teknik_TeknikType_create"),
    path("Teknik/TeknikType/detail/<int:pk>/", views.TeknikTypeDetailView.as_view(), name="Teknik_TeknikType_detail"),
    path("Teknik/TeknikType/update/<int:pk>/", views.TeknikTypeUpdateView.as_view(), name="Teknik_TeknikType_update"),
    path("Teknik/TeknikType/delete/<int:pk>/", views.TeknikTypeDeleteView.as_view(), name="Teknik_TeknikType_delete"),

)


