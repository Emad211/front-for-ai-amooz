from __future__ import annotations

import logging
from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def _as_error_dict(data: Any) -> dict[str, list[str]]:
    """Normalize DRF error payload to a dict[str, list[str]]."""
    if data is None:
        return {}

    # Typical DRF ValidationError shape: {field: ["msg", ...], ...}
    if isinstance(data, dict):
        normalized: dict[str, list[str]] = {}
        for key, value in data.items():
            if isinstance(value, (list, tuple)):
                normalized[key] = [str(v) for v in value]
            else:
                normalized[key] = [str(value)]
        return normalized

    # Sometimes DRF returns a list of messages.
    if isinstance(data, (list, tuple)):
        return {"non_field_errors": [str(v) for v in data]}

    # Fallback single message.
    return {"non_field_errors": [str(data)]}


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Unify API error responses.

    Contract:
    - Validation errors return: {"detail": "Validation error.", "errors": {..}}
    - Other errors keep DRF's default {"detail": "..."} shape.
    - Unhandled exceptions return JSON 500 (never HTML).
    """
    response = exception_handler(exc, context)

    # DRF returned None → unhandled exception (e.g. ValueError, DB error).
    # Return a generic JSON 500 instead of letting Django emit HTML.
    if response is None:
        logger.exception("Unhandled exception in %s", context.get('view', ''))
        return Response(
            {'detail': 'Internal server error.'},
            status=500,
        )

    data = response.data

    # Detect DRF-style validation errors by shape: dict without 'detail'.
    if isinstance(data, dict) and 'detail' not in data:
        response.data = {
            'detail': 'Validation error.',
            'errors': _as_error_dict(data),
        }
        return response

    # If already has 'detail', keep as-is for compatibility.
    return response
