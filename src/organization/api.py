from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from . import models, serializers
from .permissions import (
    IsStaffOrReadOnly,
    IsStaffOrTeamMember,
    TeamScopedMixin,
    team_ids_for,
)


class TeamViewSet(viewsets.ModelViewSet):
    queryset = models.Team.objects.all()
    serializer_class = serializers.TeamSerializer
    permission_classes = [IsStaffOrReadOnly]


class TeamMembershipViewSet(viewsets.ModelViewSet):
    queryset = models.TeamMembership.objects.all()
    serializer_class = serializers.TeamMembershipSerializer
    permission_classes = [IsStaffOrReadOnly]


class EventViewSet(viewsets.ModelViewSet):
    queryset = models.Event.objects.all()
    serializer_class = serializers.EventSerializer
    permission_classes = [IsStaffOrReadOnly]


class EventMembershipViewSet(viewsets.ModelViewSet):
    queryset = models.EventMembership.objects.all()
    serializer_class = serializers.EventMembershipSerializer
    permission_classes = [IsStaffOrReadOnly]


class VolunteerViewSet(viewsets.ModelViewSet):
    queryset = models.Volunteer.objects.all()
    serializer_class = serializers.VolunteerSerializer
    permission_classes = [IsStaffOrReadOnly]


class KeyViewSet(viewsets.ModelViewSet):
    queryset = models.Key.objects.all()
    serializer_class = serializers.KeySerializer
    permission_classes = [IsStaffOrReadOnly]


class TjanseViewSet(viewsets.ModelViewSet):
    queryset = models.Tjanse.objects.all()
    serializer_class = serializers.TjanseSerializer
    permission_classes = [IsStaffOrReadOnly]


class TjanseOwnershipViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.TjanseOwnership.objects.all()
    serializer_class = serializers.TjanseOwnershipSerializer
    permission_classes = [IsStaffOrTeamMember]


class TjanseSwapRequestViewSet(viewsets.ModelViewSet):
    queryset = models.TjanseSwapRequest.objects.all()
    serializer_class = serializers.TjanseSwapRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        ids = team_ids_for(user)
        return qs.filter(requesting_team_id__in=ids) | qs.filter(receiving_team_id__in=ids)

    def perform_create(self, serializer):
        user = self.request.user
        requesting = serializer.validated_data.get("requesting_team")
        if not user.is_staff and (requesting is None or requesting.id not in team_ids_for(user)):
            raise PermissionDenied("Du kan kun oprette en bytte-anmodning for dit eget team.")
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if not user.is_staff and ("requesting_team" in serializer.validated_data or "receiving_team" in serializer.validated_data):
            raise PermissionDenied("Kun administratorer kan ændre teams på en bytte-anmodning.")
        serializer.save()
