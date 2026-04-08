import django_filters
from .models import Ground


class GroundFilter(django_filters.FilterSet):
    """Filter grounds by city, type, price range, rating, etc."""

    city = django_filters.CharFilter(lookup_expr='icontains')
    state = django_filters.CharFilter(lookup_expr='icontains')
    ground_type = django_filters.CharFilter(lookup_expr='exact')
    surface_type = django_filters.CharFilter(lookup_expr='exact')
    min_rating = django_filters.NumberFilter(field_name='avg_rating', lookup_expr='gte')
    is_verified = django_filters.BooleanFilter()
    min_price = django_filters.NumberFilter(
        method='filter_min_price', label='Minimum price'
    )
    max_price = django_filters.NumberFilter(
        method='filter_max_price', label='Maximum price'
    )
    amenity = django_filters.CharFilter(
        method='filter_amenity', label='Amenity name'
    )

    class Meta:
        model = Ground
        fields = ['city', 'state', 'ground_type', 'surface_type', 'is_verified']

    def filter_min_price(self, queryset, name, value):
        return queryset.filter(
            pricing_plans__price__gte=value,
            pricing_plans__is_active=True,
        ).distinct()

    def filter_max_price(self, queryset, name, value):
        return queryset.filter(
            pricing_plans__price__lte=value,
            pricing_plans__is_active=True,
        ).distinct()

    def filter_amenity(self, queryset, name, value):
        return queryset.filter(amenities__name__icontains=value).distinct()
