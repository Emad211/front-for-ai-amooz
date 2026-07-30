import json
import io
import os
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.utils import timezone
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models import (
    ClassCreationSession,
    ExamPrepExtractionArtifact,
    ExamPrepExtractionUnit,
    ExamPrepVisualAsset,
)
from apps.classes.services import exam_prep_v3
from apps.classes.services import exam_prep_inventory_pipeline
from apps.classes.services.transcription import TranscriptionAborted
from apps.classes import tasks as class_tasks
from apps.classes.services.schemas import (
    ExamPrepAnswerInventoryOutput,
    ExamPrepPageManifestOutput,
    ExamPrepQuestionInventoryOutput,
)
from apps.classes.tasks import cleanup_stale_sessions


pytestmark = pytest.mark.django_db


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _projection():
    return {
        "exam_prep": {
            "title": "آزمون",
            "questions": [
                {
                    "question_id": "q-1",
                    "question_text_markdown": "صورت سؤال",
                    "options": [],
                    "correct_option_label": None,
                    "final_answer_markdown": "پاسخ",
                    "teacher_solution_markdown": "",
                    "visuals": [],
                }
            ],
        }
    }


def _v3_session(teacher, *, audit=None):
    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        exam_prep_json=json.dumps(_projection(), ensure_ascii=False),
    )
    artifact = ExamPrepExtractionArtifact.objects.create(
        session=session,
        pipeline_version=3,
        status=ExamPrepExtractionArtifact.Status.READY,
        audit=audit
        or {
            "status": "passed",
            "criticalIssueCount": 0,
            "issues": [],
            "questionCount": 1,
        },
    )
    return session, artifact


@pytest.mark.unit
def test_quality_contract_rejects_successful_but_repeated_output(monkeypatch):
    monkeypatch.setenv("PDF_OCR_DUPLICATE_LINE_RATIO_LIMIT", "0.35")
    text = "\n".join(["سؤال 78 پاسخ الف"] * 25)

    report = exam_prep_v3.quality_report(text, finish_reason="stop")

    assert report["hardIssues"] == []
    assert report["softIssues"] == ["duplicate_lines"]
    assert report["accepted"] is False


def test_missing_phase_acknowledgement_marks_structured_unit_retryable(
    monkeypatch,
):
    teacher = baker.make("accounts.User", role="TEACHER")
    _session, artifact = _v3_session(teacher)

    def fake_call(*, schema, blocks, phase, chunk_index, **_kwargs):
        ExamPrepExtractionUnit.objects.create(
            artifact=artifact,
            stage=phase,
            unit_key=f"{phase}:chunk:{chunk_index}",
            revision=artifact.revision,
            status=ExamPrepExtractionUnit.Status.ACCEPTED,
            source_page=min(block["page_number"] for block in blocks),
            source_segment=chunk_index,
            input_fingerprint=f"{phase[0]}" * 64,
        )
        block_ids = [block["block_id"] for block in blocks]
        if schema is ExamPrepPageManifestOutput:
            return schema.model_validate({
                "title": "آزمون",
                "pages": [
                    {
                        "page_number": block["page_number"],
                        "section_type": "mixed",
                        "section_key": "",
                        "question_numbers": ["1"],
                        "answer_numbers": ["1"],
                        "confidence": 0.9,
                    }
                    for block in blocks
                ],
            })
        if schema is ExamPrepQuestionInventoryOutput:
            return schema.model_validate({
                "processed_source_block_ids": block_ids[:1],
                "questions": [{
                    "source_question_number": "1",
                    "section_key": "",
                    "source_pages": [blocks[0]["page_number"]],
                    "source_block_ids": block_ids[:1],
                    "block_order": 0,
                    "question_text_markdown": "سؤال اول",
                    "options": [],
                    "confidence": 1,
                }],
            })
        return ExamPrepAnswerInventoryOutput.model_validate({
            "processed_source_block_ids": block_ids,
            "answers": [{
                "source_question_number": "1",
                "section_key": "",
                "source_pages": [blocks[0]["page_number"]],
                "source_block_ids": block_ids[:1],
                "block_order": 0,
                "final_answer_markdown": "پاسخ",
                "confidence": 1,
            }],
        })

    monkeypatch.setattr(
        exam_prep_inventory_pipeline,
        "_call",
        fake_call,
    )
    monkeypatch.setattr(
        exam_prep_inventory_pipeline,
        "_select_model",
        lambda: "test-model",
    )
    monkeypatch.setattr(
        exam_prep_inventory_pipeline,
        "preferred_provider",
        lambda: "test-provider",
    )

    _, _, audit, _, _ = (
        exam_prep_inventory_pipeline.extract_exam_prep_inventory(
            transcript_markdown=(
                "## صفحه 1\nسؤال ۱ چیست؟ پاسخ: الف\n\n"
                "## صفحه 2\nسؤال ۲ چیست؟ پاسخ: ب"
            ),
            artifact=artifact,
        )
    )

    question_unit = artifact.units.get(
        stage=ExamPrepExtractionUnit.Stage.QUESTIONS
    )
    answer_unit = artifact.units.get(
        stage=ExamPrepExtractionUnit.Stage.ANSWERS
    )
    assert question_unit.status == ExamPrepExtractionUnit.Status.RETRYABLE
    assert question_unit.error_code == "unprocessed_source_block"
    assert answer_unit.status == ExamPrepExtractionUnit.Status.ACCEPTED
    assert audit["status"] == "needs_review"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "finish_reason", "native_length", "expected"),
    [
        ("", "stop", 0, "empty_output"),
        ("متن معتبر", "length", 0, "incomplete_finish_reason"),
        ("الف" * 24_001, "stop", 0, "absolute_length_limit"),
        ("الف" * 301, "stop", 100, "native_text_ratio"),
    ],
    ids=["empty", "truncated", "absolute-limit", "native-ratio"],
)
def test_quality_contract_rejects_each_required_anomaly(
    monkeypatch, text, finish_reason, native_length, expected
):
    monkeypatch.setenv("PDF_OCR_MAX_OUTPUT_CHARS_PER_PAGE", "24000")
    monkeypatch.setenv("PDF_OCR_NATIVE_RATIO_LIMIT", "3")

    report = exam_prep_v3.quality_report(
        text,
        finish_reason=finish_reason,
        native_text_length=native_length,
    )

    assert expected in [*report["hardIssues"], *report["softIssues"]]


