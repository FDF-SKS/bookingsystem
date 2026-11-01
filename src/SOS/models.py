import datetime

from django.db import models
from django.urls import reverse


class SOSBooking(models.Model):

    # Relationships
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE)
    item = models.ForeignKey("SOS.SOSItem", on_delete=models.CASCADE)
    team_contact = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE)

    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )

    # Fields
    start_date = models.DateField(default=datetime.datetime.now)
    start_time = models.TimeField(default=datetime.time(8, 0))
    end_date = models.DateField(default=datetime.datetime.now)
    end_time = models.TimeField(default=datetime.time(8, 0))
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    remarks = models.TextField(blank=True)  # Blank allows for an empty value
    remarks_internal = models.TextField(blank=True)  # Blank allows for an empty value
    assistance_needed = models.BooleanField(default=False, blank=True)
    delivery_needed = models.BooleanField(default=False, blank=True)
    dispatched = models.BooleanField(default=False, editable=False)
    received = models.BooleanField(default=False, editable=False)



    class Meta:
        pass

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        return reverse("SOS_SOSBooking_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("SOS_SOSBooking_update", args=(self.pk,))
    
    def approve_bookings(self, request, queryset):
        queryset.update(status="Approved")

    approve_bookings.short_description = "Approve selected bookings"

    def reject_bookings(self, request, queryset):
        queryset.update(status="Rejected")

    reject_bookings.short_description = "Rejected selected bookings"



class SOSItem(models.Model):
    # Fields
    name = models.CharField(max_length=30)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    description = models.TextField(max_length=100)

    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("SOS_SOSItem_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("SOS_SOSItem_update", args=(self.pk,))



class SOSType(models.Model):

    # Fields
    name = models.CharField(max_length=30, null=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False, null=False)
    created = models.DateTimeField(auto_now_add=True, editable=False, null=False)

    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("SOS_SOSType_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("SOS_SOSType_update", args=(self.pk,))



