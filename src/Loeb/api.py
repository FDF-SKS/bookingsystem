from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from organization.permissions import (
    IsStaffOrReadOnly,
    IsStaffOrTeamMember,
    TeamScopedMixin,
    team_ids_for,
)

from . import models, serializers


def _team_id(value):
    """Resolve the owning team id for a Loeb-related object."""
    if value is None:
        return None
    if hasattr(value, "team_id"):
        return value.team_id
    loeb = getattr(value, "loeb", None)
    if loeb is not None:
        return loeb.team_id
    hold = getattr(value, "hold", None)
    if hold is not None:
        return hold.loeb.team_id
    return None


class LoebViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.Loeb.objects.all()
    serializer_class = serializers.LoebSerializer
    permission_classes = [IsStaffOrTeamMember]


class PhysicalStationViewSet(viewsets.ModelViewSet):
    """Physical stations are a shared/global catalog; staff-only mutation."""

    queryset = models.PhysicalStation.objects.all()
    serializer_class = serializers.PhysicalStationSerializer
    permission_classes = [IsStaffOrReadOnly]


class _LoebChildViewSet(viewsets.ModelViewSet):
    """ViewSet for models nested under ``Loeb``.

    Non-staff users only see/mutate rows whose Loeb belongs to one of their
    teams. ``team_lookup`` is the ORM path to the team (e.g. ``"loeb__team"``),
    and ``relation_fields`` are the serializer fields that must point at one of
    the user's Loebs on create/update.
    """

    permission_classes = [permissions.IsAuthenticated]
    team_lookup = None
    relation_fields = ()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff or not self.team_lookup:
            return qs
        return qs.filter(**{f"{self.team_lookup}_id__in": team_ids_for(user)})

    def _require_own_team(self, related):
        user = self.request.user
        if user.is_staff:
            return
        team_id = _team_id(related)
        if team_id is None or team_id not in team_ids_for(user):
            raise PermissionDenied("Du kan kun arbejde med data for dit eget team.")

    def perform_create(self, serializer):
        for field in self.relation_fields:
            self._require_own_team(serializer.validated_data.get(field))
        serializer.save()

    def perform_update(self, serializer):
        for field in self.relation_fields:
            if field in serializer.validated_data:
                self._require_own_team(serializer.validated_data[field])
        serializer.save()


class TaskViewSet(_LoebChildViewSet):
    queryset = models.Task.objects.all()
    serializer_class = serializers.TaskSerializer
    team_lookup = "loeb__team"
    relation_fields = ("loeb",)


class HoldViewSet(_LoebChildViewSet):
    queryset = models.Hold.objects.all()
    serializer_class = serializers.HoldSerializer
    team_lookup = "loeb__team"
    relation_fields = ("loeb",)


class TaskSubmissionViewSet(_LoebChildViewSet):
    queryset = models.TaskSubmission.objects.all()
    serializer_class = serializers.TaskSubmissionSerializer
    team_lookup = "hold__loeb__team"
    relation_fields = ("hold", "task")
