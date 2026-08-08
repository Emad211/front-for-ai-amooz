from __future__ import annotations

import json
from typing import Any, Mapping

_RETRYABLE_HTTP_STATUSES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
_NON_RETRYABLE_CODES = frozenset({
    "model_access_limited",
    "invalid_api_key",
    "unauthorized",
    "forbidden",
    "invalid_request",
    "invalid_request_error",
})


def _json_object(body: bytes | str | None) -> Mapping[str, Any]:
    if body is None:
        return {}
    try:
        payload = json.loads(body)
    except (TypeError, ValueError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def classify_avalai_ocr_failure(
    *,
    status_code: int | None,
    body: bytes | str | None,
) -> dict[str, Any]:
    """Return a content-safe retry/configuration classification for an OCR failure.

    This deliberately does not infer retryability from the human error message. AvalAI
    exposes machine-readable ``error.code`` values for configuration failures, while
    transient gateway/rate-limit failures are classified from HTTP status.
    """

    root = _json_object(body)
    error = root.get("error")
    error = error if isinstance(error, Mapping) else {}
    code = str(error.get("code") or "").strip() or None
    error_type = str(error.get("type") or "").strip() or None
    request_id = str(error.get("request_id") or root.get("request_id") or "").strip() or None
    solution = str(error.get("solution") or "").strip() or None

    normalized_code = (code or "").lower()
    if normalized_code == "model_access_limited":
        category = "credential_model_access"
        retryable = False
    elif normalized_code in _NON_RETRYABLE_CODES or status_code in {400, 401, 403, 404, 422}:
        category = "request_or_credential_configuration"
        retryable = False
    elif status_code in _RETRYABLE_HTTP_STATUSES:
        category = "transient_provider_or_gateway"
        retryable = True
    elif status_code is None:
        category = "transport"
        retryable = True
    else:
        category = "provider_unknown"
        retryable = False

    return {
        "httpStatus": status_code,
        "providerErrorCode": code,
        "providerErrorType": error_type,
        "providerRequestId": request_id,
        "providerSolution": solution,
        "category": category,
        "retryable": retryable,
    }
