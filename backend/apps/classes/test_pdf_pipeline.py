"""Integration tests: PDF uploads flow through step 1 and reuse the
source-agnostic downstream pipeline (class + exam-prep).

The PDF extraction engine itself is mocked here (it has its own dedicated
numeric tests); these tests assert wiring: source_type detection, status
transitions, page count, downstream reuse, the error contract, and idempotency.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.classes.models import ClassCreationSession

User = get_user_model()

CLASS_STEP1 = '/api/classes/creation-sessions/step-1/'
CLASS_STEP2 = '/api/classes/creation-sessions/step-2/'

PDF_BYTES = b'%PDF-1.4 fake pdf body for upload'


def _teacher_client():
    user = User.objects.create_user(username=f'tpdf_{uuid.uuid4().hex[:6]}', password='p', role=User.Role.TEACHER)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


def _pdf(name='doc.pdf'):
    return SimpleUploadedFile(name, PDF_BYTES, content_type='application/pdf')


@pytest.fixture(autouse=True)
def _sync_pipeline(settings):
    settings.CLASS_PIPELINE_ASYNC = False


@pytest.mark.django_db
class TestPdfClassPipeline:
    def test_pdf_upload_sets_source_type_and_transcribes(self, monkeypatch):
        calls = {'n': 0}

        def fake_extract(*, data, mime_type):
            calls['n'] += 1
            assert data  # bytes were read and passed through
            assert mime_type == 'application/pdf'
            return ('# محتوای استخراج‌شده از PDF', 'local', 'pdfplumber', 7)

        monkeypatch.setattr('apps.classes.views.extract_pdf_to_markdown', fake_extract)

        client, _ = _teacher_client()
        res = client.post(CLASS_STEP1, {'title': 'جزوه ریاضی', 'file': _pdf()}, format='multipart')

        assert res.status_code == 201
        assert res.data['source_type'] == 'pdf'
        assert res.data['source_page_count'] == 7
        assert res.data['status'] == ClassCreationSession.Status.TRANSCRIBED
        assert res.data['transcript_markdown'] == '# محتوای استخراج‌شده از PDF'
        assert calls['n'] == 1

        session = ClassCreationSession.objects.get(id=res.data['id'])
        assert session.source_type == ClassCreationSession.SourceType.PDF
        assert session.source_page_count == 7

    def test_media_upload_still_uses_transcription(self, monkeypatch):
        monkeypatch.setattr(
            'apps.classes.views.transcribe_media_bytes',
            lambda *, data, mime_type: ('# transcript', 'gemini', 'models/gemini-2.5-flash'),
        )

        def must_not_run(**kwargs):
            raise AssertionError('PDF engine used for a media upload')

        monkeypatch.setattr('apps.classes.views.extract_pdf_to_markdown', must_not_run)

        client, _ = _teacher_client()
        audio = SimpleUploadedFile('lecture.mp3', b'ID3 audio', content_type='audio/mpeg')
        res = client.post(CLASS_STEP1, {'title': 'درس صوتی', 'file': audio}, format='multipart')

        assert res.status_code == 201
        assert res.data['source_type'] == 'media'
        assert res.data['status'] == ClassCreationSession.Status.TRANSCRIBED

    def test_extraction_failure_returns_502_without_leaking(self, monkeypatch):
        def boom(**kwargs):
            raise RuntimeError('pdf engine internal boom')

        monkeypatch.setattr('apps.classes.views.extract_pdf_to_markdown', boom)

        client, _ = _teacher_client()
        res = client.post(CLASS_STEP1, {'title': 'x', 'file': _pdf()}, format='multipart')

        assert res.status_code == 502
        session = ClassCreationSession.objects.get(id=res.data['session_id'])
        assert session.status == ClassCreationSession.Status.FAILED
        assert 'pdf engine internal boom' in session.error_detail
        assert 'pdf engine internal boom' not in str(res.data)

    def test_pdf_transcript_flows_into_downstream_structure(self, monkeypatch):
        monkeypatch.setattr(
            'apps.classes.views.extract_pdf_to_markdown',
            lambda *, data, mime_type: ('# md from pdf', 'local', 'pdfplumber', 2),
        )
        monkeypatch.setattr(
            'apps.classes.views.structure_transcript_markdown',
            lambda *, transcript_markdown: ({'root_object': {'title': 'x'}, 'outline': []}, 'gemini', 'models/gemini-2.5-flash'),
        )

        client, _ = _teacher_client()
        res = client.post(CLASS_STEP1, {'title': 'x', 'file': _pdf()}, format='multipart')
        session_id = res.data['id']

        res2 = client.post(CLASS_STEP2, {'session_id': session_id}, format='json')
        assert res2.status_code in (200, 201, 202)

        session = ClassCreationSession.objects.get(id=session_id)
        assert session.status == ClassCreationSession.Status.STRUCTURED

    def test_pdf_idempotency_does_not_re_extract(self, monkeypatch):
        calls = {'n': 0}

        def fake_extract(*, data, mime_type):
            calls['n'] += 1
            return ('# md', 'local', 'pdfplumber', 1)

        monkeypatch.setattr('apps.classes.views.extract_pdf_to_markdown', fake_extract)

        client, _ = _teacher_client()
        rid = str(uuid.uuid4())
        r1 = client.post(CLASS_STEP1, {'title': 'x', 'file': _pdf(), 'client_request_id': rid}, format='multipart')
        r2 = client.post(CLASS_STEP1, {'title': 'x', 'file': _pdf(), 'client_request_id': rid}, format='multipart')

        assert r1.data['id'] == r2.data['id']
        assert calls['n'] == 1


@pytest.mark.django_db
class TestPdfExamPipeline:
    def test_exam_pdf_task_extracts_and_transcribes(self, monkeypatch):
        from apps.classes.tasks import process_exam_prep_step1_transcription

        monkeypatch.setattr(
            'apps.classes.services.pdf_extraction.extract_pdf_to_markdown',
            lambda *, data, mime_type: ('# سوالات استخراج‌شده', 'local', 'pdfplumber', 5),
        )

        user = User.objects.create_user(username='te_pdf', password='p', role=User.Role.TEACHER)
        session = ClassCreationSession.objects.create(
            teacher=user,
            title='آزمون ریاضی',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            source_type=ClassCreationSession.SourceType.PDF,
            source_file=_pdf('exam.pdf'),
            source_mime_type='application/pdf',
            status=ClassCreationSession.Status.EXAM_TRANSCRIBING,
        )

        process_exam_prep_step1_transcription.apply(args=[session.id]).get()

        session.refresh_from_db()
        assert session.status == ClassCreationSession.Status.EXAM_TRANSCRIBED
        assert session.transcript_markdown == '# سوالات استخراج‌شده'
        assert session.source_page_count == 5
