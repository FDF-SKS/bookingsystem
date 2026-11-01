from django.urls import path

from . import views

urlpatterns = [
    # Depot Items
    path('items/', views.DepotItemListView.as_view(), name='Depot_DepotItem_list'),
    path('items/<int:pk>/', views.DepotItemDetailView.as_view(), name='Depot_DepotItem_detail'),
    path('items/new/', views.DepotItemCreateView.as_view(), name='Depot_DepotItem_create'),
    path('items/<int:pk>/edit/', views.DepotItemUpdateView.as_view(), name='Depot_DepotItem_update'),
    path('items/<int:pk>/delete/', views.DepotItemDeleteView.as_view(), name='Depot_DepotItem_delete'),
    
    # Depot Bookings
    path('bookings/', views.DepotBookingListView.as_view(), name='Depot_DepotBooking_list'),
    path('bookings/<int:pk>/', views.DepotBookingDetailView.as_view(), name='Depot_DepotBooking_detail'),
    path('bookings/new/', views.DepotBookingCreateView.as_view(), name='Depot_DepotBooking_create'),
    path('bookings/<int:pk>/edit/', views.DepotBookingUpdateView.as_view(), name='Depot_DepotBooking_update'),
    path('bookings/<int:pk>/delete/', views.DepotBookingDeleteView.as_view(), name='Depot_DepotBooking_delete'),
]


