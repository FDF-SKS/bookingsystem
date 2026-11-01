from rest_framework import permissions, viewsets

from . import models, serializers


class LoebViewSet(viewsets.ModelViewSet):
    queryset = models.Loeb.objects.all()
    serializer_class = serializers.LoebSerializer
    permission_classes = [permissions.IsAuthenticated]


class PhysicalStationViewSet(viewsets.ModelViewSet):
    queryset = models.PhysicalStation.objects.all()
    serializer_class = serializers.PhysicalStationSerializer
    permission_classes = [permissions.IsAuthenticated]


class TaskViewSet(viewsets.ModelViewSet):
    queryset = models.Task.objects.all()
    serializer_class = serializers.TaskSerializer
    permission_classes = [permissions.IsAuthenticated]


class HoldViewSet(viewsets.ModelViewSet):
    queryset = models.Hold.objects.all()
    serializer_class = serializers.HoldSerializer
    permission_classes = [permissions.IsAuthenticated]


class TaskSubmissionViewSet(viewsets.ModelViewSet):
    queryset = models.TaskSubmission.objects.all()
    serializer_class = serializers.TaskSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
