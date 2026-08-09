from __future__ import annotations

from apps.classes.services.exam_prep_mistral_visual_review import (
    visual_metadata_issue_codes,
)
from apps.classes.services.exam_prep_page_review import audit_page_first_projection


def _asset() -> dict:
    return {
        "id": "inline-mistral-v1-source-p1-q1-question-1-deadbeef",
        "role": "question",
        "optionLabel": None,
        "sourcePage": 1,
        "sourceBBox": {"x0": 0.2, "y0": 0.2, "x1": 0.6, "y1": 0.5},
        "storagePath": "exam-prep/source/visuals/v1/source/p001-q001-question-01-deadbeef.png",
        "visualMode": "single_question",
        "reviewOnly": False,
        "sanity": {"status": "passed", "issues": []},
    }


def _contract(asset: dict) -> dict:
    return {
        "schemaVersion": 1,
        "requiredAssetIds": [asset["id"]],
        "roleCounts": {"question": 1, "option": 0, "solution": 0},
        "optionLabels": [],
        "groupedOptionLabels": [],
        "sourcePages": [1],
        "fingerprint": "server-test",
    }


def _question(*, visuals, editable_contract) -> dict:
    return {
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
        "visualSourceContract": editable_contract,
        "issues": [],
    }


def test_server_contract_detects_deleted_asset_even_if_editable_contract_is_tampered():
    asset = _asset()
    server = _contract(asset)
    question = _question(visuals=[], editable_contract={})
    assert "visual_precise_crop_unresolved" in visual_metadata_issue_codes(
        question,
        source_contract=server,
    )


def test_page_review_uses_server_contract_by_question_id():
    asset = _asset()
    server = _contract(asset)
    question = _question(visuals=[], editable_contract={})
    audit = audit_page_first_projection(
        {"exam_prep": {"title": "تست", "questions": [question]}},
        visual_source_contracts={"default-q-1": server},
    )
    assert audit["visualSourceContracts"] == {"default-q-1": server}
    assert any(
        issue["code"] == "visual_precise_crop_unresolved"
        and issue["severity"] == "critical"
        for issue in audit["issues"]
    )


def test_clean_current_asset_passes_against_server_contract_even_if_editable_copy_is_missing():
    asset = _asset()
    server = _contract(asset)
    question = _question(visuals=[asset], editable_contract={})
    assert visual_metadata_issue_codes(
        question,
        source_contract=server,
    ) == []
