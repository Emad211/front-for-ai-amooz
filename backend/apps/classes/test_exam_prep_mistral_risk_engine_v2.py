from __future__ import annotations

from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision
from apps.classes.services import exam_prep_mistral_risk_engine_v2 as risk


def _question(*, number=1, text="متن سؤال", solution="راه حل", issues=None):
    return {
        "question_id": f"default-q-{number}",
        "source_question_number": str(number),
        "question_text_markdown": text,
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "1",
        "teacher_solution_markdown": solution,
        "issues": list(issues or []),
    }


def _decision(*, kind="solution", number=1, page=2, score=45, hard_math=True, signals=(), text=""):
    return RegionRiskDecision(
        question_number=number,
        kind=kind,
        page_number=page,
        bbox=(0.1, 0.1, 0.8, 0.5),
        score=score,
        suspicious=True,
        hard_math=hard_math,
        signals=tuple(signals),
        region_issues=(),
        candidate_text=text,
    )


def test_ordinary_formula_science_does_not_trigger_provider(monkeypatch):
    monkeypatch.setattr(
        risk.base,
        "score_region_risks",
        lambda **_kwargs: [
            _decision(
                signals=("formula_math", "digits_units", "scientific_terminology"),
                text=r"F=ma و v^2=2ax با واحد m/s",
            )
        ],
    )
    projection = {"exam_prep": {"questions": [_question(solution="F=ma") ]}}
    layout = {"pages": [{"originalPageNumber": 2, "pageRole": "solution"}]}
    [item] = risk.score_region_risks(projection=projection, layout=layout)
    assert item.score < 50
    assert item.suspicious is False
    assert item.hard_math is True


def test_repeated_tau_gamma_solution_is_source_corruption_proxy(monkeypatch):
    monkeypatch.setattr(
        risk.base,
        "score_region_risks",
        lambda **_kwargs: [
            _decision(
                signals=("formula_math", "scientific_terminology"),
                text=r"x^\gamma=\gamma y^\gamma و سپس \gamma y=2",
            )
        ],
    )
    projection = {"exam_prep": {"questions": [_question(text="هندسه", solution="x") ]}}
    layout = {"pages": [{"originalPageNumber": 2, "pageRole": "solution"}]}
    [item] = risk.score_region_risks(projection=projection, layout=layout)
    assert item.suspicious is True
    assert "symbol_substitution_proxy" in item.signals


def test_pathological_numeric_persian_repetition_is_suspicious(monkeypatch):
    repeated = " ".join(["۲-۲ ذره"] * 20)
    monkeypatch.setattr(
        risk.base,
        "score_region_risks",
        lambda **_kwargs: [_decision(hard_math=False, signals=("scientific_terminology",), text=repeated)],
    )
    projection = {"exam_prep": {"questions": [_question(solution=repeated)]}}
    layout = {"pages": [{"originalPageNumber": 2, "pageRole": "solution"}]}
    [item] = risk.score_region_risks(projection=projection, layout=layout)
    assert item.suspicious is True
    assert "pathological_repetition" in item.signals


def test_fake_question_region_on_solution_page_is_removed(monkeypatch):
    monkeypatch.setattr(
        risk.base,
        "score_region_risks",
        lambda **_kwargs: [_decision(kind="question", page=33, hard_math=False, signals=("heading_conflict",))],
    )
    projection = {"exam_prep": {"questions": [_question()]}}
    layout = {"pages": [{"originalPageNumber": 33, "pageRole": "solution"}]}
    assert risk.score_region_risks(projection=projection, layout=layout) == []


def test_duplicate_target_id_buys_only_one_call(monkeypatch):
    first = _decision(page=2, signals=("heading_conflict",), hard_math=False)
    second = RegionRiskDecision(
        question_number=1,
        kind="solution",
        page_number=2,
        bbox=(0.1, 0.1, 0.9, 0.7),
        score=85,
        suspicious=True,
        hard_math=False,
        signals=("heading_conflict",),
        region_issues=("duplicate",),
        candidate_text="راه حل دوم",
    )
    monkeypatch.setattr(risk.base, "score_region_risks", lambda **_kwargs: [first, second])
    projection = {"exam_prep": {"questions": [_question()]}}
    layout = {"pages": [{"originalPageNumber": 2, "pageRole": "solution"}]}
    result = risk.score_region_risks(projection=projection, layout=layout)
    assert len(result) == 1
    assert result[0].bbox == second.bbox
