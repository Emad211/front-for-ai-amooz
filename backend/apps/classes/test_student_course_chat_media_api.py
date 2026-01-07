import pytest
from model_bakery import baker
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation, StudentCourseChatMessage


@pytest.mark.django_db
class TestStudentChatMediaApi:
    def _make_student_client(self):
        student = baker.make(User, role=User.Role.STUDENT, phone='09920000000')
        client = APIClient()
        client.force_authenticate(user=student)
        return student, client

    def _make_session_for(self, phone: str):
        teacher = baker.make(User, role=User.Role.TEACHER)
        session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='Course')
        baker.make(ClassInvitation, session=session, phone=phone, invite_code='INV-1')
        return session

    def test_media_requires_file(self):
        student, client = self._make_student_client()
        session = self._make_session_for(student.phone)

        resp = client.post(f'/api/classes/student/courses/{session.id}/chat-media/', {'message': 'x'}, format='multipart')
        assert resp.status_code == 400

    def test_media_rejects_unsupported_mime(self):
        student, client = self._make_student_client()
        session = self._make_session_for(student.phone)

        file = SimpleUploadedFile('x.bin', b'123', content_type='application/octet-stream')
        resp = client.post(
            f'/api/classes/student/courses/{session.id}/chat-media/',
            {'file': file, 'message': 'x'},
            format='multipart',
        )
        assert resp.status_code == 400

    def test_image_upload_persists_user_and_assistant_messages(self, monkeypatch):
        monkeypatch.setattr(
            'apps.classes.views.handle_student_image_upload',
            lambda **_kwargs: {'type': 'text', 'content': 'image ok', 'suggestions': ['s1']},
        )

        student, client = self._make_student_client()
        session = self._make_session_for(student.phone)

        file = SimpleUploadedFile('x.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        resp = client.post(
            f'/api/classes/student/courses/{session.id}/chat-media/',
            {'file': file, 'message': 'این چیه؟', 'lesson_id': '1'},
            format='multipart',
        )
        assert resp.status_code == 200
        assert resp.data['type'] == 'text'

        msgs = StudentCourseChatMessage.objects.filter(thread__session=session, thread__student=student).order_by('created_at')
        assert msgs.count() == 2
        assert msgs[0].role == 'user'
        assert msgs[0].content == 'این چیه؟'
        assert msgs[1].role == 'assistant'
        assert msgs[1].content == 'image ok'

    def test_audio_upload_persists_combined_voice_transcript(self, monkeypatch):
        monkeypatch.setattr('apps.classes.views.transcribe_media_bytes', lambda *, data, mime_type: ('TRANSCRIPT', 'p', 'm'))
        monkeypatch.setattr(
            'apps.classes.views.handle_student_audio_upload',
            lambda **_kwargs: {'type': 'text', 'content': 'audio ok', 'suggestions': []},
        )

        student, client = self._make_student_client()
        session = self._make_session_for(student.phone)

        file = SimpleUploadedFile('v.ogg', b'fake-audio', content_type='audio/ogg')
        resp = client.post(
            f'/api/classes/student/courses/{session.id}/chat-media/',
            {'file': file, 'message': 'گفتم', 'lesson_id': '1'},
            format='multipart',
        )
        assert resp.status_code == 200
        assert resp.data['type'] == 'text'

        msgs = StudentCourseChatMessage.objects.filter(thread__session=session, thread__student=student).order_by('created_at')
        assert msgs.count() == 2
        assert msgs[0].role == 'user'
        assert 'VOICE_TRANSCRIPT' in msgs[0].content
        assert 'TRANSCRIPT' in msgs[0].content
