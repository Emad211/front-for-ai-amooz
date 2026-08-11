from __future__ import annotations

import io
from datetime import timedelta

import pytest
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from model_bakery import baker
from PIL import Image
from rest_framework.test import APIClient

from apps.classes import tasks_exam_prep
from apps.classes.models import ClassCreationSession
from apps.classes.services.exam_prep_mistral_artifacts import (
    cleanup_session_private_artifacts,
)
from apps.classes.services.exam_prep_mistral_ocr_transport import (
    OCR4Chunk,
    PrivateOCRCheckpointStore,
)
from apps.classes.services.exam_prep_mistral_production import PRODUCTION_ENGINE
from apps.classes.services.exam_prep_mistral_visuals import (
    visual_storage_path_matches_source,
)
from apps.classes.services.exam_prep_pipeline import (
    ExamPrepPipelineCancelled,
    ExamPrepPipelineResult,
    NoExamQuestionsFound,
)


pytestmark = pytest.mark.django_db


class _MemoryTreeStorage:
    def __init__(self, names: set[str]):
        self.names = set(names)

    def listdir(self, prefix: str):
        base = f"{prefix.rstrip('/')}/"
        children = [name[len(base):] for name in self.names if name.startswith(base)]
        if not children:
            raise FileNotFoundError(prefix)
        directories: set[str] = set()
        files: set[str] = set()
        for child in children:
            head, separator, _tail = child.partition("/")
            (directories if separator else files).add(head)
        return sorted(directories), sorted(files)

    def delete(self, name: str):
        self.names.discard(name)


class _UndeletableMemoryTreeStorage(_MemoryTreeStorage):
    def delete(self, name: str):
        return None


@pytest.fixture
def source_storage(tmp_path, monkeypatch):
    storage = FileSystemStorage(location=tmp_path / "media")
    monkeypatch.setattr(
        ClassCreationSession._meta.get_field("source_file"),
        "storage",
        storage,
    )
    return storage


def _pdf_upload() -> SimpleUploadedFile:
    image = Image.new("RGB", (80, 100), "white")
    output = io.BytesIO()
    image.save(output, format="PDF")
    return SimpleUploadedFile("exam.pdf", output.getvalue(), content_type="application/pdf")


def _session() -> ClassCreationSession:
    teacher = baker.make("accounts.User", role="TEACHER")
    return ClassCreationSession.objects.create(
        teacher=teacher,
        title="آزمون",
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        source_type=ClassCreationSession.SourceType.PDF,
        source_file=_pdf_upload(),
        status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
        workflow_state={"engine": PRODUCTION_ENGINE, "extractionAudit": {}},
    )


def _result() -> ExamPrepPipelineResult:
    return ExamPrepPipelineResult(
        projection={"exam_prep": {"questions": []}},
        issues=[],
        page_count=1,
        question_count=0,
        questions_needing_review=0,
        publication_ready=True,
        transcript_markdown="# آزمون",
        extraction_audit={"status": "passed", "visualAssetsAttached": 0},
        model="mistral-ocr-4-0",
    )


