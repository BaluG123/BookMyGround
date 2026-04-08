from rest_framework import serializers
from django.utils import timezone
from .models import Review
from accounts.serializers import UserMiniSerializer
from bookings.models import Booking


class ReviewSerializer(serializers.ModelSerializer):
    customer_info = UserMiniSerializer(source='customer', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'customer', 'customer_info', 'ground',
            'rating', 'comment', 'owner_reply', 'replied_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'customer', 'owner_reply', 'replied_at', 'created_at', 'updated_at']


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['ground', 'rating', 'comment']

    def validate(self, data):
        customer = self.context['request'].user

        # Check if customer has a completed booking for this ground
        has_booking = Booking.objects.filter(
            customer=customer,
            ground=data['ground'],
            status='completed',
        ).exists()
        if not has_booking:
            raise serializers.ValidationError(
                'You can only review grounds where you have completed a booking.'
            )

        # Check if already reviewed
        existing = Review.objects.filter(
            customer=customer, ground=data['ground']
        ).exists()
        if existing:
            raise serializers.ValidationError(
                'You have already reviewed this ground. Use update instead.'
            )

        return data

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)


class ReviewReplySerializer(serializers.Serializer):
    """Ground owner reply to a review."""

    reply = serializers.CharField(max_length=1000)
