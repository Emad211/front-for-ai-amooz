"""Tests for real student enrollment + per-unit progress + teacher rosters.

All mocked / DB-only — no LLM calls.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.classes.models import (
    ClassCreationSession,
    ClassFinalExam,
    ClassInvitation,
    ClassSection,
    ClassSectionQuiz,
    ClassUnit,
    Enrollment,
    StudentUnitProgress,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


def _make_published_class(teacher, *, n_sections=2, units_per_section=2, title='C'):
    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title=title,
        description='d',
        source_file=SimpleUploadedFile('a.ogg', b'x', content_type='audio/ogg'),
        source_mime_type='audio/ogg',
        source_original_name='a.ogg',
        status=ClassCreationSession.Status.RECAPPED,
        transcript_markdown='t',
        structure_json='{"root_object": {"title": "x"}, "outline": []}',
        pipeline_type=ClassCreationSession.PipelineType.CLASS,
        is_published=True,
    )
    for s in range(n_sections):
        sec = ClassSection.objects.create(
            session=session, external_id=f'sec-{s + 1}', order=s + 1, title=f'Section {s + 1}',
        )
        for u in range(units_per_section):
            ClassUnit.objects.create(
                session=session, section=sec, external_id=f'sec-{s + 1}-u-{u + 1}',
                order=u + 1, title=f'Unit {s + 1}.{u + 1}', content_markdown='c',
            )
    return session


def _student(phone='09120000001', username='stu1'):
    return User.objects.create_user(username=username, password='p', role=User.Role.STUDENT, phone=phone)


def _teacher(username='teach1'):
    return User.objects.create_user(username=username, password='p', role=User.Role.TEACHER, phone='09150000000')


# ---------------------------------------------------------------------------
# progress service
# ---------------------------------------------------------------------------

def test_mark_unit_complete_creates_enrollment_and_progress():
    from apps.classes.services.progress import lesson_progress_percent, mark_unit_complete

    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=1, units_per_section=4)
    unit = ClassUnit.objects.filter(session=session).first()

    mark_unit_complete(session=session, student=student, unit=unit)

    assert Enrollment.objects.filter(session=session, student=student).exists()
    assert StudentUnitProgress.objects.filter(session=session, student=student).count() == 1
    # 1 of 4 units complete -> 25% content progress
    assert lesson_progress_percent(session=session, student=student) == 25


def test_mark_unit_complete_is_idempotent():
    from apps.classes.services.progress import mark_unit_complete

    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=1, units_per_section=2)
    unit = ClassUnit.objects.filter(session=session).first()

    mark_unit_complete(session=session, student=student, unit=unit)
    mark_unit_complete(session=session, student=student, unit=unit)
    assert StudentUnitProgress.objects.filter(session=session, student=student).count() == 1


def test_quiz_pass_completes_section_units():
    from apps.classes.services.progress import lesson_progress_percent, mark_section_units_complete

    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=2, units_per_section=2)  # 4 units
    section = ClassSection.objects.filter(session=session).first()

    mark_section_units_complete(session=session, student=student, section=section)
    # one of two sections (2 of 4 units) complete -> 50%
    assert lesson_progress_percent(session=session, student=student) == 50


def test_progress_caps_at_total_when_units_removed():
    from apps.classes.services.progress import lesson_progress_percent

    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=1, units_per_section=2)
    # An orphan progress row for a unit that no longer exists must not exceed 100%.
    StudentUnitProgress.objects.create(session=session, student=student, unit_external_id='sec-1-u-1')
    StudentUnitProgress.objects.create(session=session, student=student, unit_external_id='ghost')
    assert lesson_progress_percent(session=session, student=student) <= 100


# ---------------------------------------------------------------------------
# mark-lesson-complete endpoint
# ---------------------------------------------------------------------------

def test_mark_lesson_complete_endpoint_by_external_id():
    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=1, units_per_section=2)
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='X1')

    client = APIClient()
    client.force_authenticate(user=student)
    res = client.post(f'/api/classes/student/courses/{session.id}/lessons/sec-1-u-1/complete/')
    assert res.status_code == 200
    assert res.data['isCompleted'] is True
    assert res.data['progress'] == 50
    assert StudentUnitProgress.objects.filter(session=session, student=student).count() == 1


def test_mark_lesson_complete_endpoint_by_pk():
    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=1, units_per_section=2)
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='X2')
    unit = ClassUnit.objects.filter(session=session).first()

    client = APIClient()
    client.force_authenticate(user=student)
    res = client.post(f'/api/classes/student/courses/{session.id}/lessons/{unit.id}/complete/')
    assert res.status_code == 200
    # progress keyed by external_id even when called with the pk
    assert StudentUnitProgress.objects.filter(
        session=session, student=student, unit_external_id=unit.external_id,
    ).exists()


def test_mark_lesson_complete_requires_invite():
    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=1, units_per_section=1)
    # No invite for this student -> cannot access.
    client = APIClient()
    client.force_authenticate(user=student)
    res = client.post(f'/api/classes/student/courses/{session.id}/lessons/sec-1-u-1/complete/')
    assert res.status_code == 404


def test_content_view_enrolls_and_marks_completed():
    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=1, units_per_section=2)
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='X3')
    StudentUnitProgress.objects.create(session=session, student=student, unit_external_id='sec-1-u-1')

    client = APIClient()
    client.force_authenticate(user=student)
    res = client.get(f'/api/classes/student/courses/{session.id}/content/')
    assert res.status_code == 200
    # opening content lazily enrolls the student
    assert Enrollment.objects.filter(session=session, student=student).exists()
    lessons = res.data['chapters'][0]['lessons']
    completed = {l['title']: l['isCompleted'] for l in lessons}
    assert completed['Unit 1.1'] is True
    assert completed['Unit 1.2'] is False


# ---------------------------------------------------------------------------
# teacher rosters (real stats)
# ---------------------------------------------------------------------------

def test_teacher_students_list_real_stats():
    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=2, units_per_section=2)  # 4 units
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='X4')

    # 2 of 4 units complete + a passed quiz (80) and final (90) -> avg 85, active.
    from apps.classes.services.progress import touch_enrollment
    touch_enrollment(session=session, student=student)
    StudentUnitProgress.objects.create(session=session, student=student, unit_external_id='sec-1-u-1')
    StudentUnitProgress.objects.create(session=session, student=student, unit_external_id='sec-1-u-2')
    section = ClassSection.objects.filter(session=session).first()
    ClassSectionQuiz.objects.create(session=session, section=section, student=student, last_score_0_100=80)
    ClassFinalExam.objects.create(session=session, student=student, last_score_0_100=90)

    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.get('/api/classes/teacher/students/')
    assert res.status_code == 200
    row = next(r for r in res.data if r['phone'] == student.phone)
    assert row['completedLessons'] == 2
    assert row['totalLessons'] == 4
    assert row['averageScore'] == 85
    assert row['status'] == 'active'
    assert row['performance'] == 'excellent'


def test_session_students_roster_endpoint():
    teacher = _teacher()
    student = _student()
    session = _make_published_class(teacher, n_sections=1, units_per_section=4)
    ClassInvitation.objects.create(session=session, phone=student.phone, invite_code='X5')
    Enrollment.objects.create(session=session, student=student)
    StudentUnitProgress.objects.create(session=session, student=student, unit_external_id='sec-1-u-1')

    client = APIClient()
    client.force_authenticate(user=teacher)
    res = client.get(f'/api/classes/creation-sessions/{session.id}/students/')
    assert res.status_code == 200
    assert len(res.data) == 1
    row = res.data[0]
    assert row['phone'] == student.phone
    assert row['completedLessons'] == 1
    assert row['totalLessons'] == 4
    assert row['progress'] == 25


def test_session_students_roster_forbidden_for_other_teacher():
    teacher = _teacher()
    other = _teacher(username='teach2')
    session = _make_published_class(teacher, n_sections=1, units_per_section=1)

    client = APIClient()
    client.force_authenticate(user=other)
    res = client.get(f'/api/classes/creation-sessions/{session.id}/students/')
    assert res.status_code == 404
