from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, NotificationDevice, PushNotification, PayoutProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'full_name', 'role', 'phone', 'city', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'city', 'date_joined')
    search_fields = ('email', 'full_name', 'phone')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone', 'avatar', 'city', 'state')}),
        ('Role & Firebase', {'fields': ('role', 'firebase_uid')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(NotificationDevice)
class NotificationDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'platform', 'device_name', 'is_active', 'last_seen_at')
    list_filter = ('platform', 'is_active', 'last_seen_at')
    search_fields = ('user__email', 'device_name', 'token')
    readonly_fields = ('created_at', 'last_seen_at')


@admin.register(PushNotification)
class PushNotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'title', 'notification_type', 'is_read', 'sent_at')
    list_filter = ('notification_type', 'is_read', 'sent_at')
    search_fields = ('recipient__email', 'title', 'body')
    readonly_fields = ('sent_at', 'read_at')


@admin.register(PayoutProfile)
class PayoutProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'bank_name', 'upi_id', 'is_verified', 'updated_at')
    list_filter = ('is_verified', 'updated_at')
    search_fields = ('user__email', 'account_holder_name', 'bank_account_number', 'upi_id')