@pytest.mark.unit
def test_long_non_repeated_output_is_not_rejected_by_length_alone():
    text = "\n".join(f"سطر یکتای {index} با محتوای معتبر" for index in range(500))

    report = exam_prep_v3.quality_report(text, finish_reason="stop")

    assert report["accepted"] is True
    assert report["hardIssues"] == []
    assert report["softIssues"] == []


@pytest.mark.unit
def test_numeric_jaccard_detects_unstable_question_numbers():
    assert exam_prep_v3.numeric_jaccard("سؤال 78 پاسخ 4", "سؤال 78 پاسخ 4") == 1
    assert exam_prep_v3.numeric_jaccard("سؤال 78 پاسخ 4", "سؤال 87 پاسخ 3") == 0


def test_suspicious_ocr_gets_one_retry_then_is_quarantined(monkeypatch):
    teacher = baker.make("accounts.User", role="TEACHER")
    _, artifact = _v3_session(teacher)
    calls = []

    def fake_call(**_kwargs):
        calls.append(1)
        return SimpleNamespace(
            text="\n".join(["سؤال 78 پاسخ 4"] * 25),
            provider="test",
            model="vision",
            response_id=f"r-{len(calls)}",
            finish_reason="stop",
        )

    monkeypatch.setattr(exam_prep_v3, "_ocr_call", fake_call)
    outcome = exam_prep_v3.process_ocr_page(
        artifact_id=artifact.id,
        image=b"image",
        page_number=10,
        native_text_length=0,
    )

    assert len(calls) == 2
    assert outcome.status == ExamPrepExtractionUnit.Status.QUARANTINED
    assert outcome.text == ""
    unit = artifact.units.get(stage="ocr", unit_key="page:10", revision=1)
    assert unit.attempt_count == 2
    assert unit.output_payload == {}


def test_accepted_ocr_is_reused_without_provider_call(monkeypatch):
    teacher = baker.make("accounts.User", role="TEACHER")
    _, artifact = _v3_session(teacher)
    result = SimpleNamespace(
        text="سؤال 78\nپاسخ الف",
        provider="test",
        model="vision",
        response_id="r-1",
        finish_reason="stop",
    )
    calls = []
    monkeypatch.setattr(
        exam_prep_v3,
        "_ocr_call",
        lambda **_kwargs: calls.append(1) or result,
    )

    first = exam_prep_v3.process_ocr_page(
        artifact_id=artifact.id,
        image=b"same-image",
        page_number=1,
        native_text_length=0,
    )
    second = exam_prep_v3.process_ocr_page(
        artifact_id=artifact.id,
        image=b"same-image",
        page_number=1,
        native_text_length=0,
    )

    assert first.status == second.status == ExamPrepExtractionUnit.Status.ACCEPTED
    assert first.text == second.text
    assert len(calls) == 1


