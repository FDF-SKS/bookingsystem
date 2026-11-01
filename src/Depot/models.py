
from django.db import models
from django.urls import reverse
from django.utils import timezone


class DepotLocation(models.Model):
    """
    Storage location for depot items.
    Tracks where items are physically stored.
    """
    
    # Fields
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(max_length=500, blank=True)
    
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Depot Location"
        verbose_name_plural = "Depot Locations"
        ordering = ['name']

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Depot_DepotLocation_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Depot_DepotLocation_update", args=(self.pk,))


class DepotItem(models.Model):
    """
    Physical inventory item for depot management.
    Tracks total quantity available in inventory.
    """
    
    # Relationships
    location = models.ForeignKey("Depot.DepotLocation", on_delete=models.CASCADE, db_index=True, related_name='items', null=True, blank=True)
    
    # Fields
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(max_length=500, blank=True)
    image = models.ImageField(upload_to='DepotItem/', blank=True, null=True)
    quantity = models.IntegerField(default=1, help_text="Total quantity available in inventory")
    unit = models.CharField(max_length=50, default="stk", help_text="Unit of measurement (e.g., stk, liter, kg, m, etc.)")
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Depot Item"
        verbose_name_plural = "Depot Items"
        ordering = ['name']

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Depot_DepotItem_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Depot_DepotItem_update", args=(self.pk,))

    def available_quantity(self, start_datetime=None, end_datetime=None):
        """
        Calculate available quantity for a given time range.
        Available = quantity - Sum(Approved + Pending Bookings)
        
        Args:
            start_datetime: Start of the period to check
            end_datetime: End of the period to check
        
        Returns:
            int: Available quantity
        """
        if start_datetime is None:
            start_datetime = timezone.now()
        if end_datetime is None:
            end_datetime = timezone.now()
        
        start_date = start_datetime.date() if hasattr(start_datetime, 'date') else start_datetime
        end_date = end_datetime.date() if hasattr(end_datetime, 'date') else end_datetime
        
        # Get all approved and pending bookings that overlap with the time range
        overlapping_bookings = DepotBooking.objects.filter(
            item=self,
            status__in=['Approved', 'Pending'],
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        
        reserved_quantity = sum(booking.quantity for booking in overlapping_bookings)
        available = self.quantity - reserved_quantity
        
        return max(0, available)


class DepotBooking(models.Model):
    """
    Booking for depot items.
    Tracks inventory reservations with time windows.
    """
    
    # Relationships
    item = models.ForeignKey("Depot.DepotItem", on_delete=models.CASCADE, db_index=True, related_name='bookings')
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE, db_index=True)
    team_contact = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE)
    
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Udleveret', 'Udleveret'),  # Delivered
    )

    # Fields
    quantity = models.IntegerField(default=1, help_text="Quantity requested")
    start_date = models.DateField(verbose_name='Start date')
    start_time = models.TimeField(verbose_name='Start time', default='08:00')
    end_date = models.DateField(verbose_name='End date')
    end_time = models.TimeField(verbose_name='End time', default='17:00')
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending', db_index=True)
    remarks = models.TextField(blank=True, help_text="Booking remarks")
    admin_comment = models.TextField(blank=True, help_text="Admin comment on booking")
    
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Depot Booking"
        verbose_name_plural = "Depot Bookings"
        ordering = ['-start_date', '-start_time']
        indexes = [
            models.Index(fields=['item', 'status']),
            models.Index(fields=['team', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.item.name} - {self.team.name} ({self.status})"

    def get_absolute_url(self):
        return reverse("Depot_DepotBooking_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Depot_DepotBooking_update", args=(self.pk,))

    def is_overbooked(self):
        """Check if this booking exceeds available quantity."""
        # For current booking, add back its own quantity to check against other bookings
        current_reserved = sum(
            b.quantity for b in DepotBooking.objects.filter(
                item=self.item,
                status__in=['Approved', 'Pending'],
                start_date__lte=self.end_date,
                end_date__gte=self.start_date
            ).exclude(pk=self.pk)
        )
        return self.quantity > (self.item.quantity - current_reserved)

    def get_status_display_color(self):
        """Return Bootstrap color class based on status."""
        status_colors = {
            'Pending': 'warning',
            'Approved': 'success',
            'Rejected': 'danger',
            'Udleveret': 'info',
        }
        return status_colors.get(self.status, 'secondary')


