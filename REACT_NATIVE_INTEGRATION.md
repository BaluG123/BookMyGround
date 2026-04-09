# 📱 BookMyGround — React Native Integration Guide

## 🏗️ Architecture Decision: ONE App or TWO?

### ✅ Recommendation: **ONE App with Role-Based Routing**

| Approach | Pros | Cons |
|---|---|---|
| **1 App (Recommended)** | Single codebase, faster dev, shared components (auth, profile, chat), one Play Store listing, users can switch roles | — |
| 2 Apps | Cleaner separation | Double the maintenance, two codebases, duplicate code, two store listings, double CI/CD |

**How it works:** After login, the app checks `user.role` and routes to either the **Admin Dashboard** or **Customer Home**. A ground owner could even switch to "customer mode" to book other grounds.

```
App Launch
  └── Auth Screen (Login / Register / Google Sign-in)
        └── role === 'admin'  → Admin Navigator (Dashboard, My Grounds, Bookings, Revenue)
        └── role === 'customer' → Customer Navigator (Explore, Search, Book, My Bookings)
        └── Shared: Profile, Settings, Notifications
```

---

## 🔑 Django Admin Panel

| Field | Value |
|---|---|
| **URL** | http://localhost:8001/admin/ |
| **Email** | `admin@bookmyground.com` |
| **Password** | `admin123456` |

The admin panel has these sections:
- **ACCOUNTS** → Users (manage all users)
- **AUTH TOKEN** → Tokens (manage auth tokens)
- **GROUNDS** → Grounds, Amenities, Favorites
- **BOOKINGS** → Time Slots, Bookings, Payments
- **REVIEWS** → Reviews

---

## 📋 Complete API Endpoint Reference

**Base URL:** `http://localhost:8001/api/v1`

**Auth Header:** `Authorization: Token <your-token>`

**Firebase Header:** `Authorization: Firebase <firebase-id-token>`

---

### 🔐 AUTH — `/api/v1/auth/`

| # | Endpoint | Method | Auth | Role | Description | Request Body | Response |
|---|---|---|---|---|---|---|---|
| 1 | `/register/` | POST | ❌ | Any | Register new user | `{email, full_name, phone, role, city, state, password, password_confirm}` | `{token, user, message}` |
| 2 | `/login/` | POST | ❌ | Any | Email + password login | `{email, password}` | `{token, user, message}` |
| 3 | `/firebase-login/` | POST | ❌ | Any | Google/Firebase sign-in | `{firebase_token, role, full_name, phone}` | `{token, user, is_new_user}` |
| 4 | `/logout/` | POST | ✅ | Any | Logout (delete token) | — | `{message}` |
| 5 | `/profile/` | GET | ✅ | Any | Get my profile | — | `{id, email, full_name, phone, role, avatar, city, ...}` |
| 6 | `/profile/` | PUT/PATCH | ✅ | Any | Update profile | `{full_name, phone, avatar, city, state}` | Updated user object |
| 7 | `/change-password/` | POST | ✅ | Any | Change password | `{old_password, new_password}` | `{message}` |
| 8 | `/push/register/` | POST | ✅ | Any | Register FCM device token | `{token, platform, device_name}` | Device object |
| 9 | `/push/unregister/` | POST | ✅ | Any | Unregister FCM device token | `{token}` | `{message, updated}` |
| 10 | `/notifications/` | GET | ✅ | Any | List in-app notifications | `?unread_only=true&type=booking_confirmed` | Paginated notifications |
| 11 | `/notifications/{id}/read/` | PATCH | ✅ | Any | Mark notification read | — | Notification object |
| 12 | `/payout-profile/` | GET/PATCH | ✅ | Admin | Store admin bank/UPI payout details | `{account_holder_name, bank_account_number, ifsc_code, upi_id, bank_name, branch_name}` | Payout profile |

---

### 🏟️ GROUNDS — `/api/v1/grounds/`

