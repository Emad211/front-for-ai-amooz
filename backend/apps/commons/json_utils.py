from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Tuple


logger = logging.getLogger(__name__)


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_BROKEN_FLOAT_JOIN_1 = re.compile(r"(?<=\d)\s*\r?\n\s*(?=\.\d)")
_BROKEN_FLOAT_JOIN_2 = re.compile(r"(?<=\.)\s*\r?\n\s*(?=\d)")


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
    return (
        s.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u201e", '"')
        .replace("\u201f", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


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


def _repair_json_string_escapes(json_text: str) -> str:
    """Repair common JSON issues inside string literals.

    Fixes:
    - Escapes raw control characters (0x00-0x1F) inside strings.
    - Repairs invalid backslash escapes (e.g. "\\text" written as "\text").

    Notes:
    - We only attempt repairs *inside* JSON string literals.
    - We keep valid escapes (\\n, \\t, \\" , \\\\ , \\uXXXX, ...).
    """

    s = json_text or ""
    out: list[str] = []
    in_string = False
    i = 0
    n = len(s)

    def _is_hex(c: str) -> bool:
        return c.isdigit() or ("a" <= c.lower() <= "f")

    while i < n:
        ch = s[i]

        if not in_string:
            out.append(ch)
            if ch == '"':
                in_string = True
            i += 1
            continue

        # in_string
        if ch == '"':
            out.append(ch)
            in_string = False
            i += 1
            continue

        if ch == "\\":
            # Look ahead to decide whether this is a valid escape.
            if i + 1 >= n:
                out.append("\\\\")
                i += 1
                continue

            nxt = s[i + 1]
            if nxt in '"\\/bfnrt':
                out.append("\\")
                out.append(nxt)
                i += 2
                continue

            if nxt == "u" and i + 5 < n and all(_is_hex(c) for c in s[i + 2 : i + 6]):
                out.append("\\")
                out.append("u")
                out.append(s[i + 2 : i + 6])
                i += 6
                continue

            # Invalid escape like \U or \a or \_ → escape the backslash itself.
            out.append("\\\\")
            i += 1
            continue

        code = ord(ch)
        if code < 0x20:
            if ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            elif ch == "\b":
                out.append("\\b")
            elif ch == "\f":
                out.append("\\f")
            else:
                out.append(f"\\u{code:04x}")
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _repair_broken_numbers(s: str) -> str:
    s = s or ""
    if not s:
        return s
    s = _BROKEN_FLOAT_JOIN_1.sub("", s)
    s = _BROKEN_FLOAT_JOIN_2.sub("", s)
    return s


def extract_json_object(text: str) -> Any:
    """Extract a JSON object/array from noisy LLM output."""

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
    
    # Repair: escape control chars / invalid backslashes inside strings, remove trailing commas
    candidate = _repair_json_string_escapes(candidate)
    candidate = _remove_trailing_commas(candidate)
    candidate = _repair_broken_numbers(candidate)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        # Log context for debugging
        try:
            pos = getattr(e, "pos", None)
            if isinstance(pos, int):
                lo = max(0, pos - 120)
                hi = min(len(candidate), pos + 120)
                snippet = candidate[lo:hi]
                logger.warning(
                    "JSON decode failed (%s) at line=%s col=%s pos=%s; snippet(escaped)=%s",
                    e.msg,
                    getattr(e, "lineno", None),
                    getattr(e, "colno", None),
                    pos,
                    snippet.encode("unicode_escape", "backslashreplace").decode("ascii", "ignore"),
                )
        except Exception:
            pass

        # Last attempt: apply all repairs again
        repaired = _repair_broken_numbers(_remove_trailing_commas(_repair_json_string_escapes(candidate)))
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e2:
            try:
                pos2 = getattr(e2, "pos", None)
                if isinstance(pos2, int):
                    lo2 = max(0, pos2 - 120)
                    hi2 = min(len(repaired), pos2 + 120)
                    snippet2 = repaired[lo2:hi2]
                    logger.error(
                        "JSON decode still failed after repair (%s) at line=%s col=%s pos=%s; snippet(escaped)=%s",
                        e2.msg,
                        getattr(e2, "lineno", None),
                        getattr(e2, "colno", None),
                        pos2,
                        snippet2.encode("unicode_escape", "backslashreplace").decode("ascii", "ignore"),
                    )
            except Exception:
                pass
            raise
