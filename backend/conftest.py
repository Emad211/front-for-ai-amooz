"""Root conftest for backend test suite.

Automatically disables DRF throttling so tests do not receive spurious
429 responses.  Individual tests that *need* throttling can re-enable it
by overriding ``settings.REST_FRAMEWORK`` in the test body.
"""
import pytest


@pytest.fixture(autouse=True)
def _disable_throttling(settings):
    """Disable DRF throttling for every test."""
    rf = {**settings.REST_FRAMEWORK}
    rf["DEFAULT_THROTTLE_CLASSES"] = []
    rf["DEFAULT_THROTTLE_RATES"] = {}
    settings.REST_FRAMEWORK = rf

    # Clear throttle cache to prevent stale rate-limit data.
    try:
        from django.core.cache import cache
        cache.clear()
    except Exception:
        pass
