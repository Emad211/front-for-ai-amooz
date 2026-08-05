# Exam Prep — Deleted-question publication hotfix

Date: 2026-08-05

## Observed failure

A teacher reviewed an existing 50-question draft, deleted two invalid questions, saved the 48-question result, and still could not publish. The edit page showed zero unresolved question-level items while the detail page remained publication-blocked.

## Root causes

1. The post-edit audit still treated gaps in original source question numbers as critical. After intentionally deleting questions, `missing_question_number` remained a blocker even though the curated 48-question list was valid.
2. Page-first audits are stored in `workflow_state.extractionAudit`, but the legacy detail serializer returned only artifact-backed audits. The edit UI therefore could not show page-first global blockers.
3. Older drafts could retain a cover/blank page as `failed_chunk` from runs before the local non-content classifier existed.

## Final rules

- Extraction-time numbering gaps remain strict in the initial pipeline audit.
- After explicit teacher curation, source-number gaps remain visible as warnings but do not block publication.
- Duplicate question numbers, missing text/options/answers, invalid answer labels, and other structural defects remain critical.
- The page-first detail endpoint exposes the durable workflow audit even when no extraction artifact exists.
- On the first detail refresh, a completed page-first draft is re-audited and its status is repaired to `exam_structured` when no real critical blockers remain.
- Legacy failed pages are rechecked with the zero-cost local classifier. Only confidently non-content cover/blank pages are removed; classification failure stays fail-closed.
- A failed page that cannot be proven non-content remains publication-blocking.

## Compatibility

The refresh is idempotent and applies to existing drafts without re-running the provider pipeline or requiring a data migration. The current edited exam becomes publishable after deployment and page refresh when its only blockers are intentional numbering gaps or stale non-content page failures.
