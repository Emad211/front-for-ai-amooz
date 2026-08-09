"""Lexical-only decoder for structured provider JSON containing math Markdown.

This module deliberately does not repair structure or invent missing JSON data.
It only normalizes transport-level syntax that preserves the exact source text:
BOM/fences, raw controls in strings, trailing commas, and unescaped LaTeX
backslashes. Missing quotes/braces, truncated arrays and semantic schema errors
still fail closed.
"""
from __future__ import annotations

import json
import re
from typing import Any


_LATEX_COMMANDS = frozenset(
    {
        "alpha", "beta", "begin", "cdot", "cos", "delta", "displaystyle",
        "end", "exists", "frac", "gamma", "geq", "in", "infty", "int",
        "lambda", "left", "leftarrow", "leq", "lim", "ln", "log", "mathrm",
        "mid", "mu", "nabla", "neq", "not", "nu", "omega", "operatorname",
        "overline", "parallel", "phi", "pi", "qquad", "quad", "rho", "right",
        "rightarrow", "sigma", "sin", "sqrt", "subseteq", "sum", "supseteq",
        "tan", "tau", "text", "theta", "times", "to", "vec",
    }
)
_LATEX_WORD_RE = re.compile(r"[A-Za-z]+")


def _strip_outer_fence(value: str) -> str:
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else value


def _escape_string_transport_syntax(value: str) -> str:
    """Normalize only escapes/control characters while inside JSON strings."""

    output: list[str] = []
    in_string = False
    index = 0
    while index < len(value):
        char = value[index]
        if not in_string:
            output.append(char)
            if char == '"':
                in_string = True
            index += 1
            continue

        if char == '"':
            output.append(char)
            in_string = False
            index += 1
            continue
        if char == "\n":
            output.append("\\n")
            index += 1
            continue
        if char == "\r":
            output.append("\\r")
            index += 1
            continue
        if char == "\t":
            output.append("\\t")
            index += 1
            continue
        if char != "\\":
            output.append(char)
            index += 1
            continue

        if index + 1 >= len(value):
            output.append("\\\\")
            index += 1
            continue
        next_char = value[index + 1]
        if next_char in {'"', "\\", "/"}:
            output.extend(("\\", next_char))
            index += 2
            continue
        if next_char == "u" and re.match(r"^[0-9A-Fa-f]{4}$", value[index + 2 : index + 6]):
            output.extend(("\\", "u", value[index + 2 : index + 6]))
            index += 6
            continue

        word_match = _LATEX_WORD_RE.match(value, index + 1)
        word = word_match.group(0).lower() if word_match else ""
        if word in _LATEX_COMMANDS:
            # Raw ``\frac`` in JSON must become ``\\frac`` in the JSON source so
            # the decoded Python string still contains one literal backslash.
            output.append("\\\\")
            index += 1
            continue

        if next_char in "bfnrt":
            # A genuine JSON control escape remains unchanged when it is not the
            # prefix of a known LaTeX command.
            output.extend(("\\", next_char))
            index += 2
            continue

        # Any other JSON-invalid escape (e.g. \%, \,, \() is source Markdown,
        # not license to delete the backslash. Escape the slash itself.
        output.append("\\\\")
        index += 1

    return "".join(output)


def _remove_trailing_json_commas(value: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(value):
        char = value[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == ",":
            cursor = index + 1
            while cursor < len(value) and value[cursor].isspace():
                cursor += 1
            if cursor < len(value) and value[cursor] in "]}":
                index += 1
                continue
        output.append(char)
        index += 1
    return "".join(output)


def decode_structured_json_text(text: str) -> Any:
    """Decode one JSON root after content-preserving lexical normalization."""

    base = _strip_outer_fence(str(text or "").lstrip("\ufeff").strip())
    normalized = _remove_trailing_json_commas(_escape_string_transport_syntax(base))
    variants = [normalized]
    if base != normalized:
        variants.append(base)

    for value in variants:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

    for value in variants:
        start = value.find("{")
        if start < 0:
            continue
        try:
            decoded, end = json.JSONDecoder().raw_decode(value[start:])
        except json.JSONDecodeError:
            continue
        trailing = value[start + end :].strip()
        if trailing in {"", "```"}:
            return decoded
    raise json.JSONDecodeError("structured JSON is internally malformed", base, 0)


__all__ = ["decode_structured_json_text"]
