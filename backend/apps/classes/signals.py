from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from core.storage_backends import delete_answer_source_file

from .services.exam_prep_mistral_artifacts import cleanup_session_private_artifacts

from .models import (
    ClassCreationSession,
    ExamPrepExtractionArtifact,
    ExamPrepVisualAsset,
    StudentExerciseAnswerAsset,
)
from .models_v4 import ExamProject, ExamSourceDocument, ExamSourcePage
from .models_v4_blocks import ExamSourceBlock
from .models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamExtractionLifecycle,
    ExamQuestionRecord,
)
from .services.exam_prep_page_review import (
    audit_page_first_projection,
    parse_projection,
    render_projection_transcript,
    retain_failed_page_evidence,
)
from .services.exam_prep_mistral_production import PRODUCTION_ENGINE
from .services.exam_prep_mistral_readiness import (
    production_review_artifact_is_valid,
)
from .services.exam_prep_v4_create_flow import (
    cancel_source_aware_project_for_session,
    sync_create_flow_session,
)
from .services.exam_prep_v4_invalidation import (
    supersede_document_semantic_outputs,
    supersede_match_decisions_for_document,
)


def _delete_blobs_after_commit(names: list[str]) -> None:
    def delete_files() -> None:
        for name in names:
            delete_answer_source_file(name)

    transaction.on_commit(delete_files)


@receiver(
    post_delete,
    sender=ClassCreationSession,
    dispatch_uid='exam_prep_mistral_private_namespace_cleanup',
)
def cleanup_exam_prep_mistral_private_namespace(sender, instance, **kwargs):  # noqa: ARG001
    """Cover admin/cascade deletion paths that bypass the owner API."""

    if instance.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP:
        return
    session_id = instance.id
    transaction.on_commit(
        lambda: cleanup_session_private_artifacts(
            session_id,
            include_visuals=True,
            include_checkpoints=True,
        )
    )


@receiver(post_delete, sender=StudentExerciseAnswerAsset)
def delete_answer_asset_blob(sender, instance, **kwargs):  # noqa: ARG001
    name = instance.file.name
    if not name:
        return

    def delete_after_commit() -> None:
        delete_answer_source_file(name)

    transaction.on_commit(delete_after_commit)


@receiver(post_delete, sender=ExamPrepVisualAsset)
def delete_exam_visual_blobs(sender, instance, **kwargs):  # noqa: ARG001
    names = [
        field.name
        for field in (instance.source_file, instance.generated_file)
        if field and field.name
    ]
    if names:
        _delete_blobs_after_commit(names)


@receiver(post_delete, sender=ExamPrepExtractionArtifact)
def delete_exam_source_blocks(sender, instance, **kwargs):  # noqa: ARG001
    names = [
        block.get('storageName')
        for block in instance.source_blocks or []
        if isinstance(block, dict) and block.get('storageName')
    ]
    if names:
        _delete_blobs_after_commit(names)


@receiver(post_delete, sender=ExamSourcePage)
def delete_exam_v4_page_blobs(sender, instance, **kwargs):  # noqa: ARG001
    names = [
        field.name
        for field in (instance.rendered_file, instance.thumbnail_file)
        if field and field.name
    ]
    if names:
        _delete_blobs_after_commit(names)


@receiver(post_delete, sender=ExamSourceDocument)
def delete_exam_v4_document_blob(sender, instance, **kwargs):  # noqa: ARG001
    name = instance.source_file.name if instance.source_file else ''
    if name:
        _delete_blobs_after_commit([name])


@receiver(
    post_save,
    sender=ExamProject,
    dispatch_uid='exam_prep_source_aware_sync_existing_create_flow',
)
def sync_source_aware_project_to_existing_draft(
    sender,
    instance,
    **kwargs,
):  # noqa: ARG001
    sync_create_flow_session(instance)


