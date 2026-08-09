from __future__ import annotations

from apps.classes.services import exam_prep_mistral_stage4_page_batch as stage4
from apps.classes.services.exam_prep_mistral_page_batch_transcriber import BatchItem, PageBatchResult
from apps.classes.services.exam_prep_mistral_region_transcriber import RegionTranscriptionResult
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _question(number: int):
    return {
        "question_id": f"default-q-{number}",
        "scope_key": "default",
        "section_key": "default",
        "source_question_number": str(number),
        "question_text_markdown": f"سؤال {number}",
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "1",
        "teacher_solution_markdown": "متن خراب 1 2 3",
        "final_answer_markdown": "گزینه 1",
        "issues": ["broken_persian_text"],
        "source_pages": [40],
        "visuals": [
            {
                "id": f"inline-mistral-v1-{number}",
                "role": "solution",
                "reviewOnly": False,
                "sanity": {"status": "passed", "issues": []},
            }
        ],
        "visualSourceContract": {"schemaVersion": 1, "requiredAssetIds": []},
    }


def _result():
    questions = [_question(52), _question(53)]
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "تست", "questions": questions}},
        issues=[],
        question_count=2,
        questions_needing_review=0,
        matched_answer_count=2,
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=True,
    )


def _decision(number: int, *, signals=("symbol_substitution_proxy",), hard=True):
    return RegionRiskDecision(
        question_number=number,
        kind="solution",
        page_number=40,
        bbox=(0.1, 0.1, 0.8, 0.5),
        score=80,
        suspicious=True,
        hard_math=hard,
        signals=tuple(signals),
        region_issues=(),
        candidate_text="متن خراب 1 2 3",
    )


def _item(number: int, text: str):
    return BatchItem(
        target_id=f"s-{number:03d}-p040",
        kind="solution",
        question_number=number,
        question_text_markdown="",
        options=[],
        correct_option_label="3",
        teacher_solution_markdown=text,
        source_visual_required=False,
        visual_type="none",
        transcription_uncertain=False,
        uncertain_fragments=[],
    )


def test_two_corrupted_targets_on_same_page_buy_one_primary_batch(monkeypatch):
    decisions = [_decision(52), _decision(53)]
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: decisions)
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    calls = []

    def fake_batch(**kwargs):
        calls.append(kwargs)
        return PageBatchResult(
            page_number=40,
            model="gemini-3-flash-preview",
            items=(_item(52, "راه حل درست 52 300"), _item(53, "راه حل درست 53 400")),
            request_id="req",
            usage={"inputTokens": 100, "outputTokens": 50, "reasoningTokens": 20, "totalTokens": 170},
            estimated_cost={"unit": 0.001, "irt": 100.0},
        )

    monkeypatch.setattr(stage4, "transcribe_page_batch", fake_batch)
    monkeypatch.setattr(
        stage4,
        "transcribe_source_region",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("secondary must not run")),
    )

    updated, audit = stage4.verify_and_repair_risky_regions_page_batched(
        _result(), pdf_data=b"pdf", layout={}
    )
    assert len(calls) == 1
    assert len(calls[0]["targets"]) == 2
    assert audit["stats"]["pageBatches"] == 1
    assert audit["stats"]["primaryTargets"] == 2
    assert audit["stats"]["secondaryCalls"] == 0
    assert audit["stats"]["repaired"] == 2
    questions = updated.projection["exam_prep"]["questions"]
    assert questions[0]["teacher_solution_markdown"] == "راه حل درست 52 300"
    assert questions[1]["teacher_solution_markdown"] == "راه حل درست 53 400"
    assert questions[0]["visuals"][0]["id"] == "inline-mistral-v1-52"


def test_hard_math_without_proven_corruption_uses_secondary_only_on_numeric_disagreement(monkeypatch):
    decision = _decision(52, signals=("visual_anomaly",), hard=True)
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [decision])
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        stage4,
        "transcribe_page_batch",
        lambda **_kwargs: PageBatchResult(
            page_number=40,
            model="gemini-3-flash-preview",
            items=(_item(52, "راه حل منبع 9 8 7"),),
            request_id="req",
            usage={},
            estimated_cost={},
        ),
    )
    secondary_calls = []

    def fake_secondary(**kwargs):
        secondary_calls.append(kwargs)
        return RegionTranscriptionResult(
            kind="solution",
            question_number=52,
            page_number=40,
            model="gpt-5.4-mini",
            transcript={
                "transcriptionMarkdown": "52- گزینه 3\nراه حل منبع 9 8 7",
                "sourceVisualRequired": False,
                "visualType": "none",
                "transcriptionUncertain": False,
                "uncertainFragments": [],
            },
            response_id="gpt",
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            reasoning_tokens=0,
        )

    monkeypatch.setattr(stage4, "transcribe_source_region", fake_secondary)
    updated, audit = stage4.verify_and_repair_risky_regions_page_batched(
        _result(), pdf_data=b"pdf", layout={}
    )
    assert len(secondary_calls) == 1
    assert audit["stats"]["secondaryCalls"] == 1
    assert audit["stats"]["repaired"] == 1
    assert updated.projection["exam_prep"]["questions"][0]["teacher_solution_markdown"] == "راه حل منبع 9 8 7"


def test_page_batch_failure_marks_all_targets_without_region_retry(monkeypatch):
    decisions = [_decision(52), _decision(53)]
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: decisions)
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    calls = []

    def fail_batch(**_kwargs):
        calls.append(1)
        raise ValueError("bad structured output")

    monkeypatch.setattr(stage4, "transcribe_page_batch", fail_batch)
    updated, audit = stage4.verify_and_repair_risky_regions_page_batched(
        _result(), pdf_data=b"pdf", layout={}
    )
    assert calls == [1]
    assert audit["stats"]["pageBatches"] == 0
    assert audit["stats"]["unresolved"] == 2
    for question in updated.projection["exam_prep"]["questions"]:
        assert "stage4_verification_unresolved" in question["issues"]
