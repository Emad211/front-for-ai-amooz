"""Django settings and configuration tests.

Verifies that production-critical settings are correctly configured for
100 concurrent users: CONN_MAX_AGE, throttling, caching, pagination.
"""
from __future__ import annotations

import pytest
from django.conf import settings


class TestDatabaseSettings:
    """Verify database connection settings for concurrency."""

    def test_conn_max_age_nonzero(self):
        """CONN_MAX_AGE must be > 0 to avoid reconnection per request."""
        conn_max_age = settings.DATABASES['default'].get('CONN_MAX_AGE', 0)
        assert conn_max_age > 0, (
            f'CONN_MAX_AGE={conn_max_age}; should be > 0 to avoid '
            'creating a new DB connection per request under load'
        )


class TestRestFrameworkSettings:
    """Verify DRF settings for production safety."""

    def test_throttle_classes_configured(self):
        """Throttle classes must be set to prevent API abuse."""
        import core.settings as mod
        throttle_classes = mod.REST_FRAMEWORK.get('DEFAULT_THROTTLE_CLASSES', [])
        assert len(throttle_classes) >= 2, (
            f'Expected at least 2 throttle classes, got {throttle_classes}'
        )
        class_names = [c.rsplit('.', 1)[-1] for c in throttle_classes]
        assert 'AnonRateThrottle' in class_names
        assert 'UserRateThrottle' in class_names

    def test_throttle_rates_configured(self):
        """Throttle rates must be set for both anon and user."""
        import core.settings as mod
        rates = mod.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        assert 'anon' in rates, 'Missing anon throttle rate'
        assert 'user' in rates, 'Missing user throttle rate'

    def test_pagination_class_configured(self):
        """Default pagination must be set to prevent unbounded responses."""
        pagination = settings.REST_FRAMEWORK.get('DEFAULT_PAGINATION_CLASS')
        assert pagination is not None, 'DEFAULT_PAGINATION_CLASS not set'

    def test_page_size_reasonable(self):
        """PAGE_SIZE should be set to a reasonable value."""
        page_size = settings.REST_FRAMEWORK.get('PAGE_SIZE')
        assert page_size is not None
        assert 10 <= page_size <= 100, f'PAGE_SIZE={page_size}; should be 10-100'


class TestCacheSettings:
    """Verify that a shared cache backend is configured."""

    def test_cache_backend_is_redis(self):
        """Cache must use Redis (not LocMemCache) for shared throttle counters."""
        cache = settings.CACHES.get('default', {})
        backend = cache.get('BACKEND', '')
        assert 'redis' in backend.lower() or 'Redis' in backend, (
            f'Cache backend is {backend}; should be Redis for shared '
            'throttle counters across multiple workers'
        )


class TestSessionSettings:
    """Verify session configuration."""

    def test_session_engine_is_cache(self):
        """Session engine should use cache backend to avoid DB round-trips."""
        engine = getattr(settings, 'SESSION_ENGINE', '')
        assert 'cache' in engine, (
            f'SESSION_ENGINE={engine}; should use cache-backed sessions '
            'to avoid a DB read/write per request'
        )


class TestSecuritySettings:
    """Basic security settings checks."""

    def test_secret_key_not_default(self):
        """SECRET_KEY must not be the default insecure value."""
        assert settings.SECRET_KEY != 'django-insecure-change-me-in-production'

    def test_password_validators_configured(self):
        """Password validators must be set."""
        assert len(settings.AUTH_PASSWORD_VALIDATORS) >= 4

    def test_secure_proxy_ssl_header(self):
        """SECURE_PROXY_SSL_HEADER must be set for reverse proxy."""
        assert settings.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')


class TestCelerySettings:
    """Verify Celery configuration for background tasks."""

    def test_celery_broker_url_set(self):
        assert settings.CELERY_BROKER_URL is not None
        assert len(settings.CELERY_BROKER_URL) > 0

    def test_celery_time_limits(self):
        """Task time limits must be set to prevent runaway tasks."""
        assert settings.CELERY_TASK_TIME_LIMIT > 0
        assert settings.CELERY_TASK_SOFT_TIME_LIMIT > 0
        assert settings.CELERY_TASK_SOFT_TIME_LIMIT < settings.CELERY_TASK_TIME_LIMIT

    def test_prefetch_multiplier_is_one(self):
        """Prefetch multiplier should be 1 for long-running tasks."""
        assert settings.CELERY_WORKER_PREFETCH_MULTIPLIER == 1


class TestFileUploadSettings:
    """Verify file upload configuration."""

    def test_upload_handler_is_temporary(self):
        """Large files should stream to disk, not stay in memory."""
        handlers = settings.FILE_UPLOAD_HANDLERS
        assert any('TemporaryFileUploadHandler' in h for h in handlers)

    def test_max_upload_size_reasonable(self):
        """Upload size limit should be set."""
        assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE > 0
        assert settings.FILE_UPLOAD_MAX_MEMORY_SIZE > 0
