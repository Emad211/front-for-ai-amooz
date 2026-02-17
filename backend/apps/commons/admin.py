from django.contrib import admin
from django.db.models import Sum, Count, Avg
from django.utils.html import format_html

from .models import LLMUsageLog


@admin.register(LLMUsageLog)
class LLMUsageLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at',
        'user_display',
        'feature',
        'provider',
        'model_name',
        'input_tokens',
        'output_tokens',
        'total_tokens',
        'cost_display',
        'duration_display',
        'success',
    ]
    list_filter = [
        'feature',
        'provider',
        'model_name',
        'success',
        'created_at',
    ]
    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'detail',
    ]
    readonly_fields = [
        'user',
        'feature',
        'provider',
        'model_name',
        'input_tokens',
        'output_tokens',
        'total_tokens',
        'estimated_cost_usd',
        'session_id',
        'detail',
        'duration_ms',
        'success',
        'error_message',
        'created_at',
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    list_per_page = 50

    def user_display(self, obj):
        if obj.user:
            return f'{obj.user.username} ({obj.user.role})'
        return 'system'
    user_display.short_description = 'User'

    def cost_display(self, obj):
        cost = float(obj.estimated_cost_usd or 0)
        if cost >= 0.01:
            return format_html('<span style="color: #e74c3c; font-weight: bold;">${:.4f}</span>', cost)
        return f'${cost:.6f}'
    cost_display.short_description = 'Cost (USD)'

    def duration_display(self, obj):
        ms = obj.duration_ms or 0
        if ms >= 1000:
            return f'{ms / 1000:.1f}s'
        return f'{ms}ms'
    duration_display.short_description = 'Duration'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def changelist_view(self, request, extra_context=None):
        """Add summary statistics to the changelist page."""
        extra_context = extra_context or {}

        qs = self.get_queryset(request)
        # Apply any current filters
        cl = self.get_changelist_instance(request)
        qs = cl.get_queryset(request)

        aggregates = qs.aggregate(
            total_requests=Count('id'),
            total_input_tokens=Sum('input_tokens'),
            total_output_tokens=Sum('output_tokens'),
            total_tokens_all=Sum('total_tokens'),
            total_cost=Sum('estimated_cost_usd'),
            avg_duration=Avg('duration_ms'),
        )
        extra_context['usage_summary'] = {
            'total_requests': aggregates['total_requests'] or 0,
            'total_input_tokens': aggregates['total_input_tokens'] or 0,
            'total_output_tokens': aggregates['total_output_tokens'] or 0,
            'total_tokens': aggregates['total_tokens_all'] or 0,
            'total_cost_usd': float(aggregates['total_cost'] or 0),
            'avg_duration_ms': int(aggregates['avg_duration'] or 0),
        }

        return super().changelist_view(request, extra_context=extra_context)
