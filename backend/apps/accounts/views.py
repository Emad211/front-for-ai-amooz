from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializers import MeSerializer

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get current user profile",
        description="Returns the profile information of the currently authenticated user.",
        responses={
            200: MeSerializer,
            401: OpenApiResponse(description="Authentication credentials were not provided")
        },
        tags=['Accounts']
    )
    def get(self, request):
        serializer = MeSerializer(request.user)
        return Response(serializer.data)
