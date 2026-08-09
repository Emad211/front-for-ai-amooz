from __future__ import annotations

from apps.classes.services import exam_prep_mistral_stage4_runtime as runtime
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _result(question):
    return PageAssemblyResult(
        projection={"exam_prep": {"questions": [question]}},
        issues=[],
        question_count=1,
        questions_needing_review=1,
        matched_answer_count=1,
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=False,
    )


def _visual():
    return {
        "id": "inline-mistral-v1-source-p1-q1-question-1-deadbeef",
        "role": "question",
        "optionLabel": None,
        "sourcePage": 1,
        "sourceBBox": {"x0": 0.2, "y0": 0.2, "x1": 0.7, "y1": 0.6},
        "storagePath": "exam-prep/source/visuals/v1/source/p001-q001-question-01-deadbeef.png",
        "visualMode": "single_question",
        "reviewOnly": False,
        "sanity": {"status": "passed", "issues": []},
    }


def _question(*, visual=None, issues=None):
    values = [visual] if visual is not None else []
    return {
        "question_id": "default-q-1",
        "source_question_number": "1",
        "question_text_markdown": "مطابق شکل پاسخ دهید.",
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "1",
        "teacher_solution_markdown": "راه حل",
        "visuals": values,
        "visualSourceContract": (
            {
                "schemaVersion": 1,
                "requiredAssetIds": [visual["id"]],
                "roleCounts": {"question": 1, "option": 0, "solution": 0},
                "optionLabels": [],
                "groupedOptionLabels": [],
                "sourcePages": [1],
            }
            if visual is not None
            else None
        ),
        "issues": list(issues or []),
    }


def test_healthy_stage3_visual_drops_stale_visual_requirement():
    visual = _visual()
    updated = runtime._restore_visual_authority(
        _result(_question(visual=visual, issues=["visual_evidence_required"]))
    )
    assert "visual_evidence_required" not in updated.projection["exam_prep"]["questions"][0]["issues"]


def test_review_only_visual_does_not_hide_visual_blocker():
    visual = _visual()
    visual["reviewOnly"] = True
    visual["sanity"] = {"status": "needs_review", "issues": ["visual_crop_clipped"]}
    updated = runtime._restore_visual_authority(
        _result(
            _question(
                visual=visual,
                issues=["visual_evidence_required", "visual_crop_clipped"],
            )
        )
    )
    issues = updated.projection["exam_prep"]["questions"][0]["issues"]
    assert "visual_evidence_required" in issues
    assert "visual_crop_clipped" in issues


def test_one_failed_region_keeps_question_blocked_even_if_other_region_succeeded():
    question = _question(issues=[])
    audit = {
        "regions": [
            {
                "questionNumber": 1,
                "kind": "question",
                "status": "source_uncertain",
            },
            {
                "questionNumber": 1,
                "kind": "solution",
                "status": "repaired_primary",
            },
        ]
    }
    updated = runtime._restore_authority(_result(question), audit=audit)
    assert "stage4_verification_unresolved" in updated.projection["exam_prep"]["questions"][0]["issues"]


def test_all_resolved_regions_remove_stale_stage4_blocker():
    question = _question(issues=["stage4_verification_unresolved"])
    audit = {
        "regions": [
            {"questionNumber": 1, "kind": "question", "status": "verified_primary_agreement"},
            {"questionNumber": 1, "kind": "solution", "status": "repaired_primary"},
        ]
    }
    updated = runtime._restore_authority(_result(question), audit=audit)
    assert "stage4_verification_unresolved" not in updated.projection["exam_prep"]["questions"][0]["issues"]
