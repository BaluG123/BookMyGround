from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from urllib.parse import urlencode
import json

from .models import TimeSlot, Booking, Payment, PaymentOrder
from .serializers import (
    TimeSlotSerializer,
    TimeSlotBulkCreateSerializer,
    BookingListSerializer,
    BookingDetailSerializer,
    BookingCreateSerializer,
    PaymentSerializer,
    PaymentCreateSerializer,
    PaymentOrderCreateSerializer,
    PaymentUpiIntentSerializer,
    PaymentVerifySerializer,
)
from accounts.permissions import IsAdminUser, IsCustomerUser, IsBookingParticipant
from accounts.notifications import create_and_send_notification
from .payment_gateway import (
    create_razorpay_order,
    verify_razorpay_checkout_signature,
    verify_razorpay_webhook_signature,
    PaymentGatewayError,
)
from django.conf import settings


def update_booking_payment_status(booking, latest_payment_status=None):
    successful_paid = booking.payments.filter(status='success').aggregate(
        total=Sum('amount')
    )['total'] or 0
    if successful_paid >= booking.total_amount:
        booking.payment_status = 'paid'
    elif successful_paid > 0:
        booking.payment_status = 'partially_paid'
    elif latest_payment_status == 'failed':
        booking.payment_status = 'failed'
    elif booking.payments.filter(status='refunded').exists():
        booking.payment_status = 'refunded'
    else:
        booking.payment_status = 'pending'
    booking.save(update_fields=['payment_status', 'updated_at'])
    return booking.payment_status


def notify_successful_payment(booking, payment, actor=None):
    create_and_send_notification(
        recipient=booking.ground.owner,
        title='Payment received',
        body=f'Payment of Rs. {payment.amount} received for booking #{booking.booking_number}.',
        notification_type='payment_received',
        data={
            'booking_id': str(booking.id),
            'payment_id': str(payment.id),
            'screen': 'AdminBookingDetail',
        },
    )
    if actor != booking.customer:
        create_and_send_notification(
            recipient=booking.customer,
            title='Payment recorded',
            body=f'Payment of Rs. {payment.amount} was recorded for booking #{booking.booking_number}.',
            notification_type='payment_recorded',
            data={
                'booking_id': str(booking.id),
                'payment_id': str(payment.id),
                'screen': 'BookingDetail',
            },
        )


# ─── Time Slots ─────────────────────────────────────────────────

class TimeSlotListView(generics.ListAPIView):
    """
    GET /api/v1/bookings/slots/?ground={id}&date={YYYY-MM-DD}
    List available slots for a ground on a given date.
    """

    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = TimeSlot.objects.select_related('ground')
        ground_id = self.request.query_params.get('ground')
        date = self.request.query_params.get('date')
        only_bookable = self.request.query_params.get('bookable_only')
        if ground_id:
            qs = qs.filter(ground_id=ground_id)
        if date:
            qs = qs.filter(date=date)
        if only_bookable == 'true':
            qs = qs.filter(is_available=True, is_booked=False)
        return qs


