import os
from io import BytesIO

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django_tiptap_editor.fields import TipTapJSONField
from PIL import Image
from simple_history.models import HistoricalRecords


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
    discord_topic_thread_id = models.CharField(max_length=64, null=True, blank=True, help_text="ID på Discord-tråden i forumkanalen. Oprettes automatisk.")
    history = HistoricalRecords()



    class Meta:
        pass

    def __str__(self):
        return str(self.name)
    

class VolunteerManager(UserManager):
    """Look users up by their ``USERNAME_FIELD`` (email), case-insensitively."""

    def get_by_natural_key(self, username):
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': username})


class Volunteer(AbstractUser):

    objects = VolunteerManager()

    # Log in with the e-mail address; ``username`` is kept as a secondary,
    # auto-generated identifier for legacy code and imports.
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

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

    @property
    def team_ids(self):
        return set(self.teammembership_set.values_list('team_id', flat=True))

    def is_team_member(self, team_id):
        return team_id in self.team_ids
    
    def save(self, *args, **kwargs):
        old_image_name = old_thumb_name = None
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).only(
                'image', 'image_thumbnail'
            ).first()
            if old:
                old_image_name = old.image.name if old.image else None
                old_thumb_name = old.image_thumbnail.name if old.image_thumbnail else None

        current_image_name = self.image.name if self.image else None
        image_changed = old_image_name != current_image_name

        if image_changed:
            # The stored thumbnail belongs to the previous image.
            self.image_thumbnail = None

        # Generate a thumbnail when a new image is uploaded.
        if self.image and not self.image_thumbnail:
            self._create_thumbnail()

        super().save(*args, **kwargs)

        # Remove files belonging to a replaced/removed image so repeated
        # profile-image changes cannot grow media storage without bound.
        if image_changed:
            image_storage = type(self)._meta.get_field('image').storage
            thumb_storage = type(self)._meta.get_field('image_thumbnail').storage
            if old_image_name:
                image_storage.delete(old_image_name)
            if old_thumb_name:
                thumb_storage.delete(old_thumb_name)
    
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
        except Exception:
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


