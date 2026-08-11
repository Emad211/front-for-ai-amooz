from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any, Literal, Mapping, Sequence
import unicodedata

from pydantic import BaseModel, Field, field_validator


_VISUAL_TYPES = (
    "none",
    "diagram",
    "graph",
    "chemical_structure",
    "table",
    "spatial_layout",
    "other",
)


class DirectTranscription(BaseModel):
    transcription_markdown: str = Field(min_length=1, max_length=20000)
    source_visual_required: bool
    visual_type: Literal[
        "none",
        "diagram",
        "graph",
        "chemical_structure",
        "table",
        "spatial_layout",
        "other",
    ]
    transcription_uncertain: bool
    uncertain_fragments: list[str] = Field(default_factory=list, max_length=16)

    @field_validator("transcription_markdown")
    @classmethod
    def reject_non_renderable_controls(cls, value: str) -> str:
        if any(
            unicodedata.category(char) == "Cc" and char not in "\t\n\r"
            for char in value
        ):
            raise ValueError("transcription_markdown contains a control character")
        return value


@dataclass(frozen=True, slots=True)
class DirectTranscriptTarget:
    kind: Literal["question", "solution"]
    question_number: int

    @property
    def item_id(self) -> str:
        return ("q" if self.kind == "question" else "s") + f"-{self.question_number:03d}"


def normalize_text_for_similarity(value: str) -> str:
    text = str(value or "")
    text = text.translate(
        str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
            "01234567890123456789",
        )
    )
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def text_similarity(left: str, right: str) -> float:
    a = normalize_text_for_similarity(left)
    b = normalize_text_for_similarity(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return round(SequenceMatcher(None, a, b).ratio(), 6)


def numeric_signature(value: str) -> tuple[str, ...]:
    text = normalize_text_for_similarity(value)
    # Keep signs/exponents attached where possible, but deliberately avoid any
    # subject-specific interpretation. This is only a disagreement signal.
    return tuple(
        re.findall(
            r"(?<![A-Za-z0-9])[-+]?\d+(?:[\.,]\d+)?(?:\^[-+]?\d+)?",
            text,
        )
    )


def normalize_direct_transcription(value: DirectTranscription) -> dict[str, Any]:
    visual_type = str(value.visual_type)
    if visual_type not in _VISUAL_TYPES:
        visual_type = "other"
    uncertain = [str(item).strip()[:300] for item in value.uncertain_fragments if str(item).strip()]
    return {
        "transcriptionMarkdown": value.transcription_markdown,
        "sourceVisualRequired": bool(value.source_visual_required),
        "visualType": visual_type,
        "transcriptionUncertain": bool(value.transcription_uncertain),
        "uncertainFragments": uncertain,
    }


def summarize_direct_transcriptions(
    *,
    targets: Sequence[Mapping[str, Any]],
    transcripts_by_model: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    models = list(transcripts_by_model)
    if len(models) < 2:
        raise ValueError("Direct-transcription comparison requires at least two models.")
    indexed = {
        model: {str(item.get("itemId")): item for item in rows}
        for model, rows in transcripts_by_model.items()
    }
    items: list[dict[str, Any]] = []
    for target in targets:
        item_id = str(target.get("itemId") or "")
        rows = [indexed[model].get(item_id) for model in models]
        if any(row is None for row in rows):
            raise ValueError(f"Missing direct transcript for {item_id}.")
        assert all(row is not None for row in rows)
        typed_rows = [row for row in rows if row is not None]
        visual_flags = [bool(row.get("sourceVisualRequired")) for row in typed_rows]
        visual_types = [str(row.get("visualType") or "none") for row in typed_rows]
        uncertain_flags = [bool(row.get("transcriptionUncertain")) for row in typed_rows]
        pairwise: dict[str, float] = {}
        numeric_agreement: dict[str, bool] = {}
        for left_index, left_model in enumerate(models):
            for right_index in range(left_index + 1, len(models)):
                right_model = models[right_index]
                left_row = indexed[left_model][item_id]
                right_row = indexed[right_model][item_id]
                key = f"{left_model}__{right_model}"
                pairwise[key] = text_similarity(
                    str(left_row.get("transcriptionMarkdown") or ""),
                    str(right_row.get("transcriptionMarkdown") or ""),
                )
                numeric_agreement[key] = (
                    numeric_signature(str(left_row.get("transcriptionMarkdown") or ""))
                    == numeric_signature(str(right_row.get("transcriptionMarkdown") or ""))
                )
        items.append(
            {
                "itemId": item_id,
                "kind": target.get("kind"),
                "questionNumber": target.get("questionNumber"),
                "physicalPageNumber": target.get("physicalPageNumber"),
                "pairwiseTextSimilarity": pairwise,
                "pairwiseNumericSignatureAgreement": numeric_agreement,
                "sourceVisualRequiredByAll": all(visual_flags),
                "sourceVisualRequiredByAny": any(visual_flags),
                "visualTypeAgreement": len(set(visual_types)) == 1,
                "visualTypesByModel": dict(zip(models, visual_types)),
                "anyModelUncertain": any(uncertain_flags),
                "allModelsUncertain": all(uncertain_flags),
            }
        )
    return {
        "schemaVersion": 1,
        "contentFree": True,
        "modelCount": len(models),
        "models": models,
        "itemCount": len(items),
        "visualRequirementDisagreementCount": sum(
            item["sourceVisualRequiredByAny"] != item["sourceVisualRequiredByAll"]
            for item in items
        ),
        "visualTypeDisagreementCount": sum(not item["visualTypeAgreement"] for item in items),
        "numericSignatureDisagreementCount": sum(
            not all((item["pairwiseNumericSignatureAgreement"] or {}).values())
            for item in items
        ),
        "items": items,
    }
