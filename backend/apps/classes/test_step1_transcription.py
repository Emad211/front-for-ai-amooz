import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
import uuid

from apps.classes.models import ClassCreationSession


User = get_user_model()


@pytest.mark.django_db
class TestClassCreationStep1Transcription:
    @pytest.fixture(autouse=True)
    def _disable_async_pipeline(self, settings):
        settings.CLASS_PIPELINE_ASYNC = False

    def test_requires_authentication(self):
        client = APIClient()

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        res = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 't', 'description': 'd', 'file': upload},
            format='multipart',
        )

        assert res.status_code == 401

    def test_requires_teacher_role(self):
        user = User.objects.create_user(username='s1', password='pass', role=User.Role.STUDENT)
        token = str(RefreshToken.for_user(user).access_token)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        res = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 't', 'description': 'd', 'file': upload},
            format='multipart',
        )

        assert res.status_code == 403

    def test_teacher_can_transcribe_and_session_is_saved(self, monkeypatch):
        user = User.objects.create_user(username='t1', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(user).access_token)

        def _fake_transcribe_media_bytes(*, data: bytes, mime_type: str):
            assert data
            assert mime_type.startswith('audio/')
            return ('# transcript\nhello', 'gemini', 'models/gemini-2.5-flash')

        monkeypatch.setattr(
            'apps.classes.views.transcribe_media_bytes',
            _fake_transcribe_media_bytes,
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        res = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 'عنوان', 'description': 'توضیح', 'file': upload},
            format='multipart',
        )

        assert res.status_code == 201
        assert res.data['status'] == ClassCreationSession.Status.TRANSCRIBED
        assert res.data['transcript_markdown'] == '# transcript\nhello'
        assert res.data['source_mime_type'] == 'audio/ogg'
        assert res.data['source_original_name'] == 'audio.ogg'

        session = ClassCreationSession.objects.get(id=res.data['id'])
        assert session.teacher_id == user.id
        assert session.title == 'عنوان'
        assert session.transcript_markdown == '# transcript\nhello'
        assert session.status == ClassCreationSession.Status.TRANSCRIBED

    def test_step1_is_idempotent_with_client_request_id(self, monkeypatch):
        user = User.objects.create_user(username='t2', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(user).access_token)

        calls = {'count': 0}

        def _fake_transcribe_media_bytes(*, data: bytes, mime_type: str):
            calls['count'] += 1
            return ('# transcript\nhello', 'gemini', 'models/gemini-2.5-flash')

        monkeypatch.setattr('apps.classes.views.transcribe_media_bytes', _fake_transcribe_media_bytes)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        req_id = str(uuid.uuid4())
        upload1 = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        res1 = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 't', 'description': 'd', 'file': upload1, 'client_request_id': req_id},
            format='multipart',
        )
        assert res1.status_code == 201
        session_id = res1.data['id']
        assert calls['count'] == 1

        # Retry same request id -> should NOT create a new session or re-run transcription.
        upload2 = SimpleUploadedFile('audio2.ogg', b'fake-audio-2', content_type='audio/ogg')
        res2 = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 't', 'description': 'd', 'file': upload2, 'client_request_id': req_id},
            format='multipart',
        )
        assert res2.status_code == 200
        assert res2.data['id'] == session_id
        assert calls['count'] == 1

        assert ClassCreationSession.objects.filter(teacher=user, client_request_id=req_id).count() == 1

    def test_step1_returns_rich_error_payload_on_provider_failure(self, monkeypatch):
        user = User.objects.create_user(username='t3', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(user).access_token)

        def _fake_transcribe_media_bytes(*, data: bytes, mime_type: str):
            raise RuntimeError('provider boom')

        monkeypatch.setattr('apps.classes.views.transcribe_media_bytes', _fake_transcribe_media_bytes)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        upload = SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg')
        res = client.post(
            '/api/classes/creation-sessions/step-1/',
            {'title': 't', 'description': 'd', 'file': upload},
            format='multipart',
        )

        assert res.status_code == 502
        assert res.data['detail']
        assert res.data['session_id']
        assert res.data['status'] == ClassCreationSession.Status.FAILED
        assert 'error_detail' in res.data

        session = ClassCreationSession.objects.get(id=res.data['session_id'])
        assert session.status == ClassCreationSession.Status.FAILED
        assert 'provider boom' in session.error_detail


@pytest.mark.django_db
class TestClassCreationStep2Structure:
    @pytest.fixture(autouse=True)
    def _disable_async_pipeline(self, settings):
        settings.CLASS_PIPELINE_ASYNC = False

    def test_requires_authentication(self):
        client = APIClient()
        res = client.post('/api/classes/creation-sessions/step-2/', {'session_id': 1}, format='json')
        assert res.status_code == 401

    def test_requires_teacher_role(self):
        user = User.objects.create_user(username='s2', password='pass', role=User.Role.STUDENT)
        token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post('/api/classes/creation-sessions/step-2/', {'session_id': 1}, format='json')
        assert res.status_code == 403

    def test_returns_404_for_other_teachers_session(self):
        teacher1 = User.objects.create_user(username='t4', password='pass', role=User.Role.TEACHER)
        teacher2 = User.objects.create_user(username='t5', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(teacher2).access_token)

        session = ClassCreationSession.objects.create(
            teacher=teacher1,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.TRANSCRIBED,
            transcript_markdown='hello',
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post('/api/classes/creation-sessions/step-2/', {'session_id': session.id}, format='json')
        assert res.status_code == 404

    def test_returns_400_if_transcript_missing(self):
        teacher = User.objects.create_user(username='t6', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(teacher).access_token)

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.TRANSCRIBED,
            transcript_markdown='',
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = client.post('/api/classes/creation-sessions/step-2/', {'session_id': session.id}, format='json')
        assert res.status_code == 400

    def test_teacher_can_structure_and_session_is_saved(self, monkeypatch):
        teacher = User.objects.create_user(username='t7', password='pass', role=User.Role.TEACHER)
        token = str(RefreshToken.for_user(teacher).access_token)

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.TRANSCRIBED,
            transcript_markdown='## transcript\nhello',
        )

        def _fake_structure_transcript_markdown(*, transcript_markdown: str):
            assert 'transcript' in transcript_markdown
            return ({'root_object': {'title': 'x'}, 'outline': []}, 'gemini', 'models/gemini-2.5-flash')

        monkeypatch.setattr('apps.classes.views.structure_transcript_markdown', _fake_structure_transcript_markdown)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = client.post('/api/classes/creation-sessions/step-2/', {'session_id': session.id}, format='json')
        assert res.status_code == 200
        assert res.data['status'] == ClassCreationSession.Status.STRUCTURED
        assert 'structure_json' in res.data

        session.refresh_from_db()
        assert session.status == ClassCreationSession.Status.STRUCTURED
        assert session.structure_json
