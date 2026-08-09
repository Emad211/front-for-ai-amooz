"""Stage 4 risk-gated source verification and repair.

Policy:
- every numbered OCR region receives a free deterministic risk score;
- clean regions make no LLM call;
- suspicious regions send exactly one exact source crop to Gemini 3 Flash with
  minimal thinking and without the Mistral candidate;
- only hard math/formula disagreements may receive one GPT-5.4-mini second
  opinion;
- provider confidence is never used as authority;
- Stage-3 visual evidence is copied through unchanged;
- unresolved suspicious regions fail closed with one machine blocker rather than
  becoming a large teacher-review queue.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import math
import os
import re
from typing import Any, Mapping, Sequence

from PIL import Image

from . import exam_prep_mistral_stage2_core as stage2
from .exam_prep_mistral_direct_transcription import numeric_signature, text_similarity
from .exam_prep_mistral_risk_engine import RegionRiskDecision, score_region_risks
from .exam_prep_mistral_region_transcriber import (
    RegionTranscriptionResult,
    primary_model,
    secondary_model,
    transcribe_source_region,
)
from .exam_prep_mistral_solution_headings import (
    normalize_solution_option_label,
    parse_solution_heading,
)
from .exam_prep_page_records import PageAssemblyResult
from .exam_prep_question_verifier import rebuild_assembly_quality
from .exam_prep_utils import clean_exam_markdown


_STAGE4_BLOCKER = "stage4_verification_unresolved"
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_SOLUTION_Q_FIRST_STRIP = re.compile(
    r"^\s*[#«»\"'()]*\s*[0-9۰-۹٠-٩]{1,3}\s*[»\"'()]*\s*"
    r"(?:[-–—]\s*)?گزین(?:ه|ۀ|هٔ)\s*[«»\"'()]*\s*"
    r"[0-9۰-۹٠-٩]{1,2}\s*[»\"'()]*\s*",
    re.IGNORECASE,
)
_SOLUTION_OPTION_FIRST_STRIP = re.compile(
    r"^\s*[#«»\"'()]*\s*[0-9۰-۹٠-٩]{1,2}\s*[»\"'()]*\s*"
    r"گزین(?:ه|ۀ|هٔ)\s*(?:[-–—]\s*)?[0-9۰-۹٠-٩]{1,3}\s*",
    re.IGNORECASE,
)
_QUESTION_REPAIR_STALE = frozenset(
    {
        "mistral_question_option_parse_failed",
        "missing_question_text",
        "missing_options",
        "missing_option_text",
        "missing_options_text",
        "placeholder_option_text",
        "unexpected_option_count",
        "duplicate_option_label",
        "broken_persian_text",
        "duplicate_mixed_text",
    }
)
_SOLUTION_REPAIR_STALE = frozenset(
    {
        "mistral_solution_heading_unresolved",
        "missing_answer",
        "missing_correct_option_label",
        "missing_solution_text",
        "correct_option_not_in_options",
        "conflicting_correct_option",
        "conflicting_correct_option_text",
        "broken_persian_text",
        "duplicate_mixed_text",
        "count_answer_unresolved",
    }
)
_STRONG_TEXTUAL_SIGNALS = frozenset(
    {"missing_invalid_answer", "heading_conflict", "ocr_disagreement", "source_corruption"}
)


def _primary_cap() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_STAGE4_MAX_PRIMARY_CALLS", "24"))
    except (TypeError, ValueError):
        value = 24
    return max(1, min(80, value))


def _secondary_cap() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_STAGE4_MAX_SECONDARY_CALLS", "6"))
    except (TypeError, ValueError):
        value = 6
    return max(0, min(20, value))


def _crop_padding() -> float:
    try:
        value = float(os.getenv("EXAM_PREP_STAGE4_CROP_PADDING", "0.010"))
    except (TypeError, ValueError):
        value = 0.010
    return max(0.002, min(0.025, value))


def _crop_dpi() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_STAGE4_CROP_DPI", "260"))
    except (TypeError, ValueError):
        value = 260
    return max(180, min(360, value))


def _max_crop_dimension() -> int:
    try:
        value = int(os.getenv("EXAM_PREP_STAGE4_CROP_MAX_DIMENSION", "1900"))
    except (TypeError, ValueError):
        value = 1900
    return max(1200, min(2600, value))


def _question_number(question: Mapping[str, Any]) -> int:
    match = re.search(r"\d+", str(question.get("source_question_number") or "").translate(_DIGITS))
    return int(match.group(0)) if match else 0


def _question_map(result: PageAssemblyResult) -> dict[int, dict[str, Any]]:
    output: dict[int, dict[str, Any]] = {}
    for raw in (result.projection.get("exam_prep") or {}).get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        number = _question_number(raw)
        if number > 0:
            output[number] = dict(raw)
    return output


def _render_crop(pdf_data: bytes, decision: RegionRiskDecision) -> bytes:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdfium2 is required for Stage-4 source crops") from exc

    document = pdfium.PdfDocument(pdf_data)
    try:
        if decision.page_number < 1 or decision.page_number > len(document):
            raise ValueError("Stage-4 source page is outside the PDF")
        page = document[decision.page_number - 1]
        try:
            bitmap = page.render(scale=float(_crop_dpi()) / 72.0)
            try:
                image = bitmap.to_pil().convert("RGB")
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()

    try:
        pad = _crop_padding()
        x0, y0, x1, y1 = decision.bbox
        box = (
            max(0.0, x0 - pad),
            max(0.0, y0 - pad),
            min(1.0, x1 + pad),
            min(1.0, y1 + pad),
        )
        width, height = image.size
        left = max(0, min(width - 1, int(math.floor(box[0] * width))))
        top = max(0, min(height - 1, int(math.floor(box[1] * height))))
        right = max(left + 1, min(width, int(math.ceil(box[2] * width))))
        bottom = max(top + 1, min(height, int(math.ceil(box[3] * height))))
        crop = image.crop((left, top, right, bottom)).convert("RGB")
        try:
            maximum = _max_crop_dimension()
            if max(crop.size) > maximum:
                ratio = maximum / max(crop.size)
                resized = crop.resize(
                    (max(1, round(crop.width * ratio)), max(1, round(crop.height * ratio))),
                    Image.Resampling.LANCZOS,
                )
                crop.close()
                crop = resized
            output = io.BytesIO()
            crop.save(output, format="PNG", optimize=True)
            return output.getvalue()
        finally:
            crop.close()
    finally:
        image.close()


def _parse_question_transcript(value: str) -> dict[str, Any] | None:
    stem, options, style = stage2.parse_question_region_text(value)
    if not stem and style == "parenthesized_suffix" and len(options) == 4:
        first = clean_exam_markdown(options[0].get("text_markdown") or "")
        split_at = max(first.rfind("؟"), first.rfind("?"))
        if split_at >= 0:
            recovered_stem = clean_exam_markdown(first[: split_at + 1])
            first_value = clean_exam_markdown(first[split_at + 1 :])
            if recovered_stem and first_value:
                options = [dict(item) for item in options]
                options[0]["text_markdown"] = first_value
                stem = recovered_stem
    if not stem or len(options) != 4:
        return None
    labels = {str(item.get("label") or "") for item in options}
    if labels != {"1", "2", "3", "4"}:
        return None
    return {
        "question_text_markdown": clean_exam_markdown(stem),
        "options": [
            {
                "label": str(item.get("label") or ""),
                "text_markdown": clean_exam_markdown(item.get("text_markdown") or ""),
            }
            for item in sorted(options, key=lambda item: int(str(item.get("label") or "9")))
        ],
    }


def _question_payload_text(payload: Mapping[str, Any]) -> str:
    values = [clean_exam_markdown(payload.get("question_text_markdown") or "")]
    for option in payload.get("options") or []:
        if not isinstance(option, Mapping):
            continue
        values.append(
            f"{clean_exam_markdown(option.get('label') or '')}) "
            f"{clean_exam_markdown(option.get('text_markdown') or '')}"
        )
    return "\n".join(value for value in values if value)


def _parse_solution_transcript(value: str, *, expected_question: int) -> dict[str, Any] | None:
    text = clean_exam_markdown(value)
    if not text:
        return None
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    parsed = parse_solution_heading(first_line) or parse_solution_heading(text[:240])
    label: str | None = None
    if parsed is not None:
        if int(parsed.get("rawQuestionNumber") or 0) != expected_question:
            return None
        normalized, _changed, valid = normalize_solution_option_label(
            int(parsed.get("rawOptionLabel") or 0)
        )
        if not valid or normalized not in {1, 2, 3, 4}:
            return None
        label = str(normalized)
        text = _SOLUTION_Q_FIRST_STRIP.sub("", text, count=1)
        text = _SOLUTION_OPTION_FIRST_STRIP.sub("", text, count=1)
    body = clean_exam_markdown(text)
    if not body:
        return None
    return {
        "correct_option_label": label,
        "teacher_solution_markdown": body,
        "final_answer_markdown": f"گزینه {label}" if label else "",
    }


def _solution_payload_text(payload: Mapping[str, Any]) -> str:
    return clean_exam_markdown(payload.get("teacher_solution_markdown") or "")


def _proposal(
    decision: RegionRiskDecision,
    transcript: RegionTranscriptionResult,
) -> dict[str, Any] | None:
    if transcript.transcript.get("transcriptionUncertain"):
        return None
    text = clean_exam_markdown(transcript.transcript.get("transcriptionMarkdown") or "")
    if decision.kind == "question":
        return _parse_question_transcript(text)
    return _parse_solution_transcript(text, expected_question=decision.question_number)


def _proposal_text(decision: RegionRiskDecision, payload: Mapping[str, Any]) -> str:
    return _question_payload_text(payload) if decision.kind == "question" else _solution_payload_text(payload)


def _agreement(left: str, right: str) -> tuple[float, bool]:
    return text_similarity(left, right), numeric_signature(left) == numeric_signature(right)


def _apply_proposal(
    question: dict[str, Any],
    *,
    decision: RegionRiskDecision,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply text only. Visuals/contracts are intentionally never replaced."""

    visuals = question.get("visuals")
    visual_contract = question.get("visualSourceContract")
    updated = dict(question)
    if decision.kind == "question":
        updated["question_text_markdown"] = clean_exam_markdown(
            payload.get("question_text_markdown") or updated.get("question_text_markdown") or ""
        )
        updated["options"] = [dict(item) for item in (payload.get("options") or [])]
        stale = _QUESTION_REPAIR_STALE
    else:
        label = clean_exam_markdown(payload.get("correct_option_label") or "").translate(_DIGITS)
        if label in {"1", "2", "3", "4"}:
            updated["correct_option_label"] = label
            updated["final_answer_markdown"] = f"گزینه {label}"
        updated["teacher_solution_markdown"] = clean_exam_markdown(
            payload.get("teacher_solution_markdown") or updated.get("teacher_solution_markdown") or ""
        )
        stale = _SOLUTION_REPAIR_STALE
    updated["issues"] = [
        str(code)
        for code in (updated.get("issues") or [])
        if str(code) not in stale and str(code) != _STAGE4_BLOCKER
    ]
    if visuals is not None:
        updated["visuals"] = visuals
    if visual_contract is not None:
        updated["visualSourceContract"] = visual_contract
    return updated


