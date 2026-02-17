"""URL patterns for commons app (admin LLM usage analytics)."""

from django.urls import path

from .views import (
    LLMUsageSummaryView,
    LLMUsageByFeatureView,
    LLMUsageByUserView,
    LLMUsageByProviderView,
    LLMUsageDailyView,
    LLMUsageRecentLogsView,
)

urlpatterns = [
    path('llm-usage/summary/', LLMUsageSummaryView.as_view(), name='llm-usage-summary'),
    path('llm-usage/by-feature/', LLMUsageByFeatureView.as_view(), name='llm-usage-by-feature'),
    path('llm-usage/by-user/', LLMUsageByUserView.as_view(), name='llm-usage-by-user'),
    path('llm-usage/by-provider/', LLMUsageByProviderView.as_view(), name='llm-usage-by-provider'),
    path('llm-usage/daily/', LLMUsageDailyView.as_view(), name='llm-usage-daily'),
    path('llm-usage/recent/', LLMUsageRecentLogsView.as_view(), name='llm-usage-recent'),
]
