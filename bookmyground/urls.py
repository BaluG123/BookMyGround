from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .views import home_view, privacy_view, terms_view, refund_view

urlpatterns = [
    path('', home_view, name='home'),
    path('privacy-policy/', privacy_view, name='privacy'),
    path('terms-and-conditions/', terms_view, name='terms'),
    path('refund-policy/', refund_view, name='refund'),
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/grounds/', include('grounds.urls')),
    path('api/v1/bookings/', include('bookings.urls')),
    path('api/v1/reviews/', include('reviews.urls')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
