"""
Tests for Exam Prep Pipeline (2 steps: Transcribe + Q&A Extraction).

Following develop.instructions.md:
- Unit tests for services
- Integration tests for API endpoints with auth/permissions
- Error path testing
"""

import json
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession


User = get_user_model()


@pytest.mark.django_db
class TestExamPrepStep1Transcription:
    """Tests for Exam Prep Step 1: Upload and transcribe media."""

    @pytest.fixture(autouse=True)
    def _disable_async_pipeline(self, settings):
        settings.CLASS_PIPELINE_ASYNC = False

    @pytest.fixture(autouse=True)
    def _stub_celery_tasks(self, monkeypatch):
        """Stub Celery .delay() so tests don't need a running broker."""
        monkeypatch.setattr(
            'apps.classes.views.process_exam_prep_step1_transcription.delay',
            lambda session_id: None,
        )
        monkeypatch.setattr(
            'apps.classes.views.process_exam_prep_full_pipeline.delay',
            lambda session_id: None,
        )
        monkeypatch.setattr(
            'apps.classes.views.process_exam_prep_step2_structure.delay',
            lambda session_id: None,
        )

    def test_requires_authentication(self):
        """Step 1 should reject unauthenticated requests."""
        client = APIClient()
        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        res = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'title': 'Test', 'file': upload},
            format='multipart',
        )
        assert res.status_code == 401

    def test_requires_teacher_role(self):
        """Step 1 should reject non-teacher users (403)."""
        user = User.objects.create_user(username='student1', password='pass', role=User.Role.STUDENT)
        token = str(RefreshToken.for_user(user).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        res = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'title': 'Test', 'file': upload},
            format='multipart',
        )
        assert res.status_code == 403

    def test_teacher_can_start_exam_prep_transcription(self, monkeypatch):
        """Teacher can upload file and start exam prep transcription."""
        user = User.objects.create_user(username='teacher1', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(user).access_token)

        def _fake_transcribe_media_bytes(*, data: bytes, mime_type: str):
            return ('# Transcript\nسوال اول...', 'gemini', 'models/gemini-2.5-flash')

        monkeypatch.setattr(
            'apps.classes.views.transcribe_media_bytes',
            _fake_transcribe_media_bytes,
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        upload = SimpleUploadedFile('exam.ogg', b'fake-audio', content_type='audio/ogg')
        res = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'title': 'ریاضی کنکور', 'description': 'حل تست‌های فصل ۱', 'file': upload},
            format='multipart',
        )

        # Async mode is enabled in views, so we get 202
        assert res.status_code == 202
        assert 'id' in res.data
        assert res.data['pipeline_type'] == 'exam_prep'
        # Status should be exam_transcribing (background processing)
        assert res.data['status'] in [
            ClassCreationSession.Status.EXAM_TRANSCRIBING,
            ClassCreationSession.Status.EXAM_TRANSCRIBED,
        ]

        session = ClassCreationSession.objects.get(id=res.data['id'])
        assert session.teacher_id == user.id
        assert session.title == 'ریاضی کنکور'
        assert session.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP

    def test_rejects_unsupported_file(self):
        """Should reject files that are not audio, video, or PDF."""
        user = User.objects.create_user(username='teacher2', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(user).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        upload = SimpleUploadedFile('notes.txt', b'just text', content_type='text/plain')
        res = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'title': 'Test', 'file': upload},
            format='multipart',
        )
        assert res.status_code == 400
        # Validation error structure may vary; check errors dict
        assert 'errors' in res.data or 'file' in res.data

    def test_title_is_required(self):
        """Should reject requests without title."""
        user = User.objects.create_user(username='teacher3', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(user).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        res = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'file': upload},  # Missing title
            format='multipart',
        )
        assert res.status_code == 400

    def test_idempotency_with_client_request_id(self, monkeypatch):
        """A genuine retry (SAME file + SAME client_request_id) dedupes to the
        existing session — no duplicate is created."""
        user = User.objects.create_user(username='teacher4', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(user).access_token)

        def _fake_transcribe_media_bytes(*, data: bytes, mime_type: str):
            return ('# Transcript', 'gemini', 'models/gemini-2.5-flash')

        monkeypatch.setattr(
            'apps.classes.views.transcribe_media_bytes',
            _fake_transcribe_media_bytes,
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        import uuid
        client_request_id = str(uuid.uuid4())

        # First request
        upload1 = SimpleUploadedFile('exam1.ogg', b'fake-audio', content_type='audio/ogg')
        res1 = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'title': 'Test', 'file': upload1, 'client_request_id': client_request_id},
            format='multipart',
        )
        session_id_1 = res1.data['id']

        # Second request: SAME file (same name + bytes) + SAME client_request_id →
        # a genuine retry, must dedupe to the existing session.
        upload2 = SimpleUploadedFile('exam1.ogg', b'fake-audio', content_type='audio/ogg')
        res2 = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'title': 'Test', 'file': upload2, 'client_request_id': client_request_id},
            format='multipart',
        )

        # Should return same session (idempotent hit)
        assert res2.data['id'] == session_id_1

    def test_different_file_same_client_request_id_creates_new_session(self, monkeypatch):
        """A DIFFERENT file reusing the same client_request_id must NOT return the
        stale session (that would emit the old media's output for a new upload —
        the 'new input, stale output' bug). It mints a fresh session instead."""
        user = User.objects.create_user(username='teacher4b', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(user).access_token)

        monkeypatch.setattr(
            'apps.classes.views.transcribe_media_bytes',
            lambda *, data, mime_type: ('# Transcript', 'gemini', 'models/gemini-2.5-flash'),
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        import uuid
        client_request_id = str(uuid.uuid4())

        res1 = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'title': 'A', 'file': SimpleUploadedFile('a.ogg', b'audio-A', content_type='audio/ogg'),
             'client_request_id': client_request_id},
            format='multipart',
        )
        res2 = client.post(
            '/api/classes/exam-prep-sessions/step-1/',
            {'title': 'B', 'file': SimpleUploadedFile('b.ogg', b'audio-B-different', content_type='audio/ogg'),
             'client_request_id': client_request_id},
            format='multipart',
        )
        assert res2.data['id'] != res1.data['id']


