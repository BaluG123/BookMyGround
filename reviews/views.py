from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Review
from .serializers import ReviewSerializer, ReviewCreateSerializer, ReviewReplySerializer
from accounts.permissions import IsCustomerUser, IsReviewAuthor, IsAdminUser


class ReviewListView(generics.ListAPIView):
    """
    GET /api/v1/reviews/?ground={id}
    List reviews for a ground (public).
    """

    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Review.objects.select_related('customer')
        ground_id = self.request.query_params.get('ground')
        if ground_id:
            qs = qs.filter(ground_id=ground_id)
        return qs


class ReviewCreateView(generics.CreateAPIView):
    """POST /api/v1/reviews/ — Create a review (customer only)."""

    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticated, IsCustomerUser]


class ReviewUpdateView(generics.UpdateAPIView):
    """PUT/PATCH /api/v1/reviews/{id}/ — Update own review."""

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsReviewAuthor]

    def get_queryset(self):
        return Review.objects.filter(customer=self.request.user)


class ReviewDeleteView(generics.DestroyAPIView):
    """DELETE /api/v1/reviews/{id}/ — Delete own review."""

    permission_classes = [IsAuthenticated, IsReviewAuthor]

    def get_queryset(self):
        return Review.objects.filter(customer=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({'message': 'Review deleted.'}, status=status.HTTP_200_OK)


class ReviewReplyView(APIView):
    """POST /api/v1/reviews/{id}/reply/ — Ground owner reply."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk)

        # Check that the replier is the ground owner
        if review.ground.owner != request.user:
            return Response(
                {'error': 'You can only reply to reviews on your own grounds.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ReviewReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review.owner_reply = serializer.validated_data['reply']
        review.replied_at = timezone.now()
        review.save()

        return Response(
            ReviewSerializer(review).data,
            status=status.HTTP_200_OK,
        )