def test_live_unit_lease_cannot_be_stolen_and_stale_lease_can_be_reclaimed(
    monkeypatch,
):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "10")
    teacher = baker.make("accounts.User", role="TEACHER")
    _, artifact = _v3_session(teacher)

    unit, claimed = exam_prep_v3._claim_unit(
        artifact_id=artifact.id,
        page_number=4,
        fingerprint="d" * 64,
        lease="first-worker",
    )
    assert claimed is True

    same_unit, duplicate_claimed = exam_prep_v3._claim_unit(
        artifact_id=artifact.id,
        page_number=4,
        fingerprint="d" * 64,
        lease="second-worker",
    )
    assert same_unit.id == unit.id
    assert duplicate_claimed is False
    same_unit.refresh_from_db()
    assert same_unit.attempt_count == 1
    assert same_unit.processing_task_id == "first-worker"

    ExamPrepExtractionUnit.objects.filter(id=unit.id).update(
        heartbeat_at=timezone.now() - timedelta(minutes=3)
    )
    reclaimed, stale_claimed = exam_prep_v3._claim_unit(
        artifact_id=artifact.id,
        page_number=4,
        fingerprint="d" * 64,
        lease="replacement-worker",
    )
    assert stale_claimed is True
    assert reclaimed.attempt_count == 2
    assert reclaimed.processing_task_id == "replacement-worker"


def test_v3_publish_requires_review_bound_to_current_projection(monkeypatch):
    teacher = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(teacher)
    monkeypatch.setattr(
        "apps.classes.views.send_publish_sms_task.delay",
        lambda *_args, **_kwargs: None,
    )
    url = f"/api/classes/exam-prep-sessions/{session.id}/publish/"

    blocked = _auth(teacher).post(url)
    assert blocked.status_code == 409
    assert blocked.data["code"] == "teacher_extraction_confirmation_required"

    fingerprint = exam_prep_v3.projection_fingerprint(session.exam_prep_json)
    artifact.teacher_reviewed_at = timezone.now()
    artifact.teacher_reviewed_by = teacher
    artifact.reviewed_revision = artifact.revision
    artifact.reviewed_projection_fingerprint = fingerprint
    artifact.save()

    published = _auth(teacher).post(url)
    assert published.status_code == 200
    artifact.refresh_from_db()
    assert artifact.source_retain_until is not None


def test_review_confirmation_is_owner_scoped_and_rejects_stale_revision():
    owner = baker.make("accounts.User", role="TEACHER")
    other = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(owner)
    url = f"/api/classes/exam-prep-sessions/{session.id}/extraction-review/confirm/"
    payload = {
        "artifactRevision": artifact.revision,
        "projectionFingerprint": exam_prep_v3.projection_fingerprint(
            session.exam_prep_json
        ),
    }

    assert _auth(other).post(url, payload, format="json").status_code == 404
    stale = _auth(owner).post(
        url,
        {**payload, "artifactRevision": artifact.revision + 1},
        format="json",
    )
    assert stale.status_code == 409

    accepted = _auth(owner).post(url, payload, format="json")
    assert accepted.status_code == 200
    artifact.refresh_from_db()
    assert artifact.reviewed_revision == artifact.revision
    assert artifact.teacher_reviewed_by_id == owner.id


def test_teacher_edit_advances_revision_and_invalidates_confirmation():
    teacher = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(teacher)
    artifact.teacher_reviewed_at = timezone.now()
    artifact.teacher_reviewed_by = teacher
    artifact.reviewed_revision = 1
    artifact.reviewed_projection_fingerprint = exam_prep_v3.projection_fingerprint(
        session.exam_prep_json
    )
    artifact.save()
    ExamPrepExtractionUnit.objects.create(
        artifact=artifact,
        stage=ExamPrepExtractionUnit.Stage.OCR,
        unit_key="page:1",
        revision=1,
        status=ExamPrepExtractionUnit.Status.ACCEPTED,
        source_page=1,
        input_fingerprint="a" * 64,
        output_payload={"text": "متن"},
    )

    response = _auth(teacher).patch(
        f"/api/classes/exam-prep-sessions/{session.id}/",
        {"exam_prep_json": _projection()},
        format="json",
    )

    assert response.status_code == 200
    artifact.refresh_from_db()
    assert artifact.revision == 2
    assert artifact.teacher_reviewed_at is None
    assert artifact.reviewed_revision is None
    assert artifact.units.filter(revision=2, unit_key="page:1").exists()
    publish = _auth(teacher).post(
        f"/api/classes/exam-prep-sessions/{session.id}/publish/"
    )
    assert publish.status_code == 409
    session.refresh_from_db()
    assert session.is_published is False


