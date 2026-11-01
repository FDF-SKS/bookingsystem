from django.urls import include, path
from rest_framework import routers

from . import api, views

router = routers.DefaultRouter()
router.register("SOSBooking", api.SOSBookingViewSet)
router.register("SOSItem", api.SOSItemViewSet)
router.register("SOSType", api.SOSTypeViewSet)

urlpatterns = (
    path("api/v1/", include(router.urls)),
    path("SOS/SOSBooking/", views.SOSBookingListView.as_view(), name="SOS_SOSBooking_list"),
    path("SOS/SOSBooking/create/", views.SOSBookingCreateView.as_view(), name="SOS_SOSBooking_create"),
    path("SOS/SOSBooking/detail/<int:pk>/", views.SOSBookingDetailView.as_view(), name="SOS_SOSBooking_detail"),
    path("SOS/SOSBooking/update/<int:pk>/", views.SOSBookingUpdateView.as_view(), name="SOS_SOSBooking_update"),
    path("SOS/SOSBooking/delete/<int:pk>/", views.SOSBookingDeleteView.as_view(), name="SOS_SOSBooking_delete"),
    path("SOS/SOSItem/", views.SOSItemListView.as_view(), name="SOS_SOSItem_list"),
    path("SOS/SOSItem/create/", views.SOSItemCreateView.as_view(), name="SOS_SOSItem_create"),
    path("SOS/SOSItem/detail/<int:pk>/", views.SOSItemDetailView.as_view(), name="SOS_SOSItem_detail"),
    path("SOS/SOSItem/update/<int:pk>/", views.SOSItemUpdateView.as_view(), name="SOS_SOSItem_update"),
    path("SOS/SOSItem/delete/<int:pk>/", views.SOSItemDeleteView.as_view(), name="SOS_SOSItem_delete"),
    path("SOS/SOSType/", views.SOSTypeListView.as_view(), name="SOS_SOSType_list"),
    path("SOS/SOSType/create/", views.SOSTypeCreateView.as_view(), name="SOS_SOSType_create"),
    path("SOS/SOSType/detail/<int:pk>/", views.SOSTypeDetailView.as_view(), name="SOS_SOSType_detail"),
    path("SOS/SOSType/update/<int:pk>/", views.SOSTypeUpdateView.as_view(), name="SOS_SOSType_update"),
    path("SOS/SOSType/delete/<int:pk>/", views.SOSTypeDeleteView.as_view(), name="SOS_SOSType_delete"),

)


