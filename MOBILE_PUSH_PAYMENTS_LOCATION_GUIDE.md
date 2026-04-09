# BookMyGround Mobile Integration Guide

This file covers the new backend additions for:

- Firebase push notifications
- In-app notification inbox
- Razorpay payment-order flow
- Location-aware React Native UX
- Updated booking payloads

Use this with the Django backend in this repository.

## 1. New Backend Endpoints

### Push notifications

- `POST /api/v1/auth/push/register/`
- `POST /api/v1/auth/push/unregister/`
- `GET /api/v1/auth/notifications/`
- `PATCH /api/v1/auth/notifications/{id}/read/`

### Availability

- `GET /api/v1/grounds/{ground_id}/availability/?date=YYYY-MM-DD`

### Payments

- `POST /api/v1/bookings/{booking_id}/payment-order/`
- `POST /api/v1/bookings/{booking_id}/payment-verify/`
- `POST /api/v1/bookings/{booking_id}/payment/`
- `POST /api/v1/bookings/razorpay/webhook/`

## 2. Updated Booking Payload

`duration_hours` and `total_amount` are now calculated on the server.

Example booking request:

```json
{
  "ground": "ground-uuid",
  "time_slot": "slot-uuid",
  "pricing_plan": "plan-uuid",
  "booking_date": "2026-04-10",
  "start_time": "06:00:00",
  "end_time": "07:00:00",
  "customer_name": "Rahul Sharma",
  "customer_phone": "9876543210",
  "player_count": 12,
  "notes": "Morning practice",
  "special_requests": "Need cones and extra lighting"
}
```

## 3. Firebase Push Notifications

### Backend behavior

The backend now stores FCM tokens per user and sends notifications when:

- customer creates a booking
- booking is cancelled
- booking is confirmed
- booking is completed
- successful payment is recorded

Notifications are also stored in the database, so your app can show an inbox even if push delivery is missed.

### React Native packages

Recommended stack:

- `@react-native-firebase/app`
- `@react-native-firebase/messaging`

Optional for local display customization:

- `@notifee/react-native`

### Basic setup flow

1. Install Firebase packages in React Native.
2. Add Firebase config files:
   - Android: `google-services.json`
   - iOS: `GoogleService-Info.plist`
3. Request notification permission.
4. Fetch the FCM token after login.
5. Send the token to Django.
6. Refresh the token when Firebase rotates it.
7. Unregister the token on logout.

### Register token request

```http
POST /api/v1/auth/push/register/
Authorization: Token <auth-token>
Content-Type: application/json
```

```json
{
  "token": "fcm-device-token",
  "platform": "android",
  "device_name": "Pixel 8"
}
```

### Unregister token request

```json
{
  "token": "fcm-device-token"
}
```

### Notification inbox

Use this for a bell icon or notification center:

- `GET /api/v1/auth/notifications/?unread_only=true`

Mark an item read:

- `PATCH /api/v1/auth/notifications/{id}/read/`

### React Native example

```ts
import messaging from '@react-native-firebase/messaging';
import api from './client';

export async function setupPushNotifications() {
  await messaging().requestPermission();
  const token = await messaging().getToken();

  await api.post('/auth/push/register/', {
    token,
    platform: 'android',
    device_name: 'Android Device',
  });

  messaging().onTokenRefresh(async (nextToken) => {
    await api.post('/auth/push/register/', {
      token: nextToken,
      platform: 'android',
      device_name: 'Android Device',
    });
  });
}
```

### Foreground handling example

```ts
import messaging from '@react-native-firebase/messaging';

export function registerForegroundPushHandler() {
  return messaging().onMessage(async (remoteMessage) => {
    console.log('Foreground push:', remoteMessage);
  });
}
```

## 4. Razorpay Payment Flow

### Recommendation

For India, start with Razorpay for the first integration pass.

Reason:

- mature React Native checkout support
- easy order-based flow
- strong UPI/card/netbanking coverage
- easiest path for a standard marketplace-style app

Important:

