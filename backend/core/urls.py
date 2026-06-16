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

from apps.authentication.serializers import TokenObtainPairByIdentifierSerializer

from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.authentication.cookies import set_refresh_cookie, get_refresh_from_request
from apps.core.views import HealthCheckView
from apps.core.throttling import SafeScopedRateThrottle


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
    serializer_class = TokenObtainPairByIdentifierSerializer
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'login'

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code == 200 and isinstance(getattr(response, 'data', None), dict):
            set_refresh_cookie(response, response.data.get('refresh'))
        return response


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
    """Accept the refresh token from the HttpOnly cookie (falling back to the
    request body for backward compatibility) and re-set the rotated cookie."""

    def post(self, request, *args, **kwargs):
        data = request.data
        if not data.get('refresh'):
            cookie_refresh = get_refresh_from_request(request)
            if cookie_refresh:
                data = {**request.data, 'refresh': cookie_refresh}

        serializer = self.get_serializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        # Rotation returns a new refresh token → keep the cookie in sync.
        set_refresh_cookie(response, serializer.validated_data.get('refresh'))
        return response

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
    path('api/classes/', include('apps.classes.urls')),
    path('api/notifications/', include('apps.notification.urls')),
    path('api/admin/', include('apps.commons.urls')),
    path('api/organizations/', include('apps.organizations.urls')),
    path('api/waitlist/', include('apps.waitlist.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# When S3 storage is active and no public custom domain is set,
# serve media files through a Django proxy so URLs stay browser-reachable.
if getattr(settings, '_USE_S3', False) and not getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', ''):
    from core.storage_backends import media_proxy_view
    urlpatterns += [
        path('media/<path:path>', media_proxy_view, name='media_proxy'),
    ]
