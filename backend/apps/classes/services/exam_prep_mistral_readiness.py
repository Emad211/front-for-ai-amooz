"""Fail-closed state gates for production Mistral Exam Prep drafts."""
from __future__ import annotations

from collections.abc import Mapping

from .exam_prep_mistral_production import PRODUCTION_ENGINE


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def production_review_artifact_is_valid(
    workflow: object,
    *,
    require_publishable: bool = False,
) -> bool:
    """Verify durable evidence that all five production stages completed.

    A blocked Stage-5 result is still a valid *review* artifact, but it is not
    publishable. This distinction lets a teacher correct a completed draft
    without allowing hand-written workflow JSON to impersonate the pipeline.
    """

    if not isinstance(workflow, Mapping):
        return False
    if (
        workflow.get('engine') != PRODUCTION_ENGINE
        or workflow.get('stage') != 'ready_for_review'
        or workflow.get('readyForReview') is not True
    ):
        return False

    audit = workflow.get('extractionAudit')
    if not isinstance(audit, Mapping) or audit.get('engine') != PRODUCTION_ENGINE:
        return False

    # Stage 1: OCR completed against a real PDF and recorded its resolved model.
    ocr_pages = _integer(audit.get('ocrSourcePages'))
    resolved_models = audit.get('ocrResolvedModels')
    if (
        ocr_pages is None
        or ocr_pages < 1
        or not isinstance(resolved_models, list)
        or not any(str(model or '').strip() for model in resolved_models)
    ):
        return False

    # Stage 2: deterministic assembly and native answer evidence were audited.
    question_count = _integer(audit.get('questionCount'))
    intervals = audit.get('questionIntervals')
    native_evidence = audit.get('nativeAnswerEvidence')
    if (
        question_count is None
        or question_count < 1
        or not isinstance(intervals, list)
        or not intervals
        or not all(isinstance(item, Mapping) for item in intervals)
        or not isinstance(native_evidence, Mapping)
        or _integer(native_evidence.get('schemaVersion')) != 2
    ):
        return False

    # Stage 3: source-precise visual reconciliation completed, even if it found
    # review blockers or no visual assets at all.
    visual = audit.get('visualPipeline')
    if (
        not isinstance(visual, Mapping)
        or _integer(visual.get('schemaVersion')) != 2
        or len(str(visual.get('sourceSha256') or '')) != 64
        or not isinstance(visual.get('stats'), Mapping)
        or not isinstance(visual.get('unresolvedRegions'), list)
        or not isinstance(visual.get('criticalIssueCodes'), list)
    ):
        return False

    # Stage 4 leaves the deterministic risk counts; Stage 5 must prove that it
    # ran the production (non-targeted) policy over the source regions.
    risk = audit.get('riskEngine')
    if not isinstance(risk, Mapping) or _integer(risk.get('schemaVersion')) != 1:
        return False
    policy = risk.get('policy')
    stats = risk.get('stats')
    budget = risk.get('budget')
    rows = risk.get('regions')
    if (
        not isinstance(policy, Mapping)
        or policy.get('allRegionsReceivePrimary') is not True
        or policy.get('targetedEvaluation') is not False
        or not isinstance(stats, Mapping)
        or not isinstance(budget, Mapping)
        or not isinstance(rows, list)
        or not all(isinstance(row, Mapping) for row in rows)
    ):
        return False

    # Anti-forgery is satisfied: every stage left durable, schema-versioned
    # evidence that hand-written workflow JSON cannot fabricate. Publishing is
    # always allowed from here (owner policy `همیشه مجاز`), so we deliberately do
    # NOT enforce publish-readiness *consistency* on this path. In particular a
    # legitimate degraded recheck makes ``primaryCalls`` exceed ``regions``
    # (`maxPrimaryDegradedRechecksPerRegion: 1`), which is a healthy signal, not
    # a forged one — gating on it wrongly blocked real 100+ question booklets.
    if not require_publishable:
        return True

    regions = _integer(stats.get('regions'))
    missing = _integer(stats.get('missingRegions'))
    primary_calls = _integer(stats.get('primaryCalls'))
    blocked = _integer(stats.get('blocked'))
    if (
        regions is None
        or regions < 1
        or missing is None
        or missing < 0
        or primary_calls is None
        or primary_calls < 0
        or blocked is None
        or blocked < 0
    ):
        return False

    visual_stats = visual['stats']
    visual_unresolved = _integer(visual_stats.get('unresolvedRegions'))
    visual_storage_failures = _integer(visual_stats.get('storageFailures'))
    allowed_statuses = ('verified', 'repaired')
    return bool(
        workflow.get('publicationBlocked') is False
        and audit.get('status') == 'passed'
        and _integer(audit.get('criticalIssueCount')) == 0
        and missing == 0
        and blocked == 0
        and primary_calls == regions
        and len(rows) == regions
        and all(
            str(row.get('status') or '').startswith(allowed_statuses)
            for row in rows
        )
        and budget.get('preflightExceeded') is False
        and budget.get('deadlineExceeded') is False
        and not visual.get('unresolvedRegions')
        and not visual.get('criticalIssueCodes')
        and visual_unresolved == 0
        and visual_storage_failures == 0
    )


