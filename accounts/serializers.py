from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User


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
