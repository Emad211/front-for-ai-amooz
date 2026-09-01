"""Wave 5 (2026-08-31) — the parent surface: invite lifecycle, OTP login,
the filtered weekly digest and the student's transparency list.

Four sides, four permission pairs, one rule each:

* the **advisor** routes (``students/<pk>/parents/…``) resolve the engagement
  through ``scope.advisor_engagement`` and 404 for a foreign *or ended* row —
  the ق۶ convention; the only new write in the whole wave is the PENDING link
  plus its revoke, both through ``services/parent_links``;
* the **public OTP** pair under ``parent/login/`` mirrors
  ``InviteCodeLoginView`` mechanically (``authentication_classes=[]``,
  ``AllowAny``, scoped throttle, ``RefreshToken.for_user`` + the HttpOnly
  refresh cookie) while keeping its own OTP cache — see ``services/parent_links``;
* the **parent** routes (``parent/me/…``) are read-only and gated on
  ``IsParentUser``; the digest is numbers-only by construction
  (``services/parent_digest``) and every successful read appends a
  ``parent_digest_view`` access-log row (D4);
* the **student** transparency list (``me/parents/``) shows exactly what the
  student already knows: who their advisor linked, phones masked.

Like every views module here, no view builds a queryset and none may name a
tenancy-bearing model — ``test_import_boundaries`` walks this file too.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import MeSerializer
from apps.authentication.cookies import set_refresh_cookie
from apps.core.permissions import IsAdvisorUser, IsParentUser, IsStudentRole
from apps.core.throttling import SafeScopedRateThrottle

from .serializers import (
    ParentInviteCreateSerializer,
    ParentLoginRequestSerializer,
    ParentLoginVerifySerializer,
    _display_name,
)
from .services import parent_digest as digest_service
from .services import parent_links as parent_service
from .services.scope import advisor_engagement
from .services.text import mask_phone

MSG_NO_ENGAGEMENT = 'همکاری پیدا نشد.'
MSG_NO_LINK = 'پیوند والد پیدا نشد.'


def _engagement_or_404(request, pk: int):
    """Resolve the engagement out of the advisor's visible set, ACTIVE only.

    A foreign id, an unknown id and an ended engagement are one and the same
    404 — a 403 would confirm some advisor works with that student.
    """
    engagement = advisor_engagement(request.user, pk)
    if engagement is None or engagement.status != 'ACTIVE':
        return None, Response({'detail': MSG_NO_ENGAGEMENT}, status=status.HTTP_404_NOT_FOUND)
    return engagement, None


# ── advisor side: the parent-link lifecycle ───────────────────────────────────

class AdvisorParentLinksView(APIView):
    """``POST``/``GET`` ``/api/advisory/students/<pk>/parents/``.

    POST is the student-invite pattern applied to a parent phone: validate the
    shape, check the two-standing-links quota, create the PENDING link and
    enqueue exactly one SMS, answer ``202 {"status": "sent"}`` uniformly. The
    phone's owner is never looked up here — that is the OTP flow's business.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]
    # Without its own scope this inherits 'user' at 300/minute — an
    # authenticated SMS trigger. Same B3 reasoning as 'advisory_invite'.
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'advisory_parent_invite'

    @extend_schema(
        tags=['advisory'],
        summary='دعوت والد دانش‌آموز (ایجاد پیوند)',
        description=(
            '`pk` شناسه‌ی همکاری است؛ همکاری ناموجود، متعلق به مشاورِ دیگر یا '
            'پایان‌یافته ۴۰۴. بدنه `{phone, relation}`؛ شمارهٔ بدشکل یا نسبت '
            'نامعتبر ۴۰۰، بیش از دو والدِ فعال ۴۰۰. پاسخ همیشه `202 '
            '{"status": "sent"}` است و ارسال پیامک در پس‌زمینه انجام می‌شود.'
        ),
        request=ParentInviteCreateSerializer,
        responses={
            202: OpenApiResponse(description='{"status": "sent"}'),
            400: OpenApiResponse(description='شماره یا نسبت نامعتبر؛ سقف دو والد'),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def post(self, request, pk: int):
        engagement, error = _engagement_or_404(request, pk)
        if error is not None:
            return error

        serializer = ParentInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            parent_service.advisor_create_parent_link(
                engagement,
                phone=serializer.validated_data['phone'],
                relation=serializer.validated_data['relation'],
                created_by=request.user,
            )
        except parent_service.ParentLinkError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'sent'}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        tags=['advisory'],
        summary='فهرست والدینِ یک دانش‌آموز',
        description=(
            'همه‌ی پیوندها با هر وضعیتی (در انتظار/فعال/لغوشده) — شماره‌ها '
            'همیشه ماسک‌شده برمی‌گردند، حتی برای مشاوری که خودش وارد کرده است.'
        ),
        responses={
            200: OpenApiResponse(
                description='{links: [{id, phoneMasked, relation, status, createdAt}]}',
            ),
            404: OpenApiResponse(description='همکاری پیدا نشد'),
        },
    )
    def get(self, request, pk: int):
        engagement, error = _engagement_or_404(request, pk)
        if error is not None:
            return error

        return Response({
            'links': [
                {
                    'id': link.pk,
                    'phoneMasked': mask_phone(link.phone),
                    'relation': link.relation,
                    'status': link.status,
                    'createdAt': link.created_at,
                }
                for link in parent_service.advisor_parent_links(engagement)
            ],
        })


