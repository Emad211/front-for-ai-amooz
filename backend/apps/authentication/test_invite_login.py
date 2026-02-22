import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import StudentProfile

User = get_user_model()


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
def test_invite_login_allows_multi_role_same_phone():
    """A phone used by a TEACHER can still login as STUDENT via invite code.

    The system should create a new STUDENT User record for the same phone.
    """
    client = APIClient()

    # Create a teacher with this phone
    baker.make('accounts.User', role='TEACHER', phone='09120000000', username='teacher_phone')

    # Set up invite for same phone
    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='MULTI')

    resp = client.post('/api/auth/invite-login/', {'code': 'MULTI', 'phone': '09120000000'}, format='json')

    assert resp.status_code == 200
    assert resp.data['user']['role'] == 'STUDENT'

    # Should be a different user from the teacher
    student_user_id = resp.data['user']['id']
    teacher_user = User.objects.get(username='teacher_phone')
    assert student_user_id != teacher_user.id

    # Both users should exist with the same phone
    users_with_phone = User.objects.filter(phone='09120000000')
    assert users_with_phone.count() == 2
    assert set(users_with_phone.values_list('role', flat=True)) == {'TEACHER', 'STUDENT'}


@pytest.mark.django_db
def test_invite_login_reuses_existing_student_same_phone():
    """If a STUDENT account already exists for this phone, reuse it."""
    client = APIClient()

    # Create both teacher and student with same phone
    baker.make('accounts.User', role='TEACHER', phone='09120000000', username='teacher_user')
    existing_student = baker.make('accounts.User', role='STUDENT', phone='09120000000', username='student_user')

    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='REUSE')

    resp = client.post('/api/auth/invite-login/', {'code': 'REUSE', 'phone': '09120000000'}, format='json')

    assert resp.status_code == 200
    assert resp.data['user']['id'] == existing_student.id
    assert resp.data['user']['role'] == 'STUDENT'


@pytest.mark.django_db
def test_invite_login_creates_student_when_only_admin_has_phone():
    """Admin phone should not block student invite code login."""
    client = APIClient()

    baker.make('accounts.User', role='ADMIN', phone='09130000000', username='admin_user')

    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    baker.make('classes.ClassInvitation', session=session, phone='09130000000', invite_code='ADMPHONE')

    resp = client.post('/api/auth/invite-login/', {'code': 'ADMPHONE', 'phone': '09130000000'}, format='json')

    assert resp.status_code == 200
    assert resp.data['user']['role'] == 'STUDENT'

    # Admin still exists
    assert User.objects.filter(role='ADMIN', phone='09130000000').exists()


@pytest.mark.django_db
def test_invite_login_wrong_code():
    client = APIClient()

    teacher = baker.make('accounts.User')
    session = baker.make('classes.ClassCreationSession', teacher=teacher, is_published=True, title='t')
    baker.make('classes.ClassInvitation', session=session, phone='09120000000', invite_code='GOOD')

    resp = client.post('/api/auth/invite-login/', {'code': 'BAD', 'phone': '09120000000'}, format='json')
    assert resp.status_code == 400
