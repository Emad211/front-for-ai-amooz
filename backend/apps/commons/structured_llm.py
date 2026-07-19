"""Central, robust LLM -> validated-JSON layer for the whole project.

Why this exists
---------------
Historically every pipeline step scraped free-text model output with
``extract_json_object`` and either silently returned ``{}`` on failure or did
ad-hoc ``obj.get(...)`` guessing. There was no schema validation and no use of
the provider's JSON mode, even though Avalai (OpenAI-compatible) supports it.

This module provides ONE tiered path:

1. Ask the model with ``response_format={"type": "json_object"}`` (JSON mode).
   gemini-via-avalai does not reliably honour *strict* ``json_schema``, so we use
   the looser ``json_object`` mode as the baseline and validate ourselves. If the
   provider/model rejects ``response_format`` at all, we transparently retry
   without it.
2. Parse with the canonical robust extractor (``extract_json_object``).
3. Validate against a Pydantic model.
4. On parse/validation failure, do ONE repair round-trip, then re-validate.
5. If it still fails, RAISE ``StructuredOutputError`` — never return empty/garbage
   that silently corrupts downstream steps.

``validate_keep_dict`` is a lighter helper for migrating existing steps that must
preserve the model's *exact* dict (e.g. the structure step, whose output is stored
verbatim and consumed by other code): it validates the shape but returns the
original parsed object unmutated.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from apps.commons.json_utils import extract_json_object

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}


class StructuredOutputError(RuntimeError):
    """Raised when the model could not produce JSON matching the schema."""


def _json_object_mode_enabled() -> bool:
    return (os.getenv("LLM_JSON_OBJECT_MODE", "1") or "1").strip().lower() in {"1", "true", "yes"}


def _looks_like_response_format_unsupported(exc: Exception) -> bool:
    """Heuristic: did the provider reject the ``response_format`` parameter?

    Different gateways/models surface this differently (400/422, or a message
    about an unsupported/unknown parameter). We only fall back when the error
    clearly references response_format / json mode, so genuine errors still bubble.
    """
    msg = str(exc).lower()
    if "response_format" in msg or "response format" in msg:
        return True
    if "json_object" in msg or "json mode" in msg:
        return True
    # Some gateways say "unsupported parameter" / "unknown parameter".
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


def validate_obj(obj: Any, schema: Type[T]) -> T:
    """Validate an already-parsed object against ``schema`` (raises on mismatch)."""
    try:
        return schema.model_validate(obj)
    except ValidationError as exc:
        raise StructuredOutputError(
            f"{schema.__name__} validation failed: {exc.errors(include_url=False)[:5]}"
        ) from exc


def parse_structured(text: str, schema: Type[T]) -> T:
    """Extract JSON from ``text`` and validate it into ``schema``.

    Raises ``StructuredOutputError`` if no JSON can be found or the shape is wrong.
    """
    try:
        obj = extract_json_object(text)
    except Exception as exc:
        raise StructuredOutputError(f"no parseable JSON for {schema.__name__}: {exc}") from exc
    return validate_obj(obj, schema)


def validate_keep_dict(text: str, schema: Type[BaseModel]) -> Any:
    """Validate ``text`` against ``schema`` but return the ORIGINAL parsed object.

    Use when downstream code expects the model's exact dict (no Pydantic
    normalization). The validation still runs as a gate and raises on mismatch.
    """
    try:
        obj = extract_json_object(text)
    except Exception as exc:
        raise StructuredOutputError(f"no parseable JSON for {schema.__name__}: {exc}") from exc
    validate_obj(obj, schema)  # raises StructuredOutputError on mismatch
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
) -> T:
    """Call the LLM and return a validated Pydantic instance of ``schema``.

    Tiered: JSON mode (with graceful fallback) -> robust parse -> validate ->
    one repair round-trip -> validate. Raises ``StructuredOutputError`` on total
    failure rather than returning empty data.
    """
    # Imported lazily to avoid a hard import cycle at module load.
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
        ).text

    # --- First attempt (optionally in JSON mode, with graceful fallback) ---
    try:
        text = _call(base_messages, _JSON_OBJECT_RESPONSE_FORMAT if use_json_mode else None)
    except Exception as exc:
        if use_json_mode and _looks_like_response_format_unsupported(exc):
            logger.warning(
                "Provider rejected response_format=json_object; retrying without it: %s", exc
            )
            text = _call(base_messages, None)
        else:
            raise

    last_error: Optional[Exception] = None
    for attempt in range(max_repair + 1):
        try:
            obj = extract_json_object(text)
            return validate_obj(obj, schema)
        except (StructuredOutputError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= max_repair:
                break
            logger.warning(
                "%s parse/validate failed (attempt %d/%d); requesting repair: %s",
                schema.__name__, attempt + 1, max_repair + 1, exc,
            )
            repair_messages = [{"role": "user", "content": _repair_instruction(text, exc, schema)}]
            try:
                text = _call(repair_messages, None)
            except Exception as call_exc:  # network/provider error on repair
                last_error = call_exc
                break

    raise StructuredOutputError(
        f"Failed to obtain valid {schema.__name__} after {max_repair + 1} attempt(s): {last_error}"
    )
