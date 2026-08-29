from __future__ import annotations

from apps.classes.services.exam_prep_mistral_visual_review import (
    visual_metadata_issue_codes,
)
from apps.classes.services.exam_prep_page_review import audit_page_first_projection


def _asset(**overrides):
    value = {
        "id": "inline-mistral-v1-source-p1-q1-question-1-deadbeef",
        "role": "question",
        "optionLabel": None,
        "selectedVariant": "source",
        "sourcePage": 1,
        "sourceBBox": {"x0": 0.2, "y0": 0.2, "x1": 0.6, "y1": 0.5},
        "storagePath": "exam-prep/source/visuals/v1/source/p001-q001-question-01-deadbeef.png",
        "visualMode": "single_question",
        "reviewOnly": False,
        "sanity": {"status": "passed", "issues": []},
    }
    value.update(overrides)
    return value


def _contract(visuals):
    return {
        "schemaVersion": 1,
        "requiredAssetIds": [str(item.get("id") or "") for item in visuals],
        "roleCounts": {
            role: sum(str(item.get("role") or "") == role for item in visuals)
            for role in ("question", "option", "solution")
        },
        "optionLabels": sorted(
            {
                str(item.get("optionLabel") or "")
                for item in visuals
                if item.get("role") == "option"
                and str(item.get("optionLabel") or "") in {"1", "2", "3", "4"}
            }
        ),
        "groupedOptionLabels": sorted(
            {
                str(value)
                for item in visuals
                if item.get("visualMode") == "grouped_options"
                for value in (item.get("groupedOptionLabels") or [])
            }
        ),
        "sourcePages": sorted({int(item.get("sourcePage") or 0) for item in visuals}),
        "fingerprint": "test",
    }


def _question(visuals, *, issues=None, contract=None):
    value = {
        "question_id": "default-q-1",
        "scope_key": "default",
        "source_question_number": "1",
        "source_pages": [1],
        "question_text_markdown": "مطابق شکل پاسخ دهید.",
        "options": [
            {"label": "1", "text_markdown": "الف"},
            {"label": "2", "text_markdown": "ب"},
            {"label": "3", "text_markdown": "ج"},
            {"label": "4", "text_markdown": "د"},
        ],
        "correct_option_label": "1",
        "teacher_solution_markdown": "این یک راه حل تشریحی معتبر و کافی برای تست است.",
        "final_answer_markdown": "گزینه 1",
        "visuals": visuals,
        "issues": list(issues or []),
    }
    value["visualSourceContract"] = _contract(visuals) if contract is None else contract
    return value


def _projection(question):
    return {"exam_prep": {"title": "تست", "questions": [question]}}


def test_clean_stage3_visual_derives_no_visual_blocker():
    assert visual_metadata_issue_codes(_question([_asset()])) == []


def test_review_only_visual_remains_critical_even_if_question_issue_list_was_removed():
    question = _question(
        [
            _asset(
                reviewOnly=True,
                sanity={
                    "status": "needs_review",
                    "issues": ["visual_crop_clipped"],
                },
            )
        ],
        issues=[],
    )
    audit = audit_page_first_projection(_projection(question))
    matching = [
        issue
        for issue in audit["issues"]
        if issue["code"] == "visual_crop_clipped"
    ]
    assert matching
    # Owner policy: the clipped-crop blocker is re-derived from immutable metadata and
    # surfaced as a *critical advisory*, but it does not force the review lane (forced
    # review = only no-stem / no-options). Visual publish-safety is enforced separately
    # at the publish gate (anti-forgery artifact check), not via the audit status.
    assert matching[0]["severity"] == "critical"
    assert audit["status"] == "passed"


def test_whole_page_fallback_surfaces_critical_advisory_without_forcing_review():
    question = _question(
        [
            _asset(
                visualMode="whole_page_review_fallback",
                reviewOnly=False,
                sanity={"status": "passed", "issues": []},
                sourceBBox={"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
            )
        ]
    )
    codes = visual_metadata_issue_codes(question)
    assert "visual_precise_crop_unresolved" in codes
    # Tampered whole-page fallback is still detected from metadata and flagged as a
    # critical advisory, but under owner policy it is not a review blocker (the question
    # has a stem and four options). Publish-time anti-forgery lives in the publish gate.
    audit = audit_page_first_projection(_projection(question))
    matching = [
        issue
        for issue in audit["issues"]
        if issue["code"] == "visual_precise_crop_unresolved"
    ]
    assert matching and matching[0]["severity"] == "critical"
    assert audit["status"] == "passed"


def test_missing_stage3_sanity_metadata_fails_closed():
    question = _question([_asset(sanity={})])
    assert "visual_precise_crop_unresolved" in visual_metadata_issue_codes(question)


def test_deleting_required_visual_is_detected_from_source_contract():
    original = [_asset()]
    question = _question([], issues=[], contract=_contract(original))
    assert "visual_precise_crop_unresolved" in visual_metadata_issue_codes(question)
    # The deletion is detected from the immutable source contract and surfaced as a
    # critical advisory; it is not a forced-review blocker under owner policy (the
    # question still carries a stem and four options).
    audit = audit_page_first_projection(_projection(question))
    matching = [
        issue
        for issue in audit["issues"]
        if issue["code"] == "visual_precise_crop_unresolved"
    ]
    assert matching and matching[0]["severity"] == "critical"
    assert audit["status"] == "passed"


def test_stage3_asset_without_source_contract_fails_closed():
    question = _question([_asset()], contract={})
    assert "visual_precise_crop_unresolved" in visual_metadata_issue_codes(question)


def test_incomplete_option_visual_set_is_derived_again_during_review():
    option_assets = [
        _asset(
            id=f"inline-mistral-v1-source-p1-q1-option-o{label}-deadbeef",
            role="option",
            optionLabel=label,
            visualMode="separate_option",
        )
        for label in ("1", "2", "3")
    ]
    question = _question(option_assets, issues=[])
    assert "visual_missing_option_asset" in visual_metadata_issue_codes(question)
    audit = audit_page_first_projection(_projection(question))
    assert any(
        issue["code"] == "visual_missing_option_asset"
        and issue["severity"] == "critical"
        for issue in audit["issues"]
    )


def test_visual_critical_code_cannot_be_teacher_acknowledged_away():
    question = _question(
        [
            _asset(
                reviewOnly=True,
                sanity={
                    "status": "needs_review",
                    "issues": ["visual_table_border_risk"],
                },
            )
        ]
    )
    question["teacher_reviewed_issue_codes"] = ["visual_table_border_risk"]
    audit = audit_page_first_projection(_projection(question))
    assert any(
        issue["code"] == "visual_table_border_risk"
        and issue["severity"] == "critical"
        for issue in audit["issues"]
    )
