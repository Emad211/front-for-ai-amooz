import pytest

from apps.classes.services.exam_prep_mistral_fidelity_benchmark import (
    FidelityBatchReview,
    find_target_regions,
    normalize_review_batch,
    padded_pixel_box,
    parse_fidelity_targets,
    summarize_verifier_consensus,
)


def test_parse_fidelity_targets_is_explicit_and_deduplicated():
    targets = parse_fidelity_targets("question:18, solution:45,question:18")
    assert [(item.kind, item.question_number) for item in targets] == [
        ("question", 18),
        ("solution", 45),
    ]
    assert [item.item_id for item in targets] == ["q-018", "s-045"]


def test_find_target_regions_requires_exactly_one_region():
    targets = parse_fidelity_targets("question:18")
    analysis = {
        "pages": [
            {
                "originalPageNumber": 4,
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 18,
                        "bbox": [0.0, 0.1, 1.0, 0.3],
                        "text": "candidate",
                        "issues": ["visual"],
                    }
                ],
            }
        ]
    }
    selected = find_target_regions(analysis, targets)
    assert selected[0]["itemId"] == "q-018"
    assert selected[0]["physicalPageNumber"] == 4

    analysis["pages"][0]["regions"].append(dict(analysis["pages"][0]["regions"][0]))
    with pytest.raises(ValueError, match="resolved to 2 regions"):
        find_target_regions(analysis, targets)


def test_padded_pixel_box_is_clamped_to_page():
    assert padded_pixel_box(
        [0.0, 0.0, 0.5, 0.5],
        width=1000,
        height=2000,
        padding_ratio=0.01,
    ) == (0, 0, 510, 1020)


def test_normalize_review_batch_requires_all_requested_items():
    review = FidelityBatchReview.model_validate(
        {
            "items": [
                {
                    "item_id": "q-018",
                    "verdict": "major_error",
                    "candidate_usable_without_repair": False,
                    "source_visual_required": True,
                    "errors": [
                        {
                            "category": "number",
                            "severity": "critical",
                            "candidate_fragment": "5",
                            "source_reading": "3",
                        }
                    ],
                }
            ]
        }
    )
    normalized = normalize_review_batch(review, expected_item_ids=["q-018"])
    assert normalized[0]["errors"][0]["severity"] == "critical"

    with pytest.raises(ValueError, match="item mismatch"):
        normalize_review_batch(review, expected_item_ids=["q-018", "q-019"])


def test_consensus_only_marks_critical_when_all_models_agree():
    targets = [
        {
            "itemId": "q-018",
            "kind": "question",
            "questionNumber": 18,
            "physicalPageNumber": 4,
        },
        {
            "itemId": "q-052",
            "kind": "question",
            "questionNumber": 52,
            "physicalPageNumber": 11,
        },
    ]
    reviews = {
        "model-a": [
            {
                "itemId": "q-018",
                "verdict": "major_error",
                "candidateUsableWithoutRepair": False,
                "sourceVisualRequired": True,
                "errors": [{"category": "number", "severity": "critical"}],
            },
            {
                "itemId": "q-052",
                "verdict": "exact",
                "candidateUsableWithoutRepair": True,
                "sourceVisualRequired": False,
                "errors": [],
            },
        ],
        "model-b": [
            {
                "itemId": "q-018",
                "verdict": "major_error",
                "candidateUsableWithoutRepair": False,
                "sourceVisualRequired": True,
                "errors": [{"category": "number", "severity": "critical"}],
            },
            {
                "itemId": "q-052",
                "verdict": "minor_error",
                "candidateUsableWithoutRepair": True,
                "sourceVisualRequired": False,
                "errors": [{"category": "persian_text", "severity": "minor"}],
            },
        ],
    }
    report = summarize_verifier_consensus(targets=targets, reviews_by_model=reviews)
    assert report["consensusCriticalCount"] == 1
    assert report["verifierDisagreementCount"] == 1
    assert report["items"][0]["consensusIssueCategories"] == ["number"]
