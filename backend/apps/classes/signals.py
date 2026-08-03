from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.storage_backends import delete_answer_source_file

from .models import (
    ExamPrepExtractionArtifact,
    ExamPrepVisualAsset,
    StudentExerciseAnswerAsset,
)
from .models_v4 import ExamSourceDocument, ExamSourcePage


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
