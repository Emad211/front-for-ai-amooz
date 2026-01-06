import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import StudentProfile


@pytest.mark.django_db
def test_invite_login_creates_student_and_returns_tokens():
    client = APIClient()

    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='ABC')

    resp = client.post(
        '/api/auth/invite-login/',
        {
            'code': 'ABC',
            'phone': '+989120000000',
        },
        format='json',
    )

    assert resp.status_code == 200
    assert resp.data['user']['role'] == 'STUDENT'
    assert resp.data['user']['phone'] == '09120000000'
    assert 'access' in resp.data['tokens']
    assert 'refresh' in resp.data['tokens']

    user_id = resp.data['user']['id']
    assert StudentProfile.objects.filter(user_id=user_id).exists()


@pytest.mark.django_db
def test_invite_login_rejects_unpublished_session():
    client = APIClient()

    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=False, title='t')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='ABC')

    resp = client.post('/api/auth/invite-login/', {'code': 'ABC', 'phone': '09120000000'}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_invite_login_rejects_non_student_user_with_same_phone():
    client = APIClient()

    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='ABC')

    baker.make('accounts.User', role='TEACHER', phone='09120000000')

    resp = client.post('/api/auth/invite-login/', {'code': 'ABC', 'phone': '09120000000'}, format='json')
    assert resp.status_code == 403
