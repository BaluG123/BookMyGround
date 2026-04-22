import uuid
from django.db import models
from django.conf import settings
from grounds.models import Ground, PricingPlan


class TimeSlot(models.Model):
    """Available time slots for a ground, created by the admin/owner."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ground = models.ForeignKey(Ground, on_delete=models.CASCADE, related_name='time_slots')
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)
    is_booked = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_slots',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'time_slots'
        ordering = ['date', 'start_time']
        unique_together = ['ground', 'date', 'start_time', 'end_time']

    def __str__(self):
        return f"{self.ground.name} | {self.date} | {self.start_time}-{self.end_time}"

    @property
    def is_bookable(self):
        return self.is_available and not self.is_booked


class PromoCode(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ('flat', 'Flat'),
        ('percentage', 'Percentage'),
    )

    code = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=180, blank=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, default='flat')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_booking_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(default=1)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_promo_codes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'promo_codes'
        ordering = ['code']

    def __str__(self):
        return self.code


class Booking(models.Model):
    """A booking made by a customer for a ground."""

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('no_show', 'No Show'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    ground = models.ForeignKey(
        Ground, on_delete=models.CASCADE, related_name='bookings'
    )
    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings'
    )
    pricing_plan = models.ForeignKey(
        PricingPlan, on_delete=models.SET_NULL, null=True, blank=True
    )
    booking_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_hours = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    applied_promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
    )
    promo_code_snapshot = models.CharField(max_length=32, blank=True)
    referral_code_used = models.CharField(max_length=16, blank=True)
    referral_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_bookings',
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(
        max_length=15, choices=PAYMENT_STATUS_CHOICES, default='pending'
    )
    customer_name = models.CharField(max_length=150, blank=True)
    customer_phone = models.CharField(max_length=15, blank=True)
    player_count = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)
    special_requests = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.CharField(max_length=10, blank=True)  # 'customer' or 'admin'
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bookings'
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.booking_number} — {self.ground.name} — {self.booking_date}"

    def save(self, *args, **kwargs):
        if not self.booking_number:
            import random
            import string
            self.booking_number = 'BMG' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )
        super().save(*args, **kwargs)

    @property
    def outstanding_amount(self):
        paid_amount = sum(
            payment.amount for payment in self.payments.filter(status='success')
        )
        return max(self.total_amount - paid_amount, 0)


class BookingSlot(models.Model):
    """Links a booking to one or more concrete time slots."""

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='booking_slots')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='booking_links')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'booking_slots'
        ordering = ['time_slot__date', 'time_slot__start_time']
        unique_together = ['booking', 'time_slot']

    def __str__(self):
        return f"{self.booking.booking_number} -> {self.time_slot}"


class Payment(models.Model):
    """Payment record for a booking."""

    PAYMENT_METHOD_CHOICES = (
        ('online', 'Online'),
        ('upi', 'UPI'),
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('wallet', 'Wallet'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=100, blank=True, unique=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    platform_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Platform fee (e.g. 29 INR)')
    owner_share = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Amount to be paid to the owner')
    gateway_response = models.JSONField(blank=True, null=True, help_text='Raw response from payment gateway')
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.transaction_id} — ₹{self.amount} — {self.status}"


class PaymentOrder(models.Model):
    """Gateway order created before collecting payment."""

    STATUS_CHOICES = (
        ('created', 'Created'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payment_orders')
    gateway = models.CharField(max_length=30, default='razorpay')
    gateway_order_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.gateway} {self.gateway_order_id} - {self.status}"
