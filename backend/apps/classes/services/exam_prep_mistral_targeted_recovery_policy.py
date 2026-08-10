"""Conservative targeted-solution recovery policy shared by production replays."""
from __future__ import annotations

from . import exam_prep_mistral_stage2_core as core
from .exam_prep_mistral_full_width_layout_policy import install_full_width_layout_policy


_ORIGINAL_TARGETED_RECOVERY = core._targeted_recovery


def targeted_recovery_with_usable_solution_context(
    data: bytes,
    *,
    accepted,
    missing,
    invalid,
    config,
    should_cancel,
):
    """Buy targeted OCR only for invalid labels on already accepted solutions."""

    del missing
    invalid_targets = sorted({int(value) for value in invalid if int(value) > 0})
    accepted_numbers = {
        int(item.question_number)
        for item in accepted
        if int(getattr(item, "question_number", 0) or 0) > 0
    }
    eligible = [value for value in invalid_targets if value in accepted_numbers]
    if not eligible:
        return {}, None
    return _ORIGINAL_TARGETED_RECOVERY(
        data,
        accepted=accepted,
        missing=(),
        invalid=eligible,
        config=config,
        should_cancel=should_cancel,
    )


def install_targeted_recovery_policy() -> None:
    install_full_width_layout_policy()
    if core._targeted_recovery is not targeted_recovery_with_usable_solution_context:
        core._targeted_recovery = targeted_recovery_with_usable_solution_context


__all__ = [
    "install_targeted_recovery_policy",
    "targeted_recovery_with_usable_solution_context",
]
