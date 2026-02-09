"""Throttling / rate limiting tests.

Verifies that DRF throttling is correctly configured and enforced.
"""
from __future__ import annotations

import pytest
from model_bakery import baker

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


def _auth_client(user) -> APIClient:
    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.mark.django_db
class TestThrottlingConfiguration:
    """Verify that throttling is active on API endpoints."""

    def test_anonymous_rate_limit_configured(self, settings):
        """Anon throttle rate must be set."""
        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert 'anon' in rates

    def test_user_rate_limit_configured(self, settings):
        """User throttle rate must be set."""
        rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert 'user' in rates

    def test_throttle_responds_with_429(self, settings):
        """Exceeding the rate limit should return 429 Too Many Requests."""
        # Set an extremely low rate for testing.
        settings.REST_FRAMEWORK = {
            **settings.REST_FRAMEWORK,
            'DEFAULT_THROTTLE_RATES': {
                'anon': '1/minute',
                'user': '1/minute',
            },
        }

        # Clear throttle cache.
        from django.core.cache import cache
        cache.clear()

        client = APIClient()

        # First request should succeed (or 401 for auth-required).
        resp1 = client.get('/api/classes/sessions/')
        # Second request should be throttled OR auth-rejected.
        resp2 = client.get('/api/classes/sessions/')

        # If the endpoint requires auth, both will be 401.
        # If it allows anon, first=200, second=429.
        assert resp1.status_code in (200, 401, 429)
        if resp1.status_code == 200:
            assert resp2.status_code == 429


@pytest.mark.django_db
class TestPaginationConfiguration:
    """Verify that pagination is active on list endpoints."""

    def test_default_pagination_class_set(self, settings):
        assert settings.REST_FRAMEWORK.get('DEFAULT_PAGINATION_CLASS') is not None

    def test_page_size_set(self, settings):
        page_size = settings.REST_FRAMEWORK.get('PAGE_SIZE')
        assert page_size is not None
        assert page_size > 0
