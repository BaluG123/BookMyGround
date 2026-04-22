from rest_framework import serializers
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from .models import TimeSlot, PromoCode, Booking, BookingSlot, Payment, PaymentOrder
from grounds.models import Ground, PricingPlan
from accounts.models import User
from accounts.serializers import UserMiniSerializer


TWOPLACES = Decimal('0.01')
REFERRAL_DISCOUNT_PERCENT = Decimal('10.00')
REFERRAL_DISCOUNT_CAP = Decimal('150.00')


def calculate_duration_hours(start_time, end_time):
    start_dt = datetime.combine(timezone.now().date(), start_time)
    end_dt = datetime.combine(timezone.now().date(), end_time)
    seconds = (end_dt - start_dt).total_seconds()
    return (Decimal(seconds) / Decimal('3600')).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def normalize_code(value):
    return (value or '').strip().upper()


def resolve_booking_price(ground, booking_date, duration_hours, pricing_plan=None):
    weekend_booking = booking_date.weekday() >= 5

    # If a pricing plan is provided but doesn't match duration, ignore it and auto-select
    if pricing_plan:
        if pricing_plan.ground_id != ground.id:
            raise serializers.ValidationError({'pricing_plan': 'Pricing plan does not belong to this ground.'})
        if not pricing_plan.is_active:
            raise serializers.ValidationError({'pricing_plan': 'Selected pricing plan is inactive.'})
        if pricing_plan.duration_hours != duration_hours:
            # Don't fail - just ignore the provided plan and auto-select below
            pricing_plan = None
        else:
            # Pricing plan matches - use it
            amount = pricing_plan.effective_weekend_price if weekend_booking else pricing_plan.price
            amount = Decimal(amount).quantize(TWOPLACES)
    
    if not pricing_plan:
        matching_plan = ground.pricing_plans.filter(
            is_active=True,
            duration_hours=duration_hours,
        ).order_by('price').first()
        if matching_plan:
            amount = matching_plan.effective_weekend_price if weekend_booking else matching_plan.price
            amount = Decimal(amount).quantize(TWOPLACES)
            pricing_plan = matching_plan
        else:
            hourly_plan = ground.pricing_plans.filter(
                is_active=True,
                duration_type='per_hour',
            ).order_by('price').first()
            if not hourly_plan:
                raise serializers.ValidationError(
                    {'pricing_plan': 'No active pricing plan available for this duration.'}
                )

            hourly_rate = hourly_plan.effective_weekend_price if weekend_booking else hourly_plan.price
            amount = (Decimal(hourly_rate) * duration_hours).quantize(TWOPLACES)
            pricing_plan = hourly_plan

    if amount < Decimal('100.00'):
        raise serializers.ValidationError(
            {'amount': 'Minimum booking price must be at least 100 INR.'}
        )

    return pricing_plan, amount


