"""Throttling for the public waitlist intake.

The project disables throttling in tests by clearing ``DEFAULT_THROTTLE_RATES``
(see ``backend/conftest.py``). A view that hardcodes ``throttle_classes`` bypasses
that, and a bare ``ScopedRateThrottle`` then raises ``ImproperlyConfigured`` when
its scope rate is missing. This subclass instead no-ops when no rate is
configured for the scope, so it throttles in production but stays inert in tests.
"""

from __future__ import annotations

from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle


class WaitlistScopedThrottle(ScopedRateThrottle):
    def allow_request(self, request, view):
        scope = getattr(view, self.scope_attr, None)
        rates = api_settings.DEFAULT_THROTTLE_RATES or {}
        # No scope or no configured rate (e.g. the test suite clears rates) →
        # don't throttle.
        if not scope or not rates.get(scope):
            return True
        return super().allow_request(request, view)
