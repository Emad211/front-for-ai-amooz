from __future__ import annotations

from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


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
    """
    response = exception_handler(exc, context)
    if response is None:
        return None

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
