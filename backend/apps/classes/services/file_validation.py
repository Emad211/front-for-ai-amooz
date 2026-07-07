"""File validation helpers for Exercise Hub uploads.

These helpers deliberately avoid trusting browser-provided MIME types. They are
small and dependency-light so ingest, grading, and views can share them without
coupling those services together.
"""
from __future__ import annotations

from typing import Any


def is_real_image(data: bytes) -> bool:
    """Return True when ``data`` is an actual readable image."""
    if not data:
        return False
    try:
        from PIL import Image
        import io

        Image.open(io.BytesIO(data)).verify()
        return True
    except Exception:
        return False


def is_probably_pdf(data: bytes) -> bool:
    """Fast PDF magic-byte check."""
    return bool(data) and data.lstrip().startswith(b"%PDF")


def uploaded_name(uploaded: Any) -> str:
    return (getattr(uploaded, "name", "") or "").lower()


def uploaded_content_type(uploaded: Any) -> str:
    return (getattr(uploaded, "content_type", "") or "").lower()
