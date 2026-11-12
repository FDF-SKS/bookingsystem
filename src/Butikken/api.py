from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from organization.permissions import (
    IsStaffOrReadOnly,
    IsStaffOrTeamMember,
    TeamScopedMixin,
    team_ids_for,
)

from . import models, serializers


class ButikkenItemViewSet(viewsets.ModelViewSet):
    queryset = models.ButikkenItem.objects.all()
    serializer_class = serializers.ButikkenItemSerializer
    permission_classes = [IsStaffOrReadOnly]


class ButikkenBookingViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.ButikkenBooking.objects.all()
    serializer_class = serializers.ButikkenBookingSerializer
    permission_classes = [IsStaffOrTeamMember]

    def _guard_order(self, serializer, team):
        """A booking may only reference an order owned by the same team."""
        user = self.request.user
        if user.is_staff:
            return
        order = serializer.validated_data.get("order")
        if order is None:
            return
        if order.team_id not in team_ids_for(user) or (
            team is not None and order.team_id != team.id
        ):
            raise PermissionDenied("Ordren tilhører et andet team.")

    def perform_create(self, serializer):
        user = self.request.user
        team = serializer.validated_data.get("team")
        if not user.is_staff and (team is None or team.id not in team_ids_for(user)):
            raise PermissionDenied("Du kan kun oprette for dit eget team.")
        self._guard_order(serializer, team)
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if (
            not user.is_staff
            and "team" in serializer.validated_data
            and serializer.instance.team_id != serializer.validated_data["team"].id
        ):
            raise PermissionDenied("Du kan ikke flytte en post til et andet team.")
        team = serializer.validated_data.get("team") or serializer.instance.team
        self._guard_order(serializer, team)
        serializer.save()


class ButikkenItemTypeViewSet(viewsets.ModelViewSet):
    queryset = models.ButikkenItemType.objects.all()
    serializer_class = serializers.ButikkenItemTypeSerializer
    permission_classes = [IsStaffOrReadOnly]


class MealViewSet(viewsets.ModelViewSet):
    queryset = models.Meal.objects.all()
    serializer_class = serializers.MealSerializer
    permission_classes = [IsStaffOrReadOnly]


class OptionViewSet(viewsets.ModelViewSet):
    queryset = models.Option.objects.all()
    serializer_class = serializers.OptionSerializer
    permission_classes = [IsStaffOrReadOnly]


class DayViewSet(viewsets.ModelViewSet):
    queryset = models.Day.objects.all()
    serializer_class = serializers.DaySerializer
    permission_classes = [IsStaffOrReadOnly]


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = models.Recipe.objects.all()
    serializer_class = serializers.RecipeSerializer
    permission_classes = [IsStaffOrReadOnly]


class MealBookingViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.MealBooking.objects.all()
    serializer_class = serializers.MealBookingSerializer
    permission_classes = [IsStaffOrTeamMember]


class TeamMealPlanViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.TeamMealPlan.objects.all()
    serializer_class = serializers.TeamMealPlanSerializer
    permission_classes = [IsStaffOrTeamMember]


class ButikkenOrderViewSet(TeamScopedMixin, viewsets.ModelViewSet):
    queryset = models.ButikkenOrder.objects.all()
    serializer_class = serializers.ButikkenOrderSerializer
    permission_classes = [IsStaffOrTeamMember]