- there is no truly free payment gateway for production
- most gateways are pay-per-transaction, not free
- if you want money to go directly to each ground owner, you usually need a marketplace or split-settlement product, not just basic checkout

### Current backend support

The backend now creates a Razorpay order:

- `POST /api/v1/bookings/{booking_id}/payment-order/`

Optional request body:

```json
{
  "amount": 500
}
```

If omitted, backend uses the booking's outstanding amount.

Response includes:

- `gateway`
- `key_id`
- `order`
- `booking`

### React Native payment flow

1. Customer selects booking to pay.
2. App calls `/payment-order/`.
3. Backend returns Razorpay `order.id`.
4. App opens Razorpay checkout.
5. On success, app posts the signed success payload to `/payment-verify/`.
6. Backend verifies the Razorpay signature.
7. Backend records payment and updates booking payment status.

### React Native success callback example

Preferred:

```ts
await api.post(`/bookings/${bookingId}/payment-verify/`, {
  razorpay_order_id: razorpayOrderId,
  razorpay_payment_id: razorpayPaymentId,
  razorpay_signature: razorpaySignature,
  payment_method: 'online',
  gateway_response: {
    source: 'react_native_checkout',
  },
});
```

Fallback manual endpoint:

```ts
await api.post(`/bookings/${bookingId}/payment/`, {
  amount: amountPaid,
  payment_method: 'upi',
  transaction_id: razorpayPaymentId,
  status: 'success',
  gateway_response: {
    razorpay_order_id: razorpayOrderId,
    razorpay_payment_id: razorpayPaymentId,
    razorpay_signature: razorpaySignature,
  },
});
```

### Admin bank account settlement

This is the important architecture decision.

There are two models:

#### Model A: Platform account receives all money first

- easiest technical setup
- all payments settle into your platform bank account
- later you manually or automatically pay each ground owner

Use this if:

- you are launching fast
- you control payouts manually at first
- legal and accounting are handled by your business

#### Model B: Marketplace or split-settlement model

- better if each ground owner should receive their own share
- needs onboarding of each admin's bank account or UPI details
- usually requires products like Razorpay Route or Cashfree Easy Split

Use this if:

- each admin is effectively a seller/vendor
- you want cleaner automated settlements
- you want less manual payout work later

### Practical recommendation

Start in 2 phases:

1. Phase 1:
   - use Razorpay standard order flow
   - settle to platform account
   - save each admin payout liability in your own ledger
   - transfer payouts manually or with payout APIs later

2. Phase 2:
   - move to marketplace split settlement
   - onboard each admin with bank account + KYC
   - automate vendor payouts

This is the safest launch path.

## 5. Location-Important Mobile UX

Your backend already stores:

- `latitude`
- `longitude`
- `city`
- `state`
- `address`

Recommended mobile behavior:

1. Ask for location permission after onboarding, not on first app open.
2. Use current coordinates to sort grounds by nearest distance on the app side.
3. Keep city search as fallback when permission is denied.
4. Show distance, travel estimate, and opening hours on the ground card.
5. Use `/grounds/{id}/availability/` before navigating to payment.

### Recommended React Native location packages

- `react-native-permissions`
- `react-native-geolocation-service`

### Distance sorting approach

For now, fetch grounds and sort in React Native using the Haversine formula.

That keeps launch complexity lower than building geospatial backend filtering immediately.

## 6. Environment Variables

Set these on Django:

```env
FIREBASE_CREDENTIALS=/absolute/path/firebase-admin.json
RAZORPAY_KEY_ID=rzp_test_xxxxx
RAZORPAY_KEY_SECRET=your_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

## 7. Production Notes

- Register FCM token after every login.
- Unregister token on logout.
- Never trust amount from the mobile app alone.
- Always create payment orders from backend.
- Use `/payment-verify/` after Razorpay success so the backend verifies the signature.
- Save gateway payloads in `gateway_response`.
- If you later move to split settlements, keep admin bank details in a dedicated secure model, not in plain text fields scattered across the app.
