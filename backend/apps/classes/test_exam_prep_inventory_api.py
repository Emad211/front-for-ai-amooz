import json

import pytest
from django.core.files.base import ContentFile
from model_bakery import baker
from rest_framework.test import APIClient

from apps.classes.models import (
    ClassCreationSession,
    ClassInvitation,
    ExamPrepExtractionArtifact,
    ExamPrepVisualAsset,
)


pytestmark = pytest.mark.django_db


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _session(teacher):
    return baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        exam_prep_json=json.dumps({
            "exam_prep": {
                "title": "آزمون",
                "questions": [{
                    "question_id": "q-a",
                    "question_text_markdown": "سؤال",
                    "options": [],
                    "correct_option_label": None,
                    "final_answer_markdown": "پاسخ",
                    "teacher_solution_markdown": "",
                    "visuals": [],
                }],
            },
        }),
    )


def test_v2_publish_is_blocked_by_critical_audit():
    teacher = baker.make("accounts.User", role="TEACHER")
    session = _session(teacher)
    ExamPrepExtractionArtifact.objects.create(
        session=session,
        status=ExamPrepExtractionArtifact.Status.READY,
        audit={"status": "needs_review", "criticalIssueCount": 1, "issues": []},
    )

    response = _auth(teacher).post(
        f"/api/classes/exam-prep-sessions/{session.id}/publish/"
    )

    assert response.status_code == 409
    assert response.data["code"] == "extraction_review_required"
    session.refresh_from_db()
    assert session.is_published is False


def test_v2_publish_passes_after_clean_audit(monkeypatch):
    teacher = baker.make("accounts.User", role="TEACHER")
    session = _session(teacher)
    ExamPrepExtractionArtifact.objects.create(
        session=session,
        status=ExamPrepExtractionArtifact.Status.READY,
        audit={"status": "passed", "criticalIssueCount": 0, "issues": []},
    )
    monkeypatch.setattr(
        "apps.classes.views.send_publish_sms_task.delay", lambda *_args, **_kwargs: None
    )

    response = _auth(teacher).post(
        f"/api/classes/exam-prep-sessions/{session.id}/publish/"
    )

    assert response.status_code == 200
    session.refresh_from_db()
    assert session.is_published is True


def test_visual_selection_is_owner_scoped_and_requires_verified_candidate():
    owner = baker.make("accounts.User", role="TEACHER")
    other = baker.make("accounts.User", role="TEACHER")
    session = _session(owner)
    artifact = ExamPrepExtractionArtifact.objects.create(session=session)
    asset = ExamPrepVisualAsset(
        artifact=artifact,
        asset_key="a" * 64,
        question_key="زیست::78",
        role=ExamPrepVisualAsset.Role.QUESTION,
        source_kind=ExamPrepVisualAsset.SourceKind.PDF_PAGE,
        source_page=1,
        source_sha256="a" * 64,
        fingerprint="b" * 64,
    )
    asset.source_file.save("source.png", ContentFile(b"source"), save=False)
    asset.save()
    url = f"/api/classes/exam-prep-sessions/{session.id}/visuals/{asset.id}/"

    assert _auth(other).patch(url, {"selectedVariant": "source"}, format="json").status_code == 404
    response = _auth(owner).patch(url, {"selectedVariant": "generated"}, format="json")
    assert response.status_code == 409


def test_detail_exposes_inventory_audit_and_visual_review_data():
    teacher = baker.make("accounts.User", role="TEACHER")
    session = _session(teacher)
    artifact = ExamPrepExtractionArtifact.objects.create(
        session=session,
        audit={"status": "needs_review", "criticalIssueCount": 1, "issues": []},
        answer_records=[{"source_question_number": "77", "match_status": "out_of_scope"}],
    )
    asset = ExamPrepVisualAsset(
        artifact=artifact,
        asset_key="b" * 64,
        question_key="default::78",
        role=ExamPrepVisualAsset.Role.QUESTION,
        source_kind=ExamPrepVisualAsset.SourceKind.PDF_PAGE,
        source_page=1,
        source_sha256="a" * 64,
        fingerprint="b" * 64,
    )
    asset.source_file.save("source.png", ContentFile(b"source"), save=False)
    asset.save()

    response = _auth(teacher).get(
        f"/api/classes/exam-prep-sessions/{session.id}/"
    )

    assert response.status_code == 200
    assert response.data["extractionAudit"]["status"] == "needs_review"
    assert response.data["extractionVersion"] == 2
    assert response.data["visualAssets"][0]["id"] == asset.id
    assert response.data["extractionReview"]["unmatchedAnswers"][0][
        "source_question_number"
    ] == "77"


