from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connections
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import serializers

import logging

logger = logging.getLogger(__name__)


class HealthCheckResponseSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="Overall system status")
    database = serializers.CharField(help_text="Database connection status")
    redis = serializers.CharField(help_text="Redis connection status", required=False)


class HealthCheckView(APIView):
    """
    Readiness probe endpoint.  Verifies the API, database, and Redis.
    """
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="System health check",
        description="Checks the status of the API, database, and Redis.",
        responses={
            200: OpenApiResponse(
                response=HealthCheckResponseSerializer,
                description="System is healthy"
            ),
            503: OpenApiResponse(
                description="System is unhealthy (e.g., database connection failed)"
            )
        },
        tags=['System']
    )
    def get(self, request):
        health: dict = {
            'status': 'healthy',
            'database': 'connected',
            'redis': 'connected',
        }
        ok = True

        # --- Database check ---
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception:
            health['database'] = 'disconnected'
            ok = False

        # --- Redis / Celery broker check ---
        try:
            from django.conf import settings as _s
            import redis as _redis
            r = _redis.from_url(_s.REDIS_URL, socket_connect_timeout=3)
            r.ping()
        except Exception:
            health['redis'] = 'disconnected'
            ok = False

        if not ok:
            health['status'] = 'unhealthy'
            return Response(health, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(health, status=status.HTTP_200_OK)
