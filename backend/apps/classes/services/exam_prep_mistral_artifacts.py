"""Session-scoped lifecycle for private Mistral Exam Prep artifacts."""
from __future__ import annotations

import logging
import re
from typing import Any


logger = logging.getLogger("apps.classes.exam_prep")

MISTRAL_VISUAL_STORAGE_PREFIX = "exam-prep/source/visuals/v1"
MISTRAL_OCR_CHECKPOINT_PREFIX = "exam-prep/source/ocr4-checkpoints/v1"
_SESSION_NAMESPACE_RE = re.compile(r"^session-(?P<id>[1-9][0-9]*)$")


def session_artifact_namespace(session_id: int) -> str:
    """Return the only namespace shape accepted by destructive cleanup."""

    try:
        normalized = int(session_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("A positive session id is required.") from exc
    if isinstance(session_id, bool) or normalized <= 0:
        raise ValueError("A positive session id is required.")
    return f"session-{normalized}"


def validate_storage_namespace(namespace: str) -> str:
    """Validate a non-destructive storage namespace used by one task retry set."""

    normalized = str(namespace or "").strip()
    if normalized and _SESSION_NAMESPACE_RE.fullmatch(normalized) is None:
        raise ValueError("Invalid private artifact storage namespace.")
    return normalized


def _safe_child(prefix: str, component: Any) -> str | None:
    value = str(component or "")
    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        return None
    return f"{prefix}/{value}"


def _delete_prefix_once(storage, prefix: str) -> tuple[bool, int]:
    """Delete files below one already-validated prefix without leaving it."""

    pending = [prefix]
    deleted = 0
    complete = True
    while pending:
        current = pending.pop()
        try:
            directories, files = storage.listdir(current)
        except FileNotFoundError:
            continue
        except Exception:
            logger.exception("Could not list private session artifact prefix %s.", current)
            complete = False
            continue

        for filename in files:
            name = _safe_child(current, filename)
            if name is None:
                complete = False
                continue
            try:
                storage.delete(name)
                deleted += 1
            except Exception:
                logger.exception("Could not delete private session artifact %s.", name)
                complete = False

        for directory in directories:
            child = _safe_child(current, directory)
            if child is None:
                complete = False
                continue
            pending.append(child)
    return complete, deleted


def _prefix_is_empty(storage, prefix: str) -> bool:
    pending = [prefix]
    while pending:
        current = pending.pop()
        try:
            directories, files = storage.listdir(current)
        except FileNotFoundError:
            continue
        except Exception:
            logger.exception("Could not verify private session artifact prefix %s.", current)
            return False
        if files:
            return False
        for directory in directories:
            child = _safe_child(current, directory)
            if child is None:
                return False
            pending.append(child)
    return True


def cleanup_session_private_artifacts(
    session_id: int,
    *,
    include_visuals: bool = True,
    include_checkpoints: bool = True,
    storage=None,
) -> bool:
    """Delete only the private prefixes owned by one Exam Prep session.

    Two passes narrow the cancel/revoke race: an object completed while the
    first pass is listing is observed by the second pass. Stage-3 also checks
    cooperative cancellation immediately after each save.
    """

    namespace = session_artifact_namespace(session_id)
    if storage is None:
        try:
            from django.core.files.storage import storages

            storage = storages["answer_sources"]
        except Exception:
            logger.exception(
                "Could not resolve private storage for Exam Prep session %s.",
                session_id,
            )
            return False

    roots: list[str] = []
    if include_visuals:
        roots.append(f"{MISTRAL_VISUAL_STORAGE_PREFIX}/{namespace}")
    if include_checkpoints:
        roots.append(f"{MISTRAL_OCR_CHECKPOINT_PREFIX}/{namespace}")

    complete = True
    for prefix in roots:
        for _pass in range(2):
            pass_complete, _deleted = _delete_prefix_once(storage, prefix)
            complete = pass_complete and complete
        complete = _prefix_is_empty(storage, prefix) and complete
    if not complete:
        logger.warning(
            "Private artifact cleanup remains incomplete for Exam Prep session %s.",
            session_id,
        )
    return complete


__all__ = [
    "MISTRAL_OCR_CHECKPOINT_PREFIX",
    "MISTRAL_VISUAL_STORAGE_PREFIX",
    "cleanup_session_private_artifacts",
    "session_artifact_namespace",
    "validate_storage_namespace",
]
