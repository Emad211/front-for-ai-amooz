from apps.classes.services.exam_prep_mistral_gold_baseline import (
    GOLD_BASELINE_PASS_IDS,
    GOLD_GEMINI_RECOVERY_IDS,
    GOLD_ITEM_COUNT,
    GOLD_LOCAL_VISUAL_REPAIR_IDS,
    validate_gold_baseline_partition,
)


def test_gold_baseline_partition_is_frozen_and_complete():
    validate_gold_baseline_partition()
    assert GOLD_ITEM_COUNT == 48
    assert len(GOLD_BASELINE_PASS_IDS) == 7
    assert len(GOLD_LOCAL_VISUAL_REPAIR_IDS) == 1
    assert len(GOLD_GEMINI_RECOVERY_IDS) == 40
    assert set(GOLD_BASELINE_PASS_IDS) | set(GOLD_LOCAL_VISUAL_REPAIR_IDS) | set(GOLD_GEMINI_RECOVERY_IDS)


def test_q081_is_the_only_zero_llm_visual_only_repair():
    assert GOLD_LOCAL_VISUAL_REPAIR_IDS == ("q-081",)


def test_all_gold_solution_failures_route_to_gemini_recovery():
    solution_ids = {item_id for item_id in GOLD_GEMINI_RECOVERY_IDS if item_id.startswith("s-")}
    assert len(solution_ids) == 22
