from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from core.storage_backends import delete_answer_source_file

from .models import (
    ExamPrepExtractionArtifact,
    ExamPrepVisualAsset,
    StudentExerciseAnswerAsset,
)
from .models_v4 import ExamSourceDocument, ExamSourcePage
from .models_v4_blocks import ExamSourceBlock
from .models_v4_records import (
    ExamAnswerSolutionRecord,
    ExamExtractionLifecycle,
    ExamQuestionRecord,
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
