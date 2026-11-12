
from datetime import date, datetime, time

from django.db import models
from django.urls import reverse
from django.utils import timezone


def _naive(dt):
    """Normalise aware datetimes so overlap comparisons are like-for-like."""
    if isinstance(dt, datetime) and timezone.is_aware(dt):
        return timezone.make_naive(dt, timezone.get_current_timezone())
    return dt


def _as_datetime(value, *, end=False):
    """Coerce dates to datetimes so callers may pass either type."""
    if isinstance(value, datetime):
        return _naive(value)
    if isinstance(value, date):
        return datetime.combine(value, time.max if end else time.min)
    return value


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
        start_datetime = _as_datetime(start_datetime, end=False)
        end_datetime = _as_datetime(end_datetime, end=True)
        
        start_date = start_datetime.date()
        end_date = end_datetime.date()
        
        # Broad date filter narrows the candidates; the exact overlap check uses
        # the full date+time window so same-day bookings only clash when their
        # times actually overlap.
        candidates = DepotBooking.objects.filter(
            item=self,
            status__in=['Approved', 'Pending'],
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        
        reserved_quantity = sum(
            booking.quantity
            for booking in candidates
            if datetime.combine(booking.start_date, booking.start_time) < end_datetime
            and datetime.combine(booking.end_date, booking.end_time) > start_datetime
        )
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
    start_time = models.TimeField(verbose_name='Start time', default=time(8, 0))
    end_date = models.DateField(verbose_name='End date')
    end_time = models.TimeField(verbose_name='End time', default=time(17, 0))
    
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
        start = _naive(datetime.combine(self.start_date, self.start_time))
        end = _naive(datetime.combine(self.end_date, self.end_time))

        candidates = DepotBooking.objects.filter(
            item=self.item,
            status__in=['Approved', 'Pending'],
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)

        current_reserved = sum(
            b.quantity for b in candidates
            if datetime.combine(b.start_date, b.start_time) < end
            and datetime.combine(b.end_date, b.end_time) > start
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


