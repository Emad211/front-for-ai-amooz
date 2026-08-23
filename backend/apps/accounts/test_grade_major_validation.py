"""Conditional grade/major rule on the accounts write paths (advisor-mvp Step 9).

Owner decision: submitted grade ∈ {10,11,12} ⇒ major REQUIRED with the exact
Persian error «برای پایه‌های دهم تا دوازدهم انتخاب رشته الزامی است.»; grade ≤ 09
⇒ any submitted major is ignored/nulled. Covered on both endpoints that write
these fields: ``PATCH /api/accounts/me/`` (MeUpdateSerializer) and
``POST /api/accounts/complete-onboarding/`` (delegates the same fields through
MeUpdateSerializer, so one rule must hold on both).

Zero LLM, no network.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StudentProfile
from apps.accounts.services import get_or_create_student_by_phone

ME_URL = '/api/accounts/me/'
ONBOARDING_URL = '/api/accounts/complete-onboarding/'
HS_ERROR = 'برای پایه‌های دهم تا دوازدهم انتخاب رشته الزامی است.'
PWD = 'Zx9!konkur2026'

pytestmark = pytest.mark.django_db


def _profile(user) -> StudentProfile:
    return StudentProfile.objects.get(user=user)


# ── PATCH /api/accounts/me/ ───────────────────────────────────────────────────

class TestMePatchConditionalMajor:
    def test_hs_grade_without_major_is_rejected(self, student_client, student_user):
        resp = student_client.patch(ME_URL, {'grade': '10'}, format='json')
        assert resp.status_code == 400
        assert HS_ERROR in resp.data['errors']['major']
        assert _profile(student_user).grade is None   # nothing was written

    def test_hs_grade_with_major_label_is_saved(self, student_client, student_user):
        resp = student_client.patch(
            ME_URL, {'grade': 'دهم', 'major': 'ریاضی فیزیک'}, format='json',
        )
        assert resp.status_code == 200, resp.content
        prof = _profile(student_user)
        assert prof.grade == '10' and prof.major == 'math'

    def test_hs_grade_accepts_the_new_major_codes(self, student_client, student_user):
        resp = student_client.patch(
            ME_URL, {'grade': '12', 'major': 'علوم و معارف اسلامی'}, format='json',
        )
        assert resp.status_code == 200, resp.content
        assert _profile(student_user).major == 'theology'

    def test_clearing_major_on_an_hs_student_is_rejected(self, student_client, student_user):
        """A partial update cannot strip a high-schooler's track: the effective
        (existing) grade still demands a major."""
        prof = _profile(student_user)
        prof.grade, prof.major = '10', 'science'
        prof.save(update_fields=['grade', 'major'])

        resp = student_client.patch(ME_URL, {'major': None}, format='json')
        assert resp.status_code == 400
        assert HS_ERROR in resp.data['errors']['major']
        prof.refresh_from_db()
        assert prof.major == 'science'                # untouched

    def test_grade_09_nulls_any_submitted_major(self, student_client, student_user):
        resp = student_client.patch(
            ME_URL, {'grade': 'نهم', 'major': 'علوم تجربی'}, format='json',
        )
        assert resp.status_code == 200, resp.content
        prof = _profile(student_user)
        assert prof.grade == '09' and prof.major is None

    def test_grade_codes_below_ten_are_accepted(self, student_client, student_user):
        resp = student_client.patch(ME_URL, {'grade': '02'}, format='json')
        assert resp.status_code == 200, resp.content
        assert _profile(student_user).grade == '02'

    def test_moving_down_from_hs_clears_a_submitted_major(self, student_client, student_user):
        prof = _profile(student_user)
        prof.grade, prof.major = '11', 'math'
        prof.save(update_fields=['grade', 'major'])

        resp = student_client.patch(ME_URL, {'grade': '07'}, format='json')
        assert resp.status_code == 200, resp.content
        prof.refresh_from_db()
        assert prof.grade == '07' and prof.major is None

    def test_invalid_major_still_rejected(self, student_client):
        resp = student_client.patch(ME_URL, {'grade': '10', 'major': 'art'}, format='json')
        assert resp.status_code == 400
        assert 'رشته تحصیلی نامعتبر است.' in resp.data['errors']['major']

    def test_invalid_grade_still_rejected(self, student_client):
        resp = student_client.patch(ME_URL, {'grade': '13'}, format='json')
        assert resp.status_code == 400
        assert 'پایه تحصیلی نامعتبر است.' in resp.data['errors']['grade']

    def test_non_student_profiles_ignore_grade_major(self, teacher_client):
        """The rule (and the fields themselves) are student-only; a teacher's
        payload is silently dropped and no StudentProfile row appears."""
        resp = teacher_client.patch(ME_URL, {'grade': '10', 'major': 'math'}, format='json')
        assert resp.status_code == 200
        assert not StudentProfile.objects.exists()


# ── POST /api/accounts/complete-onboarding/ ───────────────────────────────────

class TestOnboardingConditionalMajor:
    def _shell(self, phone):
        user, _ = get_or_create_student_by_phone(phone)
        return user

    def test_hs_grade_without_major_is_rejected(self):
        user = self._shell('09120000301')
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(ONBOARDING_URL, {
            'username': 'hs_no_track', 'password': PWD, 'email': 'a@b.com',
            'phone': '09120000301', 'first_name': 'x',
            'grade': 'دهم',
        }, format='json')

        assert resp.status_code == 400
        assert HS_ERROR in resp.data['errors']['major']
        user.refresh_from_db()
        assert not user.is_profile_completed          # onboarding did not complete

    def test_middle_school_major_is_nulled(self):
        user = self._shell('09120000302')
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(ONBOARDING_URL, {
            'username': 'mid_school', 'password': PWD, 'email': 'b@b.com',
            'phone': '09120000302', 'first_name': 'y',
            'grade': 'هفتم', 'major': 'ریاضی فیزیک',
        }, format='json')

        assert resp.status_code == 200, resp.content
        prof = _profile(user)
        assert prof.grade == '07' and prof.major is None

    def test_hs_with_major_completes(self):
        user = self._shell('09120000303')
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(ONBOARDING_URL, {
            'username': 'hs_technical', 'password': PWD, 'email': 'c@b.com',
            'phone': '09120000303', 'first_name': 'z',
            'grade': 'دوازدهم', 'major': 'فنی و حرفه‌ای و کاردانش',
        }, format='json')

        assert resp.status_code == 200, resp.content
        prof = _profile(user)
        assert prof.grade == '12' and prof.major == 'technical'
