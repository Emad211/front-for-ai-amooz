import json

from apps.classes.services.exam_prep_avalai_ocr_errors import (
    classify_avalai_ocr_failure,
)


def test_model_access_limited_is_non_retryable_configuration_failure():
    body = json.dumps(
        {
            "error": {
                "code": "model_access_limited",
                "type": "model_access_limited",
                "request_id": "req-123",
                "solution": "Verify key permissions.",
            }
        }
    ).encode()

    result = classify_avalai_ocr_failure(status_code=403, body=body)

    assert result["category"] == "credential_model_access"
    assert result["retryable"] is False
    assert result["providerErrorCode"] == "model_access_limited"
    assert result["providerRequestId"] == "req-123"


def test_gateway_502_is_retryable():
    result = classify_avalai_ocr_failure(
        status_code=502,
        body=b"<html><body>Bad Gateway</body></html>",
    )

    assert result["category"] == "transient_provider_or_gateway"
    assert result["retryable"] is True


def test_bad_request_is_not_retryable():
    result = classify_avalai_ocr_failure(
        status_code=400,
        body=json.dumps({"error": {"code": "invalid_request"}}).encode(),
    )

    assert result["category"] == "request_or_credential_configuration"
    assert result["retryable"] is False