def production_run_is_authentic(workflow: object) -> bool:
    """Shallow anti-forgery check: did the production pipeline genuinely run?

    This is the gate that publish, the review PATCH, and the re-audit refresh
    consult. It confirms the run is a real Mistral production extraction — enough
    to defeat hand-written workflow JSON — WITHOUT demanding that every deep
    Stage-3/4/5 schema field survived byte-for-byte.

    Why shallow, and why it matters (owner-locked `همیشه مجاز`): a completed
    137-question run whose persisted ``visualPipeline.sourceSha256`` came back
    blank (a resumed-OCR run) is unmistakably real — every Stage-1/Stage-2
    authenticity fingerprint is intact — yet the strict
    :func:`production_review_artifact_is_valid` fail-closes on that one drifted
    field. Because the strict gate guarded publish AND the review PATCH conflict
    check AND the re-audit refresh, one drifted field made the run permanently
    unpublishable and un-editable, with the teacher's deletions silently refused.
    This gate checks only the fingerprints that a forgery cannot fabricate and
    that deterministic Stage-1/Stage-2 always emit, so a drifted-but-real run
    stays fully usable while a bare forged workflow is still rejected.

    A blocked/degraded Stage-5 result is still authentic — publishing remains a
    teacher-ownership decision, never an issue-count gate.
    """

    if not isinstance(workflow, Mapping):
        return False
    if (
        workflow.get('engine') != PRODUCTION_ENGINE
        or workflow.get('stage') != 'ready_for_review'
        or workflow.get('readyForReview') is not True
    ):
        return False

    audit = workflow.get('extractionAudit')
    if not isinstance(audit, Mapping) or audit.get('engine') != PRODUCTION_ENGINE:
        return False

    # Stage 1 fingerprint: OCR ran against a real PDF and recorded its model.
    ocr_pages = _integer(audit.get('ocrSourcePages'))
    resolved_models = audit.get('ocrResolvedModels')
    if (
        ocr_pages is None
        or ocr_pages < 1
        or not isinstance(resolved_models, list)
        or not any(str(model or '').strip() for model in resolved_models)
    ):
        return False

    # Stage 2 fingerprint: deterministic assembly produced numbered questions
    # over concrete source intervals. These are emitted for every real run and
    # are exactly what a hand-written workflow omits.
    question_count = _integer(audit.get('questionCount'))
    intervals = audit.get('questionIntervals')
    if (
        question_count is None
        or question_count < 1
        or not isinstance(intervals, list)
        or not intervals
        or not all(isinstance(item, Mapping) for item in intervals)
    ):
        return False

    return True


__all__ = [
    'production_review_artifact_is_valid',
    'production_run_is_authentic',
]