class VolunteerAppointmentQuerySet(models.QuerySet):
    """Queryset helpers for the visibility rules of legeaftaler."""

    def visible_to(self, user):
        """Return appointments ``user`` is allowed to see.

        A legeaftale is visible to the requester, the receiver, every member of
        the receiving team, and - when shared - the requester's teammates.
        """
        if not user or not user.is_authenticated:
            return self.none()
        if user.is_staff:
            return self
        team_ids = user.teams.values_list('pk', flat=True)
        return self.filter(
            models.Q(requester=user)
            | models.Q(receiver=user)
            | models.Q(receiver_team_id__in=team_ids)
            | models.Q(shared_with_team=True, requester__teams__in=team_ids)
        ).distinct()


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
    # Exactly one of ``receiver`` and ``receiver_team`` is set: either a single
    # person is invited, or the appointment is open to a whole team.
    receiver = models.ForeignKey(
        "organization.Volunteer",
        on_delete=models.CASCADE,
        related_name="received_appointments",
        null=True,
        blank=True,
        verbose_name="Modtager",
    )
    receiver_team = models.ForeignKey(
        "organization.Team",
        on_delete=models.CASCADE,
        related_name="received_appointments",
        null=True,
        blank=True,
        verbose_name="Modtagerteam",
        help_text="Vælg et team i stedet for en bestemt person.",
    )
    shared_with_team = models.BooleanField(
        default=False,
        verbose_name="Delt med afsenderens team",
        help_text="Gør aftalen synlig for alle på afsenderens team.",
    )
    resolved_by = models.ForeignKey(
        "organization.Volunteer",
        on_delete=models.SET_NULL,
        related_name="resolved_appointments",
        null=True,
        blank=True,
        verbose_name="Besvaret af",
        help_text="Den person, der svarede på aftalen - relevant ved teamaftaler.",
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

    objects = VolunteerAppointmentQuerySet.as_manager()

    class Meta:
        verbose_name = "Aftale"
        verbose_name_plural = "Aftaler"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(receiver__isnull=False, receiver_team__isnull=True)
                    | models.Q(receiver__isnull=True, receiver_team__isnull=False)
                ),
                name="appointment_receiver_or_team",
            ),
        ]

    def clean(self):
        super().clean()
        if bool(self.receiver_id) == bool(self.receiver_team_id):
            raise ValidationError(
                "Vælg enten en bestemt person eller et team som modtager."
            )
        if self.receiver_id and self.receiver_id == self.requester_id:
            raise ValidationError({"receiver": "Du kan ikke lave en aftale med dig selv."})

    # -- display -----------------------------------------------------------
    @property
    def is_team_appointment(self) -> bool:
        return self.receiver_team_id is not None

    @property
    def receiver_display(self) -> str:
        if self.receiver_id:
            return self.receiver.get_full_name() or self.receiver.username
        if self.receiver_team_id:
            return f"{self.receiver_team.name} (team)"
        return "-"

    def __str__(self):
        # Get first team for requester
        requester_team = self.requester.teams.first()
        requester_str = f"{self.requester} ({requester_team.short_name})" if requester_team else str(self.requester)

        if self.receiver_id:
            receiver_team = self.receiver.teams.first()
            receiver_str = f"{self.receiver} ({receiver_team.short_name})" if receiver_team else str(self.receiver)
        else:
            receiver_str = f"{self.receiver_team} (team)" if self.receiver_team_id else "?"

        return f"{requester_str} -> {receiver_str}"

    # -- permissions -------------------------------------------------------
    def is_requester(self, user) -> bool:
        return bool(user and user.is_authenticated and user.pk == self.requester_id)

    def is_receiver(self, user) -> bool:
        return bool(
            self.receiver_id
            and user
            and user.is_authenticated
            and user.pk == self.receiver_id
        )

    def is_receiver_team_member(self, user) -> bool:
        if not self.receiver_team_id or not user or not user.is_authenticated:
            return False
        return user.teams.filter(pk=self.receiver_team_id).exists()

    def is_requester_team_member(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return self.requester.teams.filter(pk__in=user.teams.values('pk')).exists()

    def can_view(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        return (
            self.is_requester(user)
            or self.is_receiver(user)
            or self.is_receiver_team_member(user)
            or (self.shared_with_team and self.is_requester_team_member(user))
        )

    def can_respond(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return (
            user.is_staff
            or self.is_receiver(user)
            or self.is_receiver_team_member(user)
        )

    def can_edit(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or self.is_requester(user)

    def role_for(self, user) -> str:
        """Return the viewer's role, used for labels in lists."""
        if self.is_requester(user):
            return 'requester'
        if self.is_receiver(user):
            return 'receiver'
        if self.is_receiver_team_member(user):
            return 'team'
        if user and user.is_authenticated and user.is_staff:
            return 'staff'
        return 'shared'

    def get_absolute_url(self):
        return reverse("organization_VolunteerAppointment_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("organization_VolunteerAppointment_update", args=(self.pk,))


class Tjanse(models.Model):
    """Reusable duty/chore template (e.g. 'Opvask'), assigned to teams per event via TjanseOwnership.

    ``kind`` separates the regular, event-long tjanser from the last-day
    Slutrengøring pool so the two workflows never appear in each other's views.
    """

    KIND_CHOICES = [
        ('regular', 'Almindelig'),
        ('slutrengoring', 'Slutrengøring'),
    ]
    PRIORITY_CHOICES = [
        ('required', 'Påkrævet'),
        ('high', 'Høj'),
        ('medium', 'Mellem'),
        ('low', 'Lav'),
    ]
    PRIORITY_RANK = {
        'required': 0,
        'high': 1,
        'medium': 2,
        'low': 3,
    }

    title = models.CharField(max_length=100)
    description = TipTapJSONField(blank=True, default=dict)
    kind = models.CharField(
        max_length=20, choices=KIND_CHOICES, default='regular', db_index=True
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default='medium', db_index=True
    )
    area = models.CharField(max_length=100, blank=True, db_index=True)
    estimated_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Tjanse"
        ordering = ['order', 'title']

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

    tjanse = models.ForeignKey(
        "organization.Tjanse",
        on_delete=models.CASCADE,
        related_name="ownerships",
        limit_choices_to={'kind': 'regular'},
    )
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

    def clean(self):
        super().clean()
        if self.tjanse_id and self.tjanse.kind != 'regular':
            raise ValidationError(
                {'tjanse': 'Slutrengøringstjanser skal tildeles via slutrengøringsmodulet.'}
            )

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


class SlutrengoringAssignment(models.Model):
    """One executable Slutrengøring task for a single event.

    A row starts as ``available`` (team is NULL) and can be claimed by a team.
    The nullable team and claimable states are what distinguish this workflow
    from the regular ``TjanseOwnership`` model.
    """

    STATUS_CHOICES = [
        ('available', 'Ledig'),
        ('assigned', 'Tildelt'),
        ('in_progress', 'I gang'),
        ('done', 'Udført'),
        ('not_finished', 'Ikke udført'),
    ]
    ACTIVE_STATUSES = ('assigned', 'in_progress')
    CLAIMABLE_STATUSES = ('available', 'not_finished')

    tjanse = models.ForeignKey(
        "organization.Tjanse",
        on_delete=models.CASCADE,
        related_name="slutrengoring_assignments",
        limit_choices_to={'kind': 'slutrengoring'},
    )
    event = models.ForeignKey(
        "organization.Event",
        on_delete=models.CASCADE,
        related_name="slutrengoring_assignments",
    )
    team = models.ForeignKey(
        "organization.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slutrengoring_assignments",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='available', db_index=True
    )

    assigned_by = models.ForeignKey(
        "organization.Volunteer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        "organization.Volunteer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    not_finished_at = models.DateTimeField(null=True, blank=True)
    not_finished_reason = models.TextField(blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    last_team = models.ForeignKey(
        "organization.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Slutrengøringstildeling"
        verbose_name_plural = "Slutrengøringstildelinger"
        constraints = [
            models.UniqueConstraint(
                fields=['tjanse', 'event'],
                name='unique_slutrengoring_task_per_event',
            ),
        ]
        indexes = [
            models.Index(fields=['event', 'status'], name='slutreng_event_status_idx'),
            models.Index(fields=['event', 'team', 'status'], name='slutreng_event_team_status_idx'),
        ]

    def __str__(self):
        owner = self.team.name if self.team_id else 'Ledig'
        return f"{self.tjanse.title} - {owner} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if self.tjanse_id and self.tjanse.kind != 'slutrengoring':
            raise ValidationError(
                {'tjanse': 'Kun tjanser af typen Slutrengøring kan tildeles her.'}
            )

    def save(self, *args, **kwargs):
        """Keep timestamps coherent when staff edit rows from the admin."""
        if self.status in self.ACTIVE_STATUSES and self.team_id and self.assigned_at is None:
            self.assigned_at = timezone.now()
        if self.status == 'in_progress' and self.started_at is None:
            self.started_at = timezone.now()
        if self.status == 'done' and self.completed_at is None:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_claimable(self):
        return self.team_id is None and self.status in self.CLAIMABLE_STATUSES

    @property
    def priority(self):
        return self.tjanse.priority

    def get_absolute_url(self):
        return reverse("organization_Slutrengoring_detail", args=(self.pk,))

