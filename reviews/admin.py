from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('customer', 'ground', 'rating', 'created_at', 'owner_reply')
    list_filter = ('rating', 'created_at')
    search_fields = ('customer__email', 'ground__name', 'comment')
    readonly_fields = ('created_at', 'updated_at')