def test_exam_content_cannot_be_edited_while_pipeline_is_processing():
    teacher = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(teacher)
    session.status = ClassCreationSession.Status.EXAM_STRUCTURING
    session.save(update_fields=["status", "updated_at"])

    response = _auth(teacher).patch(
        f"/api/classes/exam-prep-sessions/{session.id}/",
        {"exam_prep_json": _projection()},
        format="json",
    )

    assert response.status_code == 409
    artifact.refresh_from_db()
    assert artifact.revision == 1


def test_retry_single_unit_advances_revision_and_is_owner_scoped(monkeypatch):
    owner = baker.make("accounts.User", role="TEACHER")
    other = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(owner)
    unit = ExamPrepExtractionUnit.objects.create(
        artifact=artifact,
        stage=ExamPrepExtractionUnit.Stage.OCR,
        unit_key="page:10",
        revision=1,
        status=ExamPrepExtractionUnit.Status.QUARANTINED,
        source_page=10,
        input_fingerprint="b" * 64,
    )
    dispatched = []
    monkeypatch.setattr(
        "apps.classes.views._dispatch_pipeline_task",
        lambda current, task: dispatched.append((current.id, task.name)),
    )
    url = (
        f"/api/classes/exam-prep-sessions/{session.id}/"
        f"extraction-units/{unit.id}/retry/"
    )

    assert _auth(other).post(
        url, {"artifactRevision": 1}, format="json"
    ).status_code == 404
    response = _auth(owner).post(
        url, {"artifactRevision": 1}, format="json"
    )

    assert response.status_code == 202
    artifact.refresh_from_db()
    assert artifact.revision == 2
    assert artifact.units.filter(
        revision=2,
        unit_key="page:10",
        status=ExamPrepExtractionUnit.Status.PENDING,
    ).exists()
    assert dispatched and dispatched[0][0] == session.id


def test_retry_structured_unit_advances_revision(monkeypatch):
    owner = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(owner)
    unit = ExamPrepExtractionUnit.objects.create(
        artifact=artifact,
        stage=ExamPrepExtractionUnit.Stage.QUESTIONS,
        unit_key="questions:chunk:0",
        revision=1,
        status=ExamPrepExtractionUnit.Status.RETRYABLE,
        source_page=2,
        source_segment=0,
        input_fingerprint="f" * 64,
        quality_report={"missingSourceBlockIds": ["page:2:0"]},
    )
    dispatched = []
    monkeypatch.setattr(
        "apps.classes.views._dispatch_pipeline_task",
        lambda current, task: dispatched.append((current.id, task.name)),
    )

    response = _auth(owner).post(
        (
            f"/api/classes/exam-prep-sessions/{session.id}/"
            f"extraction-units/{unit.id}/retry/"
        ),
        {"artifactRevision": 1},
        format="json",
    )

    assert response.status_code == 202
    artifact.refresh_from_db()
    assert artifact.revision == 2
    assert artifact.units.filter(
        revision=2,
        stage=ExamPrepExtractionUnit.Stage.QUESTIONS,
        unit_key="questions:chunk:0",
        status=ExamPrepExtractionUnit.Status.PENDING,
    ).exists()
    assert dispatched and dispatched[0][0] == session.id


def test_extraction_source_is_private_and_owner_scoped(monkeypatch):
    owner = baker.make("accounts.User", role="TEACHER")
    other = baker.make("accounts.User", role="TEACHER")
    student = baker.make("accounts.User", role="STUDENT")
    session, artifact = _v3_session(owner)
    unit = ExamPrepExtractionUnit.objects.create(
        artifact=artifact,
        stage=ExamPrepExtractionUnit.Stage.OCR,
        unit_key="page:3",
        revision=1,
        status=ExamPrepExtractionUnit.Status.QUARANTINED,
        source_page=3,
        input_fingerprint="e" * 64,
    )
    artifact.source_blocks = [
        {
            "pageNumber": 3,
            "storageName": "private/exam/page-3.png",
            "contentType": "image/png",
        }
    ]
    artifact.save(update_fields=["source_blocks", "updated_at"])

    class FakeStorage:
        @staticmethod
        def open(name, mode):
            assert name == "private/exam/page-3.png"
            assert mode == "rb"
            return io.BytesIO(b"private-page")

    monkeypatch.setattr(
        "apps.classes.views.storages",
        {"answer_sources": FakeStorage()},
    )
    url = (
        f"/api/classes/exam-prep-sessions/{session.id}/"
        f"extraction-units/{unit.id}/source/"
    )

    assert APIClient().get(url).status_code == 401
    assert _auth(student).get(url).status_code == 403
    assert _auth(other).get(url).status_code == 404
    response = _auth(owner).get(url)
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    assert b"".join(response.streaming_content) == b"private-page"