def _mark_unresolved(question: dict[str, Any]) -> dict[str, Any]:
    updated = dict(question)
    issues = [str(code) for code in (updated.get("issues") or []) if str(code)]
    if _STAGE4_BLOCKER not in issues:
        issues.append(_STAGE4_BLOCKER)
    updated["issues"] = issues
    return updated


def _only_visual_anomaly(decision: RegionRiskDecision) -> bool:
    signals = set(decision.signals)
    return "visual_anomaly" in signals and not bool(signals & _STRONG_TEXTUAL_SIGNALS)


@dataclass(frozen=True, slots=True)
class Stage4Stats:
    regions: int
    clean: int
    suspicious: int
    primary_calls: int
    secondary_calls: int
    verified: int
    repaired: int
    unresolved: int
    deferred: int

    def as_dict(self) -> dict[str, int]:
        return {
            "regions": self.regions,
            "clean": self.clean,
            "suspicious": self.suspicious,
            "primaryCalls": self.primary_calls,
            "secondaryCalls": self.secondary_calls,
            "verified": self.verified,
            "repaired": self.repaired,
            "unresolved": self.unresolved,
            "deferred": self.deferred,
        }


def verify_and_repair_risky_regions(
    result: PageAssemblyResult,
    *,
    pdf_data: bytes,
    layout: Mapping[str, Any],
    recovered_solution_targets: Sequence[int] | set[int] = (),
    unresolved_solution_targets: Sequence[int] | set[int] = (),
    should_cancel=None,
) -> tuple[PageAssemblyResult, dict[str, Any]]:
    """Run the complete Stage-4 policy and return content-free audit metadata."""

    decisions = score_region_risks(
        projection=result.projection,
        layout=layout,
        recovered_solution_targets=recovered_solution_targets,
        unresolved_solution_targets=unresolved_solution_targets,
    )
    suspicious = [item for item in decisions if item.suspicious]
    questions = _question_map(result)
    per_question: dict[int, list[dict[str, Any]]] = {}
    primary_calls = secondary_calls = verified = repaired = unresolved = deferred = 0
    primary_limit = _primary_cap()
    secondary_limit = _secondary_cap()
    primary_name = primary_model()
    secondary_name = secondary_model()

    for decision in decisions:
        per_question.setdefault(decision.question_number, []).append(
            {**decision.safe_dict(), "status": "clean" if not decision.suspicious else "pending"}
        )

    for index, decision in enumerate(suspicious):
        if should_cancel is not None and should_cancel():
            raise RuntimeError("Cancellation requested during Stage-4 verification.")
        question = questions.get(decision.question_number)
        if question is None:
            continue
        row = next(
            item
            for item in per_question[decision.question_number]
            if item["targetId"] == decision.target_id
        )
        if index >= primary_limit:
            questions[decision.question_number] = _mark_unresolved(question)
            row.update({"status": "deferred_cost_cap", "reason": "primary_call_cap"})
            deferred += 1
            continue

        try:
            crop = _render_crop(pdf_data, decision)
            primary = transcribe_source_region(
                image=crop,
                kind=decision.kind,
                question_number=decision.question_number,
                page_number=decision.page_number,
                model=primary_name,
                thinking_minimal=True,
            )
            primary_calls += 1
        except Exception as exc:
            questions[decision.question_number] = _mark_unresolved(question)
            row.update({"status": "provider_failed", "reason": type(exc).__name__})
            unresolved += 1
            continue

        row["primary"] = primary.safe_dict()
        if primary.transcript.get("transcriptionUncertain"):
            if decision.hard_math and secondary_calls < secondary_limit:
                primary_payload = None
            elif _only_visual_anomaly(decision):
                row.update({"status": "visual_risk_preserved_source_uncertain"})
                continue
            else:
                questions[decision.question_number] = _mark_unresolved(question)
                row.update({"status": "source_uncertain"})
                unresolved += 1
                continue
        else:
            primary_payload = _proposal(decision, primary)

        if primary_payload is not None:
            proposed_text = _proposal_text(decision, primary_payload)
            similarity, numeric_same = _agreement(proposed_text, decision.candidate_text)
            row.update({"candidateSimilarity": similarity, "numericAgreement": numeric_same})
            if similarity >= 0.93 and numeric_same:
                row.update({"status": "verified_primary_agreement"})
                verified += 1
                continue

            # Numeric disagreement is always treated as real disagreement, but a
            # second paid model is reserved strictly for hard math/formulas. For
            # non-hard regions the independent source transcription is the repair.
            if not decision.hard_math:
                updated = _apply_proposal(question, decision=decision, payload=primary_payload)
                questions[decision.question_number] = updated
                row.update({"status": "repaired_primary"})
                verified += 1
                repaired += 1
                continue
            needs_second = True
        else:
            if _only_visual_anomaly(decision) and primary.transcript.get("sourceVisualRequired"):
                row.update({"status": "visual_risk_preserved"})
                continue
            needs_second = decision.hard_math

        if not needs_second or secondary_calls >= secondary_limit:
            questions[decision.question_number] = _mark_unresolved(question)
            row.update(
                {
                    "status": "unresolved",
                    "reason": "secondary_required" if needs_second else "primary_parse_failed",
                }
            )
            unresolved += 1
            continue

        try:
            secondary = transcribe_source_region(
                image=crop,
                kind=decision.kind,
                question_number=decision.question_number,
                page_number=decision.page_number,
                model=secondary_name,
                thinking_minimal=False,
            )
            secondary_calls += 1
        except Exception as exc:
            questions[decision.question_number] = _mark_unresolved(question)
            row.update({"status": "secondary_failed", "reason": type(exc).__name__})
            unresolved += 1
            continue

        row["secondary"] = secondary.safe_dict()
        secondary_payload = _proposal(decision, secondary)
        if secondary_payload is None or secondary.transcript.get("transcriptionUncertain"):
            questions[decision.question_number] = _mark_unresolved(question)
            row.update({"status": "secondary_uncertain"})
            unresolved += 1
            continue

        secondary_text = _proposal_text(decision, secondary_payload)
        primary_text = _proposal_text(decision, primary_payload) if primary_payload is not None else ""
        consensus_similarity, consensus_numeric = _agreement(primary_text, secondary_text)
        candidate_similarity_secondary, candidate_numeric_secondary = _agreement(
            secondary_text, decision.candidate_text
        )
        row.update(
            {
                "secondaryConsensusSimilarity": consensus_similarity,
                "secondaryConsensusNumeric": consensus_numeric,
                "secondaryCandidateSimilarity": candidate_similarity_secondary,
                "secondaryCandidateNumeric": candidate_numeric_secondary,
            }
        )
        if primary_payload is not None and consensus_similarity >= 0.88 and consensus_numeric:
            updated = _apply_proposal(question, decision=decision, payload=primary_payload)
            questions[decision.question_number] = updated
            row.update({"status": "repaired_two_model_consensus"})
            verified += 1
            repaired += 1
            continue
        if candidate_similarity_secondary >= 0.93 and candidate_numeric_secondary:
            row.update({"status": "verified_secondary_preserved_candidate"})
            verified += 1
            continue

        questions[decision.question_number] = _mark_unresolved(question)
        row.update({"status": "second_opinion_disagreement"})
        unresolved += 1

    projection = dict(result.projection)
    exam = dict(projection.get("exam_prep") or {})
    ordered: list[dict[str, Any]] = []
    for raw in exam.get("questions") or []:
        if not isinstance(raw, Mapping):
            continue
        number = _question_number(raw)
        question = dict(questions.get(number, raw))
        metadata = dict(question.get("stage4_verification") or {})
        metadata.update(
            {
                "regions": per_question.get(number, []),
                "hasSuspiciousRegion": any(
                    item.get("suspicious") for item in per_question.get(number, [])
                ),
            }
        )
        question["stage4_verification"] = metadata
        ordered.append(question)
    exam["questions"] = ordered
    projection["exam_prep"] = exam
    updated = result.model_copy(update={"projection": projection})
    updated = rebuild_assembly_quality(updated)

    stats = Stage4Stats(
        regions=len(decisions),
        clean=len(decisions) - len(suspicious),
        suspicious=len(suspicious),
        primary_calls=primary_calls,
        secondary_calls=secondary_calls,
        verified=verified,
        repaired=repaired,
        unresolved=unresolved,
        deferred=deferred,
    )
    audit = {
        "schemaVersion": 1,
        "policy": {
            "candidateMistralShown": False,
            "oneRegionOneImageOneCall": True,
            "primaryModel": primary_name,
            "primaryThinking": "minimal",
            "primaryProviderRetries": 0,
            "automaticPaidRepair": False,
            "secondaryModel": secondary_name,
            "secondaryOnlyForHardMath": True,
            "modelConfidenceAuthority": False,
            "visualEvidenceMutableByVerifier": False,
        },
        "stats": stats.as_dict(),
        "regions": [
            item
            for number in sorted(per_question)
            for item in per_question[number]
        ],
    }
    return updated, audit


__all__ = ["Stage4Stats", "verify_and_repair_risky_regions"]
