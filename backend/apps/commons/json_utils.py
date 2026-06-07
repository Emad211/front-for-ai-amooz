from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Tuple


logger = logging.getLogger(__name__)


# Canonical, project-wide robust JSON extractor for noisy LLM output.
#
# This module is the SINGLE source of truth. ``apps/classes/services/json_utils``
# re-exports ``extract_json_object`` from here so older imports keep working.
#
# It merges the strengths of the two historical copies:
#   * string-aware balanced-block scanning that survives markdown ``` fences
#     embedded *inside* JSON string values (programming lessons),
#   * repair of invalid backslash escapes (LaTeX like ``\cdot``) inside strings,
#   * escaping of raw control characters (0x00-0x1F) inside strings,
#   * dropping over-escaped single quotes (``\'`` -> ``'``),
#   * trailing-comma removal and broken-float rejoining,
#   * a 3-tier fallback (direct -> balanced-on-normalized -> balanced-on-raw).

# Greedy on purpose: capture up to the LAST closing fence. A non-greedy (.*?)
# truncates JSON whose own string values contain markdown code fences
# (```python ... ```), yielding "no JSON object/array found".
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*)```", re.DOTALL | re.IGNORECASE)
_BROKEN_FLOAT_JOIN_1 = re.compile(r"(?<=\d)\s*\r?\n\s*(?=\.\d)")
_BROKEN_FLOAT_JOIN_2 = re.compile(r"(?<=\.)\s*\r?\n\s*(?=\d)")

_CONTROL_MAP = {"\n": "\\n", "\r": "\\r", "\t": "\\t", "\b": "\\b", "\f": "\\f"}


def _is_hex(c: str) -> bool:
    return c.isdigit() or ("a" <= c.lower() <= "f")


def _repair_string_contents(s: str) -> str:
    r"""Repair common JSON issues that occur *inside* string literals.

    Inside ``"..."`` we:
      - keep valid escapes (``\n \t \" \\ \uXXXX`` ...),
      - convert invalid single backslashes (LaTeX like ``\cdot``) into ``\\``
        so json.loads succeeds,
      - drop over-escaped single quotes (``\'`` -> ``'``; never a real LaTeX
        command, which are letters like ``\alpha``),
      - escape raw control characters (0x00-0x1F) such as literal newlines.
    Characters outside string literals are passed through untouched.
    """
    if not s:
        return s

    out: list[str] = []
    in_string = False
    i = 0
    n = len(s)

    while i < n:
        ch = s[i]

        if not in_string:
            out.append(ch)
            if ch == '"':
                in_string = True
            i += 1
            continue

        # --- inside a string literal ---
        if ch == '"':
            out.append(ch)
            in_string = False
            i += 1
            continue

        if ch == "\\":
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt in '"\\/bfnrt':
                out.append("\\")
                out.append(nxt)
                i += 2
                continue
            if nxt == "u" and i + 5 < n and all(_is_hex(c) for c in s[i + 2 : i + 6]):
                out.append(s[i : i + 6])
                i += 6
                continue
            if nxt == "'":
                # over-escaped single quote: the model meant a literal '
                out.append("'")
                i += 2
                continue
            # invalid escape (\c, \x, \ , end-of-string) -> escape the backslash
            out.append("\\\\")
            i += 1
            continue

        code = ord(ch)
        if code < 0x20:
            out.append(_CONTROL_MAP.get(ch, f"\\u{code:04x}"))
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _strip_code_fences(text: str) -> str:
    m = _FENCE_RE.search(text or "")
    if not m:
        return text
    inner = m.group(1)
    return inner if inner is not None else text


def _normalize_quotes(text: str) -> str:
    s = (text or "").strip().lstrip("﻿")
    if not s:
        return s
    return (
        s.replace("“", '"')
        .replace("”", '"')
        .replace("„", '"')
        .replace("‟", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def _normalize_llm_text(text: str) -> str:
    s = _normalize_quotes(text)
    if not s:
        return s
    s = _strip_code_fences(s).strip()
    return _repair_string_contents(s)


def _find_balanced_json_block(text: str) -> Optional[Tuple[int, int]]:
    s = text or ""
    start: Optional[int] = None
    stack: list[str] = []
    in_string = False
    escape = False

    for i, ch in enumerate(s):
        if start is None:
            if ch in "{[":
                start = i
                stack = [ch]
                in_string = False
                escape = False
            continue

        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch in "{[":
            stack.append(ch)
            continue

        if ch in "]}":
            if not stack:
                return None
            open_ch = stack[-1]
            if (open_ch == "{" and ch != "}") or (open_ch == "[" and ch != "]"):
                return None
            stack.pop()
            if not stack:
                return (start, i)

    return None


def _remove_trailing_commas(s: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", s)


def _repair_broken_numbers(s: str) -> str:
    s = s or ""
    if not s:
        return s
    s = _BROKEN_FLOAT_JOIN_1.sub("", s)
    s = _BROKEN_FLOAT_JOIN_2.sub("", s)
    return s


def _parse_balanced_block(source: str) -> Any:
    """Find the outermost balanced ``{...}``/``[...]`` in ``source``, repair, parse.

    The balanced scanner is string-aware: it skips braces/fences that appear
    *inside* JSON string values, so it recovers the JSON even when
    content_markdown contains markdown code fences. Raises if nothing parses.
    """
    block = _find_balanced_json_block(source)
    if not block:
        raise ValueError("no JSON object/array found")

    start, end = block
    candidate = source[start : end + 1]
    candidate = _repair_string_contents(candidate)
    candidate = _remove_trailing_commas(candidate)
    candidate = _repair_broken_numbers(candidate)
    return json.loads(candidate)


def extract_json_object(text: str) -> Any:
    """Extract a JSON object/array from noisy LLM output.

    Tiered strategy:
      1. direct parse of fence-stripped, normalized text (fast path),
      2. string-aware balanced-block extraction on the normalized text,
      3. safety net: balanced scan on the RAW text (no fence stripping), in case
         fence handling ever truncated JSON whose own values contain ``` fences.
    Raises ``ValueError`` / ``json.JSONDecodeError`` if nothing parses.
    """
    normalized = _normalize_llm_text(text)
    if not normalized:
        raise ValueError("empty text")

    # 1) direct
    try:
        return json.loads(normalized)
    except Exception:
        pass

    # 2) balanced block on the normalized text
    try:
        return _parse_balanced_block(normalized)
    except Exception as exc:
        logger.debug("balanced parse on normalized text failed: %s", exc)

    # 3) safety net: balanced scan on raw text without fence stripping
    raw = _repair_string_contents(_normalize_quotes(text))
    return _parse_balanced_block(raw)
