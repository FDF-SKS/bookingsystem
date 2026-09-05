from django.urls import path, include
from rest_framework import routers

from . import api
from . import views


router = routers.DefaultRouter()
router.register("AktivitetsTeamItem", api.AktivitetsTeamItemViewSet)
router.register("AktivitetsTeamBooking", api.AktivitetsTeamBookingViewSet)

urlpatterns = (
    path("api/v1/", include(router.urls)),
    path("AktivitetsTeam/AktivitetsTeamItem/", views.AktivitetsTeamItemListView.as_view(), name="AktivitetsTeam_AktivitetsTeamItem_list"),
    path("AktivitetsTeam/AktivitetsTeamItem/create/", views.AktivitetsTeamItemCreateView.as_view(), name="AktivitetsTeam_AktivitetsTeamItem_create"),
    path("AktivitetsTeam/AktivitetsTeamItem/detail/<int:pk>/", views.AktivitetsTeamItemDetailView.as_view(), name="AktivitetsTeam_AktivitetsTeamItem_detail"),
    path("AktivitetsTeam/AktivitetsTeamItem/update/<int:pk>/", views.AktivitetsTeamItemUpdateView.as_view(), name="AktivitetsTeam_AktivitetsTeamItem_update"),
    path("AktivitetsTeam/AktivitetsTeamItem/delete/<int:pk>/", views.AktivitetsTeamItemDeleteView.as_view(), name="AktivitetsTeam_AktivitetsTeamItem_delete"),

    path("AktivitetsTeam/AktivitetsTeamBooking/", views.AktivitetsTeamBookingListView.as_view(), 
    name="AktivitetsTeam_AktivitetsTeamBooking_list"),
    path("AktivitetsTeam/AktivitetsTeamBooking/mine/", views.AktivitetsTeamBookingTeamListView.as_view(), name="AktivitetsTeam_AktivitetsTeamBooking_mine"),
    path("AktivitetsTeam/AktivitetsTeamBooking/create/", views.AktivitetsTeamBookingCreateView.as_view(), name="AktivitetsTeam_AktivitetsTeamBooking_create"),
    path("AktivitetsTeam/AktivitetsTeamBooking/create/<int:item_id>/", views.AktivitetsTeamBookingCreateView.as_view(), name="AktivitetsTeam_AktivitetsTeamBooking_create_with_item"),
    path("AktivitetsTeam/AktivitetsTeamBooking/detail/<int:pk>/", views.AktivitetsTeamBookingDetailView.as_view(), name="AktivitetsTeam_AktivitetsTeamBooking_detail"),
    path("AktivitetsTeam/AktivitetsTeamBooking/update/<int:pk>/", views.AktivitetsTeamBookingUpdateView.as_view(), name="AktivitetsTeam_AktivitetsTeamBooking_update"),
    path("AktivitetsTeam/AktivitetsTeamBooking/delete/<int:pk>/", views.AktivitetsTeamBookingDeleteView.as_view(), name="AktivitetsTeam_AktivitetsTeamBooking_delete"),
    path("AktivitetsTeam/AktivitetsTeamBooking/approve/<int:pk>/", views.approve_booking, name="AktivitetsTeam_AktivitetsTeamBooking_approve"),
    path("AktivitetsTeam/AktivitetsTeamBooking/reject/<int:pk>/", views.reject_booking, name="AktivitetsTeam_AktivitetsTeamBooking_reject"),
    

)


