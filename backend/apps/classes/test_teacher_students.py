import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.classes.models import ClassCreationSession


User = get_user_model()


@pytest.mark.django_db
def test_teacher_students_list_returns_invited_phones():
    teacher = User.objects.create_user(username='t_students', password='pass', role=User.Role.TEACHER)
    token = str(RefreshToken.for_user(teacher).access_token)

    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title='t',
        description='',
        source_file=SimpleUploadedFile('audio.ogg', b'fake-audio', content_type='audio/ogg'),
        source_mime_type='audio/ogg',
        source_original_name='audio.ogg',
        status=ClassCreationSession.Status.TRANSCRIBED,
        transcript_markdown='hello',
        is_published=True,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # Create invite via API to ensure it uses the unified invite-code generation.
    res = client.post(
        f'/api/classes/creation-sessions/{session.id}/invites/',
        {'phones': ['09120000000']},
        format='json',
    )
    assert res.status_code == 200

    res2 = client.get('/api/classes/teacher/students/')
    assert res2.status_code == 200
    assert isinstance(res2.data, list)
    assert len(res2.data) == 1
    assert res2.data[0]['phone'] == '09120000000'
