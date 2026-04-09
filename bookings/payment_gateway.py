import base64
import hashlib
import hmac
import json
from decimal import Decimal
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from django.conf import settings


class PaymentGatewayError(Exception):
    pass


def create_razorpay_order(*, amount, receipt, notes=None, partial_payment=False):
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    if not key_id or not key_secret:
        raise PaymentGatewayError('Razorpay credentials are not configured.')

    payload = {
        'amount': int((Decimal(amount) * 100).quantize(Decimal('1'))),
        'currency': 'INR',
        'receipt': receipt[:40],
        'notes': notes or {},
        'partial_payment': partial_payment,
    }

    encoded_auth = base64.b64encode(f'{key_id}:{key_secret}'.encode()).decode()
    req = urllib_request.Request(
        'https://api.razorpay.com/v1/orders',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib_request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        error_body = exc.read().decode('utf-8', errors='ignore')
        raise PaymentGatewayError(f'Razorpay order creation failed: {error_body}') from exc
    except URLError as exc:
        raise PaymentGatewayError(f'Razorpay connection failed: {exc.reason}') from exc


def verify_razorpay_checkout_signature(*, order_id, payment_id, signature):
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    if not key_secret:
        raise PaymentGatewayError('Razorpay key secret is not configured.')

    message = f'{order_id}|{payment_id}'.encode()
    expected_signature = hmac.new(
        key_secret.encode(),
        msg=message,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


def verify_razorpay_webhook_signature(*, body, signature):
    webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
    if not webhook_secret:
        raise PaymentGatewayError('Razorpay webhook secret is not configured.')

    expected_signature = hmac.new(
        webhook_secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature or '')
