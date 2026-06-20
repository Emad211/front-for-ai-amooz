"""Forced post-login onboarding: a passwordless code-logged-in user sets the
username + password + email + phone + light profile they'll use from now on."""

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient

from apps.accounts.models import StudentProfile, TeacherProfile
from apps.accounts.services import get_or_create_student_by_phone

User = get_user_model()
URL = '/api/accounts/complete-onboarding/'
PHONE = '09120000000'
PWD = 'Zx9!konkur2026'


@pytest.mark.django_db
class TestOnboarding:
    def _student(self):
        user, _ = get_or_create_student_by_phone(PHONE)
        return user

    def test_requires_auth(self):
        resp = APIClient().post(URL, {'username': 'a', 'password': PWD}, format='json')
        assert resp.status_code in (401, 403)

    def test_student_completes_and_can_login(self):
        user = self._student()
        assert not user.has_usable_password()  # passwordless shell
        c = APIClient()
        c.force_authenticate(user=user)

        resp = c.post(URL, {
            'username': 'sara77', 'password': PWD, 'email': 'Sara@Example.com',
            'phone': PHONE, 'first_name': 'سارا', 'last_name': 'رضایی',
            'grade': 'دوازدهم', 'major': 'ریاضی فیزیک',
        }, format='json')

        assert resp.status_code == 200, resp.content
        assert resp.data['is_profile_completed'] is True
        user.refresh_from_db()
        assert user.username == 'sara77'
        assert user.has_usable_password() and user.check_password(PWD)
        assert user.email == 'sara@example.com'  # normalized lowercase
        assert user.is_profile_completed is True
        prof = StudentProfile.objects.get(user=user)
        assert prof.grade == '12' and prof.major == 'math'

        # From now on they log in with username + password.
        login = APIClient().post('/api/token/', {'username': 'sara77', 'password': PWD}, format='json')
        assert login.status_code == 200, login.content
        assert 'access' in login.data

    def test_duplicate_username_rejected(self):
        baker.make('accounts.User', username='taken')
        user = self._student()
        c = APIClient(); c.force_authenticate(user=user)
        resp = c.post(URL, {
            'username': 'taken', 'password': PWD, 'email': 'x@y.com',
            'phone': PHONE, 'first_name': 'x',
        }, format='json')
        assert resp.status_code == 400
        assert 'username' in resp.data.get('errors', resp.data)

    def test_student_phone_is_immutable(self):
        user = self._student()
        c = APIClient(); c.force_authenticate(user=user)
        resp = c.post(URL, {
            'username': 'sara77', 'password': PWD, 'email': 'x@y.com',
            'phone': '09120009999', 'first_name': 'x',  # different phone
        }, format='json')
        assert resp.status_code == 400
        assert 'phone' in resp.data.get('errors', resp.data)

    def test_weak_password_rejected(self):
        user = self._student()
        c = APIClient(); c.force_authenticate(user=user)
        resp = c.post(URL, {
            'username': 'sara77', 'password': '12345678', 'email': 'x@y.com',
            'phone': PHONE, 'first_name': 'x',
        }, format='json')
        assert resp.status_code == 400
        assert 'password' in resp.data.get('errors', resp.data)

    def test_rejects_already_completed_user(self):
        # Onboarding is one-time — a completed account can't re-run it (which
        # would change username/password with no old-password check).
        user = baker.make(
            'accounts.User', role=User.Role.STUDENT, phone='09120000022',
            is_profile_completed=True,
        )
        user.set_password('something'); user.save()
        c = APIClient(); c.force_authenticate(user=user)
        resp = c.post(URL, {
            'username': 'newname', 'password': PWD, 'email': 'a@b.com',
            'phone': '09120000022', 'first_name': 'x',
        }, format='json')
        assert resp.status_code == 400, resp.content

    def test_teacher_sets_phone_and_expertise(self):
        # A passwordless teacher shell (e.g. created by org-code redeem in Phase 2).
        teacher = baker.make('accounts.User', role=User.Role.TEACHER, phone=None, username='t_shell')
        teacher.set_unusable_password(); teacher.save()
        c = APIClient(); c.force_authenticate(user=teacher)

        resp = c.post(URL, {
            'username': 'ostad_ali', 'password': PWD, 'email': 'ali@school.ir',
            'phone': '+98 912 111 2222', 'first_name': 'علی', 'last_name': 'کریمی',
            'expertise': 'ریاضیات',
        }, format='json')

        assert resp.status_code == 200, resp.content
        teacher.refresh_from_db()
        assert teacher.phone == '09121112222'  # normalized, freely set for non-students
        assert teacher.has_usable_password()
        assert TeacherProfile.objects.get(user=teacher).expertise == 'ریاضیات'
