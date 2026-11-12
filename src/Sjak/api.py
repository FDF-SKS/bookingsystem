from rest_framework import viewsets

from organization.permissions import (
    IsStaffOrReadOnly,
    IsStaffOrTeamMember,
    TeamScopedMixin,
)

from . import models, serializers


class SjakItemViewSet(viewsets.ModelViewSet):
    queryset = models.SjakItem.objects.all()
    serializer_class = serializers.SjakItemSerializer
    permission_classes = [IsStaffOrReadOnly]


class SjakBookingViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.SjakBooking.objects.all()
    serializer_class = serializers.SjakBookingSerializer
    permission_classes = [IsStaffOrTeamMember]


class SjakItemTypeViewSet(viewsets.ModelViewSet):
    queryset = models.SjakItemType.objects.all()
    serializer_class = serializers.SjakItemTypeSerializer
    permission_classes = [IsStaffOrReadOnly]
