from rest_framework import viewsets, permissions

from . import serializers
from . import models


class TeamViewSet(viewsets.ModelViewSet):
    """ViewSet for the Team class"""

    queryset = models.Team.objects.all()
    serializer_class = serializers.TeamSerializer
    permission_classes = [permissions.IsAuthenticated]


class TeamMembershipViewSet(viewsets.ModelViewSet):
    """ViewSet for the TeamMembership class"""

    queryset = models.TeamMembership.objects.all()
    serializer_class = serializers.TeamMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]


class EventViewSet(viewsets.ModelViewSet):
    """ViewSet for the Event class"""

    queryset = models.Event.objects.all()
    serializer_class = serializers.EventSerializer
    permission_classes = [permissions.IsAuthenticated]


class EventMembershipViewSet(viewsets.ModelViewSet):
    """ViewSet for the EventMembership class"""

    queryset = models.EventMembership.objects.all()
    serializer_class = serializers.EventMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]


class VolunteerViewSet(viewsets.ModelViewSet):
    """ViewSet for the Volunteer class"""

    queryset = models.Volunteer.objects.all()
    serializer_class = serializers.VolunteerSerializer
    permission_classes = [permissions.IsAuthenticated]


class KeyViewSet(viewsets.ModelViewSet):
    """ViewSet for the Key class"""

    queryset = models.Key.objects.all()
    serializer_class = serializers.KeySerializer
    permission_classes = [permissions.IsAuthenticated]


class TjanseViewSet(viewsets.ModelViewSet):
    """ViewSet for the Tjanse class"""

    queryset = models.Tjanse.objects.all()
    serializer_class = serializers.TjanseSerializer
    permission_classes = [permissions.IsAuthenticated]


class TjanseOwnershipViewSet(viewsets.ModelViewSet):
    """ViewSet for the TjanseOwnership class"""

    queryset = models.TjanseOwnership.objects.all()
    serializer_class = serializers.TjanseOwnershipSerializer
    permission_classes = [permissions.IsAuthenticated]


class TjanseSwapRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for the TjanseSwapRequest class"""

    queryset = models.TjanseSwapRequest.objects.all()
    serializer_class = serializers.TjanseSwapRequestSerializer
    permission_classes = [permissions.IsAuthenticated]