| # | Endpoint | Method | Auth | Role | Description | Request Body / Params |
|---|---|---|---|---|---|---|
| 8 | `/` | GET | ❌ | Public | List all active grounds | `?city=Bangalore&ground_type=cricket&min_price=500&max_price=2000&search=arena&ordering=-avg_rating` |
| 9 | `/` | POST | ✅ | Admin | Create a ground | `{name, description, ground_type, surface_type, address, city, state, pincode, latitude, longitude, opening_time, closing_time, max_players, rules, cancellation_policy, amenity_ids: [1,2,3]}` |
| 10 | `/{id}/` | GET | ❌ | Public | Ground detail (full) | — |
| 10A | `/{id}/availability/` | GET | ❌ | Public | Day-wise availability summary | `?date=2026-04-10` |
| 11 | `/{id}/` | PUT/PATCH | ✅ | Owner | Update ground | Same as create |
| 12 | `/{id}/` | DELETE | ✅ | Owner | Soft-delete (deactivate) | — |
| 13 | `/my-grounds/` | GET | ✅ | Admin | List admin's own grounds | — |
| 14 | `/{id}/images/` | GET | ❌ | Public | List ground images | — |
| 15 | `/{id}/images/` | POST | ✅ | Owner | Upload images (multipart) | `FormData: images (files), is_primary, caption` |
| 16 | `/{id}/images/{img_id}/` | DELETE | ✅ | Owner | Delete image | — |
| 17 | `/{id}/pricing/` | GET | ❌ | Public | List pricing plans | — |
| 18 | `/{id}/pricing/` | POST | ✅ | Owner | Add pricing plan | `{duration_type, duration_hours, price, weekend_price, is_active}` |
| 19 | `/{id}/pricing/{plan_id}/` | PUT/PATCH | ✅ | Owner | Update pricing | Same as above |
| 20 | `/{id}/pricing/{plan_id}/` | DELETE | ✅ | Owner | Delete pricing | — |
| 21 | `/amenities/` | GET | ❌ | Public | List all amenities | — |
| 22 | `/favorites/` | GET | ✅ | Customer | List my favorites | — |
| 23 | `/favorites/` | POST | ✅ | Customer | Add to favorites | `{ground_id: "uuid"}` |
| 24 | `/favorites/{id}/` | DELETE | ✅ | Customer | Remove favorite | — |

---

### 📅 BOOKINGS — `/api/v1/bookings/`

| # | Endpoint | Method | Auth | Role | Description | Request Body / Params |
|---|---|---|---|---|---|---|
| 25 | `/slots/` | GET | ✅ | Any | List slots | `?ground={id}&date=2026-04-10&bookable_only=true` |
| 26 | `/slots/create/` | POST | ✅ | Admin | Bulk create slots | `{ground_id, date, slots: [{start_time, end_time}, ...]}` |
| 27 | `/slots/{id}/` | PATCH | ✅ | Owner | Update slot | `{is_available}` |
| 28 | `/slots/{id}/delete/` | DELETE | ✅ | Owner | Delete slot (if not booked) | — |
| 29 | `/` | GET | ✅ | Any | List my bookings (auto-filtered by role) | `?status=confirmed&upcoming_only=true` |
| 30 | `/` | POST | ✅ | Customer | Create booking | `{ground, time_slot, pricing_plan, booking_date, start_time, end_time, customer_name, customer_phone, player_count, notes, special_requests}` |
| 31 | `/{id}/` | GET | ✅ | Participant | Booking detail | — |
| 32 | `/{id}/cancel/` | PATCH | ✅ | Participant | Cancel booking | `{reason}` |
| 33 | `/{id}/confirm/` | PATCH | ✅ | Admin | Confirm booking | — |
| 34 | `/{id}/complete/` | PATCH | ✅ | Admin | Mark completed | — |
| 35 | `/{id}/payment-order/` | POST | ✅ | Customer | Create Razorpay order | `{amount?}` |
| 36 | `/{id}/payment-verify/` | POST | ✅ | Customer | Verify Razorpay checkout response | `{razorpay_order_id, razorpay_payment_id, razorpay_signature, payment_method, gateway_response}` |
| 37 | `/{id}/payment/` | POST | ✅ | Participant | Record payment manually | `{amount, payment_method, transaction_id, status, gateway_response}` |
| 38 | `/razorpay/webhook/` | POST | ❌ | Gateway | Razorpay webhook receiver | Raw webhook payload |
| 39 | `/admin-bookings/` | GET | ✅ | Admin | All bookings for admin's grounds | `?ground={id}&date=2026-04-10&status=confirmed` |