def _auth(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_session_prefix_cleanup_isolated_from_another_session():
    source_sha = "a" * 64
    contract = "b" * 64
    session_101 = {
        f"exam-prep/source/visuals/v1/session-101/{source_sha}/crop.png",
        (
            "exam-prep/source/ocr4-checkpoints/v1/session-101/"
            f"{source_sha}/{contract}/chunk-000.json"
        ),
    }
    session_202 = {
        f"exam-prep/source/visuals/v1/session-202/{source_sha}/crop.png",
        (
            "exam-prep/source/ocr4-checkpoints/v1/session-202/"
            f"{source_sha}/{contract}/chunk-000.json"
        ),
    }
    storage = _MemoryTreeStorage(session_101 | session_202)

    assert cleanup_session_private_artifacts(101, storage=storage) is True

    assert storage.names == session_202


def test_session_prefix_cleanup_fails_closed_when_a_blob_remains():
    source_sha = "a" * 64
    owned = {
        f"exam-prep/source/visuals/v1/session-101/{source_sha}/crop.png",
    }
    storage = _UndeletableMemoryTreeStorage(owned)

    assert cleanup_session_private_artifacts(101, storage=storage) is False
    assert storage.names == owned


def test_ocr_checkpoint_names_are_stable_per_session_and_do_not_cross_sessions():
    chunk = OCR4Chunk(
        index=0,
        physical_pages=(1,),
        data=b"%PDF checkpoint",
        sha256="c" * 64,
    )
    kwargs = {
        "source_sha256": "a" * 64,
        "contract_fingerprint": "b" * 64,
        "chunk": chunk,
    }

    first = PrivateOCRCheckpointStore(namespace="session-101")._name(**kwargs)
    retry = PrivateOCRCheckpointStore(namespace="session-101")._name(**kwargs)
    second = PrivateOCRCheckpointStore(namespace="session-202")._name(**kwargs)

    assert first == retry
    assert first != second
    assert "/session-101/" in first
    assert "/session-202/" in second


def test_namespaced_visual_path_is_bound_to_its_exact_source_hash():
    source_sha = "a" * 64
    path = f"exam-prep/source/visuals/v1/session-101/{source_sha}/crop.png"

    assert visual_storage_path_matches_source(path, source_sha256=source_sha) is True
    assert visual_storage_path_matches_source(path, source_sha256="b" * 64) is False


def test_cancelled_task_cleans_visuals_and_checkpoints(source_storage, monkeypatch):
    session = _session()
    cleanup_calls = []
    monkeypatch.setattr(
        tasks_exam_prep,
        "run_exam_prep_mistral_pipeline",
        lambda **_kwargs: (_ for _ in ()).throw(
            ExamPrepPipelineCancelled("cancelled during Stage-3")
        ),
    )
    monkeypatch.setattr(
        tasks_exam_prep,
        "cleanup_session_private_artifacts",
        lambda session_id, **kwargs: cleanup_calls.append((session_id, kwargs)) or True,
    )

    result = tasks_exam_prep.process_exam_prep_pdf_session.run(session.id)

    assert result["status"] == "cancelled"
    assert cleanup_calls == [
        (session.id, {"include_visuals": True, "include_checkpoints": True})
    ]


def test_terminal_failure_cleans_visuals_and_checkpoints(source_storage, monkeypatch):
    session = _session()
    cleanup_calls = []
    monkeypatch.setattr(
        tasks_exam_prep,
        "run_exam_prep_mistral_pipeline",
        lambda **_kwargs: (_ for _ in ()).throw(NoExamQuestionsFound("no questions")),
    )
    monkeypatch.setattr(
        tasks_exam_prep,
        "cleanup_session_private_artifacts",
        lambda session_id, **kwargs: cleanup_calls.append((session_id, kwargs)) or True,
    )

    with pytest.raises(NoExamQuestionsFound):
        tasks_exam_prep.process_exam_prep_pdf_session.run(session.id)

    assert cleanup_calls == [
        (session.id, {"include_visuals": True, "include_checkpoints": True})
    ]


def test_success_cleans_checkpoint_but_preserves_durable_visuals(source_storage, monkeypatch):
    session = _session()
    cleanup_calls = []
    monkeypatch.setattr(
        tasks_exam_prep,
        "run_exam_prep_mistral_pipeline",
        lambda **_kwargs: _result(),
    )
    monkeypatch.setattr(
        tasks_exam_prep,
        "cleanup_session_private_artifacts",
        lambda session_id, **kwargs: cleanup_calls.append((session_id, kwargs)) or True,
    )

    result = tasks_exam_prep.process_exam_prep_pdf_session.run(session.id)

    assert result["status"] == "ready_for_review"
    assert cleanup_calls == [
        (session.id, {"include_visuals": False, "include_checkpoints": True})
    ]


def test_delete_cleans_unpersisted_session_namespace(source_storage, monkeypatch):
    session = _session()
    cleanup_calls = []
    monkeypatch.setattr(
        "apps.classes.views.cleanup_session_private_artifacts",
        lambda session_id, **kwargs: cleanup_calls.append((session_id, kwargs)) or True,
    )
    monkeypatch.setattr("apps.classes.views._cancel_session_pipeline", lambda _session: None)

    response = _auth(session.teacher).delete(
        f"/api/classes/exam-prep-sessions/{session.id}/"
    )

    assert response.status_code == 204
    assert cleanup_calls == [
        (session.id, {"include_visuals": True, "include_checkpoints": True})
    ]
    assert not ClassCreationSession.objects.filter(id=session.id).exists()


def test_stale_worker_reaper_cleans_hard_crash_artifacts(source_storage, monkeypatch):
    from apps.classes import tasks
    from apps.classes.services import exam_prep_mistral_artifacts

    session = _session()
    ClassCreationSession.objects.filter(id=session.id).update(
        updated_at=timezone.now() - timedelta(hours=3)
    )
    cleanup_calls = []
    monkeypatch.setattr(
        exam_prep_mistral_artifacts,
        "cleanup_session_private_artifacts",
        lambda session_id, **kwargs: cleanup_calls.append((session_id, kwargs)) or True,
    )

    tasks.cleanup_stale_sessions.run()

    assert (
        session.id,
        {"include_visuals": True, "include_checkpoints": True},
    ) in cleanup_calls
