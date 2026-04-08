from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import TimeSlot, Booking, Payment
from .serializers import (
    TimeSlotSerializer,
    TimeSlotBulkCreateSerializer,
    BookingListSerializer,
    BookingDetailSerializer,
    BookingCreateSerializer,
    PaymentSerializer,
    PaymentCreateSerializer,
)
from grounds.models import Ground
from accounts.permissions import IsAdminUser, IsCustomerUser, IsBookingParticipant


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
        if ground_id:
            qs = qs.filter(ground_id=ground_id)
        if date:
            qs = qs.filter(date=date)
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
            return Booking.objects.filter(
                ground__owner=user
            ).select_related('ground', 'customer')
        # Customers see their own bookings
        return Booking.objects.filter(
            customer=user
        ).select_related('ground', 'customer')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsCustomerUser()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
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

        # Update booking payment status
        if payment.status == 'success':
            total_paid = sum(
                p.amount for p in booking.payments.filter(status='success')
            )
            if total_paid >= booking.total_amount:
                booking.payment_status = 'paid'
            else:
                booking.payment_status = 'partially_paid'
            booking.save()

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )
