"""Helpers for the HttpOnly refresh-token cookie.

The refresh token is delivered as an HttpOnly cookie (instead of being readable
from localStorage) so XSS cannot steal the long-lived session. Responses still
include the refresh in the body for backward compatibility; the cookie is the
source of truth for the cookie-aware frontend. All gated by AUTH_REFRESH_COOKIE.
"""

from __future__ import annotations

from django.conf import settings


def _enabled() -> bool:
    return getattr(settings, 'AUTH_REFRESH_COOKIE', True)


def _name() -> str:
    return getattr(settings, 'AUTH_REFRESH_COOKIE_NAME', 'refresh_token')


def get_refresh_from_request(request) -> str | None:
    """Return the refresh token from the cookie, if present."""
    return request.COOKIES.get(_name())


def set_refresh_cookie(response, refresh_token):
    """Attach the refresh token as an HttpOnly cookie (no-op if disabled/empty)."""
    if not _enabled() or not refresh_token:
        return response
    try:
        max_age = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
    except Exception:
        max_age = 3 * 24 * 3600
    response.set_cookie(
        _name(),
        str(refresh_token),
        max_age=max_age,
        httponly=True,
        secure=getattr(settings, 'AUTH_REFRESH_COOKIE_SECURE', True),
        samesite=getattr(settings, 'AUTH_REFRESH_COOKIE_SAMESITE', 'Lax'),
        path=getattr(settings, 'AUTH_REFRESH_COOKIE_PATH', '/api/'),
    )
    return response


def clear_refresh_cookie(response):
    """Remove the refresh cookie (used on logout)."""
    response.delete_cookie(
        _name(),
        path=getattr(settings, 'AUTH_REFRESH_COOKIE_PATH', '/api/'),
        samesite=getattr(settings, 'AUTH_REFRESH_COOKIE_SAMESITE', 'Lax'),
    )
    return response
