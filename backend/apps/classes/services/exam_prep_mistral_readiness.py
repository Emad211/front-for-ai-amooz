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
    # considered every source region with the production (non-targeted) policy.
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

    regions = _integer(stats.get('regions'))
    missing = _integer(stats.get('missingRegions'))
    primary_calls = _integer(stats.get('primaryCalls'))
    blocked = _integer(stats.get('blocked'))
    risk_regions = _integer(audit.get('riskRegionCount'))
    suspicious_regions = _integer(audit.get('riskSuspiciousRegionCount'))
    recorded_primary_calls = _integer(audit.get('targetedRegionPrimaryCalls'))
    recorded_unresolved = _integer(audit.get('targetedRegionUnresolved'))
    if (
        regions is None
        or regions < 1
        or missing is None
        or missing < 0
        or primary_calls is None
        or not 0 <= primary_calls <= regions
        or blocked is None
        or blocked < 0
        or len(rows) < regions
        or risk_regions != regions
        or suspicious_regions is None
        or suspicious_regions < 0
        or recorded_primary_calls != primary_calls
        or recorded_unresolved != blocked
    ):
        return False

    if not require_publishable:
        return True

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


__all__ = ['production_review_artifact_is_valid']
