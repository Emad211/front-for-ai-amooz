"""Robustness of the ``_render_prompt`` (str.replace) renderer — the property
that makes brace-heavy prompt templates safe.

`test_prompt_rendering.py` checks the two happy-path substitutions; the contract
test guards the key/placeholder maps. Neither pins the RENDERER's invariants:

* the literal ``{{blank}}`` cloze token must SURVIVE rendering (the model must
  still see it — the fill-in-the-blank contract with the frontend widget),
* an injected value that itself contains ``{ }`` (JSON/LaTeX) must pass through
  verbatim and never be re-substituted or crash (the whole reason we avoid
  ``str.format``),
* an unprovided token is left untouched — no ``KeyError`` (``str.format`` raises),
* an unbalanced brace in a template does not blow up.

All pure-string, zero-token.
"""
import pytest

from apps.classes.services.quizzes import _render_prompt
from apps.commons.llm_prompts.prompts import PROMPTS

pytestmark = pytest.mark.unit


def test_blank_cloze_token_survives_section_quiz_render():
    """Rendering section_quiz must consume {count}/{section_content} but LEAVE the
    literal {{blank}} — the model needs it to build a fill-in-the-blank item."""
    template = PROMPTS['section_quiz']['default']
    assert '{{blank}}' in template  # precondition: the token is in the source
    rendered = _render_prompt(template, count=5, section_content='body')
    assert '{count}' not in rendered
    assert '{section_content}' not in rendered
    assert '{{blank}}' in rendered  # survived — not consumed by the renderer


def test_value_containing_json_braces_passes_through_verbatim():
    payload = '{"questions": [{"q": 1}]}'
    rendered = _render_prompt('BEGIN {section_content} END', section_content=payload)
    assert rendered == f'BEGIN {payload} END'  # braces intact, no re-substitution


def test_unprovided_token_is_left_untouched():
    # str.format would raise KeyError here; str.replace leaves {b} alone.
    rendered = _render_prompt('{a} and {b}', a='X')
    assert rendered == 'X and {b}'


def test_all_occurrences_of_a_token_are_replaced():
    assert _render_prompt('{x}-{x}-{x}', x='Q') == 'Q-Q-Q'


def test_unbalanced_brace_does_not_raise():
    # A lone '{' would make str.format raise ValueError; str.replace is fine.
    assert _render_prompt('a { b {c}', c='C') == 'a { b C'


def test_no_values_is_identity_passthrough():
    template = 'unchanged {token} text'
    assert _render_prompt(template) == template


def test_non_string_value_is_coerced():
    assert _render_prompt('n={count}', count=12) == 'n=12'
