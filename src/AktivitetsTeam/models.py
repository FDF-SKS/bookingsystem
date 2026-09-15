from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MaxValueValidator
from django.utils.text import slugify
from utils.fields import SafeLocationField


class AktivitetsTeamItemType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    bs_icon = models.CharField(max_length=50, default="bi-tag", help_text="Bootstrap icon name (f.eks. bi-rocket)")
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    @property
    def coords(self):
        if self.location:
            return self.location.split(',')
        return None
    
class AktivitetsTeamItem(models.Model):

    # Fields
    description = models.TextField(max_length=2000)
    short_description = models.TextField(max_length=200)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    youtube_link = models.URLField(
        max_length=2000, 
        blank=True, 
        null=True,
        help_text="Indsæt link til YouTube video (valgfrit)"
    )
    description_flow = models.TextField(max_length=200, blank=True)
    description_eksempel = models.TextField(max_length=200, blank=True)
    description_aktiverede = models.TextField(max_length=200, blank=True)
    name = models.CharField(max_length=100)
    category = models.ForeignKey(
        AktivitetsTeamItemType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="items"
    )
    is_active = models.BooleanField(default=True)
    location = SafeLocationField(
        "Placering", 
        blank=True, 
        null=True,
        default="56.113991,9.665244", # This sets the initial text value
        options={
            'map': {
                'center': [56.113991, 9.665244], # Centers the map here
                'zoom': 13, # A closer zoom level for accuracy
            },
            'marker': {
                'draggable': True,
                'position': [56.113991, 9.665244], # Places the pin here
            }
        }
    )

    image = models.ImageField(upload_to='AktivitetstTeamItem/', blank=True, null=True)


    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("AktivitetsTeam_AktivitetsTeamItem_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("AktivitetsTeam_AktivitetsTeamItem_update", args=(self.pk,))
    def to_dict(self):
        return {
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            # Add other fields as necessary
        }
    @property
    def coords_list(self):
        if self.location:
            # Most mapping objects have .lat and .lng attributes
            try:
                return [self.location.lat, self.location.lng]
            except AttributeError:
                # Fallback to string split if attributes aren't present
                return [float(x.strip()) for x in str(self.location).split(',')]
        return None






class AktivitetsTeamBooking(models.Model):
    # Relationships
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE)
    item = models.ForeignKey("AktivitetsTeam.AktivitetsTeamItem", on_delete=models.CASCADE)
    team_contact = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE, related_name='team_contact_bookings')

    # Add Many-to-Many relationship with Volunteer
    assigned_aktivitetsteam = models.ManyToManyField("organization.Volunteer", related_name='Assigned_Aktivitetsteam', blank=True)

    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )

    # Fields
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    remarks = models.TextField(blank=True, max_length=2000)  # Set an appropriate max length
    start_date = models.DateField(default=timezone.now)
    start_time = models.TimeField(default=timezone.now)
    end_date = models.DateField(default=timezone.now)
    end_time = models.TimeField(default=timezone.now)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    remarks_internal = models.TextField(blank=True, max_length=500)  # Set an appropriate max length
    location = SafeLocationField(
        "Lokation",
        blank=True,
        null=True,
        default="56.114951,9.655592", # Your default Teknik location
        options={
            'map': {
                'center': [56.114951, 9.655592],
                'zoom': 13,
            },
            'marker': {
                'draggable': True,
                'position': [56.114951, 9.655592],
            }
        }
    )


    class Meta:
        pass

    def __str__(self):
        return str(self.pk)
    @property
    def coords_list(self):
        """
        Safely splits the location string. 
        If the data is broken ('56.123' without a comma), it returns the default 
        instead of crashing the entire site.
        """
        default_coords = [56.114951, 9.655592]
        
        if not self.location:
            return default_coords
            
        try:
            # Ensure we are working with a string and split it
            parts = str(self.location).split(',')
            if len(parts) == 2:
                return [float(parts[0].strip()), float(parts[1].strip())]
        except (ValueError, IndexError, AttributeError):
            # If split fails or float conversion fails, return default
            pass
            
        return default_coords

    def get_absolute_url(self):
        return reverse("AktivitetsTeam_AktivitetsTeamBooking_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("AktivitetsTeam_AktivitetsTeamBooking_update", args=(self.pk,))

    def clean(self):
        if self.start_date and not self.start_time:
            raise ValidationError(_("Start time is required."))
        if self.end_date and not self.end_time:
            raise ValidationError(_("End time is required."))
        if self.start_date and self.start_time and self.end_date and self.end_time:
            start_datetime = timezone.make_aware(
                timezone.datetime.combine(self.start_date, self.start_time)
            )
            end_datetime = timezone.make_aware(
                timezone.datetime.combine(self.end_date, self.end_time)
            )
            if start_datetime >= end_datetime:
                raise ValidationError(_("Start time must be before end time."))
    
    def save(self, *args, **kwargs):
        if self.start_date and self.start_time:
            self.start = timezone.make_aware(
                timezone.datetime.combine(self.start_date, self.start_time),
                timezone.get_default_timezone()
            )
        if self.end_date and self.end_time:
            self.end = timezone.make_aware(
                timezone.datetime.combine(self.end_date, self.end_time),
                timezone.get_default_timezone()
            )
        super().save(*args, **kwargs)
    
    def approve_bookings(self, request, queryset):
        queryset.update(status="Approved")

    approve_bookings.short_description = "Approve selected bookings"

    def reject_bookings(self, request, queryset):
        queryset.update(status="Rejected")

    reject_bookings.short_description = "Reject selected bookings"
    
    def to_dict(self):
        """Safe dictionary conversion for JSON/Maps."""
        coords = self.coords_list  # Uses the safe property above
        return {
            'id': self.id,
            'item': str(self.item.name) if self.item else "Unknown",
            'team': str(self.team.name) if self.team else "Unknown",
            'latitude': coords[0],
            'longitude': coords[1],
            'status': self.status,
        }




