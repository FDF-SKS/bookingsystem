"""Shared authorization helpers for the API layer.

The rule is simple and applied uniformly:

- Staff may read and write anything.
- Authenticated non-staff users may read shared/global catalogs, but may only
  read/write team-scoped objects that belong to one of their own teams.
- Global catalog mutation is staff-only.
"""
from django.contrib.auth.mixins import UserPassesTestMixin
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from .models import Volunteer


def team_ids_for(user):
    if user is None or not user.is_authenticated:
        return set()
    return set(user.teammembership_set.values_list("team_id", flat=True))


def restrict_team_field(user, team_field, contact_field=None):
    """Restrict a team ``ModelChoiceField`` (and optional contact field) to the
    teams the user belongs to. Staff keep the full queryset."""
    if user is None or not user.is_authenticated or user.is_staff:
        return
    teams = user.teams.all()
    team_field.queryset = teams
    if contact_field is not None:
        contact_field.queryset = Volunteer.objects.filter(
            teammembership__team__in=teams
        ).distinct()


class StaffRequiredMixin(UserPassesTestMixin):
    """Django view mixin: only staff may access the view."""

    def test_func(self):
        user = self.request.user
        return bool(user and user.is_authenticated and user.is_staff)


class TeamQuerysetMixin:
    """Scope a List/Detail/Update/Delete queryset to the user's teams."""

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        return qs.filter(team_id__in=team_ids_for(user))


class IsStaffOrReadOnly(permissions.BasePermission):
    """Authenticated users may read; only staff may create/update/delete."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return user.is_staff


class IsStaffOrTeamMember(permissions.BasePermission):
    """Staff may act on anything; others only on their own team's objects."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff:
            return True
        team = getattr(obj, "team", None)
        return team is not None and team.id in team_ids_for(user)


class TeamScopedMixin:
    """Scopes a ``ModelViewSet`` to the user's teams and guards team changes.

    The model is expected to have a ``team`` foreign key.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        return qs.filter(team_id__in=team_ids_for(user))

    def perform_create(self, serializer):
        user = self.request.user
        team = serializer.validated_data.get("team")
        if not user.is_staff and (team is None or team.id not in team_ids_for(user)):
            raise PermissionDenied("Du kan kun oprette for dit eget team.")
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        team = serializer.validated_data.get("team")
        if (
            not user.is_staff
            and team is not None
            and serializer.instance.team_id != team.id
        ):
            raise PermissionDenied("Du kan ikke flytte en post til et andet team.")
        serializer.save()
