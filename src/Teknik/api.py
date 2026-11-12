from rest_framework import viewsets

from organization.permissions import (
    IsStaffOrReadOnly,
    IsStaffOrTeamMember,
    TeamScopedMixin,
)

from . import models, serializers


class TeknikBookingViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.TeknikBooking.objects.all()
    serializer_class = serializers.TeknikBookingSerializer
    permission_classes = [IsStaffOrTeamMember]


class TeknikItemViewSet(viewsets.ModelViewSet):
    queryset = models.TeknikItem.objects.all()
    serializer_class = serializers.TeknikItemSerializer
    permission_classes = [IsStaffOrReadOnly]


class TeknikTypeViewSet(viewsets.ModelViewSet):
    queryset = models.TeknikType.objects.all()
    serializer_class = serializers.TeknikTypeSerializer
    permission_classes = [IsStaffOrReadOnly]
