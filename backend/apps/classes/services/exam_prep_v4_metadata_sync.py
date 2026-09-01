"""Keep the visible legacy draft metadata aligned with its source-aware project."""
from __future__ import annotations

from django.db.models.signals import post_save

from apps.classes.models import ClassCreationSession
from apps.classes.models_v4 import ExamProject
from apps.classes.models_v4_bridge import ExamV4SessionBridge


_DISPATCH_UID = 'exam-prep-v4-session-metadata-sync-v1'


def _sync_session_metadata(sender, instance: ClassCreationSession, **_kwargs) -> None:
    if instance.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP:
        return
    bridge = (
        ExamV4SessionBridge.objects.filter(session_id=instance.id)
        .values_list('project_id', flat=True)
        .first()
    )
    if bridge is None:
        return
    ExamProject.objects.filter(id=bridge, teacher_id=instance.teacher_id).update(
        title=instance.title,
        description=instance.description,
    )


def install() -> None:
    post_save.connect(
        _sync_session_metadata,
        sender=ClassCreationSession,
        weak=False,
        dispatch_uid=_DISPATCH_UID,
    )


__all__ = ['install']
