from __future__ import annotations

import json
import re
from typing import Any, Optional, Tuple


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_BROKEN_FLOAT_JOIN_1 = re.compile(r"(?<=\d)\s*\r?\n\s*(?=\.\d)")
_BROKEN_FLOAT_JOIN_2 = re.compile(r"(?<=\.)\s*\r?\n\s*(?=\d)")


def _escape_invalid_backslashes_in_strings(s: str) -> str:
    """Escape invalid JSON backslash sequences inside string literals.

    LLM outputs often contain LaTeX commands inside JSON strings like "\\cdot" or "\\times".
    In JSON, backslashes must be followed by a valid escape ("\\\\", "\\/", "\\\"", "\\b", "\\f", "\\n", "\\r", "\\t", "\\uXXXX").
    This function walks the text and, inside quoted strings, converts any invalid
    single backslash into a double backslash so JSON parsing can succeed.
    """

    if not s:
        return s

    valid_escapes = {'"', '\\', '/', 'b', 'f', 'n', 'r', 't', 'u'}
    out: list[str] = []
    in_string = False
    escape = False

    i = 0
    while i < len(s):
        ch = s[i]

        if not in_string:
            out.append(ch)
            if ch == '"':
                in_string = True
                escape = False
            i += 1
            continue

        # inside string
        if escape:
            # previous char was backslash; just copy current and clear escape flag
            out.append(ch)
            escape = False
            i += 1
            continue

        if ch == '\\':
            nxt = s[i + 1] if i + 1 < len(s) else ''
            if nxt and nxt in valid_escapes:
                out.append(ch)
                escape = True
                i += 1
                continue

            # invalid escape (e.g., \c, \x, \ , end-of-string) -> escape the backslash
            out.append('\\\\')
            i += 1
            continue

        out.append(ch)
        if ch == '"':
            in_string = False
        i += 1

    return ''.join(out)


def _strip_code_fences(text: str) -> str:
    m = _FENCE_RE.search(text or "")
    if not m:
        return text
    inner = m.group(1)
    return inner if inner is not None else text


def _normalize_llm_text(text: str) -> str:
    s = (text or "").strip().lstrip("\ufeff")
    if not s:
        return s

    s = _strip_code_fences(s).strip()

    # Smart quotes etc can break JSON.
    s = (
        s.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u201e", '"')
        .replace("\u201f", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )

    # Fix invalid \ escapes inside strings (e.g., LaTeX commands).
    return _escape_invalid_backslashes_in_strings(s)


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

        if ch in "}]":
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


def extract_json_object(text: str) -> Any:
    s = _normalize_llm_text(text)
    if not s:
        raise ValueError("empty text")

    # 1) direct parse
    try:
        return json.loads(s)
    except Exception:
        pass

    # 2) extract balanced JSON
    block = _find_balanced_json_block(s)
    if not block:
        raise ValueError("no JSON object/array found")

    start, end = block
    candidate = s[start : end + 1]
    candidate = _repair_broken_numbers(candidate)
    candidate = _remove_trailing_commas(candidate)

    # One more pass of backslash repair over the extracted JSON block.
    candidate = _escape_invalid_backslashes_in_strings(candidate)

    return json.loads(candidate)
