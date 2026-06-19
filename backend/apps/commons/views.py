"""REST API endpoints for admin dashboard (admin-only)."""

from __future__ import annotations

import csv
import os
import shutil
import time
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Count, F, Prefetch, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin as IsAdminUser

from apps.commons.models import (
    AdminSetting,
    DEPARTMENT_LABELS,
    LLMUsageLog,
    ModelPrice,
    Ticket,
    TicketMessage,
)
from apps.commons.exchange_rate import get_usdt_toman_rate, usd_to_toman

User = get_user_model()

# ---------------------------------------------------------------------------
# Startup timestamp for uptime calculation
# ---------------------------------------------------------------------------
_STARTUP_TIME = time.time()


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

class LLMUsageSummarySerializer(serializers.Serializer):
    total_requests = serializers.IntegerField()
    successful_requests = serializers.IntegerField()
    failed_requests = serializers.IntegerField()
    total_input_tokens = serializers.IntegerField()
    total_output_tokens = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost_usd = serializers.FloatField()
    avg_duration_ms = serializers.FloatField()


class LLMUsageByFeatureSerializer(serializers.Serializer):
    feature = serializers.CharField()
    feature_label = serializers.CharField()
    count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost_usd = serializers.FloatField()
    total_cost_toman = serializers.FloatField()
    avg_duration_ms = serializers.FloatField()


class LLMUsageByUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(allow_null=True)
    username = serializers.CharField()
    full_name = serializers.CharField()
    role = serializers.CharField()
    count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost_usd = serializers.FloatField()
    total_cost_toman = serializers.FloatField()


class LLMUsageByProviderSerializer(serializers.Serializer):
    provider = serializers.CharField()
    count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost_usd = serializers.FloatField()
    total_cost_toman = serializers.FloatField()


class LLMUsageDailySerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost_usd = serializers.FloatField()
    total_cost_toman = serializers.FloatField()


class ModelPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelPrice
        fields = [
            'id', 'provider', 'model_name',
            'input_usd_per_1m', 'output_usd_per_1m',
            'audio_input_usd_per_1m', 'cached_input_usd_per_1m',
            'is_active', 'effective_from', 'note',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LLMUsageRecentLogSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user = serializers.CharField(allow_null=True)
    feature = serializers.CharField()
    provider = serializers.CharField()
    model_name = serializers.CharField()
    input_tokens = serializers.IntegerField()
    output_tokens = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    estimated_cost_usd = serializers.FloatField()
    duration_ms = serializers.IntegerField()
    success = serializers.BooleanField()
    created_at = serializers.DateTimeField()


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def _parse_boundary(value: str, *, end: bool):
    """Parse an ISO date or datetime into an aware datetime.

    For a bare ``YYYY-MM-DD`` used as the ``to`` boundary we snap to the end
    of that day so the range is inclusive.
    """
    value = (value or '').strip()
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        d = parse_date(value)
        if d is None:
            return None
        dt = datetime.combine(d, dtime.max if end else dtime.min)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _get_date_filter(request) -> dict:
    """Build a ``created_at`` range filter from ``from``/``to`` or ``days``.

    ``from``/``to`` accept ISO date (``YYYY-MM-DD``) or datetime. When neither
    is provided (or both unparseable), falls back to ``days`` (default 30).
    """
    qp = request.query_params
    filters: dict = {}

    dt_from = _parse_boundary(qp.get('from', ''), end=False)
    dt_to = _parse_boundary(qp.get('to', ''), end=True)
    if dt_from is not None:
        filters['created_at__gte'] = dt_from
    if dt_to is not None:
        filters['created_at__lte'] = dt_to
    if filters:
        return filters

    try:
        days = int(qp.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))
    return {'created_at__gte': timezone.now() - timedelta(days=days)}


class LLMUsageSummaryView(APIView):
    """Overall usage summary with Toman conversion."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        filters = _get_date_filter(request)
        qs = LLMUsageLog.objects.filter(**filters)
        agg = qs.aggregate(
            total_requests=Count('id'),
            successful_requests=Count('id', filter=Q(success=True)),
            failed_requests=Count('id', filter=Q(success=False)),
            total_input_tokens=Sum('input_tokens'),
            total_output_tokens=Sum('output_tokens'),
            total_tokens=Sum('total_tokens'),
            total_cost_usd=Sum('estimated_cost_usd'),
            total_cost_toman=Sum('estimated_cost_toman'),
            avg_duration_ms=Avg('duration_ms'),
            total_audio_input_tokens=Sum('audio_input_tokens'),
            total_cached_input_tokens=Sum('cached_input_tokens'),
            total_thinking_tokens=Sum('thinking_tokens'),
        )
        # Replace None with 0
        for key in agg:
            if agg[key] is None:
                agg[key] = 0

        # total_cost_toman is the historically-accurate sum of per-row Toman
        # snapshots. Also expose the current live rate for reference / display.
        agg['total_cost_toman'] = float(agg['total_cost_toman'])
        usdt_rate, _ = get_usdt_toman_rate()
        agg['usdt_toman_rate'] = usdt_rate

        return Response(agg)


class LLMUsageByFeatureView(APIView):
    """Usage breakdown by feature."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        filters = _get_date_filter(request)
        qs = (
            LLMUsageLog.objects
            .filter(**filters)
            .values('feature')
            .annotate(
                count=Count('id'),
                total_tokens=Sum('total_tokens'),
                total_cost_usd=Sum('estimated_cost_usd'),
                total_cost_toman=Sum('estimated_cost_toman'),
                avg_duration_ms=Avg('duration_ms'),
            )
            .order_by('-total_cost_toman')
        )
        feature_labels = dict(LLMUsageLog.Feature.choices)
        result = []
        for row in qs:
            row['feature_label'] = feature_labels.get(row['feature'], row['feature'])
            for k in ('total_tokens', 'total_cost_usd', 'total_cost_toman', 'avg_duration_ms'):
                if row[k] is None:
                    row[k] = 0
            result.append(row)
        return Response(result)


