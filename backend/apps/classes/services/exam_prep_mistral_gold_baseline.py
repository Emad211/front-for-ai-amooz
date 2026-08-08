from __future__ import annotations

from typing import Final

# Frozen after blinded source review followed by source-vs-candidate audit.
# This is a hard publish-safe gate, not an estimate of whole-document accuracy.
GOLD_BASELINE_PASS_IDS: Final[tuple[str, ...]] = (
    "q-033",
    "q-046",
    "q-057",
    "q-065",
    "q-110",
    "q-140",
    "q-150",
)

# Text is acceptable; failure is only source-visual preservation and can be fixed locally.
GOLD_LOCAL_VISUAL_REPAIR_IDS: Final[tuple[str, ...]] = ("q-081",)

# Independent Gemini transcription is needed. Candidate Mistral text must not be shown.
GOLD_GEMINI_RECOVERY_IDS: Final[tuple[str, ...]] = (
    "q-001", "q-007", "q-018", "q-023", "q-045", "q-052", "q-074", "q-079",
    "q-089", "q-094", "q-105", "q-111", "q-113", "q-116", "q-120", "q-122",
    "q-129", "q-155",
    "s-001", "s-012", "s-018", "s-033", "s-045", "s-046", "s-050", "s-055",
    "s-056", "s-057", "s-065", "s-073", "s-081", "s-089", "s-093", "s-095",
    "s-115", "s-116", "s-120", "s-133", "s-140", "s-150",
)

GOLD_ITEM_COUNT: Final[int] = 48


def validate_gold_baseline_partition() -> None:
    groups = (
        set(GOLD_BASELINE_PASS_IDS),
        set(GOLD_LOCAL_VISUAL_REPAIR_IDS),
        set(GOLD_GEMINI_RECOVERY_IDS),
    )
    if any(groups[i] & groups[j] for i in range(len(groups)) for j in range(i + 1, len(groups))):
        raise ValueError("Gold baseline partitions overlap.")
    union = set().union(*groups)
    if len(union) != GOLD_ITEM_COUNT:
        raise ValueError(f"Gold baseline partition must contain {GOLD_ITEM_COUNT} unique items; got {len(union)}.")
    if len(GOLD_BASELINE_PASS_IDS) != 7:
        raise ValueError("Frozen Mistral baseline pass count must stay 7.")
    if len(GOLD_LOCAL_VISUAL_REPAIR_IDS) != 1:
        raise ValueError("Frozen local visual repair count must stay 1.")
    if len(GOLD_GEMINI_RECOVERY_IDS) != 40:
        raise ValueError("Frozen Gemini recovery count must stay 40.")
