
from django.db import models
from django.urls import reverse

from organization.models import Event


class SjakItemType(models.Model):

    # Fields
    name = models.CharField(max_length=30)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Sjak_SjakItemType_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Sjak_SjakItemType_update", args=(self.pk,))


class SjakTag(models.Model):
    """
    Tag model for SjakBooking objects.
    Allows flexible tag management without database migration on every tag change.
    """
    name = models.CharField(max_length=30, unique=True)
    color = models.CharField(max_length=7, default='#0d6efd', help_text='Hex color code (e.g., #dc3545)')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Sjak Tag"
        verbose_name_plural = "Sjak Tags"
        ordering = ['name']

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Sjak_SjakTag_detail", args=(self.pk,))


class SjakItemLocation(models.Model):

    # Fields
    name = models.CharField(max_length=30)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Sjak_SjakItemType_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Sjak_SjakItemType_update", args=(self.pk,))

class SjakItem(models.Model):

    # Relationships
    #type = models.CharField(max_length=100, blank=True)
    item_type = models.ForeignKey("Sjak.SjakItemType", blank=True, on_delete=models.CASCADE, null=True)
    location = models.ForeignKey("Sjak.SjakItemLocation", default=None,  blank=True, null=True, on_delete=models.CASCADE)


    # Fields
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(max_length=500, blank=True, db_index=True)
    quantity_lager = models.CharField(max_length=100, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    image = models.ImageField(upload_to='SjakItem/', blank=True, null=True)

    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Sjak_SjakItem_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Sjak_SjakItem_update", args=(self.pk,))



class SjakBooking(models.Model):

    # Relationships
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE, db_index=True)
    item = models.ForeignKey("Sjak.SjakItem", on_delete=models.CASCADE, db_index=True)
    team_contact = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE, db_index=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, blank=True, null=True, db_index=True)
    assigned_sjak = models.ForeignKey("organization.Volunteer", on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_sjak_bookings', verbose_name="Assigned Staff")
    tag = models.ForeignKey("Sjak.SjakTag", on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings', verbose_name="Tag")
       
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )
    INTERNAL_STATUS_CHOICES = (
        ('Afventer', 'Afventer'),
        ('Igang', 'Igang'),
        ('Klar', 'Klar'),
        ('Afsluttet', 'Afsluttet'),
    )

    # Fields
    start_date = models.DateField(verbose_name='Start dato')
    start_time = models.TimeField(verbose_name='Start tidspunkt', default='12:01')
    end_date = models.DateField(verbose_name='Slut dato')
    end_time = models.TimeField(verbose_name='Slut tidspunkt', default='12:01')
    
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    remarks = models.TextField(blank=True)  # Blank allows for an empty value
    remarks_internal = models.TextField(blank=True)  # Blank allows for an empty value
    status_internal = models.CharField(max_length=20, choices=INTERNAL_STATUS_CHOICES, default='Afventer')
    image = models.ImageField(upload_to='sjak_bookings/', null=True, blank=True, verbose_name="Billede")


    class Meta:
        pass

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        return reverse("Sjak_SjakBooking_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Sjak_SjakBooking_update", args=(self.pk,))
    
    def approve_bookings(self, request, queryset):
        queryset.update(status="Approved")

    approve_bookings.short_description = "Approve selected bookings"

    def reject_bookings(self, request, queryset):
        queryset.update(status="Rejected")

    reject_bookings.short_description = "Rejected selected bookings"






