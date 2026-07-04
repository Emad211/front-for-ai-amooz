"""Pipeline service parsing: structured-output happy path + repair round-trip +
raise-not-silent — with a fully MOCKED LLM (module-bound `generate_text` seam,
zero tokens, never touches Avalai).

Two distinct parse contracts are exercised:
* ``structure.structure_transcript_markdown`` — ``validate_keep_dict`` (shape-checked
  but keeps the model's exact dict) with a genuine one-shot **repair round-trip**
  (`json_repair` re-ask) and a **raise** on still-bad (never a silent ``{}``);
* ``quizzes.generate_section_quiz_questions`` — ``extract_json_object`` which pulls
  JSON out of prose but **raises** (wrapped in RuntimeError) on true garbage.

Each test patches the module-bound ``generate_text`` so no network/model is hit;
``side_effect`` drives the multi-call repair path.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from apps.classes.services import structure as structure_mod
from apps.classes.services import quizzes as quizzes_mod

pytestmark = [pytest.mark.unit, pytest.mark.service]


def _resp(text: str):
    return SimpleNamespace(text=text, provider='test', model='test-model')


VALID_STRUCTURE = json.dumps({
    'root_object': {'title': 'Algebra'},
    'outline': [
        {'id': 's1', 'title': 'Section 1', 'units': [
            {'id': 'u1', 'title': 'Unit 1'},
        ]},
    ],
})

VALID_QUIZ = json.dumps({
    'questions': [
        {'question': 'q1', 'options': ['a', 'b'], 'correct_answer': 'a', 'difficulty': 'easy'},
    ],
})


class TestStructureService:
    def test_happy_parse_preserves_the_models_dict(self, monkeypatch):
        monkeypatch.setenv('STRUCTURE_MODEL', 'test-model')
        calls = []

        def fake(*a, **k):
            calls.append(k)
            return _resp(VALID_STRUCTURE)

        monkeypatch.setattr(structure_mod, 'generate_text', fake)

        obj, provider, model = structure_mod.structure_transcript_markdown(
            transcript_markdown='# lecture',
        )
        assert obj['root_object']['title'] == 'Algebra'
        assert obj['outline'][0]['units'][0]['id'] == 'u1'  # exact dict kept
        assert model == 'test-model'
        assert len(calls) == 1  # no repair needed

    def test_repair_round_trip_recovers_from_malformed_primary(self, monkeypatch):
        monkeypatch.setenv('STRUCTURE_MODEL', 'test-model')
        responses = iter([_resp('sorry, here is prose not json'), _resp(VALID_STRUCTURE)])
        seen = []

        def fake(*a, **k):
            seen.append(1)
            return next(responses)

        monkeypatch.setattr(structure_mod, 'generate_text', fake)

        obj, _p, _m = structure_mod.structure_transcript_markdown(transcript_markdown='x')
        assert obj['outline'][0]['title'] == 'Section 1'
        assert len(seen) == 2  # primary + one repair re-ask

    def test_raises_when_repair_still_malformed_not_silent_empty(self, monkeypatch):
        monkeypatch.setenv('STRUCTURE_MODEL', 'test-model')
        seen = []

        def fake(*a, **k):
            seen.append(1)
            return _resp('still not json')

        monkeypatch.setattr(structure_mod, 'generate_text', fake)

        with pytest.raises(RuntimeError):
            structure_mod.structure_transcript_markdown(transcript_markdown='x')
        assert len(seen) == 2  # tried primary + repair, then raised (no silent {})


class TestQuizService:
    def test_happy_parse_returns_questions(self, monkeypatch):
        monkeypatch.setenv('QUIZ_MODEL', 'test-model')
        monkeypatch.setattr(quizzes_mod, 'generate_text', lambda *a, **k: _resp(VALID_QUIZ))

        obj, provider, model = quizzes_mod.generate_section_quiz_questions(
            section_content='body', count=1,
        )
        assert isinstance(obj['questions'], list)
        assert obj['questions'][0]['correct_answer'] == 'a'
        assert model == 'test-model'

    def test_extracts_json_embedded_in_prose(self, monkeypatch):
        monkeypatch.setenv('QUIZ_MODEL', 'test-model')
        wrapped = f'Sure! Here you go:\n```json\n{VALID_QUIZ}\n```\nHope that helps.'
        monkeypatch.setattr(quizzes_mod, 'generate_text', lambda *a, **k: _resp(wrapped))

        obj, _p, _m = quizzes_mod.generate_section_quiz_questions(section_content='b', count=1)
        assert obj['questions'][0]['question'] == 'q1'  # dug out of the prose

    def test_raises_on_garbage_not_silent_empty(self, monkeypatch):
        monkeypatch.setenv('QUIZ_MODEL', 'test-model')
        monkeypatch.setattr(quizzes_mod, 'generate_text', lambda *a, **k: _resp('total nonsense'))

        with pytest.raises(RuntimeError):
            quizzes_mod.generate_section_quiz_questions(section_content='b', count=1)
