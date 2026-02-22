"""REST API endpoints for admin dashboard (admin-only)."""

from __future__ import annotations

import os
import shutil
import time
from datetime import timedelta

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin as IsAdminUser

from apps.commons.models import (
    AdminSetting,
    DEPARTMENT_LABELS,
    LLMUsageLog,
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
            avg_duration_ms=Avg('duration_ms'),
            total_audio_input_tokens=Sum('audio_input_tokens'),
            total_cached_input_tokens=Sum('cached_input_tokens'),
            total_thinking_tokens=Sum('thinking_tokens'),
        )
        # Replace None with 0
        for key in agg:
            if agg[key] is None:
                agg[key] = 0

        # USD → Toman conversion
        cost_usd = float(agg['total_cost_usd'])
        toman_amount, rate_err = usd_to_toman(cost_usd)
        usdt_rate, _ = get_usdt_toman_rate()
        agg['total_cost_toman'] = toman_amount
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
            )
            .order_by('-total_cost_usd')
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
            result.append({
                'date': row['date'].isoformat() if row['date'] else None,
                'count': row['count'],
                'total_tokens': row['total_tokens'],
                'total_cost_usd': float(row['total_cost_usd']),
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
                'duration_ms': log.duration_ms,
                'success': log.success,
                'created_at': log.created_at.isoformat(),
            })
        return Response(result)


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
# Analytics
# ═══════════════════════════════════════════════════════════════════════════

class AnalyticsStatsView(APIView):
    """Overview stats cards for the admin analytics page."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        total_students = User.objects.filter(role='STUDENT').count()
        total_teachers = User.objects.filter(role='TEACHER').count()

        from apps.classes.models import (
            ClassCreationSession,
            ClassSectionQuizAttempt,
            StudentCourseChatMessage,
        )

        active_classes = ClassCreationSession.objects.filter(
            is_published=True,
        ).count()

        total_classes = ClassCreationSession.objects.count()

        # Chat engagement (messages in last 30 days)
        recent_messages = StudentCourseChatMessage.objects.filter(
            created_at__gte=thirty_days_ago,
        ).count()

        # Quiz attempts in last 30 days
        recent_quiz_attempts = ClassSectionQuizAttempt.objects.filter(
            created_at__gte=thirty_days_ago,
        ).count()

        # Students who registered in the last 30 days
        new_students_30d = User.objects.filter(
            role='STUDENT',
            date_joined__gte=thirty_days_ago,
        ).count()

        # Previous 30 days for trend
        sixty_days_ago = now - timedelta(days=60)
        prev_students = User.objects.filter(
            role='STUDENT',
            date_joined__gte=sixty_days_ago,
            date_joined__lt=thirty_days_ago,
        ).count()

        student_change = new_students_30d - prev_students

        # LLM cost this month
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        llm_cost = LLMUsageLog.objects.filter(
            created_at__gte=month_start,
        ).aggregate(cost=Sum('estimated_cost_usd'))['cost'] or 0

        return Response({
            'total_students': total_students,
            'total_teachers': total_teachers,
            'active_classes': active_classes,
            'total_classes': total_classes,
            'recent_messages': recent_messages,
            'recent_quiz_attempts': recent_quiz_attempts,
            'new_students_30d': new_students_30d,
            'student_change': student_change,
            'llm_cost_this_month': round(float(llm_cost), 4),
        })


class AnalyticsChartView(APIView):
    """Daily user registration time-series (last N days)."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            days = int(request.query_params.get('days', 14))
        except (TypeError, ValueError):
            days = 14
        days = max(1, min(days, 90))
        since = timezone.now() - timedelta(days=days)

        qs = (
            User.objects
            .filter(date_joined__gte=since)
            .annotate(date=TruncDate('date_joined'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        return Response(list(qs))


class AnalyticsDistributionView(APIView):
    """Class distribution by pipeline type and level."""

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

        return Response({
            'by_pipeline_type': by_type,
            'by_level': by_level,
        })


class AnalyticsRecentActivityView(APIView):
    """Recent platform activities."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.classes.models import ClassCreationSession

        result: list[dict] = []

        # Recent user registrations
        recent_users = User.objects.order_by('-date_joined')[:5]
        for u in recent_users:
            role_fa = {'STUDENT': 'دانش‌آموز', 'TEACHER': 'معلم', 'ADMIN': 'مدیر'}.get(u.role, u.role)
            result.append({
                'id': f'user-{u.pk}',
                'type': 'registration',
                'user': u.get_full_name() or u.username,
                'action': f'به عنوان {role_fa} ثبت‌نام کرد',
                'time': u.date_joined.isoformat(),
            })

        # Recent class creations
        recent_classes = ClassCreationSession.objects.select_related('teacher').order_by('-created_at')[:5]
        for c in recent_classes:
            result.append({
                'id': f'class-{c.pk}',
                'type': 'class',
                'user': c.teacher.get_full_name() or c.teacher.username,
                'action': f'کلاس «{c.title}» را ایجاد کرد',
                'time': c.created_at.isoformat(),
            })

        # Recent notifications
        from apps.notification.models import AdminNotification
        recent_notifs = AdminNotification.objects.order_by('-created_at')[:3]
        for n in recent_notifs:
            result.append({
                'id': f'notif-{n.pk}',
                'type': 'broadcast',
                'user': 'مدیر',
                'action': f'پیام «{n.title}» ارسال شد',
                'time': n.created_at.isoformat(),
            })

        # Sort by time descending
        result.sort(key=lambda x: x['time'], reverse=True)
        return Response(result[:15])


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

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'fullName', 'role', 'phone', 'isActive', 'isStaff',
            'isSuperuser', 'dateJoined', 'lastLogin', 'avatar',
        ]

    @staticmethod
    def get_fullName(obj) -> str:  # noqa: N802
        return obj.get_full_name() or obj.username


class UserUpdateSerializer(serializers.Serializer):
    """Input serializer for updating a user."""

    role = serializers.ChoiceField(
        choices=User.Role.choices, required=False,
    )
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)


class AdminUserListView(APIView):
    """GET: list all users with search, role and active filters."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = User.objects.all().order_by('-date_joined')

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