@pytest.mark.parametrize(
    "path",
    [
        "/media/exam-prep/source/private-page.png",
        "/media/exam-prep/visuals/source/private-crop.png",
        "/media/exam-prep/visuals/generated/private-candidate.png",
    ],
)
def test_generic_media_routes_never_serve_private_exam_artifacts(
    monkeypatch,
    path,
):
    opened = []

    def fail_if_opened(name, mode="rb"):
        opened.append((name, mode))
        raise AssertionError("Private exam media must not reach generic storage.")

    monkeypatch.setattr(
        "django.core.files.storage.default_storage.open",
        fail_if_opened,
    )

    response = APIClient().get(path)

    assert response.status_code == 404
    assert opened == []


def test_delete_v3_session_removes_recorded_private_sources_once(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    teacher = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(teacher)
    artifact.source_blocks = [
        {"pageNumber": 1, "storageName": "private/exam/page-1.png"},
        {"pageNumber": 2, "storageName": "private/exam/page-2.png"},
    ]
    artifact.save(update_fields=["source_blocks", "updated_at"])
    deleted = []
    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )
    monkeypatch.setattr(
        "apps.classes.signals.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = _auth(teacher).delete(
            f"/api/classes/exam-prep-sessions/{session.id}/"
        )

    assert response.status_code == 204
    assert sorted(deleted) == [
        "private/exam/page-1.png",
        "private/exam/page-2.png",
    ]
    assert not ClassCreationSession.objects.filter(id=session.id).exists()


def test_delete_v3_session_removes_visual_source_and_generated_blobs(
    monkeypatch,
):
    teacher = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(teacher)
    asset = ExamPrepVisualAsset.objects.create(
        artifact=artifact,
        asset_key="visual-delete",
        question_key="q-1",
        role=ExamPrepVisualAsset.Role.QUESTION,
        source_kind=ExamPrepVisualAsset.SourceKind.PDF_PAGE,
        source_file="exam-prep/visuals/source/source.png",
        source_sha256="a" * 64,
        generated_file="exam-prep/visuals/generated/generated.png",
        generated_sha256="b" * 64,
        fingerprint="c" * 64,
    )
    deleted = []
    monkeypatch.setattr(
        "apps.classes.services.exam_prep_visuals.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )

    response = _auth(teacher).delete(
        f"/api/classes/exam-prep-sessions/{session.id}/"
    )

    assert response.status_code == 204
    assert deleted == [
        "exam-prep/visuals/generated/generated.png",
        "exam-prep/visuals/source/source.png",
    ]
    assert not ExamPrepVisualAsset.objects.filter(id=asset.id).exists()
    assert not ClassCreationSession.objects.filter(id=session.id).exists()


def test_delete_v3_session_preserves_rows_when_any_visual_blob_delete_fails(
    monkeypatch,
):
    teacher = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(teacher)
    asset = ExamPrepVisualAsset.objects.create(
        artifact=artifact,
        asset_key="visual-delete-failure",
        question_key="q-1",
        role=ExamPrepVisualAsset.Role.QUESTION,
        source_kind=ExamPrepVisualAsset.SourceKind.PDF_PAGE,
        source_file="exam-prep/visuals/source/source.png",
        source_sha256="d" * 64,
        generated_file="exam-prep/visuals/generated/generated.png",
        generated_sha256="e" * 64,
        fingerprint="f" * 64,
    )
    attempted = []

    def delete_visual(name):
        attempted.append(name)
        return name.endswith("source.png")

    monkeypatch.setattr(
        "apps.classes.services.exam_prep_visuals.delete_answer_source_file",
        delete_visual,
    )

    response = _auth(teacher).delete(
        f"/api/classes/exam-prep-sessions/{session.id}/"
    )

    assert response.status_code == 503
    assert attempted == [
        "exam-prep/visuals/generated/generated.png",
        "exam-prep/visuals/source/source.png",
    ]
    assert ExamPrepVisualAsset.objects.filter(id=asset.id).exists()
    assert ClassCreationSession.objects.filter(id=session.id).exists()


def test_delete_v2_session_removes_recorded_private_sources(monkeypatch):
    teacher = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(teacher)
    artifact.pipeline_version = 2
    artifact.source_blocks = [
        {"pageNumber": 1, "storageName": "private/exam/v2-page-1.png"},
    ]
    artifact.save(update_fields=[
        "pipeline_version",
        "source_blocks",
        "updated_at",
    ])
    deleted = []
    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )

    response = _auth(teacher).delete(
        f"/api/classes/exam-prep-sessions/{session.id}/"
    )

    assert response.status_code == 204
    assert deleted == ["private/exam/v2-page-1.png"]
    assert not ClassCreationSession.objects.filter(id=session.id).exists()


