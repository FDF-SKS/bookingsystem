from rest_framework import serializers

from . import models


class TeamSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Team
        fields = [
            "name",
            "last_updated",
            "short_name",
            "created",
        ]

class TeamMembershipSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TeamMembership
        fields = [
            "last_updated",
            "created",
            "role",
            "team",
            "member",
        ]

class EventSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Event
        fields = [
            "end_date",
            "last_updated",
            "name",
            "start_date",
            "created",
        ]

class EventMembershipSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.EventMembership
        fields = [
            "last_updated",
            "created",
            "event",
            "member",
        ]

class VolunteerSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Volunteer
        fields = [
            "first_name",
            "created",
            "last_name",
            "last_updated",
            "email",
        ]

class KeySerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Key
        fields = [
            "description",
            "created",
            "last_updated",
            "name",
            "number",
            "current_user",
        ]

class TjanseSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Tjanse
        fields = [
            "id",
            "title",
            "description",
            "created",
            "last_updated",
        ]

class TjanseOwnershipSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TjanseOwnership
        fields = [
            "id",
            "tjanse",
            "event",
            "team",
            "status",
            "due_date",
            "assigned_at",
            "completed_at",
            "created",
            "last_updated",
        ]

class TjanseSwapRequestSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TjanseSwapRequest
        fields = [
            "id",
            "task_ownership",
            "requesting_team",
            "receiving_team",
            "status",
            "resolved_by",
            "created",
            "last_updated",
        ]


