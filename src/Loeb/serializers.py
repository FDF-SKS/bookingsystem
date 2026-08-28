from rest_framework import serializers

from .models import Hold, Loeb, PhysicalStation, Task, TaskSubmission


class LoebSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loeb
        fields = '__all__'


class PhysicalStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalStation
        fields = '__all__'


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'


class HoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hold
        fields = '__all__'


class TaskSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskSubmission
        fields = '__all__'
