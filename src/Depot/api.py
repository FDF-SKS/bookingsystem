from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from .models import DepotBooking, DepotItem
from .serializers import DepotBookingSerializer, DepotItemSerializer
from organization.permissions import (
    IsStaffOrReadOnly,
    IsStaffOrTeamMember,
    TeamScopedMixin,
)


class DepotItemViewSet(viewsets.ModelViewSet):
    """API viewset for Depot Items (staff-only mutation)."""
    queryset = DepotItem.objects.all()
    serializer_class = DepotItemSerializer
    permission_classes = [IsStaffOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created', 'quantity']
    ordering = ['name']


class DepotBookingViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    """API viewset for Depot Bookings, scoped to the user's teams."""
    queryset = DepotBooking.objects.select_related('item', 'team', 'team_contact')
    serializer_class = DepotBookingSerializer
    permission_classes = [IsStaffOrTeamMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['item', 'team', 'status']
    search_fields = ['item__name', 'team__name', 'team_contact__name']
    ordering_fields = ['created_at', 'start', 'status']
    ordering = ['-created_at']
