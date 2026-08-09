from __future__ import annotations

from apps.classes.services import exam_prep_mistral_stage4 as stage4
from apps.classes.services.exam_prep_mistral_region_transcriber import RegionTranscriptionResult
from apps.classes.services.exam_prep_mistral_risk_engine import RegionRiskDecision
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _result(*, text="متن خراب", issues=None, visuals=None):
    question = {
        "question_id": "default-q-1",
        "scope_key": "default",
        "section_key": "default",
        "source_question_number": "1",
        "question_text_markdown": text,
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "2",
        "teacher_solution_markdown": "پاسخ تشریحی",
        "final_answer_markdown": "گزینه 2",
        "confidence": 0.0,
        "issues": list(issues or []),
        "source_pages": [1],
        "visuals": list(visuals or []),
        "visualSourceContract": {"schemaVersion": 1, "requiredAssetIds": []},
    }
    return PageAssemblyResult(
        projection={"exam_prep": {"title": "تست", "questions": [question]}},
        issues=[],
        question_count=1,
        questions_needing_review=0,
        matched_answer_count=1,
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=True,
    )


def _decision(
    *,
    suspicious=True,
    hard_math=False,
    candidate_text="متن خراب\n1) الف\n2) ب\n3) ج\n4) د",
    signals=None,
):
    return RegionRiskDecision(
        question_number=1,
        kind="question",
        page_number=1,
        bbox=(0.1, 0.1, 0.9, 0.7),
        score=70 if suspicious else 10,
        suspicious=suspicious,
        hard_math=hard_math,
        signals=tuple(signals if signals is not None else (("source_corruption",) if suspicious else ())),
        region_issues=(),
        candidate_text=candidate_text,
    )


def _transcript(
    text: str,
    *,
    model="gemini-3-flash-preview",
    uncertain=False,
    source_visual_required=False,
):
    return RegionTranscriptionResult(
        kind="question",
        question_number=1,
        page_number=1,
        model=model,
        transcript={
            "transcriptionMarkdown": text,
            "sourceVisualRequired": source_visual_required,
            "visualType": "diagram" if source_visual_required else "none",
            "transcriptionUncertain": uncertain,
            "uncertainFragments": ["؟"] if uncertain else [],
        },
        response_id="resp",
        input_tokens=10,
        output_tokens=10,
        total_tokens=20,
        reasoning_tokens=0,
    )


def test_clean_region_makes_no_provider_call(monkeypatch):
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [_decision(suspicious=False)])
    monkeypatch.setattr(
        stage4,
        "transcribe_source_region",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("provider must not be called")),
    )

    updated, audit = stage4.verify_and_repair_risky_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        layout={},
    )
    assert audit["stats"]["primaryCalls"] == 0
    assert audit["stats"]["clean"] == 1
    assert updated.projection["exam_prep"]["questions"][0]["question_text_markdown"] == "متن خراب"


def test_non_math_source_repair_preserves_visual_evidence(monkeypatch):
    visual = {
        "id": "inline-mistral-v1-visual",
        "role": "question",
        "reviewOnly": False,
        "sanity": {"status": "passed", "issues": []},
    }
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [_decision()])
    monkeypatch.setattr(stage4, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        stage4,
        "transcribe_source_region",
        lambda **_kwargs: _transcript("صورت درست؟\n1) یک\n2) دو\n3) سه\n4) چهار"),
    )

    updated, audit = stage4.verify_and_repair_risky_regions(
        _result(issues=["broken_persian_text"], visuals=[visual]),
        pdf_data=b"%PDF-fake",
        layout={},
    )
    question = updated.projection["exam_prep"]["questions"][0]
    assert question["question_text_markdown"] == "صورت درست؟"
    assert [item["text_markdown"] for item in question["options"]] == ["یک", "دو", "سه", "چهار"]
    assert question["visuals"] == [visual]
    assert "broken_persian_text" not in question["issues"]
    assert audit["stats"]["repaired"] == 1
    assert audit["stats"]["secondaryCalls"] == 0


