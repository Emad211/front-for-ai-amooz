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
