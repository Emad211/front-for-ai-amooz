"""Tests for the canonical robust LLM-JSON extractor (apps.commons.json_utils)."""
import json

import pytest

from apps.commons.json_utils import extract_json_object


pytestmark = pytest.mark.unit


def test_plain_object():
    assert extract_json_object('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_json_wrapped_in_markdown_fence():
    text = 'Here you go:\n```json\n{"a": 1}\n```\nthanks'
    assert extract_json_object(text) == {"a": 1}


def test_inner_code_fences_inside_string_value_are_preserved():
    # The classic bug: JSON whose own string contains ```python ... ``` fences.
    # A non-greedy fence regex truncated it; the greedy regex + balanced scanner
    # must recover the full object and keep the inner fences verbatim.
    inner = "```python\nprint('hi')\n```"
    payload = {"content_markdown": inner}
    text = "```json\n" + json.dumps(payload) + "\n```"
    out = extract_json_object(text)
    assert out["content_markdown"] == inner


def test_raw_control_char_newline_inside_string():
    # A literal (unescaped) newline inside a JSON string is invalid JSON; the
    # repair must escape it so the object parses.
    text = '{"a": "line1\nline2"}'
    out = extract_json_object(text)
    assert out["a"] == "line1\nline2"


def test_invalid_latex_backslash_is_repaired():
    # \c is not a valid JSON escape; LLMs emit LaTeX like \cdot inside strings.
    text = '{"formula": "\\cdot times"}'  # actual text contains a single backslash
    # sanity: this is genuinely invalid JSON as-is
    with pytest.raises(Exception):
        json.loads(text)
    out = extract_json_object(text)
    assert out["formula"] == "\\cdot times"


def test_trailing_comma_removed():
    assert extract_json_object('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}


def test_object_embedded_in_prose():
    text = 'Sure! {"ok": true} <- that is the result.'
    assert extract_json_object(text) == {"ok": True}


def test_array_top_level():
    assert extract_json_object("[1, 2, 3]") == [1, 2, 3]


def test_empty_raises():
    with pytest.raises(ValueError):
        extract_json_object("")


# --- T5 additions: broken-float rejoin, smart-quote normalization, raw-text net


def test_broken_float_across_newline_is_rejoined():
    """A float split by a newline (digit \n .digit) is stitched back together."""
    # tier-1 json.loads fails on the raw newline-split number; the balanced-block
    # path runs _repair_broken_numbers and recovers 12.5.
    assert extract_json_object('{"x": 12\n.5}') == {"x": 12.5}
    assert extract_json_object('{"x": 12.\n5}') == {"x": 12.5}


def test_curly_smart_quotes_are_normalized():
    """Typographic quotes on keys/values are folded to straight quotes before parse."""
    assert extract_json_object('{“a”: “b”}') == {"a": "b"}


def test_raw_text_safety_net_when_fence_would_truncate():
    """A ```-fence whose value itself contains ``` must not truncate the JSON — the
    greedy fence + raw-text tier-3 safety net recovers the whole object."""
    text = (
        'Sure:\n```json\n'
        '{"content_markdown": "```python\nprint(1)\n```", "ok": true}\n'
        '```'
    )
    obj = extract_json_object(text)
    assert obj["ok"] is True
    assert "print(1)" in obj["content_markdown"]
