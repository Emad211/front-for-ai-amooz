"""REST API endpoints for LLM usage analytics (admin-only)."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.commons.models import LLMUsageLog


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
    avg_duration_ms = serializers.FloatField()


class LLMUsageByUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(allow_null=True)
    username = serializers.CharField()
    full_name = serializers.CharField()
    role = serializers.CharField()
    count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost_usd = serializers.FloatField()


class LLMUsageByProviderSerializer(serializers.Serializer):
    provider = serializers.CharField()
    count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost_usd = serializers.FloatField()


class LLMUsageDailySerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()
    total_tokens = serializers.IntegerField()
    total_cost_usd = serializers.FloatField()


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

def _get_date_filter(request) -> dict:
    """Parse optional ``days`` query param (default 30)."""
    try:
        days = int(request.query_params.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))
    since = timezone.now() - timedelta(days=days)
    return {'created_at__gte': since}


class LLMUsageSummaryView(APIView):
    """Overall usage summary."""
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
            avg_duration_ms=Avg('duration_ms'),
        )
        # Replace None with 0
        for key in agg:
            if agg[key] is None:
                agg[key] = 0
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
                avg_duration_ms=Avg('duration_ms'),
            )
            .order_by('-total_cost_usd')
        )
        feature_labels = dict(LLMUsageLog.Feature.choices)
        result = []
        for row in qs:
            row['feature_label'] = feature_labels.get(row['feature'], row['feature'])
            for k in ('total_tokens', 'total_cost_usd', 'avg_duration_ms'):
                if row[k] is None:
                    row[k] = 0
            result.append(row)
        return Response(result)


class LLMUsageByUserView(APIView):
    """Usage breakdown by user (top consumers)."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        filters = _get_date_filter(request)
        qs = (
            LLMUsageLog.objects
            .filter(**filters)
            .values('user', 'user__username', 'user__first_name', 'user__last_name', 'user__role')
            .annotate(
                count=Count('id'),
                total_tokens=Sum('total_tokens'),
                total_cost_usd=Sum('estimated_cost_usd'),
            )
            .order_by('-total_cost_usd')[:50]
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
            )
            .order_by('-total_cost_usd')
        )
        result = []
        for row in qs:
            for k in ('total_tokens', 'total_cost_usd'):
                if row[k] is None:
                    row[k] = 0
            result.append(row)
        return Response(result)


class LLMUsageDailyView(APIView):
    """Daily usage time-series."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from django.db.models.functions import TruncDate
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
            )
            .order_by('date')
        )
        result = []
        for row in qs:
            for k in ('total_tokens', 'total_cost_usd'):
                if row[k] is None:
                    row[k] = 0
            result.append(row)
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
                'estimated_cost_usd': float(log.estimated_cost_usd),
                'duration_ms': log.duration_ms,
                'success': log.success,
                'created_at': log.created_at.isoformat(),
            })
        return Response(result)
