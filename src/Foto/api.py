from rest_framework import viewsets

from . import models, serializers
from organization.permissions import (
    IsStaffOrReadOnly,
    IsStaffOrTeamMember,
    TeamScopedMixin,
)


class FotoItemViewSet(viewsets.ModelViewSet):
    queryset = models.FotoItem.objects.all()
    serializer_class = serializers.FotoItemSerializer
    permission_classes = [IsStaffOrReadOnly]


class FotoBookingViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.FotoBooking.objects.all()
    serializer_class = serializers.FotoBookingSerializer
    permission_classes = [IsStaffOrTeamMember]
