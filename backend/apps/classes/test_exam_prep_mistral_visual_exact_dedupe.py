from __future__ import annotations

from apps.classes.services.exam_prep_mistral_visual_reconcile import (
    _dedupe_exact_visual_assets,
)
from apps.classes.services.exam_prep_page_records import PageAssemblyResult


def _result():
    asset = {
        "id": "a1",
        "role": "question",
        "optionLabel": None,
        "selectedVariant": "source",
        "sha256": "f" * 64,
    }
    duplicate = {**asset, "id": "a2"}
    return PageAssemblyResult(
        projection={
            "exam_prep": {
                "questions": [
                    {
                        "source_question_number": "288",
                        "visuals": [asset, duplicate],
                        "visualSourceContract": {
                            "schemaVersion": 1,
                            "requiredAssetIds": ["a1", "a2"],
                        },
                    }
                ]
            }
        },
        issues=[],
        question_count=1,
        questions_needing_review=0,
        matched_answer_count=0,
        orphan_answers=[],
        question_number_gaps={},
        publication_ready=False,
    )


def test_exact_same_role_visual_is_kept_once_and_contract_is_synced():
    result, stats, audit = _dedupe_exact_visual_assets(
        _result(),
        {"assetsAttached": 2, "questionVisuals": 2, "optionVisuals": 0, "solutionVisuals": 0},
        {"policy": {}},
    )
    question = result.projection["exam_prep"]["questions"][0]
    assert [asset["id"] for asset in question["visuals"]] == ["a1"]
    assert question["visualSourceContract"]["requiredAssetIds"] == ["a1"]
    assert stats["assetsAttached"] == 1
    assert stats["questionVisuals"] == 1
    assert stats["exactDuplicateAssetsRemoved"] == 1
    assert audit["policy"]["exactVisualHashDedup"] is True


def test_same_bytes_with_different_option_roles_are_not_collapsed():
    result = _result()
    question = result.projection["exam_prep"]["questions"][0]
    question["visuals"][0]["role"] = "option"
    question["visuals"][0]["optionLabel"] = "1"
    question["visuals"][1]["role"] = "option"
    question["visuals"][1]["optionLabel"] = "2"
    updated, stats, _audit = _dedupe_exact_visual_assets(
        result,
        {"assetsAttached": 2, "questionVisuals": 0, "optionVisuals": 2, "solutionVisuals": 0},
        {},
    )
    assert len(updated.projection["exam_prep"]["questions"][0]["visuals"]) == 2
    assert "exactDuplicateAssetsRemoved" not in stats