class LLMUsageByUserView(APIView):
    """Usage breakdown by user (all users, with optional role filter)."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        filters = _get_date_filter(request)

        # Optional role filter: ?role=teacher or ?role=student
        role = request.query_params.get('role', '').strip().lower()
        if role in ('teacher', 'student', 'admin'):
            filters['user__role'] = role

        qs = (
            LLMUsageLog.objects
            .filter(**filters)
            .values('user', 'user__username', 'user__first_name', 'user__last_name', 'user__role')
            .annotate(
                count=Count('id'),
                total_tokens=Sum('total_tokens'),
                total_cost_usd=Sum('estimated_cost_usd'),
                total_cost_toman=Sum('estimated_cost_toman'),
            )
            .order_by('-total_cost_toman')
        )
        result = []
        for row in qs:
            first = row.get('user__first_name') or ''
            last = row.get('user__last_name') or ''
            result.append({
                'user_id': row.get('user'),
                'username': row.get('user__username') or 'system',
                'full_name': f'{first} {last}'.strip() or '-',
                'role': row.get('user__role') or '-',
                'count': row['count'],
                'total_tokens': row['total_tokens'] or 0,
                'total_cost_usd': float(row['total_cost_usd'] or 0),
                'total_cost_toman': float(row['total_cost_toman'] or 0),
            })
        return Response(result)


class LLMUsageByProviderView(APIView):
    """Usage breakdown by LLM provider."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        filters = _get_date_filter(request)
        qs = (
            LLMUsageLog.objects
            .filter(**filters)
            .values('provider')
            .annotate(
                count=Count('id'),
                total_tokens=Sum('total_tokens'),
                total_cost_usd=Sum('estimated_cost_usd'),
                total_cost_toman=Sum('estimated_cost_toman'),
            )
            .order_by('-total_cost_toman')
        )
        result = []
        for row in qs:
            for k in ('total_tokens', 'total_cost_usd', 'total_cost_toman'):
                if row[k] is None:
                    row[k] = 0
            result.append(row)
        return Response(result)


class LLMUsageDailyView(APIView):
    """Daily usage time-series."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        filters = _get_date_filter(request)
        qs = (
            LLMUsageLog.objects
            .filter(**filters)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(
                count=Count('id'),
                total_tokens=Sum('total_tokens'),
                total_cost_usd=Sum('estimated_cost_usd'),
                total_cost_toman=Sum('estimated_cost_toman'),
            )
            .order_by('date')
        )
        result = []
        for row in qs:
            for k in ('total_tokens', 'total_cost_usd', 'total_cost_toman'):
                if row[k] is None:
                    row[k] = 0
            result.append({
                'date': row['date'].isoformat() if row['date'] else None,
                'count': row['count'],
                'total_tokens': row['total_tokens'],
                'total_cost_usd': float(row['total_cost_usd']),
                'total_cost_toman': float(row['total_cost_toman']),
            })
        return Response(result)


class LLMUsageRecentLogsView(APIView):
    """Recent LLM call logs (last 100)."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 100))
        except (TypeError, ValueError):
            limit = 100
        limit = max(1, min(limit, 500))

        qs = LLMUsageLog.objects.select_related('user').order_by('-created_at')[:limit]
        result = []
        for log in qs:
            result.append({
                'id': log.id,
                'user': log.user.username if log.user else None,
                'feature': log.feature,
                'provider': log.provider,
                'model_name': log.model_name,
                'input_tokens': log.input_tokens,
                'output_tokens': log.output_tokens,
                'total_tokens': log.total_tokens,
                'audio_input_tokens': log.audio_input_tokens,
                'cached_input_tokens': log.cached_input_tokens,
                'thinking_tokens': log.thinking_tokens,
                'estimated_cost_usd': float(log.estimated_cost_usd),
                'estimated_cost_toman': float(log.estimated_cost_toman),
                'duration_ms': log.duration_ms,
                'success': log.success,
                'created_at': log.created_at.isoformat(),
            })
        return Response(result)


# ═══════════════════════════════════════════════════════════════════════════
# Flexible breakdown (per-user × per-task, any range) + CSV export
# ═══════════════════════════════════════════════════════════════════════════

_BREAKDOWN_GROUPS = {'user', 'feature', 'provider', 'day'}
_GROUP_VALUE_FIELDS = {
    'user': ['user', 'user__username', 'user__first_name', 'user__last_name', 'user__role'],
    'feature': ['feature'],
    'provider': ['provider'],
}


def _apply_usage_filters(request) -> dict:
    """Date range (from/to or days) + optional user_id/role/feature/provider."""
    filters = _get_date_filter(request)
    qp = request.query_params

    role = (qp.get('role') or '').strip().lower()
    if role in ('teacher', 'student', 'admin'):
        filters['user__role'] = role

    user_id = (qp.get('user_id') or '').strip()
    if user_id.isdigit():
        filters['user_id'] = int(user_id)

    feature = (qp.get('feature') or '').strip()
    if feature:
        filters['feature'] = feature

    provider = (qp.get('provider') or '').strip()
    if provider:
        filters['provider'] = provider

    return filters


def _aggregate_usage(request):
    """Return (groups, rows) aggregated by the requested group_by dimensions.

    Each row carries count, token sums, and USD + Toman cost sums. Powers both
    the breakdown JSON endpoint and the CSV export.
    """
    filters = _apply_usage_filters(request)

    raw_group = request.query_params.get('group_by', 'user,feature')
    groups = [g.strip() for g in raw_group.split(',') if g.strip() in _BREAKDOWN_GROUPS]
    if not groups:
        groups = ['user', 'feature']

    qs = LLMUsageLog.objects.filter(**filters)
    if 'day' in groups:
        qs = qs.annotate(day=TruncDate('created_at'))

    value_fields: list[str] = []
    for g in groups:
        if g == 'day':
            value_fields.append('day')
        else:
            value_fields.extend(_GROUP_VALUE_FIELDS[g])
    # de-dupe, preserve order
    seen: set[str] = set()
    value_fields = [f for f in value_fields if not (f in seen or seen.add(f))]

    rows = (
        qs.values(*value_fields)
        .annotate(
            count=Count('id'),
            total_tokens=Sum('total_tokens'),
            total_input_tokens=Sum('input_tokens'),
            total_output_tokens=Sum('output_tokens'),
            total_cost_usd=Sum('estimated_cost_usd'),
            total_cost_toman=Sum('estimated_cost_toman'),
        )
        .order_by('-total_cost_toman')
    )

    feature_labels = dict(LLMUsageLog.Feature.choices)
    result = []
    for row in rows:
        item = {
            'count': row['count'],
            'total_tokens': row['total_tokens'] or 0,
            'total_input_tokens': row['total_input_tokens'] or 0,
            'total_output_tokens': row['total_output_tokens'] or 0,
            'total_cost_usd': float(row['total_cost_usd'] or 0),
            'total_cost_toman': float(row['total_cost_toman'] or 0),
        }
        if 'user' in groups:
            first = row.get('user__first_name') or ''
            last = row.get('user__last_name') or ''
            item['user_id'] = row.get('user')
            item['username'] = row.get('user__username') or 'system'
            item['full_name'] = f'{first} {last}'.strip() or '-'
            item['role'] = row.get('user__role') or '-'
        if 'feature' in groups:
            item['feature'] = row.get('feature')
            item['feature_label'] = feature_labels.get(row.get('feature'), row.get('feature'))
        if 'provider' in groups:
            item['provider'] = row.get('provider')
        if 'day' in groups:
            d = row.get('day')
            item['date'] = d.isoformat() if d else None
        result.append(item)

    return groups, result


