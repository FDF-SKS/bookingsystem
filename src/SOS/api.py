from rest_framework import viewsets

from . import models, serializers
from organization.permissions import (
    IsStaffOrReadOnly,
    IsStaffOrTeamMember,
    TeamScopedMixin,
)


class SOSBookingViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.SOSBooking.objects.all()
    serializer_class = serializers.SOSBookingSerializer
    permission_classes = [IsStaffOrTeamMember]


class SOSItemViewSet(viewsets.ModelViewSet):
    queryset = models.SOSItem.objects.all()
    serializer_class = serializers.SOSItemSerializer
    permission_classes = [IsStaffOrReadOnly]


class SOSTypeViewSet(viewsets.ModelViewSet):
    queryset = models.SOSType.objects.all()
    serializer_class = serializers.SOSTypeSerializer
    permission_classes = [IsStaffOrReadOnly]
