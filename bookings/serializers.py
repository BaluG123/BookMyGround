from rest_framework import serializers
from django.utils import timezone
from .models import TimeSlot, Booking, Payment
from grounds.models import Ground, PricingPlan
from accounts.serializers import UserMiniSerializer


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
            'transaction_id', 'status', 'paid_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['amount', 'payment_method', 'transaction_id', 'status', 'paid_at']


# ─── Booking Serializers ───────────────────────────────────────

class BookingListSerializer(serializers.ModelSerializer):
    ground_name = serializers.CharField(source='ground.name', read_only=True)
    ground_city = serializers.CharField(source='ground.city', read_only=True)
    ground_image = serializers.SerializerMethodField()
    customer_info = UserMiniSerializer(source='customer', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'ground', 'ground_name', 'ground_city',
            'ground_image', 'customer_info',
            'booking_date', 'start_time', 'end_time', 'duration_hours',
            'total_amount', 'status', 'status_display',
            'payment_status', 'payment_status_display',
            'created_at',
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


class BookingDetailSerializer(serializers.ModelSerializer):
    ground_name = serializers.CharField(source='ground.name', read_only=True)
    ground_address = serializers.CharField(source='ground.address', read_only=True)
    ground_city = serializers.CharField(source='ground.city', read_only=True)
    customer_info = UserMiniSerializer(source='customer', read_only=True)
    time_slot_info = TimeSlotSerializer(source='time_slot', read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)

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
            'customer_name', 'customer_phone', 'notes',
            'cancellation_reason', 'cancelled_by',
            'payments',
            'created_at', 'updated_at',
        ]


class BookingCreateSerializer(serializers.ModelSerializer):
    """Create a new booking (customer only)."""

    class Meta:
        model = Booking
        fields = [
            'ground', 'time_slot', 'pricing_plan',
            'booking_date', 'start_time', 'end_time',
            'duration_hours', 'total_amount',
            'customer_name', 'customer_phone', 'notes',
        ]

    def validate(self, data):
        ground = data['ground']
        if not ground.is_active:
            raise serializers.ValidationError('This ground is not available for booking.')

        # Check slot availability if provided
        time_slot = data.get('time_slot')
        if time_slot:
            if time_slot.ground != ground:
                raise serializers.ValidationError('Time slot does not belong to this ground.')
            if not time_slot.is_bookable:
                raise serializers.ValidationError('This time slot is not available.')

        # Check for duplicate bookings
        existing = Booking.objects.filter(
            ground=ground,
            booking_date=data['booking_date'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            status__in=['pending', 'confirmed'],
        ).exists()
        if existing:
            raise serializers.ValidationError('This slot is already booked.')

        return data

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        booking = Booking.objects.create(**validated_data)

        # Mark time slot as booked
        if booking.time_slot:
            booking.time_slot.is_booked = True
            booking.time_slot.save()

        # Update ground booking count
        booking.ground.total_bookings += 1
        booking.ground.save(update_fields=['total_bookings'])

        return booking
