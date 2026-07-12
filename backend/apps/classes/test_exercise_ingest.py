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
    "questions": [
        {"question_id": "q1", "question_text_markdown": "۲+۲ چند است؟",
         "question_type": "descriptive", "options": None,
         "points": None, "reference_answer_markdown": None},
    ],
})

REFERENCE_VALID = json.dumps({
    "mode_detected": "numbered_answers",
    "items": [
        {
            "item_id": "i1",
            "question_number": 1,
            "question_text_markdown": None,
            "question_type": None,
            "options": None,
            "points": 2,
            "reference_answer_markdown": "پاسخ مرجع ۱",
            "confidence": 0.91,
            "notes": "شماره سوال واضح است.",
        }
    ],
    "warnings": [],
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
        assert obj["questions"][0]["question_id"] == "q1"
        assert model == "test-model"

    def test_repair_round_trip_recovers(self, monkeypatch):
        monkeypatch.setenv("EXERCISE_STRUCTURE_MODEL", "test-model")
        calls = _patch_llm(monkeypatch, _resp("sorry, prose not json"), _resp(VALID))

        obj, _p, _m = ing.structure_exercise_markdown(ingest_markdown="x")
        assert obj["questions"][0]["question_text_markdown"] == "۲+۲ چند است؟"
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
        assert obj.questions[0].question_id == "q1"

    def test_questions_default_empty(self):
        obj = ExerciseStructureOutput.model_validate({"exercise_title": "T"})
        assert obj.questions == []

    def test_questions_must_be_a_list(self):
        with pytest.raises(ValidationError):
            ExerciseStructureOutput.model_validate({"questions": {"not": "a list"}})

    def test_legacy_sections_remain_valid_during_compatibility_window(self):
        obj = ExerciseStructureOutput.model_validate({
            "sections": [{"title": "قدیمی", "questions": [{"question_id": "old-q"}]}],
        })
        assert obj.sections[0].questions[0].question_id == "old-q"

    def test_extra_keys_allowed(self):
        obj = ExerciseStructureOutput.model_validate({"questions": [], "brand_new": 1})
        assert obj.model_dump().get("brand_new") == 1


class TestReferenceIngestMarkdown:
    def test_reference_ingest_happy_parse(self, monkeypatch):
        monkeypatch.setenv("EXERCISE_REFERENCE_INGEST_MODEL", "reference-model")
        _patch_llm(monkeypatch, _resp(REFERENCE_VALID))

        obj, _provider, model = ing.ingest_reference_answers_markdown(
            source_markdown="۱) پاسخ مرجع ۱",
            existing_questions=[{"id": 10, "number": 1, "question_markdown": "سوال"}],
            mode_hint="numbered_answers",
        )
        assert model == "reference-model"
        assert obj["mode_detected"] == "numbered_answers"
        assert obj["items"][0]["reference_answer_markdown"] == "پاسخ مرجع ۱"

    def test_reference_ingest_repair_round_trip(self, monkeypatch):
        monkeypatch.setenv("EXERCISE_REFERENCE_INGEST_MODEL", "reference-model")
        calls = _patch_llm(monkeypatch, _resp("not json"), _resp(REFERENCE_VALID))

        obj, _provider, _model = ing.ingest_reference_answers_markdown(
            source_markdown="x",
            existing_questions=[],
            mode_hint="auto",
        )
        assert obj["items"][0]["question_number"] == 1
        assert len(calls) == 2

    def test_reference_ingest_env_only(self, monkeypatch):
        for var in (
            "EXERCISE_REFERENCE_INGEST_MODEL",
            "EXERCISE_STRUCTURE_MODEL",
            "STRUCTURE_MODEL",
            "MODEL_NAME",
        ):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(RuntimeError):
            ing.ingest_reference_answers_markdown(
                source_markdown="x",
                existing_questions=[],
                mode_hint="auto",
            )
