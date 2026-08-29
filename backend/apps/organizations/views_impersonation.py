"""Risman step 4 — direct login (ورود مستقیم): mint and close borrowed sessions.

Two doors, both under ``/api/organizations/`` because tenancy lives there:

* ``ImpersonationStartView`` — ``POST <org_pk>/impersonate/<user_id>/``:
  a platform-MANAGER with an ACTIVE admin/deputy membership in THAT org borrows
  an advisor/student member's identity. The response is a fresh JWT pair whose
  payloads carry the ``imp = {by, org}`` claim on **both** tokens; the claim is
  what ``IsOrgManager`` (and every future manager-door) uses to refuse a
  borrowed session manager powers. One ``ImpersonationLog`` row opens here.
* ``ImpersonationStopView`` — ``POST <org_pk>/impersonate/stop/``: closes the
  manager's most recent open session (``ended_at``). Authentication is manual:
  the credential is the **manager's own REFRESH token** — an access token is
  not a session-closing credential (403), and the borrowed (``imp``) refresh
  must never be able to end or open sessions itself (403).

Security posture, tested in ``apps.advisory.test_org_panel``:

* stranger manager / suspended membership / expired org ⇒ 404 «سازمانی برای
  شما یافت نشد.» — no oracle about the org's existence (ق۶);
* target outside the org (or suspended member) ⇒ 404, teacher/admin member
  ⇒ 400 «هدف باید مشاور یا دانش‌آموز همین سازمان باشد.», self ⇒ 400;
* TTL: both minted tokens get a 30-minute lifetime regardless of the global
  SIMPLE_JWT settings — a borrowed session dies with or without the manager
  pressing «خروج». The frontend never refreshes an ``imp`` token (it swaps the
  pair wholesale and restores the manager's pair on exit), so the rotation
  chain is not part of the design; the 30-minute ceiling is the backstop.
"""

from __future__ import annotations

import datetime

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.authentication.cookies import get_refresh_from_request
from apps.core.permissions import IsOrgManager

from .models import ImpersonationLog, OrganizationMembership

MSG_NO_ORG = 'سازمانی برای شما یافت نشد.'
MSG_SELF = 'خودتان را نمی‌توانید انتخاب کنید.'
MSG_MEMBER_ONLY = 'هدف باید مشاور یا دانش‌آموز همین سازمان باشد.'
MSG_NOT_MEMBER = 'کاربر موردنظر در این سازمان یافت نشد.'
MSG_NO_OPEN_SESSION = 'جلسه‌ی ورود مستقیمی باز نیست.'
MSG_STAFF_ONLY = 'این جلسه در حالت ورود مستقیم است و این کار مجاز نیست.'
MSG_NOT_MANAGER = 'فقط مدیر موسسه اجازه دسترسی دارد.'
MSG_BAD_CREDENTIALS = 'شناسه‌ی ورود نامعتبر است.'

# The borrowed session's hard ceiling. Both halves of the pair get it: an
# access token that outlived its refresh would let the borrowed identity act
# after the session should have died.
IMP_LIFETIME = datetime.timedelta(minutes=30)


def _manager_membership(user, org_pk: int):
    """The user's ACTIVE admin/deputy row for exactly THIS org, else ``None``.

    Live check, no cached flag — the same rule ``views_org`` and the
    organizations app use everywhere: suspend or delete the row and every
    manager door closes on the next request, with no signal to fire.
    """
    return (
        OrganizationMembership.objects.select_related('organization')
        .filter(
            user=user,
            organization_id=org_pk,
            org_role__in=[
                OrganizationMembership.OrgRole.ADMIN,
                OrganizationMembership.OrgRole.DEPUTY,
            ],
            status=OrganizationMembership.MemberStatus.ACTIVE,
            organization__subscription_status='active',
        )
        .first())


