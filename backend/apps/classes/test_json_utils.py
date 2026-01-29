from apps.classes.services.json_utils import extract_json_object


def test_extract_json_object_repairs_invalid_backslash_escape_in_strings():
    # JSON that contains LaTeX-like sequences is commonly emitted by LLMs.
    # "\c" is not a valid JSON escape, so this would normally raise.
    raw = '{"a": "\\cdot", "b": "x\\alpha y"}'
    obj = extract_json_object(raw)
    assert obj["a"] == "\\cdot"
    assert obj["b"] == "x\\alpha y"


def test_extract_json_object_handles_code_fences_and_trailing_commas():
    raw = """```json
    {
      \"a\": 1,
      \"b\": [2,3,],
    }
    ```"""
    obj = extract_json_object(raw)
    assert obj["a"] == 1
    assert obj["b"] == [2, 3]