def test_delete_v3_session_attempts_all_sources_and_preserves_row_on_failure(
    monkeypatch,
):
    teacher = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(teacher)
    artifact.source_blocks = [
        {"pageNumber": 1, "storageName": "private/exam/page-1.png"},
        {"pageNumber": 2, "storageName": "private/exam/page-2.png"},
    ]
    artifact.save(update_fields=["source_blocks", "updated_at"])
    attempted = []

    def delete_source(name):
        attempted.append(name)
        return name.endswith("page-2.png")

    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        delete_source,
    )

    response = _auth(teacher).delete(
        f"/api/classes/exam-prep-sessions/{session.id}/"
    )

    assert response.status_code == 503
    assert set(attempted) == {
        "private/exam/page-1.png",
        "private/exam/page-2.png",
    }
    assert ClassCreationSession.objects.filter(id=session.id).exists()


def test_cleanup_does_not_fail_session_with_active_v3_unit_heartbeat():
    teacher = baker.make("accounts.User", role="TEACHER")
    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURING,
    )
    ClassCreationSession.objects.filter(id=session.id).update(
        updated_at=timezone.now() - timedelta(hours=3)
    )
    artifact = ExamPrepExtractionArtifact.objects.create(
        session=session,
        pipeline_version=3,
        heartbeat_at=timezone.now() - timedelta(hours=3),
    )
    ExamPrepExtractionUnit.objects.create(
        artifact=artifact,
        stage=ExamPrepExtractionUnit.Stage.QUESTIONS,
        unit_key="questions:1",
        revision=1,
        status=ExamPrepExtractionUnit.Status.PROCESSING,
        input_fingerprint="c" * 64,
        processing_task_id="lease",
        heartbeat_at=timezone.now(),
    )

    cleanup_stale_sessions.run()

    session.refresh_from_db()
    assert session.status == ClassCreationSession.Status.EXAM_STRUCTURING


def test_retention_cleanup_keeps_failed_source_for_retry(monkeypatch):
    teacher = baker.make("accounts.User", role="TEACHER")
    session, artifact = _v3_session(teacher)
    artifact.source_blocks = [
        {"pageNumber": 1, "storageName": "private/exam/page-1.png"},
        {"pageNumber": 2, "storageName": "private/exam/page-2.png"},
    ]
    artifact.source_retain_until = timezone.now() - timedelta(minutes=1)
    artifact.save(update_fields=[
        "source_blocks",
        "source_retain_until",
        "updated_at",
    ])

    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        lambda name: name.endswith("page-2.png"),
    )

    result = cleanup_stale_sessions.run()

    artifact.refresh_from_db()
    assert artifact.source_blocks == [
        {"pageNumber": 1, "storageName": "private/exam/page-1.png"}
    ]
    assert artifact.source_retain_until > timezone.now()
    assert result["cleaned_exam_source_count"] == 1


def test_cleanup_sweeps_bounded_orphan_source_prefix(monkeypatch, tmp_path):
    source_root = tmp_path / "exam-prep" / "source"
    (source_root / "999999").mkdir(parents=True)

    class FakeStorage:
        @staticmethod
        def path(path):
            return tmp_path / path

        @staticmethod
        def listdir(path):
            if path == "exam-prep/source/999999":
                return [], ["orphan.png"]
            raise FileNotFoundError(path)

    deleted = []
    cache.delete(class_tasks._ORPHAN_SOURCE_SWEEP_CURSOR_KEY)
    monkeypatch.setattr(
        "django.core.files.storage.storages",
        {"answer_sources": FakeStorage()},
    )
    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )

    result = cleanup_stale_sessions.run()

    assert deleted == ["exam-prep/source/999999/orphan.png"]
    assert result["cleaned_orphan_exam_source_count"] == 1


def test_cleanup_orphan_sweep_advances_beyond_live_first_page(
    monkeypatch,
    tmp_path,
):
    teacher = baker.make("accounts.User", role="TEACHER")
    sessions = ClassCreationSession.objects.bulk_create(
        [
            ClassCreationSession(
                teacher=teacher,
                title=f"live-{index}",
                status=ClassCreationSession.Status.RECAPPED,
            )
            for index in range(class_tasks._ORPHAN_SOURCE_SWEEP_LIMIT)
        ]
    )
    source_root = tmp_path / "exam-prep" / "source"
    for session in sessions:
        (source_root / str(session.id)).mkdir(parents=True, exist_ok=True)
    orphan_id = "999999999"
    (source_root / orphan_id).mkdir(parents=True)

    class FakeStorage:
        @staticmethod
        def path(path):
            return tmp_path / path

        @staticmethod
        def listdir(path):
            if path == f"exam-prep/source/{orphan_id}":
                return [], ["orphan.png"]
            return [], []

    deleted = []
    cache.delete(class_tasks._ORPHAN_SOURCE_SWEEP_CURSOR_KEY)
    monkeypatch.setattr(
        "django.core.files.storage.storages",
        {"answer_sources": FakeStorage()},
    )
    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )

    first = cleanup_stale_sessions.run()
    second = cleanup_stale_sessions.run()

    assert first["cleaned_orphan_exam_source_count"] == 0
    assert second["cleaned_orphan_exam_source_count"] == 1
    assert deleted == [f"exam-prep/source/{orphan_id}/orphan.png"]


