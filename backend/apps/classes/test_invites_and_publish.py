import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession, ClassInvitation


User = get_user_model()


@pytest.mark.django_db
class TestClassCreationSessionPublishAndInvites:
    def _auth_client(self, role: str = 'TEACHER') -> tuple[APIClient, User]:
        user = User.objects.create_user(username='t_inv', password='pass', role=getattr(User.Role, role))
        token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return client, user

    def test_publish_requires_structured(self):
        client, teacher = self._auth_client('TEACHER')

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.TRANSCRIBED,
            transcript_markdown='hello',
            structure_json='',
        )

        res = client.post(f'/api/classes/creation-sessions/{session.id}/publish/')
        assert res.status_code == 400

    def test_publish_marks_session_published(self):
        client, teacher = self._auth_client('TEACHER')

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.STRUCTURED,
            transcript_markdown='hello',
            structure_json='{"root_object": {"title": "x"}, "outline": []}',
        )

        res = client.post(f'/api/classes/creation-sessions/{session.id}/publish/')
        assert res.status_code == 200
        session.refresh_from_db()
        assert session.is_published is True
        assert session.published_at is not None

    def test_patch_updates_title_description_and_structure(self):
        client, teacher = self._auth_client('TEACHER')

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.STRUCTURED,
            transcript_markdown='hello',
            structure_json='{"root_object": {"title": "x"}, "outline": []}',
        )

        payload = {
            'title': 'عنوان جدید',
            'description': 'توضیح جدید',
            'structure_json': {'root_object': {'title': 'y'}, 'outline': []},
        }
        res = client.patch(
            f'/api/classes/creation-sessions/{session.id}/',
            payload,
            format='json',
        )
        assert res.status_code == 200

        session.refresh_from_db()
        assert session.title == 'عنوان جدید'
        assert session.description == 'توضیح جدید'
        assert '"title": "y"' in session.structure_json

    def test_invites_crud(self):
        client, teacher = self._auth_client('TEACHER')

        session = ClassCreationSession.objects.create(
            teacher=teacher,
            title='t',
            description='',
            source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
            source_mime_type='audio/ogg',
            source_original_name='audio.ogg',
            status=ClassCreationSession.Status.TRANSCRIBED,
            transcript_markdown='hello',
        )

        res = client.post(
            f'/api/classes/creation-sessions/{session.id}/invites/',
            {'phones': ['09120000000', '09120000001']},
            format='json',
        )
        assert res.status_code == 200
        assert ClassInvitation.objects.filter(session=session).count() == 2

        res2 = client.get(f'/api/classes/creation-sessions/{session.id}/invites/')
        assert res2.status_code == 200
        assert len(res2.data) == 2

        invite_id = res2.data[0]['id']
        res3 = client.delete(f'/api/classes/creation-sessions/{session.id}/invites/{invite_id}/')
        assert res3.status_code == 204
        assert ClassInvitation.objects.filter(session=session).count() == 1
