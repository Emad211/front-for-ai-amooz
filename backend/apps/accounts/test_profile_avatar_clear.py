import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient


User = get_user_model()


@pytest.mark.django_db
def test_clearing_avatar_persists_and_returns_null():
    user = User.objects.create_user(
        username='avatar_teacher',
        password='ExistingPass123!',
        role=User.Role.TEACHER,
    )
    user.avatar = SimpleUploadedFile('avatar.png', b'fake-image', content_type='image/png')
    user.save(update_fields=['avatar'])

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.patch('/api/accounts/me/', {'avatar': ''}, format='json')

    assert response.status_code == 200
    assert response.data['avatar'] is None
    user.refresh_from_db()
    assert not user.avatar