class LLMUsageBreakdownView(APIView):
    """Flexible cost breakdown grouped by any of user/feature/provider/day.

    Query params: ``from``/``to`` (ISO) or ``days``; optional ``user_id``,
    ``role``, ``feature``, ``provider``; ``group_by`` = comma list of
    ``user,feature,provider,day`` (default ``user,feature``). Returns Toman
    (snapshotted, historically accurate) and USD per group.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        groups, result = _aggregate_usage(request)
        usdt_rate, _ = get_usdt_toman_rate()
        return Response({
            'group_by': groups,
            'usdt_toman_rate': usdt_rate,
            'results': result,
        })


class LLMUsageExportCSVView(APIView):
    """CSV export of the same breakdown (per-user × per-task Toman, etc.)."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        groups, result = _aggregate_usage(request)

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="llm_usage_report.csv"'
        writer = csv.writer(response)

        header: list[str] = []
        if 'user' in groups:
            header += ['User ID', 'Username', 'Full Name', 'Role']
        if 'feature' in groups:
            header += ['Feature', 'Feature Label']
        if 'provider' in groups:
            header += ['Provider']
        if 'day' in groups:
            header += ['Date']
        header += ['Requests', 'Total Tokens', 'Input Tokens', 'Output Tokens', 'Cost (USD)', 'Cost (Toman)']
        writer.writerow(header)

        for item in result:
            row: list = []
            if 'user' in groups:
                row += [item.get('user_id'), item.get('username'), item.get('full_name'), item.get('role')]
            if 'feature' in groups:
                row += [item.get('feature'), item.get('feature_label')]
            if 'provider' in groups:
                row += [item.get('provider')]
            if 'day' in groups:
                row += [item.get('date')]
            row += [
                item['count'], item['total_tokens'],
                item['total_input_tokens'], item['total_output_tokens'],
                f"{item['total_cost_usd']:.6f}", f"{item['total_cost_toman']:.2f}",
            ]
            writer.writerow(row)

        return response


# ═══════════════════════════════════════════════════════════════════════════
# Model price table (admin-editable)
# ═══════════════════════════════════════════════════════════════════════════

class ModelPriceListCreateView(APIView):
    """List all model prices or create a new one."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        prices = ModelPrice.objects.all()
        return Response(ModelPriceSerializer(prices, many=True).data)

    def post(self, request):
        serializer = ModelPriceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ModelPriceDetailView(APIView):
    """Retrieve, update, or delete a single model price row."""
    permission_classes = [IsAdminUser]

    def _get(self, pk):
        return ModelPrice.objects.filter(pk=pk).first()

    def patch(self, request, price_pk):
        obj = self._get(price_pk)
        if obj is None:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ModelPriceSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, price_pk):
        obj = self._get(price_pk)
        if obj is None:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════════════════
# Exchange Rate
# ═══════════════════════════════════════════════════════════════════════════

class ExchangeRateView(APIView):
    """Get live USDT→Toman exchange rate."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        rate, err = get_usdt_toman_rate()
        return Response({
            'usdt_toman_rate': rate,
            'error': err,
        })


# ═══════════════════════════════════════════════════════════════════════════
# Analytics (Tehran-aware, derived entirely from existing models)
# ═══════════════════════════════════════════════════════════════════════════

TEHRAN_TZ = ZoneInfo('Asia/Tehran')

_ROLE_FA = {'STUDENT': 'دانش‌آموز', 'TEACHER': 'معلم', 'ADMIN': 'مدیر', 'MANAGER': 'مدیر سازمان آموزشی'}


def _tehran_now():
    return timezone.now().astimezone(TEHRAN_TZ)


def _tehran_day_start(days_ago: int = 0):
    """Midnight (Tehran) ``days_ago`` days back, as a tz-aware datetime.

    The server stores UTC; bucketing by UTC put a 1am-Tehran event on the
    previous calendar day. All "today / last N days" windows use this so the
    numbers match what an admin in Tehran expects.
    """
    start = _tehran_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(days=days_ago)


def _display_name(user) -> str:
    if user is None:
        return 'کاربر حذف‌شده'
    full = user.get_full_name()
    return full or user.username or (user.phone or '') or f'#{user.pk}'


