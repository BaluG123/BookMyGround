from django.urls import path
from . import views

urlpatterns = [
    # Time Slots
    path('slots/', views.TimeSlotListView.as_view(), name='slot-list'),
    path('slots/create/', views.TimeSlotBulkCreateView.as_view(), name='slot-bulk-create'),
    path('slots/<uuid:pk>/', views.TimeSlotUpdateView.as_view(), name='slot-update'),
    path('slots/<uuid:pk>/delete/', views.TimeSlotDeleteView.as_view(), name='slot-delete'),

    # Bookings
    path('', views.BookingListCreateView.as_view(), name='booking-list-create'),
    path('admin-bookings/', views.AdminBookingsView.as_view(), name='admin-bookings'),
    path('<uuid:pk>/', views.BookingDetailView.as_view(), name='booking-detail'),
    path('<uuid:pk>/cancel/', views.BookingCancelView.as_view(), name='booking-cancel'),
    path('<uuid:pk>/confirm/', views.BookingConfirmView.as_view(), name='booking-confirm'),
    path('<uuid:pk>/complete/', views.BookingCompleteView.as_view(), name='booking-complete'),
    path('<uuid:pk>/payment-order/', views.BookingPaymentOrderView.as_view(), name='booking-payment-order'),
    path('<uuid:pk>/payment-verify/', views.BookingPaymentVerifyView.as_view(), name='booking-payment-verify'),
    path('<uuid:pk>/payment/', views.BookingPaymentView.as_view(), name='booking-payment'),
    path('razorpay/webhook/', views.RazorpayWebhookView.as_view(), name='razorpay-webhook'),
]
