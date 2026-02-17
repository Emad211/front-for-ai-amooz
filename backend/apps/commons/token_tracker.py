"""Centralized token usage tracking for all LLM calls.

Usage example:
    from apps.commons.token_tracker import track_llm_usage

    resp = client.models.generate_content(model=model, contents=contents)
    track_llm_usage(
        resp=resp,
        feature=LLMUsageLog.Feature.QUIZ_GRADING,
        provider='gemini',
        model_name=model,
        user=request.user,
        session_id=session.id,
    )
"""

from __future__ import annotations

import logging
import time
import threading
from contextlib import contextmanager
from typing import Any, Optional

from apps.commons.models import LLMUsageLog, estimate_cost

logger = logging.getLogger(__name__)

# Thread-local storage for user context
_local = threading.local()


def set_current_user(user) -> None:
    """Set the current user for token tracking (call from view/middleware)."""
    _local.user = user


def get_current_user():
    """Get the current user set by the view layer."""
    return getattr(_local, 'user', None)


def set_current_session_id(session_id: int | None) -> None:
    """Set the current session ID for token tracking."""
    _local.session_id = session_id


def get_current_session_id() -> int | None:
    """Get the current session ID."""
    return getattr(_local, 'session_id', None)


@contextmanager
def llm_tracking_context(*, user=None, session_id: int | None = None):
    """Context manager that sets user/session for all LLM calls within the block."""
    old_user = getattr(_local, 'user', None)
    old_session = getattr(_local, 'session_id', None)
    if user is not None:
        _local.user = user
    if session_id is not None:
        _local.session_id = session_id
    try:
        yield
    finally:
        _local.user = old_user
        _local.session_id = old_session


def _extract_usage_metadata(resp: Any) -> tuple[int, int, int]:
    """Extract token counts from a google.genai response object."""
    usage = getattr(resp, 'usage_metadata', None)
    if usage is None:
        return 0, 0, 0

    input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
    output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
    total = getattr(usage, 'total_token_count', 0) or 0

    if total == 0:
        total = input_tokens + output_tokens

    return input_tokens, output_tokens, total


def track_llm_usage(
    *,
    resp: Any,
    feature: str,
    provider: str,
    model_name: str,
    user=None,
    session_id: int | None = None,
    detail: str = '',
    duration_ms: int = 0,
    success: bool = True,
    error_message: str = '',
) -> LLMUsageLog | None:
    """Log an LLM call's token usage to the database.

    Extracts token counts from the google.genai response ``usage_metadata``
    and persists a LLMUsageLog row.  Silently returns ``None`` on failure
    so that tracking never breaks the main application flow.
    """
    try:
        input_tokens, output_tokens, total_tokens = _extract_usage_metadata(resp)

        resolved_user = user or get_current_user()
        resolved_session = session_id or get_current_session_id()

        # If resolved_user is an AnonymousUser or not a model instance, set to None
        if resolved_user is not None:
            pk = getattr(resolved_user, 'pk', None)
            if pk is None:
                resolved_user = None

        cost = estimate_cost(model_name, input_tokens, output_tokens)

        log = LLMUsageLog(
            user=resolved_user,
            feature=feature,
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            session_id=resolved_session,
            detail=detail[:200] if detail else '',
            duration_ms=duration_ms,
            success=success,
            error_message=error_message[:1000] if error_message else '',
        )
        log.save()
        return log
    except Exception:
        logger.exception('Failed to track LLM usage')
        return None


def track_llm_error(
    *,
    feature: str,
    provider: str,
    model_name: str,
    error_message: str,
    user=None,
    session_id: int | None = None,
    detail: str = '',
    duration_ms: int = 0,
) -> LLMUsageLog | None:
    """Log a failed LLM call."""
    try:
        resolved_user = user or get_current_user()
        resolved_session = session_id or get_current_session_id()

        if resolved_user is not None:
            pk = getattr(resolved_user, 'pk', None)
            if pk is None:
                resolved_user = None

        log = LLMUsageLog(
            user=resolved_user,
            feature=feature,
            provider=provider,
            model_name=model_name,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost_usd=0,
            session_id=resolved_session,
            detail=detail[:200] if detail else '',
            duration_ms=duration_ms,
            success=False,
            error_message=str(error_message)[:1000],
        )
        log.save()
        return log
    except Exception:
        logger.exception('Failed to track LLM error')
        return None


class LLMTimer:
    """Simple timer for measuring LLM call duration."""

    def __init__(self) -> None:
        self._start: float = 0

    def start(self) -> 'LLMTimer':
        self._start = time.monotonic()
        return self

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)


def tracked_generate_content(
    client: Any,
    *,
    model: str,
    contents: Any,
    config: Any = None,
    feature: str = 'other',
    provider: str = 'unknown',
    user: Any = None,
    session_id: int | None = None,
    detail: str = '',
) -> Any:
    """Wrap ``client.models.generate_content()`` with automatic token tracking.

    Returns the raw LLM response object so callers can continue to
    extract text/JSON as before.  On failure the exception is re-raised
    after logging the error.
    """
    timer = LLMTimer().start()
    try:
        kwargs: dict[str, Any] = {'model': model, 'contents': contents}
        if config is not None:
            kwargs['config'] = config
        resp = client.models.generate_content(**kwargs)
        track_llm_usage(
            resp=resp,
            feature=feature,
            provider=provider,
            model_name=model,
            duration_ms=timer.elapsed_ms,
            user=user,
            session_id=session_id,
            detail=detail,
        )
        return resp
    except Exception as exc:
        track_llm_error(
            feature=feature,
            provider=provider,
            model_name=model,
            error_message=str(exc),
            duration_ms=timer.elapsed_ms,
            user=user,
            session_id=session_id,
            detail=detail,
        )
        raise