class AnalyticsStatsView(APIView):
    """Comprehensive, Tehran-local platform metrics for the analytics page.

    Grouped into users / classes / engagement / llm / support / orgs. A few
    flat back-compat keys are kept for any older caller.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.classes.models import (
            ClassCreationSession,
            ClassSectionQuizAttempt,
            ClassFinalExamAttempt,
            StudentExamPrepAttempt,
            StudentCourseChatMessage,
        )
        from apps.organizations.models import Organization

        Status = ClassCreationSession.Status
        today = _tehran_day_start(0)
        d7 = _tehran_day_start(7)
        d30 = _tehran_day_start(30)
        d60 = _tehran_day_start(60)

        # --- Users ---
        by_role = {
            r['role']: r['c']
            for r in User.objects.values('role').annotate(c=Count('id'))
        }
        students = by_role.get('STUDENT', 0)
        teachers = by_role.get('TEACHER', 0)
        managers = by_role.get('MANAGER', 0)
        admins = by_role.get('ADMIN', 0)
        total_users = sum(by_role.values())
        new_today = User.objects.filter(date_joined__gte=today).count()
        new_7d = User.objects.filter(date_joined__gte=d7).count()
        new_30d = User.objects.filter(date_joined__gte=d30).count()
        prev_30d = User.objects.filter(date_joined__gte=d60, date_joined__lt=d30).count()
        logged_in_7d = User.objects.filter(last_login__gte=d7).count()
        logged_in_30d = User.objects.filter(last_login__gte=d30).count()

        # --- Classes / pipelines ---
        by_status = {
            r['status']: r['c']
            for r in ClassCreationSession.objects.values('status').annotate(c=Count('id'))
        }
        total_classes = sum(by_status.values())
        published = ClassCreationSession.objects.filter(is_published=True).count()
        failed = by_status.get(Status.FAILED, 0)
        cancelled = by_status.get(Status.CANCELLED, 0)
        done_statuses = {Status.RECAPPED, Status.EXAM_STRUCTURED, Status.FAILED, Status.CANCELLED}
        processing = sum(c for s, c in by_status.items() if s not in done_statuses)
        classes_today = ClassCreationSession.objects.filter(created_at__gte=today).count()
        classes_7d = ClassCreationSession.objects.filter(created_at__gte=d7).count()
        classes_30d = ClassCreationSession.objects.filter(created_at__gte=d30).count()
        class_pipeline = ClassCreationSession.objects.filter(pipeline_type='class').count()
        exam_pipeline = ClassCreationSession.objects.filter(pipeline_type='exam_prep').count()

        # --- Engagement / learning ---
        chat_msgs = StudentCourseChatMessage.objects.filter(role='user')
        chat_total = chat_msgs.count()
        chat_today = chat_msgs.filter(created_at__gte=today).count()
        chat_7d = chat_msgs.filter(created_at__gte=d7).count()
        chat_30d = chat_msgs.filter(created_at__gte=d30).count()
        quiz_total = ClassSectionQuizAttempt.objects.count()
        quiz_7d = ClassSectionQuizAttempt.objects.filter(created_at__gte=d7).count()
        quiz_passed = ClassSectionQuizAttempt.objects.filter(passed=True).count()
        quiz_pass_rate = round(quiz_passed / quiz_total * 100, 1) if quiz_total else 0.0
        final_exam_attempts = ClassFinalExamAttempt.objects.count()
        exam_prep_attempts = StudentExamPrepAttempt.objects.filter(finalized=True).count()
        learners_quiz = set(
            ClassSectionQuizAttempt.objects
            .filter(created_at__gte=d7)
            .values_list('quiz__student_id', flat=True)
        )
        learners_chat = set(
            chat_msgs.filter(created_at__gte=d7).values_list('thread__student_id', flat=True)
        )
        active_learners_7d = len(learners_quiz | learners_chat)

        # --- LLM cost / usage ---
        month_start = _tehran_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        llm_today = LLMUsageLog.objects.filter(created_at__gte=today).aggregate(c=Sum('estimated_cost_usd'))['c'] or 0
        llm_month = LLMUsageLog.objects.filter(created_at__gte=month_start).aggregate(c=Sum('estimated_cost_usd'))['c'] or 0
        llm_agg = LLMUsageLog.objects.aggregate(
            cost=Sum('estimated_cost_usd'), reqs=Count('id'), tokens=Sum('total_tokens'),
        )
        llm_failed = LLMUsageLog.objects.filter(success=False).count()

        # --- Support / orgs ---
        ticket_rows = {
            r['status']: r['c']
            for r in Ticket.objects.values('status').annotate(c=Count('id'))
        }
        tickets_total = sum(ticket_rows.values())
        tickets_open = ticket_rows.get('open', 0) + ticket_rows.get('pending', 0)
        orgs_total = Organization.objects.count()

        return Response({
            'users': {
                'total': total_users, 'students': students, 'teachers': teachers,
                'managers': managers, 'admins': admins,
                'new_today': new_today, 'new_7d': new_7d, 'new_30d': new_30d,
                'prev_30d': prev_30d,
                'logged_in_7d': logged_in_7d, 'logged_in_30d': logged_in_30d,
            },
            'classes': {
                'total': total_classes, 'published': published, 'processing': processing,
                'failed': failed, 'cancelled': cancelled,
                'created_today': classes_today, 'created_7d': classes_7d, 'created_30d': classes_30d,
                'class_pipeline': class_pipeline, 'exam_pipeline': exam_pipeline,
            },
            'engagement': {
                'chat_total': chat_total, 'chat_today': chat_today,
                'chat_7d': chat_7d, 'chat_30d': chat_30d,
                'quiz_total': quiz_total, 'quiz_7d': quiz_7d, 'quiz_pass_rate': quiz_pass_rate,
                'final_exam_attempts': final_exam_attempts,
                'exam_prep_attempts': exam_prep_attempts,
                'active_learners_7d': active_learners_7d,
            },
            'llm': {
                'cost_today': round(float(llm_today), 4),
                'cost_month': round(float(llm_month), 4),
                'cost_total': round(float(llm_agg['cost'] or 0), 4),
                'requests_total': llm_agg['reqs'] or 0,
                'requests_failed': llm_failed,
                'tokens_total': int(llm_agg['tokens'] or 0),
            },
            'support': {'tickets_open': tickets_open, 'tickets_total': tickets_total},
            'orgs': {'total': orgs_total},
            # --- Back-compat flat keys ---
            'total_students': students,
            'total_teachers': teachers,
            'active_classes': published,
            'total_classes': total_classes,
            'recent_messages': chat_30d,
            'recent_quiz_attempts': quiz_7d,
            'new_students_30d': new_30d,
            'student_change': new_30d - prev_30d,
            'llm_cost_this_month': round(float(llm_month), 4),
            'generated_at': timezone.now().isoformat(),
        })


class AnalyticsChartView(APIView):
    """Daily multi-metric time-series (last N days), bucketed in Tehran time.

    Returns one row per Tehran day with registrations, classes created, quiz
    attempts and chat messages — zero-filled so the chart has no gaps.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.classes.models import ClassCreationSession, ClassSectionQuizAttempt, StudentCourseChatMessage

        try:
            days = int(request.query_params.get('days', 14))
        except (TypeError, ValueError):
            days = 14
        days = max(1, min(days, 90))
        since = _tehran_day_start(days - 1)

        def _daily(qs, field):
            rows = (
                qs.filter(**{f'{field}__gte': since})
                .annotate(d=TruncDate(field, tzinfo=TEHRAN_TZ))
                .values('d').annotate(c=Count('id'))
            )
            return {r['d'].isoformat(): r['c'] for r in rows if r['d'] is not None}

        regs = _daily(User.objects.all(), 'date_joined')
        classes = _daily(ClassCreationSession.objects.all(), 'created_at')
        quizzes = _daily(ClassSectionQuizAttempt.objects.all(), 'created_at')
        chats = _daily(StudentCourseChatMessage.objects.filter(role='user'), 'created_at')

        today_t = _tehran_now().date()
        out = []
        for i in range(days):
            day = (today_t - timedelta(days=days - 1 - i)).isoformat()
            out.append({
                'date': day,
                'registrations': regs.get(day, 0),
                'classes': classes.get(day, 0),
                'quizzes': quizzes.get(day, 0),
                'chats': chats.get(day, 0),
                # Back-compat: the old chart read `count` as registrations.
                'count': regs.get(day, 0),
            })
        return Response(out)


