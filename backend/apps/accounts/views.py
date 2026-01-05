from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializers import MeSerializer, MeUpdateSerializer

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

    @extend_schema(
        summary="Update current user profile",
        description="Updates profile fields for the currently authenticated user.",
        request=MeUpdateSerializer,
        responses={
            200: MeSerializer,
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication credentials were not provided"),
        },
        tags=['Accounts'],
    )
    def patch(self, request):
        serializer = MeUpdateSerializer(instance=request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MeSerializer(request.user).data)
