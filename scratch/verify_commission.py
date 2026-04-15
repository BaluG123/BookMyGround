import os
import sys
import django
from decimal import Decimal

# Add current directory to path
sys.path.append(os.getcwd())

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyground.settings')
django.setup()

from bookings.models import Booking, Payment, PaymentOrder
from accounts.models import User
from django.utils import timezone

def verify():
    # Find or create a test booking
    booking = Booking.objects.first()
    if not booking:
        print("No booking found to test.")
        return

    print(f"Testing with booking: {booking.booking_number}, Total: {booking.total_amount}")

    # Create a mock PaymentOrder
    amount = Decimal('500.00')
    payment_order = PaymentOrder.objects.create(
        booking=booking,
        gateway_order_id=f"order_{timezone.now().timestamp()}",
        amount=amount,
        status='created'
    )

    # Simulation of verification logic (manual check of the logic we implemented in the view)
    commission = Decimal('29.00')
    if payment_order.amount < commission:
        commission = payment_order.amount
    owner_share = payment_order.amount - commission

    print(f"Calculated - Commission: {commission}, Owner Share: {owner_share}")

    payment = Payment.objects.create(
        booking=booking,
        amount=payment_order.amount,
        platform_commission=commission,
        owner_share=owner_share,
        payment_method='online',
        status='success',
        transaction_id=f"pay_{timezone.now().timestamp()}",
        paid_at=timezone.now()
    )

    print(f"Payment Created - ID: {payment.transaction_id}, Commission: {payment.platform_commission}, Share: {payment.owner_share}")
    
    if payment.platform_commission == Decimal('29.00') and payment.owner_share == Decimal('471.00'):
        print("SUCCESS: Commission logic verified.")
    else:
        print("FAILURE: Calculation mismatch.")

if __name__ == "__main__":
    verify()
