from rest_framework import permissions, viewsets

from . import models, serializers


class SjakItemViewSet(viewsets.ModelViewSet):
    """ViewSet for the SjakItem class"""

    queryset = models.SjakItem.objects.all()
    serializer_class = serializers.SjakItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class SjakBookingViewSet(viewsets.ModelViewSet):
    """ViewSet for the SjakBooking class"""

    queryset = models.SjakBooking.objects.all()
    serializer_class = serializers.SjakBookingSerializer
    permission_classes = [permissions.IsAuthenticated]


class SjakItemTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for the SjakItemType class"""

    queryset = models.SjakItemType.objects.all()
    serializer_class = serializers.SjakItemTypeSerializer
    permission_classes = [permissions.IsAuthenticated]



