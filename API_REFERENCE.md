# 📖 BookMyGround — Complete API Reference

This document provides a comprehensive list of all API endpoints, including request/response examples for both **Admin (Ground Owner)** and **Customer** roles.

**Base URL:** `http://localhost:8001/api/v1` (or your PythonAnywhere URL)

---

## 🔐 Authentication & Profile

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register/` | No | Register a new Admin or Customer |
| POST | `/auth/login/` | No | Authenticate with email/password → returns Token |
| POST | `/auth/firebase-login/` | No | Login/Register via Google/Firebase Token |
| POST | `/auth/logout/` | Yes | Invalidate current token |
| GET | `/auth/profile/` | Yes | Get currently logged-in user profile |
| PATCH | `/auth/profile/` | Yes | Update profile info (city, phone, avatar, etc) |
| POST | `/auth/change-password/` | Yes | Change password (requires old password) |
| POST | `/auth/push/register/` | Yes | Register or refresh FCM push token |
| POST | `/auth/push/unregister/` | Yes | Deactivate FCM push token |
| GET | `/auth/notifications/` | Yes | List in-app/push notifications |
| PATCH | `/auth/notifications/{id}/read/` | Yes | Mark a notification as read |
| GET/PATCH | `/auth/payout-profile/` | Yes | Admin payout bank/UPI details |

---

## 🏟️ Grounds (Turfs)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/grounds/` | No | Any | List all grounds (filterable) |
| POST | `/grounds/` | Yes | Admin | Create a new ground/turf |
| GET | `/grounds/{id}/` | No | Any | Get full details of a ground |
| GET | `/grounds/{id}/availability/?date=YYYY-MM-DD` | No | Any | Get day-wise slot summary and availability |
| PATCH | `/grounds/{id}/` | Yes | Owner | Update ground info |
| DELETE | `/grounds/{id}/` | Yes | Owner | Soft-delete a ground |
| GET | `/grounds/my-grounds/` | Yes | Admin | List all grounds owned by current admin |
| GET | `/grounds/amenities/` | No | Any | List all available amenities |

### Images
| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/grounds/{id}/images/` | No | Any | List images for a ground |
| POST | `/grounds/{id}/images/` | Yes | Owner | Upload new image (Multipart/form-data) |
| DELETE | `/grounds/{id}/images/{img_id}/` | Yes | Owner | Delete a ground image |

### Pricing Plans
| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/grounds/{id}/pricing/` | No | Any | List pricing plans (1hr, half-day, etc) |
| POST | `/grounds/{id}/pricing/` | Yes | Owner | Add a pricing plan |
| PATCH | `/grounds/{id}/pricing/{plan_id}/` | Yes | Owner | Update pricing plan |
| DELETE | `/grounds/{id}/pricing/{plan_id}/` | Yes | Owner | Delete pricing plan |

### Favorites
| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/grounds/favorites/` | Yes | Cust | List current customer's favorites |
| POST | `/grounds/favorites/` | Yes | Cust | Add a ground to favorites |
| DELETE | `/grounds/favorites/{id}/` | Yes | Cust | Remove a ground from favorites |

---

## 📅 Time Slots & Bookings

### Time Slots (Scheduling)
| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/bookings/slots/?ground={id}&date=YYYY-MM-DD&bookable_only=true` | Yes | Any | List slots for a date |
| POST | `/bookings/slots/create/` | Yes | Admin | Bulk create slots for a date |
| PATCH | `/bookings/slots/{id}/` | Yes | Owner | Toggle slot availability |
| DELETE | `/bookings/slots/{id}/delete/` | Yes | Owner | Permanently delete a slot |

