from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate

from .models import User
from .serializers import (
    UserRegistrationSerializer,
    LoginSerializer,
    FirebaseLoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
)


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
