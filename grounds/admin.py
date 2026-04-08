from django.contrib import admin
from .models import Ground, GroundImage, PricingPlan, Amenity, Favorite


class GroundImageInline(admin.TabularInline):
    model = GroundImage
    extra = 1


class PricingPlanInline(admin.TabularInline):
    model = PricingPlan
    extra = 1


@admin.register(Ground)
class GroundAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'ground_type', 'city', 'avg_rating', 'is_active', 'is_verified')
    list_filter = ('ground_type', 'surface_type', 'city', 'is_active', 'is_verified')
    search_fields = ('name', 'city', 'address')
    inlines = [GroundImageInline, PricingPlanInline]


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('customer', 'ground', 'created_at')
    list_filter = ('created_at',)
