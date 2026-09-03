from rest_framework import viewsets, permissions

from . import serializers
from . import models


class ButikkenItemViewSet(viewsets.ModelViewSet):
    """ViewSet for the ButikkenItem class"""

    queryset = models.ButikkenItem.objects.all()
    serializer_class = serializers.ButikkenItemSerializer
    permission_classes = [permissions.IsAuthenticated]


class ButikkenBookingViewSet(viewsets.ModelViewSet):
    """ViewSet for the ButikkenBooking class"""

    queryset = models.ButikkenBooking.objects.all()
    serializer_class = serializers.ButikkenBookingSerializer
    permission_classes = [permissions.IsAuthenticated]


class ButikkenItemTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for the ButikkenItemType class"""

    queryset = models.ButikkenItemType.objects.all()
    serializer_class = serializers.ButikkenItemTypeSerializer
    permission_classes = [permissions.IsAuthenticated]



class MealViewSet(viewsets.ModelViewSet):
    """ViewSet for the Meal class"""

    queryset = models.Meal.objects.all()
    serializer_class = serializers.MealSerializer
    permission_classes = [permissions.IsAuthenticated]


class OptionViewSet(viewsets.ModelViewSet):
    """ViewSet for the Option class"""

    queryset = models.Option.objects.all()
    serializer_class = serializers.OptionSerializer
    permission_classes = [permissions.IsAuthenticated]

class DayViewSet(viewsets.ModelViewSet):
    """ViewSet for the Day class"""

    queryset = models.Day.objects.all()
    serializer_class = serializers.DaySerializer
    permission_classes = [permissions.IsAuthenticated]


class RecipeViewSet(viewsets.ModelViewSet):
    """ViewSet for the Recipe class"""

    queryset = models.Recipe.objects.all()
    serializer_class = serializers.RecipeSerializer
    permission_classes = [permissions.IsAuthenticated]

class MealBookingViewSet(viewsets.ModelViewSet):
    """ViewSet for the MealBooking class"""

    queryset = models.MealBooking.objects.all()
    serializer_class = serializers.MealBookingSerializer
    permission_classes = [permissions.IsAuthenticated]

class TeamMealPlanViewSet(viewsets.ModelViewSet):
    """ViewSet for the TeamMealPlan class"""

    queryset = models.TeamMealPlan.objects.all()
    serializer_class = serializers.TeamMealPlanSerializer
    permission_classes = [permissions.IsAuthenticated]


class ButikkenOrderViewSet(viewsets.ModelViewSet):
    """ViewSet for the ButikkenOrder (cart) class"""

    serializer_class = serializers.ButikkenOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = models.ButikkenOrder.objects.all()
        user = self.request.user
        if user.is_staff:
            return qs
        team_ids = user.teammembership_set.values_list('team', flat=True)
        return qs.filter(team_id__in=team_ids)

