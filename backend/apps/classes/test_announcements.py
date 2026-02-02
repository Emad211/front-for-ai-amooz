import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession


User = get_user_model()


@pytest.mark.django_db
class TestAnnouncements:
    def _auth_client(self, role: str = 'TEACHER') -> tuple[APIClient, User]:
        user = User.objects.create_user(username='t_ann', password='pass', role=getattr(User.Role, role))
        token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return client, user

    def _create_session(self, teacher: User, *, pipeline_type: str) -> ClassCreationSession:
        return ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='desc',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.TRANSCRIBED,
            transcript_markdown='hello',
            structure_json='{"root_object": {"title": "x"}, "outline": []}',
            pipeline_type=pipeline_type,
        )

    def test_class_announcements_crud(self):
        client, teacher = self._auth_client('TEACHER')
        session = self._create_session(teacher, pipeline_type=ClassCreationSession.PipelineType.CLASS)

        payload = {'title': 'اطلاعیه ۱', 'content': 'متن', 'priority': 'high'}
        res = client.post(f'/api/classes/creation-sessions/{session.id}/announcements/', payload, format='json')
        assert res.status_code == 201
        announcement_id = res.data['id']

        res = client.get(f'/api/classes/creation-sessions/{session.id}/announcements/')
        assert res.status_code == 200
        assert len(res.data) == 1

        patch_payload = {'title': 'اطلاعیه ویرایش شده'}
        res = client.patch(
            f'/api/classes/creation-sessions/{session.id}/announcements/{announcement_id}/',
            patch_payload,
            format='json',
        )
        assert res.status_code == 200
        assert res.data['title'] == 'اطلاعیه ویرایش شده'

        res = client.delete(
            f'/api/classes/creation-sessions/{session.id}/announcements/{announcement_id}/'
        )
        assert res.status_code == 204

        res = client.get(f'/api/classes/creation-sessions/{session.id}/announcements/')
        assert res.status_code == 200
        assert len(res.data) == 0

    def test_exam_prep_announcements_crud(self):
        client, teacher = self._auth_client('TEACHER')
        session = self._create_session(teacher, pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP)

        payload = {'title': 'اطلاعیه آزمون', 'content': 'متن', 'priority': 'medium'}
        res = client.post(f'/api/classes/exam-prep-sessions/{session.id}/announcements/', payload, format='json')
        assert res.status_code == 201
        announcement_id = res.data['id']

        res = client.get(f'/api/classes/exam-prep-sessions/{session.id}/announcements/')
        assert res.status_code == 200
        assert len(res.data) == 1

        patch_payload = {'content': 'متن جدید', 'priority': 'low'}
        res = client.patch(
            f'/api/classes/exam-prep-sessions/{session.id}/announcements/{announcement_id}/',
            patch_payload,
            format='json',
        )
        assert res.status_code == 200
        assert res.data['content'] == 'متن جدید'
        assert res.data['priority'] == 'low'

        res = client.delete(
            f'/api/classes/exam-prep-sessions/{session.id}/announcements/{announcement_id}/'
        )
        assert res.status_code == 204

        res = client.get(f'/api/classes/exam-prep-sessions/{session.id}/announcements/')
        assert res.status_code == 200
        assert len(res.data) == 0

    def test_exam_prep_patch_updates_fields(self):
        client, teacher = self._auth_client('TEACHER')
        session = self._create_session(teacher, pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP)

        payload = {
            'title': 'عنوان جدید',
            'description': 'توضیح جدید',
            'level': 'متوسط',
            'duration': '۶۰ دقیقه',
            'exam_prep_json': '{"exam_prep": {"title": "x", "questions": []}}',
        }
        res = client.patch(f'/api/classes/exam-prep-sessions/{session.id}/', payload, format='json')
        assert res.status_code == 200
        session.refresh_from_db()
        assert session.title == 'عنوان جدید'
        assert session.description == 'توضیح جدید'
        assert session.level == 'متوسط'
        assert session.duration == '۶۰ دقیقه'
        assert session.exam_prep_json == payload['exam_prep_json']