def test_s3_orphan_listing_is_bounded_and_resumes_after_cursor():
    calls = []

    class FakeClient:
        @staticmethod
        def list_objects_v2(**kwargs):
            calls.append(kwargs)
            return {
                "CommonPrefixes": [
                    {"Prefix": "exam-prep/source/101/"},
                    {"Prefix": "exam-prep/source/not-a-session/"},
                ]
            }

    storage = SimpleNamespace(
        bucket_name="private-media",
        connection=SimpleNamespace(meta=SimpleNamespace(client=FakeClient())),
    )

    result = class_tasks._list_exam_source_session_dirs(storage, after="100")

    assert result == ["101"]
    assert calls == [{
        "Bucket": "private-media",
        "Prefix": "exam-prep/source/",
        "Delimiter": "/",
        "MaxKeys": class_tasks._ORPHAN_SOURCE_SWEEP_LIMIT,
        "StartAfter": "exam-prep/source/100/",
    }]


def test_cleanup_removes_orphan_visual_and_preserves_referenced_blob(
    monkeypatch,
    tmp_path,
):
    teacher = baker.make("accounts.User", role="TEACHER")
    _session, artifact = _v3_session(teacher)
    prefix = "exam-prep/visuals/source"
    referenced_name = f"{prefix}/referenced.png"
    orphan_name = f"{prefix}/orphan.png"
    ExamPrepVisualAsset.objects.create(
        artifact=artifact,
        asset_key="visual-reference",
        question_key="q-1",
        role=ExamPrepVisualAsset.Role.QUESTION,
        source_kind=ExamPrepVisualAsset.SourceKind.PDF_PAGE,
        source_file=referenced_name,
        source_sha256="1" * 64,
        fingerprint="2" * 64,
    )
    visual_root = tmp_path / prefix
    visual_root.mkdir(parents=True)
    (visual_root / "referenced.png").write_bytes(b"referenced")
    (visual_root / "orphan.png").write_bytes(b"orphan")
    old_timestamp = (
        timezone.now() - timedelta(hours=2)
    ).timestamp()
    os.utime(visual_root / "referenced.png", (old_timestamp, old_timestamp))
    os.utime(visual_root / "orphan.png", (old_timestamp, old_timestamp))

    class FakeStorage:
        @staticmethod
        def path(path):
            return tmp_path / path

    deleted = []
    for visual_prefix in (
        "exam-prep/visuals/source",
        "exam-prep/visuals/generated",
    ):
        cache.delete(
            f"{class_tasks._ORPHAN_VISUAL_SWEEP_CURSOR_PREFIX}:{visual_prefix}"
        )
    monkeypatch.setattr(
        "django.core.files.storage.storages",
        {"answer_sources": FakeStorage()},
    )
    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )

    result = cleanup_stale_sessions.run()

    assert deleted == [orphan_name]
    assert result["cleaned_orphan_exam_visual_count"] == 1


def test_cleanup_preserves_recent_unreferenced_visual(monkeypatch, tmp_path):
    prefix = "exam-prep/visuals/source"
    recent_name = f"{prefix}/in-flight.png"
    visual_root = tmp_path / prefix
    visual_root.mkdir(parents=True)
    (visual_root / "in-flight.png").write_bytes(b"in-flight")

    class FakeStorage:
        @staticmethod
        def path(path):
            return tmp_path / path

    deleted = []
    for visual_prefix in (
        "exam-prep/visuals/source",
        "exam-prep/visuals/generated",
    ):
        cache.delete(
            f"{class_tasks._ORPHAN_VISUAL_SWEEP_CURSOR_PREFIX}:{visual_prefix}"
        )
    monkeypatch.setattr(
        "django.core.files.storage.storages",
        {"answer_sources": FakeStorage()},
    )
    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )

    result = cleanup_stale_sessions.run()

    assert deleted == []
    assert result["cleaned_orphan_exam_visual_count"] == 0
    assert (tmp_path / recent_name).exists()


