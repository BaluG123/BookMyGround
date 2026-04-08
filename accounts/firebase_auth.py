import logging
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)

# Firebase Admin SDK — lazy initialization
_firebase_app = None


def get_firebase_app():
    """Initialize Firebase Admin SDK once."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = settings.FIREBASE_CREDENTIALS_PATH
        if not cred_path:
            logger.warning('FIREBASE_CREDENTIALS not set. Firebase auth disabled.')
            return None

        cred = credentials.Certificate(cred_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        return _firebase_app
    except Exception as e:
        logger.error(f'Firebase init failed: {e}')
        return None


class FirebaseAuthentication(BaseAuthentication):
    """
    Authenticate users via Firebase ID token.

    The client sends:  Authorization: Firebase <id_token>
    """

    keyword = 'Firebase'

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith(f'{self.keyword} '):
            return None

        token = auth_header.split(' ', 1)[1].strip()
        if not token:
            return None

        app = get_firebase_app()
        if app is None:
            raise AuthenticationFailed('Firebase is not configured on this server.')

        try:
            from firebase_admin import auth as firebase_auth
            decoded = firebase_auth.verify_id_token(token)
        except Exception as e:
            raise AuthenticationFailed(f'Invalid Firebase token: {e}')

        uid = decoded.get('uid')
        email = decoded.get('email', '')
        name = decoded.get('name', '')

        from accounts.models import User

        user, created = User.objects.get_or_create(
            firebase_uid=uid,
            defaults={
                'email': email or f'{uid}@firebase.local',
                'full_name': name or 'Firebase User',
                'role': 'customer',
            },
        )

        if created:
            logger.info(f'Created new user from Firebase: {user.email}')

        return (user, None)

    def authenticate_header(self, request):
        return self.keyword
