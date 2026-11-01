from rest_framework import permissions, viewsets

from . import models, serializers


class SOSBookingViewSet(viewsets.ModelViewSet):
    """ViewSet for the SOSBooking class"""

    queryset = models.SOSBooking.objects.all()
    serializer_class = serializers.SOSBookingSerializer
    permission_classes = [permissions.IsAuthenticated]


class SOSItemViewSet(viewsets.ModelViewSet):
    """ViewSet for the SOSItem class"""

    queryset = models.SOSItem.objects.all()
    serializer_class = serializers.SOSItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class SOSTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for the SOSType class"""

    queryset = models.SOSType.objects.all()
    serializer_class = serializers.SOSTypeSerializer
    permission_classes = [permissions.IsAuthenticated]


