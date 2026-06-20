from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from apps.core.throttling import SafeScopedRateThrottle

from .serializers import MeSerializer, MeUpdateSerializer, OnboardingSerializer

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


class CompleteOnboardingView(APIView):
    """Forced onboarding: a code-logged-in user sets the credentials they'll log
    in with from now on (username + password), plus email + phone + light profile.
    Flips ``is_profile_completed`` so the frontend gate stops redirecting here."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'onboarding'

    @extend_schema(
        summary="Complete onboarding for the current user",
        description="Sets username/password/email/phone + role profile and marks "
                    "the profile completed.",
        request=OnboardingSerializer,
        responses={
            200: MeSerializer,
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication credentials were not provided"),
        },
        tags=['Accounts'],
    )
    def post(self, request):
        # Onboarding is one-time. A user who already completed it changes their
        # username/password through the proper flows (password-change needs the
        # old password); this endpoint must not become an old-password-free reset.
        if request.user.is_profile_completed:
            return Response(
                {'detail': 'حساب شما قبلاً تکمیل شده است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = OnboardingSerializer(instance=request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MeSerializer(request.user).data)
