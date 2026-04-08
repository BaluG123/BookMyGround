import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from grounds.models import Ground


class Review(models.Model):
    """Customer review for a ground."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    ground = models.ForeignKey(
        Ground,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True)
    owner_reply = models.TextField(blank=True, help_text='Ground owner can reply')
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reviews'
        ordering = ['-created_at']
        unique_together = ['customer', 'ground']

    def __str__(self):
        return f"{self.customer.full_name} → {self.ground.name} — {self.rating}★"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._update_ground_rating()

    def delete(self, *args, **kwargs):
        ground = self.ground
        super().delete(*args, **kwargs)
        self._update_ground_rating(ground=ground)

    def _update_ground_rating(self, ground=None):
        """Recalculate and cache average rating on the ground."""
        ground = ground or self.ground
        from django.db.models import Avg
        result = Review.objects.filter(ground=ground).aggregate(
            avg=Avg('rating'),
            count=models.Count('id'),
        )
        ground.avg_rating = round(result['avg'] or 0, 2)
        ground.total_reviews = result['count']
        ground.save(update_fields=['avg_rating', 'total_reviews'])
