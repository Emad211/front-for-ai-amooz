from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from apps.accounts.serializers import MeSerializer

from .serializers import RegisterSerializer, LogoutSerializer, PasswordChangeSerializer
from .openapi import (
    RegisterResponseSerializer,
    ErrorDetailSerializer,
    ValidationErrorResponseSerializer,
    PasswordChangeResponseSerializer,
)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Register a new user",
        description="Creates a new user account (Student or Teacher) and returns authentication tokens.",
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                response=RegisterResponseSerializer,
                description="User created successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={
                            'user': {
                                'id': 1,
                                'username': 'johndoe',
                                'email': 'john@example.com',
                                'role': 'student',
                                'is_profile_completed': False,
                            },
                            'tokens': {
                                'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                                'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=ValidationErrorResponseSerializer,
                description="Validation error (e.g., duplicate username, weak password)",
            )
        },
        tags=['Authentication']
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'user': MeSerializer(user).data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Logout user",
        description="Blacklists the provided refresh token to invalidate the session.",
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description="Successfully logged out"),
            400: OpenApiResponse(response=ErrorDetailSerializer, description="Invalid refresh token"),
            401: OpenApiResponse(description="Authentication credentials were not provided"),
            403: OpenApiResponse(description="Token does not belong to the current user")
        },
        tags=['Authentication']
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh_token = RefreshToken(serializer.validated_data['refresh'])
            token_user_id = refresh_token.get('user_id')
            if token_user_id is None or str(token_user_id) != str(request.user.id):
                raise PermissionDenied('Refresh token does not belong to the current user.')
            
            refresh_token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            from rest_framework_simplejwt.exceptions import TokenError
            if isinstance(e, TokenError):
                return Response({'detail': 'Invalid refresh token.'}, status=status.HTTP_400_BAD_REQUEST)
            raise


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change password",
        description="Updates the password for the currently authenticated user.",
        request=PasswordChangeSerializer,
        responses={
            200: OpenApiResponse(
                response=PasswordChangeResponseSerializer,
                description="Password updated successfully",
                examples=[OpenApiExample('Success', value={'detail': 'Password updated successfully.'})]
            ),
            400: OpenApiResponse(
                response=ValidationErrorResponseSerializer,
                description="Invalid old password or weak new password",
            ),
            401: OpenApiResponse(description="Authentication credentials were not provided")
        },
        tags=['Authentication']
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {
                    'detail': 'Validation error.',
                    'errors': {
                        'old_password': ['Wrong password.'],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)
