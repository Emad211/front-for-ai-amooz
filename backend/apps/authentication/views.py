import secrets

from django.contrib.auth import get_user_model

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from apps.accounts.serializers import MeSerializer
from apps.accounts.models import StudentProfile
from apps.classes.models import ClassInvitation
from apps.classes.models import StudentInviteCode

from .serializers import RegisterSerializer, LogoutSerializer, PasswordChangeSerializer, InviteCodeLoginSerializer
from .openapi import (
    RegisterResponseSerializer,
    ErrorDetailSerializer,
    ValidationErrorResponseSerializer,
    PasswordChangeResponseSerializer,
)

User = get_user_model()


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


class InviteCodeLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Login via invite code (student)',
        description='Logs in (or creates) a student user via invite code + phone and returns JWT tokens.',
        request=InviteCodeLoginSerializer,
        responses={200: RegisterResponseSerializer, 400: OpenApiResponse(response=ErrorDetailSerializer)},
        tags=['Authentication'],
    )
    def post(self, request):
        serializer = InviteCodeLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']
        phone = serializer.validated_data['phone']

        # New behavior: global, stable invite code per phone.
        # Backward-compatible behavior: accept legacy codes stored on invitations.
        global_ok = StudentInviteCode.objects.filter(phone=phone, code=code).exists()

        if global_ok:
            has_published_invite = ClassInvitation.objects.filter(
                phone=phone,
                session__is_published=True,
            ).exists()
            if not has_published_invite:
                return Response({'detail': 'کد دعوت یا شماره تماس معتبر نیست.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            inv = (
                ClassInvitation.objects.filter(invite_code=code, phone=phone)
                .select_related('session')
                .first()
            )
            if inv is None or inv.session is None or not inv.session.is_published:
                return Response({'detail': 'کد دعوت یا شماره تماس معتبر نیست.'}, status=status.HTTP_400_BAD_REQUEST)

            # Persist legacy code as the global code if it doesn't exist yet.
            StudentInviteCode.objects.get_or_create(phone=phone, defaults={'code': code})

        qs = User.objects.filter(phone=phone)
        if qs.count() > 1:
            return Response({'detail': 'برای این شماره بیش از یک حساب وجود دارد.'}, status=status.HTTP_400_BAD_REQUEST)

        user = qs.first()
        if user is None:
            base_username = f"student_{phone}"
            username = base_username
            # Guarantee uniqueness even if another user already uses this username.
            if User.objects.filter(username=username).exists():
                username = f"{base_username}_{secrets.token_hex(3)}"

            user = User(username=username, role=User.Role.STUDENT, phone=phone)
            user.set_unusable_password()
            user.save()
            StudentProfile.objects.get_or_create(user=user)
        else:
            if getattr(user, 'role', None) != User.Role.STUDENT:
                return Response({'detail': 'فقط دانش آموز می تواند با کد دعوت وارد شود.'}, status=status.HTTP_403_FORBIDDEN)
            if (getattr(user, 'phone', None) or '').strip() != phone:
                user.phone = phone
                user.save(update_fields=['phone'])
            StudentProfile.objects.get_or_create(user=user)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'user': MeSerializer(user).data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
            },
            status=status.HTTP_200_OK,
        )
