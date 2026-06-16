"""Shared throttling helpers."""

from __future__ import annotations

from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle


class SafeScopedRateThrottle(ScopedRateThrottle):
    """A ScopedRateThrottle that no-ops when its scope has no configured rate.

    The test suite disables throttling by clearing ``DEFAULT_THROTTLE_RATES``
    (see ``backend/conftest.py``). A view that hardcodes ``throttle_classes``
    bypasses that, and a bare ``ScopedRateThrottle`` then raises
    ``ImproperlyConfigured`` when its scope rate is missing. This subclass stays
    inert when no rate is configured, so it throttles in production but never
    breaks tests — and it's safe to attach to any view via ``throttle_scope``.
    """

    def allow_request(self, request, view):
        scope = getattr(view, self.scope_attr, None)
        rates = api_settings.DEFAULT_THROTTLE_RATES or {}
        if not scope or not rates.get(scope):
            return True
        return super().allow_request(request, view)