@receiver(
    post_save,
    sender=ExamSourceDocument,
    dispatch_uid='exam_prep_source_aware_sync_document_progress',
)
def sync_source_aware_document_to_existing_draft(
    sender,
    instance,
    **kwargs,
):  # noqa: ARG001
    project = ExamProject.objects.filter(id=instance.project_id).first()
    if project is not None:
        sync_create_flow_session(project)


@receiver(
    post_save,
    sender=ClassCreationSession,
    dispatch_uid='exam_prep_source_aware_propagate_existing_cancel',
)
def propagate_existing_create_flow_cancel(
    sender,
    instance,
    **kwargs,
):  # noqa: ARG001
    if (
        instance.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP
        and instance.status == ClassCreationSession.Status.CANCELLED
    ):
        cancel_source_aware_project_for_session(instance)


@receiver(
    post_save,
    sender=ClassCreationSession,
    dispatch_uid='exam_prep_revalidate_teacher_edit',
)
def revalidate_exam_prep_teacher_edit(
    sender,
    instance,
    created,
    update_fields,
    **kwargs,
):  # noqa: ARG001
    """Re-audit only a teacher edit of canonical production exam JSON.

    The production task saves ``exam_prep_json`` and ``transcript_markdown`` in
    the same operation, so that save is intentionally ignored here. The normal
    teacher PATCH updates ``exam_prep_json`` only; that edit is revalidated and
    may move an incomplete draft to ``exam_structured`` once all critical issues
    are fixed. QuerySet.update avoids recursive signals.
    """

    changed = set(update_fields or ())
    if (
        created
        or 'exam_prep_json' not in changed
        or 'transcript_markdown' in changed
        or instance.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP
        or instance.is_published
        or instance.status not in {
            ClassCreationSession.Status.EXAM_TRANSCRIBED,
            ClassCreationSession.Status.EXAM_STRUCTURED,
        }
    ):
        return
    workflow = instance.workflow_state if isinstance(instance.workflow_state, dict) else {}
    if workflow.get('engine') not in {'page_first', PRODUCTION_ENGINE}:
        return
    if (
        workflow.get('stage') != 'ready_for_review'
        or workflow.get('readyForReview') is not True
    ):
        return
    if (
        workflow.get('engine') == PRODUCTION_ENGINE
        and not production_review_artifact_is_valid(workflow)
    ):
        return

    projection = parse_projection(instance.exam_prep_json)
    previous_audit = workflow.get('extractionAudit')
    previous_audit = previous_audit if isinstance(previous_audit, dict) else {}
    visual_contracts = previous_audit.get('visualSourceContracts')
    visual_contracts = visual_contracts if isinstance(visual_contracts, dict) else {}
    preserved_visual_audit = {
        key: previous_audit[key]
        for key in ('visualAssetRegistry', 'visualPipeline')
        if isinstance(previous_audit.get(key), dict)
    }
    recomputed_audit = audit_page_first_projection(
        projection,
        visual_source_contracts=visual_contracts,
    )
    audit = {**previous_audit, **recomputed_audit}
    if visual_contracts:
        audit['visualSourceContracts'] = visual_contracts
    audit.update(preserved_visual_audit)
    failed_page_numbers = workflow.get('failedPageNumbers') or []
    audit = retain_failed_page_evidence(audit, failed_page_numbers)
    passed = audit.get('status') == 'passed'
    if workflow.get('engine') == PRODUCTION_ENGINE:
        # Anti-forgery only (all 5 stages ran); publishing is always allowed once
        # the audit passes the narrow review-blocking gate — owner policy `همیشه مجاز`.
        passed = passed and production_review_artifact_is_valid(
            {
                **workflow,
                'publicationBlocked': False,
                'extractionAudit': audit,
            },
        )
    warnings: list[str] = []
    critical_count = int(audit.get('criticalIssueCount') or 0)
    if critical_count:
        warnings.append(
            f'{critical_count} مورد بحرانی در محتوای ویرایش‌شده باقی مانده است.'
        )
    gap_count = sum(
        len(values)
        for values in (audit.get('questionNumberGaps') or {}).values()
        if isinstance(values, list)
    )
    if gap_count:
        warnings.append(f'{gap_count} شماره سؤال در توالی آزمون وجود ندارد.')
    if audit.get('failedPageNumbers'):
        pages = '، '.join(map(str, audit['failedPageNumbers']))
        warnings.append(
            f'صفحه‌های {pages} باید از روی فایل اصلی دوباره پردازش شوند.'
        )

    new_workflow = {
        **workflow,
        'stage': 'ready_for_review',
        'message': (
            'محتوای ویرایش‌شده کنترل شد و آماده انتشار است.'
            if passed
            else 'محتوای ویرایش‌شده هنوز خطای بحرانی دارد و قابل انتشار نیست.'
        ),
        'progressPercent': 100,
        'warnings': warnings,
        'readyForReview': True,
        'failedPageNumbers': list(audit.get('failedPageNumbers') or []),
        'extractionAudit': audit,
        'publicationBlocked': not passed,
    }
    new_status = (
        ClassCreationSession.Status.EXAM_STRUCTURED
        if passed
        else ClassCreationSession.Status.EXAM_TRANSCRIBED
    )
    new_transcript = render_projection_transcript(projection, audit)
    now = timezone.now()

    # Keep the object used by the current serializer response in sync with the
    # database update, so the teacher sees the revalidated status immediately.
    instance.status = new_status
    instance.transcript_markdown = new_transcript
    instance.workflow_state = new_workflow
    instance.updated_at = now
    sender.objects.filter(pk=instance.pk).update(
        status=new_status,
        transcript_markdown=new_transcript,
        workflow_state=new_workflow,
        updated_at=now,
    )


