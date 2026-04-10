from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.utils import timezone

from .models import User
from .serializers import (
    UserRegistrationSerializer,
    LoginSerializer,
    FirebaseLoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    NotificationDeviceSerializer,
    NotificationDeviceUnregisterSerializer,
    PushNotificationSerializer,
    PayoutProfileSerializer,
)
from .models import NotificationDevice, PushNotification, PayoutProfile
from .permissions import IsAdminUser


class RegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/register/ — Register a new user."""

    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'message': 'Registration successful.',
                'token': token.key,
                'user': UserProfileSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/v1/auth/login/ — Login with email & password."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'message': 'Login successful.',
                'token': token.key,
                'user': UserProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class FirebaseLoginView(APIView):
    """
    POST /api/v1/auth/firebase-login/
    Login or register via Firebase ID token (Google sign-in, etc).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FirebaseLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        firebase_token = serializer.validated_data['firebase_token']
        role = serializer.validated_data.get('role', 'customer')
        full_name = serializer.validated_data.get('full_name', '')
        phone = serializer.validated_data.get('phone', '')

        # Verify Firebase token
        try:
            from accounts.firebase_auth import get_firebase_app
            app = get_firebase_app()
            if app is None:
                return Response(
                    {'error': 'Firebase is not configured.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            from firebase_admin import auth as firebase_auth
            decoded = firebase_auth.verify_id_token(firebase_token)
        except Exception as e:
            return Response(
                {'error': f'Invalid Firebase token: {str(e)}'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        uid = decoded.get('uid')
        email = decoded.get('email', f'{uid}@firebase.local')
        name = decoded.get('name', '') or full_name or 'User'

        user, created = User.objects.get_or_create(
            firebase_uid=uid,
            defaults={
                'email': email,
                'full_name': name,
                'role': role,
                'phone': phone or None,
            },
        )

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'message': 'Login successful.' if not created else 'Account created.',
                'token': token.key,
                'user': UserProfileSerializer(user).data,
                'is_new_user': created,
            },
            status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ — Delete auth token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        return Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT/PATCH /api/v1/auth/profile/ — Current user's profile."""

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """POST /api/v1/auth/change-password/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)


class PushTokenRegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/push/register/ — Register or refresh FCM token."""

    serializer_class = NotificationDeviceSerializer
    permission_classes = [IsAuthenticated]


class PushTokenUnregisterView(APIView):
    """POST /api/v1/auth/push/unregister/ — Deactivate FCM token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = NotificationDeviceUnregisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = NotificationDevice.objects.filter(
            user=request.user,
            token=serializer.validated_data['token'],
        ).update(is_active=False)
        return Response(
            {'message': 'Push token unregistered.', 'updated': updated},
            status=status.HTTP_200_OK,
        )


class NotificationListView(generics.ListAPIView):
    """GET /api/v1/auth/notifications/ — List my push/in-app notifications."""

    serializer_class = PushNotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = PushNotification.objects.filter(recipient=self.request.user)
        unread_only = self.request.query_params.get('unread_only')
        notification_type = self.request.query_params.get('type')
        if unread_only == 'true':
            qs = qs.filter(is_read=False)
        if notification_type:
            qs = qs.filter(notification_type=notification_type)
        return qs


class NotificationReadView(APIView):
    """PATCH /api/v1/auth/notifications/{id}/read/"""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = generics.get_object_or_404(
            PushNotification,
            pk=pk,
            recipient=request.user,
        )
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=['is_read', 'read_at'])
        return Response(PushNotificationSerializer(notification).data, status=status.HTTP_200_OK)


class PayoutProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/auth/payout-profile/ — Admin payout destination."""

    serializer_class = PayoutProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_object(self):
        profile, created = PayoutProfile.objects.get_or_create(
            user=self.request.user,
            defaults={'account_holder_name': self.request.user.full_name or ''},
        )
        if not created and not profile.account_holder_name and self.request.user.full_name:
            profile.account_holder_name = self.request.user.full_name
            profile.save(update_fields=['account_holder_name', 'updated_at'])
        return profile
