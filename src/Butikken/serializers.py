from rest_framework import serializers
from . import models


class ButikkenItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.ButikkenItem
        fields = [
            "description",
            "last_updated",
            "name",
            "created",
            "type",
        ]

class ButikkenBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ButikkenBooking
        fields = [
            "id",
            "order",
            "item",
            "team",
            "team_contact",
            "quantity",
            "unit",
            "status",
            "start_date",
            "start_time",
            "date_used",
            "remarks",
            "created",
            "last_updated",
        ]

class ButikkenItemTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.ButikkenItemType
        fields = [
            "last_updated",
            "name",
            "created",
            "description",
        ]




class DaySerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Day
        fields = [
            "name",
            "last_updated",
            "created",
            "date",
        ]

class RecipeSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Recipe
        fields = [
            "last_updated",
            "name",
            "description",
            "created",
        ]

class MealSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Meal
        fields = [
            "created",
            "type",
            "last_updated",
            "day",
        ]

class OptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Option
        fields = [
            "created",
            "last_updated",
            "meal",
            "recipe",
        ]
class MealBookingSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.MealBooking
        fields = [
            "last_updated",
            "monday_breakfast",
            "monday_lunch",
            "created",
            "monday_dinner",
            "team_contact",
            "team",
        ]

class TeamMealPlanSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TeamMealPlan
        fields = [
            "last_updated",
            "created",
            "meal_plan",
            "team",
            "meal_option",
        ]


class ButikkenOrderSerializer(serializers.ModelSerializer):
    bookings = ButikkenBookingSerializer(many=True, read_only=True)

    class Meta:
        model = models.ButikkenOrder
        fields = [
            "id",
            "team",
            "team_contact",
            "pickup_date",
            "status",
            "remarks",
            "order_date",
            "bookings",
        ]


