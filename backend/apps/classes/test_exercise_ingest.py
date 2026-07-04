"""E2 — exercise ingest (structure extraction) with a MOCKED LLM (0 tokens).

Covers ``structure_exercise_markdown`` over the ``generate_structured`` seam:
happy parse, one-shot repair round-trip, raise-not-silent, and the env-only model
selection. The mocked seam is ``apps.chatbot.services.llm_client.generate_text``
(what ``generate_structured`` imports lazily) — no network, no Avalai.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from apps.classes.services import exercise_ingest as ing
from apps.classes.services.schemas import ExerciseStructureOutput

pytestmark = [pytest.mark.unit, pytest.mark.service]

VALID = json.dumps({
    "exercise_title": "تمرین فصل ۲",
    "sections": [
        {"section_id": "s1", "title": "بخش اول", "questions": [
            {"question_id": "s1q1", "question_text_markdown": "۲+۲ چند است؟",
             "question_type": "descriptive", "options": None,
             "points": None, "reference_answer_markdown": None},
        ]},
    ],
})


def _resp(text):
    return SimpleNamespace(text=text, provider="test", model="test-model")


def _patch_llm(monkeypatch, *responses):
    it = iter(responses)
    calls = []

    def fake(*a, **k):
        calls.append(k)
        return next(it)

    monkeypatch.setattr("apps.chatbot.services.llm_client.generate_text", fake)
    return calls


class TestStructureExerciseMarkdown:
    def test_happy_parse_returns_structure(self, monkeypatch):
        monkeypatch.setenv("EXERCISE_STRUCTURE_MODEL", "test-model")
        _patch_llm(monkeypatch, _resp(VALID))

        obj, provider, model = ing.structure_exercise_markdown(ingest_markdown="# src")
        assert obj["exercise_title"] == "تمرین فصل ۲"
        assert obj["sections"][0]["questions"][0]["question_id"] == "s1q1"
        assert model == "test-model"

    def test_repair_round_trip_recovers(self, monkeypatch):
        monkeypatch.setenv("EXERCISE_STRUCTURE_MODEL", "test-model")
        calls = _patch_llm(monkeypatch, _resp("sorry, prose not json"), _resp(VALID))

        obj, _p, _m = ing.structure_exercise_markdown(ingest_markdown="x")
        assert obj["sections"][0]["title"] == "بخش اول"
        assert len(calls) == 2  # primary + one repair

    def test_raises_when_still_malformed_not_silent(self, monkeypatch):
        monkeypatch.setenv("EXERCISE_STRUCTURE_MODEL", "test-model")
        _patch_llm(monkeypatch, _resp("nope"), _resp("still nope"))

        with pytest.raises(RuntimeError):
            ing.structure_exercise_markdown(ingest_markdown="x")

    def test_model_selection_is_env_only_and_raises(self, monkeypatch):
        for var in ("EXERCISE_STRUCTURE_MODEL", "STRUCTURE_MODEL", "MODEL_NAME"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(RuntimeError):
            ing.structure_exercise_markdown(ingest_markdown="x")

    def test_model_selection_prefers_exercise_env(self, monkeypatch):
        monkeypatch.delenv("STRUCTURE_MODEL", raising=False)
        monkeypatch.setenv("EXERCISE_STRUCTURE_MODEL", "exercise-model")
        monkeypatch.setenv("MODEL_NAME", "fallback-model")
        _patch_llm(monkeypatch, _resp(VALID))
        _obj, _p, model = ing.structure_exercise_markdown(ingest_markdown="x")
        assert model == "exercise-model"


class TestExerciseStructureSchema:
    def test_valid_structure_validates(self):
        obj = ExerciseStructureOutput.model_validate(json.loads(VALID))
        assert obj.sections[0].questions[0].question_id == "s1q1"

    def test_sections_default_empty(self):
        obj = ExerciseStructureOutput.model_validate({"exercise_title": "T"})
        assert obj.sections == []

    def test_sections_must_be_a_list(self):
        with pytest.raises(ValidationError):
            ExerciseStructureOutput.model_validate({"sections": {"not": "a list"}})

    def test_extra_keys_allowed(self):
        obj = ExerciseStructureOutput.model_validate({"sections": [], "brand_new": 1})
        assert obj.model_dump().get("brand_new") == 1
