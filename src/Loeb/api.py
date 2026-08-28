from rest_framework import viewsets

from . import models, serializers


class LoebViewSet(viewsets.ModelViewSet):
    queryset = models.Loeb.objects.all()
    serializer_class = serializers.LoebSerializer


class PhysicalStationViewSet(viewsets.ModelViewSet):
    queryset = models.PhysicalStation.objects.all()
    serializer_class = serializers.PhysicalStationSerializer


class TaskViewSet(viewsets.ModelViewSet):
    queryset = models.Task.objects.all()
    serializer_class = serializers.TaskSerializer


class HoldViewSet(viewsets.ModelViewSet):
    queryset = models.Hold.objects.all()
    serializer_class = serializers.HoldSerializer


class TaskSubmissionViewSet(viewsets.ModelViewSet):
    queryset = models.TaskSubmission.objects.all()
    serializer_class = serializers.TaskSubmissionSerializer
