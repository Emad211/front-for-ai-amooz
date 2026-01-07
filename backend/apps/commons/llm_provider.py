from __future__ import annotations

import os
from typing import Literal


Provider = Literal['auto', 'gemini', 'avalai']


def preferred_provider() -> Provider:
    """Return the preferred LLM provider.

    Reads `LLM_PROVIDER` first, then falls back to legacy `MODE`.

    Values:
    - `avalai`: use Avalai only
    - `gemini`: use Gemini only
    - `auto`: try Gemini then Avalai
    """

    raw = (os.getenv('LLM_PROVIDER') or os.getenv('MODE') or '').strip().lower()
    if raw in {'avalai', 'gemini', 'auto'}:
        return raw  # type: ignore[return-value]
    return 'auto'