class ImpersonationStartView(APIView):
    """``POST <org_pk>/impersonate/<user_id>/`` — mint the borrowed pair.

    Permission layer (``IsOrgManager``) already refuses anonymous, non-manager
    and ``imp``-claim bearers; the body below resolves tenancy and target
    validity only. The minted pair carries ``user_id`` of the TARGET (the
    session *is* them) plus the ``imp`` claim on both halves, and both halves
    are clamped to ``IMP_LIFETIME`` so the session cannot outlive the manager's
    attention even if «خروج» is never pressed.
    """

    permission_classes = [IsAuthenticated, IsOrgManager]

    @extend_schema(
        tags=['organizations'],
        summary='شروع ورود مستقیم به حساب یک عضو سازمان',
        description=(
            'فقط مدیر/معاون فعال همان سازمان. هدف باید عضو فعال '
            'مشاور یا دانش‌آموزِ همین سازمان باشد. پاسخ: جفت توکن ۳۰ دقیقه‌ای '
            'با claim `imp`؛ یک ردیف ImpersonationLog باز می‌شود.'
        ),
        responses={
            200: OpenApiResponse(description='جفت توکن صادر شد'),
            400: OpenApiResponse(description='هدف نامعتبر (خود/نقش نامجاز)'),
            404: OpenApiResponse(description='سازمان یا عضو یافت نشد'),
        },
    )
    def post(self, request, org_pk: int, user_id: int):
        membership = _manager_membership(request.user, org_pk)
        if membership is None:
            return Response({'detail': MSG_NO_ORG}, status=404)

        if user_id == request.user.pk:
            return Response({'detail': MSG_SELF}, status=400)

        target_membership = (
            OrganizationMembership.objects.select_related('user')
            .filter(
                user_id=user_id,
                organization_id=org_pk,
                status=OrganizationMembership.MemberStatus.ACTIVE,
            )
            .first()
        )
        if target_membership is None:
            return Response({'detail': MSG_NOT_MEMBER}, status=404)

        if target_membership.org_role not in (
            OrganizationMembership.OrgRole.ADVISOR,
            OrganizationMembership.OrgRole.STUDENT,
        ):
            return Response({'detail': MSG_MEMBER_ONLY}, status=400)

        target = target_membership.user
        claim = {'by': request.user.pk, 'org': membership.organization_id}

        refresh = RefreshToken.for_user(target)
        refresh['imp'] = claim
        refresh.set_exp(lifetime=IMP_LIFETIME)
        access = refresh.access_token
        access['imp'] = claim
        access.set_exp(lifetime=IMP_LIFETIME)

        ImpersonationLog.objects.create(
            manager=request.user,
            target_user=target,
            organization=membership.organization,
        )

        return Response({
            'access': str(access),
            'refresh': str(refresh),
            'user': {'id': target.pk, 'role': target.role},
        })


class ImpersonationStopView(APIView):
    """``POST <org_pk>/impersonate/stop/`` — close the manager's open session.

    ``authentication_classes = []`` on purpose: the credential protocol is
    manual — the manager's own REFRESH token as the bearer — and the default
    JWT authentication would answer a refresh bearer with 401 before this body
    could run. Validation order is the security contract: malformed ⇒ 401,
    ``imp``-claim or access-class token ⇒ 403 (a borrowed session can neither
    end itself nor anyone else's), no open row for THIS org ⇒ 404.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['organizations'],
        summary='پایان جلسه‌ی ورود مستقیم',
        description=(
            'اعتبارنامه: refresh توکن خودِ مدیر در هدر Bearer. بازترین جلسهٔ '
            'بازِ همان مدیر در همان سازمان بسته می‌شود (ended_at ثبت می‌شود).'
        ),
        responses={
            200: OpenApiResponse(description='`{"ended": true}`'),
            401: OpenApiResponse(description='اعتبارنامه‌ی نامعتبر'),
            403: OpenApiResponse(description='توکن از کلاس مجاز نیست'),
            404: OpenApiResponse(description='جلسهٔ بازی وجود ندارد'),
        },
    )
    def post(self, request, org_pk: int):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        raw = header[7:].strip() if header.lower().startswith('bearer ') else ''
        if not raw:
            # Cookie-aware frontend: the borrowed tab still carries the
            # MANAGER's own HttpOnly refresh cookie (impersonation never
            # touches it), so a stop request through the same-origin /api
            # proxy authenticates with it — the same credential the
            # rotated-refresh endpoint already trusts. No body parameter.
            raw = get_refresh_from_request(request) or ''
        if not raw:
            return Response({'detail': MSG_BAD_CREDENTIALS}, status=401)

        try:
            claims = token_backend.decode(raw, verify=True)
        except TokenError:
            return Response({'detail': MSG_BAD_CREDENTIALS}, status=401)

        if claims.get('imp'):
            return Response({'detail': MSG_STAFF_ONLY}, status=403)
        if claims.get('token_type') != 'refresh':
            return Response({'detail': MSG_STAFF_ONLY}, status=403)

        user = User.objects.filter(pk=claims.get('user_id')).first()
        if user is None:
            return Response({'detail': MSG_BAD_CREDENTIALS}, status=401)

        log = (
            ImpersonationLog.objects.filter(
                manager=user,
                organization_id=org_pk,
                ended_at__isnull=True,
            )
            .order_by('-started_at')
            .first()
        )
        if log is None:
            return Response({'detail': MSG_NO_OPEN_SESSION}, status=404)

        log.ended_at = timezone.now()
        log.save(update_fields=['ended_at'])
        return Response({'ended': True})