def test_exam_list_returns_audit_summary_without_heavy_review_payload():
    teacher = baker.make("accounts.User", role="TEACHER")
    session = _session(teacher)
    artifact = ExamPrepExtractionArtifact.objects.create(
        session=session,
        audit={"status": "passed", "criticalIssueCount": 0, "issues": []},
        page_manifest={"pages": [{"page_number": 1}]},
        answer_records=[{"source_question_number": "78", "match_status": "matched"}],
    )
    asset = ExamPrepVisualAsset(
        artifact=artifact,
        asset_key="d" * 64,
        question_key="default::78",
        role=ExamPrepVisualAsset.Role.QUESTION,
        source_kind=ExamPrepVisualAsset.SourceKind.PDF_PAGE,
        source_page=1,
        source_sha256="a" * 64,
        fingerprint="b" * 64,
    )
    asset.source_file.save("source.png", ContentFile(b"source"), save=False)
    asset.save()

    response = _auth(teacher).get("/api/classes/exam-prep-sessions/")

    assert response.status_code == 200
    item = next(item for item in response.data if item["id"] == session.id)
    assert item["extractionAudit"]["status"] == "passed"
    assert item["visualAssets"] == []
    assert item["extractionReview"] is None


def test_teacher_edit_rebuilds_correctable_audit_but_keeps_pipeline_failures():
    teacher = baker.make("accounts.User", role="TEACHER")
    session = _session(teacher)
    artifact = ExamPrepExtractionArtifact.objects.create(
        session=session,
        audit={
            "status": "needs_review",
            "criticalIssueCount": 2,
            "issues": [
                {"code": "missing_answer", "severity": "critical"},
                {"code": "failed_chunk", "severity": "critical"},
            ],
        },
    )
    valid_projection = {
        "exam_prep": {
            "title": "آزمون",
            "questions": [{
                "question_id": "q-a",
                "question_text_markdown": "سؤال",
                "options": [],
                "correct_option_label": None,
                "final_answer_markdown": "پاسخ",
                "teacher_solution_markdown": "",
                "visuals": [],
            }],
        },
    }

    response = _auth(teacher).patch(
        f"/api/classes/exam-prep-sessions/{session.id}/",
        {"exam_prep_json": valid_projection},
        format="json",
    )

    assert response.status_code == 200
    artifact.refresh_from_db()
    assert artifact.audit["status"] == "needs_review"
    assert artifact.audit["criticalIssueCount"] == 1
    assert [item["code"] for item in artifact.audit["issues"]] == ["failed_chunk"]

    artifact.audit = {
        "status": "needs_review",
        "criticalIssueCount": 1,
        "issues": [{"code": "missing_answer", "severity": "critical"}],
    }
    artifact.save(update_fields=["audit", "updated_at"])
    response = _auth(teacher).patch(
        f"/api/classes/exam-prep-sessions/{session.id}/",
        {"exam_prep_json": valid_projection},
        format="json",
    )
    artifact.refresh_from_db()
    assert response.status_code == 200
    assert artifact.audit["status"] == "passed"
    assert artifact.audit["criticalIssueCount"] == 0


