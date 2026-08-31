"""Student-side growth endpoints (research wave 2026-08-31) — ق۱۱: new module.

Six ``me/`` routes covering the three gaps every Iranian consultant fills but
the restart plan did not: the stated goal, the mistake notebook (دفتر
اشتباهات) and per-topic coverage — plus one read-only analytics bundle
(streak, balance, exam trend, plan execution, backlog, review queue).

The permission split is one-sided on purpose: ``IsStudentRole`` everywhere.
Reads follow the quiet rule (no active advisor ⇒ ``{"active": false, …}``,
never an error); writes without an active advisor answer the same 409 the
challenge-days door uses, so the student-side contract stays uniform.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsStudentRole

from .serializers import (
    GoalItemSerializer,
    GoalWriteSerializer,
    MistakeItemSerializer,
    MistakePatchSerializer,
    MistakeWriteSerializer,
    TopicItemSerializer,
    TopicPatchSerializer,
    TopicWriteSerializer,
)
from .services import analytics as analytics_service
from .services import goals as goal_service
from .services import mistakes as mistake_service
from .services import topics as topic_service
from .services.scope import student_active_engagement


class StudentGoalView(APIView):
    """The student's stated destination — read and wholesale replace."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='هدف تحصیلی خودم',
        description=(
            'بدون مشاور فعال `200 {"active": false, "goal": null}` — خطا نیست. '
            'با مشاور فعال، هدفِ ثبت‌شده یا null.'
        ),
        responses={200: OpenApiResponse(description='{active, goal}')},
    )
    def get(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False, 'goal': None})
        goal = goal_service.get_goal(engagement)
        return Response({
            'active': True,
            'goal': GoalItemSerializer(goal).data if goal else None,
        })

    @extend_schema(
        tags=['advisory'],
        summary='ثبت هدف تحصیلی (ایجاد یا به‌روزرسانی)',
        description=(
            '`targetTitle` الزامی و غیرخالی است؛ بقیهٔ کلیدها اختیاری. '
            'بدون مشاور فعال ۴۰۹ با پیام فارسی.'
        ),
        request=GoalWriteSerializer,
        responses={
            200: GoalItemSerializer,
            400: OpenApiResponse(description='هدف نامعتبر'),
            409: OpenApiResponse(description='مشاور فعالی ندارید'),
        },
    )
    def put(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'ابتدا مشاور خود را تأیید کنید.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = GoalWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            goal = goal_service.upsert_goal(
                engagement,
                target_title=data['target_title'],
                target_rank=data.get('target_rank', ''),
                current_rank=data.get('current_rank', ''),
                note=data.get('note', ''),
                updated_by=request.user,
            )
        except goal_service.GoalError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(GoalItemSerializer(goal).data)