class AnalyticsDistributionView(APIView):
    """Class distribution by pipeline type, level, and processing status."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.classes.models import ClassCreationSession

        by_type = list(
            ClassCreationSession.objects
            .values('pipeline_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        by_level = list(
            ClassCreationSession.objects
            .exclude(level='')
            .values('level')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        by_status = list(
            ClassCreationSession.objects
            .values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        return Response({
            'by_pipeline_type': by_type,
            'by_level': by_level,
            'by_status': by_status,
        })


class AnalyticsRecentActivityView(APIView):
    """A unified, chronological feed of what users actually do on the platform.

    Merged from existing models (no separate audit store): logins,
    registrations, class/exam-prep creation, quiz & exam attempts, support
    tickets and admin broadcasts. Query params: ``?limit=`` (default 25, max
    100) and ``?type=`` (comma-separated filter on the event types below).
    """

    permission_classes = [IsAdminUser]

    # type -> category (for frontend grouping/icons)
    TYPES = {
        'login': 'auth', 'registration': 'auth',
        'class_created': 'content', 'class_published': 'content', 'exam_prep_created': 'content',
        'quiz': 'learning', 'final_exam': 'learning', 'exam_prep_attempt': 'learning',
        'ticket': 'support', 'ticket_reply': 'support', 'broadcast': 'system',
    }

    def get(self, request):
        from apps.classes.models import (
            ClassCreationSession,
            ClassSectionQuizAttempt,
            ClassFinalExamAttempt,
            StudentExamPrepAttempt,
        )
        from apps.notification.models import AdminNotification

        try:
            limit = int(request.query_params.get('limit', 25))
        except (TypeError, ValueError):
            limit = 25
        limit = max(1, min(limit, 100))
        wanted = {t.strip() for t in (request.query_params.get('type') or '').split(',') if t.strip()}
        # Pull a few more than `limit` from each source so the merge is accurate.
        per = min(max(limit, 20), 60)

        items: list[dict] = []

        def add(type_, user, action, when, *, target='', user_role=''):
            if when is None or (wanted and type_ not in wanted):
                return
            items.append({
                'type': type_,
                'category': self.TYPES.get(type_, 'system'),
                'user': user,
                'user_role': user_role,
                'action': action,
                'target': target,
                'time': when.isoformat(),
            })

        # Logins (last_login now updated on every token obtain)
        for u in User.objects.filter(last_login__isnull=False).order_by('-last_login')[:per]:
            add('login', _display_name(u), 'وارد سیستم شد', u.last_login, user_role=u.role)

        # Registrations
        for u in User.objects.order_by('-date_joined')[:per]:
            role_fa = _ROLE_FA.get(u.role, u.role)
            add('registration', _display_name(u), f'به عنوان {role_fa} ثبت‌نام کرد', u.date_joined, user_role=u.role)

        # Class / exam-prep creations
        for c in ClassCreationSession.objects.select_related('teacher').order_by('-created_at')[:per]:
            is_exam = c.pipeline_type == 'exam_prep'
            verb = 'آمادگی آزمون' if is_exam else 'کلاس'
            add(
                'exam_prep_created' if is_exam else 'class_created',
                _display_name(c.teacher),
                f'{verb} «{c.title or "بدون عنوان"}» را ساخت',
                c.created_at, target=c.title or '', user_role='TEACHER',
            )

        # Section-quiz attempts
        for a in ClassSectionQuizAttempt.objects.select_related('quiz', 'quiz__student').order_by('-created_at')[:per]:
            stu = a.quiz.student if a.quiz else None
            verdict = 'قبول' if a.passed else 'مردود'
            add('quiz', _display_name(stu), f'در آزمونک نمره {a.score_0_100} گرفت ({verdict})',
                a.created_at, user_role='STUDENT')

        # Final-exam attempts
        for a in ClassFinalExamAttempt.objects.select_related('exam', 'exam__student').order_by('-created_at')[:per]:
            stu = a.exam.student if a.exam else None
            verdict = 'قبول' if a.passed else 'مردود'
            add('final_exam', _display_name(stu), f'در آزمون نهایی نمره {a.score_0_100} گرفت ({verdict})',
                a.created_at, user_role='STUDENT')

        # Exam-prep attempts (finalized)
        for a in (StudentExamPrepAttempt.objects.select_related('student')
                  .filter(finalized=True).order_by('-updated_at')[:per]):
            score = a.score_0_100 if a.score_0_100 is not None else 0
            add('exam_prep_attempt', _display_name(a.student),
                f'آزمون آمادگی را تمام کرد (نمره {score})', a.updated_at, user_role='STUDENT')

        # Support tickets + replies
        for t in Ticket.objects.select_related('user').order_by('-created_at')[:per]:
            add('ticket', _display_name(t.user), f'تیکت «{t.subject}» را ثبت کرد',
                t.created_at, target=t.subject, user_role=getattr(t.user, 'role', ''))
        for m in (TicketMessage.objects.select_related('user', 'ticket')
                  .order_by('-created_at')[:per]):
            add('ticket_reply', _display_name(m.user), f'به تیکت «{m.ticket.subject}» پاسخ داد',
                m.created_at, target=m.ticket.subject, user_role=getattr(m.user, 'role', ''))

        # Admin broadcasts
        for n in AdminNotification.objects.order_by('-created_at')[:per]:
            add('broadcast', 'مدیر', f'پیام «{n.title}» را ارسال کرد', n.created_at, target=n.title, user_role='ADMIN')

        items.sort(key=lambda x: x['time'], reverse=True)
        for idx, it in enumerate(items[:limit]):
            it['id'] = f'{it["type"]}-{idx}-{it["time"]}'
        return Response(items[:limit])


# ═══════════════════════════════════════════════════════════════════════════
# Tickets
# ═══════════════════════════════════════════════════════════════════════════

class TicketSerializer(serializers.Serializer):
    """Read-only serializer for ticket list responses."""
    id = serializers.SerializerMethodField()
    subject = serializers.CharField()
    status = serializers.CharField()
    priority = serializers.CharField()
    department = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at')
    updatedAt = serializers.DateTimeField(source='updated_at')
    userId = serializers.SerializerMethodField()
    userName = serializers.SerializerMethodField()
    userEmail = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()

    def get_id(self, obj) -> str:
        return f'TKT-{obj.pk:03d}'

    def get_department(self, obj) -> str:
        return DEPARTMENT_LABELS.get(obj.department, obj.department)

    def get_userId(self, obj) -> str:
        return str(obj.user_id)

    def get_userName(self, obj) -> str:
        return obj.user.get_full_name() or obj.user.username

    def get_userEmail(self, obj) -> str:
        return obj.user.email or ''

    def get_messages(self, obj) -> list[dict]:
        msgs = obj.messages.all()
        return [
            {
                'id': str(m.pk),
                'content': m.content,
                'isAdmin': m.is_admin,
                'createdAt': m.created_at.isoformat(),
            }
            for m in msgs
        ]


class TicketListView(APIView):
    """List all tickets (admin) or create a new one."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            Ticket.objects
            .select_related('user')
            .prefetch_related('messages')
            .order_by('-updated_at')
        )
        data = TicketSerializer(qs, many=True).data
        return Response(data)


