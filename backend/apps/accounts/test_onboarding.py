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
        assert resp.data['grade'] == 'دوازدهم'
        assert resp.data['major'] == 'ریاضی فیزیک'
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
        # Onboarding is one-time — an EFFECTIVELY completed account can't re-run
        # it (which would change username/password with no old-password check).
        # Stored flag alone no longer counts: a pre-curriculum student must be
        # allowed through to pick their grade/major.
        user = baker.make(
            'accounts.User', role=User.Role.STUDENT, phone='09120000022',
            is_profile_completed=True,
        )
        user.set_password('something'); user.save()
        profile, _ = StudentProfile.objects.get_or_create(user=user)
        profile.grade, profile.major = '10', 'math'
        profile.save(update_fields=['grade', 'major'])

        c = APIClient(); c.force_authenticate(user=user)
        resp = c.post(URL, {
            'username': 'newname', 'password': PWD, 'email': 'a@b.com',
            'phone': '09120000022', 'first_name': 'x',
        }, format='json')
        assert resp.status_code == 400, resp.content

    def test_student_grade_required_no_loop(self):
        # Regression for the onboarding bounce loop: completing WITHOUT a grade
        # used to flip the stored flag to True while the gate computes EFFECTIVE
        # completion (flag + grade) as False — the student was bounced back into
        # the wizard, which restarts from step 1, forever. The server must
        # refuse and leave the flag False so the flow terminates.
        user = self._student()
        c = APIClient(); c.force_authenticate(user=user)
        resp = c.post(URL, {
            'username': 'sara77', 'password': PWD, 'email': 'x@y.com',
            'phone': PHONE, 'first_name': 'سارا',
        }, format='json')  # no grade
        assert resp.status_code == 400, resp.content
        assert 'grade' in resp.data.get('errors', resp.data)
        user.refresh_from_db()
        assert user.is_profile_completed is False
        assert user.is_effectively_completed is False

    def test_student_highschool_major_required(self):
        # Grade 10-12 without a major → 400 on 'major' (the MeUpdateSerializer
        # cross-field rule) and the flag must stay False.
        user = self._student()
        c = APIClient(); c.force_authenticate(user=user)
        resp = c.post(URL, {
            'username': 'sara77', 'password': PWD, 'email': 'x@y.com',
            'phone': PHONE, 'first_name': 'سارا', 'grade': 'دهم',
        }, format='json')
        assert resp.status_code == 400, resp.content
        assert 'major' in resp.data.get('errors', resp.data)
        user.refresh_from_db()
        assert user.is_profile_completed is False

    def test_student_without_phone_can_set_it(self):
        # Regression for the step-2 dead end: a username-created student shell
        # has NO phone, and the (previously read-only) empty field could never
        # pass validation. The backend must accept a first-time phone set.
        user = baker.make('accounts.User', role=User.Role.STUDENT, phone=None, username='phoneless')
        user.set_unusable_password(); user.save()
        c = APIClient(); c.force_authenticate(user=user)
        resp = c.post(URL, {
            'username': 'phoneless', 'password': PWD, 'email': 'x@y.com',
            'phone': '09123456789', 'first_name': 'x',
            'grade': 'دهم', 'major': 'ریاضی فیزیک',
        }, format='json')
        assert resp.status_code == 200, resp.content
        user.refresh_from_db()
        assert user.phone == '09123456789'
        assert user.is_effectively_completed is True

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
