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


def test_extract_json_object_handles_inner_markdown_code_fences():
    # Reproduces the production failure: a ```json-wrapped object whose own
    # string value contains a markdown ```python code fence. A non-greedy
    # outer-fence regex truncates here, yielding "no JSON object/array found".
    raw = (
        "```json\n"
        "{\n"
        '  "title": "RAG lesson",\n'
        '  "content_markdown": "Here is code:\\n```python\\nx = 1\\nprint(x)\\n```\\nDone."\n'
        "}\n"
        "```"
    )
    obj = extract_json_object(raw)
    assert obj["title"] == "RAG lesson"
    assert "```python" in obj["content_markdown"]
    assert "print(x)" in obj["content_markdown"]


def test_extract_json_object_handles_trailing_fence_junk():
    # Some models append a stray quoted fence after the real closing fence.
    raw = '```json\n{"a": 1}\n```\n"```"'
    obj = extract_json_object(raw)
    assert obj["a"] == 1


def test_extract_json_object_drops_overescaped_single_quotes():
    # The model over-escapes single quotes (\') which is invalid JSON.
    raw = "{\"summary\": \"\\'chain\\' and \\'RAG\\'\"}"
    obj = extract_json_object(raw)
    assert obj["summary"] == "'chain' and 'RAG'"
