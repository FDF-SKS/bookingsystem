import uuid

from django.db import models
from django.urls import reverse
from django.db.models import Max
from map_location.fields import LocationField

from organization.models import Event, Team, Volunteer


class Loeb(models.Model):
    name = models.CharField(max_length=120, db_index=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='loeb_runs')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='loeb_runs', null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    show_map = models.BooleanField(default=True)
    show_points = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('Loeb_Loeb_detail', args=(self.pk,))

    def get_update_url(self):
        return reverse('Loeb_Loeb_update', args=(self.pk,))


class PhysicalStation(models.Model):
    name = models.CharField(max_length=120)
    qr_code = models.CharField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    location = LocationField(
        'Lokation',
        blank=True,
        null=True,
        default='56.113991,9.665244',
        options={
            'map': {'center': [56.113991, 9.665244], 'zoom': 13},
            'marker': {'draggable': True, 'position': [56.113991, 9.665244]},
        },
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = self.generate_qr_code()
        super().save(*args, **kwargs)

    @classmethod
    def generate_qr_code(cls):
        while True:
            candidate = f'station-{uuid.uuid4().hex[:12]}'
            if not cls.objects.filter(qr_code=candidate).exists():
                return candidate

    def get_absolute_url(self):
        return reverse('Loeb_PhysicalStation_detail', args=(self.pk,))

    def get_full_url(self, request=None):
        url = self.get_absolute_url()
        if request is not None:
            return request.build_absolute_uri(url)
        return f"{self._base_url()}{url}"

    def _base_url(self):
        from django.conf import settings
        site_url = getattr(settings, 'SITE_URL', None) or getattr(settings, 'BASE_URL', None)
        if site_url:
            return site_url.rstrip('/')
        return 'http://127.0.0.1:8000'

    @property
    def coords_list(self):
        if self.location:
            try:
                parts = str(self.location).split(',')
                return [float(parts[0]), float(parts[1])]
            except (ValueError, IndexError):
                return [56.113991, 9.665244]
        return [56.113991, 9.665244]


class Task(models.Model):
    TASK_TYPE_CHOICES = (
        ('virtual', 'Virtuel GPS-opgave'),
        ('qr', 'QR-station'),
        ('physical', 'Fysisk opgave'),
        ('manned', 'Bemandet station'),
    )

    loeb = models.ForeignKey(Loeb, on_delete=models.CASCADE, related_name='tasks', verbose_name='Løb')
    title = models.CharField(max_length=150, verbose_name='Titel')
    description = models.TextField(blank=True, verbose_name='Beskrivelse')
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES, default='physical', verbose_name='Type')
    station = models.ForeignKey('PhysicalStation', on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks', verbose_name='Station')
    location = LocationField(
        'Kortplacering',
        blank=True,
        null=True,
        default='56.113991,9.665244',
        options={
            'map': {'center': [56.113991, 9.665244], 'zoom': 13},
            'marker': {'draggable': True, 'position': [56.113991, 9.665244]},
        },
    )
    gps_latitude = models.FloatField(null=True, blank=True, verbose_name='GPS-breddegrad')
    gps_longitude = models.FloatField(null=True, blank=True, verbose_name='GPS-længdegrad')
    gps_radius_meters = models.IntegerField(default=30, verbose_name='GPS-radius (meter)')
    qr_code = models.CharField(max_length=200, blank=True, verbose_name='QR-kode')
    points = models.IntegerField(default=0, verbose_name='Point')
    input_mode = models.CharField(max_length=20, default='none', verbose_name='Inputtype')
    is_published = models.BooleanField(default=False, db_index=True)
    copied_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='clones')
    order = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('Loeb_Task_detail', args=(self.pk,))

    def get_update_url(self):
        return reverse('Loeb_Task_update', args=(self.pk,))

    @property
    def coords_list(self):
        if self.location:
            try:
                parts = str(self.location).split(',')
                return [float(parts[0]), float(parts[1])]
            except (ValueError, IndexError):
                return [56.113991, 9.665244]
        return [56.113991, 9.665244]

    @classmethod
    def next_order_for_loeb(cls, loeb):
        return (cls.objects.filter(loeb=loeb).aggregate(max_order=Max('order'))['max_order'] or 0) + 1


class Hold(models.Model):
    loeb = models.ForeignKey(Loeb, on_delete=models.CASCADE, related_name='holds')
    name = models.CharField(max_length=120)
    pin_code = models.CharField(max_length=20, unique=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.pin_code})'

    def get_absolute_url(self):
        return reverse('Loeb_Loeb_detail', args=(self.loeb_id,))


class TaskSubmission(models.Model):
    STATE_CHOICES = (
        ('UNLOCKED', 'Unlocked'),
        ('SUBMITTED', 'Submitted'),
        ('GRADED', 'Graded'),
    )

    hold = models.ForeignKey(Hold, on_delete=models.CASCADE, related_name='task_submissions')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='submissions')
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default='UNLOCKED')
    submitted_answer = models.TextField(blank=True)
    points_awarded = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        unique_together = ('hold', 'task')
        ordering = ['-last_updated']

    def __str__(self):
        return f'{self.hold} - {self.task}'
