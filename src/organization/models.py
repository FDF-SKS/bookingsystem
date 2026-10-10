from django.db import models
from django.contrib.auth.models import AbstractUser
from django.urls import reverse
from django.utils import timezone
from simple_history.models import HistoricalRecords
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django_tiptap_editor.fields import TipTapJSONField
import os




    

class TeamMembership(models.Model):

    # Relationships
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE, db_index=True)
    member = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE, db_index=True)

    # Fields
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    role = models.CharField(max_length=30, blank=True)

    class Meta:
        pass

    def __str__(self):
        return str(self.pk)
    

    

class Event(models.Model):

    # Fields
    name = models.CharField(max_length=30, db_index=True)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    deadline_sjak = models.DateField()
    deadline_teknik = models.DateField()
    deadline_mad = models.DateField()
    deadline_aktivitetsteam = models.DateField()
    deadline_foto = models.DateField()
    deadline_lokaler = models.DateField()
    deadline_sos = models.DateField()
    history = HistoricalRecords()


    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("organization_Event_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("organization_Event_update", args=(self.pk,))
    
# Create your models here.
class Team(models.Model):

    # Fields
    name = models.CharField(max_length=30, db_index=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    short_name = models.CharField(max_length=30, db_index=True)   
    events = models.ManyToManyField(Event, through='TeamEventMembership', db_index=True)
    discord_webhook_url = models.URLField(null=True, blank=True, help_text="Discord webhook URL for real-time notifications. Get this from Server Settings > Integrations > Webhooks > Copy Webhook URL")
    history = HistoricalRecords()



    class Meta:
        pass

    def __str__(self):
        return str(self.name)
    

class Volunteer(AbstractUser):

    # Fields
    username = models.CharField(max_length=30, unique=True, db_index=True)
    first_name = models.CharField(max_length=30, db_index=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_name = models.CharField(max_length=30, db_index=True)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=30, blank=True, db_index=True)
    image = models.ImageField(upload_to='volunteer_profiles/', blank=True, null=True)
    image_thumbnail = models.ImageField(upload_to='volunteer_profiles/thumbnails/', blank=True, null=True, editable=False)
    discord_id = models.CharField(max_length=30, null=True, blank=True, help_text="Discord user ID for @mention functionality (e.g., '123456789')")
    events = models.ManyToManyField(Event, through='EventMembership',blank=True, db_index=True)
    teams = models.ManyToManyField(Team, through='TeamMembership', blank=True, db_index=True)
    history = HistoricalRecords()

    class Meta:
        pass

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def save(self, *args, **kwargs):
        # Generate thumbnail when image is uploaded
        if self.image and not self.image_thumbnail:
            self._create_thumbnail()
        super().save(*args, **kwargs)
    
    def _create_thumbnail(self):
        """Generate a thumbnail from the uploaded image (300x300px, optimized)"""
        try:
            img = Image.open(self.image)
            # Convert RGBA to RGB if necessary (for JPEG compatibility)
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            # Create thumbnail
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            
            # Save to BytesIO
            thumb_io = BytesIO()
            img.save(thumb_io, format='JPEG', quality=85, optimize=True)
            thumb_io.seek(0)
            
            # Generate filename
            name = os.path.splitext(self.image.name)[0]
            thumb_filename = f"{name}_thumb.jpg"
            
            # Save thumbnail
            self.image_thumbnail.save(thumb_filename, ContentFile(thumb_io.read()), save=False)
        except Exception as e:
            # Silently fail if thumbnail generation fails
            pass

    def get_absolute_url(self):
        return reverse("organization_Volunteer_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("organization_Volunteer_update", args=(self.pk,))
    

class TeamEventMembership(models.Model):

    # Relationships
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_index=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, db_index=True)

    # Fields
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        pass

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        return reverse("organization_TeamEventMembership_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("organization_TeamEventMembership_update", args=(self.pk,))


class EventMembership(models.Model):

    # Relationships
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_index=True)
    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, db_index=True)

    # Fields
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    history = HistoricalRecords()

    class Meta:
        pass

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        return reverse("organization_EventMembership_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("organization_EventMembership_update", args=(self.pk,))
    
class Key(models.Model):

    # Relationships
    current_user = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE, blank=True, null=True, db_index=True)

    # Fields
    description = models.TextField(max_length=100, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    name = models.CharField(max_length=30)
    number = models.CharField(max_length=30)
    history = HistoricalRecords()

    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("organization_Key_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("organization_Key_update", args=(self.pk,))


class VolunteerAppointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Afventer (Pending)'),
        ('accepted', 'Accepteret'),
        ('rejected', 'Afvist'),
        ('cancelled', 'Annulleret'),
    ]

    requester = models.ForeignKey(
        "organization.Volunteer", 
        on_delete=models.CASCADE, 
        related_name="requested_appointments"
    )
    receiver = models.ForeignKey(
        "organization.Volunteer", 
        on_delete=models.CASCADE, 
        related_name="received_appointments"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    description = models.TextField(max_length=500)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )

    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Aftale"

    def __str__(self):
        # Get first team for requester
        requester_team = self.requester.teams.first()
        requester_str = f"{self.requester} ({requester_team.short_name})" if requester_team else str(self.requester)
        
        # Get first team for receiver
        receiver_team = self.receiver.teams.first()
        receiver_str = f"{self.receiver} ({receiver_team.short_name})" if receiver_team else str(self.receiver)
        
        return f"{requester_str} -> {receiver_str} "
    
    def get_absolute_url(self):
        return reverse("organization_VolunteerAppointment_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("organization_VolunteerAppointment_update", args=(self.pk,))


class Tjanse(models.Model):
    """Reusable duty/chore template (e.g. 'Opvask'), assigned to teams per event via TjanseOwnership."""

    title = models.CharField(max_length=100)
    description = TipTapJSONField(blank=True, default=dict)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Tjanse"

    def __str__(self):
        return self.title


class TjanseOwnership(models.Model):
    """Assignment of a Tjanse to a Team for a given Event, tracked with a history of team reassignments."""

    STATUS_CHOICES = [
        ('assigned', 'Tildelt'),
        ('in_progress', 'I Gang'),
        ('done', 'Udført'),
        ('not_done', 'Ikke Udført'),
    ]

    tjanse = models.ForeignKey("organization.Tjanse", on_delete=models.CASCADE, related_name="ownerships")
    event = models.ForeignKey("organization.Event", on_delete=models.CASCADE, related_name="tjanse_ownerships")
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE, related_name="tjanse_ownerships")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    due_date = models.DateField(null=True, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Tjanse-tildeling"
        verbose_name_plural = "Tjanse-tildelinger"

    def __str__(self):
        return f"{self.tjanse} - {self.team} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("organization_TjanseOwnership_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("organization_TjanseOwnership_update", args=(self.pk,))


class TjanseSwapRequest(models.Model):
    """Request from one team to hand a TjanseOwnership over to another team."""

    STATUS_CHOICES = [
        ('pending', 'Afventer (Pending)'),
        ('accepted', 'Accepteret'),
        ('rejected', 'Afvist'),
        ('cancelled', 'Annulleret'),
    ]

    task_ownership = models.ForeignKey(
        "organization.TjanseOwnership",
        on_delete=models.CASCADE,
        related_name="swap_requests"
    )
    requesting_team = models.ForeignKey(
        "organization.Team",
        on_delete=models.CASCADE,
        related_name="requested_tjanse_swaps"
    )
    receiving_team = models.ForeignKey(
        "organization.Team",
        on_delete=models.CASCADE,
        related_name="received_tjanse_swaps"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    resolved_by = models.ForeignKey(
        "organization.Volunteer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Sat hvis en administrator har godkendt/afvist byttet på vegne af modtagerteamet."
    )
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tjanse-bytte"
        verbose_name_plural = "Tjanse-bytter"

    def __str__(self):
        return f"{self.requesting_team} -> {self.receiving_team} ({self.task_ownership})"

    def get_absolute_url(self):
        return reverse("organization_TjanseSwapRequest_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("organization_TjanseSwapRequest_update", args=(self.pk,))

    def accept(self, resolved_by=None):
        """Transfer ownership to the receiving team and mark the swap accepted."""
        self.task_ownership.team = self.receiving_team
        self.task_ownership.save()
        self.status = 'accepted'
        self.resolved_by = resolved_by
        self.save()

    def reject(self, resolved_by=None):
        self.status = 'rejected'
        self.resolved_by = resolved_by
        self.save()
    







