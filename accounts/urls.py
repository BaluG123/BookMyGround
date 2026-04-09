from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='auth-register'),
    path('login/', views.LoginView.as_view(), name='auth-login'),
    path('firebase-login/', views.FirebaseLoginView.as_view(), name='auth-firebase-login'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('profile/', views.ProfileView.as_view(), name='auth-profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='auth-change-password'),
    path('push/register/', views.PushTokenRegisterView.as_view(), name='auth-push-register'),
    path('push/unregister/', views.PushTokenUnregisterView.as_view(), name='auth-push-unregister'),
    path('notifications/', views.NotificationListView.as_view(), name='auth-notification-list'),
    path('notifications/<uuid:pk>/read/', views.NotificationReadView.as_view(), name='auth-notification-read'),
    path('payout-profile/', views.PayoutProfileView.as_view(), name='auth-payout-profile'),
]
