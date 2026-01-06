import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.classes.models import ClassCreationSession, ClassInvitation


@pytest.mark.django_db
def test_invite_code_verify_returns_false_when_missing():
    client = APIClient()
    res = client.post('/api/classes/invites/verify/', {'code': 'INV-NOT-FOUND'}, format='json')
    assert res.status_code == 200
    assert res.data['valid'] is False


@pytest.mark.django_db
def test_invite_code_verify_returns_false_when_not_published():
    teacher = baker.make(User, role=User.Role.TEACHER)
    session = baker.make(ClassCreationSession, teacher=teacher, is_published=False, title='T')
    baker.make(ClassInvitation, session=session, phone='09920000000', invite_code='INV-TEST')

    client = APIClient()
    res = client.post('/api/classes/invites/verify/', {'code': 'INV-TEST'}, format='json')
    assert res.status_code == 200
    assert res.data['valid'] is False


@pytest.mark.django_db
def test_invite_code_verify_returns_true_for_published():
    teacher = baker.make(User, role=User.Role.TEACHER)
    session = baker.make(ClassCreationSession, teacher=teacher, is_published=True, title='My Class')
    baker.make(ClassInvitation, session=session, phone='09920000000', invite_code='INV-OK')

    client = APIClient()
    res = client.post('/api/classes/invites/verify/', {'code': 'INV-OK'}, format='json')
    assert res.status_code == 200
    assert res.data['valid'] is True
    assert res.data['session_id'] == session.id
    assert res.data['title'] == session.title