class StudentMistakesView(APIView):
    """The student's mistake notebook — list and create."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='دفتر اشتباهات خودم',
        description=(
            'بدون مشاور فعال `200 {"active": false, "mistakes": []}` — خطا نیست. '
            'با مشاور فعال، همهٔ ردیف‌ها (رفع‌نشده‌ها اول، بعد تاریخ نزولی).'
        ),
        responses={200: OpenApiResponse(description='{active, mistakes}')},
    )
    def get(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False, 'mistakes': []})
        rows = mistake_service.list_mistakes(engagement)
        return Response({
            'active': True,
            'mistakes': MistakeItemSerializer(rows, many=True).data,
        })

    @extend_schema(
        tags=['advisory'],
        summary='ثبت یک خطای جدید در دفتر اشتباهات',
        description=(
            '`subjectId` باید درسِ فعالِ انتخاب‌شده باشد وگرنه ۴۰۰؛ `status` و '
            '`errorType` الزامی‌اند. بدون مشاور فعال ۴۰۹.'
        ),
        request=MistakeWriteSerializer,
        responses={
            201: MistakeItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی خطا'),
            409: OpenApiResponse(description='مشاور فعالی ندارید'),
        },
    )
    def post(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'ابتدا مشاور خود را تأیید کنید.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = MistakeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            row = mistake_service.create_mistake(engagement, **data)
        except mistake_service.MistakeError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            MistakeItemSerializer(row).data, status=status.HTTP_201_CREATED,
        )


class StudentMistakeDetailView(APIView):
    """One mistake row — partial edit and delete."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='ویرایش جزئی یک خطا (و/یا رفع آن)',
        description=(
            'فقط کلیدهای ارسالی تغییر می‌کنند؛ `isResolved: true` خطا را حل‌شده '
            'علامت می‌زند (حذف نمی‌کند). خطای متعلق به همکاری دیگر ۴۰۴.'
        ),
        request=MistakePatchSerializer,
        responses={
            200: MistakeItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی'),
            404: OpenApiResponse(description='خطا پیدا نشد'),
            409: OpenApiResponse(description='مشاور فعالی ندارید'),
        },
    )
    def patch(self, request, mistake_id: int):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'ابتدا مشاور خود را تأیید کنید.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = MistakePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = mistake_service.update_mistake(
                engagement, mistake_id, patch=serializer.validated_data,
            )
        except mistake_service.MistakeError as exc:
            code = (
                status.HTTP_404_NOT_FOUND
                if isinstance(exc, mistake_service.MistakeNotFound)
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': str(exc)}, status=code)
        return Response(MistakeItemSerializer(row).data)

    @extend_schema(
        tags=['advisory'],
        summary='حذف یک خطا',
        description=('حذف قطعی ردیف؛ خطای متعلق به همکاری دیگر ۴۰۴.'),
        responses={
            204: OpenApiResponse(description='حذف شد'),
            404: OpenApiResponse(description='خطا پیدا نشد'),
            409: OpenApiResponse(description='مشاور فعالی ندارید'),
        },
    )
    def delete(self, request, mistake_id: int):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'ابتدا مشاور خود را تأیید کنید.'},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            mistake_service.delete_mistake(engagement, mistake_id)
        except mistake_service.MistakeError:
            return Response(
                {'detail': 'این خطا پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentTopicsView(APIView):
    """Per-topic coverage — list and add."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='مباحث و وضعیتشان (پوشش مبحث)',
        description=(
            'بدون مشاور فعال `200 {"active": false, "topics": []}`. با مشاور '
            'فعال، همهٔ ردیف‌ها مرتب بر نام درس و مبحث.'
        ),
        responses={200: OpenApiResponse(description='{active, topics}')},
    )
    def get(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False, 'topics': []})
        rows = topic_service.list_topics(engagement)
        return Response({
            'active': True,
            'topics': TopicItemSerializer(rows, many=True).data,
        })

    @extend_schema(
        tags=['advisory'],
        summary='افزودن یک مبحث',
        description=(
            '`subjectId` باید درسِ فعال باشد؛ مبحث تکراری ۴۰۰ با پیام فارسی. '
            'وضعیت پیش‌فرض NEW است.'
        ),
        request=TopicWriteSerializer,
        responses={
            201: TopicItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی مبحث'),
            409: OpenApiResponse(description='مشاور فعالی ندارید'),
        },
    )
    def post(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'ابتدا مشاور خود را تأیید کنید.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = TopicWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = topic_service.create_topic(engagement, **serializer.validated_data)
        except topic_service.TopicError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TopicItemSerializer(row).data, status=status.HTTP_201_CREATED)


class StudentTopicDetailView(APIView):
    """One topic row — status change, rename, delete."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='تغییر وضعیت/نام یک مبحث',
        description=(
            'فقط کلیدهای ارسالی تغییر می‌کنند. رفتن به «نیاز به مرور» بدون تاریخ '
            'صراحی، مرور را دو روز بعد می‌گذارد؛ «تسلط‌یافته» تاریخ مرور را پاک '
            'می‌کند.'
        ),
        request=TopicPatchSerializer,
        responses={
            200: TopicItemSerializer,
            400: OpenApiResponse(description='اعتبارسنجی'),
            404: OpenApiResponse(description='مبحث پیدا نشد'),
            409: OpenApiResponse(description='مشاور فعالی ندارید'),
        },
    )
    def patch(self, request, topic_id: int):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'ابتدا مشاور خود را تأیید کنید.'},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = TopicPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = topic_service.update_topic(
                engagement, topic_id, patch=serializer.validated_data,
            )
        except topic_service.TopicError as exc:
            code = (
                status.HTTP_404_NOT_FOUND
                if isinstance(exc, topic_service.TopicNotFound)
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': str(exc)}, status=code)
        return Response(TopicItemSerializer(row).data)

    @extend_schema(
        tags=['advisory'],
        summary='حذف یک مبحث',
        description=('حذف قطعی ردیف؛ مبحث متعلق به همکاری دیگر ۴۰۴.'),
        responses={
            204: OpenApiResponse(description='حذف شد'),
            404: OpenApiResponse(description='مبحث پیدا نشد'),
            409: OpenApiResponse(description='مشاور فعالی ندارید'),
        },
    )
    def delete(self, request, topic_id: int):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response(
                {'detail': 'ابتدا مشاور خود را تأیید کنید.'},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            topic_service.delete_topic(engagement, topic_id)
        except topic_service.TopicError:
            return Response(
                {'detail': 'این مبحث پیدا نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentAnalyticsView(APIView):
    """The read-only analytics bundle (streak, balance, trend, backlog…)."""

    permission_classes = [IsAuthenticated, IsStudentRole]

    @extend_schema(
        tags=['advisory'],
        summary='تحلیل پیشرفت خودم',
        description=(
            'بدون مشاور فعال `200 {"active": false}` — خطا نیست. با مشاور فعال: '
            'روزهای پیوستهٔ ثبت گزارش، تعادل مطالعاتی ۳۰ روز، روند آزمون‌ها، '
            'درصد اجرای برنامهٔ جاری، عقب‌افتادگی‌های جبران‌نشده و صف مرور.'
        ),
        responses={200: OpenApiResponse(description='{active, …analytics}')},
    )
    def get(self, request):
        engagement = student_active_engagement(request.user)
        if engagement is None:
            return Response({'active': False})
        payload = analytics_service.compute_analytics(engagement)
        return Response({'active': True, **payload})
