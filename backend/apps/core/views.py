from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connections
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import serializers

class HealthCheckResponseSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="Overall system status")
    database = serializers.CharField(help_text="Database connection status")

class HealthCheckView(APIView):
    """
    Simple health check endpoint to verify the API and database are running.
    """
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="System health check",
        description="Checks the status of the API and its connection to the database.",
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
        health = {
            'status': 'healthy',
            'database': 'connected'
        }
        
        try:
            db_conn = connections['default']
            db_conn.cursor()
        except OperationalError:
            health['status'] = 'unhealthy'
            health['database'] = 'disconnected'
            return Response(health, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
        return Response(health, status=status.HTTP_200_OK)
