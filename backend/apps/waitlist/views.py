"""Public waitlist intake views.

Phase 1: capture teacher / organization access requests. Admin review and
approval (token issue + org provisioning + SMS) land in a later phase.
"""

from __future__ import annotations

import logging

from django.contrib.auth.models import update_last_login
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import OpenApiResponse, extend_schema

from apps.accounts.serializers import MeSerializer
from apps.authentication.cookies import set_refresh_cookie
from apps.core.permissions import IsPlatformAdmin

from .models import AccessRequest
from .serializers import (
    AccessRequestAdminSerializer,
    AccessRequestCreateSerializer,
    AccessRequestRejectSerializer,
    TeacherRegistrationCompleteSerializer,
)
from .services import (
    InvalidRegistrationToken,
    approve_access_request,
    complete_teacher_registration,
    notify_access_request_approved,
    reject_access_request,
)
from .throttling import WaitlistScopedThrottle

logger = logging.getLogger(__name__)

# A request can only be decided from these (non-terminal) states.
_DECIDABLE = (AccessRequest.Status.PENDING, AccessRequest.Status.CONTACTED)


class AccessRequestCreateView(APIView):
    """POST: submit a teacher / organization access request (public)."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [WaitlistScopedThrottle]
    throttle_scope = 'waitlist'

    @extend_schema(
        summary='Submit an access request (teacher / organization waitlist)',
        description=(
            'Captures a prospective teacher or organization. No account is '
            'created here — the platform contacts the applicant and, on '
            'approval, issues a one-time registration link.'
        ),
        request=AccessRequestCreateSerializer,
        responses={
            201: OpenApiResponse(description='Request received'),
            400: OpenApiResponse(description='Validation error'),
        },
        tags=['Waitlist'],
    )
    def post(self, request):
        serializer = AccessRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        logger.info(
            'New access request #%s (kind=%s, phone=%s)',
            instance.pk, instance.kind, instance.phone,
        )
        return Response(
            {
                'id': instance.pk,
                'detail': 'درخواست شما ثبت شد. پس از بررسی، برای ثبت‌نام با شما تماس می‌گیریم.',
            },
            status=status.HTTP_201_CREATED,
        )


class TeacherRegistrationCompleteView(APIView):
    """POST: an approved teacher completes registration with their token → JWT."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [WaitlistScopedThrottle]
    throttle_scope = 'waitlist'

    @extend_schema(
        tags=['Waitlist'],
        summary='Complete teacher registration via approval token',
        request=TeacherRegistrationCompleteSerializer,
        responses={
            201: OpenApiResponse(description='Account created + logged in'),
            400: OpenApiResponse(description='Invalid token / validation error'),
        },
    )
    def post(self, request):
        serializer = TeacherRegistrationCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, _ar = complete_teacher_registration(
                token=serializer.validated_data['token'],
                username=serializer.validated_data['username'],
                password=serializer.validated_data['password'],
                first_name=serializer.validated_data.get('first_name', ''),
                last_name=serializer.validated_data.get('last_name', ''),
            )
        except InvalidRegistrationToken as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            update_last_login(None, user)
        except Exception:  # noqa: BLE001 - bookkeeping must never break registration
            logger.warning('Could not update last_login for user %s', getattr(user, 'pk', None))

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                'user': MeSerializer(user).data,
                'tokens': {'access': str(refresh.access_token), 'refresh': str(refresh)},
            },
            status=status.HTTP_201_CREATED,
        )
        set_refresh_cookie(response, str(refresh))
        return response


class AccessRequestListView(ListAPIView):
    """GET: list access requests (platform admin). Filter by ?kind= and ?status=."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = AccessRequestAdminSerializer

    @extend_schema(tags=['Waitlist'], summary='List access requests (admin)')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = AccessRequest.objects.select_related('reviewed_by', 'created_organization')
        kind = self.request.query_params.get('kind')
        status_param = self.request.query_params.get('status')
        if kind in AccessRequest.Kind.values:
            qs = qs.filter(kind=kind)
        if status_param in AccessRequest.Status.values:
            qs = qs.filter(status=status_param)
        return qs


class AccessRequestApproveView(APIView):
    """POST: approve a request — issues a registration token / provisions the org."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        tags=['Waitlist'],
        summary='Approve an access request (admin)',
        request=None,
        responses={200: AccessRequestAdminSerializer, 409: OpenApiResponse(description='Already decided')},
    )
    def post(self, request, pk: int):
        ar = get_object_or_404(AccessRequest, pk=pk)
        if ar.status not in _DECIDABLE:
            return Response(
                {'detail': 'این درخواست قبلاً بررسی شده است.'},
                status=status.HTTP_409_CONFLICT,
            )
        ar = approve_access_request(ar, request.user)
        # The admin's browser Origin lets the SMS carry a clickable registration
        # link with zero config (falls back to FRONTEND_BASE_URL env).
        frontend_base = request.headers.get('Origin') or request.headers.get('Referer') or ''
        notify_access_request_approved(ar, frontend_base=frontend_base)  # best-effort, never raises
        return Response(AccessRequestAdminSerializer(ar).data, status=status.HTTP_200_OK)


class AccessRequestRejectView(APIView):
    """POST: reject a request with an optional reason."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        tags=['Waitlist'],
        summary='Reject an access request (admin)',
        request=AccessRequestRejectSerializer,
        responses={200: AccessRequestAdminSerializer, 409: OpenApiResponse(description='Already decided')},
    )
    def post(self, request, pk: int):
        ar = get_object_or_404(AccessRequest, pk=pk)
        if ar.status not in _DECIDABLE:
            return Response(
                {'detail': 'این درخواست قبلاً بررسی شده است.'},
                status=status.HTTP_409_CONFLICT,
            )
        ser = AccessRequestRejectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ar = reject_access_request(ar, request.user, ser.validated_data.get('reason', ''))
        return Response(AccessRequestAdminSerializer(ar).data, status=status.HTTP_200_OK)