def resolve_discount_breakdown(*, user, base_amount, promo_code_value='', referral_code_value='', current_booking=None):
    base_amount = Decimal(base_amount).quantize(TWOPLACES)
    total_discount = Decimal('0.00')
    applied_promo = None
    promo_snapshot = ''
    referral_snapshot = ''
    referral_owner = None

    promo_code_value = normalize_code(promo_code_value)
    referral_code_value = normalize_code(referral_code_value)

    if promo_code_value:
        try:
            applied_promo = PromoCode.objects.get(code=promo_code_value)
        except PromoCode.DoesNotExist:
            raise serializers.ValidationError({'promo_code': 'Promo code is invalid.'})

        now = timezone.now()
        if not applied_promo.is_active:
            raise serializers.ValidationError({'promo_code': 'Promo code is inactive.'})
        if applied_promo.starts_at and applied_promo.starts_at > now:
            raise serializers.ValidationError({'promo_code': 'Promo code is not live yet.'})
        if applied_promo.ends_at and applied_promo.ends_at < now:
            raise serializers.ValidationError({'promo_code': 'Promo code has expired.'})
        if base_amount < applied_promo.min_booking_amount:
            raise serializers.ValidationError(
                {'promo_code': f'Promo code requires a minimum booking amount of Rs. {applied_promo.min_booking_amount}.'}
            )

        promo_usage_qs = Booking.objects.filter(applied_promo_code=applied_promo).exclude(status='cancelled')
        if current_booking:
            promo_usage_qs = promo_usage_qs.exclude(pk=current_booking.pk)
        if applied_promo.max_uses and promo_usage_qs.count() >= applied_promo.max_uses:
            raise serializers.ValidationError({'promo_code': 'Promo code usage limit has been reached.'})

        user_usage_qs = promo_usage_qs.filter(customer=user)
        if applied_promo.per_user_limit and user_usage_qs.count() >= applied_promo.per_user_limit:
            raise serializers.ValidationError({'promo_code': 'You have already used this promo code.'})

        if applied_promo.discount_type == 'percentage':
            promo_discount = (base_amount * applied_promo.discount_value / Decimal('100')).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        else:
            promo_discount = Decimal(applied_promo.discount_value).quantize(TWOPLACES)

        if applied_promo.max_discount_amount:
            promo_discount = min(promo_discount, Decimal(applied_promo.max_discount_amount).quantize(TWOPLACES))

        total_discount += min(promo_discount, base_amount)
        promo_snapshot = applied_promo.code

    if referral_code_value:
        try:
            referral_owner = User.objects.get(referral_code=referral_code_value)
        except User.DoesNotExist:
            raise serializers.ValidationError({'referral_code': 'Referral code is invalid.'})

        if referral_owner.pk == user.pk:
            raise serializers.ValidationError({'referral_code': 'You cannot use your own referral code.'})

        prior_booking_qs = Booking.objects.filter(customer=user).exclude(status='cancelled')
        if current_booking:
            prior_booking_qs = prior_booking_qs.exclude(pk=current_booking.pk)
        if prior_booking_qs.exists():
            raise serializers.ValidationError({'referral_code': 'Referral pricing is only available on the first active booking.'})

        if user.referred_by_id and user.referred_by_id != referral_owner.pk:
            raise serializers.ValidationError({'referral_code': 'This account is already linked to a different referral owner.'})

        referral_discount = (base_amount * REFERRAL_DISCOUNT_PERCENT / Decimal('100')).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        referral_discount = min(referral_discount, REFERRAL_DISCOUNT_CAP)
        total_discount += min(referral_discount, max(base_amount - total_discount, Decimal('0.00')))
        referral_snapshot = referral_owner.referral_code

    total_discount = min(total_discount, base_amount).quantize(TWOPLACES)
    final_amount = (base_amount - total_discount).quantize(TWOPLACES)
    if final_amount < Decimal('100.00'):
        raise serializers.ValidationError(
            {'amount': 'Booking total after discounts must remain at least 100 INR.'}
        )

    return {
        'base_amount': base_amount,
        'discount_amount': total_discount,
        'total_amount': final_amount,
        'applied_promo_code': applied_promo,
        'promo_code_snapshot': promo_snapshot,
        'referral_code_used': referral_snapshot,
        'referral_owner': referral_owner,
    }


class TimeSlotSerializer(serializers.ModelSerializer):
    is_bookable = serializers.BooleanField(read_only=True)

    class Meta:
        model = TimeSlot
        fields = [
            'id', 'ground', 'date', 'start_time', 'end_time',
            'is_available', 'is_booked', 'is_bookable', 'created_at',
        ]
        read_only_fields = ['id', 'is_booked', 'created_at']


class BookingSlotSerializer(serializers.ModelSerializer):
    time_slot = TimeSlotSerializer(read_only=True)

    class Meta:
        model = BookingSlot
        fields = ['id', 'time_slot', 'created_at']
        read_only_fields = fields


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


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'booking', 'amount', 'payment_method',
            'transaction_id', 'status', 'platform_commission', 'owner_share',
            'gateway_response', 'paid_at', 'created_at',
        ]
        read_only_fields = ['id', 'platform_commission', 'owner_share', 'created_at']


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


