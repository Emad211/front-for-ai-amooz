import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.classes.models import ClassCreationSession, ClassInvitation, StudentInviteCode

User = get_user_model()

pytestmark = pytest.mark.django_db


def _run(*args: str) -> str:
    output = StringIO()
    call_command("seed_grade9_exam_mvp", *args, stdout=output)
    return output.getvalue()


def test_from_json_seeds_published_exam_students_and_permanent_codes(tmp_path):
    exam_file = tmp_path / "exam.json"
    exam_file.write_text(
        json.dumps(
            {
                "exam_prep": {
                    "title": "نهم علوم",
                    "questions": [
                        {
                            "question_id": "q1",
                            "question_text_markdown": "آب در چند درجه می‌جوشد؟",
                            "options": ["الف) ۰", "ب) ۱۰۰"],
                            "correct_option_label": "ب",
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    output = _run("--from-exam-json", str(exam_file))

    session = ClassCreationSession.objects.get(title="نهم علوم")
    assert session.pipeline_type == ClassCreationSession.PipelineType.EXAM_PREP
    assert session.status == ClassCreationSession.Status.EXAM_STRUCTURED
    assert session.is_published is True
    assert session.exam_prep_json
    assert User.objects.filter(role=User.Role.STUDENT, studentprofile__grade="09").count() == 10
    assert ClassInvitation.objects.filter(session=session).count() == 10
    assert StudentInviteCode.objects.count() == 10
    assert "username" in output
    assert "INV-" in output

    for student in User.objects.filter(role=User.Role.STUDENT):
        assert student.has_usable_password()
        assert student.phone
        assert student.studentprofile.grade == "09"


def test_rerun_is_idempotent_and_preserves_credentials(tmp_path):
    exam_file = tmp_path / "exam.json"
    exam_file.write_text(json.dumps({"exam_prep": {"title": "Grade 9", "questions": []}}), encoding="utf-8")

    _run("--from-exam-json", str(exam_file))
    first_counts = (
        ClassCreationSession.objects.count(),
        User.objects.filter(role=User.Role.STUDENT).count(),
        ClassInvitation.objects.count(),
        StudentInviteCode.objects.count(),
    )
    first_student = User.objects.get(username="grade9_student_01")
    assert first_student.check_password("grade9-demo-123")

    _run("--from-exam-json", str(exam_file))

    assert (
        ClassCreationSession.objects.count(),
        User.objects.filter(role=User.Role.STUDENT).count(),
        ClassInvitation.objects.count(),
        StudentInviteCode.objects.count(),
    ) == first_counts
    first_student.refresh_from_db()
    assert first_student.check_password("grade9-demo-123")


def test_session_id_requires_published_exam_prep_session():
    teacher = User.objects.create_user(username="owner", password="password", role=User.Role.TEACHER)
    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title="Draft",
        pipeline_type=ClassCreationSession.PipelineType.CLASS,
        status=ClassCreationSession.Status.STRUCTURED,
        source_file="",
    )

    with pytest.raises(CommandError, match="published EXAM_PREP"):
        _run("--session-id", str(session.pk))


def test_session_id_attaches_students_to_existing_published_exam():
    teacher = User.objects.create_user(username="owner", password="password", role=User.Role.TEACHER)
    session = ClassCreationSession.objects.create(
        teacher=teacher,
        title="Published Grade 9",
        pipeline_type=ClassCreationSession.PipelineType.EXAM_PREP,
        status=ClassCreationSession.Status.EXAM_STRUCTURED,
        is_published=True,
        source_file="",
    )

    _run("--session-id", str(session.pk))

    assert ClassCreationSession.objects.count() == 1
    assert ClassInvitation.objects.filter(session=session).count() == 10


def test_roster_json_overrides_default_names_and_phones(tmp_path):
    exam_file = tmp_path / "exam.json"
    exam_file.write_text(json.dumps({"exam_prep": {"title": "Grade 9", "questions": []}}), encoding="utf-8")
    roster_file = tmp_path / "roster.json"
    roster_file.write_text(
        json.dumps(
            [
                {
                    "name": "A Student" if index == 1 else f"Student {index}",
                    "phone": f"091200000{index:02d}",
                    "password": "demo-pass-1" if index == 1 else "demo-pass",
                }
                for index in range(1, 11)
            ]
        ),
        encoding="utf-8",
    )

    _run("--from-exam-json", str(exam_file), "--students-file", str(roster_file))

    student = User.objects.get(username="grade9_student_01")
    assert student.first_name == "A Student"
    assert student.phone == "09120000001"
    assert student.check_password("demo-pass-1")


def test_roster_normalizes_iran_country_code_and_spacing(tmp_path):
    exam_file = tmp_path / "exam.json"
    exam_file.write_text(json.dumps({"exam_prep": {"title": "Grade 9", "questions": []}}), encoding="utf-8")
    roster_file = tmp_path / "roster.json"
    roster_file.write_text(
        json.dumps(
            [
                {
                    "name": f"Student {index}",
                    "phone": f"+98 912 000 00{index:02d}" if index == 1 else f"091200000{index:02d}",
                    "password": "demo-pass",
                }
                for index in range(1, 11)
            ]
        ),
        encoding="utf-8",
    )

    output = _run("--from-exam-json", str(exam_file), "--students-file", str(roster_file))

    student = User.objects.get(username="grade9_student_01")
    assert student.phone == "09120000001"
    assert ClassInvitation.objects.get(session__title="Grade 9", phone="09120000001")
    assert "grade9_student_01\t09120000001\tdemo-pass" in output


def test_roster_rejects_duplicate_canonical_phones(tmp_path):
    roster_file = tmp_path / "roster.json"
    roster_file.write_text(
        json.dumps(
            [
                {
                    "name": f"Student {index}",
                    "phone": "+98 912 000 0001" if index == 2 else f"091200000{index:02d}",
                }
                for index in range(1, 11)
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="unique phones"):
        _run("--from-exam-json", "missing-exam.json", "--students-file", str(roster_file))

    assert User.objects.filter(username__startswith="grade9_student_").count() == 0


def test_rerun_with_changed_password_resets_and_prints_actual_password(tmp_path):
    exam_file = tmp_path / "exam.json"
    exam_file.write_text(json.dumps({"exam_prep": {"title": "Grade 9", "questions": []}}), encoding="utf-8")
    first_roster = tmp_path / "first-roster.json"
    second_roster = tmp_path / "second-roster.json"
    first_roster.write_text(
        json.dumps(
            [{"name": f"Student {index}", "phone": f"091200000{index:02d}", "password": "old-pass"} for index in range(1, 11)]
        ),
        encoding="utf-8",
    )
    second_roster.write_text(
        json.dumps(
            [{"name": f"Student {index}", "phone": f"091200000{index:02d}", "password": "new-pass"} for index in range(1, 11)]
        ),
        encoding="utf-8",
    )

    _run("--from-exam-json", str(exam_file), "--students-file", str(first_roster))
    output = _run("--from-exam-json", str(exam_file), "--students-file", str(second_roster))

    student = User.objects.get(username="grade9_student_01")
    assert student.check_password("new-pass")
    assert not student.check_password("old-pass")
    assert "grade9_student_01\t09120000001\tnew-pass" in output
