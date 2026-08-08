import pytest

from apps.classes.management.commands.build_exam_prep_mistral_gold_benchmark_pack import (
    _annotation_row,
    _gold_region_targets,
)
from apps.classes.services.exam_prep_mistral_fidelity_benchmark import parse_fidelity_targets
from apps.classes.services.exam_prep_mistral_gold_benchmark import (
    GoldTarget,
    boundary_recovery_questions,
    gold_target_tokens,
    gold_targets,
    resolve_gold_target_regions,
    validate_gold_target_spec,
)


def test_gold_target_spec_is_frozen_balanced_and_unique():
    validate_gold_target_spec()
    targets = gold_targets()
    assert len(targets) == 48
    assert sum(row.kind == "question" for row in targets) == 26
    assert sum(row.kind == "solution" for row in targets) == 22
    assert len(gold_target_tokens()) == len(set(gold_target_tokens()))
    strata = {row.stratum for row in targets}
    assert "physics_circuit" in strata
    assert "chemistry_structure" in strata
    assert "solution_source_font_corruption" in strata
    assert "solution_geometry" in strata

    tokens = set(gold_target_tokens())
    assert "solution:8" not in tokens
    assert "solution:111" not in tokens
    assert "solution:113" not in tokens
    assert {"solution:12", "solution:115", "solution:116"} <= tokens


def test_offline_gold_pack_keeps_48_targets_without_weakening_paid_probe_cap():
    assert len(_gold_region_targets()) == 48

    paid_probe_tokens = ",".join(f"question:{number}" for number in range(1, 42))
    with pytest.raises(ValueError, match="capped at 40"):
        parse_fidelity_targets(paid_probe_tokens)


def test_source_aware_resolver_ignores_numbered_lists_on_solution_pages():
    target = GoldTarget("question", 1, "biology_prose")
    analysis = {
        "pages": [
            {
                "originalPageNumber": 2,
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 1,
                        "bbox": [0.0, 0.1, 1.0, 0.3],
                        "text": "real question",
                        "issues": [],
                    }
                ],
            },
            {
                "originalPageNumber": 33,
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 1,
                        "bbox": [0.5, 0.8, 1.0, 0.9],
                        "text": "numbered list false positive",
                        "issues": ["heading_sequence_gap"],
                    }
                ],
            },
            {
                "originalPageNumber": 36,
                "regions": [
                    {
                        "kind": "question",
                        "questionNumber": 1,
                        "bbox": [0.0, 0.4, 0.5, 0.7],
                        "text": "another numbered list false positive",
                        "issues": ["heading_sequence_gap"],
                    }
                ],
            },
        ]
    }
    selected = resolve_gold_target_regions(analysis, targets=[target])
    assert len(selected) == 1
    assert selected[0]["physicalPageNumber"] == 2
    assert selected[0]["candidateText"] == "real question"


def test_source_aware_resolver_keeps_solution_targets_on_worked_solution_pages():
    target = GoldTarget("solution", 115, "solution_math")
    analysis = {
        "pages": [
            {
                "originalPageNumber": 30,
                "regions": [
                    {
                        "kind": "solution",
                        "questionNumber": 115,
                        "bbox": [0.0, 0.1, 0.5, 0.2],
                        "text": "wrong page",
                        "issues": [],
                    }
                ],
            },
            {
                "originalPageNumber": 50,
                "regions": [
                    {
                        "kind": "solution",
                        "questionNumber": 115,
                        "bbox": [0.5, 0.2, 1.0, 0.5],
                        "text": "real solution",
                        "issues": [],
                    }
                ],
            },
        ]
    }
    selected = resolve_gold_target_regions(analysis, targets=[target])
    assert len(selected) == 1
    assert selected[0]["physicalPageNumber"] == 50


def test_boundary_recovery_set_matches_evidence():
    assert boundary_recovery_questions() == (4, 5, 6, 10, 15, 26, 30, 57, 74)


def test_annotation_template_is_blind_and_empty():
    item = {
        "itemId": "q-094",
        "kind": "question",
        "questionNumber": 94,
        "physicalPageNumber": 20,
        "candidateText": "MISTRAL MUST NOT LEAK",
    }
    row = _annotation_row(
        item=item,
        stratum="chemistry_structure",
        crop_file="source/q-094.png",
    )
    assert "MISTRAL MUST NOT LEAK" not in str(row)
    assert row["gold"]["transcriptionMarkdown"] == ""
    assert row["gold"]["sourceVisualRequired"] is None
    assert row["sourceCropFile"] == "source/q-094.png"
