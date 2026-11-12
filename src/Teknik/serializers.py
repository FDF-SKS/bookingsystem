from rest_framework import serializers

from . import models


class TeknikBookingSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TeknikBooking
        fields = [
            "quantity",
            "created",
            "start_date",
            "start_time",
            "end_date",
            "end_time",
            "last_updated",
            "status",
            "team",
            "item",
            "team_contact",
        ]

class TeknikItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TeknikItem
        fields = [
            "name",
            "last_updated",
            "created",
            "description",
        ]

class TeknikTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TeknikType
        fields = [
            "name",
            "last_updated",
            "created",
        ]