---

### ⭐ REVIEWS — `/api/v1/reviews/`

| # | Endpoint | Method | Auth | Role | Description | Request Body |
|---|---|---|---|---|---|---|
| 40 | `/` | GET | ❌ | Public | List reviews | `?ground={id}` |
| 41 | `/create/` | POST | ✅ | Customer | Create review (requires completed booking) | `{ground, rating, comment}` |
| 42 | `/{id}/` | PATCH | ✅ | Author | Update review | `{rating, comment}` |
| 43 | `/{id}/delete/` | DELETE | ✅ | Author | Delete review | — |
| 44 | `/{id}/reply/` | POST | ✅ | Ground Owner | Reply to review | `{reply}` |

---

### 📖 DOCS & ADMIN

| # | URL | Description |
|---|---|---|
| 45 | `/api/docs/` | Swagger UI (interactive API testing) |
| 46 | `/api/redoc/` | ReDoc (readable API docs) |
| 47 | `/api/schema/` | OpenAPI 3.0 JSON schema |
| 48 | `/admin/` | Django admin panel |

---

## 📱 React Native App Structure (Recommended)

```
BookMyGround/
├── src/
│   ├── api/
│   │   ├── client.ts              # Axios instance with token interceptor
│   │   ├── auth.ts                # register, login, firebaseLogin, logout, profile
│   │   ├── grounds.ts             # CRUD grounds, images, pricing, amenities
│   │   ├── bookings.ts            # slots, bookings, payments
│   │   ├── reviews.ts             # CRUD reviews, owner reply
│   │   └── favorites.ts           # add/remove/list favorites
│   │
│   ├── contexts/
│   │   └── AuthContext.tsx         # User state, token, role
│   │
│   ├── navigation/
│   │   ├── RootNavigator.tsx       # Auth check → Admin or Customer stack
│   │   ├── AuthNavigator.tsx       # Login, Register, ForgotPassword
│   │   ├── AdminNavigator.tsx      # Admin tab navigator
│   │   └── CustomerNavigator.tsx   # Customer tab navigator
│   │
│   ├── screens/
│   │   ├── auth/
│   │   │   ├── LoginScreen.tsx
│   │   │   ├── RegisterScreen.tsx
│   │   │   └── RoleSelectScreen.tsx
│   │   │
│   │   ├── admin/
│   │   │   ├── DashboardScreen.tsx       # Revenue, bookings summary
│   │   │   ├── MyGroundsScreen.tsx        # List admin's grounds
│   │   │   ├── AddGroundScreen.tsx        # Create/edit ground form
│   │   │   ├── GroundDetailScreen.tsx     # Manage images, pricing, slots
│   │   │   ├── ManageSlotsScreen.tsx      # Create/manage time slots
│   │   │   ├── ManagePricingScreen.tsx    # Add/edit pricing plans
│   │   │   ├── BookingRequestsScreen.tsx  # Pending/confirmed/completed
│   │   │   ├── BookingDetailScreen.tsx    # Confirm/cancel/complete
│   │   │   └── ReviewsScreen.tsx         # View & reply to reviews
│   │   │
│   │   ├── customer/
│   │   │   ├── HomeScreen.tsx            # Explore, featured grounds
│   │   │   ├── SearchScreen.tsx          # Filter by city, type, price
│   │   │   ├── GroundDetailScreen.tsx    # View ground, pricing, reviews
│   │   │   ├── SelectSlotScreen.tsx      # Pick date & time slot
│   │   │   ├── BookingConfirmScreen.tsx  # Review & confirm booking
│   │   │   ├── PaymentScreen.tsx         # Payment gateway integration
│   │   │   ├── MyBookingsScreen.tsx      # Upcoming, past, cancelled
│   │   │   ├── BookingDetailScreen.tsx   # Booking info, cancel option
│   │   │   ├── FavoritesScreen.tsx       # Saved grounds
│   │   │   └── WriteReviewScreen.tsx     # Rate & review after completed booking
│   │   │
│   │   └── shared/
│   │       ├── ProfileScreen.tsx
│   │       ├── EditProfileScreen.tsx
│   │       └── SettingsScreen.tsx
│   │
│   ├── components/
│   │   ├── GroundCard.tsx          # Ground list item card
│   │   ├── SlotPicker.tsx          # Date & time slot selector
│   │   ├── PricingTable.tsx        # Display pricing plans
│   │   ├── ReviewCard.tsx          # Single review display
│   │   ├── StarRating.tsx          # Interactive star rating
│   │   ├── ImageCarousel.tsx       # Ground image gallery
│   │   ├── BookingStatusBadge.tsx  # Status chip (pending/confirmed/etc)
│   │   └── EmptyState.tsx          # No data placeholders
│   │
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useGrounds.ts
│   │   └── useBookings.ts
│   │
│   └── utils/
│       ├── constants.ts            # API_BASE_URL, colors, etc
│       ├── storage.ts              # AsyncStorage helpers
│       └── helpers.ts              # Date formatting, price formatting
```

