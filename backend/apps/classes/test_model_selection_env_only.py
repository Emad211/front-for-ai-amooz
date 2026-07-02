"""Regression: LLM model names come from ENV only — never a hardcoded default.

CLAUDE.md rule: "Never hardcode model names or keys." Two pipeline stages had a
trailing hardcoded model fallback that would silently call a specific model on a
misconfigured deployment instead of failing loudly:
  * exam_prep_structure._select_model  → used ``or "gpt-4.1"``
  * pdf_extraction._select_vision_model → used ``or "gemini-2.5-flash"``
Both now RAISE when no model env var is set. These pure, zero-token tests lock
that in (env precedence + the raise).
"""
import pytest

from apps.classes.services.exam_prep_structure import _select_model
from apps.classes.services.pdf_extraction import _select_vision_model

pytestmark = pytest.mark.unit

# Every env var either helper consults — cleared for the "raise" cases.
_MODEL_ENV_VARS = [
    "STRUCTURE_MODEL",
    "REWRITE_MODEL",
    "MODEL_NAME",
    "PDF_VISION_MODEL",
    "TRANSCRIPTION_MODEL",
]


def _clear_model_env(monkeypatch):
    for var in _MODEL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# --- exam_prep_structure._select_model ---------------------------------------

def test_exam_prep_select_model_raises_when_no_env(monkeypatch):
    _clear_model_env(monkeypatch)
    with pytest.raises(RuntimeError):
        _select_model("STRUCTURE_MODEL", "REWRITE_MODEL")


def test_exam_prep_select_model_prefers_first_env(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("STRUCTURE_MODEL", "my-structure-model")
    monkeypatch.setenv("MODEL_NAME", "generic-model")
    assert _select_model("STRUCTURE_MODEL", "REWRITE_MODEL") == "my-structure-model"


def test_exam_prep_select_model_falls_back_to_model_name(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("MODEL_NAME", "generic-model")
    assert _select_model("STRUCTURE_MODEL", "REWRITE_MODEL") == "generic-model"


# --- pdf_extraction._select_vision_model -------------------------------------

def test_pdf_vision_model_raises_when_no_env(monkeypatch):
    _clear_model_env(monkeypatch)
    with pytest.raises(RuntimeError):
        _select_vision_model()


def test_pdf_vision_model_prefers_pdf_vision_env(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("PDF_VISION_MODEL", "vision-model")
    monkeypatch.setenv("MODEL_NAME", "generic-model")
    assert _select_vision_model() == "vision-model"


def test_pdf_vision_model_falls_back_through_chain(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("TRANSCRIPTION_MODEL", "transcription-model")
    assert _select_vision_model() == "transcription-model"