class TicketDetailView(APIView):
    """Update ticket status/priority."""

    permission_classes = [IsAdminUser]

    def patch(self, request, ticket_pk):
        try:
            ticket = Ticket.objects.get(pk=ticket_pk)
        except Ticket.DoesNotExist:
            return Response({'detail': 'تیکت یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        new_priority = request.data.get('priority')

        if new_status and new_status in dict(Ticket.Status.choices):
            ticket.status = new_status
        if new_priority and new_priority in dict(Ticket.Priority.choices):
            ticket.priority = new_priority

        ticket.save(update_fields=['status', 'priority', 'updated_at'])
        return Response({'success': True})


class TicketReplyView(APIView):
    """Add an admin reply to a ticket."""

    permission_classes = [IsAdminUser]

    def post(self, request, ticket_pk):
        try:
            ticket = Ticket.objects.get(pk=ticket_pk)
        except Ticket.DoesNotExist:
            return Response({'detail': 'تیکت یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        content = (request.data.get('content') or '').strip()
        if not content:
            return Response(
                {'detail': 'محتوای پاسخ نمی‌تواند خالی باشد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        msg = TicketMessage.objects.create(
            ticket=ticket,
            content=content,
            is_admin=True,
            author=request.user,
        )

        # Auto-update ticket status to answered
        ticket.status = Ticket.Status.ANSWERED
        ticket.save(update_fields=['status', 'updated_at'])

        return Response({
            'id': str(msg.pk),
            'content': msg.content,
            'isAdmin': msg.is_admin,
            'createdAt': msg.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class UserTicketCreateView(APIView):
    """Create a new ticket (any authenticated user)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        subject = (request.data.get('subject') or '').strip()
        content = (request.data.get('content') or '').strip()
        department = request.data.get('department', 'other')
        priority = request.data.get('priority', 'medium')

        if not subject:
            return Response({'detail': 'موضوع الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)
        if not content:
            return Response({'detail': 'متن پیام الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        ticket = Ticket.objects.create(
            user=request.user,
            subject=subject,
            department=department,
            priority=priority,
        )
        TicketMessage.objects.create(
            ticket=ticket,
            content=content,
            is_admin=False,
            author=request.user,
        )
        return Response({
            'id': f'TKT-{ticket.pk:03d}',
            'subject': ticket.subject,
            'status': ticket.status,
        }, status=status.HTTP_201_CREATED)


class UserTicketListView(APIView):
    """List tickets for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Ticket.objects
            .filter(user=request.user)
            .prefetch_related('messages')
            .order_by('-updated_at')
        )
        data = TicketSerializer(qs, many=True).data
        return Response(data)


class UserTicketReplyView(APIView):
    """Add a user reply to their own ticket."""

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_pk):
        try:
            ticket = Ticket.objects.get(pk=ticket_pk, user=request.user)
        except Ticket.DoesNotExist:
            return Response({'detail': 'تیکت یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        content = (request.data.get('content') or '').strip()
        if not content:
            return Response(
                {'detail': 'محتوای پاسخ نمی‌تواند خالی باشد.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        msg = TicketMessage.objects.create(
            ticket=ticket,
            content=content,
            is_admin=False,
            author=request.user,
        )

        # Reopen ticket if it was answered/closed
        if ticket.status in (Ticket.Status.ANSWERED, Ticket.Status.CLOSED):
            ticket.status = Ticket.Status.PENDING
            ticket.save(update_fields=['status', 'updated_at'])

        return Response({
            'id': str(msg.pk),
            'content': msg.content,
            'isAdmin': msg.is_admin,
            'createdAt': msg.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════════════════════
# Server Health & Maintenance
# ═══════════════════════════════════════════════════════════════════════════

def _read_proc_value(path: str) -> str | None:
    """Read a file from /proc (Linux only)."""
    try:
        with open(path) as f:
            return f.read()
    except (FileNotFoundError, PermissionError):
        return None


def _get_cpu_percent() -> float:
    """Rough CPU usage from /proc/stat."""
    raw = _read_proc_value('/proc/stat')
    if not raw:
        return 0.0
    parts = raw.splitlines()[0].split()  # cpu user nice system idle ...
    if len(parts) < 5:
        return 0.0
    vals = [int(x) for x in parts[1:]]
    idle = vals[3]
    total = sum(vals)
    if total == 0:
        return 0.0
    return round((1 - idle / total) * 100, 1)


def _get_memory_percent() -> float:
    """Memory usage from /proc/meminfo."""
    raw = _read_proc_value('/proc/meminfo')
    if not raw:
        return 0.0
    info: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            key = parts[0].rstrip(':')
            try:
                info[key] = int(parts[1])
            except ValueError:
                pass
    total = info.get('MemTotal', 0)
    available = info.get('MemAvailable', 0)
    if total == 0:
        return 0.0
    return round((1 - available / total) * 100, 1)


def _format_uptime(seconds: float) -> str:
    """Format seconds into a human-readable Persian string."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    if days > 0:
        return f'{days} روز و {hours} ساعت'
    return f'{hours} ساعت'


class ServerHealthView(APIView):
    """Real server health metrics."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        uptime_seconds = time.time() - _STARTUP_TIME

        # Disk usage
        try:
            usage = shutil.disk_usage('/')
            disk_percent = round(usage.used / usage.total * 100, 1)
        except Exception:
            disk_percent = 0.0

        cpu = _get_cpu_percent()
        memory = _get_memory_percent()

        # Recent pipeline failures as incidents
        from apps.classes.models import ClassCreationSession
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        incidents = ClassCreationSession.objects.filter(
            status='failed',
            updated_at__gte=month_start,
        ).count()

        last_incident_qs = ClassCreationSession.objects.filter(status='failed').order_by('-updated_at').first()
        last_incident = last_incident_qs.updated_at.isoformat() if last_incident_qs else None

        health_status = 'healthy'
        if cpu > 90 or memory > 90 or disk_percent > 90:
            health_status = 'degraded'

        return Response({
            'status': health_status,
            'uptime': _format_uptime(uptime_seconds),
            'cpu': cpu,
            'memory': memory,
            'disk': disk_percent,
            'incidentsThisMonth': incidents,
            'lastIncident': last_incident,
        })


class MaintenanceTasksView(APIView):
    """Recent pipeline failures and system tasks."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.classes.models import ClassCreationSession

        # Show recent failed pipelines as maintenance items
        failed = (
            ClassCreationSession.objects
            .filter(status='failed')
            .select_related('teacher')
            .order_by('-updated_at')[:10]
        )

        tasks = []
        for session in failed:
            tasks.append({
                'id': f'pipeline-{session.pk}',
                'title': f'خطای پایپلاین: {session.title}',
                'window': session.updated_at.isoformat(),
                'owner': session.teacher.get_full_name() or session.teacher.username,
                'status': 'failed',
                'detail': (session.error_detail or '')[:200],
            })

        return Response(tasks)


# ═══════════════════════════════════════════════════════════════════════════
# Backups
# ═══════════════════════════════════════════════════════════════════════════

class BackupsListView(APIView):
    """List DB size and backup info."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.db import connection

        # Get DB size
        db_size = '?'
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_size_pretty(pg_database_size(current_database()));"
                )
                db_size = cursor.fetchone()[0]
        except Exception:
            pass

        # Table count
        table_count = 0
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public';"
                )
                table_count = cursor.fetchone()[0]
        except Exception:
            pass

        return Response({
            'db_size': db_size,
            'table_count': table_count,
            'backups': [],  # Actual backups are managed by infrastructure
            'note': 'بک‌آپ‌ها توسط زیرساخت Hamravesh مدیریت می‌شوند.',
        })


class BackupTriggerView(APIView):
    """Trigger a manual pg_dump (if configured)."""

    permission_classes = [IsAdminUser]

    def post(self, request):
        # In a container environment, actual backups are managed by the platform.
        # This endpoint is a placeholder that returns DB info.
        return Response({
            'success': False,
            'message': 'بک‌آپ‌ها توسط زیرساخت Hamravesh به صورت خودکار انجام می‌شوند.',
        })


# ═══════════════════════════════════════════════════════════════════════════
# Server Settings
# ═══════════════════════════════════════════════════════════════════════════

class ServerSettingsView(APIView):
    """Get/update admin-configurable server settings."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        raw = AdminSetting.get_all()
        return Response({
            'autoBackup': raw.get('auto_backup', 'true').lower() == 'true',
            'backupWindow': raw.get('backup_window', '03:00-04:00'),
            'backupRetentionDays': int(raw.get('backup_retention_days', '14')),
            'maintenanceAutoApprove': raw.get('maintenance_auto_approve', 'false').lower() == 'true',
            'alertEmail': raw.get('alert_email', ''),
        })

    def patch(self, request):
        mapping = {
            'autoBackup': ('auto_backup', lambda v: str(v).lower()),
            'backupWindow': ('backup_window', str),
            'backupRetentionDays': ('backup_retention_days', str),
            'maintenanceAutoApprove': ('maintenance_auto_approve', lambda v: str(v).lower()),
            'alertEmail': ('alert_email', str),
        }
        to_save: dict[str, str] = {}
        for api_key, (db_key, transform) in mapping.items():
            if api_key in request.data:
                to_save[db_key] = transform(request.data[api_key])

        if to_save:
            AdminSetting.set_many(to_save)

        return self.get(request)


# ═══════════════════════════════════════════════════════════════════════════
# Admin Profile Settings
# ═══════════════════════════════════════════════════════════════════════════

class AdminProfileSettingsView(APIView):
    """Get/update the admin's own profile."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        u = request.user
        avatar_url = ''
        if u.avatar:
            try:
                avatar_url = u.avatar.url
            except Exception:
                pass

        return Response({
            'name': u.get_full_name() or u.username,
            'email': u.email or '',
            'phone': u.phone or '',
            'bio': self._get_bio(u),
            'location': self._get_location(u),
            'avatar': avatar_url,
        })

    def patch(self, request):
        u = request.user
        data = request.data

        update_fields: list[str] = []

        if 'name' in data:
            parts = (data['name'] or '').strip().split(' ', 1)
            u.first_name = parts[0]
            u.last_name = parts[1] if len(parts) > 1 else ''
            update_fields += ['first_name', 'last_name']

        if 'email' in data:
            u.email = (data['email'] or '').strip()
            update_fields.append('email')

        if 'phone' in data:
            u.phone = (data['phone'] or '').strip() or None
            update_fields.append('phone')

        if update_fields:
            u.save(update_fields=update_fields)

        # Profile fields
        profile = self._get_profile(u)
        if profile:
            profile_changed = False
            if 'bio' in data:
                profile.bio = (data['bio'] or '').strip() or None
                profile_changed = True
            if 'location' in data:
                profile.location = (data['location'] or '').strip() or None
                profile_changed = True
            if profile_changed:
                profile.save()

        return self.get(request)

    def _get_profile(self, user):
        for attr in ('adminprofile', 'teacherprofile', 'studentprofile'):
            if hasattr(user, attr):
                return getattr(user, attr)
        return None

    def _get_bio(self, user) -> str:
        p = self._get_profile(user)
        return (p.bio or '') if p else ''

    def _get_location(self, user) -> str:
        p = self._get_profile(user)
        return (p.location or '') if p else ''


class AdminSecuritySettingsView(APIView):
    """Read security-related info for current admin."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        u = request.user
        # Django doesn't store last_password_change easily; use last_login as proxy
        last_login = u.last_login.isoformat() if u.last_login else None

        return Response({
            'twoFactorEnabled': False,
            'lastPasswordChange': last_login,
            'lastLogin': last_login,
        })


class AdminNotificationSettingsView(APIView):
    """Get/update admin notification preferences (stored in AdminSetting)."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        prefix = f'notif_pref_{request.user.pk}_'
        return Response({
            'emailNotifications': AdminSetting.get(f'{prefix}email') != 'false',
            'browserNotifications': AdminSetting.get(f'{prefix}browser') != 'false',
            'smsNotifications': AdminSetting.get(f'{prefix}sms') == 'true',
            'marketingEmails': AdminSetting.get(f'{prefix}marketing') == 'true',
        })

    def patch(self, request):
        prefix = f'notif_pref_{request.user.pk}_'
        mapping = {
            'emailNotifications': f'{prefix}email',
            'browserNotifications': f'{prefix}browser',
            'smsNotifications': f'{prefix}sms',
            'marketingEmails': f'{prefix}marketing',
        }
        to_save: dict[str, str] = {}
        for api_key, db_key in mapping.items():
            if api_key in request.data:
                to_save[db_key] = str(request.data[api_key]).lower()

        if to_save:
            AdminSetting.set_many(to_save)

        return self.get(request)


# ═══════════════════════════════════════════════════════════════════════════
# Platform Admin — User Management
# ═══════════════════════════════════════════════════════════════════════════

class UserListSerializer(serializers.ModelSerializer):
    """Read-only serializer for user list (camelCase output)."""

    fullName = serializers.SerializerMethodField()
    dateJoined = serializers.DateTimeField(source='date_joined', read_only=True)
    lastLogin = serializers.DateTimeField(source='last_login', read_only=True)
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    isStaff = serializers.BooleanField(source='is_staff', read_only=True)
    isSuperuser = serializers.BooleanField(source='is_superuser', read_only=True)
    isFreelancer = serializers.BooleanField(source='is_freelancer', read_only=True)
    managedOrganizations = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'fullName', 'role', 'phone', 'isActive', 'isStaff',
            'isSuperuser', 'isFreelancer', 'dateJoined', 'lastLogin', 'avatar',
            'managedOrganizations',
        ]

    @staticmethod
    def get_fullName(obj) -> str:  # noqa: N802
        return obj.get_full_name() or obj.username

    @staticmethod
    def get_managedOrganizations(obj):  # noqa: N802
        """Orgs this user MANAGES (org_role=admin membership) → org-manager status.

        Reads the ``_admin_memberships`` prefetch (list view) to avoid an N+1;
        falls back to a single query for the detail view.
        """
        memberships = getattr(obj, '_admin_memberships', None)
        if memberships is None:
            from apps.organizations.models import OrganizationMembership
            memberships = list(
                OrganizationMembership.objects
                .filter(
                    user=obj,
                    org_role=OrganizationMembership.OrgRole.ADMIN,
                    status=OrganizationMembership.MemberStatus.ACTIVE,
                )
                .select_related('organization')
            )
        return [
            {'id': m.organization_id, 'name': m.organization.name}
            for m in memberships
        ]


class UserUpdateSerializer(serializers.Serializer):
    """Input serializer for updating a user."""

    role = serializers.ChoiceField(
        choices=User.Role.choices, required=False,
    )
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    # TEACHER only: whether the user may use a personal (freelancer) workspace.
    is_freelancer = serializers.BooleanField(required=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)


class AdminUserListView(APIView):
    """GET: list all users with search, role and active filters."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.organizations.models import OrganizationMembership

        # Prefetch each user's org-admin memberships (→ org-manager status) once,
        # so UserListSerializer.get_managedOrganizations reads from cache instead
        # of issuing one query per row (N+1) across the whole user table.
        admin_memberships = (
            OrganizationMembership.objects
            .filter(
                org_role=OrganizationMembership.OrgRole.ADMIN,
                status=OrganizationMembership.MemberStatus.ACTIVE,
            )
            .select_related('organization')
        )
        qs = (
            User.objects.all()
            .prefetch_related(
                Prefetch('org_memberships', queryset=admin_memberships, to_attr='_admin_memberships')
            )
            .order_by('-date_joined')
        )

        # Search
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )

        # Filter by role
        role = request.query_params.get('role', '').strip().upper()
        if role:
            qs = qs.filter(role=role)

        # Filter by active status
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ('true', '1'))

        data = UserListSerializer(qs, many=True).data
        return Response(data)


class AdminUserStatsView(APIView):
    """Platform admin: aggregate user counts by role + active status (one query)."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        agg = User.objects.aggregate(
            total=Count('id'),
            admins=Count('id', filter=Q(role=User.Role.ADMIN)),
            managers=Count('id', filter=Q(role=User.Role.MANAGER)),
            teachers=Count('id', filter=Q(role=User.Role.TEACHER)),
            students=Count('id', filter=Q(role=User.Role.STUDENT)),
            active=Count('id', filter=Q(is_active=True)),
            inactive=Count('id', filter=Q(is_active=False)),
        )
        return Response(agg)


class AdminUserDetailView(APIView):
    """GET / PATCH / DELETE a single user (platform admin)."""

    permission_classes = [IsAdminUser]

    def get(self, request, user_pk):
        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return Response(
                {'detail': 'کاربر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return Response(UserListSerializer(user).data)

    def patch(self, request, user_pk):
        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return Response(
                {'detail': 'کاربر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )

        # Prevent admin from demoting themselves
        if user.pk == request.user.pk:
            if 'role' in request.data and request.data['role'] != user.role:
                return Response(
                    {'detail': 'نمی‌توانید نقش خودتان را تغییر دهید.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if 'is_active' in request.data and not request.data['is_active']:
                return Response(
                    {'detail': 'نمی‌توانید حساب خودتان را غیرفعال کنید.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        ser = UserUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        for field, value in ser.validated_data.items():
            setattr(user, field, value)
        user.save()

        return Response(UserListSerializer(user).data)

    def delete(self, request, user_pk):
        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return Response(
                {'detail': 'کاربر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND,
            )

        # Prevent self-deletion
        if user.pk == request.user.pk:
            return Response(
                {'detail': 'نمی‌توانید حساب خودتان را حذف کنید.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminUserOrgManagerView(APIView):
    """Platform admin: designate / revoke a user as an ORGANIZATION MANAGER.

    An org manager is the distinct platform role MANAGER (NOT a teacher, NOT a
    platform admin) plus an ``org_role=admin`` membership in a specific
    organization — the same identity the SMS onboarding / invite-code flow
    produces. This lets an admin grant that status to an EXISTING user straight
    from the user panel, instead of only via the org-create + invite-code path.

    POST   /api/admin/users/<id>/org-manager/        {organization_id}  → assign
    DELETE /api/admin/users/<id>/org-manager/<org>/                     → revoke
    """

    permission_classes = [IsAdminUser]

    def post(self, request, user_pk):
        from apps.organizations.models import Organization, OrganizationMembership

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return Response({'detail': 'کاربر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        org_id = request.data.get('organization_id')
        try:
            org = Organization.objects.get(pk=int(org_id))
        except (Organization.DoesNotExist, TypeError, ValueError):
            return Response({'detail': 'سازمان آموزشی یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            # An org manager IS the MANAGER role. Promote a student/teacher to
            # MANAGER; never DEMOTE a platform ADMIN (they already outrank this).
            if user.role != User.Role.ADMIN and user.role != User.Role.MANAGER:
                user.role = User.Role.MANAGER
                user.save(update_fields=['role'])

            OrganizationMembership.objects.update_or_create(
                user=user,
                organization=org,
                defaults={
                    'org_role': OrganizationMembership.OrgRole.ADMIN,
                    'status': OrganizationMembership.MemberStatus.ACTIVE,
                },
            )

            # Adopt as owner only if the org has none yet (don't override).
            if org.owner_id is None:
                org.owner = user
                org.save(update_fields=['owner'])

        return Response(UserListSerializer(user).data)

    def delete(self, request, user_pk, org_pk):
        from apps.organizations.models import Organization, OrganizationMembership

        try:
            user = User.objects.get(pk=user_pk)
        except User.DoesNotExist:
            return Response({'detail': 'کاربر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        OrganizationMembership.objects.filter(
            user=user,
            organization_id=org_pk,
            org_role=OrganizationMembership.OrgRole.ADMIN,
        ).delete()
        # If this user was the org's owner, clear it — they no longer manage it.
        Organization.objects.filter(pk=org_pk, owner=user).update(owner=None)

        # If they no longer manage ANY org and are still a MANAGER, drop them back
        # to STUDENT (a manager with no org is a dangling role).
        still_manages = OrganizationMembership.objects.filter(
            user=user,
            org_role__in=[OrganizationMembership.OrgRole.ADMIN, OrganizationMembership.OrgRole.DEPUTY],
            status=OrganizationMembership.MemberStatus.ACTIVE,
        ).exists()
        if not still_manages and user.role == User.Role.MANAGER:
            user.role = User.Role.STUDENT
            user.save(update_fields=['role'])

        return Response(UserListSerializer(user).data)
