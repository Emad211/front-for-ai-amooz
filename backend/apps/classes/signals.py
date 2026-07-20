from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.storage_backends import delete_answer_source_file

from .models import StudentExerciseAnswerAsset

@receiver(post_delete, sender=StudentExerciseAnswerAsset)
def delete_answer_asset_blob(sender, instance, **kwargs):  # noqa: ARG001
    name = instance.file.name
    if not name:
        return

    def delete_after_commit() -> None:
        delete_answer_source_file(name)

    transaction.on_commit(delete_after_commit)