@receiver(
    pre_save,
    sender=ExamSourceDocument,
    dispatch_uid='exam_prep_v4_invalidate_on_source_contract_change',
)
def invalidate_v4_semantics_on_source_contract_change(
    sender,
    instance,
    **kwargs,
):  # noqa: ARG001
    """Make semantic output non-current before a Source Map revision changes."""

    if instance._state.adding or not instance.pk:
        return
    previous = (
        sender.objects.filter(pk=instance.pk)
        .values('classification_revision', 'source_map_fingerprint')
        .first()
    )
    if previous is None:
        return
    if (
        previous['classification_revision'] == instance.classification_revision
        and previous['source_map_fingerprint'] == instance.source_map_fingerprint
    ):
        return
    supersede_document_semantic_outputs(document_id=instance.pk)


@receiver(
    post_save,
    sender=ExamSourceBlock,
    dispatch_uid='exam_prep_v4_invalidate_on_new_block_revision',
)
def invalidate_v4_semantics_on_new_block_revision(
    sender,
    instance,
    created,
    **kwargs,
):  # noqa: ARG001
    """Invalidate record and match sets when a replacement block set is created."""

    if not created or instance.status != ExamSourceBlock.Status.ACCEPTED:
        return
    supersede_document_semantic_outputs(document_id=instance.document_id)


@receiver(
    post_save,
    sender=ExamQuestionRecord,
    dispatch_uid='exam_prep_v4_invalidate_matches_on_question_revision',
)
def invalidate_v4_matches_on_question_revision(
    sender,
    instance,
    created,
    **kwargs,
):  # noqa: ARG001
    """A new accepted question revision makes prior matches non-current."""

    if not created or instance.lifecycle_status != ExamExtractionLifecycle.ACCEPTED:
        return
    supersede_match_decisions_for_document(document_id=instance.document_id)


@receiver(
    post_save,
    sender=ExamAnswerSolutionRecord,
    dispatch_uid='exam_prep_v4_invalidate_matches_on_answer_revision',
)
def invalidate_v4_matches_on_answer_revision(
    sender,
    instance,
    created,
    **kwargs,
):  # noqa: ARG001
    """A new accepted answer-solution revision makes prior matches non-current."""

    if not created or instance.lifecycle_status != ExamExtractionLifecycle.ACCEPTED:
        return
    supersede_match_decisions_for_document(document_id=instance.document_id)
