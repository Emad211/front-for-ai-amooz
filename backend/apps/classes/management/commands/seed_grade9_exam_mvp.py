from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path
from typing import TypedDict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from pydantic import ValidationError

from apps.accounts.models import StudentProfile
from apps.commons.phone_utils import is_valid_iran_mobile, normalize_phone
from apps.classes.models import ClassCreationSession, ClassInvitation
from apps.classes.services.invite_codes import get_or_create_invite_code_for_phone
from apps.classes.services.schemas import ExamPrepOutput

User = get_user_model()
SESSION_CLIENT_REQUEST_ID = uuid.UUID("7f45e9e1-7e6f-4a32-9d91-2c9e9b8d6a01")
TEACHER_USERNAME = "grade9_demo_teacher"
DEFAULT_PASSWORD = "grade9-demo-123"
DEFAULT_STUDENTS = tuple(
    (f"Grade 9 Student {index:02d}", f"091290900{index:02d}", DEFAULT_PASSWORD)
    for index in range(1, 11)
)
DEFAULT_EXAM = {
    "exam_prep": {
        "title": "Grade 9 Exam Prep Demo",
        "questions": [
            {
                "question_id": "grade9-demo-q1",
                "question_text_markdown": "Which number is prime?",
                "options": ["الف) ۹", "ب) ۱۱", "ج) ۱۵", "د) ۲۱"],
                "correct_option_label": "ب",
                "teacher_solution_markdown": "Eleven has no divisors other than 1 and itself.",
            }
        ],
    }
}


class StudentRow(TypedDict):
    name: str
    phone: str
    password: str


class Command(BaseCommand):
    help = "Seed the shared grade-9 Exam Prep demo without sending SMS."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--session-id", type=int, help="Existing published Exam Prep session ID.")
        group.add_argument("--from-exam-json", type=str, help="JSON file following the exam_prep_json contract.")
        parser.add_argument(
            "--students-file",
            help="Optional JSON array/object or CSV with name, phone, password columns; defaults to ten deterministic students.",
        )

    def handle(self, *args, **options):
        students = self._load_students(options.get("students_file"))
        with transaction.atomic():
            teacher = self._get_teacher()
            session = self._get_session(teacher, options.get("session_id"), options.get("from_exam_json"))
            credentials = [self._seed_student(session, row, index) for index, row in enumerate(students, start=1)]
        self.stdout.write(self.style.SUCCESS(f"Seeded shared grade-9 exam: session {session.pk} ({session.title})"))
        self.stdout.write("username\tphone\tpassword\tinvite_code")
        for credential in credentials:
            self.stdout.write("\t".join(credential))

    def _get_teacher(self):
        teacher, created = User.objects.get_or_create(
            username=TEACHER_USERNAME,
            defaults={"role": User.Role.TEACHER, "email": "grade9-demo-teacher@example.com"},
        )
        if created or not teacher.has_usable_password():
            teacher.set_password("grade9-teacher-123")
        teacher.role = User.Role.TEACHER
        teacher.save(update_fields=["password", "role"])
        return teacher

    def _get_session(self, teacher, session_id: int | None, exam_path: str | None):
        if session_id is not None:
            try:
                session = ClassCreationSession.objects.get(pk=session_id)
            except ClassCreationSession.DoesNotExist as exc:
                raise CommandError(f"Exam Prep session {session_id} was not found.") from exc
            if session.pipeline_type != ClassCreationSession.PipelineType.EXAM_PREP or not session.is_published:
                raise CommandError("--session-id must refer to a published EXAM_PREP session.")
            return session

        exam_json = self._load_exam_json(Path(exam_path) if exam_path else None)
        title = exam_json["exam_prep"].get("title") or DEFAULT_EXAM["exam_prep"]["title"]
        session, _created = ClassCreationSession.objects.get_or_create(
            teacher=teacher,
            client_request_id=SESSION_CLIENT_REQUEST_ID,
            defaults={
                "title": title,
                "description": "Shared Grade 9 Exam Prep demo.",
                "pipeline_type": ClassCreationSession.PipelineType.EXAM_PREP,
                "source_type": ClassCreationSession.SourceType.MEDIA,
                "status": ClassCreationSession.Status.EXAM_STRUCTURED,
                "exam_prep_json": json.dumps(exam_json, ensure_ascii=False),
                "is_published": True,
                "published_at": timezone.now(),
                "source_file": "",
            },
        )
        return session

    def _seed_student(self, session, row: StudentRow, index: int) -> tuple[str, str, str, str]:
        username = f"grade9_student_{index:02d}"
        student, _created = User.objects.get_or_create(
            username=username,
            defaults={"role": User.Role.STUDENT, "phone": row["phone"], "first_name": row["name"]},
        )
        student.role = User.Role.STUDENT
        student.phone = row["phone"]
        student.first_name = row["name"]
        student.set_password(row["password"])
        student.is_profile_completed = True
        student.save()
        profile, _created = StudentProfile.objects.get_or_create(user=student)
        profile.grade = "09"
        profile.school = profile.school or "Grade 9 Demo School"
        profile.save(update_fields=["grade", "school"])
        invite_code = get_or_create_invite_code_for_phone(row["phone"])
        ClassInvitation.objects.get_or_create(session=session, phone=row["phone"], defaults={"invite_code": invite_code})
        return username, row["phone"], row["password"], invite_code

    def _load_exam_json(self, path: Path | None) -> dict:
        data = DEFAULT_EXAM if path is None else self._read_json(path)
        try:
            validated = ExamPrepOutput.model_validate(data)
        except ValidationError as exc:
            raise CommandError(f"Exam JSON does not follow the exam_prep_json contract: {exc}") from exc
        return data

    def _load_students(self, path: str | None) -> list[StudentRow]:
        if path is None:
            rows = [
                {"name": name, "phone": phone, "password": password}
                for name, phone, password in DEFAULT_STUDENTS
            ]
        else:
            source = Path(path)
            if source.suffix.lower() == ".csv":
                with source.open(encoding="utf-8", newline="") as roster_file:
                    rows = list(csv.DictReader(roster_file))
            else:
                rows = self._read_json(source)
        if isinstance(rows, dict):
            rows = rows.get("students")
        if not isinstance(rows, list) or not rows:
            raise CommandError("Students file must contain a non-empty array or a students array.")
        cleaned: list[StudentRow] = []
        for row in rows:
            if not isinstance(row, dict) or not all(str(row.get(key, "")).strip() for key in ("name", "phone")):
                raise CommandError("Each student row requires name and phone.")
            phone = normalize_phone(row["phone"])
            if not phone or not is_valid_iran_mobile(phone):
                raise CommandError("Each student row requires a valid Iranian mobile phone.")
            cleaned.append({"name": str(row["name"]).strip(), "phone": phone, "password": str(row.get("password") or DEFAULT_PASSWORD)})
        if len(cleaned) != 10 or len({row["phone"] for row in cleaned}) != 10:
            raise CommandError("The grade-9 demo requires exactly ten students with unique phones.")
        return cleaned

    def _read_json(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read JSON file {path}: {exc}") from exc