def test_student_cannot_fetch_solution_visual_before_reveal():
    teacher = baker.make("accounts.User", role="TEACHER")
    student = baker.make("accounts.User", role="STUDENT", phone="09120000001")
    session = _session(teacher)
    session.is_published = True
    session.save(update_fields=["is_published", "updated_at"])
    ClassInvitation.objects.create(
        session=session,
        phone=student.phone,
        invite_code="VISUAL-SOLUTION-1",
    )
    artifact = ExamPrepExtractionArtifact.objects.create(session=session)
    asset = ExamPrepVisualAsset(
        artifact=artifact,
        asset_key="c" * 64,
        question_key="default::78",
        role=ExamPrepVisualAsset.Role.SOLUTION,
        source_kind=ExamPrepVisualAsset.SourceKind.PDF_PAGE,
        source_page=2,
        source_sha256="a" * 64,
        fingerprint="b" * 64,
    )
    asset.source_file.save("solution.png", ContentFile(b"solution"), save=False)
    asset.save()

    response = _auth(student).get(
        f"/api/classes/exam-prep-sessions/{session.id}/visuals/{asset.id}/content/"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_visual_content_rejects_unknown_variant():
    teacher = baker.make("accounts.User", role="TEACHER")
    session = baker.make(
        ClassCreationSession,
        teacher=teacher,
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
    )
    artifact = baker.make(
        ExamPrepExtractionArtifact,
        session=session,
        pipeline_version=2,
    )
    asset = baker.make(
        ExamPrepVisualAsset,
        artifact=artifact,
        asset_key="unknown-variant",
        role=ExamPrepVisualAsset.Role.QUESTION,
        source_kind=ExamPrepVisualAsset.SourceKind.SOURCE_IMAGE,
        source_sha256="a" * 64,
        fingerprint="b" * 64,
    )
    asset.source_file.save("question.png", ContentFile(b"question"), save=True)
    client = APIClient()
    client.force_authenticate(teacher)

    response = client.get(
        f"/api/classes/exam-prep-sessions/{session.id}/visuals/{asset.id}/content/"
        "?variant=unexpected"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "نسخه تصویر نامعتبر است."


def test_failed_v2_extraction_can_be_retried_once(
    monkeypatch, django_capture_on_commit_callbacks
):
    teacher = baker.make("accounts.User", role="TEACHER")
    session = _session(teacher)
    ExamPrepExtractionArtifact.objects.create(
        session=session,
        pipeline_version=2,
        status=ExamPrepExtractionArtifact.Status.READY,
        audit={
            "status": "needs_review",
            "criticalIssueCount": 1,
            "issues": [{"code": "failed_chunk", "severity": "critical"}],
        },
        failed_chunks=[{"phase": "answers", "chunk": 1}],
    )
    dispatched = []
    monkeypatch.setattr(
        "apps.classes.views.process_exam_prep_step2_structure.delay",
        lambda session_id: dispatched.append(session_id),
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = _auth(teacher).post(
            "/api/classes/exam-prep-sessions/step-2/",
            {"session_id": session.id},
            format="json",
        )

    assert response.status_code == 202
    assert response.data["status"] == ClassCreationSession.Status.EXAM_STRUCTURING
    assert dispatched == [session.id]

    duplicate = _auth(teacher).post(
        "/api/classes/exam-prep-sessions/step-2/",
        {"session_id": session.id},
        format="json",
    )
    assert duplicate.status_code == 202
    assert dispatched == [session.id]


@pytest.mark.parametrize("with_clean_v2", [False, True])
def test_structured_legacy_or_clean_v2_extraction_cannot_be_retried(
    monkeypatch, with_clean_v2
):
    teacher = baker.make("accounts.User", role="TEACHER")
    session = _session(teacher)
    if with_clean_v2:
        ExamPrepExtractionArtifact.objects.create(
            session=session,
            pipeline_version=2,
            audit={"status": "passed", "criticalIssueCount": 0, "issues": []},
        )
    dispatched = []
    monkeypatch.setattr(
        "apps.classes.views.process_exam_prep_step2_structure.delay",
        lambda session_id: dispatched.append(session_id),
    )

    response = _auth(teacher).post(
        "/api/classes/exam-prep-sessions/step-2/",
        {"session_id": session.id},
        format="json",
    )

    assert response.status_code == 409
    assert dispatched == []
