"""Throttling / rate limiting tests.

Verifies that DRF throttling is correctly configured and enforced.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User


def _auth_client(user) -> APIClient:
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.mark.django_db
class TestThrottlingConfiguration:
    """Verify that throttling is active on API endpoints."""

    def test_anonymous_rate_limit_configured(self):
        """Anon throttle rate must be set in the *real* (non-test) settings."""
        from django.conf import settings as real_settings
        # Read from the original module, not the overridden test settings.
        import core.settings as mod
        rf = getattr(mod, 'REST_FRAMEWORK', {})
        rates = rf.get('DEFAULT_THROTTLE_RATES', {})
        assert 'anon' in rates

    def test_user_rate_limit_configured(self):
        """User throttle rate must be set in the *real* settings module."""
        import core.settings as mod
        rf = getattr(mod, 'REST_FRAMEWORK', {})
        rates = rf.get('DEFAULT_THROTTLE_RATES', {})
        assert 'user' in rates

    def test_throttle_responds_with_429(self, settings):
        """Exceeding the rate limit should return 429 Too Many Requests."""
        from rest_framework.throttling import UserRateThrottle
        from apps.classes.views import ClassCreationSessionListView
        from django.core.cache import cache

        cache.clear()

        # DRF resolves throttle_classes and THROTTLE_RATES at class-definition
        # time.  Override directly so the test isn't affected by import ordering.
        original_throttle = ClassCreationSessionListView.throttle_classes
        original_rates = UserRateThrottle.THROTTLE_RATES
        ClassCreationSessionListView.throttle_classes = [UserRateThrottle]
        UserRateThrottle.THROTTLE_RATES = {'user': '1/minute'}

        try:
            teacher = baker.make(User, role=User.Role.TEACHER)
            client = _auth_client(teacher)

            resp1 = client.get('/api/classes/creation-sessions/')
            assert resp1.status_code == 200

            resp2 = client.get('/api/classes/creation-sessions/')
            assert resp2.status_code == 429
        finally:
            ClassCreationSessionListView.throttle_classes = original_throttle
            UserRateThrottle.THROTTLE_RATES = original_rates


@pytest.mark.django_db
class TestPaginationConfiguration:
    """Verify that pagination is active on list endpoints."""

    def test_default_pagination_class_set(self):
        import core.settings as mod
        rf = getattr(mod, 'REST_FRAMEWORK', {})
        assert rf.get('DEFAULT_PAGINATION_CLASS') is not None

    def test_page_size_set(self):
        import core.settings as mod
        rf = getattr(mod, 'REST_FRAMEWORK', {})
        page_size = rf.get('PAGE_SIZE')
        assert page_size is not None
        assert page_size > 0
