import logging
from pathlib import Path

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)

# Firebase Admin SDK — lazy initialization
_firebase_app = None


def resolve_firebase_credentials_path():
    raw_path = (settings.FIREBASE_CREDENTIALS_PATH or '').strip()
    if not raw_path:
        return None

    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate

    return Path(settings.BASE_DIR) / candidate


def get_firebase_app():
    """Initialize Firebase Admin SDK once."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = resolve_firebase_credentials_path()
        if cred_path is None:
            logger.warning('FIREBASE_CREDENTIALS not set. Firebase auth disabled.')
            return None
        if not cred_path.exists():
            logger.warning('Firebase credentials file not found at %s', cred_path)
            return None

        cred = credentials.Certificate(str(cred_path))
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info('Firebase Admin initialized using %s', cred_path)
        return _firebase_app
    except Exception as e:
        logger.error('Firebase init failed: %s', e)
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

        user = User.objects.filter(firebase_uid=uid).first()
        created = False

        if user is None and email:
            user = User.objects.filter(email__iexact=email).first()
            if user and not user.firebase_uid:
                user.firebase_uid = uid
                if not user.full_name and name:
                    user.full_name = name
                    user.save(update_fields=['firebase_uid', 'full_name', 'updated_at'])
                else:
                    user.save(update_fields=['firebase_uid', 'updated_at'])

        if user is None:
            user = User.objects.create(
                firebase_uid=uid,
                email=email or f'{uid}@firebase.local',
                full_name=name or 'Firebase User',
                role='customer',
            )
            created = True

        if created:
            logger.info('Created new user from Firebase: %s', user.email)

        return (user, None)

    def authenticate_header(self, request):
        return self.keyword