class TimeSlotBulkCreateView(APIView):
    """POST /api/v1/bookings/slots/ — Create slots in bulk (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        serializer = TimeSlotBulkCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        slots = serializer.save()
        return Response(
            {
                'message': f'{len(slots)} slot(s) created.',
                'slots': TimeSlotSerializer(slots, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


class TimeSlotUpdateView(generics.UpdateAPIView):
    """PUT/PATCH /api/v1/bookings/slots/{id}/ — Update slot (owner only)."""

    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        return TimeSlot.objects.filter(ground__owner=self.request.user)


class TimeSlotDeleteView(generics.DestroyAPIView):
    """DELETE /api/v1/bookings/slots/{id}/ — Delete slot (owner only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        return TimeSlot.objects.filter(ground__owner=self.request.user)

    def destroy(self, request, *args, **kwargs):
        slot = self.get_object()
        if slot.is_booked:
            return Response(
                {'error': 'Cannot delete a booked slot. Cancel the booking first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        slot.delete()
        return Response({'message': 'Slot deleted.'}, status=status.HTTP_200_OK)


# ─── Bookings ───────────────────────────────────────────────────

class BookingListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/bookings/       — List my bookings
    POST /api/v1/bookings/       — Create a booking (customer only)
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BookingCreateSerializer
        return BookingListSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            # Admins see bookings for their grounds
            qs = Booking.objects.filter(
                ground__owner=user
            ).select_related('ground', 'customer')
        else:
            # Customers see their own bookings
            qs = Booking.objects.filter(
                customer=user
            ).select_related('ground', 'customer')

        status_filter = self.request.query_params.get('status')
        date_filter = self.request.query_params.get('date')
        ground_id = self.request.query_params.get('ground')
        upcoming_only = self.request.query_params.get('upcoming_only')

        if status_filter:
            qs = qs.filter(status=status_filter)
        if date_filter:
            qs = qs.filter(booking_date=date_filter)
        if ground_id:
            qs = qs.filter(ground_id=ground_id)
        if upcoming_only == 'true':
            qs = qs.filter(booking_date__gte=timezone.localdate()).exclude(status='cancelled')

        return qs

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsCustomerUser()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        create_and_send_notification(
            recipient=booking.ground.owner,
            title='New booking received',
            body=(
                f'{booking.customer.full_name} booked {booking.ground.name} on '
                f'{booking.booking_date} from {booking.start_time} to {booking.end_time}.'
            ),
            notification_type='booking_created',
            data={
                'booking_id': str(booking.id),
                'ground_id': str(booking.ground_id),
                'screen': 'AdminBookingDetail',
            },
        )
        create_and_send_notification(
            recipient=booking.customer,
            title='Booking request submitted',
            body=f'Your booking #{booking.booking_number} is pending confirmation.',
            notification_type='booking_pending',
            data={
                'booking_id': str(booking.id),
                'ground_id': str(booking.ground_id),
                'screen': 'BookingDetail',
            },
        )
        return Response(
            BookingDetailSerializer(booking, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class BookingDetailView(generics.RetrieveAPIView):
    """GET /api/v1/bookings/{id}/ — Booking detail."""

    serializer_class = BookingDetailSerializer
    permission_classes = [IsAuthenticated, IsBookingParticipant]

    def get_queryset(self):
        return Booking.objects.select_related(
            'ground', 'customer', 'time_slot', 'pricing_plan'
        ).prefetch_related('payments')


class AdminBookingsView(generics.ListAPIView):
    """GET /api/v1/bookings/admin-bookings/ — All bookings for admin's grounds."""

    serializer_class = BookingListSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = Booking.objects.filter(
            ground__owner=self.request.user
        ).select_related('ground', 'customer')

        # Optional filters
        ground_id = self.request.query_params.get('ground')
        date = self.request.query_params.get('date')
        booking_status = self.request.query_params.get('status')

        if ground_id:
            qs = qs.filter(ground_id=ground_id)
        if date:
            qs = qs.filter(booking_date=date)
        if booking_status:
            qs = qs.filter(status=booking_status)

        return qs


# ─── Booking Actions ────────────────────────────────────────────

class BookingCancelView(APIView):
    """PATCH /api/v1/bookings/{id}/cancel/ — Cancel a booking."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)

        # Only customer or ground owner can cancel
        if booking.customer != request.user and booking.ground.owner != request.user:
            return Response(
                {'error': 'You do not have permission to cancel this booking.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if booking.status in ('cancelled', 'completed'):
            return Response(
                {'error': f'Booking is already {booking.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = 'cancelled'
        booking.cancellation_reason = request.data.get('reason', '')
        booking.cancelled_by = 'admin' if request.user.role == 'admin' else 'customer'
        booking.save()

        # Free the time slot
        if booking.time_slot:
            booking.time_slot.is_booked = False
            booking.time_slot.save()

        notify_recipient = booking.customer if request.user == booking.ground.owner else booking.ground.owner
        create_and_send_notification(
            recipient=notify_recipient,
            title='Booking cancelled',
            body=f'Booking #{booking.booking_number} has been cancelled.',
            notification_type='booking_cancelled',
            data={
                'booking_id': str(booking.id),
                'ground_id': str(booking.ground_id),
                'screen': 'BookingDetail',
            },
        )

        return Response(
            BookingDetailSerializer(booking, context={'request': request}).data,
        )


class BookingConfirmView(APIView):
    """PATCH /api/v1/bookings/{id}/confirm/ — Confirm a booking (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk, ground__owner=request.user)

        if booking.status != 'pending':
            return Response(
                {'error': f'Cannot confirm a booking with status "{booking.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = 'confirmed'
        booking.save()
        create_and_send_notification(
            recipient=booking.customer,
            title='Booking confirmed',
            body=f'Your booking #{booking.booking_number} has been confirmed.',
            notification_type='booking_confirmed',
            data={
                'booking_id': str(booking.id),
                'ground_id': str(booking.ground_id),
                'screen': 'BookingDetail',
            },
        )
        return Response(
            BookingDetailSerializer(booking, context={'request': request}).data,
        )


class BookingCompleteView(APIView):
    """PATCH /api/v1/bookings/{id}/complete/ — Mark as completed (admin only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk, ground__owner=request.user)

        if booking.status not in ('confirmed', 'pending'):
            return Response(
                {'error': f'Cannot complete a booking with status "{booking.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = 'completed'
        booking.save()
        create_and_send_notification(
            recipient=booking.customer,
            title='Booking completed',
            body=f'Your booking #{booking.booking_number} is marked completed. You can now leave a review.',
            notification_type='booking_completed',
            data={
                'booking_id': str(booking.id),
                'ground_id': str(booking.ground_id),
                'screen': 'WriteReview',
            },
        )
        return Response(
            BookingDetailSerializer(booking, context={'request': request}).data,
        )


# ─── Payments ───────────────────────────────────────────────────

class BookingPaymentView(APIView):
    """POST /api/v1/bookings/{id}/payment/ — Record a payment."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)

        # Only customer or ground owner
        if booking.customer != request.user and booking.ground.owner != request.user:
            return Response(
                {'error': 'Permission denied.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save(booking=booking)

        update_booking_payment_status(booking, latest_payment_status=payment.status)

        if payment.status == 'success':
            notify_successful_payment(booking, payment, actor=request.user)

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class BookingPaymentOrderView(APIView):
    """POST /api/v1/bookings/{id}/payment-order/ — Create Razorpay order."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        if booking.customer != request.user:
            return Response(
                {'error': 'Only the booking customer can create a payment order.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if booking.status == 'cancelled':
            return Response(
                {'error': 'Cancelled bookings cannot be paid.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaymentOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data.get('amount') or booking.outstanding_amount
        if amount <= 0:
            return Response(
                {'error': 'No outstanding amount left for this booking.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if amount > booking.outstanding_amount:
            return Response(
                {'error': 'Requested amount cannot exceed outstanding amount.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = create_razorpay_order(
                amount=amount,
                receipt=booking.booking_number,
                # Each order here is created for the exact amount the customer
                # should pay now. We support split booking payments by creating
                # a smaller order, not by asking Razorpay to treat that order
                # itself as partially payable.
                partial_payment=False,
                notes={
                    'booking_id': str(booking.id),
                    'booking_number': booking.booking_number,
                    'ground_name': booking.ground.name,
                    'customer_email': booking.customer.email,
                },
            )
        except PaymentGatewayError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        PaymentOrder.objects.update_or_create(
            gateway_order_id=order['id'],
            defaults={
                'booking': booking,
                'gateway': 'razorpay',
                'amount': amount,
                'currency': order.get('currency', 'INR'),
                'status': 'created',
                'raw_response': order,
            },
        )

        return Response(
            {
                'gateway': 'razorpay',
                'key_id': settings.RAZORPAY_KEY_ID,
                'order': order,
                'booking': {
                    'id': str(booking.id),
                    'booking_number': booking.booking_number,
                    'amount_requested': str(amount),
                    'outstanding_amount': str(booking.outstanding_amount),
                    'ground_name': booking.ground.name,
                    'customer_name': booking.customer_name or booking.customer.full_name,
                    'customer_phone': booking.customer_phone or booking.customer.phone or '',
                    'customer_email': booking.customer.email,
                },
            },
            status=status.HTTP_200_OK,
        )


class BookingUpiIntentView(APIView):
    """POST /api/v1/bookings/{id}/upi-intent/ — Build direct UPI payment intent."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        if booking.customer != request.user:
            return Response(
                {'error': 'Only the booking customer can start a UPI payment.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if booking.status == 'cancelled':
            return Response(
                {'error': 'Cancelled bookings cannot be paid.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaymentUpiIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data.get('amount') or booking.outstanding_amount
        if amount <= 0:
            return Response(
                {'error': 'No outstanding amount left for this booking.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if amount > booking.outstanding_amount:
            return Response(
                {'error': 'Requested amount cannot exceed outstanding amount.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payout_profile = getattr(booking.ground.owner, 'payout_profile', None)
        upi_id = (getattr(payout_profile, 'upi_id', '') or '').strip().lower()
        if not upi_id:
            return Response(
                {'error': 'This ground owner has not added a UPI ID yet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payee_name = (
            (getattr(payout_profile, 'account_holder_name', '') or '').strip()
            or (getattr(payout_profile, 'bank_name', '') or '').strip()
            or booking.ground.owner.full_name
            or booking.ground.name
        )
        note = f'Booking {booking.booking_number}'

        params = {
            'pa': upi_id,
            'pn': payee_name,
            'am': f'{amount:.2f}',
            'cu': 'INR',
            'tn': note,
        }
        upi_uri = f"upi://pay?{urlencode(params)}"

        return Response(
            {
                'gateway': 'upi',
                'upi_uri': upi_uri,
                'upi_id': upi_id,
                'payee_name': payee_name,
                'amount': str(amount),
                'currency': 'INR',
                'note': note,
                'booking': {
                    'id': str(booking.id),
                    'booking_number': booking.booking_number,
                    'ground_name': booking.ground.name,
                    'outstanding_amount': str(booking.outstanding_amount),
                },
            },
            status=status.HTTP_200_OK,
        )


class BookingPaymentVerifyView(APIView):
    """POST /api/v1/bookings/{id}/payment-verify/ — Verify Razorpay checkout result."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        if booking.customer != request.user:
            return Response(
                {'error': 'Only the booking customer can verify payment.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PaymentVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            is_valid = verify_razorpay_checkout_signature(
                order_id=data['razorpay_order_id'],
                payment_id=data['razorpay_payment_id'],
                signature=data['razorpay_signature'],
            )
        except PaymentGatewayError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if not is_valid:
            return Response({'error': 'Invalid Razorpay signature.'}, status=status.HTTP_400_BAD_REQUEST)

        payment_order = get_object_or_404(
            PaymentOrder,
            booking=booking,
            gateway_order_id=data['razorpay_order_id'],
        )

        with transaction.atomic():
            payment, created = Payment.objects.get_or_create(
                transaction_id=data['razorpay_payment_id'],
                defaults={
                    'booking': booking,
                    'amount': payment_order.amount,
                    'payment_method': data.get('payment_method', 'online'),
                    'status': 'success',
                    'gateway_response': {
                        **(data.get('gateway_response') or {}),
                        'razorpay_order_id': data['razorpay_order_id'],
                        'razorpay_payment_id': data['razorpay_payment_id'],
                        'razorpay_signature': data['razorpay_signature'],
                    },
                    'paid_at': timezone.now(),
                },
            )
            if not created and payment.status != 'success':
                payment.status = 'success'
                payment.gateway_response = {
                    **(payment.gateway_response or {}),
                    **(data.get('gateway_response') or {}),
                    'razorpay_order_id': data['razorpay_order_id'],
                    'razorpay_payment_id': data['razorpay_payment_id'],
                    'razorpay_signature': data['razorpay_signature'],
                }
                payment.paid_at = payment.paid_at or timezone.now()
                payment.save(update_fields=['status', 'gateway_response', 'paid_at'])

            payment_order.status = 'paid'
            payment_order.raw_response = {
                **payment_order.raw_response,
                **(data.get('gateway_response') or {}),
                'verified_at': timezone.now().isoformat(),
                'razorpay_payment_id': data['razorpay_payment_id'],
            }
            payment_order.save(update_fields=['status', 'raw_response', 'updated_at'])

            update_booking_payment_status(booking, latest_payment_status='success')

        if created:
            notify_successful_payment(booking, payment, actor=request.user)

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class RazorpayWebhookView(APIView):
    """POST /api/v1/bookings/razorpay/webhook/"""

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        signature = request.headers.get('X-Razorpay-Signature')
        body = request.body

        try:
            is_valid = verify_razorpay_webhook_signature(body=body, signature=signature)
        except PaymentGatewayError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if not is_valid:
            return Response({'error': 'Invalid webhook signature.'}, status=status.HTTP_400_BAD_REQUEST)

        payload = json.loads(body.decode('utf-8'))
        event = payload.get('event')
        entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
        order_id = entity.get('order_id')
        payment_id = entity.get('id')

        if not order_id:
            return Response({'message': 'Webhook ignored.'}, status=status.HTTP_200_OK)

        payment_order = PaymentOrder.objects.filter(gateway_order_id=order_id).select_related('booking').first()
        if payment_order is None:
            return Response({'message': 'Order not found.'}, status=status.HTTP_200_OK)

        booking = payment_order.booking

        if event == 'payment.captured':
            with transaction.atomic():
                payment, created = Payment.objects.get_or_create(
                    transaction_id=payment_id,
                    defaults={
                        'booking': booking,
                        'amount': payment_order.amount,
                        'payment_method': 'online',
                        'status': 'success',
                        'gateway_response': entity,
                        'paid_at': timezone.now(),
                    },
                )
                if not created and payment.status != 'success':
                    payment.status = 'success'
                    payment.gateway_response = entity
                    payment.paid_at = payment.paid_at or timezone.now()
                    payment.save(update_fields=['status', 'gateway_response', 'paid_at'])

                payment_order.status = 'paid'
                payment_order.raw_response = payload
                payment_order.save(update_fields=['status', 'raw_response', 'updated_at'])
                update_booking_payment_status(booking, latest_payment_status='success')

            if created:
                notify_successful_payment(booking, payment)

        elif event == 'payment.failed':
            payment_order.status = 'failed'
            payment_order.raw_response = payload
            payment_order.save(update_fields=['status', 'raw_response', 'updated_at'])
            update_booking_payment_status(booking, latest_payment_status='failed')

        return Response({'message': 'Webhook processed.'}, status=status.HTTP_200_OK)
