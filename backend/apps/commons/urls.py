"""URL patterns for commons app (admin dashboard)."""

from django.urls import path

from .views import (
    # LLM usage
    LLMUsageSummaryView,
    LLMUsageByFeatureView,
    LLMUsageByUserView,
    LLMUsageByProviderView,
    LLMUsageDailyView,
    LLMUsageRecentLogsView,
    # Exchange rate
    ExchangeRateView,
    # Analytics
    AnalyticsStatsView,
    AnalyticsChartView,
    AnalyticsDistributionView,
    AnalyticsRecentActivityView,
    # Tickets (admin)
    TicketListView,
    TicketDetailView,
    TicketReplyView,
    # Tickets (user)
    UserTicketCreateView,
    UserTicketListView,
    UserTicketReplyView,
    # Server health & maintenance
    ServerHealthView,
    MaintenanceTasksView,
    # Backups
    BackupsListView,
    BackupTriggerView,
    # Server settings
    ServerSettingsView,
    # Admin profile / security / notification settings
    AdminProfileSettingsView,
    AdminSecuritySettingsView,
    AdminNotificationSettingsView,
    # User management
    AdminUserListView,
    AdminUserDetailView,
)

urlpatterns = [
    # --- LLM usage ---
    path('llm-usage/summary/', LLMUsageSummaryView.as_view(), name='llm-usage-summary'),
    path('llm-usage/by-feature/', LLMUsageByFeatureView.as_view(), name='llm-usage-by-feature'),
    path('llm-usage/by-user/', LLMUsageByUserView.as_view(), name='llm-usage-by-user'),
    path('llm-usage/by-provider/', LLMUsageByProviderView.as_view(), name='llm-usage-by-provider'),
    path('llm-usage/daily/', LLMUsageDailyView.as_view(), name='llm-usage-daily'),
    path('llm-usage/recent/', LLMUsageRecentLogsView.as_view(), name='llm-usage-recent'),
    path('exchange-rate/', ExchangeRateView.as_view(), name='exchange-rate'),

    # --- Analytics ---
    path('analytics/stats/', AnalyticsStatsView.as_view(), name='analytics-stats'),
    path('analytics/chart/', AnalyticsChartView.as_view(), name='analytics-chart'),
    path('analytics/distribution/', AnalyticsDistributionView.as_view(), name='analytics-distribution'),
    path('analytics/recent-activity/', AnalyticsRecentActivityView.as_view(), name='analytics-recent-activity'),

    # --- Tickets (admin) ---
    path('tickets/', TicketListView.as_view(), name='ticket-list'),
    path('tickets/<int:ticket_pk>/', TicketDetailView.as_view(), name='ticket-detail'),
    path('tickets/<int:ticket_pk>/reply/', TicketReplyView.as_view(), name='ticket-reply'),

    # --- Tickets (user-facing) ---
    path('my-tickets/', UserTicketListView.as_view(), name='user-ticket-list'),
    path('my-tickets/create/', UserTicketCreateView.as_view(), name='user-ticket-create'),
    path('my-tickets/<int:ticket_pk>/reply/', UserTicketReplyView.as_view(), name='user-ticket-reply'),

    # --- Server health & maintenance ---
    path('server/health/', ServerHealthView.as_view(), name='server-health'),
    path('maintenance/tasks/', MaintenanceTasksView.as_view(), name='maintenance-tasks'),

    # --- Backups ---
    path('backups/', BackupsListView.as_view(), name='backups-list'),
    path('backups/trigger/', BackupTriggerView.as_view(), name='backup-trigger'),

    # --- Server settings ---
    path('server/settings/', ServerSettingsView.as_view(), name='server-settings'),

    # --- Admin profile / security / notification settings ---
    path('settings/profile/', AdminProfileSettingsView.as_view(), name='admin-profile-settings'),
    path('settings/security/', AdminSecuritySettingsView.as_view(), name='admin-security-settings'),
    path('settings/notifications/', AdminNotificationSettingsView.as_view(), name='admin-notification-settings'),

    # --- User management ---
    path('users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('users/<int:user_pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
]