class AdvisorParentLinkDetailView(APIView):
    """``DELETE /api/advisory/students/<pk>/parents/<link_id>/`` — revoke.

    Revoke, never delete: the row is the audit trail of who could read what
    and when. A foreign or already-settled link id is a 404, like everywhere.
    """

    permission_classes = [IsAuthenticated, IsAdvisorUser]

    @extend_schema(
        tags=['advisory'],
        summary='لغو دسترسی یک والد',
        description=(
            'پیوند به وضعیت «لغوشده» می‌رود و ردیف نگه داشته می‌شود (سابقه). '
            'پیوندِ ناموجود یا متعلق به دانش‌آموزِ دیگری ۴۰۴.'
        ),
        request=None,
        responses={
            204: OpenApiResponse(description='لغو شد'),
            404: OpenApiResponse(description='همکاری یا پیوند پیدا نشد'),
        },
    )
    def delete(self, request, pk: int, link_id: int):
        engagement, error = _engagement_or_404(request, pk)
        if error is not None:
            return error

        link = parent_service.advisor_revoke_parent_link(engagement, link_id)
        if link is None:
            return Response({'detail': MSG_NO_LINK}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── public: the parent OTP login pair ─────────────────────────────────────────

class ParentLoginRequestView(APIView):
    """``POST /api/advisory/parent/login/request/`` — always ``202 sent``.

    The B2 rule verbatim: a phone with a pending link, a phone with a parent
    account and a phone nobody invited are indistinguishable from outside.
    Only the first two enqueue an OTP; the third enqueues nothing at all.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'parent_login'

    @extend_schema(
        tags=['advisory'],
        summary='درخواست کد ورود والدین',
        description=(
            'برای هر شماره‌ی خوش‌شکل پاسخ یکسان `202 {"status": "sent"}` است — '
            'وجود یا نبودِ پیوند/حساب لو نمی‌رود. کد ۶ رقمی تا ۱۰ دقیقه معتبر '
            'است و فقط برای شماره‌ی شناخته‌شده پیامک می‌شود.'
        ),
        request=ParentLoginRequestSerializer,
        responses={
            202: OpenApiResponse(description='{"status": "sent"}'),
            400: OpenApiResponse(description='شمارهٔ همراه بدشکل'),
        },
    )
    def post(self, request):
        serializer = ParentLoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            parent_service.request_parent_login(serializer.validated_data['phone'])
        except parent_service.ParentLinkError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'sent'}, status=status.HTTP_202_ACCEPTED)


class ParentLoginVerifyView(APIView):
    """``POST /api/advisory/parent/login/verify/`` — code in, JWT out.

    Mechanically ``InviteCodeLoginView``: ``RefreshToken.for_user`` + the
    HttpOnly refresh cookie, so the client-side session handling is identical
    to every other login. On success the PARENT account is minted through the
    shared phone→user seam and every PENDING link for the phone activates.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = 'parent_login'

    @extend_schema(
        tags=['advisory'],
        summary='تأیید کد و ورود والد',
        description=(
            'با کد درست، توکن‌ها + کاربر (نقش `PARENT`) برمی‌گردد و همه‌ی '
            'پیوندهای در انتظارِ این شماره فعال می‌شوند. کد اشتباه/منقضی ۴۰۰.'
        ),
        request=ParentLoginVerifySerializer,
        responses={
            200: OpenApiResponse(description='{access, refresh, user}'),
            400: OpenApiResponse(description='کد واردشده درست یا معتبر نیست'),
        },
    )
    def post(self, request):
        serializer = ParentLoginVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        otp = serializer.validated_data['otp']

        if not parent_service.verify_parent_otp(phone, otp):
            return Response(
                {'detail': parent_service.MSG_BAD_OTP},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = parent_service.complete_parent_login(phone)
        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': MeSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
        set_refresh_cookie(response, str(refresh))
        return response


# ── parent side: the read-only surface ────────────────────────────────────────

class ParentMyLinksView(APIView):
    """``GET /api/advisory/parent/me/links/`` — whose study can I follow?

    Only ACTIVE links on ACTIVE engagements: a revoke, an unclaimed invite and
    an engagement that ended are all simply absent from the list.
    """

    permission_classes = [IsAuthenticated, IsParentUser]

    @extend_schema(
        tags=['advisory'],
        summary='پیوندهای فعالِ والد',
        description=(
            'فقط پیوندهای فعال روی همکاریِ فعال. نام دانش‌آموز و مشاور برای '
            'نمایش است؛ هیچ شماره‌ای برگردانده نمی‌شود.'
        ),
        responses={
            200: OpenApiResponse(
                description='{links: [{id, engagementId, studentName, advisorName, relation, status}]}',
            ),
        },
    )
    def get(self, request):
        return Response({
            'links': [
                {
                    'id': link.pk,
                    'engagementId': link.engagement_id,
                    'studentName': _display_name(link.engagement.student),
                    'advisorName': _display_name(link.engagement.advisor),
                    'relation': link.relation,
                    'status': link.status,
                }
                for link in parent_service.parent_active_links(request.user)
            ],
        })


class ParentLinkDigestView(APIView):
    """``GET /api/advisory/parent/me/links/<link_id>/digest/`` — the weekly digest.

    The payload is the ten numeric keys ``services/parent_digest`` builds —
    mood, notes, mistake texts, call logs and assessment scores have no path
    into it. Every successful read appends one ``parent_digest_view``
    ``AdvisoryAccessLog`` row (D4: a read by someone outside the student/
    advisor pair is logged from the moment it exists). 404 for foreign,
    revoked or ended.
    """

    permission_classes = [IsAuthenticated, IsParentUser]

    @extend_schema(
        tags=['advisory'],
        summary='گزارش هفتگی فرزند (والد)',
        description=(
            'پنجره‌ی ۷ روزه تا امروز؛ فقط اعداد — دقیقه‌های مطالعه، دقیقه‌های '
            'برنامه، درصد پایبندی، تست‌ها، روند آزمون‌ها (۵ مورد آخر)، خطاهای '
            'باز، مرورهای سررسیدشده، چالش جاری و استریک. پیوندِ ناموجود/لغوشده '
            'یا همکاریِ پایان‌یافته ۴۰۴.'
        ),
        responses={
            200: OpenApiResponse(
                description=(
                    '{asOf, weekMinutes, weekPlanMinutes, adherencePercent, '
                    'testsTaken, examTrend[], openMistakesCount, reviewDueCount, '
                    'activeChallengeTitle, streak}'
                ),
            ),
            404: OpenApiResponse(description='پیوند والد پیدا نشد'),
        },
    )
    def get(self, request, link_id: int):
        link = parent_service.parent_digest_link(request.user, link_id)
        if link is None:
            return Response({'detail': MSG_NO_LINK}, status=status.HTTP_404_NOT_FOUND)

        payload = digest_service.build_parent_digest(link.engagement)
        # After the payload, before the answer — a failed read above wrote
        # nothing, so exactly one row lands per successful 200.
        parent_service.record_parent_digest_view(link.engagement, request.user)
        return Response(payload)


# ── student side: transparency ────────────────────────────────────────────────

class StudentMyParentsView(APIView):
    """``GET /api/advisory/me/parents/`` — who else reads my reports?

    The student already consented to the advisor when accepting the
    engagement; this list is the honest answer to «دقیقاً کی می‌تواند گزارش
    مرا ببیند؟». Quiet when there is no active engagement, phones masked.
    """

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='والدینِ متصل به حساب دانش‌آموز',
        description=(
            'پیوندهای فعالِ همکاریِ فعلی؛ بدون مشاورِ فعال `200 '
            '{"parents": []}` — خطا نیست. شماره‌ها ماسک‌شده‌اند.'
        ),
        responses={
            200: OpenApiResponse(description='{parents: [{id, relation, phoneMasked}]}'),
        },
    )
    def get(self, request):
        return Response({
            'parents': [
                {
                    'id': link.pk,
                    'relation': link.relation,
                    'phoneMasked': mask_phone(link.phone),
                }
                for link in parent_service.student_active_parents(request.user)
            ],
        })
