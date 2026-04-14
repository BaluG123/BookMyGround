import re

from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User
from .models import NotificationDevice, PushNotification, PayoutProfile


UPI_ID_REGEX = re.compile(r'^[a-zA-Z0-9._-]{2,256}@[a-zA-Z]{2,64}$')


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Registration serializer with password confirmation."""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone', 'full_name', 'role',
            'city', 'state', 'password', 'password_confirm',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Email + password login."""

    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid email or password.')
        if not user.is_active:
            raise serializers.ValidationError('Account is deactivated.')
        data['user'] = user
        return data


class FirebaseLoginSerializer(serializers.Serializer):
    """Login / register via Firebase token."""

    firebase_token = serializers.CharField()
    role = serializers.ChoiceField(choices=['admin', 'customer'], default='customer')
    full_name = serializers.CharField(required=False, default='')
    phone = serializers.CharField(required=False, default='')


class UserProfileSerializer(serializers.ModelSerializer):
    """Full user profile."""

    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone', 'full_name', 'role',
            'avatar', 'city', 'state', 'firebase_uid',
            'is_active', 'date_joined', 'updated_at',
        ]
        read_only_fields = ['id', 'email', 'role', 'firebase_uid', 'date_joined', 'updated_at']


class ChangePasswordSerializer(serializers.Serializer):
    """Change password for authenticated user."""

    old_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value


class UserMiniSerializer(serializers.ModelSerializer):
    """Minimal user info for embedding in other serializers."""

    class Meta:
        model = User
        fields = ['id', 'full_name', 'avatar', 'city']


class NotificationDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDevice
        fields = [
            'id', 'token', 'platform', 'device_name',
            'is_active', 'last_seen_at', 'created_at',
        ]
        read_only_fields = ['id', 'is_active', 'last_seen_at', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
        device, _ = NotificationDevice.objects.update_or_create(
            token=validated_data['token'],
            defaults={
                'user': user,
                'platform': validated_data['platform'],
                'device_name': validated_data.get('device_name', ''),
                'is_active': True,
            },
        )
        return device


class NotificationDeviceUnregisterSerializer(serializers.Serializer):
    token = serializers.CharField()


class PushNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushNotification
        fields = [
            'id', 'title', 'body', 'notification_type',
            'data', 'is_read', 'sent_at', 'read_at',
        ]
        read_only_fields = fields


class PayoutProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutProfile
        fields = [
            'account_holder_name',
            'bank_account_number',
            'ifsc_code',
            'upi_id',
            'bank_name',
            'branch_name',
            'beneficiary_code',
            'is_verified',
            'verification_notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['is_verified', 'verification_notes', 'created_at', 'updated_at']

    def to_internal_value(self, data):
        normalized = dict(data)
        if 'upi_id' in normalized and normalized['upi_id'] is not None:
            normalized['upi_id'] = str(normalized['upi_id']).strip().lower()
        if 'ifsc_code' in normalized and normalized['ifsc_code'] is not None:
            normalized['ifsc_code'] = str(normalized['ifsc_code']).strip().upper()
        if 'bank_account_number' in normalized and normalized['bank_account_number'] is not None:
            normalized['bank_account_number'] = str(normalized['bank_account_number']).replace(' ', '')
        if 'account_holder_name' in normalized and normalized['account_holder_name'] is not None:
            normalized['account_holder_name'] = str(normalized['account_holder_name']).strip()
        if 'bank_name' in normalized and normalized['bank_name'] is not None:
            normalized['bank_name'] = str(normalized['bank_name']).strip()
        if 'branch_name' in normalized and normalized['branch_name'] is not None:
            normalized['branch_name'] = str(normalized['branch_name']).strip()
        return super().to_internal_value(normalized)

    def validate(self, attrs):
        account_holder_name = attrs.get('account_holder_name') or getattr(self.instance, 'account_holder_name', '')
        bank_account_number = attrs.get('bank_account_number') or getattr(self.instance, 'bank_account_number', '')
        ifsc_code = attrs.get('ifsc_code') or getattr(self.instance, 'ifsc_code', '')
        upi_id = attrs.get('upi_id') or getattr(self.instance, 'upi_id', '')

        if not upi_id and not (bank_account_number and ifsc_code):
            raise serializers.ValidationError(
                'Provide either UPI ID or both bank account number and IFSC code.'
            )
        if upi_id and not UPI_ID_REGEX.match(upi_id):
            raise serializers.ValidationError(
                {'upi_id': 'Enter a valid UPI ID like name@bank.'}
            )
        if upi_id and not account_holder_name:
            raise serializers.ValidationError(
                {'account_holder_name': 'Account holder name is required so UPI apps can show the payee name.'}
            )
        return attrs
