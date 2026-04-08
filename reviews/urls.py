from django.urls import path
from . import views

urlpatterns = [
    path('', views.ReviewListView.as_view(), name='review-list'),
    path('create/', views.ReviewCreateView.as_view(), name='review-create'),
    path('<uuid:pk>/', views.ReviewUpdateView.as_view(), name='review-update'),
    path('<uuid:pk>/delete/', views.ReviewDeleteView.as_view(), name='review-delete'),
    path('<uuid:pk>/reply/', views.ReviewReplyView.as_view(), name='review-reply'),
]
