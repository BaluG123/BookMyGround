from rest_framework import serializers
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from .models import TimeSlot, Booking, Payment, PaymentOrder
from grounds.models import Ground, PricingPlan
from accounts.serializers import UserMiniSerializer


TWOPLACES = Decimal('0.01')


def calculate_duration_hours(start_time, end_time):
    start_dt = datetime.combine(timezone.now().date(), start_time)
    end_dt = datetime.combine(timezone.now().date(), end_time)
    seconds = (end_dt - start_dt).total_seconds()
    return (Decimal(seconds) / Decimal('3600')).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def resolve_booking_price(ground, booking_date, duration_hours, pricing_plan=None):
    weekend_booking = booking_date.weekday() >= 5

    if pricing_plan:
        if pricing_plan.ground_id != ground.id:
            raise serializers.ValidationError({'pricing_plan': 'Pricing plan does not belong to this ground.'})
        if not pricing_plan.is_active:
            raise serializers.ValidationError({'pricing_plan': 'Selected pricing plan is inactive.'})
        if pricing_plan.duration_hours != duration_hours:
            raise serializers.ValidationError(
                {'pricing_plan': 'Selected pricing plan does not match the requested duration.'}
            )
        amount = pricing_plan.effective_weekend_price if weekend_booking else pricing_plan.price
        return pricing_plan, Decimal(amount).quantize(TWOPLACES)

    matching_plan = ground.pricing_plans.filter(
        is_active=True,
        duration_hours=duration_hours,
    ).order_by('price').first()
    if matching_plan:
        amount = matching_plan.effective_weekend_price if weekend_booking else matching_plan.price
        return matching_plan, Decimal(amount).quantize(TWOPLACES)

    hourly_plan = ground.pricing_plans.filter(
        is_active=True,
        duration_type='per_hour',
    ).order_by('price').first()
    if hourly_plan:
        hourly_rate = hourly_plan.effective_weekend_price if weekend_booking else hourly_plan.price
        amount = (Decimal(hourly_rate) * duration_hours).quantize(TWOPLACES)
        return hourly_plan, amount

    raise serializers.ValidationError(
        {'pricing_plan': 'No active pricing plan is available for the selected duration.'}
    )


# ─── Time Slot Serializers ──────────────────────────────────────

class TimeSlotSerializer(serializers.ModelSerializer):
    is_bookable = serializers.BooleanField(read_only=True)

    class Meta:
        model = TimeSlot
        fields = [
            'id', 'ground', 'date', 'start_time', 'end_time',
            'is_available', 'is_booked', 'is_bookable', 'created_at',
        ]
        read_only_fields = ['id', 'is_booked', 'created_at']


class TimeSlotBulkCreateSerializer(serializers.Serializer):
    """Create multiple time slots at once for a ground."""

    ground_id = serializers.UUIDField()
    date = serializers.DateField()
    slots = serializers.ListField(
        child=serializers.DictField(),
        help_text='List of {"start_time": "06:00", "end_time": "07:00"}',
    )

    def validate_ground_id(self, value):
        request = self.context.get('request')
        try:
            ground = Ground.objects.get(pk=value, owner=request.user)
        except Ground.DoesNotExist:
            raise serializers.ValidationError('Ground not found or you are not the owner.')
        return value

    def validate_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError('Cannot create slots for past dates.')
        return value

    def validate_slots(self, value):
        if not value:
            raise serializers.ValidationError('At least one slot is required.')
        for slot in value:
            if 'start_time' not in slot or 'end_time' not in slot:
                raise serializers.ValidationError('Each slot must have start_time and end_time.')
        return value

    def create(self, validated_data):
        ground = Ground.objects.get(pk=validated_data['ground_id'])
        date = validated_data['date']
        created_slots = []
        for slot_data in validated_data['slots']:
            slot, created = TimeSlot.objects.get_or_create(
                ground=ground,
                date=date,
                start_time=slot_data['start_time'],
                end_time=slot_data['end_time'],
                defaults={
                    'is_available': True,
                    'created_by': self.context['request'].user,
                },
            )
            created_slots.append(slot)
        return created_slots