class BookingListSerializer(serializers.ModelSerializer):
    ground_name = serializers.CharField(source='ground.name', read_only=True)
    ground_city = serializers.CharField(source='ground.city', read_only=True)
    ground_image = serializers.SerializerMethodField()
    customer_info = UserMiniSerializer(source='customer', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    outstanding_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    can_cancel = serializers.SerializerMethodField()
    slot_count = serializers.SerializerMethodField()
    promo_code_display = serializers.CharField(source='promo_code_snapshot', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number', 'ground', 'ground_name', 'ground_city',
            'ground_image', 'customer_info',
            'booking_date', 'start_time', 'end_time', 'duration_hours',
            'base_amount', 'discount_amount', 'total_amount', 'promo_code_display', 'referral_code_used',
            'status', 'status_display',
            'payment_status', 'payment_status_display',
            'outstanding_amount', 'can_cancel', 'slot_count', 'created_at',
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

    def get_slot_count(self, obj):
        prefetched_slots = getattr(obj, 'booking_slots_cache', None)
        if prefetched_slots is not None:
            return len(prefetched_slots)
        booking_slots = getattr(obj, 'booking_slots', None)
        if booking_slots is not None:
            count = booking_slots.count()
            return count or (1 if obj.time_slot_id else 0)
        return 1 if obj.time_slot_id else 0


class BookingDetailSerializer(serializers.ModelSerializer):
    ground_name = serializers.CharField(source='ground.name', read_only=True)
    ground_address = serializers.CharField(source='ground.address', read_only=True)
    ground_city = serializers.CharField(source='ground.city', read_only=True)
    customer_info = UserMiniSerializer(source='customer', read_only=True)
    time_slot_info = TimeSlotSerializer(source='time_slot', read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    booked_slots = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    outstanding_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    can_cancel = serializers.SerializerMethodField()
    can_confirm = serializers.SerializerMethodField()
    can_complete = serializers.SerializerMethodField()
    promo_code_display = serializers.CharField(source='promo_code_snapshot', read_only=True)
    referral_owner_name = serializers.CharField(source='referral_owner.full_name', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_number',
            'customer', 'customer_info',
            'ground', 'ground_name', 'ground_address', 'ground_city',
            'time_slot', 'time_slot_info', 'pricing_plan',
            'booking_date', 'start_time', 'end_time', 'duration_hours',
            'base_amount', 'discount_amount', 'total_amount', 'promo_code_display', 'referral_code_used', 'referral_owner_name',
            'status', 'status_display',
            'payment_status', 'payment_status_display',
            'customer_name', 'customer_phone', 'player_count', 'notes',
            'special_requests',
            'cancellation_reason', 'cancelled_by',
            'outstanding_amount', 'can_cancel', 'can_confirm', 'can_complete',
            'booked_slots',
            'payments',
            'created_at', 'updated_at',
        ]

    def get_can_cancel(self, obj):
        return obj.status not in ('cancelled', 'completed')

    def get_can_confirm(self, obj):
        return obj.status == 'pending'

    def get_can_complete(self, obj):
        return obj.status in ('pending', 'confirmed')

    def get_booked_slots(self, obj):
        booking_slots = getattr(obj, 'booking_slots_cache', None)
        if booking_slots is None:
            booking_slots = list(
                obj.booking_slots.select_related('time_slot').order_by('time_slot__start_time')
            )
        if booking_slots:
            return BookingSlotSerializer(booking_slots, many=True, context=self.context).data
        if obj.time_slot:
            return [
                {
                    'id': None,
                    'time_slot': TimeSlotSerializer(obj.time_slot, context=self.context).data,
                    'created_at': None,
                }
            ]
        return []


class BookingCreateSerializer(serializers.ModelSerializer):
    """Create a new booking (customer only)."""

    time_slots = serializers.PrimaryKeyRelatedField(
        queryset=TimeSlot.objects.select_related('ground').all(),
        many=True,
        required=False,
        write_only=True,
    )
    promo_code = serializers.CharField(required=False, allow_blank=True, write_only=True)
    referral_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Booking
        fields = [
            'ground', 'time_slot', 'time_slots', 'pricing_plan',
            'booking_date', 'start_time', 'end_time',
            'duration_hours', 'base_amount', 'discount_amount', 'total_amount',
            'customer_name', 'customer_phone', 'player_count', 'notes',
            'special_requests', 'promo_code', 'referral_code',
        ]
        extra_kwargs = {
            'duration_hours': {'required': False},
            'base_amount': {'required': False},
            'discount_amount': {'required': False},
            'total_amount': {'required': False},
        }

    def validate(self, data):
        ground = data['ground']
        if not ground.is_active:
            raise serializers.ValidationError('This ground is not available for booking.')

        booking_date = data['booking_date']
        start_time = data['start_time']
        end_time = data['end_time']
        time_slot = data.get('time_slot')
        time_slots = list(data.get('time_slots') or ([] if not time_slot else [time_slot]))

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

        if time_slots:
            unique_slot_ids = {slot.id for slot in time_slots}
            if len(unique_slot_ids) != len(time_slots):
                raise serializers.ValidationError({'time_slots': 'Duplicate slots are not allowed.'})

            ordered_slots = sorted(time_slots, key=lambda slot: (slot.date, slot.start_time))

            for index, slot in enumerate(ordered_slots):
                if slot.ground != ground:
                    raise serializers.ValidationError({'time_slots': 'Each selected slot must belong to this ground.'})
                if not slot.is_bookable:
                    raise serializers.ValidationError({'time_slots': 'One of the selected slots is not available.'})
                if slot.date != booking_date:
                    raise serializers.ValidationError({'time_slots': 'Selected slot dates must match the booking date.'})
                if index > 0 and ordered_slots[index - 1].end_time != slot.start_time:
                    raise serializers.ValidationError({'time_slots': 'Selected slots must be consecutive.'})

            first_slot = ordered_slots[0]
            last_slot = ordered_slots[-1]

            if first_slot.start_time != start_time or last_slot.end_time != end_time:
                raise serializers.ValidationError(
                    {'time_slots': 'Selected slots must match the submitted booking start and end times.'}
                )

            data['time_slot'] = first_slot
            data['time_slots'] = ordered_slots
        elif time_slot:
            if time_slot.ground != ground:
                raise serializers.ValidationError('Time slot does not belong to this ground.')
            if not time_slot.is_bookable:
                raise serializers.ValidationError('This time slot is not available.')
            if time_slot.date != booking_date:
                raise serializers.ValidationError({'time_slot': 'Time slot date does not match booking date.'})
            if time_slot.start_time != start_time or time_slot.end_time != end_time:
                raise serializers.ValidationError({'time_slot': 'Time slot timing does not match booking times.'})
            data['time_slots'] = [time_slot]

        duration_hours = calculate_duration_hours(start_time, end_time)
        if duration_hours <= 0:
            raise serializers.ValidationError('Booking duration must be greater than zero.')
        data['duration_hours'] = duration_hours

        resolved_plan, base_amount = resolve_booking_price(
            ground=ground,
            booking_date=booking_date,
            duration_hours=duration_hours,
            pricing_plan=data.get('pricing_plan'),
        )
        data['pricing_plan'] = resolved_plan

        discount_breakdown = resolve_discount_breakdown(
            user=self.context['request'].user,
            base_amount=base_amount,
            promo_code_value=data.get('promo_code'),
            referral_code_value=data.get('referral_code'),
            current_booking=self.instance,
        )
        data.update(discount_breakdown)

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
        requested_slots = list(validated_data.pop('time_slots', []))
        validated_data.pop('promo_code', None)
        validated_data.pop('referral_code', None)
        referral_owner = validated_data.get('referral_owner')
        with transaction.atomic():
            locked_slots = []
            if requested_slots:
                requested_slot_ids = [slot.pk for slot in requested_slots]
                locked_slots = list(
                    TimeSlot.objects.select_for_update()
                    .filter(pk__in=requested_slot_ids)
                    .select_related('ground')
                    .order_by('start_time')
                )
                if len(locked_slots) != len(requested_slot_ids):
                    raise serializers.ValidationError({'time_slots': 'One or more selected slots no longer exist.'})
                for index, slot in enumerate(locked_slots):
                    if not slot.is_bookable:
                        raise serializers.ValidationError({'time_slots': 'One of the selected slots is no longer available.'})
                    if slot.ground_id != validated_data['ground'].id:
                        raise serializers.ValidationError({'time_slots': 'Selected slots must belong to this ground.'})
                    if slot.date != validated_data['booking_date']:
                        raise serializers.ValidationError({'time_slots': 'Selected slots must match the booking date.'})
                    if index > 0 and locked_slots[index - 1].end_time != slot.start_time:
                        raise serializers.ValidationError({'time_slots': 'Selected slots must remain consecutive.'})
                validated_data['time_slot'] = locked_slots[0]

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

            if locked_slots:
                BookingSlot.objects.bulk_create(
                    [BookingSlot(booking=booking, time_slot=slot) for slot in locked_slots]
                )
                for slot in locked_slots:
                    slot.is_booked = True
                    slot.save(update_fields=['is_booked', 'updated_at'])
            elif booking.time_slot:
                booking.time_slot.is_booked = True
                booking.time_slot.save(update_fields=['is_booked', 'updated_at'])

            if referral_owner and booking.customer.referred_by_id is None:
                booking.customer.referred_by = referral_owner
                booking.customer.referred_at = timezone.now()
                booking.customer.save(update_fields=['referred_by', 'referred_at', 'updated_at'])

            booking.ground.total_bookings += 1
            booking.ground.save(update_fields=['total_bookings'])

        return booking
