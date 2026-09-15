from django.db import models
from django.urls import reverse
from django.utils import timezone
from utils.fields import SafeLocationField

class FotoItem(models.Model):

    # Fields
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    name = models.CharField(max_length=100, default="Item name")
    description = models.TextField(max_length=500, blank=True)

    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Foto_FotoItem_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Foto_FotoItem_update", args=(self.pk,))



class FotoBooking(models.Model):

    # Relationships
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE)
    item = models.ForeignKey("Foto.FotoItem", on_delete=models.CASCADE)
    team_contact = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE)

    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )

    # Fields
    start_time = models.TimeField(default=timezone.now)
    end_time = models.TimeField(default=timezone.now)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(default=timezone.now)
    remarks = models.TextField(max_length=500)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    location = SafeLocationField(
        "Placering", 
        blank=True, 
        null=True,
        default="56.113991,9.665244",
        options={
            'map': {
                'center': [56.113991, 9.665244],
                'zoom': 13,
            },
            'marker': {
                'draggable': True,
                'position': [56.113991, 9.665244],
            }
        }
    )
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')

    class Meta:
        verbose_name = "Foto Booking"
        verbose_name_plural = "Foto Bookinger"
        ordering = ['-start_date', '-start_time']

    def __str__(self):
        return f"{self.item.name} - {self.team.name} ({self.start_date})"

    def get_absolute_url(self):
        return reverse("Foto_FotoBooking_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Foto_FotoBooking_update", args=(self.pk,))

    def coords_list(self):
        """Splits the 'lat,lng' string from LocationField into a float list."""
        if self.location:
            try:
                # LocationField usually stores as a string "56.11,9.66"
                parts = str(self.location).split(',')
                return [float(parts[0]), float(parts[1])]
            except (ValueError, IndexError):
                return [56.113991, 9.665244] # Your default center
        return [56.113991, 9.665244]

    def to_dict(self):
        """Used for JSON serialization and API-like context."""
        coords = self.coords_list
        return {
            'id': self.id,
            'item': str(self.item),
            'team': str(self.team),
            'latitude': coords[0],
            'longitude': coords[1],
            'status': self.status,
        }

