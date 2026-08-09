from __future__ import annotations

from apps.classes.services import exam_prep_mistral_stage4_page_batch as stage4
from apps.classes.services.exam_prep_mistral_page_batch_transcriber import (
    BatchItem,
    BatchOption,
    BatchUncertainSpan,
    PageBatchEnvelopeError,
    PageBatchResult,
)
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


def _result(questions=None):
    questions = questions or [_question(52), _question(53)]
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "تست", "questions": questions}},
        issues=[],
        question_count=len(questions),
        questions_needing_review=0,
        matched_answer_count=len(questions),
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=True,
    )


def _decision(number: int, *, signals=("symbol_substitution_proxy",), hard=True, kind="solution", issues=()):
    return RegionRiskDecision(
        question_number=number,
        kind=kind,
        page_number=40,
        bbox=(0.1, 0.1, 0.8, 0.5),
        score=80,
        suspicious=True,
        hard_math=hard,
        signals=tuple(signals),
        region_issues=tuple(issues),
        candidate_text="متن خراب 1 2 3",
    )


def _item(number: int, text: str, *, uncertain_spans=()):
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
        transcription_uncertain=bool(uncertain_spans),
        uncertain_spans=list(uncertain_spans),
        uncertain_fragments=[],
    )


def _batch(*items, missing=(), invalid=()):
    return PageBatchResult(
        page_number=40,
        model="gemini-3-flash-preview",
        items=tuple(items),
        request_id="req",
        usage={"inputTokens": 100, "outputTokens": 50, "reasoningTokens": 0, "totalTokens": 150},
        estimated_cost={"unit": 0.001, "irt": 100.0},
        requested_target_ids=tuple(item.target_id for item in items) + tuple(missing) + tuple(invalid),
        missing_target_ids=tuple(missing),
        invalid_target_ids=tuple(invalid),
    )


def test_two_corrupted_targets_on_same_page_buy_one_primary_batch(monkeypatch):
    decisions = [_decision(52), _decision(53)]
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: decisions)
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    calls = []

    def fake_batch(**kwargs):
        calls.append(kwargs)
        return _batch(_item(52, "راه حل درست 52 300"), _item(53, "راه حل درست 53 400"))

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
    assert audit["stats"]["primaryCalls"] == 1
    assert audit["stats"]["secondaryCalls"] == 0
    assert audit["stats"]["repaired"] == 2
    questions = updated.projection["exam_prep"]["questions"]
    assert questions[0]["teacher_solution_markdown"] == "راه حل درست 52 300"
    assert questions[1]["teacher_solution_markdown"] == "راه حل درست 53 400"
    assert questions[0]["visuals"][0]["id"] == "inline-mistral-v1-52"


def test_partial_batch_commits_valid_sibling_and_blocks_missing_item(monkeypatch):
    decisions = [_decision(52), _decision(53)]
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: decisions)
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        stage4,
        "transcribe_page_batch",
        lambda **_kwargs: _batch(_item(52, "راه حل درست 52"), missing=("s-053-p040",)),
    )

    updated, audit = stage4.verify_and_repair_risky_regions_page_batched(
        _result(), pdf_data=b"pdf", layout={}
    )
    questions = updated.projection["exam_prep"]["questions"]
    assert questions[0]["teacher_solution_markdown"] == "راه حل درست 52"
    assert "stage4_verification_unresolved" in questions[1]["issues"]
    assert audit["stats"]["primaryCalls"] == 1
    assert audit["stats"]["unresolved"] == 1


def test_whole_envelope_failure_splits_once_and_never_recurses(monkeypatch):
    decisions = [_decision(52), _decision(53)]
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: decisions)
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    calls = []

    def fake_batch(**kwargs):
        calls.append([decision.target_id for decision, _ in kwargs["targets"]])
        if len(kwargs["targets"]) > 1:
            raise PageBatchEnvelopeError("structured_json_invalid")
        decision = kwargs["targets"][0][0]
        return _batch(_item(decision.question_number, f"راه حل درست {decision.question_number}"))

    monkeypatch.setattr(stage4, "transcribe_page_batch", fake_batch)
    updated, audit = stage4.verify_and_repair_risky_regions_page_batched(
        _result(), pdf_data=b"pdf", layout={}
    )
    assert len(calls) == 3
    assert len(calls[0]) == 2
    assert all(len(value) == 1 for value in calls[1:])
    assert audit["stats"]["primaryCalls"] == 3
    assert audit["stats"]["splitCalls"] == 2
    assert audit["stats"]["unresolved"] == 0
    assert all(
        "stage4_verification_unresolved" not in q["issues"]
        for q in updated.projection["exam_prep"]["questions"]
    )