def test_visual_orphan_sweep_advances_past_full_referenced_page(
    monkeypatch,
    tmp_path,
):
    teacher = baker.make("accounts.User", role="TEACHER")
    _session, artifact = _v3_session(teacher)
    prefix = "exam-prep/visuals/source"
    root = tmp_path / prefix
    root.mkdir(parents=True)
    old_timestamp = (
        timezone.now() - timedelta(hours=2)
    ).timestamp()
    referenced_names = [
        f"{prefix}/file-{index:03}.png"
        for index in range(class_tasks._ORPHAN_SOURCE_SWEEP_LIMIT)
    ]
    ExamPrepVisualAsset.objects.bulk_create([
        ExamPrepVisualAsset(
            artifact=artifact,
            asset_key=f"visual-{index:03}",
            question_key="q-1",
            role=ExamPrepVisualAsset.Role.QUESTION,
            source_kind=ExamPrepVisualAsset.SourceKind.PDF_PAGE,
            source_file=name,
            source_sha256=f"{index:064x}",
            fingerprint=f"{index + 1000:064x}",
        )
        for index, name in enumerate(referenced_names)
    ])
    for name in referenced_names:
        path = tmp_path / name
        path.write_bytes(b"referenced")
        os.utime(path, (old_timestamp, old_timestamp))
    orphan_name = f"{prefix}/zz-orphan.png"
    orphan_path = tmp_path / orphan_name
    orphan_path.write_bytes(b"orphan")
    os.utime(orphan_path, (old_timestamp, old_timestamp))

    class FakeStorage:
        @staticmethod
        def path(path):
            return tmp_path / path

    deleted = []
    for visual_prefix in (
        "exam-prep/visuals/source",
        "exam-prep/visuals/generated",
    ):
        cache.delete(
            f"{class_tasks._ORPHAN_VISUAL_SWEEP_CURSOR_PREFIX}:{visual_prefix}"
        )
    monkeypatch.setattr(
        "django.core.files.storage.storages",
        {"answer_sources": FakeStorage()},
    )
    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )

    first = cleanup_stale_sessions.run()
    second = cleanup_stale_sessions.run()
    third = cleanup_stale_sessions.run()

    assert first["cleaned_orphan_exam_visual_count"] == 0
    assert second["cleaned_orphan_exam_visual_count"] == 1
    assert third["cleaned_orphan_exam_visual_count"] == 0
    assert deleted == [orphan_name]


def test_s3_private_file_listing_keeps_age_metadata_and_cursor():
    calls = []
    old_time = timezone.now() - timedelta(hours=2)
    recent_time = timezone.now()

    class FakeClient:
        @staticmethod
        def list_objects_v2(**kwargs):
            calls.append(kwargs)
            return {
                "Contents": [
                    {
                        "Key": "exam-prep/visuals/source/old.png",
                        "LastModified": old_time,
                    },
                    {
                        "Key": "exam-prep/visuals/source/recent.png",
                        "LastModified": recent_time,
                    },
                ]
            }

    storage = SimpleNamespace(
        bucket_name="private-media",
        connection=SimpleNamespace(meta=SimpleNamespace(client=FakeClient())),
    )

    result = class_tasks._list_private_files(
        storage,
        prefix="exam-prep/visuals/source",
        after="exam-prep/visuals/source/before.png",
    )

    assert result == [
        ("exam-prep/visuals/source/old.png", old_time.timestamp()),
        ("exam-prep/visuals/source/recent.png", recent_time.timestamp()),
    ]
    assert calls == [{
        "Bucket": "private-media",
        "Prefix": "exam-prep/visuals/source/",
        "MaxKeys": class_tasks._ORPHAN_SOURCE_SWEEP_LIMIT,
        "StartAfter": "exam-prep/visuals/source/before.png",
    }]


def test_source_saved_during_session_deletion_is_immediately_removed(
    monkeypatch,
    tmp_path,
):
    teacher = baker.make("accounts.User", role="TEACHER")
    session, _artifact = _v3_session(teacher)
    session.source_type = ClassCreationSession.SourceType.MEDIA
    session.source_mime_type = "image/png"
    session.save(update_fields=[
        "source_type",
        "source_mime_type",
        "updated_at",
    ])
    source_path = tmp_path / "answer.png"
    source_path.write_bytes(b"image-bytes")

    class DeletingStorage:
        @staticmethod
        def save(name, _content):
            session.delete()
            return name

    deleted = []
    monkeypatch.setattr(
        "django.core.files.storage.storages",
        {"answer_sources": DeletingStorage()},
    )
    monkeypatch.setattr(
        "core.storage_backends.delete_answer_source_file",
        lambda name: deleted.append(name) or True,
    )

    with pytest.raises(TranscriptionAborted):
        class_tasks._ingest_source_to_markdown(
            session,
            str(source_path),
        )

    assert len(deleted) == 1
    assert deleted[0].startswith("exam-prep/source/")
