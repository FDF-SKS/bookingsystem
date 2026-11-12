from rest_framework import viewsets

from organization.permissions import (
    IsStaffOrReadOnly,
    IsStaffOrTeamMember,
    TeamScopedMixin,
)

from . import models, serializers


class AktivitetsTeamItemViewSet(viewsets.ModelViewSet):
    queryset = models.AktivitetsTeamItem.objects.all()
    serializer_class = serializers.AktivitetsTeamItemSerializer
    permission_classes = [IsStaffOrReadOnly]


class AktivitetsTeamBookingViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.AktivitetsTeamBooking.objects.all()
    serializer_class = serializers.AktivitetsTeamBookingSerializer
    permission_classes = [IsStaffOrTeamMember]
