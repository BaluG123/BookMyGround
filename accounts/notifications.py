import logging

from firebase_admin import messaging

from .firebase_auth import get_firebase_app
from .models import NotificationDevice, PushNotification

logger = logging.getLogger(__name__)


def create_and_send_notification(*, recipient, title, body, notification_type='general', data=None):
    """Persist an in-app notification and attempt FCM delivery."""

    payload = data or {}
    notification = PushNotification.objects.create(
        recipient=recipient,
        title=title,
        body=body,
        notification_type=notification_type,
        data=payload,
    )

    app = get_firebase_app()
    if app is None:
        return notification

    device_tokens = list(
        NotificationDevice.objects.filter(
            user=recipient,
            is_active=True,
        ).values_list('token', flat=True)
    )
    if not device_tokens:
        return notification

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data={key: str(value) for key, value in payload.items()},
        tokens=device_tokens,
    )

    try:
        response = messaging.send_each_for_multicast(message, app=app)
        for index, send_response in enumerate(response.responses):
            if send_response.success:
                continue
            error_message = str(send_response.exception)
            if 'registration-token-not-registered' in error_message:
                NotificationDevice.objects.filter(token=device_tokens[index]).update(is_active=False)
            logger.warning('FCM delivery failed for token %s: %s', device_tokens[index], error_message)
    except Exception as exc:
        logger.warning('FCM multicast send failed: %s', exc)

    return notification