def test_non_hard_numeric_disagreement_repairs_from_primary_without_gpt(monkeypatch):
    decision = _decision(
        hard_math=False,
        candidate_text="جرم؟\n1) 10 g\n2) 20 g\n3) 30 g\n4) 40 g",
    )
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [decision])
    monkeypatch.setattr(stage4, "_render_crop", lambda *_args, **_kwargs: b"png")
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs["model"])
        return _transcript("جرم؟\n1) 11 g\n2) 20 g\n3) 30 g\n4) 40 g", model=kwargs["model"])

    monkeypatch.setattr(stage4, "transcribe_source_region", fake_call)
    monkeypatch.setattr(stage4, "primary_model", lambda: "gemini-3-flash-preview")
    monkeypatch.setattr(stage4, "secondary_model", lambda: "gpt-5.4-mini")

    updated, audit = stage4.verify_and_repair_risky_regions(
        _result(), pdf_data=b"%PDF-fake", layout={}
    )
    assert calls == ["gemini-3-flash-preview"]
    assert audit["stats"]["secondaryCalls"] == 0
    assert updated.projection["exam_prep"]["questions"][0]["options"][0]["text_markdown"] == "11 g"


def test_hard_math_disagreement_uses_one_secondary_opinion(monkeypatch):
    decision = _decision(
        hard_math=True,
        candidate_text="مقدار؟\n1) 10\n2) 20\n3) 30\n4) 40",
    )
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [decision])
    monkeypatch.setattr(stage4, "_render_crop", lambda *_args, **_kwargs: b"png")
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs["model"])
        text = "مقدار درست؟\n1) 11\n2) 20\n3) 30\n4) 40"
        return _transcript(text, model=kwargs["model"])

    monkeypatch.setattr(stage4, "transcribe_source_region", fake_call)
    monkeypatch.setattr(stage4, "primary_model", lambda: "gemini-3-flash-preview")
    monkeypatch.setattr(stage4, "secondary_model", lambda: "gpt-5.4-mini")

    _updated, audit = stage4.verify_and_repair_risky_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        layout={},
    )
    assert calls == ["gemini-3-flash-preview", "gpt-5.4-mini"]
    assert audit["stats"]["primaryCalls"] == 1
    assert audit["stats"]["secondaryCalls"] == 1


def test_uncertain_non_math_source_fails_closed_without_paid_second_opinion(monkeypatch):
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [_decision(hard_math=False)])
    monkeypatch.setattr(stage4, "_render_crop", lambda *_args, **_kwargs: b"png")
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs["model"])
        return _transcript("نامشخص", model=kwargs["model"], uncertain=True)

    monkeypatch.setattr(stage4, "transcribe_source_region", fake_call)

    updated, audit = stage4.verify_and_repair_risky_regions(
        _result(),
        pdf_data=b"%PDF-fake",
        layout={},
    )
    question = updated.projection["exam_prep"]["questions"][0]
    assert len(calls) == 1
    assert "stage4_verification_unresolved" in question["issues"]
    assert audit["stats"]["secondaryCalls"] == 0
    assert audit["stats"]["unresolved"] == 1


def test_visual_only_risk_does_not_add_duplicate_stage4_blocker(monkeypatch):
    decision = _decision(
        hard_math=False,
        signals=("visual_anomaly",),
        candidate_text="مطابق شکل پاسخ دهید",
    )
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [decision])
    monkeypatch.setattr(stage4, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        stage4,
        "transcribe_source_region",
        lambda **_kwargs: _transcript(
            "مطابق شکل پاسخ دهید",
            source_visual_required=True,
        ),
    )

    updated, audit = stage4.verify_and_repair_risky_regions(
        _result(issues=["visual_crop_clipped"]),
        pdf_data=b"%PDF-fake",
        layout={},
    )
    question = updated.projection["exam_prep"]["questions"][0]
    assert "stage4_verification_unresolved" not in question["issues"]
    assert audit["stats"]["unresolved"] == 0


def test_stage4_metadata_contains_policy_but_not_provider_transcription(monkeypatch):
    monkeypatch.setattr(stage4, "score_region_risks", lambda **_kwargs: [_decision()])
    monkeypatch.setattr(stage4, "_render_crop", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(
        stage4,
        "transcribe_source_region",
        lambda **_kwargs: _transcript("صورت درست؟\n1) یک\n2) دو\n3) سه\n4) چهار"),
    )
    updated, audit = stage4.verify_and_repair_risky_regions(
        _result(), pdf_data=b"%PDF-fake", layout={}
    )
    assert audit["policy"]["candidateMistralShown"] is False
    assert audit["policy"]["oneRegionOneImageOneCall"] is True
    assert audit["policy"]["secondaryOnlyForHardMath"] is True
    assert audit["policy"]["modelConfidenceAuthority"] is False
    assert audit["policy"]["visualEvidenceMutableByVerifier"] is False
    serialized = str(updated.projection["exam_prep"]["questions"][0].get("stage4_verification"))
    assert "transcriptionMarkdown" not in serialized
