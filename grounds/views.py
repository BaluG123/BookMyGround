from rest_framework import generics, status, parsers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

from .models import Ground, GroundImage, PricingPlan, Amenity, Favorite
from .serializers import (
    GroundListSerializer,
    GroundDetailSerializer,
    GroundCreateUpdateSerializer,
    GroundImageSerializer,
    GroundImageUploadSerializer,
    PricingPlanSerializer,
    AmenitySerializer,
    FavoriteSerializer,
)
from .filters import GroundFilter
from accounts.permissions import IsAdminUser, IsGroundOwner


# ─── Ground CRUD ────────────────────────────────────────────────

class GroundListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/grounds/          — List all active grounds (public)
    POST /api/v1/grounds/          — Create a ground (admin only)
    """

    filterset_class = GroundFilter
    search_fields = ['name', 'city', 'address', 'description']
    ordering_fields = ['avg_rating', 'total_reviews', 'created_at', 'name']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminUser()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return GroundCreateUpdateSerializer
        return GroundListSerializer

    def get_queryset(self):
        return Ground.objects.filter(is_active=True).select_related('owner').prefetch_related(
            'images', 'pricing_plans', 'amenities'
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ground = serializer.save()
        return Response(
            GroundDetailSerializer(ground, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class GroundDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/grounds/{id}/   — Ground detail (public)
    PUT    /api/v1/grounds/{id}/   — Update ground (owner only)
    DELETE /api/v1/grounds/{id}/   — Soft-delete (owner only)
    """

    lookup_field = 'pk'

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsAuthenticated(), IsGroundOwner()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return GroundCreateUpdateSerializer
        return GroundDetailSerializer

    def get_queryset(self):
        return Ground.objects.select_related('owner').prefetch_related(
            'images', 'pricing_plans', 'amenities'
        )

    def destroy(self, request, *args, **kwargs):
        ground = self.get_object()
        ground.is_active = False
        ground.save()
        return Response(
            {'message': 'Ground deactivated successfully.'},
            status=status.HTTP_200_OK,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        ground = serializer.save()
        return Response(
            GroundDetailSerializer(ground, context={'request': request}).data,
        )


class MyGroundsView(generics.ListAPIView):
    """GET /api/v1/grounds/my-grounds/ — Admin's own grounds."""

    serializer_class = GroundListSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        return Ground.objects.filter(owner=self.request.user).select_related('owner').prefetch_related(
            'images', 'pricing_plans', 'amenities'
        )


# ─── Ground Images ──────────────────────────────────────────────

class GroundImageUploadView(APIView):
    """POST /api/v1/grounds/{id}/images/ — Upload images (owner only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, ground_id):
        ground = get_object_or_404(Ground, pk=ground_id, owner=request.user)
        images = request.FILES.getlist('images')
        is_primary = request.data.get('is_primary', 'false').lower() == 'true'
        caption = request.data.get('caption', '')

        if not images:
            return Response(
                {'error': 'No images provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        for img_file in images:
            img = GroundImage.objects.create(
                ground=ground,
                image=img_file,
                is_primary=is_primary and len(created) == 0,
                caption=caption,
            )
            created.append(img)

        # Ensure only one primary
        if is_primary:
            GroundImage.objects.filter(ground=ground, is_primary=True).exclude(
                pk=created[0].pk
            ).update(is_primary=False)

        return Response(
            GroundImageSerializer(created, many=True, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, ground_id):
        ground = get_object_or_404(Ground, pk=ground_id)
        images = ground.images.all()
        return Response(
            GroundImageSerializer(images, many=True, context={'request': request}).data,
        )


class GroundImageDeleteView(APIView):
    """DELETE /api/v1/grounds/{ground_id}/images/{image_id}/"""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def delete(self, request, ground_id, image_id):
        image = get_object_or_404(
            GroundImage, pk=image_id, ground_id=ground_id, ground__owner=request.user
        )
        image.image.delete(save=False)
        image.delete()
        return Response(
            {'message': 'Image deleted successfully.'},
            status=status.HTTP_200_OK,
        )


# ─── Pricing Plans ──────────────────────────────────────────────

class PricingPlanListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/grounds/{id}/pricing/   — List pricing (public)
    POST /api/v1/grounds/{id}/pricing/   — Add pricing (owner only)
    """

    serializer_class = PricingPlanSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminUser()]
        return [AllowAny()]

    def get_queryset(self):
        return PricingPlan.objects.filter(ground_id=self.kwargs['ground_id'])

    def perform_create(self, serializer):
        ground = get_object_or_404(
            Ground, pk=self.kwargs['ground_id'], owner=self.request.user
        )
        serializer.save(ground=ground)


class PricingPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/grounds/{ground_id}/pricing/{plan_id}/
    """

    serializer_class = PricingPlanSerializer
    lookup_url_kwarg = 'plan_id'

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsAuthenticated(), IsAdminUser()]
        return [AllowAny()]

    def get_queryset(self):
        return PricingPlan.objects.filter(
            ground_id=self.kwargs['ground_id']
        )

    def perform_update(self, serializer):
        ground = get_object_or_404(
            Ground, pk=self.kwargs['ground_id'], owner=self.request.user
        )
        serializer.save()

    def perform_destroy(self, instance):
        get_object_or_404(
            Ground, pk=self.kwargs['ground_id'], owner=self.request.user
        )
        instance.delete()


# ─── Amenities ──────────────────────────────────────────────────

class AmenityListView(generics.ListAPIView):
    """GET /api/v1/grounds/amenities/ — List all amenities."""

    serializer_class = AmenitySerializer
    permission_classes = [AllowAny]
    queryset = Amenity.objects.all()
    pagination_class = None


# ─── Favorites ──────────────────────────────────────────────────

class FavoriteListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/grounds/favorites/   — List my favorites
    POST /api/v1/grounds/favorites/   — Add to favorites
    """

    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(customer=self.request.user).select_related('ground')


class FavoriteDeleteView(generics.DestroyAPIView):
    """DELETE /api/v1/grounds/favorites/{id}/"""

    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(customer=self.request.user)