# ─── Payment Serializer ────────────────────────────────────────

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'booking', 'amount', 'payment_method',
            'transaction_id', 'status', 'gateway_response', 'paid_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PaymentOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentOrder
        fields = [
            'id', 'gateway', 'gateway_order_id', 'amount',
            'currency', 'status', 'raw_response', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_method', 'transaction_id', 'status', 'paid_at', 'gateway_response']


class PaymentOrderCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class PaymentUpiIntentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class PaymentVerifySerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()
    payment_method = serializers.ChoiceField(
        choices=Payment.PAYMENT_METHOD_CHOICES,
        default='online',
        required=False,
    )
    gateway_response = serializers.JSONField(required=False)


# ─── Booking Serializers ───────────────────────────────────────

class BookingListSerializer(serializers.ModelSerializer):
    ground_name = serializers.CharField(source='ground.name', read_only=True)
    ground_city = serializers.CharField(source='ground.city', read_only=True)
    ground_image = serializers.SerializerMethodField()
    customer_info = UserMiniSerializer(source='customer', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    outstanding_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'ground', 'ground_name', 'ground_city',
            'ground_image', 'customer_info',
            'booking_date', 'start_time', 'end_time', 'duration_hours',
            'total_amount', 'status', 'status_display',
            'payment_status', 'payment_status_display',
            'outstanding_amount', 'can_cancel', 'created_at',
        ]

    def get_ground_image(self, obj):
        img = obj.ground.images.filter(is_primary=True).first()
        if not img:
            img = obj.ground.images.first()
        if img and img.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(img.image.url)
            return img.image.url
        return None

    def get_can_cancel(self, obj):
        return obj.status not in ('cancelled', 'completed')


class BookingDetailSerializer(serializers.ModelSerializer):
    ground_name = serializers.CharField(source='ground.name', read_only=True)
    ground_address = serializers.CharField(source='ground.address', read_only=True)
    ground_city = serializers.CharField(source='ground.city', read_only=True)
    customer_info = UserMiniSerializer(source='customer', read_only=True)
    time_slot_info = TimeSlotSerializer(source='time_slot', read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    outstanding_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    can_cancel = serializers.SerializerMethodField()
    can_confirm = serializers.SerializerMethodField()
    can_complete = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number',
            'customer', 'customer_info',
            'ground', 'ground_name', 'ground_address', 'ground_city',
            'time_slot', 'time_slot_info', 'pricing_plan',
            'booking_date', 'start_time', 'end_time', 'duration_hours',
            'total_amount',
            'status', 'status_display',
            'payment_status', 'payment_status_display',
            'customer_name', 'customer_phone', 'player_count', 'notes',
            'special_requests',
            'cancellation_reason', 'cancelled_by',
            'outstanding_amount', 'can_cancel', 'can_confirm', 'can_complete',
            'payments',
            'created_at', 'updated_at',
        ]

    def get_can_cancel(self, obj):
        return obj.status not in ('cancelled', 'completed')

    def get_can_confirm(self, obj):
        return obj.status == 'pending'

    def get_can_complete(self, obj):
        return obj.status in ('pending', 'confirmed')


class BookingCreateSerializer(serializers.ModelSerializer):
    """Create a new booking (customer only)."""

    class Meta:
        model = Booking
        fields = [
            'ground', 'time_slot', 'pricing_plan',
            'booking_date', 'start_time', 'end_time',
            'duration_hours', 'total_amount',
            'customer_name', 'customer_phone', 'player_count', 'notes',
            'special_requests',
        ]
        extra_kwargs = {
            'duration_hours': {'required': False},
            'total_amount': {'required': False},
        }

    def validate(self, data):
        ground = data['ground']
        if not ground.is_active:
            raise serializers.ValidationError('This ground is not available for booking.')

        booking_date = data['booking_date']
        start_time = data['start_time']
        end_time = data['end_time']

        if booking_date < timezone.localdate():
            raise serializers.ValidationError({'booking_date': 'Booking date cannot be in the past.'})
        if start_time >= end_time:
            raise serializers.ValidationError({'end_time': 'End time must be after start time.'})
        if start_time < ground.opening_time or end_time > ground.closing_time:
            raise serializers.ValidationError(
                {'start_time': 'Booking time must fall within ground operating hours.'}
            )

        if booking_date == timezone.localdate() and start_time <= timezone.localtime().time():
            raise serializers.ValidationError({'start_time': 'Start time must be later than the current time.'})

        player_count = data.get('player_count', 1)
        if player_count > ground.max_players:
            raise serializers.ValidationError(
                {'player_count': f'Maximum allowed players for this ground is {ground.max_players}.'}
            )

        # Check slot availability if provided
        time_slot = data.get('time_slot')
        if time_slot:
            if time_slot.ground != ground:
                raise serializers.ValidationError('Time slot does not belong to this ground.')
            if not time_slot.is_bookable:
                raise serializers.ValidationError('This time slot is not available.')
            if time_slot.date != booking_date:
                raise serializers.ValidationError({'time_slot': 'Time slot date does not match booking date.'})
            if time_slot.start_time != start_time or time_slot.end_time != end_time:
                raise serializers.ValidationError({'time_slot': 'Time slot timing does not match booking times.'})

        duration_hours = calculate_duration_hours(start_time, end_time)
        if duration_hours <= 0:
            raise serializers.ValidationError('Booking duration must be greater than zero.')
        data['duration_hours'] = duration_hours

        resolved_plan, total_amount = resolve_booking_price(
            ground=ground,
            booking_date=booking_date,
            duration_hours=duration_hours,
            pricing_plan=data.get('pricing_plan'),
        )
        data['pricing_plan'] = resolved_plan
        data['total_amount'] = total_amount

        overlapping_bookings = Booking.objects.filter(
            ground=ground,
            booking_date=booking_date,
            status__in=['pending', 'confirmed'],
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if self.instance:
            overlapping_bookings = overlapping_bookings.exclude(pk=self.instance.pk)
        if overlapping_bookings.exists():
            raise serializers.ValidationError('This time range overlaps with an existing booking.')

        return data

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        with transaction.atomic():
            time_slot = validated_data.get('time_slot')
            if time_slot:
                time_slot = TimeSlot.objects.select_for_update().get(pk=time_slot.pk)
                if not time_slot.is_bookable:
                    raise serializers.ValidationError({'time_slot': 'This time slot is no longer available.'})
                validated_data['time_slot'] = time_slot

            overlapping_exists = Booking.objects.select_for_update().filter(
                ground=validated_data['ground'],
                booking_date=validated_data['booking_date'],
                status__in=['pending', 'confirmed'],
                start_time__lt=validated_data['end_time'],
                end_time__gt=validated_data['start_time'],
            ).exists()
            if overlapping_exists:
                raise serializers.ValidationError('This time range has just been booked by another user.')

            booking = Booking.objects.create(**validated_data)

            if booking.time_slot:
                booking.time_slot.is_booked = True
                booking.time_slot.save(update_fields=['is_booked', 'updated_at'])

            booking.ground.total_bookings += 1
            booking.ground.save(update_fields=['total_bookings'])

        return booking
