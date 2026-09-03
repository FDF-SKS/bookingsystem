from django.db import models
from django.urls import reverse
from django.utils import timezone
from organization.models import Team, Volunteer
from datetime import date

class ButikkenItem(models.Model):

    # Relationships
    type = models.CharField(max_length=100)

    # Fields
    description = models.TextField(max_length=500, blank=True)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    name = models.CharField(max_length=100)
    content_normal = models.CharField(max_length=100, blank=True)
    content_unit = models.CharField(max_length=100, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name = "Butiksvare"
        verbose_name_plural = "Butiksvarer"
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Butikken_ButikkenItem_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_ButikkenItem_update", args=(self.pk,))
    
class ButikkenBooking(models.Model):
    

    # Relationships
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE)
    item = models.ForeignKey("Butikken.ButikkenItem", on_delete=models.CASCADE)
    team_contact = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE)
    # Optional parent order (cart). Kept nullable initially; application logic will
    # enforce that new bookings are created as part of an order.
    order = models.ForeignKey(
        "Butikken.ButikkenOrder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bookings",
    )


    # Fields
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Udleveret', 'Udleveret'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')

    start_date = models.DateField(verbose_name='Start')
    start_time = models.TimeField(verbose_name='Start_time')
    date_used = models.DateField(verbose_name='Dato brugt', blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=100)  # Blank allows for an empty value
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    remarks = models.TextField(blank=True)  # Blank allows for an empty value
    remarks_internal = models.TextField(blank=True)  # Blank allows for an empty value

    # Fields
    TYPE_CHOICES = (
        ('Aktivitet', 'Aktivitet'),
        ('Morgenmad', 'Morgenmad'),
        ('Frokost', 'Frokost'),
        ('Aftensmad', 'Aftensmad'),
    )  
    for_meal = models.CharField(max_length=10, choices=TYPE_CHOICES, default='Pending')

    class Meta:
        verbose_name = "Butiksbestilling"
        verbose_name_plural = "Butiksbestillinger"
        pass

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        return reverse("Butikken_ButikkenBooking_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_ButikkenBooking_update", args=(self.pk,))


class ButikkenOrder(models.Model):
    """Parent 'order' / cart that groups multiple ButikkenBooking rows.

    Initially orders are created first and then bookings are added with their
    `order` FK set. The DB field on `ButikkenBooking` is nullable to avoid a
    forced migration on existing data; application logic should require an
    order for new bookings.
    """
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE)
    team_contact = models.ForeignKey(
        "organization.Volunteer", on_delete=models.CASCADE, blank=True, null=True
    )

    STATUS_CHOICES = (
        ("Afventer", "Afventer"),
        ("Godkendt", "Godkendt"),
        ("Afvist", "Afvist"),
        ("Pakket", "Pakket"),
        ("Udleveret", "Udleveret"),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="Afventer")
    # Optional human readable name for the order (can be set by the user)
    name = models.CharField(max_length=200, blank=True, default="")

    order_date = models.DateTimeField(auto_now_add=True, editable=False)
    pickup_date = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Butiksordre"
        verbose_name_plural = "Butiksordrer"

    def __str__(self):
        return f"ButikkenOrder {self.pk} ({self.team})"

    def get_absolute_url(self):
        return reverse("Butikken_ButikkenOrder_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_ButikkenOrder_update", args=(self.pk,))



class ButikkenItemType(models.Model):

    # Fields
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    name = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    description = models.TextField(max_length=500, blank=True)

    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Butikken_ButikkenItemType_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_ButikkenItemType_update", args=(self.pk,))



