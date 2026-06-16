"""Throttling for the public waitlist intake.

Thin alias over the shared ``SafeScopedRateThrottle`` (kept so existing imports
of ``WaitlistScopedThrottle`` and the ``waitlist`` scope keep working).
"""

from __future__ import annotations

from apps.core.throttling import SafeScopedRateThrottle


class WaitlistScopedThrottle(SafeScopedRateThrottle):
    pass
