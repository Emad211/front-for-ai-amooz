"""Root conftest for backend test suite.

Automatically disables DRF throttling so tests do not receive spurious
429 responses.  Individual tests that *need* throttling can re-enable it
by overriding ``settings.REST_FRAMEWORK`` in the test body.
"""
import pytest


@pytest.fixture(autouse=True)
def _disable_throttling(settings):
    """Disable DRF throttling for every test.

    Global throttle classes are removed, but views that pin their own
    ``throttle_classes`` (e.g. ScopedRateThrottle on auth endpoints) still run —
    so we keep every scope defined with an effectively-infinite rate. Leaving a
    scope undefined would make ScopedRateThrottle.get_rate() raise
    ImproperlyConfigured instead of simply not throttling.
    """
    rf = {**settings.REST_FRAMEWORK}
    rf["DEFAULT_THROTTLE_CLASSES"] = []
    rf["DEFAULT_THROTTLE_RATES"] = {
        "anon": "1000000/minute",
        "user": "1000000/minute",
        "auth": "1000000/minute",
    }
    settings.REST_FRAMEWORK = rf

    # Clear throttle cache to prevent stale rate-limit data.
    try:
        from django.core.cache import cache
        cache.clear()
    except Exception:
        pass
