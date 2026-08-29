"""S4 (national-curriculum redesign) — ``scope.curriculum_subjects``: the query
that derives a student's candidate subjects from their *own* ``(grade, major)``.

This is the heart of the S4→national reversal. The flat org catalog
(``assignable_subjects``) is no longer what an advisor may focus; the candidate
set is **derived** from the student's profile. So these tests pin the three
identity axes the derivation reads (grade, major, org scope), the active gate, and
the two ways it must stay *quiet* — no profile, or no grade — returning an empty
queryset rather than raising.

Zero LLM, no network. Real Postgres though: the org-scope half leans on live
membership joins, same as ``advisor_organization_ids``.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker

from apps.advisory.models import Subject
from apps.advisory.services.scope import curriculum_subjects
from apps.organizations.models import Organization, OrganizationMembership

User = get_user_model()
OrgRole = OrganizationMembership.OrgRole
MStatus = OrganizationMembership.MemberStatus
SubStatus = Organization.SubscriptionStatus

pytestmark = pytest.mark.django_db


def _student(*, grade='10', major='math', username='stu'):
    """A student whose auto-created profile carries the two curriculum axes."""
    user = baker.make(User, username=username, role=User.Role.STUDENT)
    profile = user.studentprofile
    profile.grade = grade
    profile.major = major
    profile.save(update_fields=['grade', 'major'])
    return user


def _member_of(student, org, *, org_role=OrgRole.STUDENT, status=MStatus.ACTIVE):
    baker.make(
        OrganizationMembership, user=student, organization=org,
        org_role=org_role, status=status,
    )


def _names(qs) -> list[str]:
    return sorted(qs.values_list('name', flat=True))


# ── the three identity axes: grade, major, and general (major-NULL) ────────────

def test_a_major_specific_subject_derives_for_a_matching_student():
    student = _student(grade='10', major='math')
    Subject.objects.create(name='هندسه', grade='10', major='math')
    assert _names(curriculum_subjects(student)) == ['هندسه']


def test_a_general_subject_derives_for_every_major_of_the_grade():
    """A NULL-major subject is shared across all majors of its grade."""
    math_student = _student(grade='10', major='math', username='m')
    sci_student = _student(grade='10', major='science', username='s')
    Subject.objects.create(name='ادبیات فارسی', grade='10')  # major NULL → general

    assert _names(curriculum_subjects(math_student)) == ['ادبیات فارسی']
    assert _names(curriculum_subjects(sci_student)) == ['ادبیات فارسی']


def test_another_majors_subject_does_not_derive():
    student = _student(grade='10', major='math')
    Subject.objects.create(name='زیست', grade='10', major='science')
    assert list(curriculum_subjects(student)) == []


def test_an_out_of_band_grade_does_not_derive():
    """Exact-own-grade still holds OUTSIDE the high-school band: a نهمی never
    derives a دهم row (the multi-grade window spans 10–12 only)."""
    student = _student(grade='09', major=None)
    Subject.objects.create(name='فارسی نهم', grade='09')
    Subject.objects.create(name='فارسی دهم', grade='10')
    assert _names(curriculum_subjects(student)) == ['فارسی نهم']


def test_a_dead_grade_null_subject_derives_for_nobody():
    """The S4 reversal: a NULL-grade row is dead/legacy, never «all levels»."""
    student = _student(grade='10', major='math')
    Subject.objects.create(name='زبان')  # grade NULL
    assert list(curriculum_subjects(student)) == []


# ── the quiet-empty cases: no exception, just .none() ──────────────────────────

def test_a_student_with_no_grade_derives_nothing():
    student = _student(grade=None, major='math')
    Subject.objects.create(name='هندسه', grade='10', major='math')
    assert list(curriculum_subjects(student)) == []


def test_a_student_without_a_profile_derives_nothing():
    """Defensive: no ``StudentProfile`` at all → ``.none()``, never AttributeError.

    The ``post_save`` signal normally guarantees a profile, so this deletes it to
    exercise the ``hasattr`` guard on a fresh, un-cached instance.
    """
    student = _student()
    student.studentprofile.delete()
    Subject.objects.create(name='هندسه', grade='10', major='math')

    fresh = User.objects.get(pk=student.pk)  # no cached reverse relation
    assert list(curriculum_subjects(fresh)) == []


def test_a_null_major_student_gets_only_general_subjects():
    """No declared track → only the grade's general (major-NULL) subjects, never a
    major-specific one."""
    student = _student(grade='10', major=None)
    Subject.objects.create(name='ادبیات فارسی', grade='10')          # general
    Subject.objects.create(name='هندسه', grade='10', major='math')   # major-specific
    assert _names(curriculum_subjects(student)) == ['ادبیات فارسی']


# ── the active gate ────────────────────────────────────────────────────────────

def test_an_inactive_subject_never_derives():
    """``is_active=True`` is filtered in the derivation, so a retired subject is
    genuinely non-assignable — not merely hidden from a picker."""
    student = _student(grade='10', major='math')
    Subject.objects.create(name='هندسه', grade='10', major='math', is_active=False)
    assert list(curriculum_subjects(student)) == []


# ── organization scope: national base + the student's own active orgs ──────────

def test_a_national_subject_derives_without_any_membership():
    student = _student(grade='10', major='math')
    Subject.objects.create(name='هندسه', grade='10', major='math')  # organization=None
    assert _names(curriculum_subjects(student)) == ['هندسه']


def test_a_private_subject_derives_only_for_a_member_student():
    org = baker.make(Organization, slug='org-a')
    outsider = _student(grade='10', major='math', username='out')
    insider = _student(grade='10', major='math', username='in')
    _member_of(insider, org)
    Subject.objects.create(name='المپیاد', grade='10', major='math', organization=org)

    assert list(curriculum_subjects(outsider)) == []
    assert _names(curriculum_subjects(insider)) == ['المپیاد']


def test_a_private_subject_of_an_inactive_subscription_org_is_gated_out():
    """C1 on the student side: an expired org goes dark live, no signal fired."""
    org = baker.make(Organization, slug='org-a', subscription_status=SubStatus.EXPIRED)
    student = _student(grade='10', major='math')
    _member_of(student, org)
    Subject.objects.create(name='المپیاد', grade='10', major='math', organization=org)
    assert list(curriculum_subjects(student)) == []


def test_a_suspended_membership_loses_private_subjects_immediately():
    org = baker.make(Organization, slug='org-a')
    student = _student(grade='10', major='math')
    _member_of(student, org, status=MStatus.SUSPENDED)
    Subject.objects.create(name='المپیاد', grade='10', major='math', organization=org)
    assert list(curriculum_subjects(student)) == []


def test_a_non_student_membership_grants_no_private_subjects():
    """Being a *teacher* of an org is not being its student — the student-side scope
    filters on ``OrgRole.STUDENT``."""
    org = baker.make(Organization, slug='org-a')
    student = _student(grade='10', major='math')
    _member_of(student, org, org_role=OrgRole.TEACHER)
    Subject.objects.create(name='المپیاد', grade='10', major='math', organization=org)
    assert list(curriculum_subjects(student)) == []


# ── the multi-grade high-school window (Step 9) ───────────────────────────────

def test_a_high_schooler_derives_all_three_grades():
    """Locked decision: a student in 10/11/12 derives own-major ∪ general rows from
    ALL THREE grades — a یازدهمی still sees the دهم courses they study or retake."""
    student = _student(grade='11', major='math')
    Subject.objects.create(name='هندسه', grade='10', major='math')
    Subject.objects.create(name='حسابان', grade='11', major='math')
    Subject.objects.create(name='گسسته', grade='12', major='math')
    assert set(_names(curriculum_subjects(student))) == {'هندسه', 'حسابان', 'گسسته'}


def test_the_hs_window_carries_general_rows_across_grades_too():
    student = _student(grade='12', major='science')
    Subject.objects.create(name='سلامت و بهداشت', grade='10')   # general
    Subject.objects.create(name='فیزیک ۳', grade='12', major='science')
    assert set(_names(curriculum_subjects(student))) == {'سلامت و بهداشت', 'فیزیک ۳'}


def test_the_hs_window_never_crosses_the_major_line():
    """The window widens the grade axis only: another major's row stays hidden even
    inside the band."""
    student = _student(grade='11', major='math')
    Subject.objects.create(name='زیست‌شناسی ۲', grade='10', major='science')
    assert list(curriculum_subjects(student)) == []


def test_grade_seven_is_exact_own_grade_only():
    """تک‌پایه: a هفتمی derives ONLY '07' rows — not 08/09, and not the HS band."""
    student = _student(grade='07', major=None)
    Subject.objects.create(name='ریاضیات هفتم', grade='07')
    Subject.objects.create(name='علوم هشتم', grade='08')
    Subject.objects.create(name='فارسی دهم', grade='10')
    assert _names(curriculum_subjects(student)) == ['ریاضیات هفتم']


def test_a_theology_student_at_12_sees_shared_and_own_but_not_humanities():
    """The contract case against the real catalog shape: a معارف دوازدهمی sees the
    merged shared «فارسی ۳» and theology-only «جریان‌شناسی اندیشه‌های معاصر», but
    never humanities-only «تاریخ ۳» (theology's own is «تاریخ ۳ (تخصصی رشته)»)."""
    student = _student(grade='12', major='theology')
    Subject.objects.create(name='فارسی ۳', grade='12')                        # merged → null
    Subject.objects.create(name='جریان‌شناسی اندیشه‌های معاصر', grade='12', major='theology')
    Subject.objects.create(name='تاریخ ۳', grade='12', major='humanities')
    Subject.objects.create(name='تاریخ ۳ (تخصصی رشته)', grade='12', major='theology')
    assert set(_names(curriculum_subjects(student))) == {
        'فارسی ۳', 'جریان‌شناسی اندیشه‌های معاصر', 'تاریخ ۳ (تخصصی رشته)',
    }


def test_a_merged_null_row_is_visible_to_every_major_of_the_grade():
    """Consequence accepted by the owner: rows merged to ``major=null`` derive for
    every major of that grade — here checked across all four live majors."""
    Subject.objects.create(name='مدیریت خانواده و سبک زندگی', grade='12')     # merged
    for major in ('math', 'science', 'humanities', 'theology'):
        student = _student(grade='12', major=major, username=f'merged_{major}')
        assert _names(curriculum_subjects(student)) == ['مدیریت خانواده و سبک زندگی']
