from rest_framework import serializers

from .models import DepotBooking, DepotItem


class DepotItemSerializer(serializers.ModelSerializer):
    available_quantity = serializers.SerializerMethodField()
    location_name = serializers.CharField(source='location.name', read_only=True)

    class Meta:
        model = DepotItem
        fields = ['id', 'name', 'description', 'location', 'location_name', 'image', 'quantity', 'unit', 'available_quantity', 'created', 'last_updated']
        read_only_fields = ['id', 'created', 'last_updated']

    def get_available_quantity(self, obj):
        """Get available quantity for current time."""
        return obj.available_quantity()


class DepotBookingSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    contact_name = serializers.CharField(source='team_contact.get_full_name', read_only=True)

    class Meta:
        model = DepotBooking
        fields = [
            'id', 'item', 'item_name', 'team', 'team_name', 'team_contact', 
            'contact_name', 'quantity', 'start_date', 'start_time', 'end_date', 'end_time', 
            'status', 'remarks', 'admin_comment', 'created_at', 'last_updated'
        ]
        read_only_fields = ['id', 'created_at', 'last_updated']