class Day(models.Model):
    # Fields
    name = models.CharField(max_length=100)
    date = models.DateField()

    created = models.DateTimeField(default=timezone.now, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Butikken_Day_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_Day_update", args=(self.pk,))

class Meal(models.Model):
    DAY_CHOICES = (
        ('Breakfast', 'Breakfast'),
        ('Lunch', 'Lunch'),
        ('Dinner', 'Dinner'),
    )
    # Relationships
    day = models.ForeignKey("Butikken.Day", on_delete=models.CASCADE)
    type = models.CharField(max_length=100, choices=DAY_CHOICES)

    created = models.DateTimeField(default=timezone.now, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        pass

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        return reverse("Butikken_Meal_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_Meal_update", args=(self.pk,))

class Recipe(models.Model):
    
    # Fields
    name = models.CharField(max_length=100)
    description = models.TextField(max_length=200)
    created = models.DateTimeField(default=timezone.now, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Måltidspakke"
        verbose_name_plural = "Måltidspakker"
        pass

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse("Butikken_Recipe_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_Recipe_update", args=(self.pk,))

class Option(models.Model):

    # Relationships
    meal = models.ForeignKey("Butikken.Meal", on_delete=models.CASCADE)
    recipe = models.ForeignKey("Butikken.Recipe", on_delete=models.CASCADE)

    # Fields
    created = models.DateTimeField(default=timezone.now, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        pass

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        return reverse("Butikken_Option_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_Option_update", args=(self.pk,))

class MealBooking(models.Model):

    # Relationships
    team_contact = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE)
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE)

    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    last_updated = models.DateTimeField(auto_now=True, editable=False) 
    created = models.DateTimeField(auto_now_add=True, editable=False)
    

    class Meta:
        pass

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        return reverse("Butikken_MealBooking_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_MealBooking_update", args=(self.pk,))
    



class MealPlan(models.Model):

    # Fields
    name = models.CharField(max_length=100, blank=True)
    meal_date = models.DateField(default=date.today)
    open_date = models.DateTimeField(default=timezone.now)
    close_date = models.DateTimeField(default=timezone.now)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Måltid"
        verbose_name_plural = "Måltider"
        pass

    def __str__(self):
        return f"{self.name}"

    def get_absolute_url(self):
        return reverse("mealplan_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("mealplan_update", args=(self.pk,))

    @staticmethod
    def get_htmx_create_url():
        return reverse("mealplan_htmx_create")

    def get_htmx_delete_url(self):
        return reverse("mealplan_htmx_delete", args=(self.pk,))


class MealOption(models.Model):
    # Relationships
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)

    # Fields
    # name = models.CharField(max_length=100, blank=True)
    # description = models.TextField(max_length=500, blank=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Måltidsvalgmulighed"
        verbose_name_plural = "Måltidsvalgmulighedr"
        pass

    def __str__(self):
        return f"{self.recipe.name}"

    def get_absolute_url(self):
        return reverse("mealoption_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("mealoption_update", args=(self.pk,))

    @staticmethod
    def get_htmx_create_url():
        return reverse("mealoption_htmx_create")

    def get_htmx_delete_url(self):
        return reverse("mealoption_htmx_delete", args=(self.pk,))
    
class TeamMealPlan(models.Model):

    # Relationships
    meal_plan = models.ForeignKey("Butikken.MealPlan", on_delete=models.CASCADE)
    meal_option = models.ForeignKey("Butikken.MealOption", on_delete=models.CASCADE, blank=True, null=True)
    team = models.ForeignKey("organization.Team", on_delete=models.CASCADE)
    team_contact = models.ForeignKey("organization.Volunteer", on_delete=models.CASCADE, blank=True, null=True)
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')

    # Fields
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name = "Måltidsbestilling"
        verbose_name_plural = "Måltidsbestillinger"
        pass

    def __str__(self):
        return str(self.pk)

    def get_absolute_url(self):
        return reverse("Butikken_TeamMealPlan_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("Butikken_TeamMealPlan_update", args=(self.pk,))

    @staticmethod
    def get_htmx_create_url():
        return reverse("Butikken_TeamMealPlan_htmx_create")

    def get_htmx_delete_url(self):
        return reverse("Butikken_TeamMealPlan_htmx_delete", args=(self.pk,))




