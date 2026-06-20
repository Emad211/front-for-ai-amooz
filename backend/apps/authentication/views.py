import logging
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from apps.core.throttling import SafeScopedRateThrottle
from apps.accounts.serializers import MeSerializer
from apps.accounts.models import StudentProfile
from apps.accounts.services import get_or_create_student_by_phone
from apps.classes.models import ClassInvitation
from apps.classes.models import StudentInviteCode

from .serializers import (
    RegisterSerializer, LogoutSerializer, PasswordChangeSerializer, InviteCodeLoginSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
)
from .otp_service import find_user_by_identifier, issue_reset_otp, verify_reset_otp
from .cookies import set_refresh_cookie, clear_refresh_cookie, get_refresh_from_request
from .openapi import (
    RegisterResponseSerializer,
    ErrorDetailSerializer,
    ValidationErrorResponseSerializer,
    PasswordChangeResponseSerializer,
)

User = get_user_model()

logger = logging.getLogger(__name__)


def _safe_update_last_login(user) -> None:
    """Record a login timestamp WITHOUT ever failing the auth flow.

    last_login is bookkeeping for the admin panel; a transient write failure
    (e.g. DB lock) must never turn a successful login/registration into a 500.
    """
    try:
        update_last_login(None, user)
    except Exception:
        logger.warning('Could not update last_login for user %s', getattr(user, 'pk', None), exc_info=True)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'register'

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

        # Registration logs the user straight in; record it as a login so the
        # admin "last login" reflects it (these custom paths bypass the
        # SimpleJWT serializer that honours UPDATE_LAST_LOGIN).
        _safe_update_last_login(user)

        refresh = RefreshToken.for_user(user)

        response = Response(
            {
                'user': MeSerializer(user).data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )
        set_refresh_cookie(response, str(refresh))
        return response


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
        # Refresh token comes from the HttpOnly cookie (or the body for backward
        # compatibility). Logout is idempotent: always clear the cookie + 205.
        from rest_framework_simplejwt.exceptions import TokenError

        refresh_value = request.data.get('refresh') or get_refresh_from_request(request)
        response = Response(status=status.HTTP_205_RESET_CONTENT)
        clear_refresh_cookie(response)

        if not refresh_value:
            return response  # nothing to blacklist; session cookie cleared

        try:
            refresh_token = RefreshToken(refresh_value)
            token_user_id = refresh_token.get('user_id')
            if token_user_id is None or str(token_user_id) != str(request.user.id):
                raise PermissionDenied('Refresh token does not belong to the current user.')
            refresh_token.blacklist()
        except TokenError:
            # Already-invalid/expired token — the cookie is cleared; treat as logged out.
            pass
        return response


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

        # Terminate all existing sessions: blacklist every outstanding refresh
        # token for this user so a stolen/old token cannot survive the password
        # change (SimpleJWT is stateless — without this, a changed password does
        # NOT evict an attacker holding a refresh token for up to its lifetime).
        # Then issue the requester a fresh pair so their own session continues.
        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                'detail': 'Password updated successfully.',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            status=status.HTTP_200_OK,
        )
        set_refresh_cookie(response, str(refresh))
        return response


class PasswordResetRequestView(APIView):
    """POST: request a password-reset OTP by SMS. Always returns a generic 200
    (no account enumeration). Only password-using accounts can reset."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'password_reset'

    @extend_schema(
        summary='Request a password-reset OTP (SMS)',
        request=PasswordResetRequestSerializer,
        responses={200: OpenApiResponse(description='Generic acknowledgement')},
        tags=['Authentication'],
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = find_user_by_identifier(serializer.validated_data['identifier'])
        if user is not None and user.has_usable_password():
            issue_reset_otp(user)  # best-effort SMS
        return Response(
            {'detail': 'اگر حسابی با این مشخصات وجود داشته باشد، کد بازیابی پیامک شد.'},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """POST: confirm the OTP and set a new password. Revokes existing sessions
    and returns a fresh token pair (auto-login)."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'password_reset'

    @extend_schema(
        summary='Confirm password reset with OTP + new password',
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description='Password changed + fresh tokens'),
            400: OpenApiResponse(description='Invalid/expired code'),
        },
        tags=['Authentication'],
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = find_user_by_identifier(data['identifier'])
        if user is None or not user.has_usable_password() or not verify_reset_otp(user, data['code']):
            return Response(
                {'detail': 'کد بازیابی نامعتبر یا منقضی شده است.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(data['new_password'])
        user.save()

        # Revoke all existing sessions (same as a password change) so any leaked
        # token can't outlive the reset, then issue a fresh pair (auto-login).
        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                'detail': 'رمز عبور با موفقیت تغییر کرد.',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            status=status.HTTP_200_OK,
        )
        set_refresh_cookie(response, str(refresh))
        return response


class InviteCodeLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'invite_login'

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

        # Resolve (or create) the passwordless STUDENT account for this phone.
        # `phone` is canonical (InviteCodeLoginSerializer.validate_phone), and this
        # is the SAME helper org-code redemption uses, so both flows converge on a
        # single STUDENT identity per phone — no duplicates.
        user, _ = get_or_create_student_by_phone(phone)

        # Invite-code login is the PRIMARY way students sign in; record it so
        # the admin "last login" column works for students too.
        _safe_update_last_login(user)

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                'user': MeSerializer(user).data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
            },
            status=status.HTTP_200_OK,
        )
        set_refresh_cookie(response, str(refresh))
        return response
