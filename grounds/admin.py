from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.urls import path, reverse
from django.utils.html import format_html
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
        'is_active', 'is_verified', 'submitted_for_review_at', 'verified_at', 'review_actions',
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

    def save_model(self, request, obj, form, change):
        if obj.verification_status in ('approved', 'rejected'):
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'review-queue/',
                self.admin_site.admin_view(self.review_queue_view),
                name='grounds_ground_review_queue',
            ),
            path(
                '<uuid:ground_id>/approve/',
                self.admin_site.admin_view(self.approve_ground_view),
                name='grounds_ground_approve',
            ),
            path(
                '<uuid:ground_id>/reject/',
                self.admin_site.admin_view(self.reject_ground_view),
                name='grounds_ground_reject',
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        pending_count = Ground.objects.filter(verification_status='pending').count()
        extra_context = extra_context or {}
        extra_context['pending_review_count'] = pending_count
        extra_context['review_queue_url'] = reverse('admin:grounds_ground_review_queue')
        return super().changelist_view(request, extra_context=extra_context)

    def review_actions(self, obj):
        if obj.verification_status == 'pending':
            approve_url = reverse('admin:grounds_ground_approve', args=[obj.pk])
            reject_url = reverse('admin:grounds_ground_reject', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}">Approve</a>&nbsp;<a class="button" href="{}">Reject</a>',
                approve_url,
                reject_url,
            )
        return 'Reviewed'
    review_actions.short_description = 'Actions'

    def review_queue_view(self, request):
        pending_grounds = Ground.objects.filter(verification_status='pending').select_related('owner').order_by('submitted_for_review_at')
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Pending Grounds Review Queue',
            'pending_grounds': pending_grounds,
            'approved_count': Ground.objects.filter(verification_status='approved').count(),
            'rejected_count': Ground.objects.filter(verification_status='rejected').count(),
        }
        return TemplateResponse(request, 'admin/grounds/review_queue.html', context)

    def approve_ground_view(self, request, ground_id):
        ground = Ground.objects.get(pk=ground_id)
        ground.approve(reviewer=request.user)
        self.message_user(request, f'{ground.name} approved and made public.', level=messages.SUCCESS)
        return HttpResponseRedirect(reverse('admin:grounds_ground_review_queue'))

    def reject_ground_view(self, request, ground_id):
        ground = Ground.objects.get(pk=ground_id)
        ground.reject(reviewer=request.user, reason=ground.rejection_reason)
        self.message_user(request, f'{ground.name} rejected and hidden from customers.', level=messages.WARNING)
        return HttpResponseRedirect(reverse('admin:grounds_ground_review_queue'))


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('customer', 'ground', 'created_at')
    list_filter = ('created_at',)
