"""Central, robust LLM -> validated-JSON layer for the whole project.

Structured callers can optionally request strict JSON Schema output. Providers
that do not support it fall back safely to JSON-object mode and then to ordinary
text, while Pydantic remains the final authority.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from apps.commons.json_utils import extract_json_object

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}


class StructuredOutputError(RuntimeError):
    """Raised when the model could not produce JSON matching the schema.

    ``error_kind`` and ``validation_locations`` are content-free diagnostics.
    They may be logged even for sensitive requests because they never contain
    model output or field values.
    """

    def __init__(
        self,
        message: str,
        *,
        error_kind: str = "structured_output",
        validation_locations: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.error_kind = str(error_kind or "structured_output")[:80]
        self.validation_locations = tuple(validation_locations[:8])


def _json_object_mode_enabled() -> bool:
    return (os.getenv("LLM_JSON_OBJECT_MODE", "1") or "1").strip().lower() in {"1", "true", "yes"}


def _looks_like_response_format_unsupported(exc: Exception) -> bool:
    """Heuristic: did the provider reject structured response formatting?"""

    msg = str(exc).lower()
    if "response_format" in msg or "response format" in msg:
        return True
    if "json_object" in msg or "json object" in msg or "json mode" in msg:
        return True
    if "json_schema" in msg or "json schema" in msg:
        return True
    if ("unsupported" in msg or "unknown" in msg or "not supported" in msg) and "param" in msg:
        return True
    return False


def _build_messages(messages: Optional[list], contents: Optional[Any]) -> list:
    if messages is not None:
        return messages
    if contents is not None:
        return [{"role": "user", "content": contents}]
    raise ValueError("Either 'messages' or 'contents' must be provided")


def _repair_instruction(broken_text: str, error: Exception, schema: Type[BaseModel]) -> str:
    required_keys = ", ".join(schema.model_fields.keys()) or "(see schema)"
    return (
        "The text below was supposed to be a single JSON object but it is "
        "malformed or does not match the required shape.\n"
        f"Validation error: {error}\n"
        f"Return ONLY one valid JSON object (no markdown fences, no commentary) "
        f"whose top-level keys include: {required_keys}.\n\n"
        f"TEXT:\n{broken_text}"
    )


def _validation_locations(exc: ValidationError) -> tuple[str, ...]:
    locations: list[str] = []
    for item in exc.errors(include_url=False)[:8]:
        raw_location = item.get("loc") or ()
        location = ".".join(str(part) for part in raw_location) or "root"
        error_type = str(item.get("type") or "validation_error")
        locations.append(f"{location}:{error_type}"[:180])
    return tuple(locations)


def _strict_schema_node(value: Any) -> Any:
    """Convert a Pydantic schema into the strict OpenAI-compatible subset."""

    if isinstance(value, list):
        return [_strict_schema_node(item) for item in value]
    if not isinstance(value, dict):
        return value

    result = {
        key: _strict_schema_node(item)
        for key, item in value.items()
        if key != "default"
    }
    properties = result.get("properties")
    if isinstance(properties, dict):
        result["properties"] = {
            key: _strict_schema_node(item)
            for key, item in properties.items()
        }
        result["required"] = list(properties.keys())
        result["additionalProperties"] = False
    elif result.get("type") == "object":
        result["additionalProperties"] = False
    return result


def _strict_response_format(schema: Type[BaseModel]) -> dict[str, Any]:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", schema.__name__).strip("_")[:64]
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name or "structured_output",
            "strict": True,
            "schema": _strict_schema_node(schema.model_json_schema()),
        },
    }


def validate_obj(obj: Any, schema: Type[T]) -> T:
    """Validate an already-parsed object against ``schema`` (raises on mismatch)."""

    try:
        return schema.model_validate(obj)
    except ValidationError as exc:
        locations = _validation_locations(exc)
        raise StructuredOutputError(
            f"{schema.__name__} validation failed at {list(locations)}",
            error_kind="validation_error",
            validation_locations=locations,
        ) from exc


def parse_structured(text: str, schema: Type[T]) -> T:
    """Extract JSON from ``text`` and validate it into ``schema``."""

    try:
        obj = extract_json_object(text)
    except Exception as exc:
        raise StructuredOutputError(
            f"no parseable JSON for {schema.__name__}: {exc}",
            error_kind="json_parse_error",
        ) from exc
    return validate_obj(obj, schema)


def validate_keep_dict(text: str, schema: Type[BaseModel]) -> Any:
    """Validate ``text`` against ``schema`` but return the original parsed dict."""

    try:
        obj = extract_json_object(text)
    except Exception as exc:
        raise StructuredOutputError(
            f"no parseable JSON for {schema.__name__}: {exc}",
            error_kind="json_parse_error",
        ) from exc
    validate_obj(obj, schema)
    return obj


def generate_structured(
    *,
    schema: Type[T],
    messages: Optional[list] = None,
    contents: Optional[Any] = None,
    model: Optional[str] = None,
    feature: Optional[str] = None,
    timeout: Optional[float] = None,
    temperature: Optional[float] = None,
    max_repair: int = 1,
    json_object_mode: Optional[bool] = None,
    strict_json_schema: bool = False,
    sensitive: bool = False,
    max_output_tokens: Optional[int] = None,
    detail: str = "",
    tracking_context: Optional[dict[str, Any]] = None,
    provider_attempts: int = 3,
) -> T:
    """Call the LLM and return a validated Pydantic instance of ``schema``.

    When ``strict_json_schema`` is enabled, the first request uses strict JSON
    Schema. Unsupported providers fall back to JSON-object mode, then ordinary
    output. Parse/validation failure may use bounded repair calls.
    """

    from apps.chatbot.services.llm_client import generate_text

    base_messages = _build_messages(messages, contents)
    use_json_mode = _json_object_mode_enabled() if json_object_mode is None else json_object_mode

    def _call(msgs: list, response_format: Optional[dict]) -> str:
        return generate_text(
            messages=msgs,
            model=model,
            feature=feature,
            timeout=timeout,
            temperature=temperature,
            response_format=response_format,
            max_output_tokens=max_output_tokens,
            detail=detail,
            tracking_context=tracking_context,
            provider_attempts=provider_attempts,
        ).text

    response_formats: list[Optional[dict]] = []
    if use_json_mode:
        if strict_json_schema:
            response_formats.append(_strict_response_format(schema))
        response_formats.append(_JSON_OBJECT_RESPONSE_FORMAT)
    response_formats.append(None)

    text: str | None = None
    selected_response_format: Optional[dict] = None
    for index, response_format in enumerate(response_formats):
        try:
            text = _call(base_messages, response_format)
            selected_response_format = response_format
            break
        except Exception as exc:
            has_fallback = index + 1 < len(response_formats)
            if response_format is not None and has_fallback and _looks_like_response_format_unsupported(exc):
                logger.warning(
                    "Provider rejected structured response format; using fallback format: %s",
                    type(exc).__name__,
                )
                continue
            raise

    if text is None:
        raise StructuredOutputError(
            f"No provider response for {schema.__name__}",
            error_kind="empty_provider_response",
        )

    last_error: Optional[Exception] = None
    for attempt in range(max(0, int(max_repair)) + 1):
        try:
            obj = extract_json_object(text)
            return validate_obj(obj, schema)
        except (StructuredOutputError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= max_repair:
                break
            if sensitive:
                logger.warning(
                    "%s parse/validate failed (attempt %d/%d); requesting repair kind=%s locations=%s",
                    schema.__name__,
                    attempt + 1,
                    max_repair + 1,
                    getattr(exc, "error_kind", type(exc).__name__),
                    getattr(exc, "validation_locations", ()),
                )
            else:
                logger.warning(
                    "%s parse/validate failed (attempt %d/%d); requesting repair: %s",
                    schema.__name__,
                    attempt + 1,
                    max_repair + 1,
                    exc,
                )
            repair_messages = [{"role": "user", "content": _repair_instruction(text, exc, schema)}]
            try:
                text = _call(repair_messages, selected_response_format)
            except Exception as call_exc:
                last_error = call_exc
                break

    error_kind = getattr(last_error, "error_kind", type(last_error).__name__ if last_error else "unknown")
    locations = getattr(last_error, "validation_locations", ())
    error_detail = "" if sensitive else f": {last_error}"
    raise StructuredOutputError(
        f"Failed to obtain valid {schema.__name__} after {max_repair + 1} attempt(s){error_detail}",
        error_kind=error_kind,
        validation_locations=tuple(locations),
    )