@pytest.mark.django_db
class TestExamPrepStep2Structure:
    """Tests for Exam Prep Step 2: Q&A Extraction."""

    @pytest.fixture(autouse=True)
    def _stub_celery_tasks(self, monkeypatch):
        """Stub Celery .delay() so tests don't need a running broker."""
        monkeypatch.setattr(
            'apps.classes.views.process_exam_prep_step2_structure.delay',
            lambda session_id: None,
        )

    @pytest.fixture
    def teacher_with_transcribed_session(self):
        """Create a teacher with a transcribed exam prep session."""
        user = User.objects.create_user(username='teacher_step2', password='pass', role=User.Role.TEACHER)
        session = ClassCreationSession.objects.create(
            teacher=user,
            title='ریاضی کنکور',
            description='تست‌ها',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_TRANSCRIBED,
            transcript_markdown='# Transcript\nسوال ۱: اگر x=2 باشد...',
        )
        return user, session

    def test_requires_authentication(self, teacher_with_transcribed_session):
        """Step 2 should reject unauthenticated requests."""
        _, session = teacher_with_transcribed_session
        client = APIClient()
        res = client.post(
            '/api/classes/exam-prep-sessions/step-2/',
            {'session_id': session.id},
        )
        assert res.status_code == 401

    def test_requires_teacher_role(self, teacher_with_transcribed_session):
        """Step 2 should reject non-teacher users."""
        _, session = teacher_with_transcribed_session
        student = User.objects.create_user(username='student_step2', password='pass', role=User.Role.STUDENT)
        token = str(RefreshToken.for_user(student).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post(
            '/api/classes/exam-prep-sessions/step-2/',
            {'session_id': session.id},
        )
        assert res.status_code == 403

    def test_teacher_cannot_access_other_teacher_session(self, teacher_with_transcribed_session):
        """A teacher should not be able to process another teacher's session."""
        _, session = teacher_with_transcribed_session
        other_teacher = User.objects.create_user(username='other_teacher', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(other_teacher).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post(
            '/api/classes/exam-prep-sessions/step-2/',
            {'session_id': session.id},
        )
        assert res.status_code == 404

    def test_teacher_can_start_step2_extraction(self, teacher_with_transcribed_session, monkeypatch):
        """Teacher can start Q&A extraction on their transcribed session."""
        user, session = teacher_with_transcribed_session
        token = str(RefreshToken.for_user(user).access_token)

        def _fake_extract_exam_prep_structure(*, transcript_markdown: str):
            return {
                'exam_prep': {
                    'title': 'ریاضی',
                    'questions': [
                        {
                            'question_id': 'q-1',
                            'question_text_markdown': 'اگر x=2 باشد...',
                            'options': [],
                            'correct_option_label': None,
                            'teacher_solution_markdown': 'حل: ...',
                        }
                    ]
                }
            }, 'gemini', 'models/gemini-2.5-flash'

        monkeypatch.setattr(
            'apps.classes.views.extract_exam_prep_structure',
            _fake_extract_exam_prep_structure,
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post(
            '/api/classes/exam-prep-sessions/step-2/',
            {'session_id': session.id},
        )

        assert res.status_code == 202
        assert res.data['status'] == ClassCreationSession.Status.EXAM_STRUCTURING

    def test_rejects_session_in_wrong_status(self, teacher_with_transcribed_session):
        """Should reject if session is not in EXAM_TRANSCRIBED status."""
        user, session = teacher_with_transcribed_session
        session.status = ClassCreationSession.Status.EXAM_STRUCTURING
        session.save()

        token = str(RefreshToken.for_user(user).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post(
            '/api/classes/exam-prep-sessions/step-2/',
            {'session_id': session.id},
        )
        assert res.status_code == 409


@pytest.mark.django_db
class TestExamPrepSessionDetail:
    """Tests for getting exam prep session details (polling endpoint)."""

    @pytest.fixture
    def teacher_with_exam_session(self):
        """Create teacher with exam prep session."""
        user = User.objects.create_user(username='teacher_detail', password='pass', role=User.Role.TEACHER)
        session = ClassCreationSession.objects.create(
            teacher=user,
            title='فیزیک',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_STRUCTURED,
            transcript_markdown='# Transcript',
            exam_prep_json='{"exam_prep": {"title": "فیزیک", "questions": []}}',
        )
        return user, session

    def test_requires_authentication(self, teacher_with_exam_session):
        """Detail endpoint should require auth."""
        _, session = teacher_with_exam_session
        client = APIClient()
        res = client.get(f'/api/classes/exam-prep-sessions/{session.id}/')
        assert res.status_code == 401

    def test_teacher_can_get_own_session_detail(self, teacher_with_exam_session):
        """Teacher can get their own session details."""
        user, session = teacher_with_exam_session
        token = str(RefreshToken.for_user(user).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get(f'/api/classes/exam-prep-sessions/{session.id}/')

        assert res.status_code == 200
        assert res.data['id'] == session.id
        assert res.data['title'] == 'فیزیک'
        assert res.data['pipeline_type'] == 'exam_prep'
        assert res.data['status'] == 'exam_structured'
        assert 'exam_prep_data' in res.data

    def test_teacher_cannot_get_other_teacher_session(self, teacher_with_exam_session):
        """A teacher should not see another teacher's session."""
        _, session = teacher_with_exam_session
        other = User.objects.create_user(username='other_t', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(other).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get(f'/api/classes/exam-prep-sessions/{session.id}/')
        assert res.status_code == 404

    def test_filters_by_exam_prep_pipeline_type(self):
        """Should not return class pipeline sessions."""
        user = User.objects.create_user(username='teacher_filter', password='pass', role=User.Role.TEACHER)
        # Create a class pipeline session (not exam prep)
        class_session = ClassCreationSession.objects.create(
            teacher=user,
            title='کلاس',
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
            status=ClassCreationSession.Status.TRANSCRIBED,
        )

        token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Try to get as exam prep session (should 404)
        res = client.get(f'/api/classes/exam-prep-sessions/{class_session.id}/')
        assert res.status_code == 404


@pytest.mark.django_db
class TestExamPrepSessionList:
    """Tests for listing exam prep sessions."""

    def test_requires_authentication(self):
        """List endpoint should require auth."""
        client = APIClient()
        res = client.get('/api/classes/exam-prep-sessions/')
        assert res.status_code == 401

    def test_teacher_sees_only_own_exam_prep_sessions(self):
        """Teacher should only see their own exam prep sessions."""
        t1 = User.objects.create_user(username='t1_list', password='pass', role=User.Role.TEACHER)
        t2 = User.objects.create_user(username='t2_list', password='pass', role=User.Role.TEACHER)

        # Teacher 1's exam prep session
        s1 = ClassCreationSession.objects.create(
            teacher=t1,
            title='T1 Exam',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_STRUCTURED,
        )
        # Teacher 2's exam prep session
        ClassCreationSession.objects.create(
            teacher=t2,
            title='T2 Exam',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_STRUCTURED,
        )
        # Teacher 1's class pipeline session (should not appear)
        ClassCreationSession.objects.create(
            teacher=t1,
            title='T1 Class',
            pipeline_type=ClassCreationSession.PipelineType.CLASS,
            status=ClassCreationSession.Status.TRANSCRIBED,
        )

        token = str(RefreshToken.for_user(t1).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = client.get('/api/classes/exam-prep-sessions/')

        assert res.status_code == 200
        assert len(res.data) == 1
        assert res.data[0]['id'] == s1.id
        assert res.data[0]['title'] == 'T1 Exam'


@pytest.mark.django_db
class TestExamPrepSessionPublish:
    """Tests for publishing exam prep sessions."""

    @pytest.fixture
    def teacher_with_ready_session(self):
        """Create teacher with EXAM_STRUCTURED session ready to publish."""
        user = User.objects.create_user(username='teacher_pub', password='pass', role=User.Role.TEACHER)
        session = ClassCreationSession.objects.create(
            teacher=user,
            title='Ready Exam',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_STRUCTURED,
            exam_prep_json='{"exam_prep": {"questions": []}}',
        )
        return user, session

    def test_requires_authentication(self, teacher_with_ready_session):
        """Publish should require auth."""
        _, session = teacher_with_ready_session
        client = APIClient()
        res = client.post(f'/api/classes/exam-prep-sessions/{session.id}/publish/')
        assert res.status_code == 401

    def test_teacher_can_publish_ready_session(self, teacher_with_ready_session):
        """Teacher can publish their EXAM_STRUCTURED session."""
        user, session = teacher_with_ready_session
        token = str(RefreshToken.for_user(user).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post(f'/api/classes/exam-prep-sessions/{session.id}/publish/')

        assert res.status_code == 200
        assert res.data['is_published'] is True
        assert res.data['published_at'] is not None

        session.refresh_from_db()
        assert session.is_published is True

    def test_cannot_publish_session_in_wrong_status(self, teacher_with_ready_session):
        """Cannot publish if not EXAM_STRUCTURED."""
        user, session = teacher_with_ready_session
        session.status = ClassCreationSession.Status.EXAM_TRANSCRIBED
        session.save()

        token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = client.post(f'/api/classes/exam-prep-sessions/{session.id}/publish/')
        assert res.status_code == 400

    def test_cannot_publish_other_teacher_session(self, teacher_with_ready_session):
        """Teacher cannot publish another teacher's session."""
        _, session = teacher_with_ready_session
        other = User.objects.create_user(username='other_pub', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(other).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post(f'/api/classes/exam-prep-sessions/{session.id}/publish/')
        assert res.status_code == 404


@pytest.mark.django_db
class TestExamPrepServiceUnit:
    """Unit tests for exam prep structure extraction service."""

    def test_extract_exam_prep_structure_returns_expected_format(self, monkeypatch):
        """Service returns validated question data using the env-selected model."""
        from apps.classes.services import exam_prep_structure as eps
        from apps.classes.services.schemas import ExamPrepOutput

        monkeypatch.setenv('STRUCTURE_MODEL', 'test-structure-model')
        monkeypatch.setattr(
            eps, 'generate_structured',
            lambda **kwargs: ExamPrepOutput.model_validate({
                'exam_prep': {
                    'title': 'Test',
                    'questions': [{
                        'question_text_markdown': 'Question?',
                        'options': [],
                    }],
                }
            }),
        )

        result, provider, model = eps.extract_exam_prep_structure(
            transcript_markdown='# Test transcript'
        )

        assert 'exam_prep' in result
        assert model == 'test-structure-model'
        # provider comes from preferred_provider() (env-driven); just assert it's set.
        assert isinstance(provider, str) and provider


# ==========================================================================
# EXAM PREP INVITATIONS TESTS
# ==========================================================================


@pytest.mark.django_db
class TestExamPrepInvitations:
    """Tests for exam prep invitations API."""

    @pytest.fixture
    def teacher_with_exam_prep_session(self):
        """Create a teacher with a published exam prep session."""
        user = User.objects.create_user(username='teacher_inv', password='pass', role=User.Role.TEACHER)
        session = ClassCreationSession.objects.create(
            teacher=user,
            title='آزمون ریاضی',
            description='تست‌ها',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_STRUCTURED,
            structure_json={'exam_prep': {'questions': []}},
            is_published=True,
        )
        return user, session

    def test_list_invites_requires_authentication(self, teacher_with_exam_prep_session):
        """List invites should reject unauthenticated requests."""
        _, session = teacher_with_exam_prep_session
        client = APIClient()
        res = client.get(f'/api/classes/exam-prep-sessions/{session.id}/invites/')
        assert res.status_code == 401

    def test_list_invites_requires_teacher_role(self, teacher_with_exam_prep_session):
        """List invites should reject non-teacher users."""
        _, session = teacher_with_exam_prep_session
        student = User.objects.create_user(username='student_inv', password='pass', role=User.Role.STUDENT)
        token = str(RefreshToken.for_user(student).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get(f'/api/classes/exam-prep-sessions/{session.id}/invites/')
        assert res.status_code == 403

    def test_teacher_can_list_empty_invites(self, teacher_with_exam_prep_session):
        """Teacher can list invites (starts empty)."""
        user, session = teacher_with_exam_prep_session
        token = str(RefreshToken.for_user(user).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get(f'/api/classes/exam-prep-sessions/{session.id}/invites/')

        assert res.status_code == 200
        assert res.data == []

    def test_teacher_can_add_invites(self, teacher_with_exam_prep_session):
        """Teacher can add invitations with phone numbers."""
        user, session = teacher_with_exam_prep_session
        token = str(RefreshToken.for_user(user).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post(
            f'/api/classes/exam-prep-sessions/{session.id}/invites/',
            {'phones': ['09121234567', '09131234567']},
            format='json',
        )

        assert res.status_code == 200
        assert len(res.data) == 2
        phones = [item['phone'] for item in res.data]
        assert '09121234567' in phones
        assert '09131234567' in phones


@pytest.mark.django_db
def test_invite_code_is_stable_across_pipelines_for_same_phone():
    """Same phone must get the same invite code across class and exam_prep invites."""

    teacher = User.objects.create_user(username='t_codes', password='pass', role=User.Role.TEACHER)

    class_session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='کلاس ۱',
        description='',
        pipeline_type=ClassCreationSession.PipelineType.CLASS,
        status=ClassCreationSession.Status.TRANSCRIBED,
        transcript_markdown='x',
    )

    exam_session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='آزمون ۱',
        description='',
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        exam_prep_json='{}',
    )

    token = str(RefreshToken.for_user(teacher).access_token)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    phone = '09120000000'

    res1 = client.post(
        f'/api/classes/creation-sessions/{class_session.id}/invites/',
        {'phones': [phone]},
        format='json',
    )
    assert res1.status_code == 200
    assert len(res1.data) == 1
    code1 = res1.data[0]['invite_code']

    res2 = client.post(
        f'/api/classes/exam-prep-sessions/{exam_session.id}/invites/',
        {'phones': [phone]},
        format='json',
    )
    assert res2.status_code == 200
    assert len(res2.data) == 1
    code2 = res2.data[0]['invite_code']

    assert code1 == code2

    def test_teacher_can_delete_invite(self, teacher_with_exam_prep_session):
        """Teacher can delete an invitation."""
        from apps.classes.models import ClassInvitation
        import uuid

        user, session = teacher_with_exam_prep_session
        invite = ClassInvitation.objects.create(
            session=session,
            phone='09121234567',
            invite_code=str(uuid.uuid4())[:8],
        )

        token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = client.delete(f'/api/classes/exam-prep-sessions/{session.id}/invites/{invite.id}/')
        assert res.status_code == 204

        assert not ClassInvitation.objects.filter(id=invite.id).exists()

    def test_teacher_cannot_access_other_teacher_invites(self, teacher_with_exam_prep_session):
        """Teacher cannot access another teacher's session invites."""
        _, session = teacher_with_exam_prep_session
        other = User.objects.create_user(username='other_inv', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(other).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get(f'/api/classes/exam-prep-sessions/{session.id}/invites/')
        assert res.status_code == 404


# ==========================================================================
# STUDENT EXAM PREP LIST/DETAIL TESTS
# ==========================================================================


@pytest.mark.django_db
class TestStudentExamPrepList:
    """Tests for student exam prep list API."""

    @pytest.fixture
    def student_with_invite(self):
        """Create a student with invitation to a published exam prep session."""
        from apps.classes.models import ClassInvitation
        import uuid

        teacher = User.objects.create_user(username='teacher_std', password='pass', role=User.Role.TEACHER)
        student = User.objects.create_user(
            username='student_std',
            password='pass',
            role=User.Role.STUDENT,
        )
        # Set phone number directly
        student.phone = '09121234567'
        student.save()

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='آزمون زیست',
            description='سوالات فصل ۱',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_STRUCTURED,
            exam_prep_json=json.dumps({
                'exam_prep': {
                    'questions': [
                        {'id': 1, 'question': 'سوال ۱', 'answer': 'پاسخ ۱'},
                        {'id': 2, 'question': 'سوال ۲', 'answer': 'پاسخ ۲'},
                    ]
                }
            }),
            is_published=True,
        )
        ClassInvitation.objects.create(
            session=session,
            phone='09121234567',
            invite_code=str(uuid.uuid4())[:8],
        )

        return student, session

    def test_list_requires_authentication(self):
        """List student exam preps should reject unauthenticated requests."""
        client = APIClient()
        res = client.get('/api/classes/student/exam-preps/')
        assert res.status_code == 401

    def test_list_is_phone_scoped_for_uninvited_teacher(self, student_with_invite):
        """`IsStudentUser` allows teachers (learners); the list is phone-scoped, so
        an uninvited teacher gets 200 with NO exam-preps (no data leak) — not a
        role-403. [policy note in test_student_courses.py]"""
        _, session = student_with_invite
        teacher = User.objects.create_user(username='teacher_list', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(teacher).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get('/api/classes/student/exam-preps/')
        assert res.status_code == 200
        data = res.json()
        results = data['results'] if isinstance(data, dict) and 'results' in data else data
        assert all(item.get('id') != session.id for item in results), \
            'uninvited teacher saw an exam-prep they were not invited to (data leak)'

    def test_student_sees_invited_exam_preps(self, student_with_invite):
        """Student should see exam preps they've been invited to."""
        student, session = student_with_invite
        token = str(RefreshToken.for_user(student).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get('/api/classes/student/exam-preps/')

        assert res.status_code == 200
        assert len(res.data) == 1
        assert res.data[0]['id'] == session.id
        assert res.data[0]['title'] == 'آزمون زیست'
        assert res.data[0]['questions'] == 2

    def test_student_without_invite_sees_empty_list(self):
        """Student without invites should see empty list."""
        student = User.objects.create_user(
            username='student_no_inv',
            password='pass',
            role=User.Role.STUDENT,
        )
        student.phone = '09999999999'
        student.save()

        token = str(RefreshToken.for_user(student).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get('/api/classes/student/exam-preps/')

        assert res.status_code == 200
        assert res.data == []


@pytest.mark.django_db
class TestStudentExamPrepDetail:
    """Tests for student exam prep detail API."""

    @pytest.fixture
    def student_with_invite(self):
        """Create a student with invitation to a published exam prep session."""
        from apps.classes.models import ClassInvitation
        import uuid

        teacher = User.objects.create_user(username='teacher_det', password='pass', role=User.Role.TEACHER)
        student = User.objects.create_user(
            username='student_det',
            password='pass',
            role=User.Role.STUDENT,
        )
        student.phone = '09121234567'
        student.save()

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='آزمون فیزیک',
            description='مکانیک',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_STRUCTURED,
            exam_prep_json=json.dumps({
                'exam_prep': {
                    'questions': [
                        {
                            'question_id': '1',
                            'question_text_markdown': 'نیروی گرانش چیست؟',
                            'options': [{'label': 'الف', 'text': 'پاسخ یک'}],
                            'correct_option_label': 'الف',
                            'correct_option_text_markdown': 'پاسخ یک',
                            'teacher_solution_markdown': 'توضیحات معلم',
                            'final_answer_markdown': 'نیرویی که...',
                        },
                    ]
                }
            }),
            is_published=True,
        )
        ClassInvitation.objects.create(
            session=session,
            phone='09121234567',
            invite_code=str(uuid.uuid4())[:8],
        )

        return student, session

    def test_detail_requires_authentication(self, student_with_invite):
        """Detail should reject unauthenticated requests."""
        _, session = student_with_invite
        client = APIClient()
        res = client.get(f'/api/classes/student/exam-preps/{session.id}/')
        assert res.status_code == 401

    def test_detail_denied_to_uninvited_teacher(self, student_with_invite):
        """`IsStudentUser` allows teachers (learners); detail is phone-scoped, so
        an uninvited teacher gets 404 (not the data) — not a role-403.
        [policy note in test_student_courses.py]"""
        _, session = student_with_invite
        teacher = User.objects.create_user(username='teacher_det2', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(teacher).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get(f'/api/classes/student/exam-preps/{session.id}/')
        # Denied (no data leak): uninvited teacher — 400 (phone/enrollment) or 404.
        assert res.status_code in (400, 404)

    def test_student_can_get_exam_prep_detail(self, student_with_invite):
        """Student should be able to get exam prep details with questions."""
        student, session = student_with_invite
        token = str(RefreshToken.for_user(student).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get(f'/api/classes/student/exam-preps/{session.id}/')

        assert res.status_code == 200
        assert res.data['id'] == session.id
        assert res.data['title'] == 'آزمون فیزیک'
        assert len(res.data['questions']) == 1
        assert res.data['questions'][0]['question_text_markdown'] == 'نیروی گرانش چیست؟'
        assert res.data['questions'][0]['type'] == 'multiple_choice'

    def test_detail_repairs_legacy_question_with_duplicated_options(self, student_with_invite):
        student, session = student_with_invite
        session.exam_prep_json = json.dumps({
            'exam_prep': {
                'questions': [{
                    'question_id': 'q-1',
                    'question_text_markdown': r'کدام پاسخ درست است؟\n1) اول\n2) دوم',
                    'options': [
                        {'label': 'الف', 'text_markdown': 'اول'},
                        {'label': 'ب', 'text_markdown': 'دوم'},
                    ],
                    'correct_option_label': 'الف',
                }],
            },
        })
        session.save(update_fields=['exam_prep_json'])
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(student).access_token}'
        )

        response = client.get(f'/api/classes/student/exam-preps/{session.id}/')

        assert response.status_code == 200
        assert response.data['questions'][0]['question_text_markdown'] == 'کدام پاسخ درست است؟'
        session.refresh_from_db()
        stored = json.loads(session.exam_prep_json)
        assert stored['exam_prep']['questions'][0]['question_text_markdown'] == 'کدام پاسخ درست است؟'

    def test_student_cannot_access_uninvited_exam_prep(self, student_with_invite):
        """Student cannot access exam prep they're not invited to."""
        _, session = student_with_invite
        other_student = User.objects.create_user(
            username='other_student',
            password='pass',
            role=User.Role.STUDENT,
        )
        other_student.phone = '09999999999'
        other_student.save()

        token = str(RefreshToken.for_user(other_student).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get(f'/api/classes/student/exam-preps/{session.id}/')

        assert res.status_code == 404

    def test_student_cannot_access_unpublished_exam_prep(self):
        """Student cannot access unpublished exam prep."""
        from apps.classes.models import ClassInvitation
        import uuid

        teacher = User.objects.create_user(username='teacher_unpub', password='pass', role=User.Role.TEACHER)
        student = User.objects.create_user(
            username='student_unpub',
            password='pass',
            role=User.Role.STUDENT,
        )
        student.phone = '09121234567'
        student.save()

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='Draft Exam',
            pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
            status=ClassCreationSession.Status.EXAM_STRUCTURED,
            exam_prep_json=json.dumps({'exam_prep': {'questions': []}}),
            is_published=False,  # Not published
        )
        ClassInvitation.objects.create(
            session=session,
            phone='09121234567',
            invite_code=str(uuid.uuid4())[:8],
        )

        token = str(RefreshToken.for_user(student).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.get(f'/api/classes/student/exam-preps/{session.id}/')

        assert res.status_code == 404
