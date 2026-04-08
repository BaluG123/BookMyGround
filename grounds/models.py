import uuid
from django.db import models
from django.conf import settings


class Amenity(models.Model):
    """Amenities available at a ground (parking, floodlights, etc)."""

    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Icon name for frontend')

    class Meta:
        db_table = 'amenities'
        verbose_name_plural = 'Amenities'
        ordering = ['name']

    def __str__(self):
        return self.name


class Ground(models.Model):
    """A ground or turf managed by an admin user."""

    GROUND_TYPE_CHOICES = (
        ('cricket', 'Cricket'),
        ('football', 'Football'),
        ('badminton', 'Badminton'),
        ('tennis', 'Tennis'),
        ('basketball', 'Basketball'),
        ('volleyball', 'Volleyball'),
        ('hockey', 'Hockey'),
        ('multi_sport', 'Multi Sport'),
        ('other', 'Other'),
    )

    SURFACE_CHOICES = (
        ('natural_grass', 'Natural Grass'),
        ('artificial_turf', 'Artificial Turf'),
        ('clay', 'Clay'),
        ('concrete', 'Concrete'),
        ('synthetic', 'Synthetic'),
        ('wooden', 'Wooden'),
        ('other', 'Other'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_grounds',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    ground_type = models.CharField(max_length=20, choices=GROUND_TYPE_CHOICES)
    surface_type = models.CharField(max_length=20, choices=SURFACE_CHOICES, default='natural_grass')
    address = models.TextField()
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='grounds')
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    max_players = models.PositiveIntegerField(default=22, help_text='Max players allowed at once')
    rules = models.TextField(blank=True, help_text='Ground rules & policies')
    cancellation_policy = models.TextField(blank=True)
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.PositiveIntegerField(default=0)
    total_bookings = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'grounds'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.city}"


class GroundImage(models.Model):
    """Images for a ground."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ground = models.ForeignKey(Ground, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='grounds/')
    is_primary = models.BooleanField(default=False)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ground_images'
        ordering = ['-is_primary', '-uploaded_at']

    def __str__(self):
        return f"Image for {self.ground.name}"


class PricingPlan(models.Model):
    """Pricing plans for a ground (per hour, half day, etc)."""

    DURATION_CHOICES = (
        ('per_hour', 'Per Hour'),
        ('two_hours', '2 Hours'),
        ('three_hours', '3 Hours'),
        ('half_day', 'Half Day (5 Hours)'),
        ('full_day', 'Full Day (10 Hours)'),
        ('custom', 'Custom Duration'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ground = models.ForeignKey(Ground, on_delete=models.CASCADE, related_name='pricing_plans')
    duration_type = models.CharField(max_length=20, choices=DURATION_CHOICES)
    duration_hours = models.DecimalField(max_digits=5, decimal_places=2, help_text='Duration in hours')
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Price in INR')
    weekend_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Weekend/holiday price (leave blank to use regular price)',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pricing_plans'
        ordering = ['duration_hours']
        unique_together = ['ground', 'duration_type']

    def __str__(self):
        return f"{self.ground.name} — {self.get_duration_type_display()} — ₹{self.price}"

    @property
    def effective_weekend_price(self):
        return self.weekend_price or self.price


class Favorite(models.Model):
    """Customer's favorite/saved grounds."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites',
    )
    ground = models.ForeignKey(Ground, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'favorites'
        unique_together = ['customer', 'ground']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.full_name} → {self.ground.name}"