---

## 🔧 React Native API Client Setup

```typescript
// src/api/client.ts
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'http://localhost:8001/api/v1';
// For Android emulator use: http://10.0.2.2:8001/api/v1
// For physical device use your computer's local IP: http://192.168.x.x:8001/api/v1

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// Auto-attach auth token
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

// Handle 401 → redirect to login
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await AsyncStorage.multiRemove(['auth_token', 'user_data']);
      // Navigate to login screen
    }
    return Promise.reject(error);
  }
);

export default api;
```

---

## 🔧 Sample API Service Files

```typescript
// src/api/auth.ts
import api from './client';
import AsyncStorage from '@react-native-async-storage/async-storage';

export const authAPI = {
  register: (data: {
    email: string; full_name: string; phone: string;
    role: 'admin' | 'customer'; city: string; state: string;
    password: string; password_confirm: string;
  }) => api.post('/auth/register/', data),

  login: async (email: string, password: string) => {
    const res = await api.post('/auth/login/', { email, password });
    await AsyncStorage.setItem('auth_token', res.data.token);
    await AsyncStorage.setItem('user_data', JSON.stringify(res.data.user));
    return res.data;
  },

  firebaseLogin: (firebase_token: string, role = 'customer') =>
    api.post('/auth/firebase-login/', { firebase_token, role }),

  logout: async () => {
    await api.post('/auth/logout/');
    await AsyncStorage.multiRemove(['auth_token', 'user_data']);
  },

  getProfile: () => api.get('/auth/profile/'),
  updateProfile: (data: FormData) =>
    api.patch('/auth/profile/', data, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  changePassword: (old_password: string, new_password: string) =>
    api.post('/auth/change-password/', { old_password, new_password }),
};
```

```typescript
// src/api/grounds.ts
import api from './client';

export const groundsAPI = {
  // Public
  list: (params?: { city?: string; ground_type?: string; search?: string; page?: number }) =>
    api.get('/grounds/', { params }),
  detail: (id: string) => api.get(`/grounds/${id}/`),
  amenities: () => api.get('/grounds/amenities/'),

  // Admin only
  create: (data: any) => api.post('/grounds/', data),
  update: (id: string, data: any) => api.patch(`/grounds/${id}/`, data),
  delete: (id: string) => api.delete(`/grounds/${id}/`),
  myGrounds: () => api.get('/grounds/my-grounds/'),

  // Images (multipart)
  uploadImages: (groundId: string, formData: FormData) =>
    api.post(`/grounds/${groundId}/images/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  deleteImage: (groundId: string, imageId: string) =>
    api.delete(`/grounds/${groundId}/images/${imageId}/`),

  // Pricing
  listPricing: (groundId: string) => api.get(`/grounds/${groundId}/pricing/`),
  addPricing: (groundId: string, data: any) =>
    api.post(`/grounds/${groundId}/pricing/`, data),
  updatePricing: (groundId: string, planId: string, data: any) =>
    api.patch(`/grounds/${groundId}/pricing/${planId}/`, data),
  deletePricing: (groundId: string, planId: string) =>
    api.delete(`/grounds/${groundId}/pricing/${planId}/`),

  // Favorites
  listFavorites: () => api.get('/grounds/favorites/'),
  addFavorite: (groundId: string) =>
    api.post('/grounds/favorites/', { ground_id: groundId }),
  removeFavorite: (favId: string) => api.delete(`/grounds/favorites/${favId}/`),
};
```

```typescript
// src/api/bookings.ts
import api from './client';

