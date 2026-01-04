from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from drf_spectacular.utils import extend_schema_view, extend_schema

from apps.authentication.openapi import (
    TokenObtainPairRequestSerializer,
    TokenObtainPairResponseSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
    ErrorDetailSerializer,
    ValidationErrorResponseSerializer,
)

from apps.core.views import HealthCheckView


@extend_schema_view(
    post=extend_schema(
        tags=['Authentication'],
        summary='Obtain JWT token pair',
        request=TokenObtainPairRequestSerializer,
        responses={
            200: TokenObtainPairResponseSerializer,
            400: ValidationErrorResponseSerializer,
            401: ErrorDetailSerializer,
        },
    )
)
class TokenObtainPairViewDocs(TokenObtainPairView):
    pass


@extend_schema_view(
    post=extend_schema(
        tags=['Authentication'],
        summary='Refresh JWT access token',
        request=TokenRefreshRequestSerializer,
        responses={
            200: TokenRefreshResponseSerializer,
            400: ValidationErrorResponseSerializer,
            401: ErrorDetailSerializer,
        },
    )
)
class TokenRefreshViewDocs(TokenRefreshView):
    pass

urlpatterns = [
    path('admin/', admin.site.urls),
    # System
    path('api/health/', HealthCheckView.as_view(), name='health_check'),
    
    # Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    path('api/token/', TokenObtainPairViewDocs.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshViewDocs.as_view(), name='token_refresh'),
    
    # New App Endpoints
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/auth/', include('apps.authentication.urls')),
]
