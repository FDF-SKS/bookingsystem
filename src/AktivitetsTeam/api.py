from rest_framework import permissions, viewsets

from . import models, serializers


class AktivitetsTeamItemViewSet(viewsets.ModelViewSet):
    """ViewSet for the AktivitetsTeamItem class"""

    queryset = models.AktivitetsTeamItem.objects.all()
    serializer_class = serializers.AktivitetsTeamItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class AktivitetsTeamBookingViewSet(viewsets.ModelViewSet):
    """ViewSet for the AktivitetsTeamBooking class"""

    queryset = models.AktivitetsTeamBooking.objects.all()
    serializer_class = serializers.AktivitetsTeamBookingSerializer
    permission_classes = [permissions.IsAuthenticated]