export const bookingsAPI = {
  // Slots
  listSlots: (groundId: string, date: string) =>
    api.get('/bookings/slots/', { params: { ground: groundId, date } }),
  createSlots: (data: { ground_id: string; date: string; slots: any[] }) =>
    api.post('/bookings/slots/create/', data),
  updateSlot: (id: string, data: any) => api.patch(`/bookings/slots/${id}/`, data),
  deleteSlot: (id: string) => api.delete(`/bookings/slots/${id}/delete/`),

  // Bookings
  list: () => api.get('/bookings/'),
  create: (data: {
    ground: string; time_slot?: string; booking_date: string;
    start_time: string; end_time: string; duration_hours: number;
    total_amount: number; customer_name: string; customer_phone: string;
    notes?: string;
  }) => api.post('/bookings/', data),
  detail: (id: string) => api.get(`/bookings/${id}/`),
  cancel: (id: string, reason?: string) =>
    api.patch(`/bookings/${id}/cancel/`, { reason }),
  confirm: (id: string) => api.patch(`/bookings/${id}/confirm/`),
  complete: (id: string) => api.patch(`/bookings/${id}/complete/`),
  adminBookings: (params?: { ground?: string; date?: string; status?: string }) =>
    api.get('/bookings/admin-bookings/', { params }),

  // Payment
  recordPayment: (bookingId: string, data: {
    amount: number; payment_method: string;
    transaction_id: string; status: string;
  }) => api.post(`/bookings/${bookingId}/payment/`, data),
};
```

```typescript
// src/api/reviews.ts
import api from './client';

export const reviewsAPI = {
  list: (groundId: string) => api.get('/reviews/', { params: { ground: groundId } }),
  create: (data: { ground: string; rating: number; comment: string }) =>
    api.post('/reviews/create/', data),
  update: (id: string, data: { rating?: number; comment?: string }) =>
    api.patch(`/reviews/${id}/`, data),
  delete: (id: string) => api.delete(`/reviews/${id}/delete/`),
  reply: (id: string, reply: string) =>
    api.post(`/reviews/${id}/reply/`, { reply }),
};
```

---

## 🧭 Navigation Flow

```
┌──────────────────────────────────────────────────────────────┐
│                      APP LAUNCH                              │
│                         │                                    │
│              Check AsyncStorage for token                    │
│                    │            │                             │
│               No Token      Has Token                        │
│                    │            │                             │
│              AUTH STACK    Verify token → GET /auth/profile/  │
│           ┌────────┤            │            │                │
│           │        │         Success      401 Error           │
│         Login   Register        │            │                │
│           │        │       Check role    AUTH STACK            │
│           │     Role Select     │                             │
│           │        │      ┌─────┴──────┐                     │
│           └────────┘      │            │                     │
│                      role=admin   role=customer              │
│                           │            │                     │
│                    ┌──────┘            └──────┐              │
│                    ▼                          ▼              │
│           ADMIN TAB NAV              CUSTOMER TAB NAV        │
│         ┌─────────────┐            ┌─────────────┐          │
│         │ 🏠 Dashboard │            │ 🏠 Home      │          │
│         │ 🏟 Grounds   │            │ 🔍 Search    │          │
│         │ 📅 Bookings  │            │ 📅 Bookings  │          │
│         │ 👤 Profile   │            │ ❤️ Favorites │          │
│         └─────────────┘            │ 👤 Profile   │          │
│                                    └─────────────┘          │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎨 Key Screens by Role

