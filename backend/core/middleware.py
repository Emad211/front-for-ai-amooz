"""Lightweight health-check middleware for Kubernetes probes.

K8s readiness / liveness probes hit the Pod using its **internal IP** as the
``Host`` header.  Django's ``ALLOWED_HOSTS`` rightfully rejects those requests
(the Pod IP is not a trusted hostname).

This middleware is placed **before** ``SecurityMiddleware`` so it can intercept
``/api/health/`` requests and return ``200 OK`` without ever reaching the
``ALLOWED_HOSTS`` check, while all other requests still go through the full
Django middleware stack.

This is the industry-standard pattern for running Django inside Kubernetes.
"""

from __future__ import annotations

import json
import logging
import time

from django.http import HttpResponse

logger = logging.getLogger(__name__)

HEALTH_PATH = "/api/health/"


class HealthCheckMiddleware:
    """Return ``200`` for ``/api/health/`` before any host validation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH:
            return self._health_response()
        return self.get_response(request)

    # ------------------------------------------------------------------

    @staticmethod
    def _health_response() -> HttpResponse:
        payload: dict[str, str] = {
            "status": "healthy",
            "database": "connected",
            "redis": "unknown",
        }
        http_status = 200

        # --- Database (CRITICAL — 503 if unreachable) -----------------
        try:
            from django.db import connections

            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            logger.exception("Health check: database unreachable")
            payload["database"] = "disconnected"
            payload["status"] = "unhealthy"
            http_status = 503

        # --- Redis (NON-CRITICAL — report but don't fail probe) -------
        try:
            from django.conf import settings as _s
            import redis as _redis

            r = _redis.from_url(_s.REDIS_URL, socket_connect_timeout=3)
            r.ping()
            payload["redis"] = "connected"
        except Exception:
            logger.warning("Health check: Redis unreachable (non-critical)")
            payload["redis"] = "disconnected"
            # Do NOT set http_status=503 — Redis is needed for Celery
            # but the API can still serve requests without it.

        return HttpResponse(
            json.dumps(payload),
            content_type="application/json",
            status=http_status,
        )


class RequestLogMiddleware:
    """Log each request with method/path/status/latency and basic user context."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('core.request')

    def __call__(self, request):
        if request.path == HEALTH_PATH:
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        user = getattr(request, 'user', None)
        user_id = getattr(user, 'id', None) if getattr(user, 'is_authenticated', False) else None
        status_code = getattr(response, 'status_code', 0)
        level = logging.INFO
        if status_code >= 500:
            level = logging.ERROR
        elif status_code >= 400:
            level = logging.WARNING

        client_ip = _get_client_ip(request)
        self.logger.log(
            level,
            'HTTP %s %s %s %dms ip=%s user_id=%s size=%s',
            request.method,
            request.path,
            status_code,
            elapsed_ms,
            client_ip,
            user_id,
            response.get('Content-Length', '-'),
        )
        return response


def _get_client_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or '-'


class LLMTrackingMiddleware:
    """Automatically set thread-local user context for LLM token tracking.

    Must be placed AFTER ``AuthenticationMiddleware`` so ``request.user``
    is populated.  On every request the current user is stored in
    thread-local storage so that ``token_tracker.track_llm_usage()`` can
    associate LLM calls with the requesting user without requiring
    explicit user propagation through every service layer.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _resolve_user_from_request(request):
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            return user

        auth_header = (request.META.get('HTTP_AUTHORIZATION') or '').strip()
        if not auth_header.lower().startswith('bearer '):
            return None

        token = auth_header[7:].strip()
        if not token:
            return None

        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication

            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            return jwt_auth.get_user(validated_token)
        except Exception:
            return None

    def __call__(self, request):
        from apps.commons.token_tracker import set_current_user

        resolved_user = self._resolve_user_from_request(request)
        if resolved_user is not None and getattr(resolved_user, 'pk', None) is not None:
            set_current_user(resolved_user)
        else:
            set_current_user(None)
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)
