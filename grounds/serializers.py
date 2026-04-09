from rest_framework import serializers
from .models import Ground, GroundImage, PricingPlan, Amenity, Favorite
from accounts.serializers import UserMiniSerializer


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name', 'icon']


class GroundImageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = GroundImage
        fields = ['id', 'image', 'is_primary', 'caption', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class PricingPlanSerializer(serializers.ModelSerializer):
    duration_display = serializers.CharField(source='get_duration_type_display', read_only=True)

    class Meta:
        model = PricingPlan
        fields = [
            'id', 'duration_type', 'duration_display', 'duration_hours',
            'price', 'weekend_price', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class GroundListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for ground listings."""

    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    ground_type_display = serializers.CharField(source='get_ground_type_display', read_only=True)
    surface_type_display = serializers.CharField(source='get_surface_type_display', read_only=True)
    min_price = serializers.SerializerMethodField()
    amenities = AmenitySerializer(many=True, read_only=True)
    is_favorited = serializers.SerializerMethodField()

    class Meta:
        model = Ground
        fields = [
            'id', 'name', 'ground_type', 'ground_type_display',
            'surface_type', 'surface_type_display',
            'city', 'state', 'address',
            'latitude', 'longitude',
            'avg_rating', 'total_reviews', 'total_bookings',
            'primary_image', 'min_price', 'amenities',
            'opening_time', 'closing_time',
            'is_active', 'is_verified', 'owner_name', 'is_favorited',
        ]

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first()
        if not img:
            img = obj.images.first()
        if img and img.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(img.image.url)
            return img.image.url
        return None

    def get_min_price(self, obj):
        plan = obj.pricing_plans.filter(is_active=True).order_by('price').first()
        if plan:
            return {
                'amount': str(plan.price),
                'duration': plan.get_duration_type_display(),
            }
        return None

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(customer=request.user, ground=obj).exists()
        return False


class GroundDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer with images, pricing, amenities."""

    owner = UserMiniSerializer(read_only=True)
    images = GroundImageSerializer(many=True, read_only=True)
    pricing_plans = PricingPlanSerializer(many=True, read_only=True)
    amenities = AmenitySerializer(many=True, read_only=True)
    ground_type_display = serializers.CharField(source='get_ground_type_display', read_only=True)
    surface_type_display = serializers.CharField(source='get_surface_type_display', read_only=True)
    is_favorited = serializers.SerializerMethodField()

    class Meta:
        model = Ground
        fields = [
            'id', 'owner', 'name', 'description',
            'ground_type', 'ground_type_display',
            'surface_type', 'surface_type_display',
            'address', 'city', 'state', 'pincode',
            'latitude', 'longitude',
            'amenities', 'is_active', 'is_verified',
            'opening_time', 'closing_time',
            'max_players', 'rules', 'cancellation_policy',
            'avg_rating', 'total_reviews', 'total_bookings',
            'images', 'pricing_plans', 'is_favorited',
            'created_at', 'updated_at',
        ]

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(customer=request.user, ground=obj).exists()
        return False


class GroundCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a ground."""

    amenity_ids = serializers.PrimaryKeyRelatedField(
        queryset=Amenity.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Ground
        fields = [
            'name', 'description', 'ground_type', 'surface_type',
            'address', 'city', 'state', 'pincode',
            'latitude', 'longitude',
            'opening_time', 'closing_time',
            'max_players', 'rules', 'cancellation_policy',
            'is_active', 'amenity_ids',
        ]

    def create(self, validated_data):
        amenities = validated_data.pop('amenity_ids', [])
        ground = Ground.objects.create(
            owner=self.context['request'].user,
            **validated_data,
        )
        if amenities:
            ground.amenities.set(amenities)
        return ground

    def update(self, instance, validated_data):
        amenities = validated_data.pop('amenity_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if amenities is not None:
            instance.amenities.set(amenities)
        return instance


class GroundImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroundImage
        fields = ['id', 'image', 'is_primary', 'caption']
        read_only_fields = ['id']


class FavoriteSerializer(serializers.ModelSerializer):
    ground = GroundListSerializer(read_only=True)
    ground_id = serializers.PrimaryKeyRelatedField(
        queryset=Ground.objects.filter(is_active=True),
        write_only=True,
        source='ground',
    )

    class Meta:
        model = Favorite
        fields = ['id', 'ground', 'ground_id', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)
