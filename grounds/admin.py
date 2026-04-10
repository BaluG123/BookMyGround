from django.contrib import admin
from django.utils import timezone
from .models import Ground, GroundImage, PricingPlan, Amenity, Favorite


class GroundImageInline(admin.TabularInline):
    model = GroundImage
    extra = 1


class PricingPlanInline(admin.TabularInline):
    model = PricingPlan
    extra = 1


@admin.register(Ground)
class GroundAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'owner', 'ground_type', 'city', 'verification_status',
        'is_active', 'is_verified', 'submitted_for_review_at', 'verified_at',
    )
    list_filter = ('ground_type', 'surface_type', 'city', 'is_active', 'is_verified', 'verification_status')
    search_fields = ('name', 'city', 'address')
    inlines = [GroundImageInline, PricingPlanInline]
    readonly_fields = ('submitted_for_review_at', 'verified_at', 'verified_by')
    actions = ['approve_selected_grounds', 'reject_selected_grounds']

    fieldsets = (
        ('Ground', {
            'fields': (
                'owner', 'name', 'description', 'ground_type', 'surface_type',
                'address', 'city', 'state', 'pincode',
                'latitude', 'longitude',
            ),
        }),
        ('Operations', {
            'fields': (
                'opening_time', 'closing_time', 'max_players',
                'rules', 'cancellation_policy', 'amenities',
            ),
        }),
        ('Verification', {
            'fields': (
                'verification_status', 'is_verified', 'is_active',
                'submitted_for_review_at', 'verified_at', 'verified_by', 'rejection_reason',
            ),
        }),
    )

    def approve_selected_grounds(self, request, queryset):
        now = timezone.now()
        queryset.update(
            verification_status='approved',
            is_verified=True,
            is_active=True,
            verified_at=now,
            verified_by=request.user,
            rejection_reason='',
        )
    approve_selected_grounds.short_description = 'Approve selected grounds'

    def reject_selected_grounds(self, request, queryset):
        now = timezone.now()
        queryset.update(
            verification_status='rejected',
            is_verified=False,
            is_active=False,
            verified_at=now,
            verified_by=request.user,
        )
    reject_selected_grounds.short_description = 'Reject selected grounds'


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('customer', 'ground', 'created_at')
    list_filter = ('created_at',)
