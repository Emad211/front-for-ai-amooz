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


# ── effective completion (pre-curriculum students) ───────────────────────────
#
# A student who onboarded before the curriculum round carries the stored flag
# but no grade: their derived subject list stays silently empty. The completion
# signal must surface them as INCOMPLETE so the frontend gate routes them back
# into onboarding, and the onboarding endpoint must accept their re-completion.

BLOCKED = 'حساب شما قبلاً تکمیل شده است.'


class TestEffectiveProfileCompletion:
    def _completed_shell(self, phone, username):
        """A student whose stored flag says completed but who has no curriculum
        keys — the exact shape of every pre-round production account."""
        user, _ = get_or_create_student_by_phone(phone)
        user.username = username
        user.is_profile_completed = True
        user.save()
        return user

    def test_me_reports_incomplete_without_grade(self, student_client, student_user):
        student_user.is_profile_completed = True
        student_user.save()

        resp = student_client.get(ME_URL)

        assert resp.status_code == 200
        assert resp.data['is_profile_completed'] is False

    def test_hs_grade_without_major_still_incomplete(self, student_client, student_user):
        student_user.is_profile_completed = True
        student_user.save()
        prof = _profile(student_user)
        prof.grade = '10'
        prof.save(update_fields=['grade'])

        resp = student_client.get(ME_URL)

        assert resp.status_code == 200
        assert resp.data['is_profile_completed'] is False

    def test_hs_grade_plus_major_is_complete(self, student_client, student_user):
        student_user.is_profile_completed = True
        student_user.save()
        prof = _profile(student_user)
        prof.grade, prof.major = '10', 'math'
        prof.save(update_fields=['grade', 'major'])

        resp = student_client.get(ME_URL)

        assert resp.status_code == 200
        assert resp.data['is_profile_completed'] is True

    def test_middle_schooler_needs_only_the_grade(self, student_client, student_user):
        student_user.is_profile_completed = True
        student_user.save()
        prof = _profile(student_user)
        prof.grade = '07'
        prof.save(update_fields=['grade'])

        resp = student_client.get(ME_URL)

        assert resp.status_code == 200
        assert resp.data['is_profile_completed'] is True

    def test_non_student_flag_alone_is_enough(self, teacher_client, teacher_user):
        teacher_user.is_profile_completed = True
        teacher_user.save()

        resp = teacher_client.get(ME_URL)

        assert resp.status_code == 200
        assert resp.data['is_profile_completed'] is True

    def test_stored_false_stays_false_for_students(self, student_client, student_user):
        # A brand-new student (flag False) must never read as complete even if
        # someone seeded their profile keys out-of-band.
        student_user.is_profile_completed = False
        student_user.save()
        prof = _profile(student_user)
        prof.grade, prof.major = '11', 'science'
        prof.save(update_fields=['grade', 'major'])

        resp = student_client.get(ME_URL)

        assert resp.status_code == 200
        assert resp.data['is_profile_completed'] is False

    def test_pre_curriculum_student_can_recomplete_onboarding(self):
        user = self._completed_shell('09120000401', 'legacy_recomplete')
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(ONBOARDING_URL, {
            'username': 'legacy_recomplete', 'password': PWD, 'email': 'l@b.com',
            'phone': '09120000401', 'first_name': '',
            'grade': 'یازدهم', 'major': 'علوم انسانی',
        }, format='json')

        assert resp.status_code == 200, resp.content
        user.refresh_from_db()
        prof = _profile(user)
        assert prof.grade == '11' and prof.major == 'humanities'
        assert user.is_effectively_completed is True

    def test_blank_first_name_accepted_on_recompletion(self):
        user = self._completed_shell('09120000402', 'legacy_blankname')
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(ONBOARDING_URL, {
            'username': 'legacy_blankname2', 'password': PWD, 'email': 'm@b.com',
            'phone': '09120000402', 'first_name': '', 'last_name': '',
            'grade': 'پایه ششم',
        }, format='json')

        assert resp.status_code == 200, resp.content

    def test_truly_completed_student_still_blocked(self, student_user):
        student_user.is_profile_completed = True
        student_user.save()
        prof = _profile(student_user)
        prof.grade, prof.major = '10', 'math'
        prof.save(update_fields=['grade', 'major'])
        client = APIClient()
        client.force_authenticate(user=student_user)

        resp = client.post(ONBOARDING_URL, {
            'username': 'whatever', 'password': PWD, 'email': 'n@b.com',
            'phone': '09120000499', 'first_name': 'x',
        }, format='json')

        assert resp.status_code == 400
        assert BLOCKED in resp.data['detail']
