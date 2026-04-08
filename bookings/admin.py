from django.contrib import admin
from .models import TimeSlot, Booking, Payment


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('ground', 'date', 'start_time', 'end_time', 'is_available', 'is_booked')
    list_filter = ('date', 'is_available', 'is_booked', 'ground')
    search_fields = ('ground__name',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_number', 'customer', 'ground', 'booking_date',
        'start_time', 'end_time', 'total_amount', 'status', 'payment_status',
    )
    list_filter = ('status', 'payment_status', 'booking_date')
    search_fields = ('booking_number', 'customer__email', 'ground__name')
    readonly_fields = ('booking_number', 'created_at', 'updated_at')
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'booking', 'amount', 'payment_method', 'status', 'paid_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('transaction_id', 'booking__booking_number')