### Admin Screens
| Screen | API Calls | Features |
|---|---|---|
| **Dashboard** | `GET /bookings/admin-bookings/`, `GET /grounds/my-grounds/` | Revenue summary, today's bookings, quick stats |
| **My Grounds** | `GET /grounds/my-grounds/` | List with edit/deactivate, add new ground |
| **Add/Edit Ground** | `POST/PATCH /grounds/` | Multi-step form: info → images → pricing → slots |
| **Manage Slots** | `POST /bookings/slots/create/`, `GET /bookings/slots/` | Calendar view, bulk slot creation, toggle availability |
| **Manage Pricing** | `GET/POST/PATCH/DELETE /grounds/{id}/pricing/` | Set rates for per-hour, half-day, full-day |
| **Booking Requests** | `GET /bookings/admin-bookings/` | Filter by status, confirm/cancel/complete |
| **Reviews** | `GET /reviews/?ground={id}`, `POST /reviews/{id}/reply/` | View reviews, reply to customers |

### Customer Screens
| Screen | API Calls | Features |
|---|---|---|
| **Home** | `GET /grounds/?ordering=-avg_rating` | Featured grounds, nearby, top-rated |
| **Search** | `GET /grounds/?city=&type=&min_price=&max_price=` | Filters, search bar, map view |
| **Ground Detail** | `GET /grounds/{id}/`, `GET /reviews/?ground={id}` | Images carousel, pricing, reviews, book button |
| **Select Slot** | `GET /bookings/slots/?ground={id}&date=` | Calendar + slot picker |
| **Booking Confirm** | `POST /bookings/` | Review booking, apply pricing, submit |
| **Payment** | `POST /bookings/{id}/payment/` | Razorpay/UPI integration |
| **My Bookings** | `GET /bookings/` | Tabs: Upcoming / Completed / Cancelled |
| **Write Review** | `POST /reviews/create/` | Star rating + comment (after completed booking) |
| **Favorites** | `GET /grounds/favorites/` | Saved grounds list |

---

## 🔥 Firebase Google Sign-In Flow

```typescript
// React Native Firebase + Google Sign-In
import auth from '@react-native-firebase/auth';
import { GoogleSignin } from '@react-native-google-signin/google-signin';
import { authAPI } from '../api/auth';

async function onGoogleSignIn(role: 'admin' | 'customer') {
  // 1. Google Sign-In
  await GoogleSignin.hasPlayServices();
  const { idToken } = await GoogleSignin.signIn();

  // 2. Firebase credential
  const credential = auth.GoogleAuthProvider.credential(idToken);
  const firebaseUser = await auth().signInWithCredential(credential);

  // 3. Get Firebase ID token
  const firebaseToken = await firebaseUser.user.getIdToken();

  // 4. Send to Django backend
  const res = await authAPI.firebaseLogin(firebaseToken, role);

  // 5. Store Django token
  await AsyncStorage.setItem('auth_token', res.data.token);
  await AsyncStorage.setItem('user_data', JSON.stringify(res.data.user));

  return res.data;
}
```

---

## 💡 Pro Tips for React Native Integration

1. **Image uploads**: Use `react-native-image-picker` + `FormData` for ground images and avatars
2. **Pagination**: All list endpoints return `{count, next, previous, results}` — use `FlatList` with `onEndReached`
3. **Real-time**: Add WebSockets later for live booking notifications
4. **Maps**: Use `react-native-maps` with `latitude`/`longitude` from ground data
5. **Payments**: Integrate `react-native-razorpay` — record payment via API after gateway success
6. **Offline**: Cache ground listings with `@tanstack/react-query` for offline browsing
7. **Push Notifications**: Use Firebase Cloud Messaging for booking confirmations

---

## 🚀 Quick Start Commands

```bash
# Start Django server
cd /Users/apple/Desktop/Project/BOOKMYGROUND
source venv/bin/activate
python manage.py runserver 0.0.0.0:8001

# Create React Native app
npx react-native@latest init BookMyGround
cd BookMyGround
npm install axios @react-native-async-storage/async-storage
npm install @react-navigation/native @react-navigation/bottom-tabs @react-navigation/native-stack
npm install @react-native-firebase/app @react-native-firebase/auth
npm install @react-native-google-signin/google-signin
npm install react-native-image-picker
npm install react-native-maps
```