def test_order_only_numeric_difference_does_not_buy_secondary(monkeypatch):
    question = _question(52)
    question["teacher_solution_markdown"] = "x=2 و y=3"
    question["issues"] = []
    decision = _decision(52, signals=("visual_anomaly",), hard=True)
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [decision])
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        stage4,
        "transcribe_page_batch",
        lambda **_kwargs: _batch(_item(52, "y=3 و x=2")),
    )
    monkeypatch.setattr(
        stage4,
        "transcribe_source_region",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("secondary must not run")),
    )

    _updated, audit = stage4.verify_and_repair_risky_regions_page_batched(
        _result([question]), pdf_data=b"pdf", layout={}
    )
    assert audit["stats"]["secondaryCalls"] == 0
    assert audit["regions"][0]["status"].startswith("verified")


def test_hard_field_conflict_uses_secondary_and_repairs_only_on_field_consensus(monkeypatch):
    decision = _decision(52, signals=("visual_anomaly",), hard=True)
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [decision])
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        stage4,
        "transcribe_page_batch",
        lambda **_kwargs: _batch(_item(52, "راه حل منبع 9 8 7")),
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
                "transcriptionMarkdown": "52- گزینه 3\nراه حل منبع 7 9 8",
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


def test_uncertain_required_field_is_not_repaired(monkeypatch):
    decision = _decision(52)
    span = BatchUncertainSpan(
        field="teacher_solution_markdown",
        fragment="□",
        reason="unreadable_glyph",
    )
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [decision])
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        stage4,
        "transcribe_page_batch",
        lambda **_kwargs: _batch(_item(52, "راه حل [?]", uncertain_spans=(span,))),
    )

    updated, audit = stage4.verify_and_repair_risky_regions_page_batched(
        _result(), pdf_data=b"pdf", layout={}
    )
    q = updated.projection["exam_prep"]["questions"][0]
    assert q["teacher_solution_markdown"] == "متن خراب 1 2 3"
    assert "stage4_verification_unresolved" in q["issues"]
    assert audit["regions"][0]["status"] == "source_uncertain"


def test_sanitizer_removes_fake_visual_url_and_page_metadata_before_repair(monkeypatch):
    decision = _decision(52)
    text = "راه حل واقعی\n![](https://extracted-image-link)\n(فیزیک ۳، صفحه‌های ۴۰ تا ۴۵)"
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [decision])
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(stage4, "transcribe_page_batch", lambda **_kwargs: _batch(_item(52, text)))

    updated, audit = stage4.verify_and_repair_risky_regions_page_batched(
        _result(), pdf_data=b"pdf", layout={}
    )
    body = updated.projection["exam_prep"]["questions"][0]["teacher_solution_markdown"]
    assert body == "راه حل واقعی"
    assert "https://" not in body
    assert "صفحه" not in body
    assert audit["regions"][0]["sanitizerFlags"]


def test_option_only_repair_preserves_existing_stem(monkeypatch):
    question = _question(52)
    question["question_text_markdown"] = "صورت سؤال سالم"
    question["options"] = []
    question["issues"] = ["mistral_question_option_parse_failed"]
    decision = _decision(
        52,
        kind="question",
        signals=("ocr_disagreement",),
        hard=False,
        issues=("mistral_question_option_parse_failed",),
    )
    primary = BatchItem(
        target_id="q-052-p040",
        kind="question",
        question_number=52,
        question_text_markdown="صورت سؤال تغییر یافته",
        options=[BatchOption(label=str(i), text_markdown=f"گزینه {i}") for i in range(1, 5)],
        correct_option_label="",
        teacher_solution_markdown="",
        source_visual_required=False,
        visual_type="none",
        transcription_uncertain=False,
        uncertain_spans=[],
        uncertain_fragments=[],
    )
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [decision])
    monkeypatch.setattr(stage4.legacy, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(stage4, "transcribe_page_batch", lambda **_kwargs: _batch(primary))

    updated, audit = stage4.verify_and_repair_risky_regions_page_batched(
        _result([question]), pdf_data=b"pdf", layout={}
    )
    q = updated.projection["exam_prep"]["questions"][0]
    assert q["question_text_markdown"] == "صورت سؤال سالم"
    assert [item["text_markdown"] for item in q["options"]] == [
        "گزینه 1",
        "گزینه 2",
        "گزینه 3",
        "گزینه 4",
    ]
    assert audit["stats"]["repaired"] == 1
