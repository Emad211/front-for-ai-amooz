"""Sanitize model-produced Markdown without damaging mathematical comparisons."""

from __future__ import annotations

import html
import re


_CODE_TAG_RE = re.compile(r"<code\b[^>]*>(.*?)</code>", re.IGNORECASE | re.DOTALL)
_BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_KNOWN_TAGS = (
    "code|pre|br|b|strong|i|em|u|s|span|div|p|sub|sup|font|mark|small|big|"
    "tt|kbd|samp|abbr|cite|ins|del|blockquote"
)
_STRIP_TAG_RE = re.compile(rf"</?(?:{_KNOWN_TAGS})\b[^>]*>", re.IGNORECASE)
_EXCESS_BLANKLINES_RE = re.compile(r"\n{3,}")


def sanitize_llm_markdown(text: str | None) -> str:
    """Return idempotent, HTML-free Markdown while preserving plain ``x < y``."""
    if not text:
        return ""

    value = str(text)
    value = _CODE_TAG_RE.sub(lambda match: "`" + match.group(1).strip() + "`", value)
    value = _BR_TAG_RE.sub("\n", value)
    value = _STRIP_TAG_RE.sub("", value)
    value = html.unescape(value).replace("\xa0", " ")
    return _EXCESS_BLANKLINES_RE.sub("\n\n", value).strip()
