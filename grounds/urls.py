from django.urls import path
from . import views

urlpatterns = [
    # Grounds
    path('', views.GroundListCreateView.as_view(), name='ground-list-create'),
    path('my-grounds/', views.MyGroundsView.as_view(), name='my-grounds'),
    path('amenities/', views.AmenityListView.as_view(), name='amenity-list'),
    path('favorites/', views.FavoriteListCreateView.as_view(), name='favorite-list-create'),
    path('favorites/<uuid:pk>/', views.FavoriteDeleteView.as_view(), name='favorite-delete'),
    path('<uuid:pk>/', views.GroundDetailView.as_view(), name='ground-detail'),

    # Ground Images
    path('<uuid:ground_id>/images/', views.GroundImageUploadView.as_view(), name='ground-images'),
    path('<uuid:ground_id>/images/<uuid:image_id>/', views.GroundImageDeleteView.as_view(), name='ground-image-delete'),

    # Pricing Plans
    path('<uuid:ground_id>/pricing/', views.PricingPlanListCreateView.as_view(), name='pricing-list-create'),
    path('<uuid:ground_id>/pricing/<uuid:plan_id>/', views.PricingPlanDetailView.as_view(), name='pricing-detail'),
]