### Bookings (Reservations)
| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| POST | `/bookings/` | Yes | Cust | Create a new booking |
| GET | `/bookings/` | Yes | Any | List my bookings (supports status/date/ground/upcoming filters) |
| GET | `/bookings/admin-bookings/` | Yes | Admin | All bookings across all admin's grounds |
| GET | `/bookings/{id}/` | Yes | Any | Get detailed booking info |
| PATCH | `/bookings/{id}/cancel/` | Yes | Any | Cancel a booking |
| PATCH | `/bookings/{id}/confirm/` | Yes | Admin | Confirm a pending booking |
| PATCH | `/bookings/{id}/complete/` | Yes | Admin | Mark a booking as completed |
| POST | `/bookings/{id}/payment-order/` | Yes | Cust | Create Razorpay order for checkout |
| POST | `/bookings/{id}/payment-verify/` | Yes | Cust | Verify Razorpay checkout signature |
| POST | `/bookings/{id}/payment/` | Yes | Any | Record a payment/transaction |
| POST | `/bookings/razorpay/webhook/` | No | Gateway | Razorpay webhook receiver |

---

## ⭐ Reviews & Ratings

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/reviews/?ground={id}` | No | Any | List all reviews for a ground |
| POST | `/reviews/create/` | Yes | Cust | Add review (requires completed booking) |
| PATCH | `/reviews/{id}/` | Yes | Author | Edit your review |
| DELETE | `/reviews/{id}/delete/` | Yes | Author | Delete your review |
| POST | `/reviews/{id}/reply/` | Yes | Owner | Ground owner reply to a review |

---

# 📋 Example Payloads

### 1. Register User (`POST /auth/register/`)
```json
{
  "email": "customer@test.com",
  "full_name": "John Doe",
  "phone": "9876543210",
  "role": "customer", // options: admin, customer
  "city": "Bangalore",
  "password": "test12345",
  "password_confirm": "test12345"
}
```

### 2. Add Turf (`POST /grounds/`)
```json
{
  "name": "Super Cricket Arena",
  "description": "Premium cricket ground with floodlights",
  "ground_type": "cricket",
  "surface_type": "natural_grass",
  "address": "123 Koramangala",
  "city": "Bangalore",
  "state": "Karnataka",
  "pincode": "560095",
  "latitude": "12.93",
  "longitude": "77.62",
  "opening_time": "06:00:00",
  "closing_time": "22:00:00",
  "max_players": 22,
  "amenity_ids": [1, 2, 5]
}
```

### 3. Bulk Create Slots (`POST /bookings/slots/create/`)
```json
{
  "ground_id": "uuid-here",
  "date": "2026-04-10",
  "slots": [
    {"start_time": "06:00", "end_time": "07:00"},
    {"start_time": "07:00", "end_time": "08:00"},
    {"start_time": "08:00", "end_time": "09:00"}
  ]
}
```

### 4. Create Booking (`POST /bookings/`)
```json
{
  "ground": "uuid-here",
  "time_slot": "uuid-here",
  "pricing_plan": "uuid-here",
  "booking_date": "2026-04-10",
  "start_time": "06:00:00",
  "end_time": "07:00:00",
  "customer_name": "John Doe",
  "customer_phone": "9876543210",
  "player_count": 12,
  "special_requests": "Need bibs and water bottles"
}
```

### 5. Create Payment Order (`POST /bookings/{id}/payment-order/`)
```json
{
  "amount": 500
}
```

### 6. Record Payment (`POST /bookings/{id}/payment/`)
```json
{
  "amount": 800,
  "payment_method": "upi", // online, upi, cash, card
  "transaction_id": "pay_xxxxx",
  "status": "success",
  "gateway_response": {
    "razorpay_order_id": "order_xxxxx",
    "razorpay_signature": "signature_xxxxx"
  }
}
```

### 7. Verify Razorpay Payment (`POST /bookings/{id}/payment-verify/`)
```json
{
  "razorpay_order_id": "order_xxxxx",
  "razorpay_payment_id": "pay_xxxxx",
  "razorpay_signature": "signature_xxxxx",
  "payment_method": "online",
  "gateway_response": {
    "source": "react_native_checkout"
  }
}
```
