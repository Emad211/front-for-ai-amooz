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
from apps.commons.exchange_rate import convert_usd_to_toman

logger = logging.getLogger(__name__)

# Thread-local storage for user context. Safe under gthread/threaded workers:
# every value is set and cleared within the lifetime of one request on its own
# thread (see LLMTrackingMiddleware / llm_tracking_context).
_local = threading.local()

# Sentinel so a lazily-resolved-but-None user is cached and not re-resolved.
_UNSET = object()


def set_current_user(user) -> None:
    """Set an EXPLICIT current user (e.g. from a Celery task). Takes precedence
    over any request-derived user."""
    _local.user = user


def set_current_request(request) -> None:
    """Stash the current request so the user can be resolved LAZILY — only if/when
    an LLM call actually needs it. Avoids a redundant ``User`` SELECT on the vast
    majority of requests that never hit the LLM. Call from request middleware."""
    _local.request = request
    _local.user_cache = _UNSET


def clear_request_context() -> None:
    """Drop the per-request user/request context. Call in middleware ``finally``."""
    _local.request = None
    _local.user_cache = _UNSET
    _local.user = None


def _resolve_user_from_request(request):
    """Best-effort resolve the authenticated user from a request (DRF user first,
    then a JWT bearer token). Returns None if unauthenticated/invalid."""
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


def get_current_user():
    """Get the current user for token tracking.

    Precedence: an explicit user (set_current_user, e.g. Celery) wins; otherwise
    the user is resolved LAZILY from the stashed request the first time it is
    needed, then cached for the rest of the request.
    """
    explicit = getattr(_local, 'user', None)
    if explicit is not None:
        return explicit

    request = getattr(_local, 'request', None)
    if request is None:
        return None
    cache = getattr(_local, 'user_cache', _UNSET)
    if cache is _UNSET:
        cache = _resolve_user_from_request(request)
        _local.user_cache = cache
    return cache


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


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _resolve_session_org_group(session_id: int | None) -> tuple[int | None, int | None]:
    """Map a ClassCreationSession id → (organization_id, study_group_id).

    Best-effort denormalization so each LLM cost row can be rolled up per
    organization / per study group. Returns (None, None) for personal classes
    or when the session can't be resolved.
    """
    if not session_id:
        return None, None
    try:
        from apps.classes.models import ClassCreationSession
        row = (
            ClassCreationSession.objects
            .filter(pk=session_id)
            .values_list('organization_id', 'study_group_id')
            .first()
        )
        if row:
            return row[0], row[1]
    except Exception:  # pragma: no cover - never break tracking
        logger.debug('Could not resolve org/group for session %s', session_id, exc_info=True)
    return None, None


def _extract_usage_metadata(resp: Any) -> dict[str, int]:
    """Extract token counts from an LLM response, provider-agnostically.

    Handles both shapes:

    * **OpenAI / Avalai** (``resp.usage``): ``prompt_tokens`` /
      ``completion_tokens`` / ``total_tokens``, plus
      ``prompt_tokens_details.cached_tokens`` / ``.audio_tokens`` and
      ``completion_tokens_details.reasoning_tokens``.
    * **Google Gemini** (``resp.usage_metadata``): ``prompt_token_count`` /
      ``candidates_token_count`` / ``total_token_count``, plus
      ``cached_content_token_count`` and ``thoughts_token_count``.

    Returns a dict with keys: ``input``, ``output``, ``total``,
    ``audio_input``, ``cached_input``, ``thinking`` (all ints).
    """
    out = {
        'input': 0, 'output': 0, 'total': 0,
        'audio_input': 0, 'cached_input': 0, 'thinking': 0,
    }

    # --- OpenAI / Avalai shape -------------------------------------------
    usage = getattr(resp, 'usage', None)
    if usage is not None and (
        hasattr(usage, 'prompt_tokens') or hasattr(usage, 'completion_tokens')
    ):
        out['input'] = _as_int(getattr(usage, 'prompt_tokens', 0))
        out['output'] = _as_int(getattr(usage, 'completion_tokens', 0))
        out['total'] = _as_int(getattr(usage, 'total_tokens', 0))

        prompt_details = getattr(usage, 'prompt_tokens_details', None)
        if prompt_details is not None:
            out['cached_input'] = _as_int(getattr(prompt_details, 'cached_tokens', 0))
            out['audio_input'] = _as_int(getattr(prompt_details, 'audio_tokens', 0))

        completion_details = getattr(usage, 'completion_tokens_details', None)
        if completion_details is not None:
            out['thinking'] = _as_int(getattr(completion_details, 'reasoning_tokens', 0))

        if out['total'] == 0:
            out['total'] = out['input'] + out['output']
        return out

    # --- Google Gemini shape ---------------------------------------------
    meta = getattr(resp, 'usage_metadata', None)
    if meta is not None:
        out['input'] = _as_int(getattr(meta, 'prompt_token_count', 0))
        out['output'] = _as_int(getattr(meta, 'candidates_token_count', 0))
        out['total'] = _as_int(getattr(meta, 'total_token_count', 0))
        out['cached_input'] = _as_int(getattr(meta, 'cached_content_token_count', 0))
        out['thinking'] = _as_int(getattr(meta, 'thoughts_token_count', 0))
        if out['total'] == 0:
            out['total'] = out['input'] + out['output'] + out['thinking']
        return out

    return out


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
        usage = _extract_usage_metadata(resp)
        input_tokens = usage['input']
        output_tokens = usage['output']
        total_tokens = usage['total']

        resolved_user = user or get_current_user()
        resolved_session = session_id or get_current_session_id()
        org_id, group_id = _resolve_session_org_group(resolved_session)

        # If resolved_user is an AnonymousUser or not a model instance, set to None
        if resolved_user is not None:
            pk = getattr(resolved_user, 'pk', None)
            if pk is None:
                resolved_user = None

        cost = estimate_cost(
            model_name,
            input_tokens,
            output_tokens,
            provider=provider,
            audio_input_tokens=usage['audio_input'],
            cached_input_tokens=usage['cached_input'],
        )

        # Snapshot the Toman cost (and the rate applied) at write time so
        # historical totals never drift with today's exchange rate.
        cost_toman, rate, _rate_err = convert_usd_to_toman(float(cost))

        log = LLMUsageLog(
            user=resolved_user,
            feature=feature,
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            audio_input_tokens=usage['audio_input'],
            cached_input_tokens=usage['cached_input'],
            thinking_tokens=usage['thinking'],
            estimated_cost_usd=cost,
            estimated_cost_toman=cost_toman or 0,
            usd_toman_rate=rate or 0,
            session_id=resolved_session,
            organization_id=org_id,
            study_group_id=group_id,
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
        org_id, group_id = _resolve_session_org_group(resolved_session)

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
            organization_id=org_id,
            study_group_id=group_id,
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
